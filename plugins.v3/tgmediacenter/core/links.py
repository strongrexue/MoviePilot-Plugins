"""115 推送链路的纯逻辑：链接识别、提取码解析、分批。

这一层**不涉及网络**，因此可以完整单测；网络与协议细节在
``core/pan115_client.py``，编排在 ``modules/pan115.py``。

支持的链接形态：
- 115 分享链接：``https://115.com/s/<code>``（含 115cdn / anxia 等镜像域名）
- 分享提取码：URL 查询参数 ``password=`` / ``pwd=``、``#`` 片段（如 ``?#password=abcd``）、
  或正文里的"提取码：abcd"
- 磁力链：``magnet:?xt=urn:btih:...``（文件名可含中文）
- ed2k：``ed2k://|file|<文件名可含中文>|<大小>|<哈希>|/``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import parse_qs, urlsplit

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
    # 这条链接来自哪个「输入链接」（可能是一段含多个链接的正文）。
    # 合并下发时用它把 115 的逐条结果回填到对应的推送任务上。
    source: str = ""

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
    fragment = parse_qs((parts.fragment or "").lstrip("!"))
    password = ""
    # 提取码可能在 ? 查询参数，也可能在 # 片段（如 115.com/s/xxx?#password=abcd）
    for source_map in (query, fragment):
        for key in ("password", "pwd", "passcode"):
            values = source_map.get(key) or []
            if values and values[0].strip():
                password = values[0].strip()
                break
        if password:
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

    # 2) ed2k：优先按结构识别（文件名可含中文，老写法排除中文会把链接截断在第一个汉字）
    #    结构：ed2k://|file|<名>|<大小>|<32位哈希>|/
    ed2k_structural = re.compile(
        r"ed2k://\|file\|[^|\"'<>]*\|\d+\|[0-9a-zA-Z]{32}\|/?",
        re.IGNORECASE,
    )
    for match in ed2k_structural.finditer(source):
        url = match.group(0)
        result.items.append(PushItem(kind="ed2k", url=url, raw=url))
    if not any(item.kind == "ed2k" for item in result.items):
        # 兜底：结构不标准时按前缀识别（允许中文，遇空白/引号/尖括号停止）
        for match in re.finditer(r"ed2k://\|[^\s\"'<>]+", source, re.IGNORECASE):
            url = match.group(0).rstrip(".,;)】]|/")
            result.items.append(PushItem(kind="ed2k", url=url, raw=url))

    # 3) 磁力链（dn= 文件名可含中文，同样不能排除中文）
    for match in re.finditer(r"magnet:\?[^\s\"'<>]+", source, re.IGNORECASE):
        url = match.group(0).rstrip(".,;)】]")
        result.items.append(PushItem(kind="magnet", url=url, raw=url))

    result.total = len(result.items)
    result.supported = sum(1 for item in result.items if item.supported)
    return result


def make_items(links: Iterable[str]) -> list[PushItem]:
    """把一串链接转成条目（用于接口直接传入链接数组的场景）。

    每条条目都会记住自己的 ``source``（原始输入链接），合并下发时用于回填结果。
    """
    items: list[PushItem] = []
    for link in links or []:
        text = str(link)
        parsed = parse_push_text(text)
        for item in parsed.items:
            item.source = text
        items.extend(parsed.items)
    return items


def split_batches(items: list[PushItem], batch_size: int) -> list[list[PushItem]]:
    """按单批上限切分，``batch_size<=0`` 时视为不分批。"""
    size = int(batch_size or 0)
    if size <= 0 or size >= len(items):
        return [list(items)] if items else []
    return [items[index:index + size] for index in range(0, len(items), size)]


# 判定"115 里其实已经有了、本次没重复保存"的关键词（1.6.11 起，1.7.0 消息交互共用）。
# 与 core/pan115_client.py 的口径对齐：分享转存遇「已转存 / 重复」、离线遇
# 「已存在 / 重复」都会返回 ok=True + "…（跳过）"——是成功，但不是新转存。
_DUPLICATE_HINTS = ("已转存", "已存在", "重复", "已保存", "此前已", "已接收")


def looks_like_duplicate(message: str) -> bool:
    """这条结果说明是否表示"115 里已经有了"（转存成功，但未重复保存）。"""
    text = str(message or "")
    return any(hint in text for hint in _DUPLICATE_HINTS)
