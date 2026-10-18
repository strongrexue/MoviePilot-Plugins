"""「热门媒体」发现源：读取 MoviePilot 官方的热门订阅统计。

数据来自官方服务端 ``/subscribe/statistic``（宿主的
``MoviePilotServerHelper.async_get_subscribe_statistic``），
内容就是主程序「热门订阅」页看到的同一份数据 —— 大家都订了什么。

.. important::
   该接口要求宿主开启 **「订阅数据共享」**（``SUBSCRIBE_STATISTIC_SHARE``）；
   未开启时官方服务端直接返回空数组，本源会明确报错而不是静默空跑。
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
    """热门订阅统计源（电影 + 剧集两组，各自独立取数）。

    :param helper: 可选注入的宿主 helper（便于测试），需提供
        ``async_get_subscribe_statistic(stype=..., page=..., count=...)``
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
            groups.append((MEDIA_TYPE_MOVIE, "MOV", _int(config.get("hot_media_movie_limit"), 20)))
        if config.get("hot_media_tv_enabled", True):
            groups.append((MEDIA_TYPE_TV, "TV", _int(config.get("hot_media_tv_limit"), 20)))
        if not groups:
            raise RuntimeError("热门媒体：电影与剧集都没有勾选，抓不到任何内容")

        helper = self._get_helper()
        min_count = _int(config.get("hot_media_min_count"), 0)
        items: List[DiscoveredItem] = []
        empty_groups: List[str] = []

        for media_type, stype, limit in groups:
            try:
                rows = await helper.async_get_subscribe_statistic(
                    stype=stype, page=1, count=max(1, limit)
                )
            except Exception as err:  # noqa: BLE001 - 单组失败不影响另一组
                logger.warning(f"[SubscribeCenter] 热门媒体（{stype}）取数失败：{err}")
                raise
            if not rows:
                empty_groups.append(stype)
                continue
            for row in rows:
                item = self._to_item(row, media_type, min_count)
                if item is not None:
                    items.append(item)

        if not items and empty_groups:
            raise RuntimeError(
                "热门媒体：官方返回空数据。"
                "请确认已开启 MoviePilot 的「订阅数据共享」（SUBSCRIBE_STATISTIC_SHARE）"
            )
        logger.info(f"[SubscribeCenter] 热门媒体：取到 {len(items)} 条")
        return items

    @staticmethod
    def _to_item(row: Dict[str, Any], media_type: str, min_count: int) -> Optional[DiscoveredItem]:
        """把官方统计的一行转成 :class:`DiscoveredItem`。"""
        title = str(row.get("name") or "").strip()
        if not title:
            return None
        subscribed = _int(row.get("count"), 0)
        if min_count and subscribed < min_count:
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
            rating=_float(row.get("rating")),
            popularity=float(subscribed) if subscribed else None,
            native_ids=native_ids,
        )


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
