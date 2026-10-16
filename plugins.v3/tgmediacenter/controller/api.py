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
from ..model.hit_log import KIND_MONITOR
from ..services import pt_guard
from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/status", plugin.api_status, ["GET"], "获取插件与 TG 凭证状态"),
        ("/overview", plugin.api_overview, ["GET"], "获取详情页 / 仪表盘聚合状态"),
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
        ("/pan115/cookie_reveal", plugin.api_pan115_cookie_reveal, ["POST"], "按需获取当前登录 Cookie"),
        ("/monitor/rules", plugin.api_monitor_rules, ["GET"], "获取 TG 资源监控规则"),
        ("/monitor/rules", plugin.api_monitor_rules_save, ["PUT", "POST"], "保存 TG 资源监控规则"),
        ("/monitor/hits", plugin.api_monitor_hits, ["GET"], "查询监控命中流水"),
        ("/monitor/hits/clear", plugin.api_monitor_hits_clear, ["POST"], "清理监控命中流水（清空或按筛选删除）"),
        ("/monitor/status", plugin.api_monitor_status, ["GET"], "获取监控运行状态"),
        ("/monitor/test", plugin.api_monitor_test, ["POST"], "用一段文本测试规则处理结果"),
        ("/cache/settings", plugin.api_cache_settings, ["GET"], "获取消息缓存设置"),
        ("/cache/settings", plugin.api_cache_settings_save, ["PUT", "POST"], "保存消息缓存设置"),
        ("/cache/status", plugin.api_cache_status, ["GET"], "获取消息缓存状态与统计"),
        ("/cache/sync", plugin.api_cache_sync, ["POST"], "触发缓存同步（增量 / 时间范围）"),
        ("/cache/cancel", plugin.api_cache_cancel, ["POST"], "停止正在进行的缓存同步"),
        ("/cache/clear", plugin.api_cache_clear, ["POST"], "清空指定频道的缓存"),
        ("/cache/search", plugin.api_cache_search, ["POST"], "检索缓存消息"),
        ("/cache/check_subscriptions", plugin.api_cache_check_subscriptions, ["POST"], "立即检查新增订阅并回搜缓存"),
        ("/cache/backfill/status", plugin.api_cache_backfill_status, ["GET"], "存量补扫运行态"),
        ("/cache/backfill/start", plugin.api_cache_backfill_start, ["POST"], "触发存量补扫（全量/增量）"),
        ("/cache/backfill/cancel", plugin.api_cache_backfill_cancel, ["POST"], "停止存量补扫"),
        ("/forward/rules", plugin.api_forward_rules, ["GET"], "获取 TG 通用转发规则"),
        ("/forward/rules", plugin.api_forward_rules_save, ["PUT", "POST"], "保存 TG 通用转发规则"),
        ("/forward/status", plugin.api_forward_status, ["GET"], "获取转发运行状态"),
        ("/forward/hits", plugin.api_forward_hits, ["GET"], "查询转发命中流水"),
        ("/forward/hits/clear", plugin.api_forward_hits_clear, ["POST"], "清理转发命中流水（清空或按筛选删除）"),
        ("/forward/test", plugin.api_forward_test, ["POST"], "用一段文本测试转发规则"),
        ("/p9/guard", plugin.api_p9_guard, ["GET"], "P9 宿主能力探针"),
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
    except ValueError as err:
        # 业务校验失败（如转发规则缺目标会话）：属于可预期的配置问题，按 400 返回
        raise HTTPException(status_code=400, detail=str(err)) from err
    except (FutureTimeoutError, TimeoutError) as err:
        raise HTTPException(status_code=504, detail="Telegram 操作超时，请重试") from err
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"胖虎媒体中心 API 异常：{err}", exc_info=True)
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


def _safe_status(plugin, attr: str, fallback: Any) -> Any:
    """取某个模块的 ``status()``；模块缺失 / 抛错时返回兜底值。

    详情页是"总览"页面：单个模块异常（例如 TG 还没登录、115 模块未初始化）
    不该让整页空白，所以这里逐块容错，把问题留给对应卡片自己展示。
    """
    module = getattr(plugin, attr, None)
    if module is None:
        return fallback
    try:
        return module.status()
    except Exception as err:  # pragma: no cover - 模块异常按缺省处理
        logger.debug(f"读取 {attr} 状态失败：{err}")
        return fallback


def _recent_hits(plugin, limit: int = 10) -> List[dict]:
    """监控模块的最近流水（只展示监控；转发流水去「转发」设置页看）。

    仪表盘 / 详情页的"最近流水"定位是资源监控结果总览，转发记录混在一起
    反而干扰排查，所以这里只取监控流水。
    """
    module = getattr(plugin, "_monitor", None)
    if module is None:
        return []
    try:
        page = module.hits(page=1, page_size=max(1, int(limit)), kind="monitor")
    except Exception as err:  # pragma: no cover - 单边失败不影响整页
        logger.debug(f"读取监控流水失败：{err}")
        return []
    items = [item for item in (page.get("items") or []) if isinstance(item, dict)]
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return items[: max(1, int(limit))]


def api_overview(plugin):
    """详情页 / 仪表盘聚合状态：一次请求拿齐 TG / 115 / 缓存 / 监控 / 转发与最近流水。"""
    config = getattr(plugin, "config", {}) or {}
    data: Dict[str, Any] = {
        "plugin_version": str(getattr(plugin, "plugin_version", "") or ""),
        "enabled": bool(_state(plugin)),
        "notify": {
            "on_hit": _config_flag(config, "notify_on_hit", True),
            "on_error": _config_flag(config, "notify_on_error", True),
            "on_search": _config_flag(config, "notify_on_search", True),
        },
        "tg": _safe_status(plugin, "_credentials", {}),
        "pan115": _safe_status(plugin, "_pan115", {}),
        "cache": _safe_status(plugin, "_cache", {}),
        "monitor": _safe_status(plugin, "_monitor", {}),
        "forward": _safe_status(plugin, "_forward", {}),
        "recent_hits": _recent_hits(plugin),
    }
    return _envelope(api_schemas.OverviewData.model_validate(data))


def _state(plugin) -> bool:
    """插件启用状态（宿主接口缺失时按未启用）。"""
    try:
        return bool(plugin.get_state())
    except Exception:  # pragma: no cover - 宿主接口缺失
        return False


def _config_flag(config: Any, key: str, default: bool = True) -> bool:
    """读布尔配置（缺失/null 用默认值，字符串形式也认）。"""
    if not isinstance(config, dict):
        return default
    value = config.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("", "0", "false", "no", "off")


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


def api_pan115_cookie_reveal(plugin):
    """按需返回当前登录 Cookie（前端遮罩长条展示/复制用）。"""
    module = _pan115(plugin)
    data = _invoke(module.cookie_reveal)
    return _envelope(api_schemas.Pan115CookieData.model_validate(data), message=data.get("message", ""))


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


def api_monitor_hits(plugin, page: int = 1, page_size: int = 20, decision: str = "",
                     keyword: str = ""):
    """分页查询命中流水（可按决策与关键词过滤；关键词匹配片名 / 规则名 / 说明）。"""
    module = _monitor(plugin)
    data = _invoke(lambda: module.hits(page=page, page_size=page_size,
                                       decision=decision, keyword=keyword))
    return _envelope(api_schemas.MonitorHitsData.model_validate(data))


def api_monitor_hits_clear(plugin, request: api_schemas.MonitorHitsClearRequest):
    """清理监控流水：带 decision / keyword 时只删筛选结果，都不带即清空监控流水。"""
    module = _monitor(plugin)
    data = _invoke(lambda: module.clear_hits(kind=KIND_MONITOR,
                                             decision=request.decision,
                                             keyword=request.keyword))
    return _envelope(api_schemas.MonitorHitsClearData.model_validate(data),
                     message=str(data.get("message") or "已清理流水"))


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


# ---------------------------------------------------------------------- ⑤ 历史消息缓存


def _cache(plugin):
    """返回缓存模块；插件尚未初始化时抛 503。"""
    module = getattr(plugin, "_cache", None)
    if module is None:
        raise HTTPException(status_code=503, detail="插件尚未初始化，请稍后重试")
    return module


def api_cache_settings(plugin):
    """读取缓存设置（含推送目标与时间范围模式选项）。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.settings())
    return _envelope(api_schemas.CacheSettingsData.model_validate(data))


def api_cache_settings_save(plugin, request: api_schemas.CacheSettingsRequest):
    """保存缓存设置（归一后写插件配置）。"""
    module = _cache(plugin)
    payload = request.model_dump(exclude_none=True)
    data = _invoke(lambda: module.save_settings(payload))
    return _envelope(api_schemas.CacheSettingsData.model_validate(data), message="缓存设置已保存")


def api_cache_status(plugin):
    """缓存状态：频道统计、同步进度、订阅回搜状态。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.status())
    return _envelope(api_schemas.CacheStatusData.model_validate(data))


def api_cache_sync(plugin, request: api_schemas.CacheSyncRequest):
    """触发缓存同步（后台线程执行，立即返回）。"""
    module = _cache(plugin)
    data = _invoke(
        lambda: module.sync(
            chat_ids=list(request.chat_ids or []),
            mode=request.mode or "",
            days=request.days,
            start=request.start or "",
            end=request.end or "",
        )
    )
    return _envelope(api_schemas.CacheSyncData.model_validate(data), message=data.get("message", ""))


def api_cache_cancel(plugin):
    """请求停止正在进行的缓存同步（同步线程在下一批拉取前退出）。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.cancel_sync())
    return _envelope(api_schemas.CacheCancelData.model_validate(data), message=data.get("message", ""))


def api_cache_clear(plugin, request: api_schemas.CacheClearRequest):
    """清空指定频道的缓存与位点。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.clear(list(request.chat_ids or [])))
    return _envelope(api_schemas.CacheClearData.model_validate(data), message=data.get("message", ""))


def api_cache_search(plugin, request: api_schemas.CacheSearchRequest):
    """检索缓存消息（归一标题命中 + 全文兜底）。"""
    module = _cache(plugin)
    if not str(request.keyword or "").strip():
        raise HTTPException(status_code=400, detail="请输入要检索的片名")
    items = _invoke(lambda: module.search(request.keyword, limit=request.limit or 50))
    data = api_schemas.CacheSearchData(
        items=[api_schemas.CacheSearchItem.model_validate(item) for item in items],
        total=len(items),
    )
    return _envelope(data, message=f"找到 {len(items)} 条缓存记录")


def api_cache_check_subscriptions(plugin):
    """立即执行一次订阅检查（与定时任务同一逻辑，便于手动验证）。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.check_subscriptions(trigger="手动"))
    return _envelope(api_schemas.CacheCheckSubscriptionsData.model_validate(data), message=data.get("message", ""))


def api_cache_backfill_status(plugin):
    """存量补扫运行态（进度、水位、最近一次结果）。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.backfill_state())
    return _envelope(api_schemas.CacheBackfillState.model_validate(data))


def api_cache_backfill_start(plugin, request: api_schemas.CacheBackfillStartRequest):
    """触发存量补扫（full=True 全量翻历史，False 增量自水位起）。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.start_backfill(full=bool(request.full)))
    return _envelope(
        api_schemas.CacheBackfillStartData.model_validate(data),
        message=data.get("message", ""),
    )


def api_cache_backfill_cancel(plugin):
    """请求停止存量补扫（当前批次结束后退出）。"""
    module = _cache(plugin)
    data = _invoke(lambda: module.cancel_backfill())
    return _envelope(
        api_schemas.CacheBackfillCancelData.model_validate(data),
        message=data.get("message", ""),
    )


# ---------------------------------------------------------------------- ⑥ TG 通用转发


def _forward(plugin):
    """返回转发模块；插件尚未初始化时抛 503。"""
    module = getattr(plugin, "_forward", None)
    if module is None:
        raise HTTPException(status_code=503, detail="插件尚未初始化，请稍后重试")
    return module


def _forward_rules_payload(module, rules=None) -> api_schemas.ForwardRulesData:
    """规则读写响应（含前端下拉选项）。"""
    source = module.rules() if rules is None else rules
    return api_schemas.ForwardRulesData(
        rules=[api_schemas.ForwardRule.model_validate(rule) for rule in source],
        watched_chats=len(module.watched_chat_ids()),
        decisions=[api_schemas.OptionItem.model_validate(item) for item in module.decision_options()],
    )


def api_forward_rules(plugin):
    """读取转发规则（含归一化后补齐的规则 ID）。"""
    module = _forward(plugin)
    data = _invoke(lambda: _forward_rules_payload(module))
    return _envelope(data)


def api_forward_rules_save(plugin, request: api_schemas.ForwardRulesSaveRequest):
    """保存转发规则（校验 + 归一后整份写回配置）。

    校验失败（缺转发目标、启用了过滤却没填内容）返回 400 并把原因写在 detail 里——
    这类配置事故会让转发在运行时全军覆没，必须挡在保存这一步。
    """
    module = _forward(plugin)
    payload = [rule.model_dump() for rule in (request.rules or [])]
    data = _invoke(lambda: _forward_rules_payload(module, module.save_rules(payload)))
    return _envelope(data, message=f"已保存 {len(data.rules)} 条转发规则")


def api_forward_status(plugin):
    """转发运行状态（规则数 / 监听会话 / 全局冷却 / FloodWait 退避）。"""
    module = _forward(plugin)
    data = _invoke(lambda: module.status())
    return _envelope(api_schemas.ForwardStatusData.model_validate(data))


def api_forward_hits(plugin, page: int = 1, page_size: int = 20, decision: str = "",
                     keyword: str = ""):
    """分页查询转发流水（可按决策与关键词过滤）。"""
    module = _forward(plugin)
    data = _invoke(lambda: module.hits(page=page, page_size=page_size,
                                       decision=decision, keyword=keyword))
    return _envelope(api_schemas.MonitorHitsData.model_validate(data))


def api_forward_hits_clear(plugin, request: api_schemas.MonitorHitsClearRequest):
    """清理转发流水：带 decision / keyword 时只删筛选结果，都不带即清空转发流水。"""
    module = _forward(plugin)
    data = _invoke(lambda: module.clear_hits(decision=request.decision,
                                             keyword=request.keyword))
    return _envelope(api_schemas.MonitorHitsClearData.model_validate(data),
                     message=str(data.get("message") or "已清理流水"))


def api_forward_test(plugin, request: api_schemas.ForwardTestRequest):
    """用一段文本测试各转发规则的处理结果（不落库、不入队、不推送）。"""
    module = _forward(plugin)
    if not str(request.text or "").strip():
        raise HTTPException(status_code=400, detail="请先粘贴一条频道消息文本")
    data = _invoke(lambda: module.test_text(request.text))
    return _envelope(api_schemas.ForwardTestData.model_validate(data), message="测试完成（未落库、未推送）")


# ---------------------------------------------------------------------- ⑩ P9 重复获取治理


def api_p9_guard(plugin):
    """P9 数据源探针（只读、无副作用）。

    探针存在的意义：闸门 A 要用 ``list_download_history`` 与 ``DownloaderHelper``
    这两组宿主能力，而它们在本插件里**此前一处都没用过**——先问清楚"到底能不能
    导入、真实落在哪个模块"，再动手写闸门，避免判定链靠猜。
    """
    probe = _invoke(pt_guard.probe)
    return _envelope(api_schemas.P9GuardData.model_validate({"probe": probe}))
