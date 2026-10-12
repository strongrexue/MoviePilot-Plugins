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


API_RESPONSE_MODELS: Dict[str, type] = {
    "/status": TgStatusData,
    "/telegram/send_code": TgSendCodeData,
    "/telegram/sign_in": TgAuthResult,
    "/telegram/logout": TgAuthResult,
    "/telegram/dialogs": TgDialogsData,
    "/telegram/refresh_dialogs": TgDialogsData,
}
