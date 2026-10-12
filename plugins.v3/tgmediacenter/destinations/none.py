"""仅记录目标：不执行任何推送，用于调试与观察命中情况。"""
from __future__ import annotations

from typing import Any, Dict

from .base import Destination, PushResult


class NoneDestination(Destination):
    """把推送意图记录下来即可。"""

    name = "none"

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def push(self, task: Dict[str, Any]) -> PushResult:
        links = task.get("links") or []
        return PushResult(
            ok=True,
            message=f"仅记录（未推送）：{len(links)} 个链接",
            detail={"links": len(links)},
        )
