"""推送目标抽象（Destination）。

监控规则命中后按 ``destination`` 分派：
- ``smart``：115 已启用且已登录 → 115；否则退化为仅记录；
- ``pan115``：115 网盘（分享转存 / 磁力 eD2k 离线，复用 115 模块）；
- ``tg_forward``：把原消息转发到目标会话（受全局冷却约束）；
- ``none``：仅记录（调试用）。

CMS / 阿里云盘 / 宿主订阅链作为扩展位预留（二期），在此新增实现即可。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class PushResult:
    """单次推送的执行结果。"""

    __slots__ = ("ok", "message", "retryable", "detail")

    def __init__(self, *, ok: bool, message: str = "", retryable: bool = False, detail: Optional[dict] = None) -> None:
        self.ok = bool(ok)
        self.message = str(message or "")
        # retryable：是否值得稍后重试（FloodWait、临时网络错误等）
        self.retryable = bool(retryable)
        self.detail = dict(detail or {})

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "message": self.message,
            "retryable": self.retryable,
            "detail": self.detail,
        }


class Destination(Protocol):
    """推送目标协议。"""

    name: str
    # 可选属性：为 True 时推送 worker 会把同一目标的多条待推送任务**合并成一次
    # push 调用**（payload.links 为各任务链接的拼接）。目标需在 ``PushResult.detail``
    # 的 ``results[].source`` 里回报每条输入链接的结果，worker 据此回填各任务终态。
    # 未声明（或不支持多条链接）的目标一律逐任务调用。
    supports_batch: bool

    def available(self) -> bool:
        """当前是否可用（未配置时让调用方尽早失败并给出原因）。"""
        ...

    def unavailable_reason(self) -> str:
        """不可用原因（可展示给用户）。"""
        ...

    def push(self, task: Dict[str, Any]) -> PushResult:
        """执行推送；task 至少含 links/text/target_id/chat_id/message_id。"""
        ...


class DestinationError(Exception):
    """可预期的推送失败（消息可安全展示）。"""
