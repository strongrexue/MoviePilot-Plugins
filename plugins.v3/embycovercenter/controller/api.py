"""EmbyCoverCenter API 路由声明与统一响应控制层。

约定（对齐 MoviePilot V3 API 响应适配指南）：
- 路径前缀由宿主补全为 ``/api/v1/plugin/<PluginID>``；
- 每个路由显式声明 ``response_model = schemas.Response[业务模型]``；
- 查询正常但无数据时仍返回 ``success=True``，不把空结果当成失败；
- 未预期异常记录日志后交给宿主错误层，不把堆栈写进 ``message``。
"""
from __future__ import annotations

from typing import Any, Dict, List

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException

from ..service import emby_tasks as tasks_service
from ..service.emby_gateway import GatewayError
from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/ping", plugin.api_ping, ["GET"], "连通性探针"),
        ("/status", plugin.api_status, ["GET"], "获取插件与媒体服务器状态"),
        ("/emby_tasks", plugin.api_emby_tasks, ["GET"], "获取 Emby 计划任务列表"),
        ("/emby_tasks/{task_id}", plugin.api_emby_task_detail, ["GET"], "获取 Emby 单个计划任务与触发器"),
        ("/emby_tasks/{task_id}/triggers", plugin.api_emby_task_triggers_save, ["POST"], "保存 Emby 计划任务触发器"),
        ("/emby_tasks/{task_id}/run", plugin.api_emby_task_run, ["POST"], "立即运行 Emby 计划任务"),
        ("/emby_tasks/{task_id}/stop", plugin.api_emby_task_stop, ["POST"], "停止 Emby 计划任务"),
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


def _raise_gateway_http(error: GatewayError) -> None:
    """把网关错误映射为合适的 HTTP 状态码（配置类问题 400，其余 502）。"""
    text = str(error)
    if any(token in text for token in ("未配置", "未找到", "不支持", "缺失", "缺少")):
        raise HTTPException(status_code=400, detail=text)
    raise HTTPException(status_code=502, detail=text)


def _to_response(result: Any, data_model) -> Any:
    """把业务结果统一包装成单层 V3 响应。"""
    if isinstance(result, schemas.Response):
        return result
    payload = result or None
    data = None
    if payload is not None:
        try:
            data = data_model.model_validate(payload)
        except Exception as error:  # pragma: no cover - 仅防御性
            logger.error(f"[EmbyCoverCenter] 响应模型校验失败: {error}")
    return schemas.Response(success=True, message="", data=data)


def api_ping(plugin):
    """连通性探针：确认 API 注册与前后端链路已打通。"""
    return _to_response(
        {
            "plugin_version": plugin.plugin_version,
            "enabled": plugin.get_state(),
            "message": "pong",
        },
        api_schemas.PingData,
    )


def api_status(plugin):
    """返回插件状态与已启用的媒体服务器列表。"""
    return _to_response(
        {
            "plugin_version": plugin.plugin_version,
            "enabled": plugin.get_state(),
            "selected_servers": plugin.selected_servers,
            "servers": plugin.list_servers(),
        },
        api_schemas.StatusData,
    )


def api_emby_tasks(plugin, server: str = ""):
    """返回归一化后的 Emby 计划任务列表。"""
    try:
        payload = tasks_service.list_tasks(server)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except GatewayError as error:
        _raise_gateway_http(error)
        return None
    return _to_response(payload, api_schemas.EmbyTaskListData)


def api_emby_task_detail(plugin, task_id: str, server: str = ""):
    """返回单个 Emby 计划任务与触发器。"""
    try:
        payload = tasks_service.get_task(server, task_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except GatewayError as error:
        _raise_gateway_http(error)
        return None
    return _to_response(payload, api_schemas.EmbyTaskData)


def api_emby_task_triggers_save(plugin, task_id: str, request):
    """保存 Emby 计划任务触发器。"""
    try:
        triggers = [item.model_dump() for item in (request.triggers or [])]
        payload = tasks_service.save_triggers(request.server, task_id, triggers)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except GatewayError as error:
        _raise_gateway_http(error)
        return None
    return _to_response(payload, api_schemas.EmbyTaskData)


def api_emby_task_run(plugin, task_id: str, server: str = ""):
    """立即运行 Emby 计划任务。"""
    try:
        tasks_service.run_task(server, task_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except GatewayError as error:
        _raise_gateway_http(error)
        return None
    return _to_response({"status": "success", "message": "任务已启动"}, api_schemas.EmbyActionData)


def api_emby_task_stop(plugin, task_id: str, server: str = ""):
    """停止 Emby 计划任务。"""
    try:
        tasks_service.stop_task(server, task_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except GatewayError as error:
        _raise_gateway_http(error)
        return None
    return _to_response({"status": "success", "message": "停止命令已发送"}, api_schemas.EmbyActionData)
