"""115 网盘推送目标：复用 P2 的 115 模块（分享转存 / 磁力 eD2k 离线）。"""
from __future__ import annotations

from typing import Any, Dict

from app.sdk.logging import logger

from .base import Destination, PushResult


class Pan115Destination(Destination):
    """把任务里的链接批量推送到 115。"""

    name = "pan115"

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin

    # ------------------------------------------------------------------ 可用性

    def _module(self):
        return getattr(self._plugin, "_pan115", None)

    def available(self) -> bool:
        module = self._module()
        if module is None:
            return False
        try:
            return bool(module.enabled())
        except Exception:  # pragma: no cover - 模块异常按不可用
            return False

    def unavailable_reason(self) -> str:
        if self._module() is None:
            return "115 模块未初始化"
        if not self.available():
            return "115 网盘未启用（请在「115 网盘」面板开启并完成扫码登录）"
        return ""

    # ------------------------------------------------------------------ 推送

    def push(self, task: Dict[str, Any]) -> PushResult:
        module = self._module()
        if module is None:
            return PushResult(ok=False, message="115 模块未初始化", retryable=False)
        if not self.available():
            return PushResult(ok=False, message=self.unavailable_reason(), retryable=False)

        links = [str(link) for link in (task.get("links") or []) if str(link).strip()]
        if not links:
            return PushResult(ok=False, message="任务中没有可推送的链接", retryable=False)

        try:
            result = module.push(links, cid=task.get("target_cid") or None)
        except Exception as err:
            logger.warning(f"115 推送目标执行失败：{err}")
            return PushResult(ok=False, message=f"115 推送失败：{err}", retryable=True)

        succeeded = int(result.get("succeeded") or 0)
        failed = int(result.get("failed") or 0)
        remaining = int(result.get("remaining") or 0)
        message = str(result.get("message") or "")
        ok = succeeded > 0 and failed == 0
        # 超时预算用尽（remaining>0）或部分失败：值得重试把剩余的推完
        retryable = remaining > 0 or (failed > 0 and succeeded == 0)
        if not message:
            message = f"115 推送完成：成功 {succeeded}，失败 {failed}" + (f"，剩余 {remaining}" if remaining else "")
        return PushResult(ok=ok, message=message, retryable=retryable, detail=result)
