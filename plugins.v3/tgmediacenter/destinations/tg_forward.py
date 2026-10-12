"""TG 转发推送目标：把命中的原消息转发到目标会话（个人号，受全局冷却约束）。

与 P6「通用转发规则引擎」的区别：这里只做**整条消息转发**（监控规则的
``target_id``），不涉及两级匹配 / 内容转换 / 置顶——那些属于转发规则引擎。

风控纪律（沿用 MA 经验）：
- 全局冷却：相邻两次转发至少间隔 ``tg_user_cooldown_seconds``；
- FloodWait：把冷却门禁推到 Telegram 要求的等待时长之后，任务标记可重试。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.sdk.logging import logger

from ..core.cooldown import CooldownGate, describe_flood_wait
from .base import Destination, PushResult


class TgForwardDestination(Destination):
    """转发原消息到目标会话。"""

    name = "tg_forward"

    def __init__(self, plugin: Any, gate: Optional[CooldownGate] = None) -> None:
        self._plugin = plugin
        self._gate = gate or CooldownGate(5.0)

    # ------------------------------------------------------------------ 运行时

    def _runtime(self):
        credentials = getattr(self._plugin, "_credentials", None)
        if credentials is None:
            return None
        return getattr(credentials, "_runtime", None)

    def available(self) -> bool:
        runtime = self._runtime()
        return bool(runtime and runtime.is_running())

    def unavailable_reason(self) -> str:
        if not self.available():
            return "TG 客户端未连接（请先完成登录并保持连接）"
        return ""

    # ------------------------------------------------------------------ 推送

    def push(self, task: Dict[str, Any]) -> PushResult:
        runtime = self._runtime()
        if runtime is None or not runtime.is_running():
            return PushResult(ok=False, message=self.unavailable_reason() or "TG 运行时未启动")

        chat_id = task.get("chat_id")
        message_id = task.get("message_id")
        target_id = str(task.get("target_id") or "").strip()
        if not chat_id or not message_id:
            return PushResult(ok=False, message="任务缺少消息定位（chat_id/message_id）")
        if not target_id:
            return PushResult(ok=False, message="未配置转发目标（规则的 target_id）")

        # 全局冷却：拿不到名额就稍后由 worker 重试，不无限阻塞
        if not self._gate.acquire(timeout=15):
            wait = int(self._gate.ready_at() - _now())
            return PushResult(
                ok=False,
                message=f"TG 转发冷却中（约 {max(wait, 1)} 秒后可执行）",
                retryable=True,
            )
        try:
            result = self._forward(runtime, int(chat_id), int(message_id), int(target_id))
        except Exception as err:
            flood = describe_flood_wait(err)
            if flood is not None:
                self._gate.backoff(flood)
                return PushResult(
                    ok=False,
                    message=f"Telegram 要求等待 {flood} 秒后重试（已排入退避）",
                    retryable=True,
                )
            logger.warning(f"TG 转发失败：{err}")
            return PushResult(ok=False, message=f"TG 转发失败：{err}", retryable=True)
        finally:
            self._gate.release()
        return result

    def _forward(self, runtime: Any, chat_id: int, message_id: int, target_id: int) -> PushResult:
        """在 TG 运行时内执行转发（同步等待，带超时预算）。"""

        async def _do():
            client = runtime.client
            if client is None:
                raise RuntimeError("TG 客户端未就绪")
            messages = await client.get_messages(chat_id, ids=message_id)
            if not messages:
                raise RuntimeError(f"消息不存在或已被删除（chat={chat_id}, id={message_id}）")
            await client.forward_messages(target_id, messages)
            return True

        # 转发本身很快，预算照旧压在同步接口网关超时之内（后台线程调用无此限制，
        # 但保持一致便于同一入口在接口里直接触发时也不超时）
        runtime.call(_do(), timeout=30)
        return PushResult(ok=True, message=f"已转发到 {target_id}")


def _now() -> float:
    import time

    return time.monotonic()
