"""缺失判断服务（matcher）：依据 MoviePilot 自身的媒体库与订阅状态。

数据源（都是宿主**只读**能力，插件不重复建设）：
1. **媒体服务器存在性（权威）**：``MediaServerHelper`` 取已启用实例，
   ``module.media_exists(MediaInfo(...))`` → None 表示不存在；剧集返回
   ``seasons: {季: [已存在集]}``，据此逐集比对目标集是否缺失。
   —— "媒体库里到底有没有这一集"只有它说了算。
   媒体库查询按**逐层放宽**进行（见 ``_fetch_media_exists``）：片名+年份 →
   仅片名 → **名称变体**（``片名 (年份)`` 等，见 ``_name_variants``）。原因是
   宿主 Emby/Jellyfin 系按 ``Name == 片名 and ProductionYear == 年份``
   **精确**匹配，而资源名里的年份与媒体库刮削年份/名称常常对不上（未刮削的
   条目更甚），真机表现为"库里明明有，插件却说没有"→ 回搜把整部剧全推出去
   （1.4.5 真机踩坑）。

   ⚠️ 三层放宽**全部是定向精确查询**（每次只返回一个小结果集，代价与媒体库
   规模无关）。1.4.6~1.7.8 曾用过一条"把整个媒体库拉进内存建条目索引"的兜底
   路径，30 万级媒体库下既慢（分钟级）又必然被规模上限跳过，1.7.9 已整条移除——
   新加兜底能力时**不要**再走全量拉取。
2. **订阅快照（门禁 + 兜底）**：``list_subscriptions()`` 按标题+年份+季匹配订阅。
   - ``lack_episode`` 为 0 → 可直接判"不缺"（省掉一次媒体库查询的快速通道）；
   - 开启「仅缺失」且资源未订阅 → 判"未订阅"跳过（方案 A 门禁）；
   - 媒体库不可用时，才用 ``lack_episode > 0`` 作为缺集依据。

   注意 ``lack_episode`` **不能单独判"缺"**：宿主新建订阅时
   （``app/chain/subscribe/create.py`` 的 ``__fill_subscribe_lack_episode``）
   直接令 ``lack_episode = total_episode``，要等订阅刷新任务比对过媒体库才会收敛。
   若拿它当权威，刚订阅的剧会把缓存里全部候选都判成缺集（1.4.4 真机踩坑：
   媒体库已有 S01E01-E10，34 条候选全被推送）。

两级都不可用（未配置媒体服务器、也没有订阅）时返回 ``missing=None``
（"无法判断"），由调用方决定跳过还是放行——不静默当成"不缺"。

性能：TG 消息可能密集，对判断结果做 60 秒 TTL 内存缓存（键为归一化媒体身份）；
媒体服务器查询另有一层按「片名+年份+类型+季」的缓存，避免同一部剧逐集重复查询。
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

from app.sdk.logging import logger

try:  # 宿主只读查询：缺失时降级为"订阅不可用"
    from app.sdk.queries import list_subscriptions

    QUERIES_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境
    list_subscriptions = None  # type: ignore[assignment]
    QUERIES_AVAILABLE = False

try:  # 媒体服务器助手：缺失时降级为"媒体库不可用"
    from app.sdk.services import MediaServerHelper

    MEDIASERVER_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境
    MediaServerHelper = None  # type: ignore[assignment]
    MEDIASERVER_AVAILABLE = False

try:  # MediaType 枚举（值为中文字符串）
    from app.schemas.types import MediaType

    _MEDIA_TYPE_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境
    MediaType = None  # type: ignore[assignment]
    _MEDIA_TYPE_AVAILABLE = False

# 判断结果缓存 TTL（秒）
_CACHE_TTL_SECONDS = 60
# 归一化时丢弃的字符
_NORMALIZE_RE = re.compile(r"[\s·・:：\-_－—\-]+")
# 订阅翻页的页大小（宿主 MAX_QUERY_PAGE_SIZE=200）
_SUB_PAGE_SIZE = 200
# 翻页硬上限，防异常宿主死循环
_SUB_MAX_PAGES = 100
# 名称变体的候选上限（保序截断，避免异常片名生成过多候选把查询打散）
_NAME_VARIANT_LIMIT = 6


def iter_subscriptions() -> "Iterator[Any]":
    """翻页读取全部宿主订阅。

    宿主 ``list_subscriptions()`` 无参调用只返回第一页（默认页大小 50），
    订阅多于 50 时必须显式翻页——否则订阅回搜基线不全，且订阅门禁会把
    第 2 页之后的订阅误判为「未订阅」（1.4.0 实测踩坑）。
    """
    if not QUERIES_AVAILABLE or list_subscriptions is None:
        return
    page_num = 1
    while page_num <= _SUB_MAX_PAGES:
        try:
            try:
                page = list_subscriptions(None, {"page": page_num, "count": _SUB_PAGE_SIZE})
            except TypeError:
                # 宿主签名不支持分页参数（或测试桩是无参 lambda）：退回无参调用
                page = list_subscriptions()
        except Exception as err:
            logger.warning(f"读取宿主订阅失败（第 {page_num} 页）：{err}")
            return
        items = list(getattr(page, "items", None) or [])
        yield from items
        if len(items) < _SUB_PAGE_SIZE:
            # 不足一页说明已是最后一页（测试桩返回全量时同样在此收束）
            return
        total = getattr(page, "total", None)
        try:
            if total is not None and page_num * _SUB_PAGE_SIZE >= int(total):
                return
        except (TypeError, ValueError):
            pass
        page_num += 1


def _normalize_title(value: Any) -> str:
    """标题归一化：小写、去空白与常见分隔符，用于跨源比对。"""
    text = str(value or "").strip().lower()
    return _NORMALIZE_RE.sub("", text)


def _as_int(value: Any) -> Optional[int]:
    """宽松转 int：None / 空串 / 非法值都返回 None（宿主字段类型不保证）。"""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _title_score(left: Any, right: Any) -> int:
    """归一标题匹配打分：2=完全相等，1=一方包含另一方，0=不匹配。"""
    a, b = _normalize_title(left), _normalize_title(right)
    if not a or not b:
        return 0
    if a == b:
        return 2
    return 1 if (a in b or b in a) else 0


def _titles_match(left: str, right: str) -> bool:
    """两个标题是否指向同一媒体（相等或一方包含另一方）。"""
    return _title_score(left, right) > 0


def _safe_call(target: Any, method: str, *args: Any, **kwargs: Any) -> Any:
    """调用宿主对象的方法；方法不存在或抛异常一律返回 None。

    媒体服务器"探测"属于尽力而为：不同宿主版本/不同服务器类型的方法面不同，
    任何一步失败都不该把主流程（缺失判断）带崩。
    """
    func = getattr(target, method, None)
    if not callable(func):
        return None
    try:
        return func(*args, **kwargs)
    except Exception as err:  # pragma: no cover - 依赖宿主实现，按不可用处理
        logger.debug(f"调用媒体服务器 {method} 失败（忽略）：{err}")
        return None


def _safe_list(target: Any, method: str, *args: Any) -> list:
    """调用宿主方法并物化成 list（生成器内部异常也算失败）。"""
    result = _safe_call(target, method, *args)
    if result is None:
        return []
    try:
        return list(result)
    except Exception as err:  # pragma: no cover
        logger.debug(f"展开媒体服务器 {method} 结果失败（忽略）：{err}")
        return []


def _name_variants(title: str, year: str) -> List[str]:
    """资源名 → 媒体库内可能使用的命名候选（保序去重，含原始片名）。

    宿主 Emby/Jellyfin 的 ``__get_emby_series_id_by_name`` 按 ``Name``
    **完全相等**匹配，而库内条目名常带年份后缀（``林间鸽踪 (2026)``）、
    半角/全角括号或分隔差异（``片名 2026``）。这里给出少量候选名，让调用方
    逐个做**定向精确查询**——每次只返回一个小结果集，代价与媒体库规模无关。

    这是 1.7.9 用来取代 1.4.6「全量条目索引」的做法：后者要把整个媒体库拉进
    内存，30 万级库下既慢（分钟级）又必然被规模上限跳过，且存在"拿不到条目数
    时静默全量拉取"的隐患。
    """
    base = str(title or "").strip()
    if not base:
        return []
    variants: List[str] = [base]
    y = str(year or "").strip()
    if y:
        variants.extend([
            f"{base} ({y})",   # MP 规范化命名的常见形态
            f"{base}({y})",    # 无空格
            f"{base}（{y}）",  # 全角括号
            f"{base} {y}",     # 纯空格分隔
        ])
    ordered: List[str] = []
    for item in variants[:_NAME_VARIANT_LIMIT]:
        if item and item not in ordered:
            ordered.append(item)
    return ordered


def _seasons_of(exist: Any) -> dict:
    """从 ``ExistMediaInfo`` 取季集表（类型不符按空处理）。"""
    seasons = getattr(exist, "seasons", None) or {}
    return seasons if isinstance(seasons, dict) else {}


def _years_compatible(left: Any, right: Any) -> bool:
    """两边都有年份时必须一致；缺一边时不阻止匹配。"""
    a, b = str(left or "").strip(), str(right or "").strip()
    if not a or not b:
        return True
    return a == b


def _summarize_episodes(episodes: list) -> str:
    """把缺失集号列表压缩成区间描述（[1, 4, 5, 6] → "E01, E04-E06"）。"""
    if not episodes:
        return ""
    sorted_eps = sorted(episodes)
    parts: list = []
    start = prev = sorted_eps[0]
    for ep in sorted_eps[1:]:
        if ep == prev + 1:
            prev = ep
            continue
        parts.append(f"E{start:02d}" if start == prev else f"E{start:02d}-E{prev:02d}")
        start = prev = ep
    parts.append(f"E{start:02d}" if start == prev else f"E{start:02d}-E{prev:02d}")
    return ", ".join(parts)


class MediaMatcher:
    """媒体缺失判断（带短 TTL 缓存，线程安全）。"""

    def __init__(self, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl = max(1, int(ttl_seconds or _CACHE_TTL_SECONDS))
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        # 媒体服务器查询缓存：键 = 片名|年份|类型|季，值 = (queried, exists, seasons, note)
        self._media_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ 能力探测

    def capabilities(self) -> dict:
        """当前可用的判断手段（供状态接口展示，不抛异常）。"""
        subscriptions = 0
        try:
            subscriptions = self._count_subscriptions()
        except Exception as err:  # pragma: no cover - 探测失败按 0 处理
            logger.debug(f"探测订阅数量失败：{err}")
        return {
            "queries_available": QUERIES_AVAILABLE,
            "mediaserver_available": MEDIASERVER_AVAILABLE,
            "subscriptions": subscriptions,
            "mediaserver": self._mediaserver_name(),
        }

    def _count_subscriptions(self) -> int:
        if not QUERIES_AVAILABLE:
            return 0
        # 注意：无参调用只返回第一页（默认页大小 50），计数必须用 total，
        # 否则订阅多于 50 时界面显示的数字与 MP 订阅页对不上。
        page = list_subscriptions()
        total = getattr(page, "total", None)
        if total is not None:
            try:
                return int(total)
            except (TypeError, ValueError):
                pass
        items = getattr(page, "items", None)
        if items is None:
            return 0
        try:
            return len(list(items))
        except Exception:  # pragma: no cover
            return 0

    @staticmethod
    def _mediaserver_name() -> str:
        if not MEDIASERVER_AVAILABLE:
            return ""
        try:
            helper = MediaServerHelper()
            for service in helper.iterate_module_instances():
                name = getattr(service, "name", "") or ""
                if name:
                    return str(name)
        except Exception as err:  # pragma: no cover
            logger.debug(f"探测媒体服务器失败：{err}")
        return ""

    # ------------------------------------------------------------------ 主判断

    def is_missing(
        self,
        *,
        title: str,
        year: str = "",
        media_type: str = "",
        season: Optional[int] = None,
        episode: Optional[int] = None,
        episode_end: Optional[int] = None,
        require_subscription: bool = False,
    ) -> dict:
        """判断媒体是否缺失。

        :param episode_end: 集区间结束（如 "S01E01-E09" 的 9）；与 episode 一起
            表达"这批资源覆盖的集范围"，缺失判断按区间逐一比对。
        :param require_subscription: 开启「仅缺失」订阅门禁——当订阅数据源可用、但
            该资源未命中任何订阅时，直接判为"未订阅"跳过，不再落媒体库比对。
            这是方案 A 的语义：监控只处理「已订阅 + 缺失」的资源，未订阅的绝不推送，
            也不会被误标成"媒体库已存在"。订阅数据源不可用时（未配置订阅）退回旧逻辑，
            继续按媒体库判断，避免"没配订阅就全盘拦截"。
        :returns: ``{"missing": bool|None, "reason": str, "source": str, "detail": str}``
            ``missing=None`` 表示无法判断（无数据源）。

        判定顺序（媒体库优先，"缺"必须由媒体库或订阅兜底给出）：
        1. 订阅 lack_episode<=0 → 不缺（快速通道）；
        2. 未订阅 + 门禁开启 → 未订阅（跳过）；
        3. 媒体服务器存在性 → **权威结论**（含逐集比对）；
        4. 媒体库不可用 → 退回订阅 lack_episode>0 判缺，否则无法判断。
        """
        key = self._cache_key(title, year, media_type, season, episode, episode_end, require_subscription)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        result = self._decide(
            title=title, year=year, media_type=media_type, season=season,
            episode=episode, episode_end=episode_end,
            require_subscription=require_subscription,
        )
        self._cache_put(key, result)
        return result

    def _decide(
        self,
        *,
        title: str,
        year: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        episode_end: Optional[int],
        require_subscription: bool = False,
    ) -> dict:
        # 1) 订阅快照：只用于「不缺」的快速排除与「未订阅」门禁（见函数 docstring）
        subscription = self._match_subscription(title=title, year=year, season=season)
        lack = None
        if subscription is not None:
            lack = _as_int(subscription.get("lack_episode"))
            if lack is not None and lack <= 0:
                return {
                    "missing": False,
                    "reason": "订阅已存在且无缺集",
                    "source": "subscription",
                    "detail": f"订阅「{subscription.get('name') or title}」lack_episode={lack}",
                }
        elif require_subscription and QUERIES_AVAILABLE:
            # 方案 A 订阅门禁：订阅数据源可用，但本资源未命中任何订阅 → 直接跳过，
            # 不再去查媒体库（否则会被误标成"媒体库已存在"，与用户预期不符）。
            return {
                "missing": False,
                "reason": "未订阅",
                "source": "subscription",
                "detail": f"「{title}」未在订阅列表中，按仅缺失规则跳过",
            }

        # 2) 媒体服务器存在性（主力，权威）：缺不缺由媒体库说了算
        exists = self._query_media_exists(
            title=title, year=year, media_type=media_type, season=season,
            episode=episode, episode_end=episode_end,
        )
        if exists is not None:
            return exists

        # 3) 媒体库不可用：退回订阅的缺集数（不能因为查不到媒体库就当"不缺"）
        if lack is not None and lack > 0:
            return {
                "missing": True,
                "reason": f"订阅缺 {lack} 集（媒体库不可用，按订阅判断）",
                "source": "subscription",
                "detail": f"订阅「{subscription.get('name') or title}」lack_episode={lack}",
            }

        # 4) 无数据源
        return {
            "missing": None,
            "reason": "未配置媒体服务器与订阅，无法判断缺失",
            "source": "none",
            "detail": "",
        }

    # ------------------------------------------------------------------ 订阅匹配

    def _match_subscription(
        self, *, title: str, year: str, season: Optional[int]
    ) -> Optional[dict]:
        """在宿主订阅里找同名（同年份、同季）的订阅。"""
        if not QUERIES_AVAILABLE:
            return None
        try:
            # 必须翻页读全量：只取第一页会把第 51 个之后的订阅误判成「未订阅」
            for item in iter_subscriptions():
                name = str(getattr(item, "name", "") or "")
                item_year = str(getattr(item, "year", "") or "")
                item_season = getattr(item, "season", None)
                if not _titles_match(title, name):
                    continue
                if not _years_compatible(year, item_year):
                    continue
                if season is not None and item_season is not None:
                    try:
                        if int(item_season) != int(season):
                            continue
                    except (TypeError, ValueError):
                        pass
                return {
                    "name": name,
                    "year": item_year,
                    "season": item_season,
                    "lack_episode": getattr(item, "lack_episode", None),
                    "state": getattr(item, "state", None),
                    # P9 订阅桥：借出宿主的媒体身份对（供下载历史精确查询）。
                    # 快照里这对字段可能为空（脏半对会被宿主归一成 None），
                    # 调用方须自行判空退回 title 路径。
                    "media_source": getattr(item, "media_source", None),
                    "media_id": getattr(item, "media_id", None),
                }
        except Exception as err:
            logger.debug(f"读取宿主订阅失败：{err}")
            return None
        return None

    def subscription_identity(
        self, *, title: str, year: str, season: Optional[int]
    ) -> "tuple[Optional[str], Optional[str]]":
        """P9 订阅桥：TG 身份 → MP 订阅 → ``(media_source, media_id)``。

        未命中订阅或订阅缺身份对时返回 ``(None, None)``，调用方退回
        title 路径查下载历史。复用 ``_match_subscription`` 的翻页与匹配逻辑，
        不另写一套片名比对（1.4.0「第 51 条之后匹配不到」的教训）。
        """
        sub = self._match_subscription(title=title, year=year, season=season)
        if not sub:
            return (None, None)
        source = str(getattr(sub.get("media_source"), "value", "") or sub.get("media_source") or "").strip()
        media_id = str(sub.get("media_id") or "").strip()
        if not source or not media_id or media_id == "0":
            return (None, None)
        return (source, media_id)

    # ------------------------------------------------------------------ 媒体服务器

    def _query_media_exists(
        self,
        *,
        title: str,
        year: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        episode_end: Optional[int] = None,
    ) -> Optional[dict]:
        """查询媒体服务器；返回判断字典，不可用时返回 None。"""
        queried, exists, seasons, note = self._lookup_media(
            title=title, year=year, media_type=media_type, season=season
        )
        if not queried:
            return None
        if not exists:
            return {
                "missing": True,
                "reason": "媒体库中不存在",
                "source": "mediaserver",
                "note": note,
                "detail": f"「{title}」在已配置媒体服务器中未找到"
                + (f"（{note}）" if note else ""),
            }
        if media_type == "tv" and season is not None:
            owned = self._episodes_of(seasons, season)
            if episode is None:
                # 只识别到季没识别到集：该季已有内容即算不缺
                return {
                    "missing": not owned,
                    "reason": "该季媒体库已有内容" if owned else "该季在媒体库中缺失",
                    "source": "mediaserver",
                    "detail": f"S{season:02d} 已存在 {len(owned)} 集",
                }
            # 集区间（"S01E01-E09"）按范围逐一比对：任一集缺失即视为缺
            end = episode_end if episode_end is not None and episode_end >= episode else episode
            wanted = range(episode, end + 1)
            missing_eps = [ep for ep in wanted if ep not in owned]
            range_text = f"E{episode:02d}" if end == episode else f"E{episode:02d}-E{end:02d}"
            if not missing_eps:
                return {
                    "missing": False,
                    "reason": f"S{season:02d}{range_text} 已在媒体库",
                    "source": "mediaserver",
                    "detail": f"该季已存在 {len(owned)} 集",
                }
            return {
                "missing": True,
                "reason": f"S{season:02d}{range_text} 缺 {len(missing_eps)} 集",
                "source": "mediaserver",
                "detail": (
                    f"缺失集：{_summarize_episodes(missing_eps)}"
                    + (f"；该季已存在 {len(owned)} 集" if owned else "")
                ),
            }
        # 电影（或未识别出季集的剧集条目）：存在即不缺
        return {
            "missing": False,
            "reason": "媒体库中已存在",
            "source": "mediaserver",
            "detail": f"「{title}」已存在",
        }

    # ------------------------------------------------------- 媒体库查询（带缓存）

    def _lookup_media(
        self, *, title: str, year: str, media_type: str, season: Optional[int]
    ) -> "tuple[bool, bool, dict, str]":
        """按「片名+年份+类型+季」查询媒体库，返回 ``(是否查到, 是否存在, 季集表, 说明)``。

        调用方会逐集调用本方法（一条消息一集），但``media_exists`` 是按整部剧
        查询的——没有这层缓存，34 条候选就会打 34 次同样的媒体服务器请求。
        ``queried=False`` 表示无法查询（未配置媒体服务器 / 查询异常），
        调用方据此退回"无法判断"，不能当成"不存在"。
        """
        key = "|".join([
            _normalize_title(title), str(year or ""), str(media_type or ""),
            str(season if season is not None else ""),
        ])
        with self._lock:
            entry = self._media_cache.get(key)
            if entry and time.monotonic() - entry["at"] <= self._ttl:
                return entry["value"]
        value = self._fetch_media_exists(
            title=title, year=year, media_type=media_type, season=season
        )
        with self._lock:
            if len(self._media_cache) > 256:
                self._media_cache.clear()
            self._media_cache[key] = {"at": time.monotonic(), "value": value}
        return value

    def _fetch_media_exists(
        self, *, title: str, year: str, media_type: str, season: Optional[int]
    ) -> "tuple[bool, bool, dict, str]":
        """真正调用媒体服务器（无缓存）。

        返回 ``(queried, exists, seasons, note)``，``note`` 是未命中时的可读原因。
        ``queried=False`` 表示查不动（未配置实例 / 调用异常），调用方据此退回
        "无法判断"，绝不能当成"不存在"。

        查询**逐层放宽**，任一命中即返回：

        1. **片名 + 年份**：宿主原生口径（MP 自己也是这么查的）；
        2. **仅片名（忽略年份）**：宿主 Emby/Jellyfin 系按
           ``Name == 片名 and ProductionYear == 年份`` 精确匹配，资源名里的年份
           与媒体库刮削年份常有偏差；命中后用 ``get_iteminfo`` 复核库中年份，
           同名不同年的翻拍剧不会被误判"已有"；
        3. **名称变体**（``片名 (年份)`` / ``片名(年份)`` / 全角括号 / ``片名 年份``）：
           库内条目名常带年份后缀或分隔差异（如 ``林间鸽踪 (2026)``），宿主按
           名称**完全相等**匹配时资源名对不上；用少量候选名各做一次定向精确
           查询，命中后用 ``get_iteminfo`` 复核库内年份。
           —— 三层全是定向查询，代价与媒体库规模无关；1.4.6~1.7.8 的
           「全量条目索引」兜底（把整个库拉进内存）已整条移除，别再引入。
        """
        if not MEDIASERVER_AVAILABLE:
            return (False, False, {}, "")
        module = None
        instances: List[tuple] = []
        try:
            helper = MediaServerHelper()
            for service in helper.iterate_module_instances():
                instance = getattr(service, "instance", None)
                if instance is not None:
                    instances.append((str(getattr(service, "name", "") or ""), instance))
                if module is None:
                    # iterate_module_instances 产出的 ServiceInfo 里，带 media_exists 的
                    # 是 **module**（媒体服务器模块基类实例，其内部会遍历该类型的全部服务）；
                    # instance 是具体某个服务器实例（如 Emby 客户端对象），没有该方法——
                    # 取错层级会报 "'Emby' object has no attribute 'media_exists'"。
                    candidate = getattr(service, "module", None) or instance
                    if candidate is not None and hasattr(candidate, "media_exists"):
                        module = candidate
        except Exception as err:
            logger.info(f"查询媒体服务器存在性失败（按无法判断处理）：{err}")
            return (False, False, {}, "")
        if module is None:
            # 没有可用实例：宿主 media_exists 会因循环体不执行而返回 None，
            # 若在这里当成"不存在"，就会把全部资源误判为缺失
            return (False, False, {}, "")

        # 1) 片名 + 年份；2) 仅片名
        plans: List[tuple] = [("片名+年份", year)]
        if year:
            plans.append(("仅片名", ""))
        rejected = ""
        for label, attempt_year in plans:
            ok, exist = self._call_media_exists(
                module, title=title, year=attempt_year, media_type=media_type, season=season
            )
            if not ok:
                return (False, False, {}, "")
            if exist is None:
                continue
            if label == "仅片名":
                lib_year, accepted = self._verify_year(instances, exist, year)
                if not accepted:
                    rejected = (
                        f"仅按片名命中但库中年份为 {lib_year}（资源年份 {year}），已忽略"
                    )
                    logger.info(f"媒体库查询：「{title}」{rejected}")
                    break
                logger.info(
                    f"媒体库查询：「{title}」按年份 {year} 未命中，改用仅片名命中"
                )
            return (True, True, _seasons_of(exist), "")

        # 3) 名称变体探测：库内命名常带「片名 (年份)」等后缀，宿主按 Name
        #    精确匹配时资源名对不上；用少量候选名各做一次定向查询（毫秒级、
        #    与库大小无关）。裸片名已在第 2 层试过，这里只试带后缀的变体。
        variants = _name_variants(title, year)[1:]
        if variants:
            started = time.monotonic()
            for variant in variants:
                ok, exist = self._call_media_exists(
                    module, title=variant, year="", media_type=media_type, season=season
                )
                if not ok:
                    return (False, False, {}, "")
                if exist is None:
                    continue
                lib_year, accepted = self._verify_year(instances, exist, year)
                if not accepted:
                    rejected = (
                        f"按候选名「{variant}」命中但库中年份为 {lib_year}"
                        f"（资源年份 {year}），已忽略"
                    )
                    logger.info(f"媒体库查询：「{title}」{rejected}")
                    continue
                logger.info(
                    f"媒体库查询：「{title}」按候选名「{variant}」命中"
                    f"（探测 {len(variants)} 个候选，耗时 {time.monotonic() - started:.2f}s）"
                )
                return (True, True, _seasons_of(exist), "")
            logger.debug(
                f"媒体库查询：「{title}」{len(variants)} 个候选名均未命中"
                f"（耗时 {time.monotonic() - started:.2f}s）"
            )

        note = self._diagnose_not_found(
            instances, title=title, year=year, media_type=media_type
        )
        if rejected:
            note = f"{note}；{rejected}" if note else rejected
        logger.info(
            f"媒体库查询：「{title}」({year or '-'}) 未命中"
            + (f"：{note}" if note else "（已放宽到仅片名与名称变体）")
        )
        return (True, False, {}, note)

    @staticmethod
    def _call_media_exists(
        module: Any, *, title: str, year: str, media_type: str, season: Optional[int],
        item_id: str = "", server: str = "",
    ) -> "tuple[bool, Any]":
        """调用一次 ``media_exists``；返回 ``(是否调用成功, 结果)``。

        ``是否调用成功=False`` 才表示"查不动"（构造/调用失败）；结果为 None
        表示"查过了，媒体库里没有"。
        """
        try:
            mediainfo = MediaMatcher._build_media_info(
                title=title, year=year, media_type=media_type, season=season
            )
        except Exception as err:
            logger.info(f"构造媒体信息失败（按无法判断处理）：{err}")
            return (False, None)
        kwargs: Dict[str, Any] = {}
        if item_id:
            kwargs["itemid"] = item_id
        if server:
            kwargs["server"] = server
        try:
            return (True, module.media_exists(mediainfo, **kwargs))
        except TypeError:
            # 自定义/旧版模块不支持 itemid、server 参数
            return (False, None)
        except Exception as err:
            logger.info(f"调用媒体服务器存在性检查失败（按无法判断处理）：{err}")
            return (False, None)

    @staticmethod
    def _verify_year(
        instances: List[tuple], exist: Any, year: str
    ) -> "tuple[str, bool]":
        """仅片名命中后的年份复核：返回 ``(库中年份, 是否接受)``。

        查不到库中年份时不阻止命中（宁可用起来，也不要因为拿不到年份就全推出去）；
        只有明确拿到不相容的年份才拒绝，避免同名不同年的翻拍剧被误判"媒体库已有"。
        """
        item_id = str(getattr(exist, "itemid", "") or "")
        server = str(getattr(exist, "server", "") or "")
        if not item_id or not year:
            return "", True
        for name, client in instances:
            if server and name and name != server:
                continue
            info = _safe_call(client, "get_iteminfo", item_id)
            lib_year = str(getattr(info, "year", "") or "") if info is not None else ""
            if not lib_year:
                continue
            return lib_year, _years_compatible(year, lib_year)
        return "", True

    def _diagnose_not_found(
        self, instances: List[tuple], *, title: str, year: str, media_type: str
    ) -> str:
        """媒体库未命中时给出可读原因，区分"没这条"与"有条目但没集"。"""
        if media_type == "movie":
            return "媒体库中没有匹配的电影条目"
        for _name, client in instances:
            func = getattr(client, "get_tv_episodes", None)
            if not callable(func):
                continue
            try:
                item_id, seasons = func(title=title, year=year)
            except TypeError:
                continue
            except Exception as err:  # pragma: no cover - 探测失败只作说明
                return f"探测剧集条目出错：{err}"
            if item_id is None and seasons is None:
                # 1.8.0：宿主的 get_tv_episodes 会把自己的（None / "" / ID）三态
                # **折叠**成两态——(None, None) 才是查询真失败（连不通/接口异常），
                # 而 (None, {}) 是"连接正常、库里就是没这条"（宿主内部把 "" 转成了
                # None）。此前只看 item_id 判失败，于是"库里没有"被误报成
                # 「媒体服务器查询失败（请求未成功）」，回搜通知里天天出现。
                return "媒体服务器查询失败（请求未成功）"
            if not item_id:
                # 兼容把空串当"未找到"原样冒泡的宿主实现
                return "媒体库中没有同名剧集条目（宿主按片名+年份精确匹配失败）"
            owned = 0
            if isinstance(seasons, dict):
                for value in seasons.values():
                    if isinstance(value, (list, tuple, set)):
                        owned += len(value)
            if not owned:
                return f"剧集条目在库（item_id={item_id}）但没有任何已入库的集"
            return f"剧集条目在库且已入库 {owned} 集"
        return ""

    @staticmethod
    def _episodes_of(seasons: Any, season: int) -> set:
        """从 ``seasons: {季: [集]}`` 取出目标季的已存在集号。"""
        if not isinstance(seasons, dict):
            return set()
        owned: set = set()
        for key, value in seasons.items():
            try:
                if int(key) != int(season):
                    continue
            except (TypeError, ValueError):
                continue
            if isinstance(value, (list, tuple, set)):
                for ep in value:
                    try:
                        owned.add(int(ep))
                    except (TypeError, ValueError):
                        continue
        return owned

    @staticmethod
    def _build_media_info(*, title: str, year: str, media_type: str, season: Optional[int]):
        """构造宿主 MediaInfo（dataclass，字段全可选）。"""
        from app.sdk.media import MediaInfo

        media_type_value = None
        if _MEDIA_TYPE_AVAILABLE:
            if media_type == "tv":
                media_type_value = MediaType.TV
            elif media_type == "movie":
                media_type_value = MediaType.MOVIE
        return MediaInfo(
            title=str(title or ""),
            year=str(year or "") or None,
            type=media_type_value,
            season=int(season) if season is not None else None,
        )

    # ------------------------------------------------------------------ 缓存

    @staticmethod
    def _cache_key(title: str, year: str, media_type: str, season: Optional[int],
                   episode: Optional[int], episode_end: Optional[int] = None,
                   require_subscription: bool = False) -> str:
        return "|".join([
            _normalize_title(title), str(year or ""), str(media_type or ""),
            str(season if season is not None else ""), str(episode if episode is not None else ""),
            str(episode_end if episode_end is not None else ""),
            str(require_subscription),
        ])

    def _cache_get(self, key: str) -> Optional[dict]:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.monotonic() - entry["at"] > self._ttl:
                self._cache.pop(key, None)
                return None
            return dict(entry["value"])

    def _cache_put(self, key: str, value: dict) -> None:
        with self._lock:
            # 简单兜底防无限增长
            if len(self._cache) > 512:
                self._cache.clear()
            self._cache[key] = {"at": time.monotonic(), "value": dict(value)}
