"""115 网盘推送目标：复用 P2 的 115 模块（分享转存 / 磁力 eD2k 离线）。"""
from __future__ import annotations

from typing import Any, Dict

from app.sdk.logging import logger

from .base import Destination, PushResult

# 1.13.38：不可恢复的 115 侧错误——重试只会白等（真机事故：分享被取消的任务
# 重试 3 次、每次 4 分钟，最后仍是同一句「分享已取消」）。命中即判为终态失败。
_FATAL_HINTS = (
    "分享已取消",
    "分享不存在",
    "分享已删除",
    "分享已失效",
    "分享文件不存在",
    "提取码错误",
    "分享已过期",
    "文件已和谐",
)


def _fatal(message: str) -> bool:
    """该失败原因是否属于「再试也没用」的永久性错误。"""
    text = str(message or "")
    return any(hint in text for hint in _FATAL_HINTS)


class Pan115Destination(Destination):
    """把任务里的链接批量推送到 115。"""

    name = "pan115"
    # 支持一次调用提交多条链接（115 模块内部再按 batch_max_size 分批）：
    # 让推送 worker 把多条待推送任务合并成一次调用，避免"一条链接一次客户端"
    supports_batch = True

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

        wash = task.get("wash") if isinstance(task.get("wash"), dict) else {}
        episodes = wash.get("episodes") or None
        try:
            result = module.push(links, cid=task.get("target_cid") or None, episodes=episodes)
        except Exception as err:
            logger.warning(f"115 推送目标执行失败：{err}")
            return PushResult(ok=False, message=f"115 推送失败：{err}", retryable=True)

        succeeded = int(result.get("succeeded") or 0)
        failed = int(result.get("failed") or 0)
        remaining = int(result.get("remaining") or 0)
        message = str(result.get("message") or "")
        ok = succeeded > 0 and failed == 0
        # 超时预算用尽（remaining>0）或部分失败：值得重试把剩余的推完。
        # 但整条都是永久性错误（分享已取消 / 提取码错误…）时重试只是白等，
        # 1.13.38 起直接判终态：真机事故里同一句「分享已取消」重试了 3 轮。
        fatal = succeeded == 0 and failed > 0 and _fatal(message)
        retryable = (not fatal) and (remaining > 0 or (failed > 0 and succeeded == 0))
        if not message:
            message = f"115 推送完成：成功 {succeeded}，失败 {failed}" + (f"，剩余 {remaining}" if remaining else "")
        return PushResult(ok=ok, message=message, retryable=retryable, detail=result)
