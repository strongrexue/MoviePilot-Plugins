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

from app.sdk.logging import logger

from ..core import links as link_utils
from ..core import transfer_ledger
from ..core.notify import (
    ICON_ERROR,
    ICON_FAIL,
    ICON_OK,
    ICON_PENDING,
    ICON_RECEIPT,
    ICON_RECYCLE,
    ICON_SKIP,
    Notifier,
    media_line,
)
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

    def dedup_enabled(self) -> bool:
        """是否开启「私聊转存查重」（默认开启，可关闭强制重存）。"""
        config = getattr(self._plugin, "config", None) or {}
        if not isinstance(config, dict):
            return True
        return _as_bool(config.get("interactive_dedup", True), True)

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
        supported = [item for item in parsed.items if item.supported]
        if not supported:
            return None

        module = getattr(self._plugin, "_pan115", None)
        if module is None:
            return self._reply(f"{ICON_ERROR} 115 模块未初始化，未能转存")

        # 台账查重（1.7.5）：转存成功过的链接不再调 115——115 的分享转存接口
        # 对"已保存过"照样返回成功并再存一份（真机实测同一链接落盘两份），
        # 不像离线下载会报「任务已存在」，所以本地必须补一道。
        local_hits: Dict[str, dict] = {}
        pending = supported
        if self.dedup_enabled():
            try:
                identities = [
                    transfer_ledger.link_identity(item.kind, item.url, item.code)
                    for item in supported
                ]
                local_hits = transfer_ledger.lookup(self._plugin, identities)
                if local_hits:
                    pending = [
                        item for item in supported
                        if transfer_ledger.link_identity(item.kind, item.url, item.code)
                        not in local_hits
                    ]
            except Exception as err:  # pragma: no cover - 查重失败按全部待转处理
                logger.warning(f"[{self._plugin_id()}] 转存查重失败（忽略）：{err}")
                local_hits, pending = {}, supported

        result: Optional[Dict[str, Any]] = None
        error_text = ""
        if pending:
            # 只把未转存过的链接交给 115；提取码可能写在正文里，逐条补进 URL
            #（不传整段正文：正文里的已转存链接必须剔除，否则 115 会再存一份）
            push_inputs = []
            for item in pending:
                url = item.url
                if (item.kind == "share" and item.password
                        and "password=" not in url and "pwd=" not in url):
                    url = url + ("&" if "?" in url else "?") + f"password={item.password}"
                push_inputs.append(url)
            try:
                # 不做额外"可用性"预检：未登录 / 未配 CID 等问题由 push 抛 Pan115Error，
                # 错误文案本身就可操作（1.7.0 曾误调目标封装的 available() 导致真机全误报）。
                result = module.push(
                    push_inputs,
                    cid=None,
                    batch_size=None,
                    dry_run=False,
                    max_items=_MAX_ITEMS,
                    deadline_seconds=_DEADLINE_SECONDS,
                )
            except Pan115Error as err:
                # 115 模块抛出的错误已按用户视角写好（未登录 / CID 缺失 / 网络失败），原样回
                error_text = f"115 未能转存：{err}"
            except Exception as err:  # pragma: no cover - 115 侧异常按失败回执
                error_text = f"115 转存失败：{err}"

        # 消息里不支持链接的条数（原走 115 解析统计，现在由本地解析补上）
        local_skipped = max(0, int(parsed.total or 0) - int(parsed.supported or 0))
        # 记台账（1.7.5）：本次 115 侧返回成功的链接都记入（含"已存在"——
        # 资源确实在 115 里），下次再发同链接由台账直接判"已转存过"
        if result is not None:
            try:
                entries = []
                for res_item in result.get("results") or []:
                    if not res_item.get("ok"):
                        continue
                    src = str(res_item.get("source") or "")
                    match = next((it for it in pending if it.url == src), None)
                    if match is None:
                        continue
                    entries.append({
                        "kind": match.kind,
                        "url": match.url,
                        "code": match.code,
                        "label": str(res_item.get("label") or res_item.get("target") or ""),
                    })
                if entries:
                    transfer_ledger.record(self._plugin, entries)
            except Exception as err:  # pragma: no cover - 台账失败不影响回执
                logger.debug(f"[{self._plugin_id()}] 已转存台账记录失败（忽略）：{err}")
        if error_text and not local_hits:
            return self._reply(error_text)
        return self._reply(self._render(result, local_hits, error_text, local_skipped))

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

    def _render(self, result: Optional[Dict[str, Any]], local_hits: Dict[str, dict],
                error_text: str = "", local_skipped: int = 0) -> str:
        """把转存结果渲染成回执正文（与 115 转存通知同款版式）。

        1.7.6 用户定稿：去掉「新转存 N 条：」统计头行，回执直接从媒体名块
        开始（单链接时正文只有两行：媒体名 + 状态）；头行原本捎带的
        「忽略 / 未处理」统计改到块列表末尾按需出现，信息不丢。
        每条块尽量带媒体名（识别器格式：片名 (年份) SxxExx）；
        台账命中的「已转存过」块不经过 115，由本地判定直接给出。

        1.7.7 图标化：标题 🔗，媒体名按剧集/电影分 📺/🎬，字段行统一
        「emoji + 文案」格式（✅ 成功 / ♻️ 已转存过 / ❌ 失败 / 🚫 忽略 /
        ⏳ 未处理 / ⚠️ 错误），块与块之间不插空行（紧凑版式）。
        """
        results = [item for item in ((result or {}).get("results") or []) if isinstance(item, dict)]
        skipped = int((result or {}).get("skipped") or 0) + max(0, int(local_skipped or 0))
        remaining = int((result or {}).get("remaining") or 0)

        lines: List[str] = []
        shown = results[:_MAX_BLOCKS]
        for item in shown:
            lines.append(media_line(_clip_label(item.get("label") or item.get("target"))))
            message = str(item.get("message") or "").strip()
            if not item.get("ok"):
                lines.append(f"{ICON_FAIL} 失败原因：{message or '未知原因'}")
            elif link_utils.looks_like_duplicate(message):
                lines.append(f"{ICON_RECYCLE} 已转存过，本次未重复保存")
            else:
                lines.append(f"{ICON_OK} {message or '已提交到 115'}")
        if len(results) > len(shown):
            lines.append(f"…其余 {len(results) - len(shown)} 条未逐条列出")
        # 本地台账命中块：这些链接根本没交给 115，直接按"已转存过"回
        for hit in list(local_hits.values())[:_MAX_BLOCKS]:
            lines.append(
                media_line(_clip_label(str(hit.get("label") or "")))
                or f"{ICON_RECYCLE} 已转存过的链接"
            )
            first_at = str(hit.get("at") or "")[:10]
            lines.append(
                f"{ICON_RECYCLE} 已转存过（{first_at} 首次转存），本次未重复保存" if first_at
                else f"{ICON_RECYCLE} 已转存过，本次未重复保存"
            )
        # 原头行统计的落点：仅在确实发生时才出现，正常单链接回执看不到
        if skipped:
            lines.append(f"{ICON_SKIP} 另有 {skipped} 条不支持的链接已忽略")
        if remaining:
            lines.append(f"{ICON_PENDING} 还有 {remaining} 条未处理（可再发一次）")
        if not results and not local_hits:
            if error_text:
                lines.append(f"{ICON_ERROR} {error_text}")
            else:
                lines.append(
                    f"{ICON_SKIP} {str((result or {}).get('message') or '没有可处理的链接')}"
                )
        return "\n".join(lines)

    def _reply(self, text: str) -> str:
        """发一条回执通知（渠道由宿主「通知」设置决定）。"""
        self._notifier.send(f"{ICON_RECEIPT} TG媒体中心 · 链接转存回执", str(text or ""))
        return str(text or "")


def _clip_label(label: Any, limit: int = 60) -> str:
    """回执块标题截断（超长文件名以 … 收尾）。"""
    text = str(label or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _as_bool(value: Any, default: bool) -> bool:
    """配置值转布尔（宿主配置可能是字符串）。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("", "0", "false", "no", "off")
