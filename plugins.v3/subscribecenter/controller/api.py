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
from fastapi import HTTPException

from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/status", plugin.api_status, ["GET"], "获取插件运行状态与各源情况"),
        ("/history", plugin.api_history, ["GET"], "分页查询发现/写入流水"),
        ("/run_once", plugin.api_run_once, ["POST"], "手动触发一次发现任务"),
        ("/mapping_cache", plugin.api_mapping_cache, ["GET"], "查看身份映射缓存"),
        ("/mapping_cache/fix", plugin.api_mapping_fix, ["POST"], "人工修正一条身份映射"),
    ]
    return [
        {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            "response_model": _response_model(path),
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
        data = plugin.mapping_fix(
            key=request.key,
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
    "api_mapping_fix",
    "api_run_once",
    "api_status",
    "get_api",
]
