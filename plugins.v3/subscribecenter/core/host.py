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
import asyncio
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.constants import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV
from ..core.identity import HOST_SOURCE_TMDB
from ..core.window import parse_date, today

try:  # 宿主日志（插件内其它模块都这么用；失败时退回标准库，保证可离线单测）
    from app.sdk.logging import logger
except Exception:  # noqa: BLE001  # pragma: no cover
    import logging

    logger = logging.getLogger("SubscribeCenter")

#: 宿主 TMDB 的季详情查询并发上限。
#:
#: 真机教训：一次运行几百部剧、身份解析 8 路并发，每部剧还要查「最多 6 季」
#: 的详情 —— TMDB 很容易限流/超时。一旦异常，``resolve_target_season`` 的
#: fail-open 会把季号变成 ``None``，宿主按默认第 1 季订阅（「续作全订成 S1」）。
_SEASON_SEMAPHORE: Optional[Any] = None


def _season_semaphore() -> Any:
    """懒加载季详情查询信号量（在事件循环内创建）。"""
    global _SEASON_SEMAPHORE
    if _SEASON_SEMAPHORE is None:
        _SEASON_SEMAPHORE = asyncio.Semaphore(4)
    return _SEASON_SEMAPHORE

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

#: Bangumi 搜索接口的 UA（Bangumi 会拒绝默认 UA）
BANGUMI_SEARCH_USER_AGENT = "SubscribeCenter/1.0.0 (MoviePilot plugin; +https://github.com/strongrexue)"

#: 豆瓣 API 的并发上限（真机：不限制会被限流，别名大量返回空）
_DOUBAN_SEMAPHORE: Optional[Any] = None


def _douban_semaphore() -> Any:
    """懒加载一个模块级信号量（在事件循环里创建，避免跨循环复用）。"""
    global _DOUBAN_SEMAPHORE
    if _DOUBAN_SEMAPHORE is None:
        _DOUBAN_SEMAPHORE = asyncio.Semaphore(2)
    return _DOUBAN_SEMAPHORE


#: 抓海报时的 UA（图片 CDN 会拒绝空 UA）
IMAGE_USER_AGENT = "MoviePilot/SubscribeCenter"

#: 海报图片缓存（path -> (bytes, content_type)）。海报是不可变资源，可长期复用。
_IMAGE_CACHE: Dict[str, Any] = {}
_IMAGE_CACHE_LIMIT = 400


#: 从 TMDB 图片 URL 里抠出图片路径（``/t/p/original/abc.jpg`` -> ``/abc.jpg``）
_TMDB_IMAGE_RE = re.compile(r"/t/p/[^/]+(/[^\s]+)$")


def _poster_path(value: Any) -> Optional[str]:
    """把海报值归一化成 TMDB 图片**路径**（``/abc.jpg``）。

    真机：宿主识别返回的 ``poster_path`` **有时是完整 URL**
    （``https://image.tmdb.org/t/p/original/xxx.jpg``），有时是纯路径。
    存成完整 URL 会让前端直连 ``image.tmdb.org`` —— 国内网络下必然失败，
    表现为「只有少数卡片有图」（正好是那些拿到纯路径的条目）。
    """
    text = str(value or "").strip()
    if not text:
        return None
    match = _TMDB_IMAGE_RE.search(text)
    if match:
        return match.group(1)
    if text.startswith("/"):
        return text
    return None


async def fetch_poster_bytes(path: str) -> Optional[tuple]:
    """按 TMDB 的图片路径抓取海报字节，返回 ``(content, content_type)``。

    .. important::
       为什么必须由**后端**代理：TMDB 的 API 是服务器带的代理去访问的，
       但海报图片是**浏览器直连** ``image.tmdb.org`` —— 国内网络下常常
       根本连不上，于是流水里的封面全部空白（真机反馈）。
       走插件后端代理后，浏览器只连 MoviePilot，图片由服务器绕代理取回。
    """
    key = _poster_path(path)
    if not key:
        return None
    cached = _IMAGE_CACHE.get(key)
    if cached:
        return cached

    from app.runtime.settings import get_runtime_setting
    from app.sdk.network import AsyncRequestUtils

    url = f"https://image.tmdb.org/t/p/w185{key}"
    utils = AsyncRequestUtils(
        ua=IMAGE_USER_AGENT,
        proxies=get_runtime_setting("PROXY") or None,
        timeout=20,
    )
    response = await utils.get_res(url, raise_exception=True)
    if not response or not getattr(response, "content", None):
        return None
    content_type = str(getattr(response, "headers", {}).get("content-type") or "image/jpeg")
    payload = (bytes(response.content), content_type)
    if len(_IMAGE_CACHE) >= _IMAGE_CACHE_LIMIT:
        _IMAGE_CACHE.clear()
    _IMAGE_CACHE[key] = payload
    return payload


class HostTmdbResolver:
    """用宿主识别引擎实现 :class:`~..core.identity.TmdbResolver`。

    **为什么复用宿主识别而不是自己拼 TMDB 请求**：
    ``TmdbChain`` 没有 search 方法；宿主模块层的 ``TheMovieDbModule`` 虽可调用，
    但属于内部实现。而 ``MediaChain.async_recognize_media`` /
    ``async_recognize_by_meta`` 正是宿主自己「标题 → 媒体信息」的稳定入口，
    包含标题变体、跨源换算与年份匹配策略。
    """

    def __init__(self) -> None:
        """初始化按标题的豆瓣别名缓存（同一进程内复用，避免重复请求）。"""
        self._alias_cache: Dict[str, List[str]] = {}
        #: tmdb_id -> poster_path。**零额外请求**：resolve_target_season 里
        #: 为裁决季号本来就会拉 TMDB 详情，那份 JSON 就带 poster_path。
        self._poster_index: Dict[str, str] = {}

    def poster_path(self, tmdb_id: str) -> Optional[str]:
        """返回已抓到的海报路径（没有则为 None，不发起请求）。"""
        return self._poster_index.get(str(tmdb_id))

    async def search(
        self,
        title: str,
        year: Optional[str],
        media_type: str,
        *,
        limit: int = 5,
    ) -> Sequence[Dict[str, Any]]:
        """返回候选：宿主识别结果 + 不带年份的原始搜索。

        .. important::
           宿主识别**返回了结果**也要补两次搜索。真机踩过：宿主把
           「豫见她们 第2季」识别成了别的剧，我们的匹配规则拒掉之后就没有
           第二次机会，条目直接退化成「待确认」。识别结果只是**候选之一**，
           不是最终答案。

        .. important::
           这里调 **`async_recognize_media`**（宿主完整的多源识别，就是 MP 搜索框
           用的那条链路），而不是只调 `async_recognize_by_meta`。

           真机对照：另一个同类插件（doubancenter）只做
           ``plugin.chain.recognize_media(meta, mtype)`` 就够 —— 因为宿主内部会
           走 TMDB + 豆瓣 + Bangumi 并做跨源换算。而我们之前只调了单源变体，
           把最强的这条路径绕过去了，于是「人生交换」（TMDB 叫「交换人生」）
           这类译名不同的条目全部落进待确认。
        """
        from app.chain.media import MediaChain

        candidates: List[Dict[str, Any]] = []
        seen: set = set()

        def _append(mediainfo: Any, source: str) -> None:
            """把识别结果转成候选。"""
            tmdb_id = getattr(mediainfo, "tmdb_id", None) if mediainfo else None
            if not tmdb_id or str(tmdb_id) in seen:
                return
            seen.add(str(tmdb_id))
            candidates.append(
                {
                    "tmdb_id": tmdb_id,
                    "title": getattr(mediainfo, "title", None) or title,
                    "original_title": getattr(mediainfo, "original_title", None),
                    "year": getattr(mediainfo, "year", None),
                    "release_date": getattr(mediainfo, "release_date", None),
                    "media_type": media_type,
                    "poster_path": getattr(mediainfo, "poster_path", None),
                    "via": source,
                }
            )

        try:
            metainfo = _build_metainfo(title, year, media_type)
        except Exception:  # noqa: BLE001 - 构造失败等同无候选
            metainfo = None

        # ① 宿主完整多源识别（TMDB + 豆瓣 + Bangumi + 跨源换算）
        try:
            _append(
                await MediaChain().async_recognize_media(
                    metainfo, mtype=media_type_enum(media_type)
                ),
                "recognize_media",
            )
        except Exception:  # noqa: BLE001 - 识别失败只表示少一个候选
            pass

        # ② 指定 TMDB 源的识别（某些场景更精确）
        if metainfo is not None:
            try:
                _append(
                    await MediaChain().async_recognize_by_meta(
                        metainfo,
                        media_source=media_source_enum(HOST_SOURCE_TMDB),
                        obtain_images=False,
                        mtype=media_type_enum(media_type),
                    ),
                    "recognize_by_meta",
                )
            except Exception:  # noqa: BLE001
                pass

        # ③ 不带年份的原始搜索（绕过宿主那层「名称必须包含查询词」的过滤）
        for candidate in await self._search_without_year(title, media_type):
            key = str(candidate.get("tmdb_id"))
            if key and key not in seen:
                seen.add(key)
                candidates.append(candidate)

        return tuple(candidates[: max(limit, 1)])

    async def search_raw(
        self, term: str, media_type: str
    ) -> Sequence[Dict[str, Any]]:
        """按任意关键词做**原始** TMDB 搜索（不做任何名称过滤）。

        .. important::
           必须绕过宿主的 `TmdbApi.async_search_tvs` —— 它在结果上还加了一层
           过滤：`if title not in item_name: continue`，也就是说 TMDB 返回的
           条目名必须**包含**查询词才能留下。

           真机后果：豆瓣译名与 TMDB 中文名不同时，TMDB 自己明明搜得到，
           却被这层过滤丢掉了::

               查询「闹鬼酒店」-> TMDB 返回「酒店有鬼」(255752) -> 被丢
               查询「虚无的十字架」-> TMDB 返回「空洞的十字架」(326140) -> 被丢

           TMDB 的原始搜索会利用 alternative_titles / 原名做跨语言匹配，
           所以这里直接打 `/3/search/tv` 与 `/3/search/movie`。
        """
        if not term:
            return ()
        is_movie = media_type == MEDIA_TYPE_MOVIE
        path = "/search/movie" if is_movie else "/search/tv"
        try:
            payload = await self._tmdb_get(path, {"query": term, "page": 1})
        except Exception:  # noqa: BLE001 - 搜索失败等同无候选
            return ()

        candidates: List[Dict[str, Any]] = []
        for record in (payload or {}).get("results") or []:
            if not isinstance(record, dict):
                continue
            tmdb_id = record.get("id")
            if not tmdb_id:
                continue
            date = record.get("release_date") if is_movie else record.get("first_air_date")
            candidates.append(
                {
                    "tmdb_id": tmdb_id,
                    "title": record.get("title") if is_movie else record.get("name"),
                    "original_title": (
                        record.get("original_title") if is_movie else record.get("original_name")
                    ),
                    "year": str(date)[:4] if date else None,
                    "release_date": date,
                    "media_type": media_type,
                    "popularity": record.get("popularity"),
                }
            )
        return tuple(candidates)

    async def convert_to_tmdb(
        self,
        media_source: str,
        media_id: str,
        media_type: str,
    ) -> Optional[Dict[str, Any]]:
        """跨源换算为 TMDB（Bangumi/豆瓣 → TMDB）。

        返回 ``{"tmdb_id", "year", "title", "season"}``。

        .. danger::
           同样是**必须存在**的方法。0.8.4 的一次切片替换把它连同
           ``resolve_target_season`` 一起删掉了，真机后果是 Bangumi / 豆瓣
           条目的跨源换算静默失效，只能退回标题搜索（待确认数量上升）。

        .. important::
           宿主这条换算内部是**标题+年份匹配**（``_build_bangumi_tmdb_match``），
           不是 ID 直映。因此返回结构里带上年份，供调用方做二次硬校验。
        """
        from app.chain.media import MediaChain

        source_enum = media_source_enum(media_source)
        if source_enum is None:
            return None
        payload = await MediaChain().async_convert_media_identity(
            target_source=media_source_enum(HOST_SOURCE_TMDB),
            media_source=source_enum,
            media_id=str(media_id),
            mtype=media_type_enum(media_type),
        )
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
            #: 宿主从来源标题解析出的季号；续作靠它才不会订错季
            "season": season_number,
        }

    async def bangumi_aliases(self, title: str, media_type: str = "tv") -> List[str]:
        """用 Bangumi 搜索把**日文原名翻译成中文名**。

        为什么需要这一层：AniList 的日番条目给的是日文原名
        （`ジョジョの奇妙な冒険...`），而 TMDB 对日文标题的搜索命中率很差
        （真机实测：`ライフトレード` / `虚ろな十字架` 都是 0 条结果）。
        Bangumi 同一部番的 `name_cn` 就是主流中文译名，拿它再搜 TMDB 就能命中。

        于是 Bangumi 从「数据源」降级为「标题翻译层」——它不再负责发现，
        只负责在识别卡住时把日文名换成中文名。成本是每次一条额外请求，
        结果按标题缓存。
        """
        cache_key = f"{media_type}:{title}"
        if cache_key in self._alias_cache:
            return list(self._alias_cache[cache_key])

        names: List[str] = []
        try:
            payload = await self._bgm_search(title)
            names = _bangumi_names(payload, title)
        except Exception:  # noqa: BLE001 - 翻译失败只是少一条兜底
            names = []
        self._alias_cache[cache_key] = list(names)
        return names

    async def _bgm_search(self, keyword: str) -> Any:
        """调用 Bangumi 搜索接口（经宿主网络通道，容器内可直连 api.bgm.tv）。"""
        from urllib.parse import quote

        from app.runtime.settings import get_runtime_setting
        from app.sdk.network import AsyncRequestUtils

        url = (
            "https://api.bgm.tv/search/subject/"
            f"{quote(keyword)}?type=2&responseGroup=small&max_results=3"
        )
        utils = AsyncRequestUtils(
            ua=BANGUMI_SEARCH_USER_AGENT,
            proxies=get_runtime_setting("PROXY") or None,
            timeout=15,
        )
        response = await utils.get_res(url, raise_exception=True)
        if not response:
            return None
        try:
            return response.json()
        except Exception:  # noqa: BLE001 - 非 JSON 视为无结果
            return None

    async def douban_aliases(
        self,
        title: str,
        media_type: str,
        year: Optional[str] = None,
    ) -> List[str]:
        """用豆瓣 API 查该剧的「又名 / 原名」，用于 TMDB 搜索。

        .. important::
           豆瓣译名与 TMDB 中文名经常不同，而 TMDB 的搜索索引里**没有**豆瓣
           那个译名，直接搜命中率为 0::

               豆瓣「闹鬼酒店」  -> TMDB 搜 0 条（TMDB 叫「酒店有鬼」）
               豆瓣「虚无的十字架」-> TMDB 搜 0 条（TMDB 叫「空洞的十字架」）
               豆瓣「人生交换」  -> TMDB 搜 0 条（TMDB 叫「交换人生」）

           但豆瓣条目的 `aka` / `original_title` 里带着 TMDB 认识的名字
           （「酒店有鬼2」「ライフトレード」「Haunted Hotel Season 2」），
           所以拿它们再搜 TMDB 就能命中。

        .. important::
           **必须限流 + 重试**。真机事故：一次运行 371 条候选、8 路并发，
           豆瓣在几十次请求后开始拒绝，`douban_aliases` 大量返回空 ——
           于是「人生交换」这种只能靠别名命中的条目全部退化成待确认。
           这里用信号量把豆瓣并发压到 2，失败重试一次，并按标题缓存结果。

        :return: 候选名字列表（已去重、已剔除与原名相同的）；查询失败返回空列表
        """
        cache_key = f"{media_type}:{title}:{year or ''}"
        if cache_key in self._alias_cache:
            return list(self._alias_cache[cache_key])

        semaphore = _douban_semaphore()
        for attempt in (1, 2):
            try:
                async with semaphore:
                    names = await self._fetch_douban_aliases(title, media_type, year)
                self._alias_cache[cache_key] = list(names)
                return names
            except Exception:  # noqa: BLE001 - 豆瓣失败只是少一条兜底路径
                if attempt == 1:
                    await asyncio.sleep(0.6)
                    continue
                break
        self._alias_cache[cache_key] = []
        return []

    async def _fetch_douban_aliases(
        self, title: str, media_type: str, year: Optional[str]
    ) -> List[str]:
        "真正去豆瓣查询并抽取候选名字。"
        from app.modules.douban import DoubanApi

        api = DoubanApi()
        search = (
            api.async_movie_search if media_type == MEDIA_TYPE_MOVIE else api.async_tv_search
        )
        detail_call = (
            api.async_movie_detail if media_type == MEDIA_TYPE_MOVIE else api.async_tv_detail
        )

        result = await search(title, count=5)
        subjects = _douban_subjects(result)
        if not subjects:
            return []

        subject = _pick_douban_subject(subjects, title, year)
        subject_id = subject.get("id") or subject.get("target_id")
        if not subject_id:
            return []

        detail = await detail_call(str(subject_id)) or {}
        names: List[str] = []
        for value in (
            detail.get("original_title"),
            *(detail.get("aka") or []),
            detail.get("title"),
            subject.get("title"),
        ):
            text = str(value or "").strip()
            if len(text) >= 2 and text not in names and text != title:
                names.append(text)
        return names

    async def resolve_target_season(
        self,
        tmdb_id: str,
        media_type: str,
        season_hint: Optional[int] = None,
        tz_name: Optional[str] = None,
        *,
        prefer_episode_group: bool = True,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """确定该订阅**哪一季**（以及是否要用 episode group）。

        返回 ``(可订, 季号, episode_group_id)``。

        .. danger::
           这是**必须存在**的方法：缺失时 `IdentityResolver` 会 fail-open
           成「可订 + 默认季」，导致所有剧集都被按第 1 季订阅。
           0.8.4 修 bug 时一次切片替换把它连带删掉了，真机上表现为
           「黑帮领地本该订第 2 季却订了第 1 季」——
           `tests/v3/subscribecenter/test_host_structure.py` 会守住它。

        为什么需要 episode group（真机：《药屋少女的呢喃》）：

        - TMDB 把它压成 **1 季 60 集**连续编号（第 49~60 集才是第 3 季）。
        - 只按 season=1 订阅，宿主要去补前 48 集旧番。
        - 但 TMDB 的 ``episode_group``（type=6「Seasons」）里 **Season 3 = 12 集**，
          带 group + season=3 订阅后宿主只追这 12 集。

        判定顺序：

        1. 列出常规季（排除第 0 季），找**有未播集**的季；
        2. 一个都没有 -> 不可订；
        3. 提示季正好有未播集 -> 用它，不用 group；
        4. 多个季都有未播集且没有提示 -> 取**季号最大**的那个
           （回归系列的最新一季才是正在更新的那季；取默认季会把
           已经播完的第 1 季再订一遍）；
        5. 剧集被压成单季且提示季更大 -> 去 episode group 找同序号的季。

        **失败时 fail-open**（可订 + 默认季 + 无 group）。
        """
        if media_type != MEDIA_TYPE_TV:
            return (True, None, None)
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi
            from app.schemas.types import MediaType

            api = TmdbApi()
            info = await api.async_get_info(mtype=MediaType.TV, tmdbid=int(tmdb_id)) or {}
            poster = info.get("poster_path")
            if poster:
                self._poster_index[str(tmdb_id)] = str(poster)
            numbers = sorted(
                {
                    int(season.get("season_number") or 0)
                    for season in (info.get("seasons") or [])
                    if isinstance(season, dict) and int(season.get("season_number") or 0) > 0
                },
                reverse=True,
            )
            if not numbers:
                return (True, None, None)

            start = today(tz_name)
            # 只查「提示季 + 最新两季」：原来 numbers[:6]，每部剧最多 6 次 TMDB
            # 请求，几百部剧 8 路并发很容易触发限流 → 异常 → fail-open → 订成 S1。
            probed = list(numbers[:2])
            if season_hint is not None and season_hint in numbers and season_hint not in probed:
                probed.insert(0, season_hint)

            upcoming: List[int] = []
            async with _season_semaphore():
                for number in probed:
                    if await self._season_has_upcoming(api, int(tmdb_id), number, start):
                        upcoming.append(number)
                    if season_hint is not None and season_hint in upcoming:
                        break

            if not upcoming:
                return (False, None, None)
            if season_hint is not None and season_hint in upcoming:
                return (True, season_hint, None)

            # 被压成单季的番剧：去 episode group 里找真实季
            if prefer_episode_group and season_hint and len(numbers) == 1:
                group_id = await self._find_season_group(int(tmdb_id), season_hint, start)
                if group_id:
                    return (True, season_hint, group_id)

            # 多个季都有未播集：取季号最大的（最新一季才在更新）
            return (True, max(upcoming), None)
        except Exception as err:  # noqa: BLE001 - 校验失败 fail-open
            # 静默 fail-open 会让 season=None、宿主按第 1 季订阅，而日志里毫无痕迹
            # —— 1.0.1~1.0.4 的「续作全订成 S1」就是这样藏了四个版本。
            logger.warning(
                f"[SubscribeCenter] 季号裁决失败，回退默认季：tmdb={tmdb_id} "
                f"hint={season_hint} error={type(err).__name__}: {err}"
            )
            return (True, None, None)

    @staticmethod
    async def season_exists(tmdb_id: str, media_type: str, season: int) -> bool:
        """该剧是否存在第 N 季（不论是否播完）。

        用于消歧：多个同名候选里，只有正确那条才有「第 5 季」。
        播完与否交给 `finished` 闸门去标注，别把「已播完」误报成「搜不到」。
        """
        if media_type != MEDIA_TYPE_TV:
            return False
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi

            detail = await TmdbApi().async_get_tv_season_detail(int(tmdb_id), int(season)) or {}
            return bool(detail.get("episodes"))
        except Exception:  # noqa: BLE001 - 查询失败视为不存在
            return False

    @staticmethod
    async def async_poster_path(
        self, tmdb_id: str, media_type: str
    ) -> Optional[str]:
        """获取海报路径：先查已抓到的，没有再查一次 TMDB 详情。

        只有电影会走到「再查一次」—— 剧集的详情在季号裁决里已经拉过。
        """
        cached = self._poster_index.get(str(tmdb_id))
        if cached:
            return cached
        try:
            path = f"/3/{'movie' if media_type == MEDIA_TYPE_MOVIE else 'tv'}/{tmdb_id}"
            payload = await self._tmdb_get(path)
            poster = (payload or {}).get("poster_path")
            if poster:
                self._poster_index[str(tmdb_id)] = str(poster)
                return str(poster)
        except Exception:  # noqa: BLE001 - 海报只是展示用，失败不影响订阅
            return None
        return None

    @staticmethod
    async def _season_has_upcoming(api: Any, tmdb_id: int, season: int, start: Any) -> bool:
        """该季是否还有未播集。

        .. danger::
           **必须带 `@staticmethod`。** 1.0.1 的一次编辑把它弄丢了，而签名第一个
           参数是 ``api`` —— 绑定成实例方法后，``self._season_has_upcoming(api, ...)``
           会让 ``self`` 占掉 ``api`` 的位置，**每次调用都 TypeError**，再被
           ``resolve_target_season`` 的 fail-open 静默吞掉：季号变成 ``None``，
           宿主按默认第 1 季订阅。真机表现就是「所有续作都订成 S1」。
           ``test_host_structure.py`` 现在会锁住这个装饰器。

        失败**重试一次**：TMDB 偶发 429/超时同样会退化成 fail-open，
        而 fail-open 的代价是整部剧订错季。
        """
        detail: Any = None
        for attempt in (1, 2):
            try:
                detail = await api.async_get_tv_season_detail(tmdb_id, season) or {}
                break
            except Exception as err:  # noqa: BLE001
                if attempt == 2:
                    raise
                logger.warning(
                    f"[SubscribeCenter] 查询季详情失败，重试一次：tmdb={tmdb_id} "
                    f"S{season} error={type(err).__name__}"
                )
                await asyncio.sleep(0.4)
        detail = detail or {}
        for episode in detail.get("episodes") or []:
            if not isinstance(episode, dict):
                continue
            air = parse_date(episode.get("air_date"))
            if air and air >= start:
                return True
        return False

    async def _find_season_group(
        self, tmdb_id: int, season_hint: int, start: Any
    ) -> Optional[str]:
        """在被压成单季的剧里找出「第 N 季」的 episode group id。

        只在**该分组确实有未播集**时返回，避免为了一个已经播完的季去建订阅。
        """
        groups = await self._tmdb_get(f"/tv/{tmdb_id}/episode_groups")
        group_id = None
        for entry in (groups or {}).get("results") or []:
            # type 6 = 「Seasons」分组（实测：药屋少女的呢喃）
            if str(entry.get("type")) == "6" and int(entry.get("group_count") or 0) > 1:
                group_id = entry.get("id")
                break
        if not group_id:
            return None

        payload = await self._tmdb_get(f"/tv/episode_group/{group_id}")
        for group in (payload or {}).get("groups") or []:
            order = int(group.get("order") or 0)
            name = str(group.get("name") or "")
            if order != season_hint and name != f"Season {season_hint}":
                continue
            for episode in group.get("episodes") or []:
                air = parse_date(episode.get("air_date"))
                if air and air >= start:
                    return str(group_id)
            return None
        return None

    @staticmethod
    async def _tmdb_get(
        path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """直连 TMDB 原始接口（宿主的 TmdbApi 未暴露 episode_groups 列表）。"""
        from app.runtime.settings import get_runtime_setting
        from app.sdk.network import AsyncRequestUtils

        domain = get_runtime_setting("TMDB_API_DOMAIN") or "api.themoviedb.org"
        key = get_runtime_setting("TMDB_API_KEY") or ""
        url = f"https://{domain}/3{path}"
        utils = AsyncRequestUtils(
            proxies=get_runtime_setting("PROXY") or None,
            timeout=20,
        )
        query = {"api_key": key, "language": "zh-CN"}
        query.update(params or {})
        response = await utils.get_res(url, params=query, raise_exception=True)
        if not response:
            return {}
        return response.json() or {}

    async def _search_without_year(
        self, title: str, media_type: str, *, normalize: bool = True
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

        base = (strip_season_suffix(title) or title) if normalize else title
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


def _douban_subjects(result: Any) -> List[Dict[str, Any]]:
    """从豆瓣搜索响应里取出条目列表（不同接口的键不同）。"""
    if not isinstance(result, dict):
        return []
    for key in ("subject_collection_items", "items", "subjects"):
        value = result.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    return []


def _pick_douban_subject(
    subjects: Sequence[Dict[str, Any]], title: str, year: Optional[str]
) -> Dict[str, Any]:
    """挑最像的那条豆瓣条目：先看标题相似度，再看年份。"""
    from ..core.identity import normalize_title

    target = normalize_title(title)
    best = subjects[0]
    best_score = -1.0
    for subject in subjects:
        name = normalize_title(subject.get("title") or subject.get("target", {}).get("title"))
        score = 1.0 if name == target else 0.0
        if name and target and (name in target or target in name):
            score = max(score, 0.5)
        subject_year = str(subject.get("year") or "")
        if year and subject_year and subject_year == str(year):
            score += 0.25
        if score > best_score:
            best_score = score
            best = subject
    return best


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
        episode_group: Optional[str] = None,
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
            # episode_group 用于「被 TMDB 压成单季」的番剧按真实季精确订阅
            # （真机：《药屋少女的呢喃》TMDB 是 1 季 60 集连续编号，
            #  但 episode group 里 Season 3 = 第 49~60 集。带 group + season=3
            #  订阅后宿主只追这 12 集，不会去补前 48 集旧番。）
            episode_group=episode_group or None,
            season=season,
            media_source=source_enum,
            media_id=str(media_id),
            message=bool(message),
            exist_ok=bool(exist_ok),
        )
        return sid, str(msg or "")

    async def subscription_exists(
        self, media_source: str, media_id: str, season: Optional[int] = None
    ) -> bool:
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
            SubscriptionFilter(
                media_source=source_enum, media_id=str(media_id), season=season
            ),
            QueryPageRequest(page=1, count=QUERY_PAGE_SIZE),
        )
        return bool(getattr(page, "total", 0))

    async def history_exists(
        self, media_source: str, media_id: str, season: Optional[int] = None
    ) -> bool:
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
            SubscriptionHistoryFilter(
                media_source=source_enum, media_id=str(media_id), season=season
            ),
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



def _bangumi_names(payload: Any, keyword: str) -> List[str]:
    """从 Bangumi 搜索结果里挑出「和关键字同一部作品」的中文名。

    Bangumi 是老站，搜索经常返回一堆无关条目（尤其用日文长标题搜时），
    因此这里要求结果与关键字的**归一化后相似度**足够高才采用，
    否则宁可返回空 —— 错译比不译更糟（会把 A 番订成 B 番）。
    """
    if not isinstance(payload, dict):
        return []
    rows = payload.get("list")
    if not isinstance(rows, list):
        return []

    from .identity import normalize_title

    target = normalize_title(keyword)
    names: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidates = [row.get("name_cn"), row.get("name")]
        for value in candidates:
            text = str(value or "").strip()
            if not text or text in names:
                continue
            normalized = normalize_title(text)
            # 至少有一半字符重合才算同一部作品
            if _overlap_ratio(target, normalized) >= 0.5:
                names.append(text)
    return names


def _overlap_ratio(left: str, right: str) -> float:
    """两个字串的字符集合重合度（0~1）。"""
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    return len(common) / max(len(set(left)), 1)
