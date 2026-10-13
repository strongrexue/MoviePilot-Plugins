"""缺失判断服务（matcher）：依据 MoviePilot 自身的媒体库与订阅状态。

两级数据源（都是宿主**只读**能力，插件不重复建设）：
1. **订阅快照预筛**：``app.sdk.queries.list_subscriptions()`` 按标题+年份匹配订阅，
   ``lack_episode`` 为 0 说明不缺（可省掉一次媒体库查询）；
2. **媒体服务器存在性（主力）**：``MediaServerHelper`` 取已启用实例，
   ``module.media_exists(MediaInfo(...))`` → None 表示不存在；剧集返回
   ``seasons: {季: [已存在集]}``，据此判断目标集是否缺失。

两级都不可用（未配置媒体服务器、也没有订阅）时返回 ``missing=None``
（"无法判断"），由调用方决定跳过还是放行——不静默当成"不缺"。

性能：TG 消息可能密集，对判断结果做 60 秒 TTL 内存缓存，键为归一化媒体身份。
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, Optional

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


def _normalize_title(value: Any) -> str:
    """标题归一化：小写、去空白与常见分隔符，用于跨源比对。"""
    text = str(value or "").strip().lower()
    return _NORMALIZE_RE.sub("", text)


def _titles_match(left: str, right: str) -> bool:
    """两个标题是否指向同一媒体（相等或一方包含另一方）。"""
    a, b = _normalize_title(left), _normalize_title(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # 季/集后缀等差异常见，包含关系足够宽松地覆盖中英文标题混用
    return a in b or b in a


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
        # 1) 订阅快照预筛（不需要媒体服务器）
        subscription = self._match_subscription(title=title, year=year, season=season)
        if subscription is not None:
            lack = subscription.get("lack_episode")
            if lack is not None and int(lack) <= 0:
                return {
                    "missing": False,
                    "reason": "订阅已存在且无缺集",
                    "source": "subscription",
                    "detail": f"订阅「{subscription.get('name') or title}」lack_episode={lack}",
                }
            if lack is not None and int(lack) > 0:
                return {
                    "missing": True,
                    "reason": f"订阅缺 {int(lack)} 集",
                    "source": "subscription",
                    "detail": f"订阅「{subscription.get('name') or title}」",
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

        # 2) 媒体服务器存在性（主力）
        exists = self._query_media_exists(
            title=title, year=year, media_type=media_type, season=season,
            episode=episode, episode_end=episode_end,
        )
        if exists is not None:
            return exists

        # 3) 无数据源
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
            page = list_subscriptions()
            items = list(getattr(page, "items", None) or [])
        except Exception as err:
            logger.debug(f"读取宿主订阅失败：{err}")
            return None
        for item in items:
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
            }
        return None

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
        if not MEDIASERVER_AVAILABLE:
            return None
        try:
            helper = MediaServerHelper()
            # 注意：iterate_module_instances 产出的 ServiceInfo 里，带 media_exists 的
            # 是 **module**（媒体服务器模块基类实例，其内部会遍历该类型的全部服务）；
            # instance 是具体某个服务器实例（如 Emby 客户端对象），没有该方法——
            # 取错层级会报 "'Emby' object has no attribute 'media_exists'"。
            module = None
            for service in helper.iterate_module_instances():
                candidate = getattr(service, "module", None) or getattr(service, "instance", None)
                if candidate is not None and hasattr(candidate, "media_exists"):
                    module = candidate
                    break
            if module is None:
                return None
            mediainfo = self._build_media_info(
                title=title, year=year, media_type=media_type, season=season
            )
            exist = module.media_exists(mediainfo)
        except Exception as err:
            logger.info(f"查询媒体服务器存在性失败（按无法判断处理）：{err}")
            return None

        if exist is None:
            return {
                "missing": True,
                "reason": "媒体库中不存在",
                "source": "mediaserver",
                "detail": f"「{title}」在已配置媒体服务器中未找到",
            }
        seasons = getattr(exist, "seasons", None) or {}
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
