"""TgMediaCenter 通用工具：代理解析、敏感值掩码、对象归一。"""
from __future__ import annotations

from typing import Any, Optional
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


def normalize_dialog(dialog: Any) -> dict:
    """把 Telethon 的 dialog 归一为前端使用的结构。"""
    entity = getattr(dialog, "entity", None) or dialog
    chat_id = getattr(dialog, "id", None)
    if chat_id is None:
        chat_id = getattr(entity, "id", 0)

    is_channel = bool(getattr(entity, "broadcast", False))
    is_group = bool(getattr(entity, "megagroup", False)) or bool(getattr(entity, "chat_id", None))
    is_user = bool(getattr(entity, "first_name", None) is not None and not is_group)

    if is_channel:
        chat_type = "频道"
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
