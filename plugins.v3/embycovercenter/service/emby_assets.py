"""媒体库与素材读取（基于 emby_gateway 透传）。

- 媒体库：``Library/VirtualFolders``（物理路径）+ ``Users/{uid}/Views``（用户可见排序）；
- 素材：``Items?ImageTypes=Primary|Backdrop``，把 ImageTags 拼成可直接访问的图片 URL
  （Emby 系约定：URL 带 ``api_key`` 与 ``tag``，宿主与参考实现均如此）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from . import emby_gateway

POSTER_MAX_HEIGHT = 600
BACKDROP_MAX_HEIGHT = 2160
LIBRARY_COVER_MAX_HEIGHT = 300


def image_url(ref: emby_gateway.ServerRef, path: str, query: Optional[dict] = None) -> str:
    """拼接可直接访问的图片 URL（含 api_key，供引擎下载与前端展示）。"""
    return emby_gateway.real_url(ref, path, query)


def admin_user_id(ref: emby_gateway.ServerRef) -> Optional[str]:
    """返回管理员用户 ID（Emby 的部分查询需要用户上下文）。"""
    try:
        users = emby_gateway.get_json(ref, "Users")
    except emby_gateway.GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取用户列表失败: {error}")
        return None
    if not isinstance(users, list) or not users:
        return None
    for user in users:
        if isinstance(user, dict) and (user.get("Policy") or {}).get("IsAdministrator"):
            return user.get("Id")
    return users[0].get("Id") if isinstance(users[0], dict) else None


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
                    {"maxHeight": LIBRARY_COVER_MAX_HEIGHT, "quality": 90},
                ),
            }
        )
    return result


def library_count(ref: emby_gateway.ServerRef, library_id: str) -> int:
    """返回媒体库内影片 / 剧集数量（用于角标）。"""
    try:
        data = emby_gateway.get_json(
            ref,
            "Items",
            {
                "ParentId": library_id,
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Series",
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
    endpoint = _items_endpoint(ref)
    sort = {"SortBy": "Random"} if mode != "latest" else {"SortBy": "DateCreated", "SortOrder": "Descending"}

    backdrops: List[str] = []
    if backdrop_count > 0:
        try:
            data = emby_gateway.get_json(
                ref,
                endpoint,
                {
                    "ParentId": library_id,
                    "Recursive": "true",
                    "IncludeItemTypes": "Movie,Series",
                    "ImageTypes": "Backdrop",
                    "Fields": "ImageTags,BackdropImageTags",
                    "Limit": max(20, backdrop_count + 5),
                    **sort,
                },
            )
            for item in (data or {}).get("Items", []) if isinstance(data, dict) else []:
                tags = item.get("BackdropImageTags") or []
                tag = tags[0] if tags else (item.get("ImageTags") or {}).get("Backdrop")
                if tag:
                    backdrops.append(
                        image_url(
                            ref,
                            f"Items/{item.get('Id')}/Images/Backdrop/0",
                            {"tag": tag, "maxHeight": BACKDROP_MAX_HEIGHT, "quality": 90},
                        )
                    )
                if len(backdrops) >= max(2, backdrop_count):
                    break
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
                    "IncludeItemTypes": "Movie,Series",
                    "ImageTypes": "Primary",
                    "Fields": "ImageTags",
                    "Limit": max(30, poster_count + 10),
                    **sort,
                },
            )
            for item in (data or {}).get("Items", []) if isinstance(data, dict) else []:
                tag = (item.get("ImageTags") or {}).get("Primary")
                if tag:
                    posters.append(
                        image_url(
                            ref,
                            f"Items/{item.get('Id')}/Images/Primary",
                            {"tag": tag, "maxHeight": POSTER_MAX_HEIGHT, "quality": 90},
                        )
                    )
                if len(posters) >= poster_count:
                    break
        except emby_gateway.GatewayError as error:
            logger.warning(f"[EmbyCoverCenter] 读取海报失败: {error}")

    return {
        "bg_url": backdrops[0] if backdrops else (posters[0] if posters else ""),
        "backdrops": backdrops,
        "posters": posters,
        "count": library_count(ref, library_id),
    }
