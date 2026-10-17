"""宿主能力适配层 —— **本插件唯一直接 import 宿主 `app.*` 的地方**。

把「取数 / 写入 / 查询」收口在这里的好处：真机上出问题时，故障面是这薄薄一层，
而不是整条业务逻辑（开发文档 §16 的 adapter 收口策略）。

用到的入口与依据（MoviePilot v3.1.6）：

============================  ==================================================
能力                          入口
============================  ==================================================
写入订阅                      ``app.chain.subscribe.SubscribeChain.async_add``
标题识别（L3 搜索）             ``app.chain.media.MediaChain.async_recognize_by_meta``
跨源换算                      ``app.chain.media.MediaChain.async_convert_media_identity``
标题解析                      ``app.sdk.media.MetaInfo``
活跃订阅查询                   ``app.sdk.queries.async_list_subscriptions``
订阅历史查询                   ``app.sdk.queries.async_list_subscription_history``
枚举                          ``app.schemas.types.MediaType`` / ``MediaSource``
============================  ==================================================
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.constants import MEDIA_TYPE_MOVIE
from ..core.identity import HOST_SOURCE_TMDB
from ..core.window import parse_date

#: 单次查询的分页大小（宿主无参查询只返回第一页，必须显式翻页）
QUERY_PAGE_SIZE = 200


# --------------------------------------------------------------------- 枚举工具

def media_type_enum(media_type: str) -> Any:
    """``"movie"``/``"tv"`` → 宿主 ``MediaType``。"""
    from app.schemas.types import MediaType

    return MediaType.MOVIE if media_type == MEDIA_TYPE_MOVIE else MediaType.TV


def media_source_enum(value: Any) -> Any:
    """把来源值（字符串或枚举）规范为宿主 ``MediaSource``；非法返回 ``None``。"""
    from app.schemas.types import MediaSource

    if value is None:
        return None
    if isinstance(value, MediaSource):
        return value
    try:
        return MediaSource(str(value))
    except ValueError:
        return None


# --------------------------------------------------------------------- TMDB 解析

class HostTmdbResolver:
    """用宿主识别引擎实现 :class:`~..core.identity.TmdbResolver`。

    **为什么复用宿主识别而不是自己拼 TMDB 请求**：
    ``TmdbChain`` 没有 search 方法；宿主模块层的 ``TheMovieDbModule`` 虽可调用，
    但属于内部实现。而 ``MediaChain.async_recognize_by_meta`` 正是宿主自己
    「标题 → TMDB 识别」的稳定入口，包含标题变体与年份匹配策略。

    .. important::
       宿主识别**可能**返回非精确匹配（它内部有模糊回退）。因此本适配器
       把结果作为「候选」交给 :func:`~..core.identity.match_candidate_year`
       做**年份硬校验** —— 校验不过就只进 L4 待确认列表，绝不写入。
       Year 校验是我们加的那道闸门，宿主不提供。
    """

    async def search(
        self,
        title: str,
        year: Optional[str],
        media_type: str,
        *,
        limit: int = 5,
    ) -> Sequence[Dict[str, Any]]:
        """返回至多一个候选（宿主识别只给最佳匹配）。"""
        from app.chain.media import MediaChain

        try:
            metainfo = _build_metainfo(title, year, media_type)
            mediainfo = await MediaChain().async_recognize_by_meta(
                metainfo,
                media_source=media_source_enum(HOST_SOURCE_TMDB),
                obtain_images=False,
                mtype=media_type_enum(media_type),
            )
        except Exception:  # noqa: BLE001 - 识别失败等同「无候选」
            return ()

        if not mediainfo:
            # 宿主识别带年份约束，**续作必然失败**（Bangumi 写 2026，
            # TMDB 剧集是首季的 2022/2024）。兜底走不带年份的原始搜索。
            return await self._search_without_year(title, media_type)
        tmdb_id = getattr(mediainfo, "tmdb_id", None)
        if not tmdb_id:
            return await self._search_without_year(title, media_type)
        return (
            {
                "tmdb_id": tmdb_id,
                "title": getattr(mediainfo, "title", None) or title,
                "original_title": getattr(mediainfo, "original_title", None),
                "year": getattr(mediainfo, "year", None),
                "release_date": getattr(mediainfo, "release_date", None),
                "media_type": media_type,
            },
        )

    async def convert_to_tmdb(
        self,
        media_source: str,
        media_id: str,
        media_type: str,
    ) -> Optional[Dict[str, Any]]:
        """跨源换算为 TMDB（Bangumi/豆瓣 → TMDB）。

        .. important::
           宿主这条换算内部是**标题+年份匹配**（`_build_bangumi_tmdb_match`），
           不是 ID 直映。因此返回结构里带上年份，供调用方做二次硬校验。
        """
        from app.chain.media import MediaChain

        source_enum = media_source_enum(media_source)
        if source_enum is None:
            return None
        try:
            payload = await MediaChain().async_convert_media_identity(
                target_source=media_source_enum(HOST_SOURCE_TMDB),
                media_source=source_enum,
                media_id=str(media_id),
                mtype=media_type_enum(media_type),
            )
        except Exception:  # noqa: BLE001 - 换算失败等同「无法确认」
            return None
        if not payload:
            return None
        if isinstance(payload, dict):
            tmdb_id = payload.get("id")
            date = payload.get("release_date") or payload.get("first_air_date")
            title = payload.get("title") or payload.get("name")
            season = payload.get("season")
        else:
            tmdb_id = getattr(payload, "id", None)
            date = getattr(payload, "release_date", None) or getattr(payload, "first_air_date", None)
            title = getattr(payload, "title", None) or getattr(payload, "name", None)
            season = getattr(payload, "season", None)
        if not tmdb_id:
            return None
        try:
            season_number = int(season) if season not in (None, "") else None
        except (TypeError, ValueError):
            season_number = None
        return {
            "tmdb_id": str(tmdb_id),
            "year": str(date)[:4] if date else None,
            "title": title,
            #: 宿主从 Bangumi 标题解析出的季号；续作靠它才不会订错季
            "season": season_number,
        }


    async def _search_without_year(
        self, title: str, media_type: str
    ) -> Sequence[Dict[str, Any]]:
        """不带年份的 TMDB 搜索（续作兜底）。

        用「基础剧名」搜（去掉尾部季号）：Bangumi 的「牧神记5」对应 TMDB
        《牧神记》更靠后的集数，用「牧神记5」永远搜不到。

        .. note::
           这里**不传年份**是有意的：TMDB 剧集年份是首季首播年，
           续作条目年份必然不同，带年份会把正确结果滤掉。
           年份把关改由调用方的 `match_candidate_year`（剧集不做年份硬校验）
           与标题精确匹配共同承担。
        """
        from app.modules.themoviedb.tmdbapi import TmdbApi

        from .identity import strip_season_suffix

        base = strip_season_suffix(title) or title
        try:
            api = TmdbApi()
            if media_type == MEDIA_TYPE_MOVIE:
                records = await api.async_search_movies(base, "") or []
            else:
                records = await api.async_search_tvs(base, "") or []
        except Exception:  # noqa: BLE001 - 兜底失败等同无候选
            return ()

        candidates: List[Dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            tmdb_id = record.get("id")
            if not tmdb_id:
                continue
            title_field = record.get("title") if media_type == MEDIA_TYPE_MOVIE else record.get("name")
            date_field = (
                record.get("release_date") if media_type == MEDIA_TYPE_MOVIE
                else record.get("first_air_date")
            )
            candidates.append(
                {
                    "tmdb_id": tmdb_id,
                    "title": title_field or title,
                    "original_title": (
                        record.get("original_title") if media_type == MEDIA_TYPE_MOVIE
                        else record.get("original_name")
                    ),
                    "year": str(date_field)[:4] if date_field else None,
                    "release_date": date_field,
                    "media_type": media_type,
                }
            )
        return tuple(candidates)


def _build_metainfo(title: str, year: Optional[str], media_type: str) -> Any:
    """构造宿主 ``MetaInfo``（``year`` 属性是字符串口径）。"""
    from app.sdk.media import MetaInfo

    metainfo = MetaInfo(title)
    if year:
        metainfo.year = str(year)
    metainfo.type = media_type_enum(media_type)
    return metainfo


# --------------------------------------------------------------------- 订阅写入

class HostSubscribeBackend:
    """用宿主官方接口实现 :class:`~..core.writer.SubscribeBackend`。"""

    async def add(
        self,
        title: str,
        year: str,
        media_source: str,
        media_id: str,
        media_type: str,
        season: Optional[int] = None,
        *,
        message: bool = False,
        exist_ok: bool = False,
    ) -> Tuple[Optional[int], str]:
        """调用 ``SubscribeChain().async_add()``。

        身份走 ``media_source`` + ``media_id`` 成对字段（**没有** ``tmdbid`` 形参），
        ``title`` / ``year`` 是位置必填且 ``year`` 为字符串（开发文档 §7.3）。
        """
        from app.chain.subscribe import SubscribeChain

        source_enum = media_source_enum(media_source)
        if source_enum is None:
            return None, f"媒体来源非法：{media_source!r}"

        sid, msg = await SubscribeChain().async_add(
            title,
            str(year or ""),
            mtype=media_type_enum(media_type),
            season=season,
            media_source=source_enum,
            media_id=str(media_id),
            message=bool(message),
            exist_ok=bool(exist_ok),
        )
        return sid, str(msg or "")

    async def subscription_exists(self, media_source: str, media_id: str) -> bool:
        """该身份是否已有**活跃**订阅（``Subscribe`` 表，任意状态都算已有）。

        .. note::
           ``states`` 的权威取值是 ``N`` 新建 / ``R`` 订阅中 / ``P`` 待定 /
           ``S`` 暂停（``app/chain/subscribe/search.py:287``）。这里**不传 states**，
           因为「暂停」也算已订阅，重新订阅的行为由宿主策略决定，插件不介入。
        """
        from app.sdk.queries import (
            QueryPageRequest,
            SubscriptionFilter,
            async_list_subscriptions,
        )

        source_enum = media_source_enum(media_source)
        if source_enum is None:
            return False
        page = await async_list_subscriptions(
            SubscriptionFilter(media_source=source_enum, media_id=str(media_id)),
            QueryPageRequest(page=1, count=QUERY_PAGE_SIZE),
        )
        return bool(getattr(page, "total", 0))

    async def history_exists(self, media_source: str, media_id: str) -> bool:
        """该身份是否已有**已完成**订阅历史（``SubscribeHistory`` 表）。

        .. important::
           宿主 ``async_add()`` **不做这个检查**，而订阅完成后记录会移入
           ``SubscribeHistory``。宿主自己的「订阅分享/追更」路径正是用
           ``query.py:179`` 的 ``history_exists`` 来避免重复订阅的
           （开发文档 §7.6）。漏掉这一步会把「已经拿到过」的剧当新片重订。
        """
        from app.sdk.queries import (
            QueryPageRequest,
            SubscriptionHistoryFilter,
            async_list_subscription_history,
        )

        source_enum = media_source_enum(media_source)
        if source_enum is None:
            return False
        page = await async_list_subscription_history(
            SubscriptionHistoryFilter(media_source=source_enum, media_id=str(media_id)),
            QueryPageRequest(page=1, count=QUERY_PAGE_SIZE),
        )
        return bool(getattr(page, "total", 0))


# --------------------------------------------------------------------- 组装

def build_host_adapters() -> Dict[str, Any]:
    """构造运行时需要的全部宿主适配器（延迟导入，避免模块期副作用）。"""
    return {
        "tmdb": HostTmdbResolver(),
        "subscribe": HostSubscribeBackend(),
    }


def candidate_matches(
    candidate: Dict[str, Any],
    *,
    year: Optional[str],
) -> bool:
    """判断候选的年份是否与期望一致（L3 硬校验的单一实现点）。

    候选无年份、或期望年份为空时：前者判不通过（无法校验就不确认），
    后者判通过（调用方没要求校验）。
    """
    if not year:
        return True
    candidate_year = parse_date(candidate.get("year") or candidate.get("release_date"))
    if candidate_year is None:
        return False
    return str(candidate_year.year) == str(year)


__all__ = [
    "QUERY_PAGE_SIZE",
    "HostSubscribeBackend",
    "HostTmdbResolver",
    "build_host_adapters",
    "candidate_matches",
    "media_source_enum",
    "media_type_enum",
]
