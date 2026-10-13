"""④ TG 资源监控模块：规则管理、命中流水、流水线编排。

职责边界
--------
- 规则存**配置**（``monitor_rules``，随配置表单整份保存），本模块负责归一与校验；
- 命中流水 / 推送任务存**自有表**（P4 起启用的插件 schema）；
- 流水线（``core/pipeline.py``）的生命周期由本模块持有；
- 推送 worker 内嵌在流水线线程里，按 destination 分派执行。

与 P6「通用转发」的分界：本模块的 tg_forward 目标只做**整条消息转发**；
两级匹配 / 内容转换 / 置顶属于转发规则引擎（P6）。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core.cooldown import CooldownGate
from ..core.pipeline import MessagePipeline, new_rule_id
from ..destinations import DESTINATION_VALUES
from ..model.hit_log import DECISIONS, TgHitLog
from ..model.push_task import STATUS_DONE, STATUS_FAILED, STATUS_PENDING, TgPushTask
from ..services.matcher import MediaMatcher

_RULES_KEY = "monitor_rules"
# ensure_started 去抖窗口（秒）
_START_DEBOUNCE_SECONDS = 5.0


class MonitorModule:
    """TG 资源监控编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._matcher = MediaMatcher()
        self._gate = CooldownGate(5.0)
        self._pipeline: Optional[MessagePipeline] = None
        # 规则归一缓存：插件配置对象不变则复用（TG 事件线程会高频查询）
        self._rules_cache: Optional[tuple] = None
        # ensure_started 去抖时间戳（单调时钟）
        self._start_attempt_at = 0.0

    # ------------------------------------------------------------------ 配置读取

    @property
    def _config(self) -> dict:
        return getattr(self._plugin, "config", {}) or {}

    def _cfg(self, key: str, default: Any = None) -> Any:
        value = self._config.get(key)
        return default if value is None else value

    def config_value(self, key: str, default: Any = None) -> Any:
        """供流水线读取聚合窗口等配置。"""
        return self._cfg(key, default)

    def enabled(self) -> bool:
        return bool(self._cfg("monitor_enabled"))

    # ------------------------------------------------------------------ 规则归一

    def normalize_rules(self, raw: Any) -> List[dict]:
        """把配置里的原始规则列表归一为后端内部结构。

        - 补稳定 ``id``（保存时生成，重排/重命名后流水不串）；
        - ``source_ids`` 只保留能转成整数的（TG 会话 ID，含 -100 前缀频道）；
        - ``destination`` 非法值回落 ``smart``；
        - 未启用的规则不参与匹配，但仍保存（用户可能临时停用某条）。
        """
        rules: List[dict] = []
        for index, item in enumerate(raw or []):
            if not isinstance(item, dict):
                continue
            destination = str(item.get("destination") or "").strip().lower()
            if destination not in DESTINATION_VALUES:
                destination = "smart"
            rule_type = str(item.get("rule_type") or "").strip().lower()
            if rule_type not in ("client", "web"):
                rule_type = "client"
            rules.append({
                "id": str(item.get("id") or "").strip() or new_rule_id(),
                "name": str(item.get("name") or "").strip() or f"监控规则 {index + 1}",
                "source_ids": self._normalize_ids(item.get("source_ids")),
                "destination": destination,
                "target_id": str(item.get("target_id") or "").strip()[:64],
                "match_only_if_missing": bool(item.get("match_only_if_missing", True)),
                "match_custom_keywords": bool(item.get("match_custom_keywords", False)),
                "custom_keywords": [
                    str(kw).strip()[:64] for kw in (item.get("custom_keywords") or []) if str(kw).strip()
                ],
                "rule_type": rule_type,
                "web_channel_usernames": [
                    str(u).strip().lstrip("@")[:64]
                    for u in (item.get("web_channel_usernames") or []) if str(u).strip()
                ],
                "enabled": bool(item.get("enabled", True)),
            })
        return rules

    @staticmethod
    def _normalize_ids(raw: Any) -> List[int]:
        ids: List[int] = []
        for value in raw or []:
            try:
                number = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if number and number not in ids:
                ids.append(number)
        return ids

    def rules(self) -> List[dict]:
        """归一后的全部规则（带缓存：配置对象不变则复用）。"""
        current = self._config
        cached = self._rules_cache
        if cached is not None and cached[0] is current:
            return cached[1]
        rules = self.normalize_rules(current.get(_RULES_KEY))
        self._rules_cache = (current, rules)
        return rules

    def rules_for_chat(self, chat_id: int) -> List[dict]:
        """监听指定会话的启用规则。"""
        chat = int(chat_id)
        return [rule for rule in self.rules() if rule.get("enabled") and chat in (rule.get("source_ids") or [])]

    def watched_chat_ids(self) -> List[int]:
        """全部被监听的会话 ID（去重）。"""
        seen: List[int] = []
        for rule in self.rules():
            if not rule.get("enabled"):
                continue
            for chat_id in rule.get("source_ids") or []:
                if chat_id not in seen:
                    seen.append(chat_id)
        return seen

    def is_watched(self, chat_id: int) -> bool:
        """该会话是否有启用中的规则监听（TG 事件线程高频调用，必须便宜）。"""
        chat = int(chat_id)
        for rule in self.rules():
            if rule.get("enabled") and chat in (rule.get("source_ids") or []):
                return True
        return False

    def save_rules(self, raw: Any) -> List[dict]:
        """归一并保存规则；返回归一后的列表（前端据此拿到生成的 id）。"""
        rules = self.normalize_rules(raw)
        self._plugin.save_config(**{_RULES_KEY: rules})
        self._rules_cache = None
        # 冷却间隔可能随配置一起被用户调整，顺手刷新
        self.refresh_gate()
        # 首批规则保存后即时进入运行态，不必等插件重载
        self.ensure_started()
        return rules

    # ------------------------------------------------------------------ 流水线

    def _ensure_pipeline(self) -> MessagePipeline:
        if self._pipeline is None:
            self._pipeline = MessagePipeline(self._plugin, self, self._matcher, self._gate)
        return self._pipeline

    def start(self) -> bool:
        """启用监控时启动流水线（幂等）。

        插件整体停用（``get_state()`` 为假）时不启动：宿主停用插件时会走
        ``stop_service``，但配置页仍可能被打开，懒启动不能绕过停用语义。
        """
        if not self.enabled():
            return False
        try:
            if not self._plugin.get_state():
                return False
        except Exception:  # pragma: no cover - 宿主接口缺失时不阻塞启动
            pass
        self.refresh_gate()
        pipeline = self._ensure_pipeline()
        if not pipeline.is_running():
            pipeline.start()
        return True

    def ensure_started(self) -> None:
        """按需启动流水线（去抖 + 临时线程，不阻塞调用方）。

        用户保存规则 / 打开状态页时触发：不必等插件重载，监控即进入运行态。
        与 TG 连接的「打开配置页即自愈」是同一种模式。
        """
        if not self.enabled() or not self.watched_chat_ids():
            return
        if self._pipeline is not None and self._pipeline.is_running():
            return
        now = time.monotonic()
        if now - self._start_attempt_at < 5.0:
            return
        self._start_attempt_at = now
        threading.Thread(target=self._start_quietly, name="tgmc.monitor.start", daemon=True).start()

    def _start_quietly(self) -> None:
        try:
            self.start()
        except Exception as err:  # pragma: no cover - 启动失败不影响接口返回
            logger.warning(f"[TgMediaCenter] 按需启动监控流水线失败：{err}")

    def stop(self) -> None:
        """停止流水线（插件停用 / 重载 / 关闭监控时调用）。"""
        pipeline, self._pipeline = self._pipeline, None
        if pipeline is not None:
            pipeline.stop()

    def refresh_gate(self) -> None:
        """按当前配置刷新 TG 转发全局冷却间隔。"""
        try:
            seconds = int(self._cfg("tg_user_cooldown_seconds", 5) or 5)
        except (TypeError, ValueError):
            seconds = 5
        self._gate.set_interval(max(0, seconds))

    # ------------------------------------------------------------------ 查询

    def hits(self, *, page: int = 1, page_size: int = 20, decision: str = "") -> dict:
        """分页读取命中流水（可按 decision 过滤）。"""
        from sqlalchemy import func, select

        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 20)))
        db = getattr(self._plugin, "get_database", lambda: None)()
        if db is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        plugin_id = getattr(self._plugin, "__class__").__name__
        filters = [TgHitLog.plugin_id == plugin_id]
        if decision:
            filters.append(TgHitLog.decision == str(decision)[:32])
        try:
            with db.session() as session:
                total = session.execute(
                    select(func.count()).select_from(TgHitLog).where(*filters)
                ).scalar() or 0
                rows = session.execute(
                    select(TgHitLog)
                    .where(*filters)
                    .order_by(TgHitLog.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                ).scalars().all()
                items = [self._hit_view(row) for row in rows]
        except Exception as err:  # pragma: no cover - 表未就绪等按空处理
            logger.warning(f"读取命中流水失败：{err}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        return {"items": items, "total": int(total), "page": page, "page_size": page_size}

    @staticmethod
    def _hit_view(row: Any) -> dict:
        created = getattr(row, "created_at", None)
        return {
            "id": int(getattr(row, "id", 0) or 0),
            "rule_id": str(getattr(row, "rule_id", "") or ""),
            "rule_name": str(getattr(row, "rule_name", "") or ""),
            "chat_id": int(getattr(row, "chat_id", 0) or 0),
            "message_id": int(getattr(row, "message_id", 0) or 0),
            "title": str(getattr(row, "title", "") or ""),
            "year": str(getattr(row, "year", "") or ""),
            "season": getattr(row, "season", None),
            "episode": getattr(row, "episode", None),
            "media_type": str(getattr(row, "media_type", "") or ""),
            "decision": str(getattr(row, "decision", "") or ""),
            "destination": str(getattr(row, "destination", "") or ""),
            "detail": str(getattr(row, "detail", "") or ""),
            "created_at": created.isoformat(timespec="seconds") if created else "",
        }

    def push_stats(self) -> dict:
        """推送队列统计。"""
        from sqlalchemy import func, select

        db = getattr(self._plugin, "get_database", lambda: None)()
        if db is None:
            return {"pending": 0, "failed": 0, "done": 0}
        plugin_id = getattr(self._plugin, "__class__").__name__
        try:
            with db.session() as session:
                def _count(status_value: str) -> int:
                    return int(session.execute(
                        select(func.count()).select_from(TgPushTask).where(
                            TgPushTask.plugin_id == plugin_id,
                            TgPushTask.status == status_value,
                        )
                    ).scalar() or 0)

                return {
                    "pending": _count(STATUS_PENDING),
                    "failed": _count(STATUS_FAILED),
                    "done": _count(STATUS_DONE),
                }
        except Exception as err:  # pragma: no cover
            logger.debug(f"统计推送队列失败：{err}")
            return {"pending": 0, "failed": 0, "done": 0}

    def status(self) -> dict:
        """监控模块运行态（供状态接口与前端展示）。"""
        pipeline = self._pipeline
        push = self.push_stats()
        pipeline_stats = pipeline.stats() if pipeline is not None else {
            "running": False,
            "handler_registered": False,
            "buffered": 0,
            "queued": 0,
            "processed": 0,
            "hit": 0,
            "skipped": 0,
            "failed": 0,
            "events_received": 0,
            "events_watched": 0,
            "events_unwatched": 0,
            "messages_enqueued": 0,
            "last_event_at": "",
            "recent_sources": [],
            "watched_detail": [],
            "recent_sources": [],
            "push_done": push["done"],
            "push_pending": push["pending"],
            "push_failed": push["failed"],
            "started_at": "",
            "last_error": "",
        }
        # 推送完成数用数据库口径（跨重启累计），比 worker 内存计数更直观
        pipeline_stats["push_done"] = push["done"]
        return {
            "enabled": self.enabled(),
            "rules_count": len(self.rules()),
            "watched_chats": len(self.watched_chat_ids()),
            "watched_chat_ids": self.watched_chat_ids(),
            "pipeline": pipeline_stats,
            "matcher": self._matcher.capabilities(),
            "gate_interval": self._gate.interval(),
            "flood_remaining": int(self._gate.flood_remaining()),
        }

    # ------------------------------------------------------------------ 规则测试

    def test_text(self, text: str) -> dict:
        """对一段文本预览各规则的处理结果（不落库、不入队、不推送）。"""
        return self._ensure_pipeline().test_text(str(text or ""))

    # ------------------------------------------------------------------ 供前端选项

    @staticmethod
    def decision_options() -> List[dict]:
        """命中流水的决策过滤选项。"""
        labels = {
            "hit": "已推送",
            "skipped_not_missing": "不缺（已存在）",
            "skipped_unrecognized": "无法识别",
            "skipped_keyword": "关键词未命中",
            "skipped_no_link": "无链接",
            "skipped_unknown": "无法判断缺失",
            "failed": "处理失败",
        }
        return [
            {"value": value, "title": labels.get(value, value)} for value in DECISIONS
        ]
