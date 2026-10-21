"""统一通知封装。

宿主通知渠道（``plugin.post_message(title=..., text=...)``）是插件唯一的对外
通道——本插件不自建 Bot（设计文档决策 3）。所有通知都从这里出，好处：

- **失败不影响主流程**：通知是锦上添花，任何异常都吞掉并只写 debug 日志；
- **按类别去重**：``key`` 相同的通知在 ``window`` 秒内只发第一条，
  避免风控类故障（如 115 登录态失效）在每批推送里重复刷屏；
- 便于单测：注入替身插件即可断言通知内容与节流行为。

配置口径（沿用 P0 骨架就预留、P7 才启用的两个开关）：

- ``notify_on_hit``：推送成功类通知（如 115 转存完成汇总）；
- ``notify_on_error``：故障类通知（如 115 登录态失效 / 转存失败）；
- ``notify_mtype``：通知类型（宿主 ``MessageType`` 的中文名，1.13.22 起默认「插件」）。

调用方自己读开关再决定是否调用；本模块只管「发出去」与节流。

关于 ``notify_mtype``：宿主 ``post_message(mtype=...)`` 的类型决定三件事——
通知中心里的归属图标、按类型配置的「通知范围」（admin / user / all）、
以及各通知渠道自己的类型白名单。此前插件一直不传 mtype，库里落成空串，
用户没法在宿主里按类型单独控制它；现在默认归「插件」，可选九类中的任意一类。
"""
from __future__ import annotations

import inspect
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

# ------------------------------------------------------------ 通知类型（1.13.22）
# 宿主 ``app.schemas.types.MessageType`` 的九个取值。这里只存中文名（= 枚举的
# value），不 import 宿主枚举：一是插件测试与离线仿真没有宿主包，二是宿主把
# 中文字符串交给 ``Message(mtype="插件")`` 时 pydantic 会自己转成枚举成员。
DEFAULT_NOTIFY_MTYPE = "插件"
NOTIFY_MTYPES = (
    "资源下载",
    "整理入库",
    "订阅",
    "站点",
    "媒体服务器",
    "手动处理",
    "插件",
    "智能体",
    "其它",
)


def notify_mtype(value: Any) -> str:
    """把配置值归一成宿主认的通知类型中文名。

    - 未配置 / 空串 / 空白 → ``DEFAULT_NOTIFY_MTYPE``（「插件」）；
    - 在九类白名单内 → 原样返回；
    - 其它（拼错、未来被宿主删掉的值）→ 回落默认，绝不给宿主塞非法枚举值。
    """
    text = str(value or "").strip()
    if not text:
        return DEFAULT_NOTIFY_MTYPE
    return text if text in NOTIFY_MTYPES else DEFAULT_NOTIFY_MTYPE


def _accepts_mtype(func: Any) -> bool:
    """判断 ``post_message`` 是否接收 ``mtype`` 关键字（宿主 3.x 有，替身可能没有）。"""
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):  # 内建 / 动态签名：按不支持处理，走旧调用
        return False
    for param in params.values():
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            return True
    return "mtype" in params


def deliver(func: Any, title: str, text: str, mtype: str) -> None:
    """把一条通知交给 ``func``（宿主的 ``post_message``）。

    宿主 3.x 的签名有 ``mtype``，旧版 / 测试替身可能只有 ``title``/``text``：
    先探签名再决定要不要带，避免用 try/except TypeError 把真正的报错一起吞掉。
    """
    if _accepts_mtype(func):
        func(title=title, text=text, mtype=mtype)
    else:
        func(title=title, text=text)


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

    def mtype(self) -> str:
        """当前配置的通知类型（归一后必是九类之一，默认「插件」）。"""
        return notify_mtype(self._cfg("notify_mtype", DEFAULT_NOTIFY_MTYPE))

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
            deliver(func, title, str(text or ""), self.mtype())
            return True
        except Exception as err:  # pragma: no cover - 通知失败不能影响主流程
            from app.sdk.logging import logger

            logger.debug(f"发送插件通知失败：{err}")
            return False

    def reset(self) -> None:
        """清空节流记录（插件重载 / 测试用）。"""
        with self._lock:
            self._last_sent.clear()
