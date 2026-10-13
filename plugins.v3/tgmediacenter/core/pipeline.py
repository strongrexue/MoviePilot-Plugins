"""④ TG 资源监控：消息流水线。

```
Telethon 新消息事件（TG loop 线程，只入队不处理）
  ▼ 线程安全队列
聚合窗口缓冲（同频道 N 秒内的批量消息合并，降低 FloodWait 概率）
  ▼ worker 线程
净化（去广告行）→ 宿主识别（MetaVideo）→ 规则匹配（关键词 / 仅缺集）
  ▼
命中流水落库（hit_log，同规则同消息去重）＋ 推送任务入队（push_task）
  ▼ worker 周期扫描
推送 worker：按 destination 分派（115 / TG 转发 / 仅记录），失败指数退避重试
```

线程模型
--------
- **TG loop 线程**：事件处理器只做「是否被监控 + 入队」，绝不做重活；
- **worker 线程**：聚合、识别、匹配、落库、推送全在这里，宿主同步 API
  （媒体服务器 / 订阅查询 / 115 HTTP）都不会阻塞 TG 连接；
- **健康检查**：worker 每轮检查事件处理器是否还注册在当前客户端上
  （运行时可能因掉线重建，处理器会丢），丢了就重新注册。
"""
from __future__ import annotations

import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core import forward as forward_engine
from ..core import links as link_utils
from ..core import push_queue
from ..core.cooldown import CooldownGate, report_flood_wait
from ..core.notify import Notifier
from ..destinations import resolve_destination
from ..model.push_task import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    TgPushTask,
)
from ..model.hit_log import (
    DECISION_FAILED,
    DECISION_HIT,
    DECISION_SKIPPED_KEYWORD,
    DECISION_SKIPPED_NOT_MISSING,
    DECISION_SKIPPED_NOT_SUBSCRIBED,
    DECISION_SKIPPED_NO_LINK,
    DECISION_SKIPPED_UNKNOWN,
    DECISION_SKIPPED_UNRECOGNIZED,
    KIND_FORWARD,
    KIND_MONITOR,
    TgHitLog,
)
from ..services import recognizer as recognizer_service

# 单频道批量消息条数上限：超过即无视聚合窗口立即处理（防大频道刷爆缓冲）
_MAX_BATCH = 20
# 「最近消息来源」环形记录上限：只记录被监听会话（状态卡「来源 ID」行）
_MAX_RECENT_SOURCES = 40
# 推送 worker 扫描周期（秒）
_PUSH_INTERVAL = 15.0
# 合并下发：同一目标的多条待推送任务合成一次调用，单次链接数上限。
# 逐条调用会让每条链接都走一遍"新建客户端 + 风控间隔"——一次回搜 34 条链接
# 就是 34 次调用、拖上一分钟，还更容易触发 115 风控（1.4.4 真机观察到的
# 连续 16 行"已完成第 1/1 批"）。上限同时也避开 115 模块的单次条目上限。
_PUSH_GROUP_MAX_LINKS = 20
# 失败重试基础退避（秒）：30 * 2^retries，上限 600
_RETRY_BASE_SECONDS = 30.0
_RETRY_MAX_SECONDS = 600.0
# 115 登录态失效的提醒间隔（秒）：属"要人工介入且会持续存在"的故障，
# 不按轮次重复提醒，6 小时内只发一次。
_CREDENTIAL_NOTIFY_WINDOW = 6 * 3600.0
# 判定"这是登录态/鉴权问题"的关键词（115 侧文案不完全固定，按语义兜）
_AUTH_ERROR_HINTS = ("登录", "cookie", "授权", "安全密钥", "验证", "未启用", "失效", "401", "403")


def _looks_like_auth_error(message: str) -> bool:
    """这条失败信息是否像 115 登录态失效（用于给通知加"重新扫码"引导）。"""
    text = str(message or "").lower()
    return any(hint in text for hint in _AUTH_ERROR_HINTS)


def _task_links(task: Dict[str, Any]) -> List[str]:
    """取任务负载里的链接列表。"""
    payload = task.get("payload")
    if not isinstance(payload, dict):
        return []
    return [str(link) for link in (payload.get("links") or []) if str(link).strip()]


def _link_outcomes(detail: Any) -> Dict[str, Dict[str, Any]]:
    """把目标的逐条结果整理成 ``{输入链接: {"ok": bool}}``（合并下发回填用）。

    同一输入链接可能被解析出多条条目（一段正文含多个链接）：任一条失败即视为失败。
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not isinstance(detail, dict):
        return result
    for entry in detail.get("results") or []:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "").strip()
        if not source:
            continue
        slot = result.setdefault(source, {"ok": True})
        if not entry.get("ok"):
            slot["ok"] = False
    return result


def _decision_for_skip(verdict: dict) -> "tuple[str, str]":
    """把"缺失判断未命中"的 verdict 归一为（决策常量, 人类可读原因）。

    - 无法判断缺失 → skipped_unknown
    - 未订阅（方案 A 门禁）→ skipped_not_subscribed
    - 其余（订阅已齐全 / 媒体库已存在）→ skipped_not_missing
    """
    if verdict.get("missing") is None:
        return DECISION_SKIPPED_UNKNOWN, verdict.get("reason") or "无法判断缺失"
    if verdict.get("reason") == "未订阅":
        return DECISION_SKIPPED_NOT_SUBSCRIBED, verdict.get("reason")
    return DECISION_SKIPPED_NOT_MISSING, verdict.get("reason") or "媒体库已存在"


class MessagePipeline:
    """监控消息流水线（事件接入 + 聚合 + 识别 + 决策 + 推送队列）。"""

    def __init__(self, plugin: Any, monitor: Any, matcher: Any, gate: Optional[CooldownGate] = None) -> None:
        self._plugin = plugin
        self._monitor = monitor
        self._matcher = matcher
        self._gate = gate or CooldownGate(5.0)

        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._buffers: Dict[int, Dict[str, Any]] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._handler = None
        self._handler_ok = False
        self._last_push_cycle = 0.0
        # P7：通知（成功汇总 / 故障），按轮次聚合后在 _push_cycle 末尾统一发出
        self._notifier = Notifier(plugin)
        self._cycle: Dict[str, Any] = self._empty_cycle()
        self._started_at = ""
        self._last_error = ""
        self._last_event_at = ""
        self._stats = {
            "processed": 0,
            "hit": 0,
            "skipped": 0,
            "failed": 0,
            # 事件可观测性计数：用于诊断"监听是否真的在收消息"
            "events_received": 0,   # 事件处理器被触发（任何新消息，含非监听会话）
            "events_watched": 0,    # 命中监听会话的条数
            "events_unwatched": 0,  # 非关心会话被丢弃的条数
            "messages_enqueued": 0, # 进入流水线处理的条数
            "cache_written": 0,     # 写入消息缓存的条数（P5）
        }
        # 最近消息来源（只记被监听会话）：chat_id -> {"count", "last_at", "_mono"}
        self._recent_sources: Dict[int, Dict[str, Any]] = {}
        # 监听会话反查结果：[{"chat_id", "title", "resolved", "error"}]
        self._watched_detail: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ 生命周期

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> bool:
        """启动 worker 线程（幂等）。"""
        if self.is_running():
            return True
        self._stop.clear()
        self._started_at = datetime.now().isoformat(timespec="seconds")
        self._thread = threading.Thread(target=self._run, name="tgmc.monitor", daemon=True)
        self._thread.start()
        logger.info(f"[{self._plugin_id()}] 监控流水线已启动")
        return True

    def stop(self) -> None:
        """停止 worker 并注销事件处理器（幂等）。"""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=8)
        self._unregister_handler()
        logger.info(f"[{self._plugin_id()}] 监控流水线已停止")

    def _plugin_id(self) -> str:
        return getattr(self._plugin, "__class__").__name__ or "TgMediaCenter"

    # ------------------------------------------------------------------ 事件入口

    def on_new_message(self, chat_id: int, message_id: int, text: str) -> None:
        """TG 新消息入口（事件处理器调用，必须极快且不抛异常）。"""
        self._stats["messages_enqueued"] += 1
        self._queue.put({
            "chat_id": int(chat_id),
            "message_id": int(message_id),
            "text": str(text or ""),
        })

    def _handle_event(self, event: Any) -> None:
        """Telethon 事件处理器（运行在 TG loop 线程）。

        关心会话 = 监控频道 ∪ 缓存频道：只有这两个集合的消息才进流水线，
        其余完全静默（仅计数），避免大流量频道把运行日志刷成噪音。
        """
        try:
            chat_id = getattr(event, "chat_id", None)
            if chat_id is None:
                return
            self._stats["events_received"] += 1
            purposes = self._purposes(int(chat_id))
            if not purposes:
                self._stats["events_unwatched"] += 1
                return
            self._stats["events_watched"] += 1
            self._record_source(int(chat_id))
            self._last_event_at = datetime.now().isoformat(timespec="seconds")
            message = getattr(event, "message", None)
            message_id = int(getattr(message, "id", 0) or 0)
            text = str(getattr(event, "raw_text", "") or "")
            label = "+".join(purposes) or "关心"
            logger.info(
                f"[{self._plugin_id()}] [{label}] 会话 {chat_id} 新消息 #{message_id}"
                f"（{len(text)} 字），进入处理流水线"
            )
            self.on_new_message(int(chat_id), message_id, text)
        except Exception as err:  # pragma: no cover - 事件解析异常不能影响 TG 连接
            logger.debug(f"处理 TG 新消息事件失败（忽略）：{err}")

    # ------------------------------------------------------------------ 关心会话

    def _cache_module(self):
        """缓存模块（P5 起）；未接线时返回 None。"""
        return getattr(self._plugin, "_cache", None)

    def _forward_module(self):
        """转发模块（P6 起）；未接线时返回 None。"""
        return getattr(self._plugin, "_forward", None)

    def _forward_watched(self, chat_id: int) -> bool:
        """该会话是否有启用中的转发规则监听。"""
        module = self._forward_module()
        if module is None:
            return False
        try:
            return bool(module.is_watched(int(chat_id)))
        except Exception:  # pragma: no cover - 转发模块异常不影响监控
            return False

    def _forward_rules_for_chat(self, chat_id: int) -> List[dict]:
        """监听该会话的启用转发规则。"""
        module = self._forward_module()
        if module is None:
            return []
        try:
            return list(module.rules_for_chat(int(chat_id)))
        except Exception:  # pragma: no cover
            return []

    def _cached_chat(self, chat_id: int) -> bool:
        module = self._cache_module()
        if module is None:
            return False
        try:
            return bool(module.is_cached_chat(int(chat_id)))
        except Exception:  # pragma: no cover - 缓存模块异常不影响监控
            return False

    def _purposes(self, chat_id: int) -> List[str]:
        """该会话被关心的用途：监控 / 转发 / 缓存（可叠加）。"""
        try:
            watched = bool(self._monitor.is_watched(int(chat_id)))
        except Exception:  # pragma: no cover
            watched = False
        purposes: List[str] = []
        if watched:
            purposes.append("监控")
        if self._forward_watched(chat_id):
            purposes.append("转发")
        if self._cached_chat(chat_id):
            purposes.append("缓存")
        return purposes

    def _interested_chat_ids(self) -> List[int]:
        """关心会话 ID 清单（监控 ∪ 转发 ∪ 缓存，去重）。"""
        ids: List[int] = []
        try:
            for chat_id in self._monitor.watched_chat_ids():
                if int(chat_id) not in ids:
                    ids.append(int(chat_id))
        except Exception:  # pragma: no cover
            pass
        module = self._forward_module()
        if module is not None:
            try:
                for chat_id in module.watched_chat_ids():
                    if int(chat_id) not in ids:
                        ids.append(int(chat_id))
            except Exception:  # pragma: no cover
                pass
        module = self._cache_module()
        if module is not None:
            try:
                for chat_id in module.chat_ids():
                    if int(chat_id) not in ids:
                        ids.append(int(chat_id))
            except Exception:  # pragma: no cover
                pass
        return ids

    def _record_source(self, chat_id: int) -> None:
        """记录最近消息来源（TG 线程内只做字典自增，足够便宜）。"""
        record = self._recent_sources.get(chat_id)
        now_iso = datetime.now().isoformat(timespec="seconds")
        if record is None:
            if len(self._recent_sources) >= _MAX_RECENT_SOURCES:
                # 淘汰最久未活跃的来源，避免无限增长
                oldest = min(self._recent_sources, key=lambda cid: self._recent_sources[cid]["_mono"])
                self._recent_sources.pop(oldest, None)
            self._recent_sources[chat_id] = {"count": 1, "last_at": now_iso, "_mono": time.monotonic()}
        else:
            record["count"] += 1
            record["last_at"] = now_iso
            record["_mono"] = time.monotonic()

    # ------------------------------------------------------------------ worker 主循环

    def _run(self) -> None:
        self._register_handler()
        while not self._stop.is_set():
            try:
                self._drain_queue()
                self._flush_batches()
                self._push_cycle()
                self._ensure_handler()
            except Exception as err:  # pragma: no cover - 单轮异常不中断 worker
                self._last_error = str(err)
                logger.warning(f"[{self._plugin_id()}] 监控流水线本轮异常：{err}")
            self._stop.wait(0.5)
        self._unregister_handler()

    def _drain_queue(self) -> None:
        """把队列里的原始消息并入聚合缓冲。"""
        pending: List[Dict[str, Any]] = []
        while True:
            try:
                pending.append(self._queue.get_nowait())
            except queue.Empty:
                break
        for item in pending:
            chat_id = item["chat_id"]
            buffer = self._buffers.get(chat_id)
            if buffer is None:
                buffer = {"first_at": time.monotonic(), "messages": []}
                self._buffers[chat_id] = buffer
            buffer["messages"].append(item)

    def _window_seconds(self) -> float:
        """聚合窗口（配置 tg_aggregation_window_seconds，收敛到 1~30 秒）。"""
        try:
            value = float(self._monitor.config_value("tg_aggregation_window_seconds", 3.0) or 3.0)
        except (TypeError, ValueError):
            value = 3.0
        return min(30.0, max(1.0, value))

    def _flush_batches(self) -> None:
        """处理窗口已到（或批量已满）的缓冲。"""
        now = time.monotonic()
        window = self._window_seconds()
        ready = [
            chat_id for chat_id, buffer in self._buffers.items()
            if now - buffer["first_at"] >= window or len(buffer["messages"]) >= _MAX_BATCH
        ]
        for chat_id in ready:
            buffer = self._buffers.pop(chat_id)
            self._process_batch(chat_id, buffer["messages"])

    # ------------------------------------------------------------------ 批处理

    def _process_batch(self, chat_id: int, messages: List[Dict[str, Any]]) -> None:
        # 只有缓存、没有监控 / 转发规则的频道也要处理（缓存是独立的下游）
        rules = self._monitor.rules_for_chat(chat_id)
        forward_rules = self._forward_rules_for_chat(chat_id)
        if not rules and not forward_rules and not self._cached_chat(chat_id):
            return
        for message in messages:
            try:
                self._process_message(chat_id, message, rules, forward_rules)
            except Exception as err:  # pragma: no cover - 单条异常不中断整批
                self._stats["failed"] += 1
                self._last_error = str(err)
                logger.warning(f"[{self._plugin_id()}] 处理监控消息失败（chat={chat_id}）：{err}")
        self._stats["processed"] += len(messages)
        # 每批打一条 INFO，让"消息确实被处理了"在运行日志里可见（排查静默丢弃的关键）
        logger.info(
            f"[{self._plugin_id()}] 收到 {len(messages)} 条消息（chat={chat_id}），"
            f"累计处理 {self._stats['processed']} / 监控命中 {self._stats['hit']}"
            f" / 转发命中 {self._stats.get('forward_hit', 0)}"
        )

    def _process_message(self, chat_id: int, message: Dict[str, Any], rules: List[dict],
                         forward_rules: Optional[List[dict]] = None) -> None:
        text = str(message.get("text") or "")
        if not text.strip():
            return
        message_id = int(message.get("message_id") or 0)
        cleaned = recognizer_service.purify_text(text)
        meta = self._recognizer().recognize(text)
        parsed = link_utils.parse_push_text(text)
        links = [item.raw or item.url for item in parsed.items if item.supported]

        # 缓存写入（与该频道是否有监控 / 转发规则无关）
        if self._cached_chat(chat_id):
            self._record_cache(chat_id, message_id, text, cleaned=cleaned, meta=meta, links=links)

        if not rules and not forward_rules:
            return
        for rule in rules or []:
            self._apply_rule(chat_id=chat_id, message_id=message_id, text=text,
                             cleaned=cleaned, meta=meta, links=links, rule=rule)
        for rule in forward_rules or []:
            self._apply_forward_rule(chat_id=chat_id, message_id=message_id, text=text,
                                     cleaned=cleaned, meta=meta, links=links, rule=rule)

    def _record_cache(self, chat_id: int, message_id: int, text: str, *,
                      cleaned: Optional[str], meta: Optional[dict], links: List[str]) -> None:
        """写入历史消息缓存（复用已算好的净化与识别结果，不重复识别）。"""
        module = self._cache_module()
        if module is None:
            return
        try:
            inserted = module.record(chat_id, message_id, text,
                                     cleaned=cleaned, meta=meta, links=links)
            if inserted:
                self._stats["cache_written"] = self._stats.get("cache_written", 0) + 1
        except Exception as err:  # pragma: no cover - 缓存写入失败不影响监控
            logger.debug(f"写入消息缓存失败（chat={chat_id}, msg={message_id}）：{err}")

    def _apply_rule(self, *, chat_id: int, message_id: int, text: str, cleaned: str,
                    meta: Optional[dict], links: List[str], rule: dict) -> None:
        rule_id = str(rule.get("id") or "")
        rule_name = str(rule.get("name") or "")
        destination = str(rule.get("destination") or "smart")

        # 同规则同消息只处理一次（插件重载 / 事件重放时防重复推送）。
        # 注意：不能再插一条 skipped_duplicate 流水——去重唯一键与首条流水冲突，
        # 插入必被拒；首条流水本身就是该消息的处理记录，这里只计统计。
        if self._hit_exists(rule_id, chat_id, message_id):
            self._stats["skipped"] += 1
            logger.debug(
                f"[{self._plugin_id()}] 重复消息跳过（rule={rule_id}, chat={chat_id}, msg={message_id}）"
            )
            return

        # 逻辑一：自定义关键词（OR）
        if rule.get("match_custom_keywords"):
            keywords = [str(kw) for kw in (rule.get("custom_keywords") or []) if str(kw).strip()]
            if keywords and not any(keyword in cleaned for keyword in keywords):
                self._record(rule, chat_id, message_id, meta, DECISION_SKIPPED_KEYWORD,
                             "自定义关键词未命中", destination, links)
                return

        # 仅缺失判断（依据 MP 媒体服务器 + 订阅快照）。
        # 标题识别只在需要判断缺失时是硬性要求：仅缺失关闭时，纯链接消息
        # 也应能按规则推送（推送 115 只需要链接，不需要标题）。
        if rule.get("match_only_if_missing"):
            if meta is None:
                reason = ("宿主识别引擎不可用（请确认 MoviePilot 版本）"
                          if not recognizer_service.meta_available() else "标题无法识别，无法判断缺失")
                self._record(rule, chat_id, message_id, meta, DECISION_SKIPPED_UNRECOGNIZED,
                             reason, destination, links)
                return
            verdict = self._matcher.is_missing(
                title=meta.get("title") or "",
                year=meta.get("year") or "",
                media_type=meta.get("media_type") or "",
                season=meta.get("season"),
                episode=meta.get("episode"),
                episode_end=meta.get("episode_end"),
                # 方案 A 订阅门禁：仅缺失开启时，未订阅的资源直接跳过，
                # 不再误标成"媒体库已存在"（订阅数据源可用时生效）。
                require_subscription=True,
            )
            if verdict.get("missing") is None or not verdict.get("missing"):
                decision, reason = _decision_for_skip(verdict)
                self._record(rule, chat_id, message_id, meta, decision, reason, destination, links)
                return

        # 115 类目标必须拿到可推送的链接；TG 转发 / 仅记录不需要
        if destination in ("smart", "pan115") and not links:
            self._record(rule, chat_id, message_id, meta, DECISION_SKIPPED_NO_LINK,
                         "消息中没有可推送的链接（115 分享 / 磁力 / eD2k）", destination, links)
            return

        task_id = self._enqueue_push(rule=rule, chat_id=chat_id, message_id=message_id,
                                     text=text, links=links, destination=destination,
                                     title=self._media_label(meta))
        if task_id:
            self._record(rule, chat_id, message_id, meta, DECISION_HIT,
                         f"已入推送队列 #{task_id}", destination, links)
            self._stats["hit"] += 1
        else:
            self._record(rule, chat_id, message_id, meta, DECISION_FAILED,
                         "推送任务入队失败（请查看运行日志）", destination, links)
            self._stats["failed"] += 1

    # ------------------------------------------------------------------ 转发规则（⑥）

    def _apply_forward_rule(self, *, chat_id: int, message_id: int, text: str, cleaned: str,
                            meta: Optional[dict], links: List[str], rule: dict) -> None:
        """⑥ 通用转发：两级匹配 → 内容转换 → 入转发队列（可选置顶）。

        转发与订阅彻底解耦（1.5.1）：只按关键词（逻辑一）与扩展名（逻辑二）匹配，
        不查宿主订阅、不要求识别成功——不认标题的播报与普通聊天也能按规则转发。
        """
        rule_id = str(rule.get("id") or "")
        rule_name = str(rule.get("name") or "")
        destination = "tg_forward"

        # 同规则同消息只处理一次（插件重载 / 事件重放时防重复转发）。
        # 转发规则 id 用 f 前缀，与监控规则的 r 前缀不冲突，去重键不会串。
        if self._hit_exists(rule_id, chat_id, message_id):
            self._stats["skipped"] += 1
            logger.debug(
                f"[{self._plugin_id()}] 重复消息跳过（转发规则={rule_id}, chat={chat_id}, msg={message_id}）"
            )
            return

        verdict = forward_engine.match_rule(rule, text=text, cleaned=cleaned, links=links)
        if not verdict.get("matched"):
            self._record(rule, chat_id, message_id, meta,
                         forward_engine.skip_decision(verdict),
                         verdict.get("reason") or "未命中", destination, links, kind=KIND_FORWARD)
            return

        forward_meta: Dict[str, Any] = {}
        if rule.get("enable_transform"):
            outcome = forward_engine.apply_transform(text, rule.get("transform_rules"))
            forward_meta["transform"] = True
            forward_meta["send_text"] = str(outcome.get("text") or "")[:4000]
            if outcome.get("errors"):
                logger.warning(
                    f"[{self._plugin_id()}] 转发规则「{rule_name}」的转换规则有问题："
                    + "；".join(outcome["errors"])
                )
        pinned = forward_engine.should_pin(rule, text=text, links=links)
        if pinned:
            forward_meta["pin"] = True
        extra = {"forward": forward_meta} if forward_meta else None

        task_id = self._enqueue_push(rule=rule, chat_id=chat_id, message_id=message_id,
                                     text=text, links=links, destination=destination,
                                     title=self._media_label(meta), extra=extra)
        if task_id:
            notes = []
            if forward_meta.get("transform"):
                notes.append("转换后发送")
            if pinned:
                notes.append("含置顶")
            suffix = f"（{'、'.join(notes)}）" if notes else ""
            self._record(rule, chat_id, message_id, meta, DECISION_HIT,
                         f"已入转发队列 #{task_id}{suffix}", destination, links, kind=KIND_FORWARD)
            self._stats["forward_hit"] = self._stats.get("forward_hit", 0) + 1
        else:
            self._record(rule, chat_id, message_id, meta, DECISION_FAILED,
                         "转发任务入队失败（请查看运行日志）", destination, links, kind=KIND_FORWARD)
            self._stats["failed"] += 1

    # ------------------------------------------------------------------ 落库

    def _db(self):
        return getattr(self._plugin, "get_database", lambda: None)()

    def _record(self, rule: dict, chat_id: int, message_id: int, meta: Optional[dict],
                decision: str, detail: str, destination: str, links: List[str],
                kind: str = KIND_MONITOR) -> None:
        """写命中流水（去重键冲突时静默跳过，说明已处理过）。

        ``kind`` 区分来源（监控 / 转发）—— 两套规则共用一张表，靠它分栏。
        """
        # 决策过程直接落运行日志：用户在 MP 日志页能看到每条消息怎么被判的
        prefix = "转发" if kind == KIND_FORWARD else ""
        logger.info(
            f"[{self._plugin_id()}] {prefix}决策（chat={chat_id}, msg={message_id}, "
            f"规则「{rule.get('name') or rule.get('id')}」）：{decision} —— {detail}"
        )
        db = self._db()
        if db is None:
            return
        try:
            with db.session() as session:
                session.add(TgHitLog(
                    plugin_id=self._plugin_id(),
                    kind=str(kind)[:16],
                    rule_id=str(rule.get("id") or "")[:64],
                    rule_name=str(rule.get("name") or "")[:128],
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    title=str((meta or {}).get("title") or "")[:250],
                    year=str((meta or {}).get("year") or "")[:16],
                    season=(meta or {}).get("season"),
                    episode=(meta or {}).get("episode"),
                    episode_end=(meta or {}).get("episode_end"),
                    media_type=str((meta or {}).get("media_type") or "")[:16],
                    decision=str(decision)[:32],
                    destination=str(destination or "")[:32],
                    target_id=str(rule.get("target_id") or "")[:64],
                    detail=str(detail or "")[:500],
                ))
                session.commit()
            if str(decision).startswith("skipped"):
                self._stats["skipped"] += 1
        except Exception as err:
            # 去重键冲突属于正常竞态；其余异常只记录，不中断流水线
            logger.debug(f"写命中流水失败（{decision}）：{err}")

    def _hit_exists(self, rule_id: str, chat_id: int, message_id: int) -> bool:
        """同规则同消息是否已处理过。"""
        db = self._db()
        if db is None:
            return False
        try:
            from sqlalchemy import select

            with db.session() as session:
                row = session.execute(
                    select(TgHitLog.id).where(
                        TgHitLog.plugin_id == self._plugin_id(),
                        TgHitLog.rule_id == str(rule_id or "")[:64],
                        TgHitLog.chat_id == int(chat_id),
                        TgHitLog.message_id == int(message_id),
                    )
                ).first()
                return row is not None
        except Exception as err:  # pragma: no cover - 查询失败按未处理（宁可重复也不漏推）
            logger.debug(f"查询命中流水失败：{err}")
            return False

    def _enqueue_push(self, *, rule: dict, chat_id: int, message_id: int, text: str,
                      links: List[str], destination: str,
                      title: str = "",
                      extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """入队推送任务，返回任务 ID（监控 / 转发 / 缓存回搜共用同一入队实现）。

        ``title`` 取自识别结果，用于通知里直接显示片名（而非退化为「消息 #ID」）。
        """
        return push_queue.enqueue_push(
            self._db(),
            self._plugin_id(),
            rule_id=str(rule.get("id") or ""),
            chat_id=chat_id,
            message_id=message_id,
            destination=destination,
            target_id=str(rule.get("target_id") or ""),
            links=links,
            text=text,
            title=title,
            extra=extra,
        )

    @staticmethod
    def _media_label(meta: Optional[dict]) -> str:
        """把识别结果拼成通知 / 流水用的简报文案，如「美人余 (2026) S01E01-E11」。"""
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

    # ------------------------------------------------------------------ 推送 worker

    def _push_cycle(self) -> None:
        now = time.monotonic()
        if now - self._last_push_cycle < _PUSH_INTERVAL:
            return
        self._last_push_cycle = now
        self._cycle = self._empty_cycle()
        for group in self._group_tasks(self._claim_pending_tasks()):
            if len(group) == 1:
                self._execute_push(group[0])
            else:
                self._execute_push_group(group)
        # 通知按轮次聚合：一批推送完只发一条汇总，避免逐条刷屏
        self._flush_notifications()

    @staticmethod
    def _empty_cycle() -> Dict[str, Any]:
        """本轮推送结果桶（只记 115 转存；通用转发不发通知）。"""
        return {"pan115_done": [], "pan115_failed": []}

    @staticmethod
    def _task_label(task: Dict[str, Any]) -> str:
        """任务的简报（通知里用）：优先片名，其次消息 ID。"""
        payload = task.get("payload") or {}
        title = str(payload.get("title") or "").strip()
        links = len(_task_links(task))
        if title:
            return f"{title}（{links} 条链接）"
        return f"消息 #{task.get('message_id')}（{links} 条链接）"

    def _note_outcome(self, *, task: Dict[str, Any], via: str, outcome: str, message: str) -> None:
        """把 115 转存的推送终态记进本轮通知桶（重试挂起的不算）。

        通知只覆盖 115 转存（用户明确要求）：通用转发（tg_forward）的成败
        不进通知桶，转发结果去详情页 / 转发面板看。
        """
        if outcome not in ("done", "failed"):
            return
        if str(via or "").strip().lower() != "pan115":
            return
        links = _task_links(task)
        if outcome == "done":
            self._cycle["pan115_done"].append((self._task_label(task), links))
            return
        self._cycle["pan115_failed"].append((self._task_label(task), str(message or "")))

    def _flush_notifications(self) -> None:
        """本轮 115 转存结束后发汇总通知（成功 / 失败各一条，开关可关）。"""
        cycle = self._cycle or {}
        done = list(cycle.get("pan115_done") or [])
        failed_115 = list(cycle.get("pan115_failed") or [])

        if done and self._notifier.enabled("notify_on_hit", True):
            lines: List[str] = []
            for label, links in done[:8]:
                lines.append(f"· {label}")
                for url in links[:3]:
                    lines.append(f"  {url}")
            text = "已转存到 115（" + str(len(done)) + " 条）：\n" + "\n".join(lines)
            if len(done) > 8:
                text += f"\n…另有 {len(done) - 8} 条"
            self._notifier.send(f"TG媒体中心 · 115 转存完成（{len(done)} 条）", text)

        total = len(failed_115)
        if total and self._notifier.enabled("notify_on_error", True):
            credential_issue = any(_looks_like_auth_error(msg) for _, msg in failed_115)
            lines: List[str] = [
                f"115 转存失败 {total} 条：",
            ]
            lines += [f"· {label} —— {msg}" for label, msg in failed_115[:6]]
            shown = min(total, 6)
            if total > shown:
                lines.append(f"…另有 {total - shown} 条")
            if credential_issue:
                lines.append("看起来是 115 登录态失效：请到「115 网盘」面板重新扫码登录，之后重推即可。")
            self._notifier.send(
                f"TG媒体中心 · 115 转存失败（{total} 条）",
                "\n".join(lines),
                # 登录态失效属"需要人工介入且会长时间持续"的故障：6 小时内只提醒一次
                key="pan115_credential" if credential_issue else "",
                window=_CREDENTIAL_NOTIFY_WINDOW,
            )

    def _group_tasks(self, tasks: List[Dict[str, Any]]) -> "List[List[Dict[str, Any]]]":
        """把可合并的任务分组（保持原顺序）。

        合并条件：同一 destination + target_id，目标声明 ``supports_batch``，
        且累计链接数不超过 ``_PUSH_GROUP_MAX_LINKS``。不满足的一律各自成组
        （走原来的单任务路径）。
        """
        groups: List[List[Dict[str, Any]]] = []
        opened: Dict[str, List[Dict[str, Any]]] = {}
        counts: Dict[str, int] = {}
        for task in tasks:
            destination = str(task.get("destination") or "smart")
            links = _task_links(task)
            if len(links) < 1 or not self._supports_batch(destination, task):
                groups.append([task])
                continue
            key = f"{destination}|{task.get('target_id') or ''}"
            current = opened.get(key)
            if current is not None and counts.get(key, 0) + len(links) <= _PUSH_GROUP_MAX_LINKS:
                current.append(task)
                counts[key] = counts.get(key, 0) + len(links)
                continue
            current = [task]
            opened[key] = current
            counts[key] = len(links)
            groups.append(current)
        return groups

    def _supports_batch(self, destination: str, task: Dict[str, Any]) -> bool:
        """该任务的目标是否支持一次提交多条链接。"""
        try:
            target = resolve_destination(destination, self._plugin, self._gate)
        except Exception:  # pragma: no cover - 未知目标交给单任务路径报错
            return False
        return bool(getattr(target, "supports_batch", False))

    def _claim_pending_tasks(self) -> List[Dict[str, Any]]:
        """领取待处理任务（带重试退避：退避窗口内的失败任务不提前重试）。"""
        db = self._db()
        if db is None:
            return []
        try:
            from sqlalchemy import select

            with db.session() as session:
                rows = session.execute(
                    select(TgPushTask)
                    .where(
                        TgPushTask.plugin_id == self._plugin_id(),
                        TgPushTask.status == STATUS_PENDING,
                    )
                    .order_by(TgPushTask.id)
                    .limit(TgPushTask.worker_batch())
                ).scalars().all()
                tasks = [self._task_view(row) for row in rows]
                now = datetime.now()
                claimable = []
                for row, view in zip(rows, tasks):
                    retries = int(view.get("retries") or 0)
                    backoff = min(_RETRY_MAX_SECONDS, _RETRY_BASE_SECONDS * (2 ** max(0, retries - 1)))
                    updated = view.get("updated_at")
                    if retries > 0 and updated:
                        try:
                            age = (now - datetime.fromisoformat(str(updated))).total_seconds()
                        except (TypeError, ValueError):
                            age = backoff
                        if age < backoff:
                            continue
                    row.status = STATUS_RUNNING
                    claimable.append(view)
                session.commit()
                return claimable
        except Exception as err:  # pragma: no cover
            logger.debug(f"领取推送任务失败：{err}")
            return []

    def _execute_push(self, task: Dict[str, Any]) -> None:
        """按 destination 分派执行单个推送任务。"""
        db = self._db()
        if db is None:
            return
        destination = str(task.get("destination") or "smart")
        try:
            target = resolve_destination(destination, self._plugin, self._gate)
        except Exception as err:
            self._finish_task(task, ok=False, message=f"未知推送目标 {destination}：{err}", retryable=False)
            return

        try:
            result = target.push(self._push_payload(task))
        except Exception as err:  # pragma: no cover - 目标实现未兜底的异常
            logger.warning(f"推送目标执行异常（{destination}）：{err}")
            result = None
            self._finish_task(task, ok=False, message=f"推送异常：{err}", retryable=True,
                              via=getattr(target, "name", ""))
            return

        if result is None:
            return
        self._finish_task(
            task,
            ok=result.ok,
            message=result.message,
            retryable=result.retryable,
            detail=result.detail,
            via=getattr(target, "name", ""),
        )

    @staticmethod
    def _push_payload(task: Dict[str, Any]) -> Dict[str, Any]:
        """把任务负载与任务顶层定位合并成目标的入参。

        ``payload`` 只存 links/text/title/forward 这类负载，但 ``tg_forward``
        目标还需要 ``chat_id`` / ``message_id``（定位原消息）与 ``target_id``
        （转发去向）——它们在任务表的独立列里，这里合并后传给目标，
        目标实现仍只面对一个 dict。
        """
        payload = dict(task.get("payload") or {})
        for key in ("chat_id", "message_id", "target_id"):
            value = task.get(key)
            if value not in (None, ""):
                payload.setdefault(key, value)
        return payload

    def _execute_push_group(self, group: List[Dict[str, Any]]) -> None:
        """合并执行：一次调用提交多条任务的链接，再按逐条结果回填各任务终态。

        目标必须在 ``result.detail["results"]`` 里给出每条**输入链接**的
        ``source``/``ok``；拿不到逐条结果时退回整批结论（保守：整批成功才算成功）。

        注意：需要消息定位的目标（如 ``tg_forward``）不支持合并——各任务的
        ``chat_id``/``message_id`` 互不相同，合并会张冠李戴。这类目标未声明
        ``supports_batch``，永远走单任务路径。
        """
        first = group[0]
        destination = str(first.get("destination") or "smart")
        try:
            target = resolve_destination(destination, self._plugin, self._gate)
        except Exception as err:
            for task in group:
                self._finish_task(task, ok=False, message=f"未知推送目标 {destination}：{err}", retryable=False)
            return

        links: List[str] = []
        spans: List["tuple[Dict[str, Any], int, int]"] = []
        for task in group:
            start = len(links)
            links.extend(_task_links(task))
            spans.append((task, start, len(links)))
        payload = {
            "links": links,
            "text": str((first.get("payload") or {}).get("text") or ""),
            "title": str((first.get("payload") or {}).get("title") or "")[:250],
        }
        try:
            result = target.push(payload)
        except Exception as err:  # pragma: no cover - 目标实现未兜底的异常
            logger.warning(f"合并推送异常（{destination}）：{err}")
            for task in group:
                self._finish_task(task, ok=False, message=f"推送异常：{err}", retryable=True,
                                  via=getattr(target, "name", ""))
            return
        if result is None:
            return

        outcomes = _link_outcomes(result.detail)
        logger.info(
            f"[{self._plugin_id()}] 合并推送：{len(group)} 条任务 / {len(links)} 条链接"
            f"（{destination}）→ {result.message}"
        )
        for task, start, end in spans:
            task_links = links[start:end]
            if not outcomes:
                # 目标完全不回报逐条结果：只能用整批结论兜底（保守：整批成功才算成功）
                succeeded = len(task_links) if result.ok else 0
                failed = len(task_links) - succeeded
                ok, retryable = bool(result.ok), bool(result.retryable)
            else:
                known = [outcomes.get(link) for link in task_links]
                known = [entry for entry in known if entry]
                succeeded = sum(1 for entry in known if entry["ok"])
                # 没进结果的链接 = 没被处理（未识别 / 超时 / 超上限），计入失败并交回队列
                failed = len(task_links) - succeeded
                ok = len(known) == len(task_links) and failed == 0
                retryable = len(known) < len(task_links) or (failed > 0 and succeeded == 0)
            self._finish_task(
                task,
                ok=ok,
                message=f"合并推送（{len(task_links)} 条）：成功 {succeeded}，失败 {failed}",
                retryable=retryable,
                detail={"batch": True, "links": len(task_links)},
                via=getattr(target, "name", ""),
            )

    def _finish_task(self, task: Dict[str, Any], *, ok: bool, message: str,
                     retryable: bool, detail: Optional[dict] = None,
                     via: str = "") -> str:
        """更新任务终态（成功 done；可重试失败回 pending 并退避；否则 failed）。

        ``via`` 是实际执行的目标名（``pan115`` / ``tg_forward`` …），
        供通知按目标归类。返回终态字符串：``done`` / ``retry`` / ``failed``。
        """
        db = self._db()
        if db is None:
            return "failed"
        import json

        task_id = int(task.get("id") or 0)
        retries = int(task.get("retries") or 0)
        terminal = ok or not retryable
        outcome = "done" if ok else ("failed" if terminal else "retry")
        try:
            with db.session() as session:
                row = session.get(TgPushTask, task_id)
                if row is None:
                    return
                if ok:
                    row.status = STATUS_DONE
                    row.error = ""
                    row.result = json.dumps({"message": message, "detail": detail or {}}, ensure_ascii=False)[:2000]
                elif retryable and retries < TgPushTask.max_retries():
                    row.status = STATUS_PENDING
                    row.retries = retries + 1
                    row.error = str(message)[:500]
                else:
                    row.status = STATUS_FAILED
                    row.error = str(message)[:500]
                    row.result = json.dumps({"message": message}, ensure_ascii=False)[:2000]
                session.commit()
        except Exception as err:  # pragma: no cover
            logger.warning(f"更新推送任务状态失败（#{task_id}）：{err}")
            return "failed"
        # 终态时把推送结果回写到命中流水：流水里的"已入推送队列 #N"能看到结局
        if terminal:
            self._annotate_hit(task, ok, message)
        if ok:
            self._stats["push_done"] = self._stats.get("push_done", 0) + 1
        # 记进本轮通知桶（成功汇总 / 失败汇总在 _push_cycle 末尾统一发出）
        self._note_outcome(task=task, via=via, outcome=outcome, message=message)
        return outcome

    def _annotate_hit(self, task: Dict[str, Any], ok: bool, message: str) -> None:
        """把推送结果追加到对应命中流水的说明里（同规则同消息、决策为 hit 的行）。"""
        db = self._db()
        if db is None:
            return
        try:
            from sqlalchemy import select

            with db.session() as session:
                rows = session.execute(
                    select(TgHitLog).where(
                        TgHitLog.plugin_id == self._plugin_id(),
                        TgHitLog.rule_id == str(task.get("rule_id") or "")[:64],
                        TgHitLog.chat_id == int(task.get("chat_id") or 0),
                        TgHitLog.message_id == int(task.get("message_id") or 0),
                        TgHitLog.decision == DECISION_HIT,
                    )
                ).scalars().all()
                suffix = f" ｜ 推送{'成功' if ok else '失败'}：{str(message or '')[:120]}"
                for row in rows:
                    row.detail = f"{row.detail}{suffix}"[:500]
                session.commit()
        except Exception as err:  # pragma: no cover - 回写失败不影响推送本身
            logger.debug(f"回写推送结果到命中流水失败（忽略）：{err}")

    @staticmethod
    def _task_view(row: Any) -> Dict[str, Any]:
        return {
            "id": int(getattr(row, "id", 0) or 0),
            "rule_id": str(getattr(row, "rule_id", "") or ""),
            "chat_id": int(getattr(row, "chat_id", 0) or 0),
            "message_id": int(getattr(row, "message_id", 0) or 0),
            "destination": str(getattr(row, "destination", "") or ""),
            "target_id": str(getattr(row, "target_id", "") or ""),
            "payload": _loads(getattr(row, "payload", "") or "{}"),
            "status": str(getattr(row, "status", "") or ""),
            "retries": int(getattr(row, "retries", 0) or 0),
            "error": str(getattr(row, "error", "") or ""),
            "updated_at": getattr(row, "updated_at", None),
        }

    # ------------------------------------------------------------------ 处理器注册

    def _runtime(self):
        credentials = getattr(self._plugin, "_credentials", None)
        if credentials is None:
            return None
        return getattr(credentials, "_runtime", None)

    def _register_handler(self) -> bool:
        """把新消息事件处理器注册到当前 TG 客户端（在 loop 内执行）。"""
        runtime = self._runtime()
        if runtime is None or not runtime.is_running() or runtime.client is None:
            self._handler_ok = False
            return False
        try:
            from telethon import events
        except Exception:  # pragma: no cover - 依赖缺失
            self._handler_ok = False
            return False

        if self._handler is None:
            self._handler = self._handle_event

        async def _register() -> bool:
            client = runtime.client
            if client is None:
                return False
            client.add_event_handler(self._handler, events.NewMessage)
            await self._resolve_watched(client)
            return True

        try:
            ok = runtime.call(_register(), timeout=10)
            self._handler_ok = bool(ok)
            if ok:
                logger.info(
                    f"[{self._plugin_id()}] 已注册 TG 新消息监听（client={id(runtime.client)}），"
                    f"关心会话 ID：{self._interested_chat_ids()}"
                )
            else:
                logger.warning(f"[{self._plugin_id()}] TG 新消息监听注册失败（客户端不可用）")
            return bool(ok)
        except Exception as err:
            self._handler_ok = False
            logger.warning(f"[{self._plugin_id()}] 注册 TG 新消息监听失败（下轮重试）：{err}")
            return False

    def _unregister_handler(self) -> None:
        runtime = self._runtime()
        client = getattr(runtime, "client", None) if runtime is not None else None
        if client is not None and self._handler is not None:
            try:
                client.remove_event_handler(self._handler)
            except Exception as err:  # pragma: no cover - 注销失败不影响停止
                logger.debug(f"注销 TG 新消息监听失败（忽略）：{err}")
        self._handler_ok = False

    async def _resolve_watched(self, client: Any) -> None:
        """把关心会话（监控 ∪ 缓存）的 ID 反查成会话标题（在 TG loop 内执行）。

        反查成功 → 日志明确"这个 ID 是哪个频道"；失败 → 该 ID 在此账号视角
        不存在 / 无权限 / 已失效，规则或缓存频道必然永远收不到它的事件。
        """
        detail: List[Dict[str, Any]] = []
        for chat_id in self._interested_chat_ids():
            purposes = self._purposes(int(chat_id))
            entry: Dict[str, Any] = {
                "chat_id": int(chat_id), "title": "", "resolved": False,
                "error": "", "purposes": purposes,
            }
            try:
                entity = await client.get_entity(int(chat_id))
                title = (
                    getattr(entity, "title", None)
                    or getattr(entity, "username", None)
                    or getattr(entity, "first_name", None)
                    or ""
                )
                entry["title"] = str(title)[:60]
                entry["resolved"] = True
                logger.info(
                    f"[{self._plugin_id()}] 关心会话 {chat_id} →「{entry['title']}」"
                    f"（{'/'.join(purposes)}）"
                )
            except Exception as err:
                # 反查撞 FloodWait 也要上报（读取失败往往意味着账号正被限流）
                report_flood_wait(self._plugin, err)
                entry["error"] = str(err)[:120]
                logger.warning(
                    f"[{self._plugin_id()}] 关心会话 {chat_id} 反查失败（账号看不到该会话，"
                    f"将收不到它的事件；请到 TG 凭证页刷新对话后重选）：{err}"
                )
            detail.append(entry)
        self._watched_detail = detail

    def _ensure_handler(self) -> None:
        """健康检查：运行时可能因掉线重建客户端，处理器会丢，需要补注册。"""
        runtime = self._runtime()
        if runtime is None or not runtime.is_running():
            if self._handler_ok:
                logger.info(f"[{self._plugin_id()}] TG 运行时已停止，暂停消息监听")
            self._handler_ok = False
            return
        client = runtime.client
        if client is None:
            return
        if self._handler_ok and self._is_registered(client):
            return
        self._register_handler()

    def _is_registered(self, client: Any) -> bool:
        """处理器是否仍注册在该客户端上（Telethon 存于 _event_builders）。"""
        builders = getattr(client, "_event_builders", None)
        if not isinstance(builders, list) or self._handler is None:
            return False
        return any(callback is self._handler for _, callback in builders)

    # ------------------------------------------------------------------ 识别器与状态

    def _recognizer(self):
        return recognizer_service

    def stats(self) -> dict:
        """流水线运行态（供状态接口）。"""
        pending, failed = self._push_counts()
        return {
            "running": self.is_running(),
            "handler_registered": bool(self._handler_ok),
            "buffered": sum(len(buffer["messages"]) for buffer in self._buffers.values()),
            "queued": self._queue.qsize(),
            "processed": self._stats["processed"],
            "hit": self._stats["hit"],
            "skipped": self._stats["skipped"],
            "failed": self._stats["failed"],
            "events_received": self._stats["events_received"],
            "events_watched": self._stats["events_watched"],
            "events_unwatched": self._stats["events_unwatched"],
            "messages_enqueued": self._stats["messages_enqueued"],
            "cache_written": self._stats.get("cache_written", 0),
            "forward_hit": self._stats.get("forward_hit", 0),
            "last_event_at": self._last_event_at,
            "recent_sources": self._recent_sources_view(),
            "watched_detail": [dict(entry) for entry in self._watched_detail],
            "push_done": self._stats.get("push_done", 0),
            "push_pending": pending,
            "push_failed": failed,
            "started_at": self._started_at,
            "last_error": self._last_error,
        }

    def _recent_sources_view(self) -> List[dict]:
        """最近消息来源（按活跃时间倒序，最多 24 条，带关心的用途标记）。"""
        items = sorted(
            self._recent_sources.items(),
            key=lambda pair: pair[1]["_mono"],
            reverse=True,
        )[:24]
        return [
            {
                "chat_id": int(chat_id),
                "count": int(record["count"]),
                "last_at": str(record["last_at"]),
                "watched": bool(self._monitor.is_watched(int(chat_id))),
                "forwarded": self._forward_watched(int(chat_id)),
                "cached": self._cached_chat(int(chat_id)),
            }
            for chat_id, record in items
        ]

    def _push_counts(self) -> tuple:
        db = self._db()
        if db is None:
            return 0, 0
        try:
            from sqlalchemy import func, select

            with db.session() as session:
                pending = session.execute(
                    select(func.count()).select_from(TgPushTask).where(
                        TgPushTask.plugin_id == self._plugin_id(),
                        TgPushTask.status == STATUS_PENDING,
                    )
                ).scalar() or 0
                failed = session.execute(
                    select(func.count()).select_from(TgPushTask).where(
                        TgPushTask.plugin_id == self._plugin_id(),
                        TgPushTask.status == STATUS_FAILED,
                    )
                ).scalar() or 0
                return int(pending), int(failed)
        except Exception as err:  # pragma: no cover
            logger.debug(f"统计推送任务失败：{err}")
            return 0, 0

    # ------------------------------------------------------------------ 测试入口

    def test_text(self, text: str) -> dict:
        """对一段文本跑一遍「净化 → 识别 → 逐规则决策」，不落库不入队。

        供配置界面的「规则测试」使用：用户粘贴一条频道消息，即可预览每条规则
        会怎么处理，不必等真实消息。
        """
        cleaned = recognizer_service.purify_text(text)
        meta = self._recognizer().recognize(text)
        parsed = link_utils.parse_push_text(text)
        links = [item.raw or item.url for item in parsed.items if item.supported]

        traces: List[dict] = []
        for rule in self._monitor.rules():
            trace = {
                "rule_id": str(rule.get("id") or ""),
                "rule_name": str(rule.get("name") or ""),
                "destination": str(rule.get("destination") or "smart"),
                "enabled": bool(rule.get("enabled", True)),
            }
            if rule.get("match_custom_keywords"):
                keywords = [str(kw) for kw in (rule.get("custom_keywords") or []) if str(kw).strip()]
                if keywords and not any(keyword in cleaned for keyword in keywords):
                    trace.update(decision=DECISION_SKIPPED_KEYWORD, reason="自定义关键词未命中")
                    traces.append(trace)
                    continue
            if rule.get("match_only_if_missing"):
                if meta is None:
                    trace.update(
                        decision=DECISION_SKIPPED_UNRECOGNIZED,
                        reason=("宿主识别引擎不可用" if not recognizer_service.meta_available()
                                else "标题无法识别，无法判断缺失"),
                    )
                    traces.append(trace)
                    continue
                try:
                    verdict = self._matcher.is_missing(
                        title=meta.get("title") or "",
                        year=meta.get("year") or "",
                        media_type=meta.get("media_type") or "",
                        season=meta.get("season"),
                        episode=meta.get("episode"),
                        episode_end=meta.get("episode_end"),
                        require_subscription=True,
                    )
                except Exception as err:  # pragma: no cover
                    verdict = {"missing": None, "reason": f"缺失判断异常：{err}"}
                if verdict.get("missing") is None or not verdict.get("missing"):
                    decision, reason = _decision_for_skip(verdict)
                    trace.update(decision=decision, reason=reason)
                    traces.append(trace)
                    continue
            destination = str(rule.get("destination") or "smart")
            if destination in ("smart", "pan115") and not links:
                trace.update(decision=DECISION_SKIPPED_NO_LINK, reason="没有可推送的链接")
                traces.append(trace)
                continue
            trace.update(decision=DECISION_HIT, reason="会入推送队列并执行")
            traces.append(trace)

        return {
            "purified": cleaned,
            "recognized": meta,
            "links": links,
            "rules": traces,
        }


def _loads(raw: str) -> dict:
    import json

    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:  # pragma: no cover
        return {}


def new_rule_id() -> str:
    """生成规则稳定 ID（保存时补缺，保证重排/重命名后流水不串）。"""
    return "r" + uuid.uuid4().hex[:8]
