"""TgMediaCenter 插件 API 的请求与响应模型。

响应统一使用宿主 ``schemas.Response[T]``，因此每个路由都要在
``API_RESPONSE_MODELS`` 中登记自己的业务数据模型，由控制层据此声明
``response_model``，保证 OpenAPI 与运行时校验一致。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TgMe(BaseModel):
    """当前登录的 Telegram 账号信息。"""

    id: int = 0
    username: str = ""
    name: str = ""
    phone: str = ""


class TgPendingLogin(BaseModel):
    """待验证的登录上下文（用于刷新页面后恢复登录向导）。"""

    phone_masked: str = ""
    sent_at: str = ""
    delivery: str = "unknown"
    delivery_text: str = ""
    resend_in: int = 0


class TgStatusData(BaseModel):
    """插件与 TG 凭证运行状态。"""

    plugin_version: str = ""
    enabled: bool = False
    telethon_available: bool = False
    api_configured: bool = False
    session_present: bool = False
    running: bool = False
    connected: bool = False
    authorized: bool = False
    me: Optional[TgMe] = None
    phone_masked: str = ""
    dialog_count: int = 0
    dialogs_updated_at: str = ""
    pending_login: Optional[TgPendingLogin] = None
    user_cooldown_seconds: int = 5
    keep_alive_seconds: int = 60
    aggregation_window_seconds: float = 3.0


class TgSendCodeRequest(BaseModel):
    """请求登录验证码。"""

    phone: str = Field(default="", description="手机号，需包含国家码，如 +8613800000000")


class TgSendCodeData(BaseModel):
    """发码结果：告知投递渠道与可重发倒计时，便于前端给出准确引导。"""

    phone_masked: str = ""
    delivery: str = "unknown"
    delivery_text: str = ""
    resend_in: int = 0
    message: str = ""


class TgSignInRequest(BaseModel):
    """提交验证码或两步验证密码。"""

    phone: str = Field(default="", description="手机号；留空时使用上次发码的手机号")
    code: str = Field(default="", description="短信/应用内验证码；两步验证时可留空")
    password: str = Field(default="", description="两步验证密码；仅在需要时填写")


class TgAuthResult(BaseModel):
    """登录类操作的统一结果。"""

    authorized: bool = False
    need_password: bool = False
    message: str = ""
    me: Optional[TgMe] = None


class TgDialog(BaseModel):
    """归一化后的对话条目。"""

    id: int = 0
    name: str = ""
    type: str = ""
    username: str = ""


class TgDialogsData(BaseModel):
    """对话列表响应。"""

    dialogs: List[TgDialog] = Field(default_factory=list)
    count: int = 0
    updated_at: str = ""


# ---------------------------------------------------------------------- ② 115 网盘


class Pan115Space(BaseModel):
    """115 空间配额。"""

    total: str = ""
    used: str = ""
    remain: str = ""


class Pan115QrApp(BaseModel):
    """扫码登录可选的设备标识。"""

    value: str = ""
    title: str = ""


class Pan115QrPending(BaseModel):
    """进行中的扫码登录（刷新页面后可恢复展示）。"""

    app: str = ""
    image: str = ""
    expires_in: int = 0


class Pan115StatusData(BaseModel):
    """115 模块状态。"""

    enabled: bool = False
    cookie_configured: bool = False
    authorized: bool = False
    account: str = ""
    qr_app: str = ""
    login_device: str = ""
    space: Pan115Space = Field(default_factory=Pan115Space)
    last_check: str = ""
    target_cid: str = ""
    batch_max_size: int = 20
    qr_apps: List[Pan115QrApp] = Field(default_factory=list)
    qr_pending: Optional[Pan115QrPending] = None


class Pan115QrStartRequest(BaseModel):
    """获取登录二维码。"""

    app: str = Field(default="alipaymini", description="扫码绑定的设备标识，如 alipaymini / 115ios")


class Pan115QrData(BaseModel):
    """扫码登录状态。"""

    app: str = ""
    image: str = Field(default="", description="二维码图片 data URL")
    status: str = Field(default="waiting", description="waiting/scanned/success/expired/canceled")
    status_text: str = ""
    message: str = ""
    expires_in: int = 0
    status_data: Optional[Pan115StatusData] = None


class Pan115PushRequest(BaseModel):
    """推送链接（分享 / 磁力 / eD2k）。"""

    text: str = Field(default="", description="原始文本，可含多个链接与提取码说明")
    links: List[str] = Field(default_factory=list, description="链接数组；与 text 合并处理")
    cid: str = Field(default="", description="目标目录 CID；留空用配置值")
    batch_size: int = Field(default=0, description="单批最大链接数；0 表示用配置值")
    dry_run: bool = Field(default=False, description="仅解析不提交")


class Pan115VerifyDirRequest(BaseModel):
    """校验目标目录。"""

    cid: str = Field(default="", description="目标目录 CID；留空用配置值")


class Pan115PushItemResult(BaseModel):
    """单条链接的推送结果。"""

    target: str = ""
    ok: bool = False
    message: str = ""


class Pan115PushResult(BaseModel):
    """批量推送结果。"""

    total: int = 0
    processed: int = 0
    remaining: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    batches: int = 0
    message: str = ""
    results: List[Pan115PushItemResult] = Field(default_factory=list)


class Pan115DirData(BaseModel):
    """目录校验结果。"""

    cid: str = ""
    dirname: str = ""
    count: int = 0
    message: str = ""


# ---------------------------------------------------------------------- ④ TG 资源监控


class OptionItem(BaseModel):
    """下拉选项。"""

    value: str = ""
    title: str = ""


class MonitorRule(BaseModel):
    """监控规则（与 MA resource_subscriber_rules 对齐，v1 只实现 client 模式）。"""

    id: str = Field(default="", description="规则稳定 ID，保存时由后端补缺")
    name: str = Field(default="", description="规则名称")
    source_ids: List[int] = Field(default_factory=list, description="监听的会话 ID（频道/群组，可多选）")
    destination: str = Field(default="smart", description="推送目标：smart/pan115/tg_forward/none")
    target_id: str = Field(default="", description="TG 转发目标会话 ID（destination=tg_forward 时必填）")
    match_only_if_missing: bool = Field(default=True, description="仅当媒体库/订阅缺失时才推送")
    match_custom_keywords: bool = Field(default=False, description="是否启用自定义关键词过滤")
    custom_keywords: List[str] = Field(default_factory=list, description="自定义关键词（任一命中即通过）")
    rule_type: str = Field(default="client", description="client=Telethon 个人号监听；web=免登录监听（二期）")
    web_channel_usernames: List[str] = Field(default_factory=list, description="web 监听模式频道用户名（二期预留）")
    enabled: bool = Field(default=True, description="是否启用该规则")


class MonitorRulesData(BaseModel):
    """监控规则读写响应。"""

    rules: List[MonitorRule] = Field(default_factory=list)
    destinations: List[OptionItem] = Field(default_factory=list)
    decisions: List[OptionItem] = Field(default_factory=list)
    watched_chats: int = 0


class MonitorRulesSaveRequest(BaseModel):
    """保存监控规则请求。"""

    rules: List[MonitorRule] = Field(default_factory=list)


class MonitorHit(BaseModel):
    """命中流水条目。"""

    id: int = 0
    rule_id: str = ""
    rule_name: str = ""
    chat_id: int = 0
    message_id: int = 0
    title: str = ""
    year: str = ""
    season: Optional[int] = None
    episode: Optional[int] = None
    media_type: str = ""
    decision: str = ""
    destination: str = ""
    detail: str = ""
    created_at: str = ""


class MonitorHitsData(BaseModel):
    """命中流水分页响应。"""

    items: List[MonitorHit] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class MonitorPipelineStats(BaseModel):
    """流水线运行态（与 MonitorModule.status()["pipeline"] 对应）。"""

    running: bool = False
    handler_registered: bool = False
    buffered: int = 0
    queued: int = 0
    processed: int = 0
    hit: int = 0
    skipped: int = 0
    failed: int = 0
    # 事件可观测性计数（诊断"监听是否真的在收消息"）
    events_received: int = 0
    events_watched: int = 0
    events_unwatched: int = 0
    messages_enqueued: int = 0
    last_event_at: str = ""
    push_done: int = 0
    push_pending: int = 0
    push_failed: int = 0
    started_at: str = ""
    last_error: str = ""


class MonitorStatusData(BaseModel):
    """监控模块运行状态。

    注意：``running`` 等字段在嵌套的 ``pipeline`` 里——平铺建模会让
    model_validate 静默取默认值（界面永远显示"未运行"）。
    """

    enabled: bool = False
    rules_count: int = 0
    watched_chats: int = 0
    pipeline: MonitorPipelineStats = Field(default_factory=MonitorPipelineStats)
    matcher: Dict[str, Any] = Field(default_factory=dict)
    gate_interval: int = 5
    flood_remaining: int = 0


class MonitorTestRequest(BaseModel):
    """规则测试请求。"""

    text: str = Field(default="", description="粘贴一条频道消息原文")


class MonitorTestTrace(BaseModel):
    """单条规则的测试结果。"""

    rule_id: str = ""
    rule_name: str = ""
    destination: str = ""
    decision: str = ""
    reason: str = ""
    enabled: bool = True


class MonitorTestData(BaseModel):
    """规则测试结果（不落库、不入队、不推送）。"""

    purified: str = ""
    recognized: Optional[Dict[str, Any]] = None
    links: List[str] = Field(default_factory=list)
    rules: List[MonitorTestTrace] = Field(default_factory=list)


API_RESPONSE_MODELS: Dict[str, type] = {
    "/status": TgStatusData,
    "/telegram/send_code": TgSendCodeData,
    "/telegram/sign_in": TgAuthResult,
    "/telegram/logout": TgAuthResult,
    "/telegram/dialogs": TgDialogsData,
    "/telegram/connect": TgStatusData,
    "/telegram/refresh_dialogs": TgDialogsData,
    "/pan115/status": Pan115StatusData,
    "/pan115/check": Pan115StatusData,
    "/pan115/logout": Pan115StatusData,
    "/pan115/verify_dir": Pan115DirData,
    "/pan115/push": Pan115PushResult,
    "/pan115/qr_start": Pan115QrData,
    "/pan115/qr_poll": Pan115QrData,
    "/pan115/qr_cancel": Pan115QrData,
    "/monitor/rules": MonitorRulesData,
    "/monitor/hits": MonitorHitsData,
    "/monitor/status": MonitorStatusData,
    "/monitor/test": MonitorTestData,
}
