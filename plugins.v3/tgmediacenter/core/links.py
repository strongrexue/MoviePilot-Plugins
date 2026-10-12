"""115 推送链路的纯逻辑：链接识别、提取码解析、分批。

这一层**不涉及网络**，因此可以完整单测；网络与协议细节在
``core/pan115_client.py``，编排在 ``modules/pan115.py``。

支持的链接形态：
- 115 分享链接：``https://115.com/s/<code>``（含 115cdn / anxia 等镜像域名）
- 分享提取码：URL 查询参数 ``password=`` / ``pwd=``，或正文里的"提取码：abcd"
- 磁力链：``magnet:?xt=urn:btih:...``
- ed2k：``ed2k://|file|...``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import parse_qs, unquote, urlsplit

# 115 分享链接可能出现的域名（含历史/镜像）
SHARE_HOSTS = ("115.com", "115cdn.com", "anxia.com", "115vod.com", "lecloud.com")

# 正文中的提取码写法：提取码：abcd / 提取码:abcd / 访问码：abcd / password: abcd
_CODE_PATTERNS = (
    r"(?:提取码|访问码|密码|提取码是|code)[\s:：]*([0-9a-zA-Z]{4})",
    r"(?:password|pwd)[\s:：=]*([0-9a-zA-Z]{4})",
)


@dataclass
class PushItem:
    """一条待推送的链接。"""

    kind: str  # share | magnet | ed2k | unknown
    url: str
    code: str = ""      # 分享链接的 share_code
    password: str = ""  # 分享提取码
    raw: str = ""

    @property
    def supported(self) -> bool:
        """当前版本是否支持推送该类型。"""
        return self.kind in ("share", "magnet", "ed2k")

    def describe(self) -> str:
        """用于日志/提示的简短描述（不含提取码）。"""
        if self.kind == "share":
            return f"115分享:{self.code}"
        if self.kind == "magnet":
            return f"磁力:{self.url[:40]}…"
        if self.kind == "ed2k":
            return f"ed2k:{self.url[:40]}…"
        return f"未知:{self.url[:40]}"


@dataclass
class ParsedLinks:
    """一次解析的完整结果。"""

    items: list[PushItem] = field(default_factory=list)
    total: int = 0
    supported: int = 0

    def __bool__(self) -> bool:
        return bool(self.items)


def _find_code_in_text(text: str) -> str:
    """从正文里找提取码。"""
    import re

    for pattern in _CODE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _parse_share(url: str, text: str) -> Optional[PushItem]:
    """解析 115 分享链接；不是分享链接时返回 None。"""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not any(host == item or host.endswith("." + item) for item in SHARE_HOSTS):
        return None
    segments = [seg for seg in (parts.path or "").split("/") if seg]
    if len(segments) < 2 or segments[0] != "s":
        return None
    code = segments[1].strip()
    if not code:
        return None

    query = parse_qs(parts.query or "")
    password = ""
    for key in ("password", "pwd", "passcode"):
        values = query.get(key) or []
        if values and values[0].strip():
            password = values[0].strip()
            break
    if not password:
        password = _find_code_in_text(text)
    return PushItem(kind="share", url=url, code=code, password=password, raw=url)


def parse_push_text(text: str) -> ParsedLinks:
    """从一段文本中解析出所有可推送的链接。

    文本可能来自 Telegram 消息（含标题、广告、多个链接、提取码说明）。
    """
    import re

    source = str(text or "")
    result = ParsedLinks()

    # 1) 分享链接（含常见镜像域名），顺带把 URL 查询里的提取码带上
    share_pattern = re.compile(
        r"https?://(?:[\w-]+\.)*(?:" + "|".join(host.replace(".", r"\.") for host in SHARE_HOSTS) + r")"
        r"/s/[\w-]+(?:\?[^\s\u4e00-\u9fff\"'<>]*)?",
        re.IGNORECASE,
    )
    taken: list[str] = []
    for match in share_pattern.finditer(source):
        url = match.group(0).rstrip(".,;)】]")
        item = _parse_share(url, source)
        if item is None:
            continue
        result.items.append(item)
        taken.append(url)

    # 2) 磁力链
    for match in re.finditer(r"magnet:\?[^\s\u4e00-\u9fff\"'<>]+", source, re.IGNORECASE):
        url = match.group(0).rstrip(".,;)】]")
        result.items.append(PushItem(kind="magnet", url=url, raw=url))

    # 3) ed2k
    for match in re.finditer(r"ed2k://\|[^\s\u4e00-\u9fff\"'<>]+", source, re.IGNORECASE):
        url = match.group(0).rstrip(".,;)】]")
        result.items.append(PushItem(kind="ed2k", url=unquote(url), raw=url))

    result.total = len(result.items)
    result.supported = sum(1 for item in result.items if item.supported)
    return result


def make_items(links: Iterable[str]) -> list[PushItem]:
    """把一串链接转成条目（用于接口直接传入链接数组的场景）。"""
    items: list[PushItem] = []
    for link in links or []:
        parsed = parse_push_text(link)
        if parsed.items:
            items.extend(parsed.items)
    return items


def split_batches(items: list[PushItem], batch_size: int) -> list[list[PushItem]]:
    """按单批上限切分，``batch_size<=0`` 时视为不分批。"""
    size = int(batch_size or 0)
    if size <= 0 or size >= len(items):
        return [list(items)] if items else []
    return [items[index:index + size] for index in range(0, len(items), size)]
