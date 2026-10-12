"""Telethon 语义封装：登录流程、会话状态、对话读取。

本层只做“把 Telethon 的异常与返回值翻译成插件自己的语义”，不涉及配置读写与
持久化，便于单测与替换实现。

异常按 **名字** 动态取用：Telethon 各版本的错误类集合并不完全一致，
``from telethon.errors import X`` 一旦有名字缺失就会连带让整组映射失效。
"""
from __future__ import annotations

from typing import Any, Optional

from app.sdk.logging import logger

from ..utils import normalize_dialog

try:  # 依赖为可选：未安装 telethon 时整层降级为“不可用”
    from telethon import errors as tg_errors
except Exception:  # pragma: no cover - 环境缺依赖时的降级分支
    tg_errors = None  # type: ignore[assignment]

# Telethon 的 SentCodeType* 类名 → 插件内部的投递渠道标识
_DELIVERY_BY_TYPE = {
    "SentCodeTypeApp": "app",
    "SentCodeTypeSms": "sms",
    "SentCodeTypeCall": "call",
    "SentCodeTypeMissedCall": "flash_call",
    "SentCodeTypeFlashCall": "flash_call",
    "SentCodeTypeEmailCode": "email",
    "SentCodeTypeSetUpEmailRequired": "email",
    "SentCodeTypeFragmentSms": "sms",
}


class TelegramOperationError(Exception):
    """可预期的 TG 操作失败：消息可安全展示给用户。"""


# ---------------------------------------------------------------------- 异常工具


def _error_type(name: str) -> Any:
    """按名字取 Telethon 异常类；依赖缺失或该版本无此异常时返回 None。"""
    return getattr(tg_errors, name, None) if tg_errors is not None else None


def _is_error(err: BaseException, name: str) -> bool:
    """安全判断异常类型。"""
    error_type = _error_type(name)
    return bool(error_type is not None and isinstance(err, error_type))


def _as_int(value: Any, default: int = 0) -> int:
    """宽松转 int，失败时返回默认值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _flood_message(err: BaseException) -> str:
    """把 FloodWait 类异常转成带等待秒数的提示。"""
    seconds = _as_int(getattr(err, "seconds", 0))
    if seconds > 0:
        minutes = seconds // 60
        if minutes >= 1:
            return f"操作过于频繁，Telegram 要求等待约 {minutes} 分钟（{seconds} 秒）后重试"
        return f"操作过于频繁，Telegram 要求等待 {seconds} 秒后重试"
    return "操作过于频繁，请稍后再试"


# ---------------------------------------------------------------------- 发码辅助


def _reset_phone_code_hash(client: Any, phone: str) -> None:
    """清除 Telethon 客户端内缓存的 phone_code_hash。

    Telethon 在客户端实例上维护 ``_phone_code_hash[phone]``：一旦存在，再次调用
    ``send_code_request()`` 会被改写成 ``auth.ResendCodeRequest``。该请求的语义是
    “换一种投递方式重发”，因此当这个号码可用的方式已经用尽时，Telegram 会直接
    回 ``SEND_CODE_UNAVAILABLE``（界面上表现为一长串英文报错）。

    用户点「发送验证码」预期的是正常重发，所以先清掉缓存，让它走一次干净的
    ``auth.SendCodeRequest``。

    该属性属于 Telethon 内部实现，跨版本可能变化，因此整体兜底、失败不影响主流程。
    """
    try:
        cache = getattr(client, "_phone_code_hash", None)
        if isinstance(cache, dict):
            cache.pop(phone, None)
    except Exception as err:  # pragma: no cover - 清理缓存失败不影响发码
        logger.debug(f"清除验证码缓存失败（忽略）：{err}")


def delivery_channel(sent: Any) -> str:
    """从 Telethon 的 SentCode 推断验证码投递渠道。

    :returns: ``app`` / ``sms`` / ``call`` / ``flash_call`` / ``email`` / ``unknown``
    """
    return _DELIVERY_BY_TYPE.get(type(getattr(sent, "type", None)).__name__, "unknown")


def _translate_send_code_error(err: BaseException) -> TelegramOperationError:
    """把发码阶段的 Telethon 异常翻译成可操作的提示。"""
    if _is_error(err, "PhoneNumberInvalidError"):
        return TelegramOperationError("手机号无效，请检查国家码格式（例如 +8613800138000）")
    if _is_error(err, "ApiIdInvalidError"):
        return TelegramOperationError("API ID / API Hash 不正确，请到 my.telegram.org 核对")
    if _is_error(err, "PhoneNumberBannedError"):
        return TelegramOperationError("该手机号已被 Telegram 封禁，无法用于登录")
    if _is_error(err, "SendCodeUnavailableError"):
        return TelegramOperationError(
            "Telegram 拒绝了这次验证码请求：该号码可用的发送方式已用完，或距上次发送太近。"
            "如果之前已经收到过验证码，请直接使用它；否则请等待 1~2 分钟后重试。"
        )
    if _is_error(err, "PhoneNumberFloodError"):
        return TelegramOperationError("该手机号请求验证码过于频繁，请稍后再试（必要时需等待数小时）")
    if _is_error(err, "FloodWaitError"):
        return TelegramOperationError(_flood_message(err))
    return TelegramOperationError(f"发送验证码失败：{err}")


# ---------------------------------------------------------------------- 会话状态


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


# ---------------------------------------------------------------------- 登录流程


async def send_code(client, phone: str) -> dict:
    """请求登录验证码。

    :returns: ``{"phone", "phone_code_hash", "delivery", "timeout"}``
        ``timeout`` 为 Telegram 给出的可重发间隔（秒），供前端做倒计时。
    """
    normalized = str(phone or "").strip()
    if not normalized:
        raise TelegramOperationError("手机号不能为空")

    # 见 _reset_phone_code_hash：避免被 Telethon 静默改成 ResendCodeRequest
    _reset_phone_code_hash(client, normalized)

    try:
        sent = await client.send_code_request(normalized)
    except Exception as err:
        raise _translate_send_code_error(err) from err

    return {
        "phone": normalized,
        "phone_code_hash": str(getattr(sent, "phone_code_hash", "") or ""),
        "delivery": delivery_channel(sent),
        "timeout": _as_int(getattr(sent, "timeout", 0)),
    }


async def sign_in(
    client,
    *,
    phone: str,
    code: str = "",
    phone_code_hash: Optional[str] = None,
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
            if _is_error(err, "PasswordHashInvalidError"):
                raise TelegramOperationError("两步验证密码错误") from err
            if _is_error(err, "FloodWaitError"):
                raise TelegramOperationError(_flood_message(err)) from err
            raise TelegramOperationError(f"两步验证失败：{err}") from err

    if not normalized_phone or not code:
        raise TelegramOperationError("手机号与验证码不能为空")

    # 留空时交给 Telethon 使用客户端内缓存的 hash；两者都没有会得到明确失败
    resolved_hash = str(phone_code_hash or "").strip() or None
    try:
        await client.sign_in(phone=normalized_phone, code=str(code).strip(),
                             phone_code_hash=resolved_hash)
        return {"authorized": True, "need_password": False, "message": "登录成功"}
    except Exception as err:
        if _is_error(err, "SessionPasswordNeededError"):
            return {"authorized": False, "need_password": True, "message": "该账号启用了两步验证，请输入密码"}
        if _is_error(err, "PhoneCodeInvalidError"):
            raise TelegramOperationError("验证码错误") from err
        if _is_error(err, "PhoneCodeExpiredError"):
            raise TelegramOperationError("验证码已过期，请重新发送验证码") from err
        if _is_error(err, "PhoneCodeHashEmptyError") or _is_error(err, "PhoneCodeEmptyError"):
            raise TelegramOperationError("验证码请求已失效，请重新发送验证码") from err
        if _is_error(err, "FloodWaitError"):
            raise TelegramOperationError(_flood_message(err)) from err
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
        if _is_error(err, "FloodWaitError"):
            raise TelegramOperationError(_flood_message(err)) from err
        raise TelegramOperationError(f"读取对话列表失败：{err}") from err
    dialogs.sort(key=lambda item: (item.get("type") or "", item.get("name") or ""))
    return dialogs


async def log_out(client) -> None:
    """注销当前会话（清除服务端登录态）。"""
    try:
        await client.log_out()
    except Exception as err:
        raise TelegramOperationError(f"退出登录失败：{err}") from err
