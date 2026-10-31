"""TG 转发推送目标：把消息转发到目标会话（个人号，受全局冷却约束）。

两种模式（由负载里的 ``forward`` 指令决定，见 P6 转发规则引擎）：
- **原样转发**（默认）：``forward_messages`` 转发原消息，保留来源频道；
- **转换后发送**（``forward.transform``）：对原文应用转换规则后 ``send_message``，
  转发的是"改写过的内容"而不是原消息。

``forward.pin`` 为真时，转发 / 发送完成后把该消息在目标会话内置顶
（``notify=False`` 静默置顶）。置顶失败不影响"转发成功"的结论。

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
    """转发消息到目标会话（可选内容转换与置顶）。"""

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

        forward = task.get("forward") if isinstance(task.get("forward"), dict) else {}

        # 全局冷却：拿不到名额就稍后由 worker 重试，不无限阻塞
        if not self._gate.acquire(timeout=15):
            wait = int(self._gate.ready_at() - _now())
            return PushResult(
                ok=False,
                message=f"TG 转发冷却中（约 {max(wait, 1)} 秒后可执行）",
                retryable=True,
            )
        try:
            result = self._forward(runtime, int(chat_id), int(message_id), int(target_id), forward)
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

    def _forward(self, runtime: Any, chat_id: int, message_id: int, target_id: int,
                 forward: Dict[str, Any]) -> PushResult:
        """在 TG 运行时内执行转发（同步等待，带超时预算）。"""

        async def _do() -> "tuple[str, bool]":
            client = runtime.client
            if client is None:
                raise RuntimeError("TG 客户端未就绪")
            messages = await client.get_messages(chat_id, ids=message_id)
            if not messages:
                raise RuntimeError(f"消息不存在或已被删除（chat={chat_id}, id={message_id}）")
            if forward.get("transform"):
                send_text = str(forward.get("send_text") or "")
                if not send_text.strip():
                    raise RuntimeError("转换后内容为空（检查转换规则是否把全文替换掉了）")
                sent = await client.send_message(target_id, send_text)
                how = "转换后发送"
            else:
                sent = await client.forward_messages(target_id, messages)
                how = "转发原消息"
            pinned = False
            if forward.get("pin"):
                message = _first_sent(sent)
                if message is not None:
                    try:
                        await client.pin_message(target_id, message, notify=False)
                        pinned = True
                    except Exception as err:  # 置顶失败不算转发失败
                        logger.warning(f"转发后置顶失败（转发仍算成功）：{err}")
            return how, pinned

        # 走 credentials._call_tg：断线时自动重连并重试一次（断线自愈闭环）。
        # 否则持续断开时转发只会退回 pending 重试、自身不触发重连，要等别的
        # _call_tg 调用者撞上才恢复——1.13.27 把 keep-alive 改成被动探活后，
        # 这个盲区比之前更突出。
        # 转发本身很快，预算照旧压在同步接口网关超时之内。
        credentials = getattr(self._plugin, "_credentials", None)
        if credentials is not None and hasattr(credentials, "_call_tg"):
            how, pinned = credentials._call_tg(runtime, _do, timeout=30)
        else:
            how, pinned = runtime.call(_do(), timeout=30)
        suffix = "（已置顶）" if pinned else ""
        return PushResult(
            ok=True,
            message=f"已{how}到 {target_id}{suffix}",
            detail={"mode": how, "pinned": pinned},
        )


def _first_sent(value: Any) -> Any:
    """从 ``send_message`` / ``forward_messages`` 的返回值里取第一条消息。

    ``forward_messages`` 在多条消息时返回列表，单条时返回 SentMessage。
    """
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _now() -> float:
    import time

    return time.monotonic()
