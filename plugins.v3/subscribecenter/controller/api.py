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
        ("/calendar", plugin.api_calendar, ["GET"], "今日日历：今天已入库/待播"),
        ("/card_theme", plugin.api_card_theme, ["GET"], "读取订阅卡片配色"),
        ("/card_theme/save", plugin.api_card_theme_save, ["POST"], "保存订阅卡片配色"),
        ("/run_once", plugin.api_run_once, ["POST"], "手动触发一次发现任务"),
        ("/preview", plugin.api_preview, ["POST"], "只读预览：跑一次但不写入"),
        ("/system_share", plugin.api_system_share, ["GET"], "读取订阅数据共享开关"),
        ("/system_share/save", plugin.api_system_share_save, ["POST"], "设置订阅数据共享开关"),
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


async def api_calendar(plugin) -> Any:
    """今日日历：今天已入库 / 今天待播的订阅。"""
    try:
        data = await plugin.calendar_today()
        return schemas.Response(success=True, data=api_schemas.CalendarView(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取今日日历失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取今日日历失败") from err


async def api_card_theme(plugin) -> Any:
    """读取订阅卡片配色。"""
    return schemas.Response(success=True, data=api_schemas.CardTheme(**plugin.card_theme_config()))


async def api_card_theme_save(plugin, request: api_schemas.CardThemeRequest) -> Any:
    """保存订阅卡片配色并写入宿主自定义 CSS。"""
    colors = None if request.reset else (request.colors or None)
    data = await plugin.apply_card_theme(colors=colors)
    return schemas.Response(
        success=bool(data.get("success")),
        message=str(data.get("error") or ""),
        data=api_schemas.CardThemeResult(
            success=bool(data.get("success")), error=str(data.get("error") or "")
        ),
    )


async def api_run_once(plugin, source: str = "") -> Any:
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


async def api_system_share(plugin) -> Any:
    """读取宿主的「订阅数据共享」开关。"""
    data = await plugin.system_share()
    return schemas.Response(success=True, data=api_schemas.SystemShareState(**data))


async def api_system_share_save(
    plugin, request: api_schemas.SystemShareRequest
) -> Any:
    """设置「订阅数据共享」开关（热门媒体依赖它）。"""
    data = await plugin.set_system_share(request.enabled)
    return schemas.Response(success=True, data=api_schemas.SystemShareState(**data))



