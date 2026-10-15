"""EmbyCoverCenter API 路由声明与统一响应控制层。

约定（对齐 MoviePilot V3 API 响应适配指南）：
- 路径前缀由宿主补全为 ``/api/v1/plugin/<PluginID>``；
- 每个路由显式声明 ``response_model = schemas.Response[业务模型]``；
- 查询正常但无数据时仍返回 ``success=True``，不把空结果当成失败；
- 未预期异常记录日志后交给宿主错误层，不把堆栈写进 ``message``。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException
from fastapi.responses import FileResponse

from ..service import assets_meta
from ..service import cover_auto
from ..service import emby_assets
from ..service import emby_gateway
from ..service import emby_tasks as tasks_service
from ..service.emby_gateway import GatewayError
from ..service.render_engine import COMMON_GROUP_NAME, COMMON_SCHEMA_FIELDS, PosterEngine
from . import schemas as api_schemas

# 原生响应：字体文件与模板预览图（二进制流，不走 envelope）。
NATIVE_ROUTE_CONTENT = {
    "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
    "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
}


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
        ("/libraries", plugin.api_libraries, ["GET"], "获取媒体库列表"),
        ("/layouts", plugin.api_layouts, ["GET"], "获取封面布局与参数字段"),
        ("/fonts", plugin.api_fonts, ["GET"], "获取可用字体"),
        ("/fonts/upload", plugin.api_font_upload, ["POST"], "上传字体（base64）"),
        ("/fonts/delete", plugin.api_font_delete, ["POST"], "删除字体"),
        ("/templates", plugin.api_templates, ["GET"], "获取模板预设"),
        ("/templates/save", plugin.api_template_save, ["POST"], "保存模板预设"),
        ("/templates/delete", plugin.api_template_delete, ["POST"], "删除模板预设"),
        ("/templates/upload", plugin.api_template_upload, ["POST"], "上传模板文件（base64）"),
        ("/preview", plugin.api_preview, ["POST"], "生成封面预览"),
        ("/apply", plugin.api_apply, ["POST"], "应用封面到媒体库"),
        ("/auto_cover/run", plugin.api_auto_cover_run, ["POST"], "立即运行自动封面任务"),
    ]
    routes: List[Dict[str, Any]] = [
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
    routes.append(
        {
            "path": "/asset/font/{name}",
            "endpoint": plugin.api_asset_font,
            "methods": ["GET"],
            "auth": "bear",
            # 浏览器 <img> 无法携带 Bearer 头，字体与预览图属于设计素材，放行匿名读取。
            "allow_anonymous": True,
            "summary": "获取字体文件",
            "response_model": None,
            "response_class": FileResponse,
            "responses": {200: {"content": NATIVE_ROUTE_CONTENT}},
        }
    )
    routes.append(
        {
            "path": "/asset/template/{filename}",
            "endpoint": plugin.api_asset_template_preview,
            "methods": ["GET"],
            "auth": "bear",
            "allow_anonymous": True,
            "summary": "获取模板预览图",
            "response_model": None,
            "response_class": FileResponse,
            "responses": {200: {"content": NATIVE_ROUTE_CONTENT}},
        }
    )
    return routes


# 素材列表短缓存：同一媒体库连续预览/应用时不必重复查询 Emby。
_ASSETS_CACHE: Dict[str, Any] = {}
_ASSETS_CACHE_TTL = 120
_ASSETS_CACHE_MAX = 16


def _raise_gateway_http(error: GatewayError) -> None:
    """把网关错误映射为合适的 HTTP 状态码（配置类问题 400，其余 502），并写入日志。"""
    text = str(error)
    logger.error(f"[EmbyCoverCenter] 媒体服务器访问失败：{text}")
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


# --------------------------------------------------------------------------- 封面系统


def _guard(callback):
    """执行可能抛网关 / 校验错误的业务函数，并映射为 HTTP 错误。"""
    try:
        return callback()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GatewayError as error:
        _raise_gateway_http(error)


def _library_name(ref, library_id: str) -> str:
    """按 ID 取媒体库名称（取不到时退回 ID 本身）。"""
    if not library_id:
        return ""
    for library in emby_assets.list_libraries(ref):
        if library.get("id") == library_id:
            return str(library.get("name") or library_id)
    return library_id


def _prepare_config(request, ref) -> Dict[str, Any]:
    """把请求参数整理成引擎可用的渲染配置。"""
    config = dict(request.config or {})
    config["engine"] = request.layout or "classic"
    if not config.get("title"):
        config["title"] = _library_name(ref, request.library_id)
    return config


def _fetch_assets(request, ref, config) -> Dict[str, Any]:
    """读取素材：数量优先取布局 schema 里的 ``poster_count`` / ``backdrop_count``。"""

    def _count(key: str, fallback: int) -> int:
        try:
            return int(config.get(key) or fallback or 0)
        except (TypeError, ValueError):
            return int(fallback or 0)

    poster_count = _count("poster_count", request.poster_count)
    backdrop_count = _count("backdrop_count", request.backdrop_count)
    cache_key = f"{ref.name}|{request.library_id}|{request.mode}|{poster_count}|{backdrop_count}"
    cached = _ASSETS_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < _ASSETS_CACHE_TTL:
        return cached[1]

    assets = emby_assets.fetch_assets(
        ref,
        request.library_id,
        mode=request.mode,
        poster_count=poster_count,
        backdrop_count=backdrop_count,
    )
    if len(_ASSETS_CACHE) >= _ASSETS_CACHE_MAX:
        _ASSETS_CACHE.pop(next(iter(_ASSETS_CACHE)), None)
    _ASSETS_CACHE[cache_key] = (time.time(), assets)
    return assets


def api_libraries(plugin, server: str = ""):
    """返回媒体库列表。"""
    return _to_response(
        _guard(lambda: {"libraries": emby_assets.list_libraries(emby_gateway.resolve(server))}),
        api_schemas.LibraryListData,
    )


def api_layouts(plugin):
    """返回布局清单与其分组参数字段（含引擎通用字段）。"""
    engine: PosterEngine = plugin.cover_engine()
    return _to_response(
        {
            "common_group": COMMON_GROUP_NAME,
            "common_fields": COMMON_SCHEMA_FIELDS,
            "layouts": engine.layout_schemas(),
        },
        api_schemas.LayoutListData,
    )


def api_fonts(plugin):
    """返回数据目录内可用字体。"""
    return _to_response({"fonts": assets_meta.list_fonts(plugin)}, api_schemas.FontListData)


def api_font_upload(plugin, request: api_schemas.FontUploadRequest):
    """上传字体（base64）。"""
    _guard(lambda: assets_meta.save_font_base64(plugin, request.name, request.data))
    return _to_response({"fonts": assets_meta.list_fonts(plugin)}, api_schemas.FontListData)


def api_font_delete(plugin, request: api_schemas.NameRequest):
    """删除字体。"""
    if not _guard(lambda: assets_meta.delete_font(plugin, request.name)):
        raise HTTPException(status_code=404, detail="字体不存在")
    return _to_response({"fonts": assets_meta.list_fonts(plugin)}, api_schemas.FontListData)


def api_templates(plugin):
    """返回模板预设列表。"""
    return _to_response({"templates": assets_meta.list_templates(plugin)}, api_schemas.TemplateListData)


def api_template_save(plugin, request: api_schemas.TemplateSaveRequest):
    """保存模板预设（可选附带预览 dataURL）。"""
    _guard(
        lambda: assets_meta.save_template(
            plugin,
            request.filename,
            layout=request.layout,
            config=request.config,
            name=request.name,
            preview_data_url=request.preview or None,
        )
    )
    return _to_response({"templates": assets_meta.list_templates(plugin)}, api_schemas.TemplateListData)


def api_template_delete(plugin, request: api_schemas.NameRequest):
    """删除模板预设。"""
    if not _guard(lambda: assets_meta.delete_template(plugin, request.filename)):
        raise HTTPException(status_code=404, detail="模板不存在")
    return _to_response({"templates": assets_meta.list_templates(plugin)}, api_schemas.TemplateListData)


def api_template_upload(plugin, request: api_schemas.TemplateUploadRequest):
    """上传模板 JSON（base64）。"""
    _guard(lambda: assets_meta.save_template_base64(plugin, request.filename, request.data))
    return _to_response({"templates": assets_meta.list_templates(plugin)}, api_schemas.TemplateListData)


def api_preview(plugin, request: api_schemas.CoverPreviewRequest):
    """生成封面预览，返回 dataURL。"""

    def _run():
        ref = emby_gateway.resolve(request.server)
        engine: PosterEngine = plugin.cover_engine()
        config = _prepare_config(request, ref)
        assets = _fetch_assets(request, ref, config)
        image = engine.draw(config, assets)
        return {
            "image": f"data:{PosterEngine.base64_mime(image)};base64,{image}",
            "count": int(assets.get("count") or 0),
            "title": str(config.get("title") or ""),
        }

    return _to_response(_guard(_run), api_schemas.CoverPreviewData)


def api_apply(plugin, request: api_schemas.CoverApplyRequest):
    """把封面写回媒体库：带 ``image_data`` 时直接上传成品图，否则现场渲染后上传。"""

    def _run():
        if not request.library_id:
            raise ValueError("缺少媒体库 ID")
        ref = emby_gateway.resolve(request.server)
        config = _prepare_config(request, ref)
        image = str(request.image_data or "").split(",", 1)[-1]
        if not image:
            engine: PosterEngine = plugin.cover_engine()
            image = engine.draw(config, _fetch_assets(request, ref, config))
        emby_gateway.post_raw(
            ref,
            f"Items/{request.library_id}/Images/Primary",
            data=image,
            content_type=PosterEngine.base64_mime(image),
        )
        return {"uploaded": True, "message": "封面已更新"}

    return _to_response(_guard(_run), api_schemas.CoverApplyData)


def api_auto_cover_run(plugin):
    """立即运行自动封面任务：后台线程执行，接口立即返回。"""
    if not plugin.get_state():
        raise HTTPException(status_code=400, detail="插件未启用，请先在配置里开启")
    cover_auto.run_auto_cover_async(plugin)
    return _to_response(
        {"status": "success", "message": "自动封面任务已在后台启动，完成后按通知设置推送结果"},
        api_schemas.OkData,
    )


def api_asset_font(plugin, name: str):
    """原生返回字体文件。"""
    try:
        path = assets_meta.font_path(plugin, name)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type="application/octet-stream")


def api_asset_template_preview(plugin, filename: str):
    """原生返回模板预览图。"""
    try:
        path = assets_meta.template_preview_path(plugin, filename)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if path is None:
        raise HTTPException(status_code=404, detail="预览图不存在")
    return FileResponse(path, media_type="image/jpeg")
