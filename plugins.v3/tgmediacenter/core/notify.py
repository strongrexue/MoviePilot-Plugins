"""统一通知封装。

宿主通知渠道（``plugin.post_message(title=..., text=...)``）是插件唯一的对外
通道——本插件不自建 Bot（设计文档决策 3）。所有通知都从这里出，好处：

- **失败不影响主流程**：通知是锦上添花，任何异常都吞掉并只写 debug 日志；
- **按类别去重**：``key`` 相同的通知在 ``window`` 秒内只发第一条，
  避免风控类故障（如 115 登录态失效）在每批推送里重复刷屏；
- 便于单测：注入替身插件即可断言通知内容与节流行为。

配置口径（沿用 P0 骨架就预留、P7 才启用的两个开关）：

- ``notify_on_hit``：推送成功类通知（如 115 转存完成汇总）；
- ``notify_on_error``：故障类通知（如 115 登录态失效 / 转存失败）。

调用方自己读开关再决定是否调用；本模块只管「发出去」与节流。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional


class Notifier:
    """插件通知发送器（线程安全，带按类别节流）。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._lock = threading.Lock()
        # 类别 → 上次发送的单调时刻
        self._last_sent: dict[str, float] = {}
        self._sent_count = 0

    # ------------------------------------------------------------------ 配置

    def _cfg(self, key: str, default: Any = None) -> Any:
        config = getattr(self._plugin, "config", None) or {}
        if not isinstance(config, dict):
            return default
        value = config.get(key)
        return default if value is None else value

    @staticmethod
    def _as_bool(value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in ("", "0", "false", "no", "off")

    def enabled(self, key: str, default: bool = True) -> bool:
        """读取通知开关（配置缺失时按 ``default``）。"""
        return self._as_bool(self._cfg(key, default), default)

    def stats(self) -> dict:
        with self._lock:
            return {"sent": self._sent_count, "keys": sorted(self._last_sent)}

    # ------------------------------------------------------------------ 发送

    def send(self, title: str, text: str = "", *, key: str = "", window: float = 0.0) -> bool:
        """发送一条通知；``key`` 非空时按 ``window`` 秒节流。

        :returns: 真的发出去了返回 True；被节流、渠道缺失或发送失败返回 False。
        """
        title = str(title or "").strip()
        if not title:
            return False
        dedupe_key = str(key or "").strip()
        now = time.monotonic()
        with self._lock:
            if dedupe_key:
                window_seconds = max(0.0, float(window or 0.0))
                last = self._last_sent.get(dedupe_key)
                if last is not None and window_seconds > 0 and now - last < window_seconds:
                    return False
                self._last_sent[dedupe_key] = now
            self._sent_count += 1

        func = getattr(self._plugin, "post_message", None)
        if not callable(func):
            return False
        try:
            func(title=title, text=str(text or ""))
            return True
        except Exception as err:  # pragma: no cover - 通知失败不能影响主流程
            from app.sdk.logging import logger

            logger.debug(f"发送插件通知失败：{err}")
            return False

    def reset(self) -> None:
        """清空节流记录（插件重载 / 测试用）。"""
        with self._lock:
            self._last_sent.clear()
