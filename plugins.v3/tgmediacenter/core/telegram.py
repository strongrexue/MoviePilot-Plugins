"""Telethon 语义封装：登录流程、会话状态、对话读取。

本层只做“把 Telethon 的异常与返回值翻译成插件自己的语义”，不涉及配置读写与
持久化，便于单测与替换实现。
"""
from __future__ import annotations

from typing import Any, Optional

from app.sdk.logging import logger

from ..utils import normalize_dialog

try:
    from telethon.errors import (
        PasswordHashInvalidError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        PhoneNumberInvalidError,
        SessionPasswordNeededError,
    )

    _TELETHON_ERRORS_READY = True
except Exception:  # pragma: no cover - 缺依赖时的降级分支
    PasswordHashInvalidError = None  # type: ignore[assignment]
    PhoneCodeExpiredError = None  # type: ignore[assignment]
    PhoneCodeInvalidError = None  # type: ignore[assignment]
    PhoneNumberInvalidError = None  # type: ignore[assignment]
    SessionPasswordNeededError = None  # type: ignore[assignment]
    _TELETHON_ERRORS_READY = False


class TelegramOperationError(Exception):
    """可预期的 TG 操作失败：消息可安全展示给用户。"""


def _is_error(err: BaseException, error_type: Any) -> bool:
    """忽略缺依赖导致的 None 类型，安全判断异常类型。"""
    return bool(_TELETHON_ERRORS_READY and error_type is not None and isinstance(err, error_type))


async def is_authorized(client: Any) -> bool:
    """判断当前会话是否已完成登录。"""
    try:
        return bool(await client.is_user_authorized())
    except Exception as err:
        logger.debug(f"检查 TG 授权状态失败：{err}")
        return False


async def get_me_info(client: Any) -> Optional[dict]:
    """读取当前登录账号信息；未登录时返回 None。"""
    try:
        me = await client.get_me()
    except Exception as err:
        logger.debug(f"读取 TG 账号信息失败：{err}")
        return None
    if me is None:
        return None
    name = " ".join(part for part in [getattr(me, "first_name", "") or "",
                                      getattr(me, "last_name", "") or ""] if part)
    return {
        "id": int(getattr(me, "id", 0) or 0),
        "username": str(getattr(me, "username", "") or ""),
        "name": name or str(getattr(me, "username", "") or ""),
        "phone": str(getattr(me, "phone", "") or ""),
    }


async def send_code(client, phone: str) -> dict:
    """请求登录验证码，返回 phone_code_hash。"""
    normalized = str(phone or "").strip()
    if not normalized:
        raise TelegramOperationError("手机号不能为空")
    try:
        sent = await client.send_code_request(normalized)
    except Exception as err:
        if _is_error(err, PhoneNumberInvalidError):
            raise TelegramOperationError("手机号无效，请检查国家码格式") from err
        raise TelegramOperationError(f"发送验证码失败：{err}") from err
    return {
        "phone": normalized,
        "phone_code_hash": str(getattr(sent, "phone_code_hash", "") or ""),
    }


async def sign_in(
    client,
    *,
    phone: str,
    code: str = "",
    phone_code_hash: str = "",
    password: Optional[str] = None,
) -> dict:
    """完成登录；需要两步验证时返回 ``need_password=True``。

    :returns: ``{"authorized": bool, "need_password": bool, "message": str}``
    """
    normalized_phone = str(phone or "").strip()

    # 已授权则直接返回，允许前端重复提交
    if await is_authorized(client):
        return {"authorized": True, "need_password": False, "message": "已处于登录状态"}

    if password:
        try:
            await client.sign_in(password=password)
            return {"authorized": True, "need_password": False, "message": "两步验证通过"}
        except Exception as err:
            if _is_error(err, PasswordHashInvalidError):
                raise TelegramOperationError("两步验证密码错误") from err
            raise TelegramOperationError(f"两步验证失败：{err}") from err

    if not normalized_phone or not code:
        raise TelegramOperationError("手机号与验证码不能为空")
    if not phone_code_hash:
        raise TelegramOperationError("验证码请求已失效，请重新获取")

    try:
        await client.sign_in(phone=normalized_phone, code=str(code).strip(),
                             phone_code_hash=phone_code_hash)
        return {"authorized": True, "need_password": False, "message": "登录成功"}
    except Exception as err:
        if _is_error(err, SessionPasswordNeededError):
            return {"authorized": False, "need_password": True, "message": "该账号启用了两步验证，请输入密码"}
        if _is_error(err, PhoneCodeInvalidError):
            raise TelegramOperationError("验证码错误") from err
        if _is_error(err, PhoneCodeExpiredError):
            raise TelegramOperationError("验证码已过期，请重新获取") from err
        raise TelegramOperationError(f"登录失败：{err}") from err


async def fetch_dialogs(client, limit: int = 500) -> list[dict]:
    """读取对话列表（群组 / 频道 / 用户），供规则编辑器选择。"""
    dialogs: list[dict] = []
    try:
        async for dialog in client.iter_dialogs(limit=int(limit)):
            try:
                dialogs.append(normalize_dialog(dialog))
            except Exception as err:  # pragma: no cover - 单条异常不影响整体
                logger.debug(f"跳过异常对话：{err}")
    except Exception as err:
        raise TelegramOperationError(f"读取对话列表失败：{err}") from err
    dialogs.sort(key=lambda item: (item.get("type") or "", item.get("name") or ""))
    return dialogs


async def log_out(client) -> None:
    """注销当前会话（清除服务端登录态）。"""
    try:
        await client.log_out()
    except Exception as err:
        raise TelegramOperationError(f"退出登录失败：{err}") from err
