"""TgMediaCenter 通用工具：代理解析、敏感值掩码、对象归一、同步执行异步。"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlsplit

# 代理 scheme 到 Telethon proxy_type 的映射
_PROXY_SCHEME_MAP = {
    "http": "http",
    "https": "http",
    "socks5": "socks5",
    "socks5h": "socks5",
    "socks4": "socks4",
}


def _pick_proxy_url(proxies: Any) -> Optional[str]:
    """从宿主代理配置中挑出一个可用地址。"""
    if isinstance(proxies, str):
        return proxies.strip() or None
    if isinstance(proxies, dict):
        for key in ("https", "http", "all", "all://"):
            value = proxies.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            # httpx 风格：{"all://": "http://..."}
            if isinstance(value, (list, tuple)) and value:
                first = value[0]
                if isinstance(first, str) and first.strip():
                    return first.strip()
    return None


def parse_proxy_for_telethon(proxies: Any) -> Optional[dict]:
    """把宿主 `settings.PROXY` 转成 Telethon 的 proxy 参数。

    宿主 `settings.PROXY` 形如 ``{"http": "http://127.0.0.1:7890", "https": "..."}``；
    Telethon 需要 ``{"proxy_type": ..., "addr": ..., "port": ...}``。
    无法解析时返回 None（表示直连），不抛异常。
    """
    url = _pick_proxy_url(proxies)
    if not url:
        return None
    if "://" not in url:
        url = f"http://{url}"
    try:
        parts = urlsplit(url)
    except ValueError:
        return None

    proxy_type = _PROXY_SCHEME_MAP.get((parts.scheme or "").lower())
    if not proxy_type or not parts.hostname:
        return None
    try:
        port = parts.port or (1080 if proxy_type == "socks5" else 8080)
    except ValueError:
        return None

    proxy: dict[str, Any] = {
        "proxy_type": proxy_type,
        "addr": parts.hostname,
        "port": port,
        "rdns": True,
    }
    if parts.username:
        proxy["username"] = unquote(parts.username)
    if parts.password:
        proxy["password"] = unquote(parts.password)
    return proxy


def mask_secret(value: Any, keep: int = 4) -> str:
    """掩码敏感值，仅保留首尾片段用于确认。"""
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= keep * 2:
        return "*" * len(text)
    return f"{text[:keep]}{'*' * 6}{text[-keep:]}"


# 验证码投递渠道 → 面向用户的中文说明
_DELIVERY_TEXT = {
    "app": "已发送到你的 Telegram 应用（请打开手机或电脑上已登录的 Telegram 查看，不是短信）",
    "sms": "已通过短信发送",
    "call": "将通过语音电话播报",
    "flash_call": "将通过闪信呼叫显示",
    "email": "已发送到账号绑定的邮箱",
    "unknown": "已发送（请同时留意 Telegram 应用与短信）",
}


def describe_delivery(channel: Any) -> str:
    """把 Telegram 的验证码投递渠道翻译为可展示的中文说明。"""
    key = str(channel or "").strip().lower() or "unknown"
    return _DELIVERY_TEXT.get(key, _DELIVERY_TEXT["unknown"])


def run_sync(factory: Callable[[], Any], *, timeout: float = 90.0) -> Any:
    """在同步上下文里执行协程。

    :param factory: 返回协程的可调用对象（协程不可重复使用，必须现造）
    :param timeout: 仅用于"已有事件循环"的降级路径

    宿主插件接口是同步方法（由线程池调用），正常情况下当前线程没有运行中的事件循环，
    直接新建循环执行即可；若检测到已有循环（防御性处理），则放到临时线程执行，
    避免 "This event loop is already running"。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(factory())
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # pragma: no cover - 收尾异常不影响结果
                pass
            loop.close()

    box: dict[str, Any] = {}

    def _worker() -> None:
        loop = asyncio.new_event_loop()
        try:
            box["value"] = loop.run_until_complete(factory())
        except BaseException as err:  # noqa: BLE001 - 原样回抛给调用方
            box["error"] = err
        finally:
            loop.close()

    thread = threading.Thread(target=_worker, name="tgmc.run_sync", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"异步任务执行超时（{timeout:.0f} 秒）")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def remaining_seconds(sent_at: Any, window: Any, *, now: Optional[datetime] = None) -> int:
    """计算“距离允许重新发送验证码”还剩多少秒。

    :param sent_at: 上次发码时间（``datetime.now().isoformat()`` 形式）
    :param window: Telegram 返回的可重发间隔（秒）
    :returns: 剩余秒数；无法计算时返回 0（表示可以立即重发）
    """
    try:
        total = int(window or 0)
    except (TypeError, ValueError):
        return 0
    if total <= 0:
        return 0
    try:
        started = datetime.fromisoformat(str(sent_at or "").strip())
    except (TypeError, ValueError):
        return 0
    # 统一按本地朴素时间比较，避免带时区的输入与 datetime.now() 相减报错
    if started.tzinfo is not None:
        started = started.replace(tzinfo=None)
    elapsed = ((now or datetime.now()) - started).total_seconds()
    return max(0, int(round(total - elapsed)))


def normalize_dialog(dialog: Any) -> dict:
    """把 Telethon 的 dialog 归一为前端使用的结构。"""
    entity = getattr(dialog, "entity", None) or dialog
    chat_id = getattr(dialog, "id", None)
    if chat_id is None:
        chat_id = getattr(entity, "id", 0)

    is_channel = bool(getattr(entity, "broadcast", False))
    is_group = bool(getattr(entity, "megagroup", False)) or bool(getattr(entity, "chat_id", None))
    is_bot = bool(getattr(entity, "bot", False))
    is_user = bool(getattr(entity, "first_name", None) is not None and not is_group and not is_bot)

    if is_channel:
        chat_type = "频道"
    elif is_bot:
        chat_type = "机器人"
    elif is_group:
        chat_type = "群组"
    elif is_user:
        chat_type = "用户"
    else:
        chat_type = "其他"

    name = getattr(dialog, "name", None) or getattr(entity, "title", None) or ""
    if not name:
        parts = [getattr(entity, "first_name", "") or "", getattr(entity, "last_name", "") or ""]
        name = " ".join(part for part in parts if part)

    return {
        "id": int(chat_id),
        "name": str(name or "未命名"),
        "type": chat_type,
        "username": str(getattr(entity, "username", "") or ""),
    }
