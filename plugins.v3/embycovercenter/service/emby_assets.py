"""媒体库与素材读取（基于 emby_gateway 透传）。

- 媒体库：``Library/VirtualFolders``（物理路径）+ ``Users/{uid}/Views``（用户可见排序）；
- 素材：``Items?ImageTypes=Primary|Backdrop``，把 ImageTags 拼成可直接访问的图片 URL
  （Emby 系约定：URL 带 ``api_key`` 与 ``tag``，宿主与参考实现均如此）。
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from . import emby_gateway
from .library_names import english_name_for

# 素材图尺寸：按 4K 画布（3840×2160）留足余量，避免服务器先压到 1260 高、
# 再被放大回 2160 导致糊掉。Emby 侧 ``maxHeight`` 只是上限，原图更小就按原图给。
POSTER_MAX_HEIGHT = 1000
BACKDROP_MAX_HEIGHT = 2160
LIBRARY_COVER_MAX_HEIGHT = 600
# 素材图质量：与渲染输出的 JPEG 画质保持一致，不在取图环节先降一档。
ASSET_QUALITY = 95
# 单次素材数量上限：预设里可能出现很大的数字（如海报墙 poster_count=40），
# 不设上限会让一次预览下载几十张图，直接拖到反向代理读超时。
MAX_POSTER_COUNT = 60
MAX_BACKDROP_COUNT = 6
# 题材标签上限：布局会把标签铺在画面左下角，超过 6 个只能无限缩字号。
MAX_GENRES = 6
# 素材/用户 ID 的短缓存，避免每次预览都重复请求。
_ADMIN_USER_CACHE: Dict[str, str] = {}
# 库名缓存：{(服务器名, 库ID): (时间戳, 名称)}。
_LIBRARY_NAME_CACHE: Dict[tuple, tuple] = {}
_LIBRARY_NAME_TTL = 300


def image_url(ref: emby_gateway.ServerRef, path: str, query: Optional[dict] = None) -> str:
    """拼接可直接访问的图片 URL（含 api_key，供引擎下载与前端展示）。"""
    return emby_gateway.real_url(ref, path, query)


def admin_user_id(ref: emby_gateway.ServerRef) -> Optional[str]:
    """返回管理员用户 ID（Emby 的部分查询需要用户上下文）；按服务器缓存。"""
    cached = _ADMIN_USER_CACHE.get(ref.name)
    if cached:
        return cached
    try:
        users = emby_gateway.get_json(ref, "Users")
    except emby_gateway.GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取用户列表失败: {error}")
        return None
    if not isinstance(users, list) or not users:
        return None
    resolved = None
    for user in users:
        if isinstance(user, dict) and (user.get("Policy") or {}).get("IsAdministrator"):
            resolved = user.get("Id")
            break
    if not resolved and isinstance(users[0], dict):
        resolved = users[0].get("Id")
    if resolved:
        _ADMIN_USER_CACHE[ref.name] = str(resolved)
        return str(resolved)
    return None


def list_libraries(ref: emby_gateway.ServerRef) -> List[Dict[str, Any]]:
    """返回媒体库列表（名称 / 类型 / 物理路径 / 当前封面 URL）。"""
    paths_map: Dict[str, List[str]] = {}
    try:
        virtual = emby_gateway.get_json(ref, "Library/VirtualFolders")
        for item in virtual or []:
            if isinstance(item, dict):
                paths_map[item.get("ItemId")] = list(item.get("Locations") or [])
    except emby_gateway.GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取物理路径失败（不影响列表）: {error}")

    uid = admin_user_id(ref)
    if not uid:
        return []
    views = emby_gateway.get_json(ref, f"Users/{uid}/Views")
    items = views.get("Items") if isinstance(views, dict) else views
    result: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        library_id = item.get("Id")
        if not library_id:
            continue
        result.append(
            {
                "id": str(library_id),
                "name": str(item.get("Name") or ""),
                "type": str(item.get("CollectionType") or "unknown"),
                "paths": paths_map.get(library_id, []),
                "cover_url": image_url(
                    ref,
                    f"Items/{library_id}/Images/Primary",
                    {"maxHeight": LIBRARY_COVER_MAX_HEIGHT, "quality": ASSET_QUALITY},
                ),
            }
        )
    return result


def library_count(ref: emby_gateway.ServerRef, library_id: str) -> int:
    """返回媒体库内条目数量（用于角标）。

    计数端点与素材查询、Emby 网页端保持一致（Users/{uid}/Items，管理员视图）——
    裸 /Items 无用户上下文，对隐藏/特殊条目的可见性不同，角标会与界面显示差一两数。

    音乐库只数专辑（MusicAlbum）——素材查询虽含艺术家兜底，但角标应反映
    用户认知里的库内容数，专辑 + 艺术家相加会显示翻倍。
    """
    types = _include_types(ref, library_id)
    if library_type(ref, library_id) == "music":
        types = "MusicAlbum"
    try:
        data = emby_gateway.get_json(
            ref,
            _items_endpoint(ref),
            {
                "ParentId": library_id,
                "Recursive": "true",
                "IncludeItemTypes": types,
                "Limit": 0,
                "EnableTotalRecordCount": "true",
            },
        )
    except emby_gateway.GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取媒体库数量失败: {error}")
        return 0
    if not isinstance(data, dict):
        return 0
    return int(data.get("TotalRecordCount") or 0)


def library_type(ref: emby_gateway.ServerRef, library_id: str) -> str:
    """返回媒体库的 CollectionType（movies / tvshows / music…），未知时为空串。"""
    try:
        data = emby_gateway.get_json(ref, "Library/MediaFolders")
        for item in (data or {}).get("Items", []) if isinstance(data, dict) else []:
            if str(item.get("Id") or "") == str(library_id):
                return str(item.get("CollectionType") or "")
    except emby_gateway.GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取媒体库类型失败: {error}")
    return ""


def library_name(ref: emby_gateway.ServerRef, library_id: str) -> str:
    """返回媒体库名称；取不到时返回空串（调用方自行回退到 ID）。

    预览 / 应用 / 自动封面每轮都要用库名当标题，这里按 (服务器, 库) 缓存 5 分钟，
    避免一次渲染里重复打 ``Users/{uid}/Views``。
    """
    if not library_id:
        return ""
    cache_key = (str(ref.name), str(library_id))
    cached = _LIBRARY_NAME_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < _LIBRARY_NAME_TTL:
        return cached[1]
    name = ""
    uid = admin_user_id(ref)
    if uid:
        try:
            views = emby_gateway.get_json(ref, f"Users/{uid}/Views")
            items = views.get("Items") if isinstance(views, dict) else views
            for item in items or []:
                if isinstance(item, dict) and str(item.get("Id") or "") == str(library_id):
                    name = str(item.get("Name") or "")
                    break
        except emby_gateway.GatewayError as error:
            logger.warning(f"[EmbyCoverCenter] 读取媒体库名称失败: {error}")
    if name:
        if len(_LIBRARY_NAME_CACHE) >= 64:
            _LIBRARY_NAME_CACHE.pop(next(iter(_LIBRARY_NAME_CACHE)), None)
        _LIBRARY_NAME_CACHE[cache_key] = (time.time(), name)
    return name


def library_genres(ref: emby_gateway.ServerRef, library_id: str) -> List[str]:
    """汇总媒体库内条目的题材（Emby ``Genres`` 字段），按出现次数降序取前几个。

    取不到（接口失败 / 库为空 / 未刮削）时返回空列表，由布局回退到手填标签。
    """
    if not library_id:
        return []
    try:
        # 题材只统计库的**主体类型**（音乐库取 MusicAlbum，不把 MusicArtist 也算进来），
        # 否则歌手条目会把标签稀释成演员名。
        include_types = _include_types(ref, library_id).split(",")[0]
        data = emby_gateway.get_json(
            ref,
            _items_endpoint(ref),
            {
                "ParentId": library_id,
                "Recursive": "true",
                "IncludeItemTypes": include_types,
                "Fields": "Genres",
                "Limit": 120,
                "EnableTotalRecordCount": "false",
            },
        )
    except emby_gateway.GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取媒体库题材失败: {error}")
        return []
    counts: Dict[str, int] = {}
    for item in (data or {}).get("Items", []) if isinstance(data, dict) else []:
        for genre in (item or {}).get("Genres") or []:
            text = str(genre or "").strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [name for name, _ in ranked[:MAX_GENRES]]


def _include_types(ref: emby_gateway.ServerRef, library_id: str) -> str:
    """按库类型决定素材查询的 IncludeItemTypes：音乐库取专辑封面 + 艺术家图
    （只刮削了艺术家的库专辑无 Primary，艺术家图兜底），电影/剧集库照旧，
    混合或未知库全类型兜底。"""
    kind = library_type(ref, library_id)
    if kind == "music":
        return "MusicAlbum,MusicArtist"
    if kind == "movies":
        return "Movie"
    if kind == "tvshows":
        return "Series"
    return "Movie,Series,MusicAlbum"


def _items_endpoint(ref: emby_gateway.ServerRef) -> str:
    uid = admin_user_id(ref)
    return f"Users/{uid}/Items" if uid else "Items"


def fetch_assets(
    ref: emby_gateway.ServerRef,
    library_id: str,
    *,
    mode: str = "random",
    poster_count: int = 6,
    backdrop_count: int = 1,
) -> Dict[str, Any]:
    """读取媒体库素材：背景 + 剧照 + 海报 + 数量。"""
    if not library_id:
        raise emby_gateway.GatewayError("缺少媒体库 ID")
    poster_count = max(0, min(int(poster_count or 0), MAX_POSTER_COUNT))
    backdrop_count = max(0, min(int(backdrop_count or 0), MAX_BACKDROP_COUNT))
    endpoint = _items_endpoint(ref)
    sort = {"SortBy": "Random"} if mode != "latest" else {"SortBy": "DateCreated", "SortOrder": "Descending"}

    # 先收集全部有效素材，再按 ChillPoster 的方式随机抽样（random.sample），
    # 而不是顺序截断：这样每次预览的素材组合都不一样。
    bg_url = ""
    backdrops: List[str] = []
    if backdrop_count > 0:
        try:
            data = emby_gateway.get_json(
                ref,
                endpoint,
                {
                    "ParentId": library_id,
                    "Recursive": "true",
                    "IncludeItemTypes": _include_types(ref, library_id),
                    "ImageTypes": "Backdrop",
                    "Fields": "ImageTags,BackdropImageTags",
                    "Limit": max(20, backdrop_count + 5),
                    **sort,
                },
            )
            pool: List[str] = []
            for item in (data or {}).get("Items", []) if isinstance(data, dict) else []:
                tags = item.get("BackdropImageTags") or []
                tag = tags[0] if tags else (item.get("ImageTags") or {}).get("Backdrop")
                if tag:
                    pool.append(
                        image_url(
                            ref,
                            f"Items/{item.get('Id')}/Images/Backdrop/0",
                            {"tag": tag, "maxHeight": BACKDROP_MAX_HEIGHT, "quality": ASSET_QUALITY},
                        )
                    )
            if pool:
                if mode == "random":
                    # 素材不够抽样时也要打散顺序：否则 pool[:n] 永远取前几张，
                    # 小库（比如只有一两张背景图）表现就是「随机抽取每次都一样」。
                    if len(pool) > backdrop_count:
                        backdrops = random.sample(pool, backdrop_count)
                    else:
                        shuffled = list(pool)
                        random.shuffle(shuffled)
                        backdrops = shuffled[:backdrop_count]
                else:
                    backdrops = pool[:backdrop_count]
                bg_url = backdrops[0]
        except emby_gateway.GatewayError as error:
            logger.warning(f"[EmbyCoverCenter] 读取背景图失败: {error}")

    posters: List[str] = []
    if poster_count > 0:
        try:
            data = emby_gateway.get_json(
                ref,
                endpoint,
                {
                    "ParentId": library_id,
                    "Recursive": "true",
                    "IncludeItemTypes": _include_types(ref, library_id),
                    "ImageTypes": "Primary",
                    "Fields": "ImageTags",
                    "Limit": max(30, poster_count + 10),
                    **sort,
                },
            )
            pool: List[str] = []
            for item in (data or {}).get("Items", []) if isinstance(data, dict) else []:
                tag = (item.get("ImageTags") or {}).get("Primary")
                if tag:
                    pool.append(
                        image_url(
                            ref,
                            f"Items/{item.get('Id')}/Images/Primary",
                            {"tag": tag, "maxHeight": POSTER_MAX_HEIGHT, "quality": ASSET_QUALITY},
                        )
                    )
            if pool:
                if mode == "random":
                    if len(pool) > poster_count:
                        posters = random.sample(pool, poster_count)
                    else:
                        shuffled = list(pool)
                        random.shuffle(shuffled)
                        posters = shuffled[:poster_count]
                else:
                    posters = pool[:poster_count]
        except emby_gateway.GatewayError as error:
            logger.warning(f"[EmbyCoverCenter] 读取海报失败: {error}")

    # 库名 / 英文名 / 题材一并带上：布局可以直接把库名当标题、库题材当标签，
    # 不必每个布局各自再查一次 Emby（「分类横幅」的按库主视觉与自动标签依赖这些）。
    name = library_name(ref, library_id)
    return {
        "bg_url": bg_url,
        "backdrops": backdrops,
        "posters": posters,
        "count": library_count(ref, library_id),
        "library_id": str(library_id),
        "library_name": name,
        "library_en": english_name_for(name) or name,
        "genres": library_genres(ref, library_id),
    }
