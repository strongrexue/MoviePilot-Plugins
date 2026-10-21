"""发现流水线编排：拉取 → 归一 → 去重 → 过滤 → 写入。

流程对应开发文档 §7.1。两条纪律贯穿全文件：

1. **单源失败不得阻塞其他源** —— 每个源独立 ``try/except``，失败只记录；
2. **宁缺毋滥** —— 没有确定性身份的条目进待确认列表，绝不写入。

``select_items()`` 是纯函数（不碰网络、不碰宿主），因此过滤/去重/配额逻辑
全部可离线单测（开发文档 §14.1）；``run_pipeline()`` 只负责把它们串起来。
"""
import asyncio
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from .blacklist import BlacklistRules, check_item, check_keywords, rules_from_config
from .constants import (
    DECISION_PENDING_REVIEW,
    DECISION_SKIPPED_BLACKLIST,
    DECISION_SKIPPED_DUPLICATE,
    DECISION_SKIPPED_NO_DATE,
    DECISION_SKIPPED_NOT_FUTURE,
    DECISION_SKIPPED_OUT_OF_WINDOW,
    DECISION_SKIPPED_POPULARITY,
    DECISION_SKIPPED_RATING,
    DECISION_SKIPPED_WANT,
)
from .identity import IdentityResolver, normalize_title
from .model import DiscoveredItem, item_sort_key
from .window import in_window, local_now_text, parse_date, today, utc_now_text
from .writer import SubscriptionWriter, WriteOutcome, WriteReport

#: TMDB 关键词查询函数签名：``(media_type, tmdb_id) -> [keyword, ...]``
KeywordLookup = Callable[[str, str], Awaitable[Sequence[str]]]



class SourceAdapter(Protocol):
    """数据源适配器契约。

    实现方负责「取数 + 归一」，**不负责**去重、过滤、写订阅。
    """

    @property
    def name(self) -> str:
        """源标识（对应 :mod:`core.constants` 里的 ``SOURCE_*``）。"""
        ...

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """拉取并归一为发现条目；上游异常直接抛出，由流水线捕获。"""
        ...


@dataclass
class SourceResult:
    """单个源的拉取结果。"""

    source: str
    items: List[DiscoveredItem] = field(default_factory=list)
    error: str = ""
    skipped: bool = False

    @property
    def ok(self) -> bool:
        """该源是否成功（未跳过且无异常）。"""
        return not self.skipped and not self.error


@dataclass
class RunSummary:
    """一次完整运行的汇总。"""

    sources: List[SourceResult] = field(default_factory=list)
    selected: List[DiscoveredItem] = field(default_factory=list)
    prefiltered: List[WriteOutcome] = field(default_factory=list)
    report: Optional[WriteReport] = None
    dry_run: bool = False
    #: 源内去重时被丢弃的条目数（不进流水，但要计入总数才能对账）
    deduped_out: int = 0
    started_at: str = ""
    finished_at: str = ""

    @property
    def failed_sources(self) -> List[str]:
        """失败的源标识列表。"""
        return [s.source for s in self.sources if s.error]

    @property
    def fetched_count(self) -> int:
        """所有源拉取到的原始条目总数。"""
        return sum(len(s.items) for s in self.sources)

    def to_summary(self) -> Dict[str, Any]:
        """汇总字典（状态接口 / 通知共用）。"""
        report = self.report.to_summary() if self.report else {}
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
                "fetched": self.fetched_count,
            "prefiltered": len(self.prefiltered),
            "rejected_reasons": self._rejected_reasons(),
            "sources": [
                {
                    "source": s.source,
                    "count": len(s.items),
                    "error": s.error,
                    "skipped": s.skipped,
                }
                for s in self.sources
            ],
            "failed_sources": self.failed_sources,
            # 注意顺序：report 的键（total/added/skipped/pending_review）覆盖上面的派生值。
            # 但 writer 的 skipped 只统计 writer 自己产生的跳过，**不含**预过滤阶段被
            # 拦下的条目 —— 那部分必须在这里补，否则会出现「拉取 100 / 跳过 0」的假象
            # （0.2.0 真实事故）。
            **report,
            "skipped": self.skipped_count(report),
            "pending_review": self.pending_count(report),
            "deduped_out": self.deduped_out,
            "total": self.fetched_count,
        }

    def skipped_count(self, report: Optional[Dict[str, Any]] = None) -> int:
        """返回真正跳过的总条数（含预过滤阶段，**不含**待确认）。

        :param report: 已算好的 ``report.to_summary()``，避免重复计算
        """
        data = report if report is not None else (self.report.to_summary() if self.report else {})
        return int(data.get("skipped", 0)) + len(self._prefiltered_skipped())

    def pending_count(self, report: Optional[Dict[str, Any]] = None) -> int:
        """待确认总数（writer 产出 + 预过滤阶段）。

        跳过与待确认必须**互斥**，否则通知里「跳过 + 待确认」会超过「拉取」。
        真机就是这样：跳过 341 里其实包含了 18 条待确认。
        """
        data = report if report is not None else (self.report.to_summary() if self.report else {})
        return int(data.get("pending_review", 0)) + len(self._prefiltered_pending())

    def _prefiltered_skipped(self) -> List[WriteOutcome]:
        """预过滤阶段的**真正跳过**（不含待确认）。"""
        return [o for o in self.prefiltered if o.decision != DECISION_PENDING_REVIEW]

    def _prefiltered_pending(self) -> List[WriteOutcome]:
        """预过滤阶段的待确认。"""
        return [o for o in self.prefiltered if o.decision == DECISION_PENDING_REVIEW]

    def _rejected_reasons(self) -> Dict[str, int]:
        """按决策统计被预过滤拦下的条目数，便于一眼看出为什么一条都没写。"""
        counts: Dict[str, int] = {}
        for outcome in self.prefiltered:
            key = outcome.decision or "unknown"
            counts[key] = counts.get(key, 0) + 1
        return counts


# --------------------------------------------------------------------- 纯逻辑

def dedupe_within_source(items: Sequence[DiscoveredItem]) -> List[DiscoveredItem]:
    """第一层去重：``source + source_id`` 唯一，再按标题兜底。

    同一 ``source_id`` 重复出现时**保留先出现的**（源实现通常已按重要性排序）。

    .. important::
       还要按「标准化标题 + 年份 + 类型」再兜一次。真机原因：豆瓣不同路线的
       结构不同 —— ``/douban/tv/coming`` 带 ``<link>``（有 subject id，作为
       source_id），而 ``/douban/list/*`` 的 ``<link>`` 是空的（只能用标题造
       source_id）。同一部剧同时出现在两类路线里时 source_id 不同，会被当成
       两条：重复占用额度，也让待确认列表出现成对重复（真机：伊甸园之东、
       流人 第六季、爱上草莓的季节 各出现两次）。
       合并时**优先保留带原生 id 的那条**（能省一次标题搜索）。
    """
    seen: set = set()
    first_pass: List[DiscoveredItem] = []
    for item in items:
        key = (item.source, item.source_id)
        if key in seen:
            continue
        seen.add(key)
        first_pass.append(item)

    kept: List[DiscoveredItem] = []
    index: Dict[tuple, List[int]] = {}
    for item in first_pass:
        title = normalize_title(item.title)
        if not title:
            kept.append(item)
            continue
        title_key = (item.source, title, str(item.year or ""), item.media_type)
        positions = index.setdefault(title_key, [])
        merged = False
        for position in positions:
            existing = kept[position]
            # 两条都带原生 id -> 是不同的作品（同名），不合并
            if existing.native_ids and item.native_ids:
                if existing.source_id == item.source_id:
                    merged = True
                    break
                continue
            # 只有一方带原生 id 或都没带 -> 视为同一部剧，带 id 的优先保留
            if not existing.native_ids and item.native_ids:
                kept[position] = item
            merged = True
            break
        if not merged:
            positions.append(len(kept))
            kept.append(item)
    return kept


def dedupe_cross_source(items: Sequence[DiscoveredItem]) -> Tuple[List[DiscoveredItem], List[DiscoveredItem]]:
    """第二层去重：跨源按解析后的确定性身份合并。

    无确定性身份的条目（``resolved is None``）**不参与合并** —— 它们本来就
    不会被写入，合并它们只会让待确认列表变短、丢失排查线索。

    :return: ``(保留条目, 被合并掉的条目)``
    """
    best: Dict[str, DiscoveredItem] = {}
    dropped: List[DiscoveredItem] = []
    unresolved: List[DiscoveredItem] = []

    for item in items:
        if not item.resolved:
            unresolved.append(item)
            continue
        key = item.resolved.as_key()
        existing = best.get(key)
        if existing is None:
            best[key] = item
            continue
        # 同身份多来源：保留「定档日期更早，其次评分更高」的那条
        if item_sort_key(item) < item_sort_key(existing):
            dropped.append(existing)
            best[key] = item
        else:
            dropped.append(item)

    kept = list(best.values()) + unresolved
    kept.sort(key=item_sort_key)
    dropped.sort(key=item_sort_key)
    return kept, dropped


def filter_by_rating(item: DiscoveredItem, min_rating: float) -> bool:
    """评分过滤：``None`` 视为「无评分」——不拦截（由关注度与窗口把关）。

    只有**明确低于**阈值时才拦截，避免源缺评分字段就整批丢弃。
    """
    if item.rating is None:
        return True
    try:
        return float(item.rating) >= float(min_rating)
    except (TypeError, ValueError):
        return True


def filter_by_popularity(item: DiscoveredItem, min_popularity: float) -> bool:
    """关注度过滤 —— 未来档期条目**唯一可用**的质量信号。

    为什么必须有这一层：未来 30 天要上映的片子几乎都没有评分（``vote_average=0``），
    而同一天上映的冷门片会挤满日期升序列表。0.2.2 真实事故：写入的 29 条全是
    ``Black Ink`` / ``Ghost Lake`` / ``FLESH!`` 这类 popularity 个位数的片子，
    把每日 30 条额度全吃掉了。

    ``popularity`` 缺失（``None``）时**放行** —— 不同源字段可用性不同，
    不能因为缺字段就丢弃；宁可由评分与窗口把关。
    """
    if item.popularity is None:
        return True
    try:
        return float(item.popularity) >= float(min_popularity)
    except (TypeError, ValueError):
        return True


def selection_sort_key(item: DiscoveredItem) -> tuple:
    """候选写入顺序：**关注度降序**优先，其次定档日期升序。

    原来按日期升序写，等于「先订今天上映的」——而被挤在最前面的恰恰是
    冷门同日上映片。改成关注度优先后，额度会先花在真正受关注的作品上。
    """
    return (
        -(item.popularity or 0.0),
        item.release_date or "9999-99-99",
        item.source,
        item.title_year,
    )


def filter_by_window(
    item: DiscoveredItem,
    future_days: int,
    *,
    tz_name: Optional[str] = None,
    now: Any = None,
) -> bool:
    """窗口过滤：只保留「今天 ~ 今天+N 天」内的条目。

    无定档日期 → 拦截（无法判断「即将开播」，宁缺毋滥）。
    """
    release = parse_date(item.release_date, tz_name)
    if release is None:
        return False
    return in_window(release, future_days, tz_name=tz_name, now=now)


def filter_blacklist(
    items: Sequence[DiscoveredItem],
    rules: BlacklistRules,
) -> Tuple[List[DiscoveredItem], List[WriteOutcome]]:
    """黑名单第一层：类型 + 题材词（同步、零请求）。

    **必须放在身份解析之前**（:func:`run_pipeline` 第 2.5 步）：
    命中的条目不该再花一次 TMDB 请求去解析身份。参考插件 doubancenter 也在
    同一位置拦，实测每轮省下几十次网络往返。

    这一层覆盖：

    - ``排除类型``：条目自带 ``genre_ids``（TMDB 源）或中英文字样（豆瓣/AniList）
      反查出的 TMDB genre id；
    - ``排除题材``：片名 / 原名，以及来源给的题材串（豆瓣 ``category`` 里
      ``剧情 同性 犯罪`` 这种中文字样正是「同性剧」唯一可靠的免费信号）。

    :return: ``(放行条目, 被拦的 WriteOutcome 列表)``
    """
    if not rules.active:
        return list(items), []
    kept: List[DiscoveredItem] = []
    rejected: List[WriteOutcome] = []
    for item in items:
        reason = check_item(rules, item)
        if reason:
            rejected.append(
                WriteOutcome(item=item, decision=DECISION_SKIPPED_BLACKLIST, reason=reason)
            )
            continue
        kept.append(item)
    return kept, rejected


async def filter_blacklist_keywords(
    items: Sequence[DiscoveredItem],
    rules: BlacklistRules,
    lookup: Optional[KeywordLookup],
    *,
    concurrency: int = 4,
) -> Tuple[List[DiscoveredItem], List[WriteOutcome]]:
    """黑名单第二层：TMDB keyword（有请求成本，只对即将写入的条目查）。

    ``blacklist_tmdb_keywords`` 默认关 —— 每条要多一次详情请求。开启后也只
    作用于「已通过全部其它过滤」的少量条目（:func:`run_pipeline` 第 5 步之前），
    不会把请求量摊到几百条候选上。

    查不到关键词时**放行**（fail-open）：网络抖动不该让整轮发现把该订的条目
    全丢掉；宁可漏拦一条，也不能错杀一批。
    """
    if not rules.active or not rules.tmdb_keywords or not rules.words or lookup is None:
        return list(items), []
    if not items:
        return [], []

    width = max(1, int(concurrency or 1))
    semaphore = asyncio.Semaphore(width)

    async def one(item: DiscoveredItem) -> Optional[str]:
        resolved = item.resolved
        if not resolved or not resolved.media_id:
            return ""
        async with semaphore:
            try:
                keywords = await lookup(item.media_type, str(resolved.media_id))
            except Exception:  # noqa: BLE001 - fail-open（见 docstring）
                return ""
        return check_keywords(rules, keywords or ())

    reasons = list(await asyncio.gather(*(one(item) for item in items)))
    kept: List[DiscoveredItem] = []
    rejected: List[WriteOutcome] = []
    for item, reason in zip(items, reasons):
        if reason:
            rejected.append(
                WriteOutcome(item=item, decision=DECISION_SKIPPED_BLACKLIST, reason=reason)
            )
            continue
        kept.append(item)
    return kept, rejected


def select_items(
    items: Sequence[DiscoveredItem],
    *,
    future_days: int,
    min_rating: float,
    min_popularity: float = 0.0,
    min_want: float = 0.0,
    tz_name: Optional[str] = None,
    now: Any = None,
    future_days_by_source: Optional[Dict[str, int]] = None,
    min_rating_by_source: Optional[Dict[str, float]] = None,
    min_popularity_by_source: Optional[Dict[str, float]] = None,
) -> Tuple[List[DiscoveredItem], List[WriteOutcome]]:
    """对（已解析身份的）条目做过滤，返回 ``(通过, 被拦下的带原因结果)``。

    顺序：源内去重 → 跨源去重 → 评分 → 关注度 → 窗口。
    被拦下的条目也返回，便于流水线写入「跳过原因」日志。

    :param min_popularity: 最低关注度；``<=0`` 表示不过滤
    :param future_days_by_source: 按源覆盖窗口天数。**必须按源区分**：
        TMDB 与 Bangumi 的窗口是各自配置的，用同一个值会把窗口更窄的源
        的条目错误放行、或把更宽的源错误拦下。
    :param min_rating_by_source: 按源覆盖评分门槛。TMDB 与 Bangumi 的评分
        量纲不同（Bangumi 的评分普遍更高），共用一个门槛不合理。
    """
    within = dedupe_within_source(items)
    kept, dropped = dedupe_cross_source(within)

    rejected: List[WriteOutcome] = [
        WriteOutcome(
            item=item,
            decision=DECISION_SKIPPED_DUPLICATE,
            reason=f"跨源重复，已保留同身份的另一条（{item.resolved.as_key() if item.resolved else '—'}）",
        )
        for item in dropped
    ]

    passed: List[DiscoveredItem] = []
    window_map = future_days_by_source or {}
    rating_map = min_rating_by_source or {}
    popularity_map = min_popularity_by_source or {}
    for item in kept:
        # 按源取各自的评分门槛与窗口天数（TMDB / Bangumi 的配置是分开的）
        rating_threshold = rating_map.get(item.source, min_rating)
        window_days = window_map.get(item.source, future_days)
        # 热度门槛也必须按源区分：TMDB popularity 中位数约 3（>=15 算热门），
        # 而 AniList popularity 冷门番也有上千，共用 15 等于完全不过滤。
        popularity_threshold = popularity_map.get(item.source, min_popularity)
        # 每条榜单可以带自己的窗口与想看门槛（豆瓣 RSS 的「每榜独立控制」）：
        # 即将上映带精确日期、窗口可放宽；榜单类无日期靠 TMDB 判断。
        raw = item.raw if isinstance(item.raw, dict) else {}
        try:
            window_days = int(raw.get("future_days") or window_days)
        except (TypeError, ValueError):
            pass
        try:
            item_min_want = float(raw.get("min_want") or min_want)
        except (TypeError, ValueError):
            item_min_want = min_want

        if not filter_by_rating(item, rating_threshold):
            rejected.append(
                WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_RATING,
                    reason=f"评分 {item.rating} < {rating_threshold}（{item.source} 门槛）",
                )
            )
            continue
        if min_want > 0:
            # 豆瓣「想看人数」：量纲是人数（动辄上万），与 TMDB popularity 无关，
            # 所以单独设门槛。缺失时放行 —— 榜单类路线没有这个数据，
            # 若按「缺失即拦」处理会让整个榜单源失效。
            want = item.raw.get("want") if isinstance(item.raw, dict) else None
            if want is not None and float(want) < item_min_want:
                rejected.append(
                    WriteOutcome(
                        item=item,
                        decision=DECISION_SKIPPED_WANT,
                        reason=f"豆瓣想看 {want} < {item_min_want:.0f}（冷门，避免占用写入额度）",
                    )
                )
                continue

        if popularity_threshold > 0 and not filter_by_popularity(item, popularity_threshold):
            rejected.append(
                WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_POPULARITY,
                    reason=(
                        f"关注度 {item.popularity} < {popularity_threshold}"
                        "（冷门条目，避免占用写入额度）"
                    ),
                )
            )
            continue
        if item.date_unknown:
            # 来源没给定档日期（豆瓣榜单类 RSS 常见）。
            #
            # 剧集：放行 —— 它是否值得订由「TMDB 还有没有未播集」判定
            # （在 IdentityResolver._resolve_target_season 里已完成），
            # 这比时间窗口更准：正在连载的剧本来就没有「上映日」。
            # 电影：跳过 —— 没有日期就无从判断是否即将上映，
            # 榜单里的电影往往是老片，订了就是浪费额度。
            if item.is_tv:
                passed.append(item)
            else:
                rejected.append(
                    WriteOutcome(
                        item=item,
                        decision=DECISION_SKIPPED_NO_DATE,
                        reason="来源未提供上映日期（榜单类），电影无从判断是否即将上映",
                    )
                )
            continue

        if not filter_by_window(item, window_days, tz_name=tz_name, now=now):
            release = parse_date(item.release_date, tz_name)
            if release is None:
                reason = "无定档日期，无法判断是否即将开播"
                decision = DECISION_PENDING_REVIEW
            elif release < (now or today(tz_name)):
                reason = f"定档日期 {release.isoformat()} 已过去"
                decision = DECISION_SKIPPED_NOT_FUTURE
            else:
                reason = f"定档日期 {release.isoformat()} 超出 {window_days} 天窗口"
                decision = DECISION_SKIPPED_OUT_OF_WINDOW
            rejected.append(WriteOutcome(item=item, decision=decision, reason=reason))
            continue
        passed.append(item)

    # 关注度降序优先，保证每日额度先花在真正受关注的作品上
    passed.sort(key=selection_sort_key)
    return passed, rejected


# --------------------------------------------------------------------- 编排

async def fetch_all(
    sources: Sequence[SourceAdapter],
    config: Dict[str, Any],
    *,
    enabled: Sequence[str],
) -> List[SourceResult]:
    """并发拉取所有启用的源；单源失败不影响其他源。"""

    async def one(adapter: SourceAdapter) -> SourceResult:
        if adapter.name not in enabled:
            return SourceResult(source=adapter.name, skipped=True)
        try:
            items = await adapter.fetch(config)
        except Exception as err:  # noqa: BLE001 - 单源失败必须被隔离
            return SourceResult(source=adapter.name, error=f"{type(err).__name__}: {err}")
        return SourceResult(source=adapter.name, items=list(items or []))

    return list(await asyncio.gather(*(one(a) for a in sources)))


async def run_pipeline(
    *,
    sources: Sequence[SourceAdapter],
    enabled: Sequence[str],
    resolver: IdentityResolver,
    writer: SubscriptionWriter,
    config: Dict[str, Any],
    future_days: int,
    min_rating: float,
    min_popularity: float = 0.0,
    min_want: float = 0.0,
    resolve_concurrency: int = 8,
    dry_run: bool,
    already_written_today: int = 0,
    tz_name: Optional[str] = None,
    future_days_by_source: Optional[Dict[str, int]] = None,
    min_rating_by_source: Optional[Dict[str, float]] = None,
    min_popularity_by_source: Optional[Dict[str, float]] = None,
    keyword_lookup: Optional[KeywordLookup] = None,
) -> RunSummary:
    """执行一次完整发现流水线。

    顺序（开发文档 §7.1）：拉取 → 源内去重 → 归一（源实现内完成）→ 跨源去重
    → **黑名单** → 身份解析 → 过滤 → 额度 → 写入。
    """
    summary = RunSummary(started_at=local_now_text(tz_name), dry_run=dry_run)
    now = today(tz_name)

    # ---- 1. 并发拉取
    summary.sources = await fetch_all(sources, config, enabled=enabled)

    raw: List[DiscoveredItem] = []
    for result in summary.sources:
        if result.skipped:
            continue
        raw.extend(result.items)

    for item in raw:
        if not item.discovered_at:
            item.discovered_at = utc_now_text()

    # ---- 2. 源内去重（提前做，减少后续网络调用）
    before_dedupe = len(raw)
    raw = dedupe_within_source(raw)
    # 记录被丢弃数：否则「拉取」与「各决策之和」对不上（真机：371 vs 341 差 30）
    summary.deduped_out = max(0, before_dedupe - len(raw))

    # ---- 2.5 黑名单（**必须在身份解析之前**：拦掉的条目不该再花 TMDB 请求）
    rules = rules_from_config(config)
    blocked: List[WriteOutcome] = []
    if rules.active:
        raw, blocked = filter_blacklist(raw, rules)

    # ---- 3. 身份解析（**并发**，单条失败不影响其余）
    #
    # 为什么必须并发：豆瓣榜单类来源一次能产出 200+ 条候选，每条要做
    # 「TMDB 标题搜索 + 季/集查询」，实测串行约 0.7s/条 —— 260 条要 3 分钟，
    # 会拖死 cron 与手动运行。并发 8 路实测降到约 20~30 秒。
    width = max(1, int(resolve_concurrency or 1))
    semaphore = asyncio.Semaphore(width)

    async def _resolve_one(item: DiscoveredItem) -> None:
        async with semaphore:
            try:
                await resolver.resolve(item)
            except Exception as err:  # noqa: BLE001 - 单条失败不影响其余
                item.resolved = None
                item.raw.setdefault("resolve_error", f"{type(err).__name__}: {err}")

    await asyncio.gather(*(_resolve_one(item) for item in raw))

    # ---- 4. 过滤（跨源去重 / 评分 / 窗口）
    summary.selected, summary.prefiltered = select_items(
        raw,
        future_days=future_days,
        min_rating=min_rating,
        min_popularity=min_popularity,
        min_want=min_want,
        future_days_by_source=future_days_by_source,
        min_rating_by_source=min_rating_by_source,
        min_popularity_by_source=min_popularity_by_source,
        tz_name=tz_name,
        now=now,
    )
    if blocked:
        summary.prefiltered = blocked + summary.prefiltered

    # ---- 4.5 黑名单第二层：TMDB keyword（只对即将写入的少量条目查）
    if rules.active and rules.tmdb_keywords and keyword_lookup is not None:
        summary.selected, keyword_blocked = await filter_blacklist_keywords(
            summary.selected,
            rules,
            keyword_lookup,
            concurrency=min(4, max(1, int(resolve_concurrency or 1))),
        )
        if keyword_blocked:
            summary.prefiltered = summary.prefiltered + keyword_blocked

    # ---- 5. 写入（dry_run 或首次运行时只判定）
    effective_dry_run = bool(dry_run)
    summary.dry_run = effective_dry_run
    summary.report = await writer.write(
        summary.selected,
        dry_run=effective_dry_run,
        already_written_today=already_written_today,
        tz_name=tz_name,
    )
    summary.finished_at = local_now_text(tz_name)
    return summary


__all__ = [
    "KeywordLookup",
    "RunSummary",
    "SourceAdapter",
    "SourceResult",
    "dedupe_cross_source",
    "dedupe_within_source",
    "fetch_all",
    "filter_blacklist",
    "filter_blacklist_keywords",
    "filter_by_rating",
    "filter_by_window",
    "run_pipeline",
    "select_items",
]
