"""消息交互：私聊发链接直接转存 115 并回执（P8 / 1.7.0）。

宿主在"内置搜索 / 指令都没匹配上"时才把用户消息广播成
``EventType.UserMessage``（payload: ``{text, userid, channel}``）——正好是
"直接丢一条链接过来"的场景。本模块负责：

1. 从消息正文里解析出可推送的链接（115 分享 / 磁力 / eD2k）；
2. 交给 115 模块转存（限量 + 时间预算，不拖住事件回调）；
3. 用通知渠道回一条回执：成功 / 失败 / **已转存过**都要说清。

边界（重要）：
- **解析不到链接就完全不回话**——否则用户在机器人里随便说一句都会被打扰；
- 回执走宿主通知渠道（``post_message``），与插件其余通知一致；宿主不支持
  定向回复，所以回执会回到你配置的通知渠道（微信 / Telegram / …）；
- 配置开关 ``interactive_push`` 可整体关闭。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core import links as link_utils
from ..core.notify import Notifier
from ..core.pan115_client import Pan115Error

# 单条消息最多处理的链接数：事件回调里做网络转存，不能无限拖
_MAX_ITEMS = 5
# 时间预算（秒）：115 每条之间有间隔，这里压在宿主同步网关超时之内
_DEADLINE_SECONDS = 40
# 回执里最多列多少个链接块（与 115 转存通知同款兜底）
_MAX_BLOCKS = 8


class InteractiveModule:
    """把"用户发来的链接"接到 115 转存上，并给出可读回执。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._notifier = Notifier(plugin)

    # ------------------------------------------------------------------ 配置

    def enabled(self) -> bool:
        """是否开启「发链接即转存」（默认开启，可整体关闭）。"""
        config = getattr(self._plugin, "config", None) or {}
        if not isinstance(config, dict):
            return True
        return _as_bool(config.get("interactive_push", True), True)

    # ------------------------------------------------------------------ 入口

    def handle(self, event: Any) -> Optional[str]:
        """处理一条用户消息；返回回执文本，``None`` 表示与本插件无关（不回复）。

        异常不往外抛：宿主事件回调里的异常会打断消息链，这里一律吞掉并回一条
        "没转成功"的回执（用户主动发链接，静默失败比报错更糟）。
        """
        if not self.enabled():
            return None
        text = self.message_text(event)
        if not text:
            return None
        try:
            parsed = link_utils.parse_push_text(text)
        except Exception:  # pragma: no cover - 解析异常按"没链接"处理
            return None
        if not [item for item in parsed.items if item.supported]:
            return None

        module = getattr(self._plugin, "_pan115", None)
        if module is None:
            return self._reply("115 模块未初始化，未能转存")

        try:
            # 传整段正文（不拆成单条链接）：提取码常写在正文里，整段解析才认得到。
            # 不做额外"可用性"预检：未登录 / 未配 CID 等问题由 push 抛 Pan115Error，
            # 错误文案本身就可操作（1.7.0 曾误调目标封装的 available() 导致真机全误报）。
            result = module.push(
                [text],
                cid=None,
                batch_size=None,
                dry_run=False,
                max_items=_MAX_ITEMS,
                deadline_seconds=_DEADLINE_SECONDS,
            )
        except Pan115Error as err:
            # 115 模块抛出的错误已按用户视角写好（未登录 / CID 缺失 / 网络失败），原样回
            return self._reply(f"115 未能转存：{err}")
        except Exception as err:  # pragma: no cover - 115 侧异常按失败回执
            return self._reply(f"115 转存失败：{err}")
        return self._reply(self._render(result))

    # ------------------------------------------------------------------ 解析

    @staticmethod
    def message_text(event: Any) -> str:
        """从宿主事件里取消息正文（不同宿主字段略有差异，按语义兜）。"""
        data = getattr(event, "event_data", None)
        if data is None and isinstance(event, dict):
            data = event
        if not isinstance(data, dict):
            return ""
        for key in ("text", "content", "message", "body"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    # ------------------------------------------------------------------ 回执

    def _render(self, result: Dict[str, Any]) -> str:
        """把 115 的推送结果渲染成回执正文（与 115 转存通知同款版式）。"""
        results = [item for item in (result.get("results") or []) if isinstance(item, dict)]
        succeeded = int(result.get("succeeded") or 0)
        failed = int(result.get("failed") or 0)
        skipped = int(result.get("skipped") or 0)
        remaining = int(result.get("remaining") or 0)

        duplicates = sum(
            1 for item in results
            if item.get("ok") and link_utils.looks_like_duplicate(item.get("message"))
        )
        fresh = max(0, succeeded - duplicates)

        lines: List[str] = []
        # 「新转存」与「已转存过」分开计数：115 把重复也报成成功，混在一起说
        # 用户会以为刚又存了一份（与 115 转存通知的标注口径一致）。
        head = f"新转存 {fresh} 条"
        if duplicates:
            head += f"、已转存过 {duplicates} 条"
        if failed:
            head += f"、失败 {failed} 条"
        if skipped:
            head += f"、忽略 {skipped} 条（不支持的链接）"
        if remaining:
            head += f"、还有 {remaining} 条未处理（可再发一次）"
        lines.append(head + "：")

        shown = results[:_MAX_BLOCKS]
        for item in shown:
            lines.append(str(item.get("target") or item.get("source") or "链接"))
            message = str(item.get("message") or "").strip()
            if not item.get("ok"):
                lines.append(f"失败原因：{message or '未知原因'}")
            elif link_utils.looks_like_duplicate(message):
                lines.append("已转存过，本次未重复保存")
            else:
                lines.append(message or "已提交到 115")
        if len(results) > len(shown):
            lines.append(f"…其余 {len(results) - len(shown)} 条未逐条列出")
        if not shown:
            lines.append(str(result.get("message") or "没有解析到可推送的链接"))
        return "\n".join(lines)

    def _reply(self, text: str) -> str:
        """发一条回执通知（渠道由宿主「通知」设置决定）。"""
        self._notifier.send("TG媒体中心 · 链接转存回执", str(text or ""))
        return str(text or "")


def _as_bool(value: Any, default: bool) -> bool:
    """配置值转布尔（宿主配置可能是字符串）。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("", "0", "false", "no", "off")
