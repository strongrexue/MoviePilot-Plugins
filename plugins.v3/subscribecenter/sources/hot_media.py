"""「热门媒体」发现源：读取 MoviePilot 官方的热门订阅统计。

数据来自官方服务端 ``/subscribe/statistic``（宿主的
``MoviePilotServerHelper.async_get_subscribe_statistic``），
内容就是主程序「热门订阅」页看到的同一份数据 —— 大家都订了什么。

.. important::
   该接口要求宿主开启 **「订阅数据共享」**（``SUBSCRIBE_STATISTIC_SHARE``）；
   未开启时官方服务端直接返回空数组，本源会明确报错而不是静默空跑。

筛选（与「自动订阅助手」对齐）：

- **风格**：TMDB genre id 列表；选了多个时依次查询再按媒体去重
- **评分下限** / **订阅人次下限**：0 表示不限
"""
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core.constants import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    SOURCE_HOT_MEDIA,
)
from ..core.model import DiscoveredItem


class HotMediaSource:
    """热门订阅统计源（电影 + 剧集两组，各自独立取数与筛选）。

    :param helper: 可选注入的宿主 helper（便于测试），需提供
        ``async_get_subscribe_statistic(stype=..., page=..., count=...,
        genre_id=..., min_rating=...)``
    """

    def __init__(self, helper: Any = None) -> None:
        self._helper = helper

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_HOT_MEDIA

    def _get_helper(self) -> Any:
        if self._helper is not None:
            return self._helper
        from app.adapters.external.server import MoviePilotServerHelper

        self._helper = MoviePilotServerHelper
        return self._helper

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """拉取电影 + 剧集两组热门订阅并归一为发现条目。"""
        groups = []
        if config.get("hot_media_movie_enabled", True):
            groups.append(("movie", MEDIA_TYPE_MOVIE, "MOV"))
        if config.get("hot_media_tv_enabled", True):
            groups.append(("tv", MEDIA_TYPE_TV, "TV"))
        if not groups:
            raise RuntimeError("热门媒体：电影与剧集都没有勾选，抓不到任何内容")

        helper = self._get_helper()
        items: List[DiscoveredItem] = []
        seen: set = set()
        empty_groups: List[str] = []

        for prefix, media_type, stype in groups:
            limit = _int(config.get(f"hot_media_{prefix}_limit"), 20)
            min_rating = _float(config.get(f"hot_media_{prefix}_min_rating")) or 0.0
            min_count = _int(config.get(f"hot_media_{prefix}_min_count"), 0)
            genres = _genres(config.get(f"hot_media_{prefix}_genres"))
            got_any = False

            for genre_id in genres or [None]:
                kwargs: Dict[str, Any] = {"stype": stype, "page": 1, "count": max(1, limit)}
                if genre_id is not None:
                    kwargs["genre_id"] = genre_id
                if min_rating > 0:
                    kwargs["min_rating"] = min_rating
                try:
                    rows = await helper.async_get_subscribe_statistic(**kwargs)
                except Exception as err:  # noqa: BLE001 - 单次查询失败直接上报
                    logger.warning(
                        f"[SubscribeCenter] 热门媒体（{stype} genre={genre_id}）取数失败：{err}"
                    )
                    raise
                if not rows:
                    continue
                got_any = True
                for row in rows:
                    item = self._to_item(row, media_type, min_count, min_rating)
                    if item is None or item.source_id in seen:
                        continue
                    seen.add(item.source_id)
                    items.append(item)

            if not got_any:
                empty_groups.append(stype)

        if not items and empty_groups:
            raise RuntimeError(
                "热门媒体：官方返回空数据。"
                "请确认已开启 MoviePilot 的「订阅数据共享」（SUBSCRIBE_STATISTIC_SHARE），"
                "或放宽风格 / 评分 / 人次筛选"
            )
        logger.info(f"[SubscribeCenter] 热门媒体：取到 {len(items)} 条")
        return items

    @staticmethod
    def _to_item(
        row: Dict[str, Any],
        media_type: str,
        min_count: int,
        min_rating: float,
    ) -> Optional[DiscoveredItem]:
        """把官方统计的一行转成 :class:`DiscoveredItem`（本地复核筛选）。"""
        title = str(row.get("name") or "").strip()
        if not title:
            return None
        subscribed = _int(row.get("count"), 0)
        if min_count and subscribed < min_count:
            return None
        rating = _float(row.get("rating"))
        if min_rating and rating is not None and rating < min_rating:
            return None
        media_source = str(row.get("media_source") or "").strip().lower()
        media_id = row.get("media_id")
        source_id = f"{media_source}:{media_id}" if media_id is not None else title
        native_ids: Dict[str, str] = {}
        if media_source and media_id is not None:
            native_ids[media_source] = str(media_id)
        return DiscoveredItem(
            source=SOURCE_HOT_MEDIA,
            source_id=source_id,
            title=title,
            media_type=media_type,
            year=str(row.get("year") or "") or None,
            season=_int(row.get("season"), 0) or None,
            rating=rating,
            popularity=float(subscribed) if subscribed else None,
            native_ids=native_ids,
        )


def _genres(value: Any) -> List[int]:
    """把配置里的风格列表规范成 int 列表（兼容字符串 / 单值）。"""
    if value is None or value == "":
        return []
    raw = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    genres: List[int] = []
    for item in raw:
        try:
            genres.append(int(item))
        except (TypeError, ValueError):
            continue
    return genres


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
