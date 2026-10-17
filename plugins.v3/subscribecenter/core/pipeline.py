"""发现流水线编排：拉取 → 归一 → 去重 → 过滤 → 写入。

流程对应开发文档 §7.1。两条纪律贯穿全文件：

1. **单源失败不得阻塞其他源** —— 每个源独立 ``try/except``，失败只记录；
2. **宁缺毋滥** —— 没有确定性身份的条目进待确认列表，绝不写入。

``select_items()`` 是纯函数（不碰网络、不碰宿主），因此过滤/去重/配额逻辑
全部可离线单测（开发文档 §14.1）；``run_pipeline()`` 只负责把它们串起来。
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from .constants import (
    DECISION_PENDING_REVIEW,
    DECISION_SKIPPED_DUPLICATE,
    DECISION_SKIPPED_NOT_FUTURE,
    DECISION_SKIPPED_OUT_OF_WINDOW,
    DECISION_SKIPPED_POPULARITY,
    DECISION_SKIPPED_RATING,
)
from .identity import IdentityResolver
from .model import DiscoveredItem, item_sort_key
from .window import in_window, local_now_text, parse_date, today, utc_now_text
from .writer import SubscriptionWriter, WriteOutcome, WriteReport


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
    first_run: bool = False
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
            "first_run": self.first_run,
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
            "total": self.fetched_count,
        }

    def skipped_count(self, report: Optional[Dict[str, Any]] = None) -> int:
        """返回跳过的总条数（**含**预过滤阶段被拦下的条目）。

        :param report: 已算好的 ``report.to_summary()``，避免重复计算
        """
        data = report if report is not None else (self.report.to_summary() if self.report else {})
        return int(data.get("skipped", 0)) + len(self.prefiltered)

    def _rejected_reasons(self) -> Dict[str, int]:
        """按决策统计被预过滤拦下的条目数，便于一眼看出为什么一条都没写。"""
        counts: Dict[str, int] = {}
        for outcome in self.prefiltered:
            key = outcome.decision or "unknown"
            counts[key] = counts.get(key, 0) + 1
        return counts


# --------------------------------------------------------------------- 纯逻辑

def dedupe_within_source(items: Sequence[DiscoveredItem]) -> List[DiscoveredItem]:
    """第一层去重：``source + source_id`` 唯一。

    同一 ``source_id`` 重复出现时**保留先出现的**（源实现通常已按重要性排序）。
    """
    seen: set = set()
    result: List[DiscoveredItem] = []
    for item in items:
        key = (item.source, item.source_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


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


def select_items(
    items: Sequence[DiscoveredItem],
    *,
    future_days: int,
    min_rating: float,
    min_popularity: float = 0.0,
    tz_name: Optional[str] = None,
    now: Any = None,
    future_days_by_source: Optional[Dict[str, int]] = None,
    min_rating_by_source: Optional[Dict[str, float]] = None,
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
    for item in kept:
        # 按源取各自的评分门槛与窗口天数（TMDB / Bangumi 的配置是分开的）
        rating_threshold = rating_map.get(item.source, min_rating)
        window_days = window_map.get(item.source, future_days)

        if not filter_by_rating(item, rating_threshold):
            rejected.append(
                WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_RATING,
                    reason=f"评分 {item.rating} < {rating_threshold}（{item.source} 门槛）",
                )
            )
            continue
        if min_popularity > 0 and not filter_by_popularity(item, min_popularity):
            rejected.append(
                WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_POPULARITY,
                    reason=f"关注度 {item.popularity} < {min_popularity}（冷门条目，避免占用写入额度）",
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
    dry_run: bool,
    first_run: bool,
    already_written_today: int = 0,
    tz_name: Optional[str] = None,
    future_days_by_source: Optional[Dict[str, int]] = None,
    min_rating_by_source: Optional[Dict[str, float]] = None,
) -> RunSummary:
    """执行一次完整发现流水线。

    顺序（开发文档 §7.1）：拉取 → 源内去重 → 归一（源实现内完成）→ 跨源去重
    → 身份解析 → 过滤 → 额度 → 写入。
    """
    summary = RunSummary(started_at=local_now_text(tz_name), dry_run=dry_run, first_run=first_run)
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
    raw = dedupe_within_source(raw)

    # ---- 3. 身份解析（按条目独立，单条失败不影响其余）
    for item in raw:
        try:
            await resolver.resolve(item)
        except Exception as err:  # noqa: BLE001
            item.resolved = None
            item.raw.setdefault("resolve_error", f"{type(err).__name__}: {err}")

    # ---- 4. 过滤（跨源去重 / 评分 / 窗口）
    summary.selected, summary.prefiltered = select_items(
        raw,
        future_days=future_days,
        min_rating=min_rating,
        min_popularity=min_popularity,
        future_days_by_source=future_days_by_source,
        min_rating_by_source=min_rating_by_source,
        tz_name=tz_name,
        now=now,
    )

    # ---- 5. 写入（dry_run 或首次运行时只判定）
    effective_dry_run = bool(dry_run or first_run)
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
    "RunSummary",
    "SourceAdapter",
    "SourceResult",
    "dedupe_cross_source",
    "dedupe_within_source",
    "fetch_all",
    "filter_by_rating",
    "filter_by_window",
    "run_pipeline",
    "select_items",
]
