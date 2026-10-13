"""⑥ TG 通用转发模块：规则管理、运行态与规则测试。

职责边界
--------
- 规则存**配置**（``forward_rules``，随配置表单整份保存），本模块负责归一与校验；
- 匹配 / 转换 / 置顶的**纯逻辑**在 ``core/forward.py``；实际执行在消息流水线里
  （转发与监控**共用一条**事件流水线，见 ``core/pipeline.py``——两条流水线各注册
  一次 NewMessage 监听既浪费又容易与宿主事件风暴叠加）；
- 消息流水复用 ``monitor_hit_log``，以 ``kind="forward"`` 区分（前端分栏展示）；
- 转发与监控共用同一把全局冷却门（``tg_user_cooldown_seconds``），避免两套规则
  各持一把冷却，把风控算漏。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core import forward as forward_engine
from ..core import links as link_utils
from ..model.hit_log import (
    DECISION_HIT,
    DECISION_SKIPPED_EXTENSION,
    DECISION_SKIPPED_KEYWORD,
    DECISION_SKIPPED_NOT_SUBSCRIBED,
    DECISION_SKIPPED_UNRECOGNIZED,
    KIND_FORWARD,
)
from ..services import recognizer as recognizer_service
from ..services.matcher import MediaMatcher

_RULES_KEY = "forward_rules"


class ForwardModule:
    """TG 通用转发编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        # 规则归一缓存：插件配置对象不变则复用（TG 事件线程会高频查询）
        self._rules_cache: Optional[tuple] = None

    # ------------------------------------------------------------------ 配置读取

    @property
    def _config(self) -> dict:
        return getattr(self._plugin, "config", {}) or {}

    def _cfg(self, key: str, default: Any = None) -> Any:
        value = self._config.get(key)
        return default if value is None else value

    def enabled(self) -> bool:
        return bool(self._cfg("forward_enabled"))

    def _matcher(self) -> MediaMatcher:
        """复用监控模块的 matcher 实例（共享订阅 / 媒体库 TTL 缓存）。"""
        monitor = getattr(self._plugin, "_monitor", None)
        matcher = getattr(monitor, "_matcher", None) if monitor is not None else None
        return matcher if matcher is not None else MediaMatcher()

    # ------------------------------------------------------------------ 规则归一

    def normalize_rules(self, raw: Any) -> List[dict]:
        """把配置里的原始规则列表归一为后端内部结构。

        - 补稳定 ``id``（**f 前缀**，与监控规则的 r 前缀区分）；
        - ``source_ids`` / ``target_id`` 只保留能转成整数的（TG 会话 ID，含 -100 频道）；
        - ``match_mode`` 只接受 or / and；
        - 未启用的规则不参与匹配，但仍保存（用户可能临时停用某条）。
        """
        rules: List[dict] = []
        for index, item in enumerate(raw or []):
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("id") or "").strip() or forward_engine.new_rule_id()
            if not rule_id.startswith("f"):
                # 老数据 / 手写配置里可能用了 r 前缀或裸 id：统一加 f 前缀防与监控串号
                rule_id = "f" + rule_id.lstrip("rf")
            rules.append({
                "id": rule_id,
                "name": str(item.get("name") or "").strip() or f"转发规则 {index + 1}",
                "source_ids": _normalize_ids(item.get("source_ids")),
                "target_id": _normalize_id(item.get("target_id")),
                "match_subscription_keywords": bool(item.get("match_subscription_keywords", False)),
                "match_custom_keywords": bool(item.get("match_custom_keywords", False)),
                "custom_keywords": _normalize_keywords(item.get("custom_keywords")),
                "match_mode": forward_engine.normalize_match_mode(item.get("match_mode")),
                "pin_links_enabled": bool(item.get("pin_links_enabled", False)),
                "pin_link_keywords": _normalize_keywords(item.get("pin_link_keywords")),
                "match_file_extensions": bool(item.get("match_file_extensions", False)),
                "file_extensions_to_match": _normalize_extensions(item.get("file_extensions_to_match")),
                "enable_transform": bool(item.get("enable_transform", False)),
                "transform_rules": _normalize_lines(item.get("transform_rules")),
                "enabled": bool(item.get("enabled", True)),
            })
        return rules

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
        """该会话是否有启用中的转发规则监听（TG 事件线程高频调用，必须便宜）。"""
        chat = int(chat_id)
        for rule in self.rules():
            if rule.get("enabled") and chat in (rule.get("source_ids") or []):
                return True
        return False

    def save_rules(self, raw: Any) -> List[dict]:
        """归一并保存规则；返回归一后的列表（前端据此拿到生成的 id）。

        保存前逐条校验（缺转发目标 / 启用了过滤却没填内容），任一不通过即整体拒绝——
        这类配置事故会让转发在运行时全军覆没，且原因分散在推送队列里。
        """
        rules = self.normalize_rules(raw)
        for rule in rules:
            problem = forward_engine.validate_rule(rule)
            if problem:
                raise ValueError(problem)
        self._plugin.save_config(**{_RULES_KEY: rules})
        self._rules_cache = None
        # 首批规则保存后即时进入运行态（流水线由监控模块持有，这里触发按需启动）
        self.ensure_pipeline()
        return rules

    def ensure_pipeline(self) -> None:
        """按需启动共用流水线（开关关闭时也照样启动，规则未启用不会匹配）。"""
        monitor = getattr(self._plugin, "_monitor", None)
        schedule = getattr(monitor, "ensure_started", None) if monitor is not None else None
        if not callable(schedule):
            return
        try:
            schedule()
        except Exception as err:  # pragma: no cover - 启动属增强能力
            logger.debug(f"[TgMediaCenter] 按需启动转发流水线失败：{err}")

    # ------------------------------------------------------------------ 规则测试

    def test_text(self, text: str) -> dict:
        """预览各转发规则对一段文本的处理（不落库、不入队、不推送）。

        自己算而不走流水线：转发规则可能在监控未启动时就要能测（两条路径
        共用同一份识别 / 订阅判断，口径一致）。
        """
        raw = str(text or "")
        cleaned = recognizer_service.purify_text(raw)
        meta = recognizer_service.recognize(raw)
        parsed = link_utils.parse_push_text(raw)
        links = [item.raw or item.url for item in parsed.items if item.supported]
        title = str((meta or {}).get("title") or "")
        year = str((meta or {}).get("year") or "")
        season = (meta or {}).get("season")
        matcher = self._matcher()

        traces: List[dict] = []
        for rule in self.rules():
            trace: Dict[str, Any] = {
                "rule_id": str(rule.get("id") or ""),
                "rule_name": str(rule.get("name") or ""),
                "target_id": rule.get("target_id") or 0,
                "enabled": bool(rule.get("enabled", True)),
                "matched": False,
                "decision": "",
                "reason": "",
                "send_text": "",
                "pin": False,
            }
            subscribed: Optional[bool] = None
            if rule.get("match_subscription_keywords"):
                try:
                    subscribed = matcher.is_subscribed(title=title, year=year, season=season)
                except Exception as err:  # pragma: no cover - 订阅探测异常按无法判断
                    logger.debug(f"转发规则测试：订阅判断失败：{err}")
                    subscribed = None
            verdict = forward_engine.match_rule(
                rule,
                text=raw,
                cleaned=cleaned,
                title=title,
                year=year,
                season=season,
                is_subscribed=subscribed,
                links=links,
            )
            if not verdict.get("matched"):
                trace.update(decision=forward_engine.skip_decision(verdict),
                             reason=verdict.get("reason") or "未命中")
                traces.append(trace)
                continue
            send_text = raw
            if rule.get("enable_transform"):
                outcome = forward_engine.apply_transform(raw, rule.get("transform_rules"))
                send_text = outcome["text"]
                if outcome["errors"]:
                    trace["reason"] = "；".join(outcome["errors"])
            trace.update(
                matched=True,
                decision=DECISION_HIT,
                reason="会转发到目标会话",
                send_text=send_text,
                pin=forward_engine.should_pin(rule, text=raw, links=links),
            )
            traces.append(trace)

        return {
            "purified": cleaned,
            "recognized": meta,
            "links": links,
            "rules": traces,
        }

    # ------------------------------------------------------------------ 查询与状态

    def hits(self, *, page: int = 1, page_size: int = 20, decision: str = "") -> dict:
        """分页读取转发流水（复用监控模块的流水实现，按 kind=forward 过滤）。"""
        monitor = getattr(self._plugin, "_monitor", None)
        if monitor is None:
            return {"items": [], "total": 0, "page": max(1, int(page or 1)), "page_size": int(page_size or 20)}
        return monitor.hits(page=page, page_size=page_size, decision=decision, kind=KIND_FORWARD)

    def status(self) -> dict:
        """转发模块运行态（供状态接口与前端展示）。"""
        interval = 0
        flood = 0
        monitor = getattr(self._plugin, "_monitor", None)
        gate = getattr(monitor, "_gate", None) if monitor is not None else None
        if gate is not None:
            try:
                interval = int(gate.interval())
                flood = int(gate.flood_remaining())
            except Exception:  # pragma: no cover - 展示字段失败不影响主体
                interval, flood = 0, 0
        capabilities: Dict[str, Any] = {}
        try:
            capabilities = self._matcher().capabilities()
        except Exception as err:  # pragma: no cover
            logger.debug(f"读取转发模块判断能力失败：{err}")
        rules = self.rules()
        return {
            "enabled": self.enabled(),
            "rules_count": len(rules),
            "watched_chats": len(self.watched_chat_ids()),
            "watched_chat_ids": self.watched_chat_ids(),
            "transform_rules_count": sum(len(rule.get("transform_rules") or []) for rule in rules),
            "gate_interval": interval,
            "flood_remaining": flood,
            "subscriptions": int(capabilities.get("subscriptions") or 0),
            "queries_available": bool(capabilities.get("queries_available")),
        }

    @staticmethod
    def decision_options() -> List[dict]:
        """转发流水的决策过滤选项。"""
        labels = {
            DECISION_HIT: "已转发",
            DECISION_SKIPPED_KEYWORD: "关键词未命中",
            DECISION_SKIPPED_NOT_SUBSCRIBED: "未订阅",
            DECISION_SKIPPED_EXTENSION: "扩展名未命中",
            DECISION_SKIPPED_UNRECOGNIZED: "无法识别",
        }
        return [{"value": value, "title": title} for value, title in labels.items()]


# ---------------------------------------------------------------------- 归一助手


def _normalize_ids(raw: Any) -> List[int]:
    ids: List[int] = []
    for value in raw or []:
        number = _normalize_id(value)
        if number and number not in ids:
            ids.append(number)
    return ids


def _normalize_id(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _normalize_keywords(raw: Any) -> List[str]:
    return [str(item).strip()[:64] for item in (raw or []) if str(item).strip()]


def _normalize_extensions(raw: Any) -> List[str]:
    exts: List[str] = []
    for item in raw or []:
        ext = str(item).strip().lstrip(".").lower()[:16]
        if ext and ext not in exts:
            exts.append(ext)
    return exts


def _normalize_lines(raw: Any) -> List[str]:
    return [str(item).strip()[:200] for item in (raw or []) if str(item).strip()]
