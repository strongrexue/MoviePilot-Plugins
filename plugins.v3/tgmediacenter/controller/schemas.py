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
    """命中流水条目（监控与转发共表，靠 kind 区分）。"""

    id: int = 0
    kind: str = Field(default="monitor", description="流水来源：monitor / forward")
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


class MonitorChatActivity(BaseModel):
    """最近消息来源（关心的会话：监控 ∪ 转发 ∪ 缓存）。"""

    chat_id: int = 0
    count: int = 0
    last_at: str = ""
    watched: bool = False
    forwarded: bool = False
    cached: bool = False


class MonitorWatchedChat(BaseModel):
    """关心会话反查结果（ID 是否能被当前账号解析成具体会话）。"""

    chat_id: int = 0
    title: str = ""
    resolved: bool = False
    error: str = ""
    purposes: List[str] = Field(default_factory=list, description="用途：监控 / 缓存")


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
    cache_written: int = 0
    forward_hit: int = 0
    last_event_at: str = ""
    recent_sources: List[MonitorChatActivity] = Field(default_factory=list)
    watched_detail: List[MonitorWatchedChat] = Field(default_factory=list)
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
    watched_chat_ids: List[int] = Field(default_factory=list)
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


# ---------------------------------------------------------------------- ⑤ 历史消息缓存


class CacheChannelStat(BaseModel):
    """单个缓存频道的统计。"""

    chat_id: int = 0
    name: str = ""
    count: int = 0
    latest_date: str = ""
    latest_message_id: int = 0
    cursor: int = 0


class CacheSyncState(BaseModel):
    """缓存同步运行态。"""

    running: bool = False
    chat_id: int = 0
    mode: str = ""
    processed: int = 0
    inserted: int = 0
    started_at: str = ""
    finished_at: str = ""
    last_error: str = ""


class CacheSubscribeState(BaseModel):
    """订阅回搜运行态。"""

    enabled: bool = True
    checking: bool = False
    event_listener: bool = False
    last_check_at: str = ""
    last_check_new: int = 0
    last_check_pushed: int = 0
    last_error: str = ""


class CacheSettingsData(BaseModel):
    """缓存设置（含前端下拉选项）。"""

    enabled: bool = False
    chat_ids: List[int] = Field(default_factory=list)
    destination: str = "smart"
    sync_mode: str = "relative"
    sync_days: int = 30
    batch_size: int = 200
    subscribe_enabled: bool = True
    cron: str = "0 */6 * * *"
    subscribe_cron: str = "*/5 * * * *"
    destinations: List[OptionItem] = Field(default_factory=list)
    sync_modes: List[OptionItem] = Field(default_factory=list)


class CacheSettingsRequest(BaseModel):
    """保存缓存设置请求（字段缺省表示不改该项）。"""

    enabled: Optional[bool] = None
    chat_ids: Optional[List[int]] = None
    destination: Optional[str] = None
    sync_mode: Optional[str] = None
    sync_days: Optional[int] = None
    batch_size: Optional[int] = None
    subscribe_enabled: Optional[bool] = None
    cron: Optional[str] = Field(default=None, description="增量同步 cron（5 段）")
    subscribe_cron: Optional[str] = Field(default=None, description="订阅检查 cron（5 段）")


class CacheMatcherStatus(BaseModel):
    """缺失判断数据源状态（缓存回搜口径）。"""

    queries_available: bool = False
    mediaserver_available: bool = False
    mediaserver: str = ""
    subscriptions: int = 0


class CacheStatusData(BaseModel):
    """缓存模块状态。"""

    enabled: bool = False
    chat_ids: List[int] = Field(default_factory=list)
    chats: int = 0
    destination: str = "smart"
    total: int = 0
    channels: List[CacheChannelStat] = Field(default_factory=list)
    sync: CacheSyncState = Field(default_factory=CacheSyncState)
    subscribe: CacheSubscribeState = Field(default_factory=CacheSubscribeState)
    matcher: CacheMatcherStatus = Field(default_factory=CacheMatcherStatus)
    settings: CacheSettingsData = Field(default_factory=CacheSettingsData)


class CacheSyncRequest(BaseModel):
    """触发缓存同步。"""

    chat_ids: List[int] = Field(default_factory=list, description="留空表示全部缓存频道")
    mode: str = Field(default="", description="all/relative/absolute；留空用配置值")
    days: Optional[int] = Field(default=None, description="relative 模式的天数")
    start: str = Field(default="", description="absolute 模式起始日期 YYYY-MM-DD")
    end: str = Field(default="", description="absolute 模式结束日期 YYYY-MM-DD")


class CacheSyncData(BaseModel):
    """同步触发结果。"""

    started: bool = False
    message: str = ""


class CacheClearRequest(BaseModel):
    """清空缓存请求。"""

    chat_ids: List[int] = Field(default_factory=list, description="留空表示全部缓存频道")


class CacheCancelData(BaseModel):
    """停止缓存同步请求结果。"""

    stopped: bool = False
    message: str = ""


class CacheClearData(BaseModel):
    """清空结果。"""

    deleted: int = 0
    message: str = ""


class CacheSearchRequest(BaseModel):
    """检索缓存。"""

    keyword: str = Field(default="", description="片名关键词")
    limit: int = Field(default=50, description="返回条数上限")


class CacheSearchItem(BaseModel):
    """缓存检索结果条目。"""

    chat_id: int = 0
    message_id: int = 0
    title: str = ""
    year: str = ""
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_end: Optional[int] = None
    media_type: str = ""
    text: str = ""
    links: List[str] = Field(default_factory=list)
    message_date: str = ""


class CacheSearchData(BaseModel):
    """检索结果。"""

    items: List[CacheSearchItem] = Field(default_factory=list)
    total: int = 0


class CacheCheckSubscriptionsData(BaseModel):
    """订阅回搜检查结果。"""

    checked: bool = False
    baseline: bool = False
    subscriptions: int = 0
    new: int = 0
    pushed: int = 0
    message: str = ""
    details: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------- ⑥ TG 通用转发


class ForwardRule(BaseModel):
    """转发规则（两级匹配 + 内容转换 + 置顶；1.5.1 起与订阅彻底解耦）。

    匹配语义：逻辑一（自定义关键词）与逻辑二（文件扩展名）之间**恒为 AND**；
    转发不查宿主订阅、不要求识别成功。
    """

    id: str = Field(default="", description="规则稳定 ID（f 前缀），保存时由后端补缺")
    name: str = Field(default="", description="规则名称")
    source_ids: List[int] = Field(default_factory=list, description="监听的来源会话 ID（可多选）")
    target_id: int = Field(default=0, description="转发目标会话 ID（必填）")
    match_custom_keywords: bool = Field(default=False, description="逻辑一：自定义关键词过滤")
    custom_keywords: List[str] = Field(default_factory=list, description="自定义关键词")
    pin_links_enabled: bool = Field(default=False, description="转发后置顶该消息")
    pin_link_keywords: List[str] = Field(default_factory=list, description="仅消息命中这些关键词时置顶")
    match_file_extensions: bool = Field(default=False, description="逻辑二：按文件扩展名过滤")
    file_extensions_to_match: List[str] = Field(default_factory=list, description="扩展名列表，如 mp4 / mkv")
    enable_transform: bool = Field(default=False, description="启用内容转换")
    transform_rules: List[str] = Field(default_factory=list, description='转换规则，每行「原文 -> 替换文」，支持正则')
    enabled: bool = Field(default=True, description="是否启用该规则")


class ForwardRulesData(BaseModel):
    """转发规则读写响应。"""

    rules: List[ForwardRule] = Field(default_factory=list)
    watched_chats: int = 0
    decisions: List[OptionItem] = Field(default_factory=list)


class ForwardRulesSaveRequest(BaseModel):
    """保存转发规则请求。"""

    rules: List[ForwardRule] = Field(default_factory=list)


class ForwardStatusData(BaseModel):
    """转发模块运行状态。"""

    enabled: bool = False
    rules_count: int = 0
    watched_chats: int = 0
    watched_chat_ids: List[int] = Field(default_factory=list)
    transform_rules_count: int = 0
    gate_interval: int = 5
    flood_remaining: int = 0


class ForwardTestRequest(BaseModel):
    """转发规则测试请求。"""

    text: str = Field(default="", description="粘贴一条频道消息原文")


class ForwardTestTrace(BaseModel):
    """单条转发规则的测试结果。"""

    rule_id: str = ""
    rule_name: str = ""
    target_id: int = 0
    enabled: bool = True
    matched: bool = False
    decision: str = ""
    reason: str = ""
    send_text: str = Field(default="", description="转换后的发送内容（未启用转换时等于原文）")
    pin: bool = False


class ForwardTestData(BaseModel):
    """转发规则测试结果（不落库、不入队、不推送）。"""

    purified: str = ""
    recognized: Optional[Dict[str, Any]] = None
    links: List[str] = Field(default_factory=list)
    rules: List[ForwardTestTrace] = Field(default_factory=list)


class OverviewNotifyConfig(BaseModel):
    """通知开关（详情页展示用）。"""

    on_hit: bool = True
    on_error: bool = True


class OverviewData(BaseModel):
    """详情页 / 仪表盘的聚合视图（一次请求拿齐各模块状态）。

    每个模块块都是 **可缺省** 的：某个模块初始化失败时该块留默认值，
    详情页仍能渲染其余部分（不让一个模块拖垮整页）。
    """

    plugin_version: str = ""
    enabled: bool = False
    notify: OverviewNotifyConfig = Field(default_factory=OverviewNotifyConfig)
    tg: TgStatusData = Field(default_factory=TgStatusData)
    pan115: Pan115StatusData = Field(default_factory=Pan115StatusData)
    cache: CacheStatusData = Field(default_factory=CacheStatusData)
    monitor: MonitorStatusData = Field(default_factory=MonitorStatusData)
    forward: ForwardStatusData = Field(default_factory=ForwardStatusData)
    recent_hits: List[MonitorHit] = Field(default_factory=list)


API_RESPONSE_MODELS: Dict[str, type] = {
    "/status": TgStatusData,
    "/overview": OverviewData,
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
    "/cache/settings": CacheSettingsData,
    "/cache/status": CacheStatusData,
    "/cache/sync": CacheSyncData,
    "/cache/cancel": CacheCancelData,
    "/cache/clear": CacheClearData,
    "/cache/search": CacheSearchData,
    "/cache/check_subscriptions": CacheCheckSubscriptionsData,
    "/forward/rules": ForwardRulesData,
    "/forward/status": ForwardStatusData,
    "/forward/hits": MonitorHitsData,
    "/forward/test": ForwardTestData,
}
