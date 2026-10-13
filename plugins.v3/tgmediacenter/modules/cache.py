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

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

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
from ..services import matcher as matcher_service
from ..services.matcher import MediaMatcher

# 缓存回搜在命中流水里的"虚拟规则"标识（便于在流水里与监控规则区分）
CACHE_SEARCH_RULE_ID = "cache_search"
CACHE_SEARCH_RULE_NAME = "缓存回搜"
# 上次订阅快照的插件数据键。
# v2：1.4.1 的推送因 push_task.chat_id 超出 int32 全部入队失败，但快照已把
# 那批订阅记为「已处理」；换键作废旧快照，修复后首次检查会全量重搜——
# 已成功推送过的被命中流水拦住，入队失败的那批（无流水记录）得以补推。
_SUB_SNAPSHOT_KEY = "cache_sub_snapshot_v2"
_SUB_STATE_KEY = "cache_sub_state"
# 定时任务默认 cron（5 段：分 时 日 月 周）
DEFAULT_SYNC_CRON = "0 */6 * * *"
DEFAULT_SUBSCRIBE_CRON = "*/30 * * * *"
# 订阅事件防抖秒数：批量添加订阅时合并为一次回搜
_EVENT_DEBOUNCE_SECONDS = 5.0


class CacheModule:
    """历史消息缓存编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._history = HistoryCacheService(plugin)
        self._matcher = MediaMatcher()
        self._lock = threading.Lock()
        # 订阅事件防抖（事件处理器挂在插件主类上，见 TgMediaCenter.on_subscribe_added）
        self._evt_lock = threading.Lock()
        self._evt_timer: Optional[threading.Timer] = None
        self._listener_installed = False
        self._pending_events: List[dict] = []
        self._event_runs = 0
        self._state: Dict[str, Any] = {
            "last_check_at": "",
            "last_check_new": 0,
            "last_check_pushed": 0,
            "last_error": "",
            "checking": False,
        }

    # ------------------------------------------------------ 订阅事件（实时回搜）

    def mark_event_listener(self, installed: bool) -> None:
        """登记事件监听状态（注册动作在插件主类，宿主只解析插件实例方法）。"""
        self._listener_installed = bool(installed)
        if installed:
            logger.info(
                f"[{self._plugin_id()}] 已监听宿主新增订阅事件：新增订阅后 "
                f"{_EVENT_DEBOUNCE_SECONDS:.0f} 秒内回搜缓存"
            )

    @property
    def event_listener_installed(self) -> bool:
        return self._listener_installed

    @property
    def event_runs(self) -> int:
        """事件触发的回搜已执行次数（可观测性 / 测试用）。"""
        with self._lock:
            return int(self._event_runs)

    def on_subscribe_event(self, event: Any = None) -> None:
        """宿主新增订阅事件入口：收集订阅 ID 并防抖触发回搜。

        与定时检查的「快照对比」不同，事件路径**按订阅精准回搜**——
        删除后重新添加的订阅（快照里已存在）同样会回搜，重复推送由
        命中流水拦掉，因入队失败而没写流水的则是补推。
        """
        if not (self.enabled() and self.subscribe_enabled()):
            return
        payload = _event_payload(event)
        sid = _as_int(payload.get("subscribe_id"))
        info = payload.get("mediainfo")
        info = info if isinstance(info, dict) else {}
        if not sid and not info:
            logger.debug(f"[{self._plugin_id()}] 订阅事件缺少 subscribe_id 与 mediainfo，忽略")
            return
        with self._lock:
            self._pending_events.append({"id": sid, "info": info})
        logger.info(
            f"[{self._plugin_id()}] 收到新增订阅事件"
            f"（subscribe_id={sid if sid else '未提供'}），{_EVENT_DEBOUNCE_SECONDS:.0f} 秒后回搜缓存"
        )
        self._schedule_event_check()

    def _schedule_event_check(self) -> None:
        """重置防抖定时器：批量添加订阅合并为一次回搜。"""
        with self._evt_lock:
            self._cancel_event_timer(locked=True)
            timer = threading.Timer(_EVENT_DEBOUNCE_SECONDS, self._run_pending_search)
            timer.daemon = True
            self._evt_timer = timer
            timer.start()

    def _cancel_event_timer(self, locked: bool = False) -> None:
        if not locked:
            with self._evt_lock:
                self._cancel_event_timer(locked=True)
                return
        timer = self._evt_timer
        self._evt_timer = None
        if timer is not None:
            timer.cancel()

    def cancel_event_timer(self) -> None:
        """取消待执行的防抖回搜（插件停止时调用）。"""
        self._cancel_event_timer()

    def _run_pending_search(self) -> None:
        """防抖到点：对事件带来的订阅逐个回搜。"""
        try:
            with self._lock:
                if self._state.get("checking"):
                    # 定时检查/手动检查正在进行：稍后重试（pending 不丢）
                    self._schedule_event_check()
                    return
                self._state["checking"] = True
                events = list(self._pending_events)
                self._pending_events.clear()
            try:
                self._search_event_subscriptions(events)
            finally:
                with self._lock:
                    self._state["checking"] = False
        except Exception as err:  # pragma: no cover
            logger.warning(f"[{self._plugin_id()}] 订阅事件回搜失败：{err}")

    def _search_event_subscriptions(self, events: List[dict]) -> dict:
        """按事件里的订阅 ID / 媒体信息回搜缓存并推送。"""
        with self._lock:
            self._event_runs += 1
        targets: List[tuple] = []
        items: List[Any] = []
        if any(item.get("id") for item in events):
            try:
                items = list(matcher_service.iter_subscriptions())
            except Exception as err:
                logger.warning(f"[{self._plugin_id()}] 订阅事件回搜：读取宿主订阅失败：{err}")
                items = []
        by_id: Dict[int, Any] = {}
        for item in items:
            value = _as_int(getattr(item, "id", None))
            if value:
                by_id[value] = item

        for event in events:
            sid = _as_int(event.get("id"))
            info = event.get("info") if isinstance(event.get("info"), dict) else {}
            entry: dict = {}
            key = ""
            if sid:
                snapshot_item = by_id.get(sid)
                if snapshot_item is not None:
                    key, entry = _snapshot_entry(snapshot_item)
                elif info:
                    # 订阅查询里还看不到（事务/缓存窗口）时用事件里的媒体信息兜底
                    logger.info(
                        f"[{self._plugin_id()}] 订阅事件回搜：订阅 {sid} 不在订阅列表中，"
                        f"改用事件媒体信息回搜"
                    )
            if not entry and info:
                key, entry = _entry_from_mediainfo(info)
            if not entry:
                logger.info(f"[{self._plugin_id()}] 订阅事件回搜：订阅 {sid or '未知'} 无可用信息，跳过")
                continue
            targets.append((key, entry))

        if not targets:
            self._remember_check(new=0, pushed=0, error="")
            return {"checked": True, "new": 0, "pushed": 0, "message": "订阅事件无可回搜目标"}

        # 快照并入：事件已处理的订阅不该在下次定时检查里再被当作「新增」。
        # 无基线时先建立完整基线，否则并入后会把其余存量订阅误判为新增。
        previous = self._plugin.get_data(_SUB_SNAPSHOT_KEY)
        if not isinstance(previous, dict) or not previous:
            self._check_subscriptions_locked(trigger="订阅事件（建基线）")
            previous = self._plugin.get_data(_SUB_SNAPSHOT_KEY)
        merged = dict(previous) if isinstance(previous, dict) else {}
        for key, entry in targets:
            merged[key] = entry
        self._plugin.save_data(_SUB_SNAPSHOT_KEY, merged)

        logger.info(f"[{self._plugin_id()}] 订阅事件回搜：{len(targets)} 个订阅")
        pushed_total = 0
        details: List[dict] = []
        for key, sub in targets:
            try:
                result = self._search_subscription(sub)
            except Exception as err:  # 单个订阅失败不影响其余
                logger.warning(f"[{self._plugin_id()}] 订阅「{sub.get('name')}」缓存回搜失败：{err}")
                result = {"name": sub.get("name"), "candidates": 0, "pushed": 0, "error": str(err)}
            pushed_total += int(result.get("pushed") or 0)
            details.append(result)
        self._remember_check(new=len(targets), pushed=pushed_total, error="")
        self._notify_search_result(len(targets), details)
        return {"checked": True, "new": len(targets), "pushed": pushed_total, "details": details}

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
        value = str(self._cfg("cache_destination", "smart") or "smart").strip().lower()
        return value if value in DESTINATION_VALUES else "smart"

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

    def subscribe_enabled(self) -> bool:
        return bool(self._cfg("cache_subscribe_enabled", True))

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

    def subscribe_cron(self) -> str:
        """订阅检查 cron。"""
        return _normalize_cron(self._cfg("cache_subscribe_cron"), DEFAULT_SUBSCRIBE_CRON)

    def settings(self) -> dict:
        """缓存设置（供前端面板回显）。"""
        return {
            "enabled": self.enabled(),
            "chat_ids": self.chat_ids(),
            "destination": self.destination(),
            "sync_mode": self.sync_mode(),
            "sync_days": self.sync_days(),
            "batch_size": self.batch_size(),
            "subscribe_enabled": self.subscribe_enabled(),
            "cron": self.cron(),
            "subscribe_cron": self.subscribe_cron(),
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
        if "subscribe_enabled" in data:
            patch["cache_subscribe_enabled"] = bool(data.get("subscribe_enabled"))
        if "cron" in data:
            patch["cache_cron"] = _normalize_cron(data.get("cron"), DEFAULT_SYNC_CRON)
        if "subscribe_cron" in data:
            patch["cache_subscribe_cron"] = _normalize_cron(data.get("subscribe_cron"), DEFAULT_SUBSCRIBE_CRON)
        if patch:
            self._plugin.save_config(**patch)
        return self.settings()

    def batch_size(self) -> int:
        try:
            return min(500, max(20, int(self._cfg("cache_batch_size", 200) or 200)))
        except (TypeError, ValueError):
            return 200

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
        try:
            func(title=title, text=text)
        except Exception as err:  # pragma: no cover - 通知失败不影响主流程
            logger.debug(f"发送缓存回搜通知失败：{err}")

    def check_subscriptions(self, *, trigger: str = "定时") -> dict:
        """对比订阅快照，对新增订阅执行缓存回搜并推送。"""
        if not self.enabled():
            return {"checked": False, "message": "未启用消息缓存"}
        if not self.subscribe_enabled():
            return {"checked": False, "message": "未启用订阅回搜"}
        if not matcher_service.QUERIES_AVAILABLE:
            return {"checked": False, "message": "宿主订阅查询不可用"}
        with self._lock:
            if self._state.get("checking"):
                return {"checked": False, "message": "已有订阅检查在进行中"}
            self._state["checking"] = True
        try:
            return self._check_subscriptions_locked(trigger=trigger)
        finally:
            with self._lock:
                self._state["checking"] = False

    def _check_subscriptions_locked(self, *, trigger: str) -> dict:
        try:
            # 翻页读全量：无参调用只返回第一页 50 条，基线会漏掉其余订阅（1.4.0 实测踩坑）
            items = list(matcher_service.iter_subscriptions())
        except Exception as err:
            self._remember_check(new=0, pushed=0, error=f"读取订阅失败：{err}")
            logger.warning(f"[{self._plugin_id()}] 读取宿主订阅失败：{err}")
            return {"checked": False, "message": f"读取订阅失败：{err}"}

        snapshot = {key: value for key, value in (_snapshot_entry(item) for item in items) if key}
        previous = self._plugin.get_data(_SUB_SNAPSHOT_KEY) or {}
        if not isinstance(previous, dict):
            previous = {}

        if not previous:
            # 首次运行：只建立基线，避免把存量订阅一次性全部回搜推送
            self._plugin.save_data(_SUB_SNAPSHOT_KEY, snapshot)
            self._remember_check(new=0, pushed=0, error="")
            logger.info(
                f"[{self._plugin_id()}] 订阅回搜：已建立基线（{len(snapshot)} 个订阅），"
                f"后续新增订阅将自动回搜缓存"
            )
            return {"checked": True, "baseline": True, "subscriptions": len(snapshot),
                    "new": 0, "pushed": 0, "message": f"已建立订阅基线（{len(snapshot)} 个）"}

        new_keys = [key for key in snapshot if key not in previous]
        # 先落快照：即使回搜中途出错，也不会在下轮把同一订阅重复当作"新增"
        self._plugin.save_data(_SUB_SNAPSHOT_KEY, snapshot)
        if not new_keys:
            self._remember_check(new=0, pushed=0, error="")
            return {"checked": True, "new": 0, "pushed": 0, "message": "没有新增订阅"}

        logger.info(f"[{self._plugin_id()}] 订阅回搜（{trigger}）：发现 {len(new_keys)} 个新增订阅")
        pushed_total = 0
        details: List[dict] = []
        for key in new_keys:
            sub = snapshot[key]
            try:
                result = self._search_subscription(sub)
            except Exception as err:  # 单个订阅失败不影响其余
                logger.warning(f"[{self._plugin_id()}] 订阅「{sub.get('name')}」缓存回搜失败：{err}")
                result = {"name": sub.get("name"), "candidates": 0, "pushed": 0, "error": str(err)}
            pushed_total += int(result.get("pushed") or 0)
            details.append(result)

        self._remember_check(new=len(new_keys), pushed=pushed_total, error="")
        self._notify_search_result(len(new_keys), details)
        return {
            "checked": True,
            "new": len(new_keys),
            "pushed": pushed_total,
            "details": details,
            "message": f"新增订阅 {len(new_keys)} 个，推送 {pushed_total} 条",
        }

    def _notify_search_result(self, new_count: int, details: List[dict]) -> None:
        """回搜结果通知。

        两种口径都要发：**推了**要说清推了几条；**一条没推**更要说清为什么
        （媒体库已存在 / 已推送过），否则界面上就是"什么都没发生"，
        用户无法判断是漏推还是正常跳过（1.4.3 真机反馈"新增订阅插件没有任何输出"）。
        """
        candidates = sum(int(item.get("candidates") or 0) for item in details)
        pushed = sum(int(item.get("pushed") or 0) for item in details)
        if not candidates and not pushed:
            return
        lines: List[str] = []
        for item in details:
            if not (int(item.get("candidates") or 0) or int(item.get("pushed") or 0)):
                continue
            line = (
                f"· {item.get('name')}：候选 {item.get('candidates', 0)} 条，"
                f"推送 {item.get('pushed', 0)} 条"
            )
            extra: List[str] = []
            if item.get("reason_text"):
                extra.append(str(item["reason_text"]))
            # 全推出去时必须说清"为什么判定媒体库没有"——否则用户只知道推了，
            # 不知道判定依据对不对（1.4.6 真机：媒体库明明有却被判成不存在）
            if item.get("media_note"):
                extra.append(f"媒体库未收录：{item['media_note']}")
            if extra:
                line += "（" + "；".join(extra) + "）"
            lines.append(line)
        if pushed:
            header = f"新增订阅 {new_count} 个，命中并推送 {pushed} 条资源："
        else:
            header = f"新增订阅 {new_count} 个，候选 {candidates} 条，无需推送："
        self._notify("TG媒体中心 缓存回搜", header + "\n" + "\n".join(lines))

    def _search_subscription(self, sub: dict) -> dict:
        """对单个订阅在缓存里回搜并推送。"""
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
        skipped = 0
        reasons: Dict[str, int] = {}
        media_note = ""
        for item in candidates:
            links = [str(link) for link in (item.get("links") or []) if str(link).strip()]
            if not links:
                skipped += 1
                _count_reason(reasons, "无可用链接")
                continue
            chat_id = int(item.get("chat_id") or 0)
            message_id = int(item.get("message_id") or 0)
            if self._hit_exists(chat_id, message_id):
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
            else:
                skipped += 1
                _count_reason(reasons, "入队失败")
        reason_text = _reason_text(reasons)
        logger.info(
            f"[{self._plugin_id()}] 缓存回搜结果：「{title}」候选 {len(candidates)} 条，"
            f"推送 {pushed} 条，跳过 {skipped} 条"
            + (f"（{reason_text}）" if reason_text else "")
        )
        return {
            "name": title,
            "candidates": len(candidates),
            "pushed": pushed,
            "skipped": skipped,
            "reasons": reasons,
            "reason_text": reason_text,
            "media_note": media_note,
        }

    def _remember_check(self, *, new: int, pushed: int, error: str) -> None:
        state = {
            "last_check_at": datetime.now().isoformat(timespec="seconds"),
            "last_check_new": int(new),
            "last_check_pushed": int(pushed),
            "last_error": str(error or ""),
        }
        self._plugin.save_data(_SUB_STATE_KEY, state)
        with self._lock:
            self._state.update(state)

    def subscribe_state(self) -> dict:
        """订阅回搜运行态（读插件数据，跨重启保留）。"""
        stored = self._plugin.get_data(_SUB_STATE_KEY) or {}
        if not isinstance(stored, dict):
            stored = {}
        with self._lock:
            return {
                "enabled": self.subscribe_enabled(),
                "checking": bool(self._state.get("checking")),
                "event_listener": self._listener_installed,
                "last_check_at": str(stored.get("last_check_at") or ""),
                "last_check_new": int(stored.get("last_check_new") or 0),
                "last_check_pushed": int(stored.get("last_check_pushed") or 0),
                "last_error": str(stored.get("last_error") or ""),
            }

    # ------------------------------------------------------------------ 命中流水

    def _plugin_id(self) -> str:
        return getattr(self._plugin, "__class__").__name__ or "TgMediaCenter"

    def _db(self):
        return getattr(self._plugin, "get_database", lambda: None)()

    def _hit_exists(self, chat_id: int, message_id: int) -> bool:
        """该缓存消息是否已因回搜推送过（虚拟规则维度去重）。"""
        db = self._db()
        if db is None:
            return False
        try:
            from sqlalchemy import select

            with db.session() as session:
                row = session.execute(
                    select(TgHitLog.id).where(
                        TgHitLog.plugin_id == self._plugin_id(),
                        TgHitLog.rule_id == CACHE_SEARCH_RULE_ID,
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
            "subscribe": self.subscribe_state(),
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

    def run_subscription_job(self) -> None:
        """定时订阅检查（cache_subscribe_cron 触发）。"""
        if not self.enabled() or not self.subscribe_enabled():
            return
        result = self.check_subscriptions(trigger="定时")
        if result.get("pushed"):
            logger.info(f"[{self._plugin_id()}] 订阅回搜：{result.get('message')}")


def _normalize_cron(raw: Any, fallback: str) -> str:
    """只接受 5 段式 cron；非法值退回默认。

    非法 cron 会让 ``CronTrigger.from_crontab`` 抛异常，进而拖垮整个
    缓存定时任务注册（get_service 整体兜底），因此在写入配置前就拦掉。
    """
    text = str(raw or "").strip()
    if len(text.split()) != 5:
        return fallback
    return text


def _snapshot_entry(item: Any) -> "tuple[str, dict]":
    """把一条订阅快照归一为 (快照键, 订阅信息)。"""
    return _entry_from_fields(
        name=getattr(item, "name", ""),
        year=getattr(item, "year", ""),
        season=getattr(item, "season", None),
        media_source=getattr(item, "media_source", ""),
        media_id=getattr(item, "media_id", ""),
        lack_episode=getattr(item, "lack_episode", None),
    )


def _entry_from_mediainfo(info: dict) -> "tuple[str, dict]":
    """把宿主事件 payload 里的 mediainfo 归一为 (快照键, 订阅信息)。

    事件里订阅 ID 可能查不到（刚删除 / 事务未提交），此时用 mediainfo 兜底：
    host ``MediaInfo.to_dict()`` 的标题字段是 ``title``（订阅名同源）。
    """
    return _entry_from_fields(
        name=info.get("title") or info.get("name") or "",
        year=info.get("year") or "",
        season=info.get("season"),
        media_source=info.get("media_source") or "",
        media_id=info.get("media_id") or "",
    )


def _entry_from_fields(
    *,
    name: Any,
    year: Any,
    season: Any,
    media_source: Any,
    media_id: Any,
    lack_episode: Any = None,
) -> "tuple[str, dict]":
    """订阅字段 → (快照键, 订阅信息)；键优先媒体来源+ID，回退片名+年份+季。"""
    name = str(name or "").strip()
    year = str(year or "")
    media_source = str(media_source or "")
    media_id = str(media_id or "")
    season_text = season if season is not None else ""
    if media_source or media_id:
        key = f"{media_source}|{media_id}|{season_text}"
    elif name:
        key = f"name|{name}|{year}|{season_text}"
    else:
        return "", {}
    return key, {
        "name": name,
        "year": year,
        "season": season,
        "media_source": media_source,
        "media_id": media_id,
        "lack_episode": lack_episode,
    }


def _event_payload(event: Any) -> dict:
    """从宿主事件对象里取出 dict payload（兼容 event_data / data 两种属性）。"""
    for attr in ("event_data", "data"):
        value = getattr(event, attr, None)
        if isinstance(value, dict):
            return value
    return {}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _count_reason(bucket: Dict[str, int], label: str) -> None:
    """累计跳过原因（回搜结果说明用）。"""
    key = str(label or "其他").strip() or "其他"
    bucket[key] = int(bucket.get(key) or 0) + 1


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
    ordered = sorted(bucket.items(), key=lambda item: (-int(item[1]), item[0]))
    return "、".join(f"{label} {count}" for label, count in ordered)


def _destination_options() -> List[dict]:
    """前端下拉用的推送目标选项。"""
    from ..destinations import DESTINATION_OPTIONS

    return list(DESTINATION_OPTIONS)
