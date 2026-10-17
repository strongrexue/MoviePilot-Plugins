"""SubscribeCenter API 路由声明与响应控制层。

约定（对齐本仓库既有插件与 V3 API 响应适配指南）：

- 路径前缀由宿主补全为 ``/api/v1/plugin/SubscribeCenter``，这里只写**裸路径**；
- 每个路由显式声明 ``response_model = schemas.Response[业务模型]``；
- 插件路由**不进入**宿主统一响应包装，因此必须自己声明一致的模型；
- 可预期业务失败返回 HTTP 400 + 友好 detail；未预期异常记日志后返回 500。
"""
from __future__ import annotations

from typing import Any, Dict, List

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException, Response

from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/status", plugin.api_status, ["GET"], "获取插件运行状态与各源情况"),
        ("/history", plugin.api_history, ["GET"], "分页查询发现/写入流水"),
        ("/subscriptions", plugin.api_subscriptions, ["GET"], "订阅总览：按状态分组"),
        ("/run_once", plugin.api_run_once, ["POST"], "手动触发一次发现任务"),
        ("/preview", plugin.api_preview, ["POST"], "只读预览：跑一次但不写入"),
        ("/mapping_cache", plugin.api_mapping_cache, ["GET"], "查看身份映射缓存"),
        ("/mapping_cache/fix", plugin.api_mapping_fix, ["POST"], "人工修正一条身份映射"),
        ("/poster", plugin.api_poster, ["GET"], "代理 TMDB 海报图片（浏览器不可直连）"),
    ]
    return [
        {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            # /poster 直接返回图片字节，不能套 JSON envelope 模型
            "response_model": None if path == "/poster" else _response_model(path),
            # **只有 /poster 允许匿名**：<img> 标签发起的请求不会携带 Bearer token，
            # 走 auth 必然 401（真机 F12：/poster?... -> 401 Unauthorized）。
            # 安全性可接受：该路由只代理 TMDB 海报，且 _poster_path 会拒绝非
            # TMDB 域名的地址，不会被当成任意 URL 代理。
            "allow_anonymous": path == "/poster",
        }
        for path, endpoint, methods, summary in definitions
    ]


# --------------------------------------------------------------------- 端点实现

async def api_status(plugin) -> Any:
    """返回插件运行状态。"""
    try:
        return schemas.Response(success=True, data=plugin.status_snapshot())
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 获取状态失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取插件状态失败") from err


async def api_history(
    plugin,
    page: int = 1,
    count: int = 20,
    decision: str = "",
    source: str = "",
    keyword: str = "",
) -> Any:
    """分页返回发现/写入流水。"""
    try:
        data = plugin.history_page(
            page=page,
            count=count,
            decision=decision,
            source=source,
            keyword=keyword,
        )
        return schemas.Response(success=True, data=data)
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 查询流水失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询流水失败") from err


async def api_subscriptions(plugin) -> Any:
    """订阅总览：宿主订阅按状态分组 + 明细（供「订阅总览」标签页）。"""
    data = await plugin.subscription_overview()
    return schemas.Response(success=True, data=api_schemas.SubscriptionOverview(**data))


async def api_run_once(plugin) -> Any:
    """手动触发一次发现任务。

    与定时任务共用同一把互斥锁（开发文档 §7.2）：已有运行在跑时返回
    ``skipped=True``，不排队、不并发。
    """
    try:
        result = await plugin.run_once()
        return schemas.Response(success=True, data=result)
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 手动运行失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="手动运行失败") from err


async def api_preview(plugin) -> Any:
    """只读预览：跑完整流水线但不写入订阅，返回会订哪些。

    与 `/run_once` 共用同一把互斥锁，但**不消耗每日写入额度**。
    """
    try:
        result = await plugin.preview()
        return schemas.Response(success=True, data=result)
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 预览失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="预览失败") from err


async def api_mapping_cache(plugin) -> Any:
    """返回映射缓存内容。"""
    try:
        return schemas.Response(success=True, data=plugin.mapping_cache_view())
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取映射缓存失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取映射缓存失败") from err


async def api_mapping_fix(plugin, request: api_schemas.MappingFixRequest) -> Any:
    """人工修正一条身份映射。"""
    try:
        key = request.key
        if not key and request.title:
            # 前端只让用户填 TMDB ID；键由后端按「归一化标题 + 年份 + 类型」生成，
            # 与身份解析用的键完全一致，所以下一次运行必定命中。
            from ..core.identity import normalize_title, strip_season_suffix, title_key

            key = title_key(
                normalize_title(strip_season_suffix(request.title)),
                request.year,
                request.media_type or "tv",
            )
        data = plugin.mapping_fix(
            key=key,
            media_source=request.media_source,
            media_id=request.media_id,
        )
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 修正映射失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="修正映射失败") from err
    if not data.get("success"):
        raise HTTPException(status_code=400, detail="媒体身份非法，未写入映射")
    return schemas.Response(success=True, data=data)


__all__ = [
    "api_history",
    "api_mapping_cache",
    "api_preview",
    "api_mapping_fix",
    "api_run_once",
    "api_status",
    "get_api",
]


async def api_poster(plugin, path: str = "") -> Any:
    """代理 TMDB 海报。

    ``path`` 是 TMDB 返回的 ``poster_path``（形如 ``/abc.jpg``）。
    走插件后端抓取，浏览器只连 MoviePilot —— 否则国内网络下
    ``image.tmdb.org`` 往往连不上，流水封面会整片空白。
    """
    try:
        payload = await plugin.poster_bytes(path)
    except Exception as err:  # noqa: BLE001
        logger.warning(f"[SubscribeCenter] 抓取海报失败：{err}")
        payload = None
    if not payload:
        raise HTTPException(status_code=404, detail="海报不存在")
    content, content_type = payload
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
