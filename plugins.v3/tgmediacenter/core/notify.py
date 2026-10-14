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

import re
import threading
import time
from typing import Any, Optional

# ---------------------------------------------------------------- 通知图标（1.7.7）
# 借鉴 MP「资源下载」通知与 TG 资源播报的 emoji 行首风格：标题一个主图标、
# 正文每行「图标 + 标签：值」，眼睛在通知列表里先抓图标再读字。
# 选用原则：与 MP / TG 生态同款（用户机器已验证可显示），不引入生僻 emoji。
ICON_DOWNLOAD = "📥"   # 转存完成（与 MP「开始下载」同款）
ICON_ERROR = "⚠️"     # 转存失败 / 错误提示
ICON_SEARCH = "🔍"    # 缓存回搜
ICON_RECEIPT = "🔗"   # 链接转存回执
ICON_TV = "📺"        # 剧集媒体名
ICON_MOVIE = "🎬"     # 电影媒体名
ICON_LINK = "🔗"      # 链接行
ICON_SOURCE = "📢"    # 来源（频道名）
ICON_OK = "✅"        # 转存成功
ICON_RECYCLE = "♻️"   # 已转存过，本次未重复保存
ICON_FAIL = "❌"      # 失败原因
ICON_NOTE = "📋"      # 媒体库未收录备注
ICON_PENDING = "⏳"   # 还有 N 条未处理
ICON_SKIP = "🚫"     # 忽略 / 没有可处理的链接

_SEASON_EPISODE_RE = re.compile(r"S\d{1,2}E\d{1,2}", re.IGNORECASE)


def media_icon(label: str) -> str:
    """媒体名行首图标：带 SxxExx 段判为剧集 📺，否则电影 🎬。

    媒体名一律是「片名 (年份) [SxxExx]」拼装格式（recognizer.label_for /
    pipeline._media_label 同款），有季集段必是剧集；原名兜底场景（识别失败）
    按同一特征猜，猜错也只影响观感。
    """
    return ICON_TV if _SEASON_EPISODE_RE.search(str(label or "")) else ICON_MOVIE


def media_line(label: str) -> str:
    """媒体名行：类型图标 + 媒体名（空名返回空串，由调用方兜底）。"""
    text = str(label or "").strip()
    if not text:
        return ""
    return f"{media_icon(text)} {text}"


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
