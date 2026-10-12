"""全局冷却与频率限制。

TG 个人号对外操作（转发等）有严格的风控频率限制：MA 的经验是给个人号转发加
**全局冷却**（默认 5 秒一次），配合聚合窗口（把同一频道 3 秒内的批量消息合并
处理）显著降低 FloodWait 概率。

本模块提供：
- ``CooldownGate``：同一时刻只允许一个 TG 操作，且相邻操作间隔不低于配置秒数；
- FloodWait 退避：Telegram 返回 ``FloodWaitError`` 时把门禁到等待秒数之后。
"""
from __future__ import annotations

import threading
import time
from typing import Optional


class CooldownGate:
    """全局冷却门（线程安全）。"""

    def __init__(self, min_interval_seconds: float = 5.0) -> None:
        self._interval = max(0.0, float(min_interval_seconds or 0.0))
        self._lock = threading.Lock()
        self._last_done = 0.0
        self._flood_until = 0.0

    # ------------------------------------------------------------------ 参数

    def set_interval(self, seconds: float) -> None:
        """更新冷却间隔（配置变更时调用，立即生效）。"""
        with self._lock:
            self._interval = max(0.0, float(seconds or 0.0))

    def interval(self) -> float:
        with self._lock:
            return self._interval

    # ------------------------------------------------------------------ 门禁

    def ready_at(self) -> float:
        """下一次允许执行的单调时钟时间点。"""
        with self._lock:
            return max(self._last_done + self._interval, self._flood_until)

    def acquire(self, timeout: float = 30.0) -> bool:
        """阻塞直到满足冷却；``timeout`` 秒内仍未就绪返回 False。

        调用方拿到 True 后必须执行操作，并在结束后调用 ``release()``
        （操作失败也要 release，否则冷却永远占位）。
        """
        deadline = time.monotonic() + max(0.0, float(timeout or 0.0))
        while True:
            with self._lock:
                now = time.monotonic()
                ready = max(self._last_done + self._interval, self._flood_until)
                if now >= ready:
                    # 先占位：防止并发方在同一窗口拿到第二个名额
                    self._last_done = now
                    return True
                wait = ready - now
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(wait, remaining, 1.0))

    def release(self) -> None:
        """标记一次操作完成，把冷却基准校准到当前时刻。"""
        with self._lock:
            self._last_done = time.monotonic()

    # ------------------------------------------------------------------ 退避

    def backoff(self, seconds: float) -> None:
        """遇到 FloodWait：把门禁推到 ``seconds`` 秒之后。"""
        with self._lock:
            until = time.monotonic() + max(0.0, float(seconds or 0.0))
            self._flood_until = max(self._flood_until, until)

    def flood_remaining(self) -> float:
        """距 FloodWait 退避结束的剩余秒数（0 表示无退避）。"""
        with self._lock:
            return max(0.0, self._flood_until - time.monotonic())


def describe_flood_wait(err: BaseException) -> Optional[int]:
    """从 FloodWait 类异常里取出等待秒数；不是 FloodWait 返回 None。

    按属性判断而不是导入具名异常类：Telethon 各版本错误类集合不完全一致，
    ``from telethon.errors import FloodWaitError`` 一旦名字缺失会连带让整组
    错误映射失效（本插件在 P1 已踩过这个坑）。
    """
    seconds = getattr(err, "seconds", None)
    if seconds is None:
        return None
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return None
    return max(0, value)
