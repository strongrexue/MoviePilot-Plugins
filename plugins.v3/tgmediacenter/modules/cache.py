"""⑤ 历史消息缓存模块：设置、同步编排、订阅回搜。

与监控的分界
------------
缓存的频道集合与监控规则的 ``source_ids`` **完全独立**：可以在「只缓存不监控」
的频道上归档消息，也可以两者重叠。事件入口把它们并集处理后分别投递。

订阅回搜
--------
```
定时/手动 → 读取订阅快照 → 与上次快照对比出「新增订阅」
  → 缓存库按标题检索（归一标题匹配）
  → 逐条判缺失（is_missing + 订阅门禁）→ 过滤无链接 / 已推送
  → 入推送队列（destination 取 cache_destination）→ 通知结果
```
首次运行只建立基线（不把已有订阅全部当成新增，避免一次推几百条）。
"""
from __future__ import annotations

import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core import forward as forward_engine
from ..core import push_queue
from ..core.history_cache import (
    MODE_ABSOLUTE,
    MODE_ALL,
    MODE_RELATIVE,
    SYNC_MODES,
    HistoryCacheService,
)
from ..destinations import DESTINATION_VALUES
from ..model.hit_log import DECISION_HIT, TgHitLog
from ..core.notify import (
    DEFAULT_NOTIFY_MTYPE,
    ICON_LINK,
    ICON_NOTE,
    ICON_SEARCH,
    ICON_SOURCE,
    deliver,
    media_line,
    notify_mtype,
)
from ..services import matcher as matcher_service
from ..services import quality as quality_service
from ..services import recognizer as recognizer_service
from ..services.matcher import MediaMatcher

# 缓存回搜在命中流水里的"虚拟规则"标识（便于在流水里与监控规则区分）
CACHE_SEARCH_RULE_ID = "cache_search"
CACHE_SEARCH_RULE_NAME = "缓存回搜"
# 洗版基线（1.13.32）：按「订阅标题 + 年份 + 季集区间」记住已推送过的最好画质，
# 后续候选只有逐维比较严格更优才算升级。存插件数据，重启不丢。
_WASH_BASELINE_KEY = "cache_wash_baseline"
# 基线条目上限：超过按最近更新时间截断，防止长期运行无限膨胀
_WASH_BASELINE_LIMIT = 500
# 推送节奏由推送 worker 的「每批条数 / 批间隔」控制（见 core/pipeline.py 的
# push_batch_size / push_batch_interval），队列不会被瞬间灌满；重复入队由命中流水挡住。
# 定时任务默认 cron（5 段：分 时 日 月 周）
DEFAULT_SYNC_CRON = "0 */6 * * *"


class CacheModule:
    """历史消息缓存编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._history = HistoryCacheService(plugin)
        self._matcher = MediaMatcher()
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "last_check_at": "",
            "last_check_new": 0,
            "last_check_pushed": 0,
            "last_error": "",
            "checking": False,
        }

    # ------------------------------------------------------------------ 配置

    @property
    def _config(self) -> dict:
        return getattr(self._plugin, "config", {}) or {}

    def _cfg(self, key: str, default: Any = None) -> Any:
        value = self._config.get(key)
        return default if value is None else value

    def enabled(self) -> bool:
        return bool(self._cfg("cache_enabled"))

    def destination(self) -> str:
        """命中推送目标：1.13.9 起固定走 115（界面不再提供选择）。"""
        value = str(self._cfg("cache_destination", "pan115") or "pan115").strip().lower()
        return value if value in DESTINATION_VALUES else "pan115"

    def chat_ids(self) -> List[int]:
        """归一后的缓存频道列表。"""
        result: List[int] = []
        for value in self._cfg("cache_chat_ids", []) or []:
            try:
                number = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if number and number not in result:
                result.append(number)
        return result

    def is_cached_chat(self, chat_id: int) -> bool:
        """该会话是否需要缓存（TG 事件线程高频调用，必须便宜）。"""
        if not self.enabled():
            return False
        try:
            return int(chat_id) in self.chat_ids()
        except (TypeError, ValueError):
            return False

    def wash_rules(self) -> dict:
        """洗版规则（1.13.32）：七维白名单 + 逐维字典序 + TopN + 比对来源。

        ``cache_wash_rules.enabled`` 是唯一总开关（质量门禁语义并入这里）：
        关闭 = 回搜命中即推送，不做任何洗版比较。
        """
        return quality_service.normalize_rules(self._cfg("cache_wash_rules"))

    def notify_enabled(self) -> bool:
        """回搜结果通知开关（115 面板「通知」卡片里的第三个开关，默认开）。"""
        return bool(self._cfg("notify_on_search", True))

    @staticmethod
    def _normalize_ids(raw: Any) -> List[int]:
        result: List[int] = []
        for value in raw or []:
            try:
                number = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if number and number not in result:
                result.append(number)
        return result

    def sync_mode(self) -> str:
        mode = str(self._cfg("cache_sync_mode", MODE_RELATIVE) or MODE_RELATIVE).strip().lower()
        return mode if mode in SYNC_MODES else MODE_RELATIVE

    def sync_days(self) -> int:
        try:
            return max(1, int(self._cfg("cache_sync_days", 30) or 30))
        except (TypeError, ValueError):
            return 30

    def cron(self) -> str:
        """增量同步 cron（非法值回默认，避免弄坏宿主定时注册）。"""
        return _normalize_cron(self._cfg("cache_cron"), DEFAULT_SYNC_CRON)

    def settings(self) -> dict:
        """缓存设置（供前端面板回显）。"""
        return {
            "enabled": self.enabled(),
            "chat_ids": self.chat_ids(),
            "destination": self.destination(),
            "sync_mode": self.sync_mode(),
            "sync_days": self.sync_days(),
            "batch_size": self.batch_size(),
            "wash_rules": self.wash_rules(),
            "push_batch_size": self.push_batch_size(),
            "push_batch_interval": self.push_batch_interval(),
            "cron": self.cron(),
            "destinations": [
                {"value": str(item.get("value")), "title": str(item.get("title"))}
                for item in _destination_options()
            ],
            "sync_modes": [
                {"value": MODE_ALL, "title": "所有消息"},
                {"value": MODE_RELATIVE, "title": "相对时间（最近 N 天）"},
                {"value": MODE_ABSOLUTE, "title": "绝对时间范围"},
            ],
        }

    def save_settings(self, payload: Any) -> dict:
        """保存缓存设置（写插件配置）。"""
        data = payload if isinstance(payload, dict) else {}
        patch: Dict[str, Any] = {}
        if "enabled" in data:
            patch["cache_enabled"] = bool(data.get("enabled"))
        if "chat_ids" in data:
            patch["cache_chat_ids"] = self._normalize_ids(data.get("chat_ids"))
        if "destination" in data:
            destination = str(data.get("destination") or "smart").strip().lower()
            patch["cache_destination"] = destination if destination in DESTINATION_VALUES else "smart"
        if "sync_mode" in data:
            mode = str(data.get("sync_mode") or MODE_RELATIVE).strip().lower()
            patch["cache_sync_mode"] = mode if mode in SYNC_MODES else MODE_RELATIVE
        if "sync_days" in data:
            try:
                patch["cache_sync_days"] = max(1, int(data.get("sync_days") or 30))
            except (TypeError, ValueError):
                patch["cache_sync_days"] = 30
        if "batch_size" in data:
            try:
                patch["cache_batch_size"] = min(500, max(20, int(data.get("batch_size") or 200)))
            except (TypeError, ValueError):
                patch["cache_batch_size"] = 200
        if "wash_rules" in data:
            patch["cache_wash_rules"] = quality_service.normalize_rules(data.get("wash_rules"))
        if "push_batch_size" in data:
            patch["cache_push_batch_size"] = self._coerce_batch_size(data.get("push_batch_size"))
        if "push_batch_interval" in data:
            patch["cache_push_batch_interval"] = self._coerce_batch_interval(
                data.get("push_batch_interval"))
        if "cron" in data:
            patch["cache_cron"] = _normalize_cron(data.get("cron"), DEFAULT_SYNC_CRON)
        if patch:
            self._plugin.save_config(**patch)
        return self.settings()

    def batch_size(self) -> int:
        try:
            return min(500, max(20, int(self._cfg("cache_batch_size", 200) or 200)))
        except (TypeError, ValueError):
            return 200

    @staticmethod
    def _coerce_batch_size(raw: Any) -> int:
        """每批条数收敛到 1~200；缺省/非法回默认 10（0 属于越界，收敛到下限 1）。"""
        if raw is None or raw == "":
            return 10
        try:
            return min(200, max(1, int(raw)))
        except (TypeError, ValueError):
            return 10

    @staticmethod
    def _coerce_batch_interval(raw: Any) -> int:
        """批间隔秒数收敛到 5~3600；缺省/非法回默认 15。"""
        if raw is None or raw == "":
            return 15
        try:
            return min(3600, max(5, int(raw)))
        except (TypeError, ValueError):
            return 15

    def push_batch_size(self) -> int:
        """推送每批条数（1.13.25 新增，推送 worker 读取，默认 10）。

        注意只把「缺省 / 空值」当默认：填 0 是越界要收敛到下限 1，不能悄悄变成 10。
        """
        return self._coerce_batch_size(self._cfg("cache_push_batch_size", 10))

    def push_batch_interval(self) -> int:
        """推送批间隔秒数（1.13.25 新增，推送 worker 读取，默认 15 秒）。"""
        return self._coerce_batch_interval(self._cfg("cache_push_batch_interval", 15))

    # ------------------------------------------------------------------ 写入

    def history(self) -> HistoryCacheService:
        """缓存服务实例（监控流水线写缓存用）。"""
        return self._history

    def record(self, chat_id: int, message_id: int, text: str, **kwargs: Any) -> bool:
        """写一条缓存（供监控流水线复用已算好的净化/识别结果）。"""
        if not self.enabled():
            return False
        return self._history.record(int(chat_id), int(message_id), text, **kwargs)

    # ------------------------------------------------------------------ 同步

    def _runtime(self):
        credentials = getattr(self._plugin, "_credentials", None)
        return getattr(credentials, "_runtime", None) if credentials is not None else None

    def sync(self, *, chat_ids: Optional[List[int]] = None, mode: str = "",
             days: Optional[int] = None, start: Any = None, end: Any = None) -> dict:
        """触发后台同步（默认对全部缓存频道）。"""
        if not self.enabled():
            return {"started": False, "message": "未启用消息缓存"}
        targets = self._normalize_ids(chat_ids) if chat_ids else self.chat_ids()
        if not targets:
            return {"started": False, "message": "未选择要缓存的频道"}
        return self._history.start_sync(
            targets,
            mode=str(mode or self.sync_mode()),
            days=int(days if days is not None else self.sync_days()),
            start=start,
            end=end,
            runtime=self._runtime(),
            batch=self.batch_size(),
        )

    def cancel_sync(self) -> dict:
        """请求停止同步（后台线程在下一批拉取前退出）。"""
        running = self._history.is_syncing()
        self._history.request_cancel()
        if not running:
            return {"stopped": False, "message": "当前没有正在进行的缓存同步"}
        return {"stopped": True, "message": "已请求停止缓存同步（当前批次结束后退出）"}

    def clear(self, chat_ids: Optional[List[int]]) -> dict:
        """清空缓存（未指定频道时清空全部缓存频道）。"""
        targets = self._normalize_ids(chat_ids) if chat_ids else self.chat_ids()
        if not targets:
            return {"deleted": 0, "message": "未选择要清空的频道"}
        deleted = self._history.clear(targets)
        return {"deleted": deleted, "message": f"已清空 {len(targets)} 个频道的缓存（{deleted} 条）"}

    def search(self, keyword: str, *, limit: int = 50) -> List[dict]:
        return self._history.search(keyword, limit=limit, chat_ids=self.chat_ids() or None)

    # ------------------------------------------------------------------ 订阅回搜

    def _notify(self, title: str, text: str) -> None:
        # 通知开关在 115 面板「通知」卡片（与转存通知开关并列），关闭后只回搜不打扰
        if not self.notify_enabled():
            return
        func = getattr(self._plugin, "post_message", None)
        if not callable(func):
            return
        mtype = notify_mtype(self._cfg("notify_mtype", DEFAULT_NOTIFY_MTYPE))
        try:
            deliver(func, title, text, mtype)
        except Exception as err:  # pragma: no cover - 通知失败不影响主流程
            logger.debug(f"发送缓存回搜通知失败：{err}")

    def _notify_search_result(self, new_count: int, details: List[dict]) -> None:
        """回搜结果通知。

        1.13.25 起口径收窄（用户要求）：**只有真正推出去东西才发**。一条都没推
        （「已推送过」「订阅无缺集」「无可用链接」「未订阅」）就完全不发——那些
        判定照旧写命中流水，运行详情页可查，不再发一条"什么都没做"的通知。

        渲染（1.6.10 起，1.7.5 定稿，1.7.6 去头行）：去「· 」前缀、媒体名带年份、
        附真实链接、来源用频道名；已推送的**按消息分块**——每条被推送的消息一个块，
        块内列链接、块自带「来源：频道名」（缓存本就能配多个频道，多频道时才能看出
        每条链接来自哪）。1.7.6：去掉「新增订阅 N 个…」头行直接从块开始。
        总量兜底：推送块最多列 20 条，其余只计数。
        """
        candidates = sum(int(item.get("candidates") or 0) for item in details)
        pushed_total = sum(int(item.get("pushed") or 0) for item in details)
        # 1.13.25 用户要求：只有真正推了东西才发通知。「已推送过」「订阅无缺集」
        # 「无可用链接」「未订阅」这些没推的订阅不再打扰——它们只记在流水里
        # （运行详情页可查），通知正文也不再出现「无需推送」块。
        if not pushed_total:
            return
        names = self._dialog_names()
        lines: List[str] = []

        # 已推送：按消息分块（每块自带来源 + 真实链接）
        pushed_items: List[dict] = []
        shown_count = 0
        for item in details:
            blocks = list(item.get("pushed_items") or [])
            shown = blocks[: max(0, 20 - shown_count)]
            pushed_items.extend(blocks)
            for blk in shown:
                label = _media_label(blk)
                links = list(blk.get("links") or [])
                lines.append(f"{media_line(label)}（{len(links)} 条链接）")
                for url in links[:3]:
                    lines.append(f"{ICON_LINK} 链接：{url}")
                if len(links) > 3:
                    lines.append(f"{ICON_LINK} 还有 {len(links) - 3} 条链接")
                chat_id = int(blk.get("chat_id") or 0)
                src = names.get(chat_id) or str(chat_id)
                lines.append(f"{ICON_SOURCE} 来源：{src}")
            shown_count += len(shown)
            # 推了也要说清"为什么判定媒体库没有"——否则用户只知道推了，
            # 不知道判定依据对不对（1.4.6 真机：媒体库明明有却被判成不存在）
            if blocks and item.get("media_note"):
                lines.append(f"{ICON_NOTE} 媒体库未收录：{item['media_note']}")
        if len(pushed_items) > shown_count:
            lines.append(f"…其余 {len(pushed_items) - shown_count} 条资源请在运行详情页查看")

        # 未推送的订阅块（「候选 N 条，无需推送」）1.13.25 起不再渲染——用户要求
        # 「已推送过 / 无需推送」的不再进通知。这些判定照旧写入命中流水，
        # 在运行详情页可查；通知只报真正推出去的东西。

        # 1.7.6 用户定稿：去「新增订阅 N 个，命中并推送 N 条资源：」/
        # 「新增订阅 N 个，候选 N 条」头行，通知直接从块开始；总量只在
        # 截断时由「…其余 N 条」兜底表达。极端情况（计数>0 但无可展示块）
        # 给一句兜底正文，避免发空通知。
        body = "\n".join(lines) or "本次回搜没有可展示的结果"
        title = f"{ICON_SEARCH} 胖虎媒体中心 缓存回搜"
        self._notify(title, body)

    # ------------------------------------------------------ 缓存推送的频道级过滤

    def rule_filter_reason(self, chat_id: int, text: str) -> str:
        """缓存类推送的「频道级过滤」：空串=放行，否则返回跳过原因。

        为什么需要（1.13.30）：缓存回搜此前完全不经过监控规则的关键词闸——判定链
        只有「有链接 → 未推送过 → 媒体库缺失」就入队，推送时用虚拟规则 id
        （``cache_search``）落流水。于是
        「关键词=电影、排除词=iso」这类**频道级意图**对缓存翻出来的资源一律失效：
        同一个频道里已订阅的电视剧，会从缓存路径被推到 115，而用户明明只想要电影。

        作用域（重要）：**只看这条缓存消息来自哪个频道**，取该频道启用的监控规则
        逐条套用与实时监控同一套判定（逻辑零排除词 → 逻辑一关键词，走
        ``core.forward`` 的共享 helper），任一规则放行即放行——与实时监控「多规则
        独立判定、任一命中即推」语义一致。因此它表达的是「**这个频道**只给我
        电影」，不是「我不要电视剧」：同一部剧若能从别的频道补档，照旧会推。
        频道没有监控规则（只缓存不监控）时无约束，保持旧行为。
        """
        monitor = getattr(self._plugin, "_monitor", None)
        if monitor is None:
            return ""
        try:
            rules = monitor.rules_for_chat(int(chat_id or 0))
        except Exception as err:  # pragma: no cover - 规则读取异常不拦推送
            logger.debug(f"[{self._plugin_id()}] 缓存过滤读取监控规则失败（放行）：{err}")
            return ""
        if not rules:
            return ""
        haystack = recognizer_service.purify_text(text) or str(text or "")
        last_reason = ""
        for rule in rules:
            excluded = forward_engine.excluded_keyword(rule, text=haystack)
            if excluded:
                last_reason = f"命中排除关键词「{excluded}」"
                continue
            keywords = [str(kw).strip() for kw in (rule.get("custom_keywords") or []) if str(kw).strip()]
            if rule.get("match_custom_keywords") and keywords:
                if not any(kw in haystack for kw in keywords):
                    last_reason = "未命中监控规则关键词"
                    continue
            return ""
        return last_reason or "未通过监控规则过滤"

    def _search_subscription(self, sub: dict) -> dict:
        """对单个订阅在缓存里回搜并推送。

        1.13.34 起这是洗版规则唯一的判定路径：频道来了新消息 → 入库 → 按订阅
        回搜缓存 → 洗版规则逐维比较（``cache_wash_rules`` 开启时）→ 更优才入队。
        """
        title = str(sub.get("name") or "").strip()
        if not title:
            return {"name": "", "candidates": 0, "pushed": 0}
        candidates = self._history.search_by_title(
            title, year=str(sub.get("year") or ""), limit=200, chat_ids=self.chat_ids() or None
        )
        logger.info(
            f"[{self._plugin_id()}] 缓存回搜：「{title}」命中候选 {len(candidates)} 条"
        )
        pushed = 0
        pushed_items: List[dict] = []
        skipped = 0
        reasons: Dict[str, int] = {}
        media_note = ""
        # 第一遍：筛出「可推候选」——有链接、没推过、媒体库判定通过。
        # 洗版回搜的媒体库判定本来就是伪造的（不判库），这里保持原样。
        eligible: List[dict] = []
        for item in candidates:
            links = [str(link) for link in (item.get("links") or []) if str(link).strip()]
            if not links:
                skipped += 1
                _count_reason(reasons, "无可用链接")
                continue
            chat_id = int(item.get("chat_id") or 0)
            message_id = int(item.get("message_id") or 0)
            # 频道级过滤（1.13.30）：缓存翻出来的资源同样要遵守来源频道监控规则的
            # 排除词 / 关键词——否则「关键词=电影」对回搜 / 洗版这条路径完全失效。
            filter_reason = self.rule_filter_reason(chat_id, str(item.get("text") or ""))
            if filter_reason:
                skipped += 1
                _count_reason(reasons, filter_reason)
                continue
            already = self._hit_exists(chat_id, message_id)
            if already:
                skipped += 1
                _count_reason(reasons, "已推送过")
                continue
            verdict = self._matcher.is_missing(
                title=str(item.get("title") or title),
                year=str(item.get("year") or sub.get("year") or ""),
                media_type=str(item.get("media_type") or ""),
                season=item.get("season"),
                episode=item.get("episode"),
                episode_end=item.get("episode_end"),
                require_subscription=True,
            )
            if verdict.get("missing") is True and verdict.get("reason") == "媒体库中不存在":
                media_note = media_note or str(verdict.get("note") or "")
            if verdict.get("missing") is not True:
                skipped += 1
                label = _skip_label(verdict)
                _count_reason(reasons, label)
                logger.debug(
                    f"[{self._plugin_id()}] 缓存回搜跳过：{item.get('title') or title}"
                    f"（chat={chat_id}, msg={message_id}）{label}"
                    f"｜{verdict.get('reason') or ''}"
                )
                continue
            eligible.append({
                "item": item,
                "links": links,
                "chat_id": chat_id,
                "message_id": message_id,
                "verdict": verdict,
            })

        # 第二遍（1.13.34）：洗版规则开着才做「准入过滤 → TopN → 逐维比较」
        baseline_updates: Dict[str, dict] = {}
        rules = self.wash_rules()
        if rules.get("enabled"):
            eligible, gate_skipped = self._apply_wash_rules(
                eligible, sub, title, reasons
            )
            skipped += gate_skipped

        # 第三遍：入队
        for record in eligible:
            item = record["item"]
            links = record["links"]
            chat_id = int(record["chat_id"])
            message_id = int(record["message_id"])
            verdict = record["verdict"]
            task_id = push_queue.enqueue_push(
                self._db(),
                self._plugin_id(),
                rule_id=CACHE_SEARCH_RULE_ID,
                chat_id=chat_id,
                message_id=message_id,
                destination=self.destination(),
                target_id="",
                links=links,
                text=str(item.get("text") or ""),
                title=str(item.get("title") or title),
            )
            if task_id:
                self._record_hit(item, title, verdict, task_id)
                pushed += 1
                # 收集每条被推送消息的展示详情：通知里按消息分块、各自标来源
                pushed_items.append({
                    "title": str(item.get("title") or title),
                    "year": str(item.get("year") or sub.get("year") or ""),
                    "season": item.get("season"),
                    "episode": item.get("episode"),
                    "episode_end": item.get("episode_end"),
                    "links": links,
                    "chat_id": chat_id,
                })
                # 推送成功才把画质记进基线：入队失败的下一轮还要能再比一次
                baseline_key = record.get("baseline_key")
                if baseline_key and record.get("profile"):
                    baseline_updates[baseline_key] = record["profile"]
            else:
                skipped += 1
                _count_reason(reasons, "入队失败")
        if baseline_updates:
            self._save_wash_baseline(baseline_updates)
        reason_text = _reason_text(reasons)
        channels = sorted({int(item.get("chat_id") or 0) for item in candidates if item.get("chat_id")})
        # 候选识别年份里最多的一种：订阅没写年份时通知块名兜底用（1.7.5）
        year_counts: Dict[str, int] = {}
        for item in candidates:
            year = str(item.get("year") or "").strip()
            if year:
                year_counts[year] = int(year_counts.get(year) or 0) + 1
        candidate_year = max(year_counts.items(), key=lambda kv: (kv[1], kv[0]))[0] if year_counts else ""
        logger.info(
            f"[{self._plugin_id()}] 缓存回搜结果：「{title}」候选 {len(candidates)} 条，"
            f"推送 {pushed} 条，跳过 {skipped} 条"
            + (f"（{reason_text}）" if reason_text else "")
        )
        return {
            "name": title,
            "year": str(sub.get("year") or ""),
            "candidate_year": candidate_year,
            "candidates": len(candidates),
            "pushed": pushed,
            "pushed_items": pushed_items,
            "skipped": skipped,
            "reasons": reasons,
            "reason_text": reason_text,
            "media_note": media_note,
            "channels": channels,
        }

    def _apply_wash_rules(self, records: List[dict], sub: dict, title: str,
                          reasons: Dict[str, int]) -> "tuple[List[dict], int]":
        """洗版的三道收口（1.13.32，规则见 ``cache_wash_rules``）。

        1. **准入过滤**：逐维白名单——取值为 ✕ 的淘汰，未列出值按该维
           ``unlisted`` 策略（默认排除），体积小于/大于阈值的淘汰。
        2. **TopN**：同一「季 + 集区间」的候选按 ``order`` 逐维字典序排序，
           只留最优 ``top_n`` 条（默认 1，0 = 不限）。不同集区间各自比较。
        3. **逐维比较**：候选与该订阅的基线（已推送 / 媒体库 / 下载历史）
           逐维字典序比较，只有更优才留下；同质量 + 同分辨率 + 同体积
           （±容差）视为持平；画质解析不出的候选不参与比较（交给 TopN 兜底）。

        :returns: ``(保留的候选, 被这三道收口跳过的条数)``。
        """
        if not records:
            return [], 0
        rules = self.wash_rules()
        skipped = 0

        # —— 准入过滤 ——
        kept: List[dict] = []
        for record in records:
            profile = quality_service.parse_quality(record["item"].get("text") or "")
            ok, why = quality_service.filter_profile(profile, rules)
            if not ok:
                skipped += 1
                _count_reason(reasons, why)
                logger.debug(
                    f"[{self._plugin_id()}] 洗版淘汰："
                    f"{record['item'].get('title') or title}"
                    f"（msg={record['message_id']}）{why}"
                )
                continue
            record["profile"] = profile
            kept.append(record)

        # —— TopN：按（媒体类型, 季, 集, 集尾）分组，组内取逐维最优 ——
        top_n = int(rules.get("top_n") or 0)
        groups: Dict[tuple, List[dict]] = {}
        for record in kept:
            item = record["item"]
            key = (
                str(item.get("media_type") or ""),
                item.get("season"),
                item.get("episode"),
                item.get("episode_end"),
            )
            groups.setdefault(key, []).append(record)
        selected: List[dict] = []
        for bucket in groups.values():
            bucket.sort(
                key=lambda r: (
                    quality_service.sort_key(r["profile"], rules),
                    -int(r["item"].get("message_id") or 0),
                )
            )
            if top_n > 0 and len(bucket) > top_n:
                dropped = bucket[top_n:]
                skipped += len(dropped)
                for record in dropped:
                    _count_reason(reasons, "非最优版本")
                    logger.debug(
                        f"[{self._plugin_id()}] 洗版跳过（非最优）："
                        f"{record['item'].get('title') or title}"
                        f"（msg={record['message_id']}，"
                        f"{quality_service.describe(record['profile'])}）"
                    )
                bucket = bucket[:top_n]
            selected.extend(bucket)

        # —— 基线比对：已推送 + 下载历史 ——
        baselines = self._wash_baselines(title, sub)
        gated: List[dict] = []
        for record in selected:
            item = record["item"]
            profile = record["profile"]
            key = quality_service.baseline_key(
                title,
                sub.get("year"),
                item.get("season"),
                item.get("episode"),
                item.get("episode_end"),
            )
            base = baselines.get(key) or baselines.get(_normalized_key(key))
            state, why = quality_service.compare(base, profile, rules)
            if state == quality_service.STATE_FLAT:
                skipped += 1
                _count_reason(reasons, "画质未升级")
                logger.debug(
                    f"[{self._plugin_id()}] 洗版跳过（画质未升级）："
                    f"{item.get('title') or title}（msg={record['message_id']}）"
                    f"{quality_service.describe(profile)}｜{why}"
                )
                continue
            record["baseline_key"] = key
            record["quality_state"] = state
            record["quality_reason"] = why
            gated.append(record)
        return gated, skipped

    def _wash_baselines(self, title: str, sub: dict) -> Dict[str, dict]:
        """汇总比对来源（已推送 / 下载历史），键为 ``baseline_key``。"""
        rules = self.wash_rules()
        sources = set(rules.get("compare_sources") or ())
        baselines: Dict[str, dict] = {}
        if "pushed" in sources:
            baselines.update(self._wash_baseline())
        if "history" in sources:
            for key, profile in self._history_baseline(title, sub).items():
                baselines.setdefault(key, profile)
        return baselines

    def _history_baseline(self, title: str, sub: dict) -> Dict[str, dict]:
        """下载历史（PT 已下）基线：把发布名解析成画像，按季集区间归并。

        宿主媒体库拿不到画质字段（``MediaServerItem`` 无 resolution / codec），
        所以「媒体库已存在」这一来源目前不参与画质比较；PT 下载历史里有发布名
        与体积，足以判断「同质量同大小」。
        """
        records = self._download_history(title)
        if not records:
            return {}
        rules = self.wash_rules()
        result: Dict[str, dict] = {}
        for record in records:
            text = " ".join(
                str(record.get(field) or "")
                for field in ("torrent_name", "text", "path", "title")
            )
            profile = quality_service.parse_quality(text)
            if not profile.get("known"):
                continue
            key = _normalized_key(quality_service.baseline_key(
                title,
                sub.get("year"),
                _first_value(record.get("seasons")),
                _first_value(record.get("episodes")),
                None,
            ))
            current = result.get(key)
            if current is None or (
                quality_service.sort_key(profile, rules)
                < quality_service.sort_key(current, rules)
            ):
                result[key] = profile
        return result

    @staticmethod
    def _download_history(title: str) -> List[dict]:
        """按标题分页拉下载历史；宿主接口缺失或异常时返回空（不阻断洗版）。"""
        try:
            from ..services import forward_gate as gate
        except Exception:
            return []
        query = getattr(gate, "list_history_records", None)
        if not getattr(gate, "HISTORY_QUERIES_AVAILABLE", False) or query is None:
            return []
        try:
            records = query({"title": title})
        except Exception as err:
            logger.warning(
                f"[tgmediacenter] 下载历史查询失败，洗版仅用已推送基线：{err}"
            )
            return []
        return [_history_fields(item) for item in list(records or [])]

    def _wash_baseline(self) -> Dict[str, dict]:
        """读取洗版质量基线（订阅 + 季集区间 → 最优画质画像）。"""
        stored = self._plugin.get_data(_WASH_BASELINE_KEY) or {}
        items = stored.get("items") if isinstance(stored, dict) else None
        if not isinstance(items, dict):
            return {}
        return {str(key): dict(value) for key, value in items.items() if isinstance(value, dict)}

    def _save_wash_baseline(self, updates: Dict[str, dict]) -> None:
        """把本轮推送成功的画质合并进基线并落盘（按最近时间截断）。"""
        if not updates:
            return
        items = dict(self._wash_baseline())
        now = datetime.now().isoformat(timespec="seconds")
        for key, profile in updates.items():
            if not profile or not profile.get("known"):
                continue
            items[str(key)] = {**dict(profile), "ts": now}
        if len(items) > _WASH_BASELINE_LIMIT:
            ordered = sorted(
                items.items(),
                key=lambda kv: str(kv[1].get("ts") or ""),
                reverse=True,
            )
            items = dict(ordered[:_WASH_BASELINE_LIMIT])
        self._plugin.save_data(_WASH_BASELINE_KEY, {"items": items, "version": 1})

    # ------------------------------------------------------------------ 命中流水

    def _plugin_id(self) -> str:
        return getattr(self._plugin, "__class__").__name__ or "TgMediaCenter"

    def _db(self):
        return getattr(self._plugin, "get_database", lambda: None)()

    def _hit_exists(self, chat_id: int, message_id: int) -> bool:
        """该缓存消息是否已因回搜推送过（虚拟规则维度去重）。"""
        return self._hit_exists_by_rule(chat_id, message_id, CACHE_SEARCH_RULE_ID)

    def _hit_exists_by_rule(self, chat_id: int, message_id: int, rule_id: str) -> bool:
        db = self._db()
        if db is None:
            return False
        try:
            from sqlalchemy import select

            with db.session() as session:
                row = session.execute(
                    select(TgHitLog.id).where(
                        TgHitLog.plugin_id == self._plugin_id(),
                        TgHitLog.rule_id == rule_id,
                        TgHitLog.chat_id == int(chat_id),
                        TgHitLog.message_id == int(message_id),
                    )
                ).first()
                return row is not None
        except Exception as err:  # pragma: no cover
            logger.debug(f"查询缓存回搜流水失败：{err}")
            return False

    def _record_hit(self, item: dict, subscription: str, verdict: dict, task_id: int) -> None:
        """写一条缓存回搜的命中流水（与监控流水同表，用虚拟规则区分）。"""
        logger.info(
            f"[{self._plugin_id()}] 缓存回搜命中：「{item.get('title') or subscription}」"
            f"（chat={item.get('chat_id')}, msg={item.get('message_id')}）已入推送队列 #{task_id}"
        )
        db = self._db()
        if db is None:
            return
        try:
            with db.session() as session:
                session.add(TgHitLog(
                    plugin_id=self._plugin_id(),
                    rule_id=CACHE_SEARCH_RULE_ID,
                    rule_name=CACHE_SEARCH_RULE_NAME,
                    chat_id=int(item.get("chat_id") or 0),
                    message_id=int(item.get("message_id") or 0),
                    title=str(item.get("title") or subscription or "")[:250],
                    year=str(item.get("year") or "")[:16],
                    season=item.get("season"),
                    episode=item.get("episode"),
                    media_type=str(item.get("media_type") or "")[:16],
                    decision=DECISION_HIT,
                    destination=self.destination()[:32],
                    target_id="",
                    detail=f"订阅「{subscription}」缓存回搜：{verdict.get('reason') or ''}；已入推送队列 #{task_id}"[:500],
                ))
                session.commit()
        except Exception as err:  # pragma: no cover - 冲突说明已处理过
            logger.debug(f"写缓存回搜流水失败：{err}")

    # ------------------------------------------------------------------ 状态

    def status(self) -> dict:
        """缓存模块运行态（供状态接口与前端展示）。"""
        chat_ids = self.chat_ids()
        channels = self._history.stats(chat_ids)
        names = self._dialog_names()
        for item in channels:
            item["name"] = names.get(int(item.get("chat_id") or 0), "")
        try:
            matcher_status = MediaMatcher().capabilities()
        except Exception as err:  # pragma: no cover - 探测失败不阻塞状态
            logger.debug(f"[{self._plugin_id()}] 探测缺失判断数据源失败：{err}")
            matcher_status = {}
        return {
            "enabled": self.enabled(),
            "chat_ids": chat_ids,
            "chats": len(chat_ids),
            "destination": self.destination(),
            "total": self._history.total_count(),
            "channels": channels,
            "sync": self._history.progress(),
            "matcher": {
                "queries_available": bool(matcher_status.get("queries_available")),
                "mediaserver_available": bool(matcher_status.get("mediaserver_available")),
                "mediaserver": str(matcher_status.get("mediaserver") or ""),
                "subscriptions": int(matcher_status.get("subscriptions") or 0),
            },
            "settings": self.settings(),
        }

    def _dialog_names(self) -> Dict[int, str]:
        """对话缓存里的 ID → 标题映射（展示增强，失败不影响主体）。"""
        credentials = getattr(self._plugin, "_credentials", None)
        if credentials is None:
            return {}
        try:
            dialogs = credentials.cached_dialogs() or []
        except Exception:  # pragma: no cover
            return {}
        result: Dict[int, str] = {}
        for item in dialogs:
            try:
                result[int(item.get("id"))] = str(item.get("name") or "")
            except (TypeError, ValueError, AttributeError):
                continue
        return result

    # ------------------------------------------------------------------ 定时任务入口

    # -------------------------------------------------- 洗版回搜（1.13.34 唯一入口）

    def _list_subscription_targets(self) -> List[dict]:
        """把宿主订阅压成 ``[{name, year, media_id}]``（读不到就返回空列表）。"""
        targets: List[dict] = []
        try:
            iterator = matcher_service.iter_subscriptions()
        except Exception as err:  # pragma: no cover - 宿主查询异常
            logger.debug(f"[{self._plugin_id()}] 读取订阅失败：{err}")
            return targets
        for item in iterator or []:
            try:
                name = str(getattr(item, "name", "") or "").strip()
            except Exception:  # pragma: no cover - 宿主对象异常
                continue
            if not name:
                continue
            targets.append({
                "name": name,
                "year": str(getattr(item, "year", "") or ""),
                "media_id": str(getattr(item, "tmdb_id", "") or getattr(item, "media_id", "") or ""),
            })
        return targets

    def run_subscription_search(self) -> dict:
        """遍历订阅逐条回搜缓存，命中更优资源才入队。

        1.13.34 起这是洗版规则唯一的判定路径：频道来了新消息 → 入库 →
        对每个订阅回搜本地缓存 → 洗版规则逐维比较 → 更优才推 115。
        """
        empty = {"checked": False, "pushed": 0, "details": [], "subscriptions": 0}
        if not self.enabled() or not self.chat_ids():
            return empty
        targets = self._list_subscription_targets()
        if not targets:
            return empty
        details: List[dict] = []
        pushed = 0
        for sub in targets:
            try:
                detail = self._search_subscription(sub)
            except Exception as err:  # pragma: no cover - 单订阅异常不拖垮整轮
                logger.warning(f"[{self._plugin_id()}] 洗版回搜「{sub.get('name')}」失败：{err}")
                continue
            details.append(detail)
            pushed += int(detail.get("pushed") or 0)
        if pushed:
            self._notify_search_result(pushed, details)
        return {
            "checked": True,
            "pushed": pushed,
            "details": details,
            "subscriptions": len(targets),
        }

    def request_wash_search(self, delay: float = 2.0) -> None:
        """新消息入库后请求一次洗版回搜（``delay`` 秒防抖，合并连续消息）。"""
        if not self.wash_rules().get("enabled"):
            return
        lock = getattr(self, "_wash_request_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._wash_request_lock = lock  # type: ignore[attr-defined]
        with lock:
            timer = getattr(self, "_wash_request_timer", None)
            if timer is not None and timer.is_alive():
                return
            timer = threading.Timer(max(0.0, float(delay)), self._run_wash_search_quietly)
            timer.daemon = True
            self._wash_request_timer = timer  # type: ignore[attr-defined]
            timer.start()

    def _run_wash_search_quietly(self) -> None:
        try:
            result = self.run_subscription_search()
            if result.get("pushed"):
                logger.info(
                    f"[{self._plugin_id()}] 洗版回搜推送 {result['pushed']} 条"
                    f"（订阅 {result['subscriptions']} 个）"
                )
        except Exception as err:  # pragma: no cover - 后台线程兜底
            logger.warning(f"[{self._plugin_id()}] 洗版回搜异常：{err}")

    def cancel_wash_search(self) -> None:
        """停用/卸载时取消挂起的洗版回搜。"""
        timer = getattr(self, "_wash_request_timer", None)
        if timer is not None and timer.is_alive():
            timer.cancel()
        self._wash_request_timer = None  # type: ignore[attr-defined]

    def run_scheduled_sync(self) -> None:
        """定时增量同步（cache_cron 触发）。"""
        if not self.enabled() or not self.chat_ids():
            return
        if self._history.is_syncing():
            logger.info(f"[{self._plugin_id()}] 缓存定时同步跳过：已有任务在进行中")
            return
        result = self.sync(mode=MODE_ALL)
        if result.get("started"):
            logger.info(f"[{self._plugin_id()}] 缓存定时同步已启动：{result.get('message')}")
        else:
            logger.info(f"[{self._plugin_id()}] 缓存定时同步未启动：{result.get('message')}")


def _normalize_cron(raw: Any, fallback: str) -> str:
    """只接受 5 段式 cron；非法值退回默认。

    非法 cron 会让 ``CronTrigger.from_crontab`` 抛异常，进而拖垮整个
    缓存定时任务注册（get_service 整体兜底），因此在写入配置前就拦掉。
    """
    text = str(raw or "").strip()
    if len(text.split()) != 5:
        return fallback
    return text







def _count_reason(bucket: Dict[str, int], label: str) -> None:
    """累计跳过原因（回搜结果说明用）。"""
    key = str(label or "其他").strip() or "其他"
    bucket[key] = int(bucket.get(key) or 0) + 1


def _numbered(value: Any) -> str:
    """季/集值归一：``S01`` / ``第1季`` / ``1`` 都压成 ``1``（认不出就原样返回）。"""
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.findall(r"\d+", text)
    return digits[0] if digits else text


def _normalized_key(key: str) -> str:
    """基线键的季/集归一版本（下载历史的 ``S01`` 与缓存写法对齐）。"""
    parts = str(key or "").split("|")
    if len(parts) >= 5:
        for index in (2, 3, 4):
            parts[index] = _numbered(parts[index])
    return "|".join(parts)


def _first_value(raw: Any) -> Any:
    """``seasons`` / ``episodes`` 可能是列表或标量，取第一个。"""
    if isinstance(raw, (list, tuple)):
        return raw[0] if raw else None
    return raw


def _history_fields(item: Any) -> Dict[str, Any]:
    """下载历史快照压成判定所需字段（发布名/体积在部分宿主上是 torrent_*）。"""
    return {
        "torrent_name": getattr(item, "torrent_name", None),
        "torrent_size": getattr(item, "torrent_size", None),
        "text": getattr(item, "text", None),
        "path": getattr(item, "path", None),
        "title": getattr(item, "title", None),
        "seasons": getattr(item, "seasons", None),
        "episodes": getattr(item, "episodes", None),
        "date": getattr(item, "date", None),
    }


def _skip_label(verdict: dict) -> str:
    """把判定结果压成一句人话（决定跳过原因归类）。

    归类要粗（媒体库已存在 / 未订阅 / 无缺集 / 无法判断），
    否则"逐集"的原因会把说明撑成 34 种写法。
    """
    if verdict.get("missing") is None:
        return "无法判断（无媒体库数据源）"
    source = str(verdict.get("source") or "")
    if source == "mediaserver":
        return "媒体库已存在"
    if source == "subscription":
        return "未订阅" if verdict.get("reason") == "未订阅" else "订阅无缺集"
    return str(verdict.get("reason") or "跳过")


def _reason_text(bucket: Dict[str, int]) -> str:
    """跳过原因汇总文本：``媒体库已存在 30、已推送过 3、无可用链接 1``。"""
    if not bucket:
        return ""
    ordered = _reason_order(bucket)
    return "、".join(f"{label} {count}" for label, count in ordered)


def _reason_order(bucket: Dict[str, int]) -> List["tuple[str, int]"]:
    """跳过原因排序（条数多在前，同数按名称），供带计数 / 不带计数两种文案共用。"""
    return sorted(bucket.items(), key=lambda item: (-int(item[1]), item[0]))


def _media_label(meta: Optional[dict]) -> str:
    """把识别结果拼成通知 / 流水用的简报文案，如「美人余 (2026) S01E01-E11」。

    与 ``core.pipeline.MessagePipeline._media_label`` 同款拼法（缓存回搜通知
    与 115 转存通知口径一致，避免两套格式漂移）。
    """
    if not meta:
        return ""
    title = str(meta.get("title") or "").strip()
    if not title:
        return ""
    parts: List[str] = [title]
    year = str(meta.get("year") or "").strip()
    if year:
        parts.append(f"({year})")
    season = meta.get("season")
    episode = meta.get("episode")
    episode_end = meta.get("episode_end")
    if season:
        seg = f"S{int(season):02d}"
        if episode:
            seg += f"E{int(episode):02d}"
            if episode_end and int(episode_end) != int(episode):
                seg += f"-E{int(episode_end):02d}"
        parts.append(seg)
    return " ".join(parts)


def _destination_options() -> List[dict]:
    """前端下拉用的推送目标选项。"""
    from ..destinations import DESTINATION_OPTIONS

    return list(DESTINATION_OPTIONS)
