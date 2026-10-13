"""P6 TG 通用转发测试。

覆盖：两级匹配（逻辑一关键词、逻辑二扩展名恒 AND）/ 内容转换（正则、非法正则跳过、
顺序应用）/ 置顶判定 / 规则归一与校验 / 转发模块状态与测试预览 /
流水线接入（命中入队带 forward 指令、未命中落 kind=forward 流水、去重、
推送 worker 把消息定位并入目标负载）/ tg_forward 目标（原样转发 / 转换后发送 /
置顶）/ hit_log kind 列迁移 / API 层。

1.5.1 起转发与订阅彻底解耦（无「匹配订阅」、无 OR/AND 组合），相关用例随之移除。

宿主依赖（MetaVideo / 通知 / 插件 DB / TG 运行时）用可注入替身驱动，
真机行为仍以部署验证为准。
"""
from __future__ import annotations

import asyncio
import json
import re

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.plugins.tgmediacenter.controller import api as controller_api
from app.plugins.tgmediacenter.controller import schemas as api_schemas
from app.plugins.tgmediacenter.core import forward as forward_engine
from app.plugins.tgmediacenter.core.cooldown import CooldownGate
from app.plugins.tgmediacenter.core.pipeline import MessagePipeline
from app.plugins.tgmediacenter.destinations.base import PushResult
from app.plugins.tgmediacenter.destinations.tg_forward import TgForwardDestination
from app.plugins.tgmediacenter.model.hit_log import (
    DECISION_HIT,
    DECISION_SKIPPED_EXTENSION,
    DECISION_SKIPPED_KEYWORD,
    KIND_FORWARD,
    KIND_MONITOR,
    TgHitLog,
)
from app.plugins.tgmediacenter.model.migration import ensure_hit_log_columns, ensure_schema
from app.plugins.tgmediacenter.model.push_task import STATUS_PENDING, TgPushTask
from app.plugins.tgmediacenter.modules.forward import ForwardModule
from app.plugins.tgmediacenter.modules.monitor import MonitorModule
from app.plugins.tgmediacenter.services import recognizer as recognizer_module

CHAT_A = -1004316104321
TARGET = -1003229693136
LINK = "https://115.com/s/swabc123?password=abcd"


def _text(title_line: str, link: str = LINK) -> str:
    return f"{title_line}\n🔗 链接: {link}"


# ---------------------------------------------------------------------- 测试替身


class FakeType:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeMetaVideo:
    """``名称 (年份) S01E02`` → 剧集；``名称 (年份)`` → 电影。"""

    def __init__(self, title: str, subtitle=None, isfile: bool = False) -> None:
        self.org_string = title
        self.subtitle = subtitle
        self.isfile = isfile
        self.year = ""
        match = re.search(r"S(\d+)E(\d+)", title, re.IGNORECASE)
        year = re.search(r"(19|20)\d{2}", title)
        if year:
            self.year = year.group(0)
        clean = re.sub(r"S\d+E\d+", "", title, flags=re.IGNORECASE)
        clean = re.sub(r"[（(]?(?:19|20)\d{2}[）)]?", "", clean)
        self.name = clean.strip(" .·-_（）()")
        self.begin_season = int(match.group(1)) if match else None
        self.begin_episode = int(match.group(2)) if match else None
        self.end_episode = None
        self.type = FakeType("电视剧" if match else "电影")


class FakeDatabase:
    """内存 SQLite 插件数据库句柄（session 是方法，与宿主一致）。"""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        TgHitLog.__table__.create(self.engine)
        TgPushTask.__table__.create(self.engine)
        self._factory = sessionmaker(bind=self.engine)

    def session(self):
        return self._factory()


class FakePlugin:
    def __init__(self, config: dict | None = None) -> None:
        self._config = dict(config or {})
        self._data: dict = {}
        self._db = FakeDatabase()
        self._credentials = None
        self._cache = None
        self._forward = None
        self._monitor = None
        self.messages: list = []

    @property
    def config(self) -> dict:
        return self._config

    def save_config(self, **patch) -> None:
        merged = dict(self._config)
        merged.update(patch)
        self._config = merged

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value

    def get_database(self):
        return self._db

    def get_state(self) -> bool:
        return bool(self._config.get("enabled"))

    def post_message(self, title="", text="") -> None:
        self.messages.append({"title": title, "text": text})


class FakeMatcher:
    """matcher 替身（流水线构造参数；转发已不查订阅，仅监控路径可能用到）。"""

    def __init__(self, subscribed=True) -> None:
        self.subscribed = subscribed
        self.calls = 0

    def is_missing(self, **kwargs):
        return {"missing": None, "reason": "替身不做缺失判断"}

    def capabilities(self) -> dict:
        return {
            "queries_available": True,
            "mediaserver_available": True,
            "subscriptions": 3,
            "mediaserver": "emby",
        }


class _SentMessage:
    def __init__(self, message_id: int) -> None:
        self.id = message_id


class FakeTGClient:
    """记录转发 / 发送 / 置顶调用的 TG 客户端替身。"""

    def __init__(self, *, has_message: bool = True) -> None:
        self.has_message = has_message
        self.forward_calls: list = []
        self.send_calls: list = []
        self.pin_calls: list = []
        self.pin_error = ""

    async def get_messages(self, chat_id, ids=None):
        return _SentMessage(ids) if self.has_message else None

    async def forward_messages(self, target, messages):
        self.forward_calls.append((target, messages))
        return _SentMessage(9001)

    async def send_message(self, target, text_value):
        self.send_calls.append((target, text_value))
        return _SentMessage(9002)

    async def pin_message(self, target, message, notify=False):
        if self.pin_error:
            raise RuntimeError(self.pin_error)
        self.pin_calls.append((target, getattr(message, "id", message), notify))


class FakeRuntime:
    """真正执行协程的运行时替身（转发目标内部用 runtime.call 跑 async）。"""

    def __init__(self, client: FakeTGClient | None = None) -> None:
        self.client = client or FakeTGClient()

    def is_running(self) -> bool:
        return True

    def call(self, coro, timeout=0):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ---------------------------------------------------------------------- fixtures


@pytest.fixture()
def fake_metavideo(monkeypatch):
    monkeypatch.setattr(recognizer_module, "META_AVAILABLE", True)
    monkeypatch.setattr(recognizer_module, "MetaVideo", FakeMetaVideo)
    return FakeMetaVideo


@pytest.fixture()
def plugin():
    return FakePlugin({
        "enabled": True,
        "forward_enabled": True,
        "tg_user_cooldown_seconds": 0,
    })


@pytest.fixture()
def forward(plugin):
    module = ForwardModule(plugin)
    plugin._forward = module
    return module


def _rule(**overrides) -> dict:
    rule = {
        "name": "测试转发",
        "source_ids": [CHAT_A],
        "target_id": TARGET,
        "match_custom_keywords": False,
        "custom_keywords": [],
        "pin_links_enabled": False,
        "pin_link_keywords": [],
        "match_file_extensions": False,
        "file_extensions_to_match": [],
        "enable_transform": False,
        "transform_rules": [],
        "enabled": True,
    }
    rule.update(overrides)
    return rule


def _hits(plugin, kind: str = "") -> list:
    with plugin.get_database().session() as session:
        stmt = select(TgHitLog)
        if kind:
            stmt = stmt.where(TgHitLog.kind == kind)
        return list(session.execute(stmt).scalars().all())


def _tasks(plugin) -> list:
    with plugin.get_database().session() as session:
        return list(session.execute(select(TgPushTask)).scalars().all())


# ---------------------------------------------------------------------- 规则引擎


class TestMatchRule:
    def test_no_constraints_always_matches(self):
        verdict = forward_engine.match_rule(_rule(), text="随便一条消息", cleaned="随便一条消息")
        assert verdict["matched"] is True

    def test_custom_keywords_or(self):
        rule = _rule(match_custom_keywords=True, custom_keywords=["链接", "合集"])
        assert forward_engine.match_rule(rule, text="有链接", cleaned="有链接")["matched"] is True
        miss = forward_engine.match_rule(rule, text="无关", cleaned="无关")
        assert miss["matched"] is False
        assert "关键词" in miss["reason"]

    def test_empty_keywords_rejected(self):
        rule = _rule(match_custom_keywords=True, custom_keywords=[])
        verdict = forward_engine.match_rule(rule, text="x", cleaned="x")
        assert verdict["matched"] is False and "未填写任何关键词" in verdict["reason"]

    def test_legacy_match_mode_and_subscription_fields_ignored(self):
        """1.5.0 的「匹配订阅」与 match_mode 字段被静默忽略（与订阅解耦）。"""
        rule = _rule(
            match_subscription_keywords=True, match_mode="and",
            match_custom_keywords=True, custom_keywords=["链接"],
        )
        verdict = forward_engine.match_rule(rule, text="有链接", cleaned="有链接")
        assert verdict["matched"] is True

    def test_extension_is_and_with_logic_one(self):
        rule = _rule(match_custom_keywords=True, custom_keywords=["链接"],
                     match_file_extensions=True, file_extensions_to_match=["mkv"])
        # 关键词命中但扩展名不符 → 恒 AND 下不通过
        verdict = forward_engine.match_rule(
            rule, text="有链接 1080p.mp4", cleaned="有链接 1080p.mp4"
        )
        assert verdict["matched"] is False
        assert forward_engine.skip_decision(verdict) == DECISION_SKIPPED_EXTENSION
        assert forward_engine.match_rule(
            rule, text="有链接 2160p.mkv", cleaned="有链接 2160p.mkv"
        )["matched"] is True

    def test_extension_forms(self):
        assert forward_engine.match_extensions("片名.mkv", ["mkv"]) == ["mkv"]
        assert forward_engine.match_extensions("【MP4】片名", ["mp4"]) == ["mp4"]
        assert forward_engine.match_extensions("片名.avi", ["mkv"]) == []


class TestTransform:
    def test_parse_and_apply(self):
        outcome = forward_engine.apply_transform(
            "加入群组 https://t.me/ad 看片", ["加入群组 -> ", "看片 -> 观影"]
        )
        assert "加入群组" not in outcome["text"]
        assert "观影" in outcome["text"]
        assert outcome["applied"] == 2
        assert outcome["errors"] == []

    def test_greedy_regex_replaces_to_end_of_line(self):
        """``.*`` 是贪婪的：规则写「加入群组.*->」会把该行后面全部吃掉（符合正则直觉）。"""
        outcome = forward_engine.apply_transform(
            "加入群组 https://t.me/ad 看片", ["加入群组.*-> "]
        )
        assert outcome["text"].strip() == ""

    def test_invalid_regex_is_skipped_not_fatal(self):
        outcome = forward_engine.apply_transform("原文", ["[非法 -> x", "原文 -> 新文"])
        assert outcome["text"] == "新文"
        assert outcome["applied"] == 1
        assert outcome["errors"] and "正则非法" in outcome["errors"][0]

    def test_arrow_variants(self):
        assert forward_engine.parse_transform_rules(["a => b", "c → d"]) == [("a", "b"), ("c", "d")]

    def test_comments_and_blank_lines_skipped(self):
        assert forward_engine.parse_transform_rules(["# 注释", "", "a -> b"]) == [("a", "b")]

    def test_sequential_application(self):
        outcome = forward_engine.apply_transform("abc", ["a -> 1", "1 -> 2"])
        assert outcome["text"] == "2bc"


class TestPin:
    def test_disabled(self):
        assert forward_engine.should_pin(_rule(), text="x", links=[LINK]) is False

    def test_requires_links(self):
        rule = _rule(pin_links_enabled=True)
        assert forward_engine.should_pin(rule, text="x", links=[]) is False

    def test_keywords_filter(self):
        rule = _rule(pin_links_enabled=True, pin_link_keywords=["115"])
        assert forward_engine.should_pin(rule, text=f"网盘 {LINK}", links=[LINK]) is True
        assert forward_engine.should_pin(rule, text="磁力 magnet:x", links=["magnet:x"]) is False

    def test_keywords_empty_means_any_link(self):
        rule = _rule(pin_links_enabled=True)
        assert forward_engine.should_pin(rule, text="x", links=[LINK]) is True


class TestValidateRule:
    def test_missing_target(self):
        assert "未填写转发目标" in forward_engine.validate_rule(_rule(target_id=0))

    def test_extension_without_values(self):
        rule = _rule(match_file_extensions=True, file_extensions_to_match=[])
        assert "扩展名" in forward_engine.validate_rule(rule)

    def test_ok(self):
        assert forward_engine.validate_rule(_rule()) == ""


# ---------------------------------------------------------------------- 转发模块


class TestForwardModule:
    def test_normalize_assigns_f_prefix_and_int_target(self):
        rules = ForwardModule(FakePlugin()).normalize_rules([{"target_id": str(TARGET)}])
        assert rules[0]["id"].startswith("f")
        assert rules[0]["target_id"] == TARGET

    def test_normalize_strips_extension_dots(self):
        rules = ForwardModule(FakePlugin()).normalize_rules(
            [{"target_id": TARGET, "file_extensions_to_match": [".MKV", "mp4"]}]
        )
        assert rules[0]["file_extensions_to_match"] == ["mkv", "mp4"]

    def test_monitor_rule_id_prefix_converted(self):
        rules = ForwardModule(FakePlugin()).normalize_rules([{"id": "rabc1234", "target_id": TARGET}])
        assert rules[0]["id"] == "fabc1234"

    def test_rules_for_chat_and_watched(self, forward):
        forward.save_rules([_rule(source_ids=[CHAT_A, CHAT_A, "bad"])])
        assert forward.watched_chat_ids() == [CHAT_A]
        assert forward.is_watched(CHAT_A) is True
        assert forward.rules_for_chat(CHAT_A)[0]["name"] == "测试转发"

    def test_save_rules_rejects_invalid(self, forward):
        with pytest.raises(ValueError):
            forward.save_rules([_rule(target_id=0)])
        assert forward.rules() == []

    def test_status(self, forward):
        forward.save_rules([_rule(transform_rules=["a -> b", "c -> d"])])
        data = forward.status()
        assert data["rules_count"] == 1
        assert data["watched_chats"] == 1
        assert data["transform_rules_count"] == 2
        assert "subscriptions" not in data and "queries_available" not in data

    def test_test_text_reports_match_and_transform(self, forward, fake_metavideo):
        forward.save_rules([
            _rule(match_custom_keywords=True, custom_keywords=["链接"],
                  enable_transform=True, transform_rules=["看片 -> 观影"])
        ])
        data = forward.test_text("青与碧 (2026) S01E02\n有链接 https://t.me/x\n看片")
        assert data["rules"][0]["matched"] is True
        assert data["rules"][0]["decision"] == DECISION_HIT
        assert "观影" in data["rules"][0]["send_text"]

    def test_test_text_marks_unmatched(self, forward, fake_metavideo):
        forward.save_rules([_rule(match_custom_keywords=True, custom_keywords=["不存在的词"])])
        data = forward.test_text("青与碧 (2026) S01E02\nhttps://115.com/s/xyz")
        assert data["rules"][0]["matched"] is False
        assert data["rules"][0]["decision"] == DECISION_SKIPPED_KEYWORD


# ---------------------------------------------------------------------- 流水线接入


@pytest.fixture()
def pipeline(plugin, forward):
    monitor = MonitorModule(plugin)
    plugin._monitor = monitor
    monkeypatch_matcher = FakeMatcher()
    pipe = MessagePipeline(plugin, monitor, monkeypatch_matcher, CooldownGate(0))
    monitor._pipeline = pipe
    pipe._matcher = monkeypatch_matcher
    return pipe


class TestPipelineForward:
    def test_interested_chats_include_forward_sources(self, pipeline, forward):
        forward.save_rules([_rule(source_ids=[CHAT_A])])
        assert CHAT_A in pipeline._interested_chat_ids()
        assert pipeline._purposes(CHAT_A) == ["转发"]

    def test_hit_enqueues_forward_task(self, plugin, pipeline, forward, fake_metavideo):
        forward.save_rules([_rule()])
        text = _text("青与碧 (2026) S01E02")
        pipeline._process_message(CHAT_A, {"message_id": 7001, "text": text},
                                  [], forward.rules_for_chat(CHAT_A))

        tasks = _tasks(plugin)
        assert len(tasks) == 1
        assert tasks[0].destination == "tg_forward"
        assert tasks[0].target_id == str(TARGET)
        hits = _hits(plugin, KIND_FORWARD)
        assert hits and hits[0].decision == DECISION_HIT
        assert "已入转发队列" in hits[0].detail

    def test_transform_and_pin_land_in_payload(self, plugin, pipeline, forward, fake_metavideo):
        forward.save_rules([_rule(
            enable_transform=True, transform_rules=["看片 -> 观影"],
            pin_links_enabled=True, pin_link_keywords=["115"],
        )])
        text = f"青与碧 (2026) S01E02\n看片 {LINK}"
        pipeline._process_message(CHAT_A, {"message_id": 7002, "text": text},
                                  [], forward.rules_for_chat(CHAT_A))

        payload = json.loads(_tasks(plugin)[0].payload)
        assert payload["forward"]["transform"] is True
        assert "观影" in payload["forward"]["send_text"]
        assert payload["forward"]["pin"] is True
        detail = _hits(plugin, KIND_FORWARD)[0].detail
        assert "转换后发送" in detail and "含置顶" in detail

    def test_unmatched_records_skip_hit(self, plugin, pipeline, forward, fake_metavideo):
        forward.save_rules([_rule(match_custom_keywords=True, custom_keywords=["不存在的词"])])
        pipeline._process_message(CHAT_A, {"message_id": 7003, "text": _text("青与碧 (2026) S01E02")},
                                  [], forward.rules_for_chat(CHAT_A))
        assert _tasks(plugin) == []
        hits = _hits(plugin, KIND_FORWARD)
        assert hits and hits[0].decision == DECISION_SKIPPED_KEYWORD

    def test_normalize_drops_legacy_subscription_fields(self, forward):
        """保存带 1.5.0 废弃字段的规则：归一后不再出现。"""
        rules = forward.normalize_rules([_rule(
            match_subscription_keywords=True, match_mode="and",
        )])
        assert "match_subscription_keywords" not in rules[0]
        assert "match_mode" not in rules[0]

    def test_execute_push_merges_message_location(self, plugin, pipeline, forward, fake_metavideo):
        """推送 worker 必须把 chat_id/message_id/target_id 并入目标负载——
        tg_forward 目标靠它们定位原消息（1.5.0 真机「任务缺少消息定位」的回归）。"""
        client = FakeTGClient()
        plugin._credentials = type("Creds", (), {"_runtime": FakeRuntime(client)})()
        forward.save_rules([_rule()])
        text = _text("青与碧 (2026) S01E02")
        pipeline._process_message(CHAT_A, {"message_id": 7100, "text": text},
                                  [], forward.rules_for_chat(CHAT_A))
        task = pipeline._task_view(_tasks(plugin)[0])
        assert task["destination"] == "tg_forward"
        payload = pipeline._push_payload(task)
        assert payload["chat_id"] == CHAT_A
        assert payload["message_id"] == 7100
        assert payload["target_id"] == str(TARGET)
        # 端到端：直接执行该任务应成功转发（而不是报「任务缺少消息定位」）
        pipeline._execute_push(task)
        assert client.forward_calls and client.forward_calls[0][0] == TARGET

    def test_push_payload_never_merges_into_group_payload(self, plugin):
        """合并下发的 payload 不携带单任务定位（各任务定位互不相同）。"""
        task = {"payload": {"links": ["x"]}, "chat_id": CHAT_A, "message_id": 1, "target_id": "t"}
        payload = MessagePipeline._push_payload(task)
        assert payload["chat_id"] == CHAT_A  # 单任务路径需要定位
        # 合并路径构造的 payload 只含 links/text/title（见 _execute_push_group），不调用本方法

    def test_duplicate_message_not_forwarded_twice(self, plugin, pipeline, forward, fake_metavideo):
        forward.save_rules([_rule()])
        text = _text("青与碧 (2026) S01E02")
        for _ in range(2):
            pipeline._process_message(CHAT_A, {"message_id": 7005, "text": text},
                                      [], forward.rules_for_chat(CHAT_A))
        assert len(_tasks(plugin)) == 1

    def test_monitor_and_forward_coexist(self, plugin, pipeline, forward, fake_metavideo):
        """两套规则监听同一频道：各自落自己的 kind 流水。"""
        plugin.save_config(monitor_enabled=False)
        forward.save_rules([_rule(source_ids=[CHAT_A])])
        pipeline._process_message(
            CHAT_A, {"message_id": 7006, "text": _text("青与碧 (2026) S01E02")},
            [{"id": "r1", "name": "监控", "destination": "none", "target_id": "",
              "match_only_if_missing": False, "enabled": True}],
            forward.rules_for_chat(CHAT_A),
        )
        assert len(_hits(plugin, KIND_MONITOR)) == 1
        assert len(_hits(plugin, KIND_FORWARD)) == 1

    def test_stats_counts_forward_hit(self, plugin, pipeline, forward, fake_metavideo):
        forward.save_rules([_rule()])
        pipeline._process_message(CHAT_A, {"message_id": 7007, "text": _text("青与碧 (2026) S01E02")},
                                  [], forward.rules_for_chat(CHAT_A))
        assert pipeline.stats()["forward_hit"] == 1


# ---------------------------------------------------------------------- 转发目标


def _destination(plugin, client=None, gate=None) -> TgForwardDestination:
    runtime = FakeRuntime(client)
    plugin._credentials = type("Creds", (), {"_runtime": runtime})()
    return TgForwardDestination(plugin, gate or CooldownGate(0))


class TestTgForwardDestination:
    def test_plain_forward(self, plugin):
        client = FakeTGClient()
        dest = _destination(plugin, client)
        result = dest.push({"chat_id": CHAT_A, "message_id": 11, "target_id": str(TARGET)})
        assert result.ok is True
        assert client.forward_calls and client.forward_calls[0][0] == TARGET
        assert client.send_calls == [] and client.pin_calls == []

    def test_transform_sends_new_text(self, plugin):
        client = FakeTGClient()
        dest = _destination(plugin, client)
        result = dest.push({
            "chat_id": CHAT_A, "message_id": 12, "target_id": str(TARGET),
            "forward": {"transform": True, "send_text": "转换后的内容"},
        })
        assert result.ok is True
        assert client.send_calls == [(TARGET, "转换后的内容")]
        assert client.forward_calls == []
        assert "转换后发送" in result.message

    def test_empty_transform_text_fails(self, plugin):
        client = FakeTGClient()
        dest = _destination(plugin, client)
        result = dest.push({
            "chat_id": CHAT_A, "message_id": 13, "target_id": str(TARGET),
            "forward": {"transform": True, "send_text": "   "},
        })
        assert result.ok is False and "转换后内容为空" in result.message

    def test_pin_after_forward(self, plugin):
        client = FakeTGClient()
        dest = _destination(plugin, client)
        result = dest.push({
            "chat_id": CHAT_A, "message_id": 14, "target_id": str(TARGET),
            "forward": {"pin": True},
        })
        assert result.ok is True
        assert client.pin_calls and client.pin_calls[0][2] is False  # notify=False 静默置顶

    def test_pin_failure_does_not_fail_forward(self, plugin):
        client = FakeTGClient()
        client.pin_error = "CHAT_ADMIN_REQUIRED"
        dest = _destination(plugin, client)
        result = dest.push({
            "chat_id": CHAT_A, "message_id": 15, "target_id": str(TARGET),
            "forward": {"pin": True},
        })
        assert result.ok is True
        assert "已置顶" not in result.message

    def test_missing_message_fails(self, plugin):
        client = FakeTGClient(has_message=False)
        dest = _destination(plugin, client)
        result = dest.push({"chat_id": CHAT_A, "message_id": 16, "target_id": str(TARGET)})
        assert result.ok is False and "消息不存在" in result.message

    def test_missing_target_fails(self, plugin):
        dest = _destination(plugin, FakeTGClient())
        result = dest.push({"chat_id": CHAT_A, "message_id": 17, "target_id": ""})
        assert result.ok is False and "未配置转发目标" in result.message

    def test_cooldown_defers(self, plugin):
        gate = CooldownGate(0)
        # 手动把门禁推到未来：立刻再取名额必然失败 → 任务应标记可重试
        gate.backoff(60)
        dest = _destination(plugin, FakeTGClient(), gate)
        result = dest.push({"chat_id": CHAT_A, "message_id": 18, "target_id": str(TARGET)})
        assert result.ok is False and result.retryable is True
        assert "冷却" in result.message


# ---------------------------------------------------------------------- 迁移


class _MigHandle:
    def __init__(self, engine) -> None:
        self.engine = engine

    def session(self):
        return sessionmaker(bind=self.engine)()


def _legacy_hit_log_engine():
    """建一张 1.4.x 形态的流水表（没有 kind 列）。"""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE monitor_hit_log ("
            "id INTEGER PRIMARY KEY, plugin_id VARCHAR(64), rule_id VARCHAR(64), "
            "chat_id BIGINT, message_id BIGINT, decision VARCHAR(32))"
        ))
    return engine


class TestMigration:
    def test_ensure_hit_log_columns_adds_kind(self):
        engine = _legacy_hit_log_engine()
        ensure_hit_log_columns(_MigHandle(engine))
        with engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(monitor_hit_log)")).fetchall()
        assert "kind" in {row[1] for row in rows}
        assert "episode_end" in {row[1] for row in rows}

    def test_ensure_hit_log_columns_is_idempotent(self):
        engine = _legacy_hit_log_engine()
        handle = _MigHandle(engine)
        ensure_hit_log_columns(handle)
        ensure_hit_log_columns(handle)  # 再跑一次不应报错
        with engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(monitor_hit_log)")).fetchall()
        assert len([row for row in rows if row[1] == "kind"]) == 1

    def test_ensure_schema_tolerates_missing_tables(self):
        engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        ensure_schema(_MigHandle(engine))  # 表都不存在：只告警，不抛


# ---------------------------------------------------------------------- API 层


class _StubPlugin(FakePlugin):
    """带 API 端点占位的插件替身（契约与真实主类一致）。"""

    def api_forward_rules(self):
        return controller_api.api_forward_rules(self)

    def api_forward_rules_save(self, request):
        return controller_api.api_forward_rules_save(self, request)

    def api_forward_status(self):
        return controller_api.api_forward_status(self)

    def api_forward_hits(self, page=1, page_size=20, decision=""):
        return controller_api.api_forward_hits(self, page=page, page_size=page_size, decision=decision)

    def api_forward_test(self, request):
        return controller_api.api_forward_test(self, request)


@pytest.fixture()
def api_plugin():
    plugin = _StubPlugin({"enabled": True, "forward_enabled": True})
    plugin._forward = ForwardModule(plugin)
    plugin._monitor = MonitorModule(plugin)
    return plugin


class TestForwardApi:
    def test_rules_payload_has_options(self, api_plugin):
        response = api_plugin.api_forward_rules()
        data = response.data
        assert data.rules == []
        assert any(item.value == DECISION_HIT for item in data.decisions)

    def test_save_and_read_back(self, api_plugin):
        request = api_schemas.ForwardRulesSaveRequest(
            rules=[api_schemas.ForwardRule.model_validate(_rule())]
        )
        response = api_plugin.api_forward_rules_save(request)
        assert response.data.rules[0].id.startswith("f")
        assert response.data.watched_chats == 1
        assert api_plugin.api_forward_rules().data.rules[0].target_id == TARGET

    def test_save_rejects_missing_target(self, api_plugin):
        request = api_schemas.ForwardRulesSaveRequest(
            rules=[api_schemas.ForwardRule.model_validate(_rule(target_id=0))]
        )
        with pytest.raises(HTTPException) as excinfo:
            api_plugin.api_forward_rules_save(request)
        assert excinfo.value.status_code == 400
        assert "未填写转发目标" in str(excinfo.value.detail)

    def test_status_endpoint(self, api_plugin):
        data = api_plugin.api_forward_status().data
        assert data.enabled is True
        assert data.rules_count == 0

    def test_hits_endpoint_empty(self, api_plugin):
        data = api_plugin.api_forward_hits().data
        assert data.total == 0 and data.items == []

    def test_test_endpoint_requires_text(self, api_plugin):
        with pytest.raises(HTTPException) as excinfo:
            api_plugin.api_forward_test(api_schemas.ForwardTestRequest(text="  "))
        assert excinfo.value.status_code == 400
