"""TgMediaCenter API 路由声明与统一响应控制层。

约定（对齐 V3 API 响应适配指南）：
- 路径前缀由宿主补全为 ``/api/v1/plugin/<PluginID>``；
- 每个路由显式声明 ``response_model = schemas.Response[业务模型]``；
- 可预期的业务失败（验证码错误等）返回 HTTP 400 + 友好的 detail；
- 未预期异常记录日志后返回 HTTP 500，不把堆栈写进 message；
- 查询正常但无数据时仍返回 ``success=True``。
"""
from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Callable, Dict, List

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException

from ..core.telegram import TelegramOperationError
from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/status", plugin.api_status, ["GET"], "获取插件与 TG 凭证状态"),
        ("/telegram/send_code", plugin.api_telegram_send_code, ["POST"], "发送 Telegram 登录验证码"),
        ("/telegram/sign_in", plugin.api_telegram_sign_in, ["POST"], "完成 Telegram 登录或两步验证"),
        ("/telegram/logout", plugin.api_telegram_logout, ["POST"], "退出 Telegram 登录"),
        ("/telegram/dialogs", plugin.api_telegram_dialogs, ["GET"], "获取缓存的对话列表"),
        ("/telegram/refresh_dialogs", plugin.api_telegram_refresh_dialogs, ["POST"], "刷新并返回对话列表"),
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


def _envelope(data_model: Any, *, message: str = "", success: bool = True):
    """把业务模型包进宿主统一响应 envelope。"""
    return schemas.Response(success=success, message=message, data=data_model)


def _invoke(callback: Callable, **kwargs):
    """执行业务回调，并把可预期失败翻译为合适的 HTTP 状态码。"""
    try:
        return callback(**kwargs)
    except TelegramOperationError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except (FutureTimeoutError, TimeoutError) as err:
        raise HTTPException(status_code=504, detail="Telegram 操作超时，请重试") from err
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"TG媒体中心 API 异常：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="插件内部错误，请查看运行日志") from err


def _credentials(plugin):
    """返回凭证模块；插件尚未初始化时抛 503。"""
    module = getattr(plugin, "_credentials", None)
    if module is None:
        raise HTTPException(status_code=503, detail="插件尚未初始化，请稍后重试")
    return module


# ---------------------------------------------------------------------- 端点实现


def api_status(plugin):
    """返回插件与 TG 凭证状态。"""
    module = _credentials(plugin)
    data = _invoke(lambda: module.status())
    return _envelope(api_schemas.TgStatusData.model_validate(data))


def api_telegram_send_code(plugin, request: api_schemas.TgSendCodeRequest):
    """发送登录验证码。"""
    module = _credentials(plugin)
    result = _invoke(module.send_code, phone=request.phone)
    return _envelope(api_schemas.TgSendCodeData.model_validate(result), message=result.get("message", ""))


def api_telegram_sign_in(plugin, request: api_schemas.TgSignInRequest):
    """完成登录或两步验证。"""
    module = _credentials(plugin)
    result = _invoke(
        module.sign_in,
        phone=request.phone,
        code=request.code,
        password=request.password,
    )
    return _envelope(api_schemas.TgAuthResult.model_validate(result), message=result.get("message", ""))


def api_telegram_logout(plugin):
    """退出登录并清除本地会话。"""
    module = _credentials(plugin)
    result = _invoke(module.logout)
    return _envelope(api_schemas.TgAuthResult.model_validate(result), message=result.get("message", ""))


def _dialogs_payload(plugin, dialogs: List[dict]) -> api_schemas.TgDialogsData:
    """把对话列表包装成响应模型。"""
    try:
        updated_at = str(plugin.get_data("dialogs_updated_at") or "")
    except Exception:  # pragma: no cover - 展示增强，失败不影响主体
        updated_at = ""
    return api_schemas.TgDialogsData(
        dialogs=[api_schemas.TgDialog.model_validate(item) for item in dialogs],
        count=len(dialogs),
        updated_at=updated_at,
    )


def api_telegram_dialogs(plugin):
    """返回缓存的对话列表。"""
    module = _credentials(plugin)
    dialogs = _invoke(lambda: module.cached_dialogs())
    return _envelope(_dialogs_payload(plugin, dialogs or []))


def api_telegram_refresh_dialogs(plugin):
    """从 Telegram 刷新对话列表。"""
    module = _credentials(plugin)
    dialogs = _invoke(lambda: module.refresh_dialogs())
    return _envelope(_dialogs_payload(plugin, dialogs or []), message="对话列表已刷新")
