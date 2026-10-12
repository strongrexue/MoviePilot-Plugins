"""③ 订阅服务拉取：MP 榜单（走宿主 API，零新增依赖）。

包装 ``TmdbChain`` / ``BangumiChain``，把 ``MediaInfo`` 归一为统一的条目 dict
（``subscribe 模块`` 与豆瓣源共用同一份条目结构）。
"""
from __future__ import annotations

from typing import Any, List, Optional

from app.sdk.logging import logger


def _media_item(info: Any, fallback_media_type: str) -> dict:
    """把宿主 ``MediaInfo`` 归一为统一条目。

    条目字段（与豆瓣源一致）：``title / year / media_type / vote_average /
    tmdb_id / douban_id / bangumi_id / poster``。
    """
    media_type = ""
    try:
        media_type = getattr(info, "type", None).value if getattr(info, "type", None) else ""
    except Exception:  # pragma: no cover - type 可能是 str
        media_type = str(getattr(info, "type", "") or "")
    if not media_type:
        media_type = fallback_media_type
    return {
        "title": str(getattr(info, "title", "") or ""),
        "year": str(getattr(info, "year", "") or ""),
        "media_type": media_type,
        "vote_average": _to_float(getattr(info, "vote_average", None)),
        "tmdb_id": str(getattr(info, "tmdb_id", "") or ""),
        "douban_id": str(getattr(info, "douban_id", "") or ""),
        "bangumi_id": str(getattr(info, "bangumi_id", "") or ""),
        "poster": str(getattr(info, "poster_path", "") or ""),
    }


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _tmdb_chain():
    from app.chain.tmdb import TmdbChain

    return TmdbChain()


def _bangumi_chain():
    from app.chain.bangumi import BangumiChain

    return BangumiChain()


def _movie_type():
    from app.schemas.types import MediaType

    return MediaType.MOVIE


def _tv_type():
    from app.schemas.types import MediaType

    return MediaType.TV


def fetch_mp_source(source_key: str, *, page: int = 1, count: int = 30) -> List[dict]:
    """拉取一个 MP 榜单源，返回统一条目列表。

    全部走宿主**同步版**链方法（run_module 桥接到宿主自己的事件循环）：
    链的异步变体（async_*）依赖宿主 loop 上下文，放进我们自建的循环会永久
    挂起（run_sync 纪律：同步宿主 API 直接调用，绝不包 run_sync）。
    """
    if source_key == "tmdb_trending":
        infos = _tmdb_chain().tmdb_trending(page=page) or []
        return [_media_item(info, "all") for info in infos if info]
    if source_key == "tmdb_movie":
        infos = _tmdb_chain().tmdb_discover(
            mtype=_movie_type(), sort_by="popularity.desc", with_genres="",
            with_original_language="", with_keywords="", with_watch_providers="",
            vote_average=0.0, vote_count=0, release_date="", page=page,
        ) or []
        return [_media_item(info, "电影") for info in infos if info]
    if source_key == "tmdb_tv":
        infos = _tmdb_chain().tmdb_discover(
            mtype=_tv_type(), sort_by="popularity.desc", with_genres="",
            with_original_language="", with_keywords="", with_watch_providers="",
            vote_average=0.0, vote_count=0, release_date="", page=page,
        ) or []
        return [_media_item(info, "电视剧") for info in infos if info]
    if source_key == "bangumi_calendar":
        infos = _bangumi_chain().calendar() or []
        return [_media_item(info, "动画") for info in infos if info]
    logger.warning(f"未知的 MP 榜单源：{source_key}")
    return []
