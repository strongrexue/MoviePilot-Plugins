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

from ..core.pan115_client import Pan115Error
from ..core.pan115_login import Pan115QrError
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
        ("/telegram/connect", plugin.api_telegram_connect, ["POST"], "连接 / 重连 TG 客户端"),
        ("/telegram/refresh_dialogs", plugin.api_telegram_refresh_dialogs, ["POST"], "刷新并返回对话列表"),
        ("/pan115/status", plugin.api_pan115_status, ["GET"], "获取 115 网盘状态"),
        ("/pan115/check", plugin.api_pan115_check, ["POST"], "测试 115 连接并读取账号与配额"),
        ("/pan115/logout", plugin.api_pan115_logout, ["POST"], "清除 115 Cookie 与状态"),
        ("/pan115/verify_dir", plugin.api_pan115_verify_dir, ["POST"], "校验 115 目标目录 CID"),
        ("/pan115/push", plugin.api_pan115_push, ["POST"], "批量推送链接到 115"),
        ("/pan115/qr_start", plugin.api_pan115_qr_start, ["POST"], "获取 115 扫码登录二维码"),
        ("/pan115/qr_poll", plugin.api_pan115_qr_poll, ["POST"], "查询 115 扫码登录状态"),
        ("/pan115/qr_cancel", plugin.api_pan115_qr_cancel, ["POST"], "取消 115 扫码登录"),
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
    except Pan115Error as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Pan115QrError as err:
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


def _pan115(plugin):
    """返回 115 模块；插件尚未初始化时抛 503。"""
    module = getattr(plugin, "_pan115", None)
    if module is None:
        raise HTTPException(status_code=503, detail="插件尚未初始化，请稍后重试")
    return module


# ---------------------------------------------------------------------- 端点实现


def api_status(plugin):
    """返回插件与 TG 凭证状态。"""
    module = _credentials(plugin)
    data = _invoke(lambda: module.status())
    # 已配置凭证但客户端没连上（例如刚升级插件、连接掉线）：顺手在后台安排一次连接，
    # 不阻塞本次响应；下次刷新状态即可看到真实结果。
    if data.get("api_configured") and not data.get("connected"):
        schedule = getattr(plugin, "ensure_background_connect", None)
        if callable(schedule):
            try:
                schedule()
            except Exception as err:  # pragma: no cover - 自愈属增强能力
                logger.debug(f"安排后台 TG 连接失败：{err}")
    return _envelope(api_schemas.TgStatusData.model_validate(data))


def api_telegram_connect(plugin):
    """连接 / 重连 TG 客户端（同步执行，受同步接口的网关超时约束）。"""
    module = _credentials(plugin)
    data = _invoke(lambda: module.connect_now())
    return _envelope(api_schemas.TgStatusData.model_validate(data), message="TG 客户端已连接")


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


# ---------------------------------------------------------------------- ② 115 网盘


def api_pan115_status(plugin):
    """返回 115 模块状态（不联网）。"""
    module = _pan115(plugin)
    data = _invoke(lambda: module.status())
    return _envelope(api_schemas.Pan115StatusData.model_validate(data))


def api_pan115_check(plugin):
    """测试 115 连接，读取账号与空间配额。"""
    module = _pan115(plugin)
    data = _invoke(lambda: module.check())
    account = data.get("account") or "115"
    return _envelope(api_schemas.Pan115StatusData.model_validate(data), message=f"115 连接正常：{account}")


def api_pan115_logout(plugin):
    """清除 115 Cookie 与状态缓存。"""
    module = _pan115(plugin)
    data = _invoke(lambda: module.logout())
    return _envelope(api_schemas.Pan115StatusData.model_validate(data), message="已清除 115 Cookie")


def api_pan115_verify_dir(plugin, request: api_schemas.Pan115VerifyDirRequest):
    """校验目标目录 CID 是否可用。"""
    module = _pan115(plugin)
    data = _invoke(module.verify_dir, cid=request.cid or None)
    return _envelope(api_schemas.Pan115DirData.model_validate(data), message=data.get("message", ""))


def api_pan115_push(plugin, request: api_schemas.Pan115PushRequest):
    """批量推送链接到 115（分享转存 / 磁力 / eD2k 离线）。"""
    module = _pan115(plugin)
    sources = list(request.links or [])
    if request.text:
        sources.append(request.text)
    result = _invoke(
        lambda: module.push(
            sources,
            cid=request.cid or None,
            batch_size=request.batch_size or None,
            dry_run=bool(request.dry_run),
        ),
    )
    return _envelope(api_schemas.Pan115PushResult.model_validate(result), message=result.get("message", ""))


def api_pan115_qr_start(plugin, request: api_schemas.Pan115QrStartRequest):
    """获取 115 扫码登录二维码（App 通道，不触发 Web 安全密钥）。"""
    module = _pan115(plugin)
    data = _invoke(module.qr_start, app=request.app or None)
    return _envelope(api_schemas.Pan115QrData.model_validate(data), message=data.get("message", ""))


def api_pan115_qr_poll(plugin):
    """查询 115 扫码登录状态；确认后自动写入 Cookie。"""
    module = _pan115(plugin)
    data = _invoke(module.qr_poll)
    return _envelope(api_schemas.Pan115QrData.model_validate(data), message=data.get("message", ""))


def api_pan115_qr_cancel(plugin):
    """取消 115 扫码登录。"""
    module = _pan115(plugin)
    data = _invoke(module.qr_cancel)
    return _envelope(api_schemas.Pan115QrData.model_validate(data), message=data.get("message", ""))
