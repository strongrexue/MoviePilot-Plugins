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
        ("/monitor/rules", plugin.api_monitor_rules, ["GET"], "获取 TG 资源监控规则"),
        ("/monitor/rules", plugin.api_monitor_rules_save, ["PUT", "POST"], "保存 TG 资源监控规则"),
        ("/monitor/hits", plugin.api_monitor_hits, ["GET"], "查询监控命中流水"),
        ("/monitor/status", plugin.api_monitor_status, ["GET"], "获取监控运行状态"),
        ("/monitor/test", plugin.api_monitor_test, ["POST"], "用一段文本测试规则处理结果"),
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


# ---------------------------------------------------------------------- ④ TG 资源监控


def _monitor(plugin):
    """返回监控模块；插件尚未初始化时抛 503。"""
    module = getattr(plugin, "_monitor", None)
    if module is None:
        raise HTTPException(status_code=503, detail="插件尚未初始化，请稍后重试")
    return module


def _rules_payload(module) -> api_schemas.MonitorRulesData:
    """规则读写响应（含前端下拉选项）。"""
    from ..destinations import DESTINATION_OPTIONS

    rules = module.rules()
    return api_schemas.MonitorRulesData(
        rules=[api_schemas.MonitorRule.model_validate(rule) for rule in rules],
        destinations=[api_schemas.OptionItem.model_validate(item) for item in DESTINATION_OPTIONS],
        decisions=[api_schemas.OptionItem.model_validate(item) for item in module.decision_options()],
        watched_chats=len(module.watched_chat_ids()),
    )


def api_monitor_rules(plugin):
    """读取监控规则（含归一化后补齐的规则 ID）。"""
    module = _monitor(plugin)
    data = _invoke(lambda: _rules_payload(module))
    return _envelope(data)


def api_monitor_rules_save(plugin, request: api_schemas.MonitorRulesSaveRequest):
    """保存监控规则（归一 + 校验后整份写回配置）。"""
    module = _monitor(plugin)
    # 先校验再落库：TG 转发缺少目标 ID 是最常见的配置事故
    for rule in request.rules or []:
        if rule.destination == "tg_forward" and not str(rule.target_id or "").strip():
            raise HTTPException(status_code=400, detail=f"规则「{rule.name or '未命名'}」选择 TG 转发时必须填写目标会话 ID")
    data = _invoke(lambda: _rules_payload_after_save(module, request))
    return _envelope(data, message=f"已保存 {len(data.rules)} 条监控规则")


def _rules_payload_after_save(module, request: api_schemas.MonitorRulesSaveRequest) -> api_schemas.MonitorRulesData:
    saved = module.save_rules([rule.model_dump() for rule in (request.rules or [])])
    from ..destinations import DESTINATION_OPTIONS

    return api_schemas.MonitorRulesData(
        rules=[api_schemas.MonitorRule.model_validate(rule) for rule in saved],
        destinations=[api_schemas.OptionItem.model_validate(item) for item in DESTINATION_OPTIONS],
        decisions=[api_schemas.OptionItem.model_validate(item) for item in module.decision_options()],
        watched_chats=len(module.watched_chat_ids()),
    )


def api_monitor_hits(plugin, page: int = 1, page_size: int = 20, decision: str = ""):
    """分页查询命中流水（可按决策过滤）。"""
    module = _monitor(plugin)
    data = _invoke(lambda: module.hits(page=page, page_size=page_size, decision=decision))
    return _envelope(api_schemas.MonitorHitsData.model_validate(data))


def api_monitor_status(plugin):
    """监控运行状态（流水线 / 处理器注册 / 推送队列 / 缺失判断能力）。"""
    module = _monitor(plugin)
    data = _invoke(lambda: module.status())
    # 自愈：已启用且有监听规则但流水线没在跑（如刚保存首批规则、插件刚重载），
    # 顺手安排启动，不阻塞本次响应——与 TG 连接的同一种模式。
    schedule = getattr(module, "ensure_started", None)
    if callable(schedule):
        try:
            schedule()
        except Exception as err:  # pragma: no cover - 自愈属增强能力
            logger.debug(f"安排监控流水线启动失败：{err}")
    return _envelope(api_schemas.MonitorStatusData.model_validate(data))


def api_monitor_test(plugin, request: api_schemas.MonitorTestRequest):
    """用一段文本测试各规则会怎么处理（不落库、不入队、不推送）。"""
    module = _monitor(plugin)
    if not str(request.text or "").strip():
        raise HTTPException(status_code=400, detail="请先粘贴一条频道消息文本")
    data = _invoke(lambda: module.test_text(request.text))
    return _envelope(api_schemas.MonitorTestData.model_validate(data), message="测试完成（未落库、未推送）")
