"""⑤ 历史消息缓存模块：设置、同步编排、订阅回搜。

与监控的分界
------------
缓存的频道集合与监控规则的 ``source_ids`` **完全独立**：可以在「只缓存不监控」
的频道上归档消息，也可以两者重叠。事件入口把它们并集处理后分别投递。

订阅回搜（对标 MA 新版「订阅触发缓存搜索」）
--------------------------------------------
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
# 上次订阅快照的插件数据键
_SUB_SNAPSHOT_KEY = "cache_sub_snapshot"
_SUB_STATE_KEY = "cache_sub_state"
# 定时任务默认 cron（5 段：分 时 日 月 周）
DEFAULT_SYNC_CRON = "0 */6 * * *"
DEFAULT_SUBSCRIBE_CRON = "*/5 * * * *"


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
            page = matcher_service.list_subscriptions()
            items = list(getattr(page, "items", None) or [])
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
        if pushed_total:
            lines = [
                f"· {item.get('name')}：候选 {item.get('candidates', 0)} 条，推送 {item.get('pushed', 0)} 条"
                for item in details
            ]
            self._notify(
                "TG媒体中心 缓存回搜",
                f"新增订阅 {len(new_keys)} 个，命中并推送 {pushed_total} 条资源：\n" + "\n".join(lines),
            )
        return {
            "checked": True,
            "new": len(new_keys),
            "pushed": pushed_total,
            "details": details,
            "message": f"新增订阅 {len(new_keys)} 个，推送 {pushed_total} 条",
        }

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
        for item in candidates:
            links = [str(link) for link in (item.get("links") or []) if str(link).strip()]
            if not links:
                skipped += 1
                continue
            chat_id = int(item.get("chat_id") or 0)
            message_id = int(item.get("message_id") or 0)
            if self._hit_exists(chat_id, message_id):
                skipped += 1
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
            if verdict.get("missing") is not True:
                skipped += 1
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
        return {
            "name": title,
            "candidates": len(candidates),
            "pushed": pushed,
            "skipped": skipped,
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
        return {
            "enabled": self.enabled(),
            "chat_ids": chat_ids,
            "chats": len(chat_ids),
            "destination": self.destination(),
            "total": self._history.total_count(),
            "channels": channels,
            "sync": self._history.progress(),
            "subscribe": self.subscribe_state(),
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
    """把一条订阅归一为 (快照键, 订阅信息)。"""
    name = str(getattr(item, "name", "") or "")
    year = str(getattr(item, "year", "") or "")
    season = getattr(item, "season", None)
    media_source = str(getattr(item, "media_source", "") or "")
    media_id = str(getattr(item, "media_id", "") or "")
    if media_source or media_id:
        key = f"{media_source}|{media_id}|{season if season is not None else ''}"
    elif name:
        key = f"name|{name}|{year}|{season if season is not None else ''}"
    else:
        return "", {}
    return key, {
        "name": name,
        "year": year,
        "season": season,
        "media_source": media_source,
        "media_id": media_id,
        "lack_episode": getattr(item, "lack_episode", None),
    }


def _destination_options() -> List[dict]:
    """前端下拉用的推送目标选项。"""
    from ..destinations import DESTINATION_OPTIONS

    return list(DESTINATION_OPTIONS)
