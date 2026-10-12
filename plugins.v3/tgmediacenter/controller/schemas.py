"""TgMediaCenter 插件 API 的请求与响应模型。

响应统一使用宿主 ``schemas.Response[T]``，因此每个路由都要在
``API_RESPONSE_MODELS`` 中登记自己的业务数据模型，由控制层据此声明
``response_model``，保证 OpenAPI 与运行时校验一致。
"""
from __future__ import annotations

from typing import Dict, List, Optional

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


class SubscribeSourceItem(BaseModel):
    """订阅源配置项（用户勾选）。"""

    key: str = ""
    channel: str = "douban"
    enabled: bool = False
    min_rating: float = 0.0
    media_type: str = "all"


class SubscribeStatusData(BaseModel):
    """订阅服务状态。"""

    enabled: bool = False
    rsshub_base: str = ""
    sources: List[SubscribeSourceItem] = Field(default_factory=list)
    mp_count: int = 0
    douban_count: int = 0
    last_sync: str = ""
    last_result: dict = Field(default_factory=dict)


class SubscribeSyncRequest(BaseModel):
    """同步订阅源请求。"""

    channel: str = Field(default="", description="mp / douban / 空=全部")
    dry_run: bool = Field(default=False, description="仅解析不建订阅")


class SubscribeSyncResult(BaseModel):
    """一次同步的结果汇总。"""

    total_sources: int = 0
    hit: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    remaining: int = 0
    message: str = ""
    results: List[Pan115PushItemResult] = Field(default_factory=list)


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
    "/subscribe/sources": List[dict],
    "/subscribe/status": SubscribeStatusData,
    "/subscribe/sync": SubscribeSyncResult,
}
