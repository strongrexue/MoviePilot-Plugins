"""排除关键词（黑名单，1.13.0）测试。

覆盖：
- ``forward_engine.excluded_keyword`` helper：命中/未命中/空词
- ``match_rule`` 排除层：优先级高于逻辑一命中；``skip_decision`` 归一
- pipeline 监控判定层：排除词命中 → skipped_excluded，且优先于关键词命中/入队
- pipeline 监控 test_text 渲染点与转发 _apply_forward_rule 同款
- 决策常量注册（DECISIONS / DECISION_LABELS）
- 监控 / 转发规则归一化保留 ``exclude_keywords``
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.plugins.tgmediacenter.core import forward as forward_engine
from app.plugins.tgmediacenter.core import pipeline as pipeline_module
from app.plugins.tgmediacenter.core.cooldown import CooldownGate
from app.plugins.tgmediacenter.model.hit_log import (
    DECISIONS,
    DECISION_HIT,
    DECISION_LABELS,
    DECISION_SKIPPED_EXCLUDED,
    TgHitLog,
)
from app.plugins.tgmediacenter.modules.forward import ForwardModule
from app.plugins.tgmediacenter.modules.monitor import MonitorModule
from app.plugins.tgmediacenter.services.matcher import MediaMatcher
from app.plugins.tgmediacenter.services import recognizer as recognizer_module

from .test_p4_monitor import CHAT_A, FakeMetaVideo, FakePlugin, query_all


# --------------------------------------------------------------------- helper


def test_excluded_keyword_helper():
    rule = {"exclude_keywords": ["加更", "花絮"]}
    assert forward_engine.excluded_keyword(rule, text="奔跑吧兄弟 加更篇 第5期") == "加更"
    assert forward_engine.excluded_keyword(rule, text="分类：综艺 花絮合集") == "花絮"
    assert forward_engine.excluded_keyword(rule, text="奔跑吧兄弟 正片 第5期") == ""
    assert forward_engine.excluded_keyword({"exclude_keywords": []}, text="加更") == ""
    assert forward_engine.excluded_keyword({}, text="加更") == ""
    # 空白词被跳过，不误命中
    assert forward_engine.excluded_keyword({"exclude_keywords": ["  ", ""]}, text="任意") == ""


def test_match_rule_exclusion_overrides_keywords():
    """命中自定义关键词 + 命中排除词 → 排除优先（stage=excluded）。"""
    rule = {
        "match_custom_keywords": True,
        "custom_keywords": ["综艺"],
        "exclude_keywords": ["加更"],
    }
    verdict = forward_engine.match_rule(rule, text="x", cleaned="综艺 第5期 加更篇")
    assert verdict["matched"] is False
    assert verdict["stage"] == "excluded"
    assert "加更" in verdict["reason"]
    assert forward_engine.skip_decision(verdict) == DECISION_SKIPPED_EXCLUDED


def test_match_rule_without_exclusion_still_passes():
    rule = {
        "match_custom_keywords": True,
        "custom_keywords": ["综艺"],
        "exclude_keywords": ["加更", "花絮"],
    }
    verdict = forward_engine.match_rule(rule, text="x", cleaned="综艺 正片 第5期")
    assert verdict["matched"] is True


def test_match_rule_exclusion_works_without_keyword_level():
    """只配排除词、不启用关键词级 → 同样拦截。"""
    rule = {"match_custom_keywords": False, "exclude_keywords": ["花絮"]}
    verdict = forward_engine.match_rule(rule, text="x", cleaned="某综艺 花絮")
    assert verdict["matched"] is False
    assert verdict["stage"] == "excluded"


def test_decision_registered():
    assert DECISION_SKIPPED_EXCLUDED in DECISIONS
    assert DECISION_LABELS[DECISION_SKIPPED_EXCLUDED] == "命中排除词"


# --------------------------------------------------------------------- 仅排除词模式（1.13.1 回归）


def test_match_rule_exclude_only_mode_passes_clean_message():
    """启用关键词过滤但只填排除词 → 白名单不设限，干净消息正常命中。"""
    rule = {
        "match_custom_keywords": True,
        "custom_keywords": [],
        "exclude_keywords": ["加更", "花絮"],
    }
    verdict = forward_engine.match_rule(rule, text="x", cleaned="综艺 正片 第5期")
    assert verdict["matched"] is True
    # 脏消息仍被逻辑零拦截
    verdict = forward_engine.match_rule(rule, text="x", cleaned="综艺 加更篇")
    assert verdict["matched"] is False and verdict["stage"] == "excluded"


def test_validate_rule_exclude_only_mode_allowed():
    """只配排除词的规则可以保存；连排除词也没有才拦。"""
    rule = {
        "target_id": -1003229693136,
        "match_custom_keywords": True,
        "custom_keywords": [],
        "exclude_keywords": ["加更"],
    }
    assert forward_engine.validate_rule(rule) == ""
    rule["exclude_keywords"] = []
    assert "未填写关键词" in forward_engine.validate_rule(rule)


def test_rule_response_models_keep_exclude_keywords():
    """回归锁（1.13.0 真机事故）：接口响应模型必须保留 exclude_keywords，
    否则保存后返回的规则丢字段 → 前端输入框清空、配置被旧值覆盖。"""
    from app.plugins.tgmediacenter.controller import schemas as api_schemas

    assert "exclude_keywords" in api_schemas.MonitorRule.model_fields
    assert "exclude_keywords" in api_schemas.ForwardRule.model_fields
    payload = {"id": "r1", "exclude_keywords": ["加更", "花絮"]}
    assert api_schemas.MonitorRule.model_validate(payload).exclude_keywords == ["加更", "花絮"]
    assert api_schemas.ForwardRule.model_validate(payload).exclude_keywords == ["加更", "花絮"]


# --------------------------------------------------------------------- 归一化


def test_monitor_normalize_keeps_exclude_keywords():
    module = MonitorModule(FakePlugin())
    rules = module.normalize_rules([{
        "source_ids": [1],
        "exclude_keywords": [" 加更 ", "", "花絮"],
    }])
    assert rules[0]["exclude_keywords"] == ["加更", "花絮"]


def test_forward_normalize_keeps_exclude_keywords():
    module = ForwardModule(FakePlugin())
    rules = module.normalize_rules([{
        "source_ids": [1], "target_id": -1003229693136,
        "exclude_keywords": [" 加更 ", "", "预告"],
    }])
    assert rules[0]["exclude_keywords"] == ["加更", "预告"]


# --------------------------------------------------------------------- pipeline


@pytest.fixture()
def plugin():
    return FakePlugin()


@pytest.fixture()
def monitor(plugin):
    module = MonitorModule(plugin)
    plugin._monitor = module
    return module


def _build(plugin, monitor, monkeypatch):
    monkeypatch.setattr(recognizer_module, "META_AVAILABLE", True)
    monkeypatch.setattr(recognizer_module, "MetaVideo", FakeMetaVideo)
    return pipeline_module.MessagePipeline(plugin, monitor, MediaMatcher(), CooldownGate(0.0))


def _process(pipeline, chat_id, text, message_id=1):
    pipeline._process_batch(chat_id, [{"chat_id": chat_id, "message_id": message_id, "text": text}])


def test_monitor_rule_excluded_skips_push(plugin, monitor, monkeypatch):
    monitor.save_rules([{
        "id": "r1", "name": "综艺", "source_ids": [CHAT_A],
        "destination": "pan115", "match_only_if_missing": False,
        "match_custom_keywords": True, "custom_keywords": ["综艺"],
        "exclude_keywords": ["加更", "花絮"],
    }])
    pipeline = _build(plugin, monitor, monkeypatch)
    _process(pipeline, CHAT_A, "奔跑吧兄弟 综艺 加更篇 E5\nhttps://115.com/s/swtest?password=abcd")
    logs = query_all(TgHitLog, plugin)
    assert len(logs) == 1
    assert logs[0].decision == DECISION_SKIPPED_EXCLUDED
    assert "加更" in logs[0].detail
    # 正片（无排除词）正常命中推送
    _process(pipeline, CHAT_A, "奔跑吧兄弟 综艺 正片 E6\nhttps://115.com/s/swtest?password=abcd", message_id=2)
    logs = query_all(TgHitLog, plugin)
    assert [log.decision for log in logs] == [DECISION_SKIPPED_EXCLUDED, DECISION_HIT]


def test_monitor_test_text_excluded(plugin, monitor, monkeypatch):
    monitor.save_rules([{
        "id": "r1", "name": "综艺", "source_ids": [CHAT_A],
        "match_only_if_missing": False,
        "match_custom_keywords": True, "custom_keywords": ["综艺"],
        "exclude_keywords": ["花絮"],
    }])
    _build(plugin, monitor, monkeypatch)
    pipeline = pipeline_module.MessagePipeline(plugin, monitor, MediaMatcher(), CooldownGate(0.0))
    data = pipeline.test_text("某综艺 花絮合集 2026")
    trace = data["rules"][0]
    assert trace["decision"] == DECISION_SKIPPED_EXCLUDED
    assert "花絮" in trace["reason"]


def test_forward_rule_excluded_skips_push(plugin, monitor, monkeypatch):
    monitor.save_rules([])
    pipeline = _build(plugin, monitor, monkeypatch)
    rule = {
        "id": "f1", "name": "转发综艺", "source_ids": [CHAT_A],
        "target_id": -1003229693136, "destination": "tg_forward",
        "match_custom_keywords": False, "custom_keywords": [],
        "exclude_keywords": ["加更"],
        "pin_links_enabled": False, "pin_link_keywords": [],
        "match_file_extensions": False, "file_extensions_to_match": [],
        "enable_transform": False, "transform_rules": [],
        "enabled": True,
    }
    pipeline._apply_forward_rule(
        chat_id=CHAT_A, message_id=7, text="综艺 加更 E5 https://t.me/x",
        cleaned="综艺 加更 E5", meta=None,
        links=["https://t.me/x"], rule=rule)
    logs = query_all(TgHitLog, plugin)
    assert len(logs) == 1
    assert logs[0].decision == DECISION_SKIPPED_EXCLUDED
    assert logs[0].kind == "forward"
