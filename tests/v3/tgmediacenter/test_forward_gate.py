"""P9 前向闸门 A（services/forward_gate.py）的判定链测试。

覆盖规格 §3.3 结论表的关键分支 + §8 的 fail-open 纪律：
- 闸门未启用 → 不参与判定（现状行为）
- 查询失败 → 放行且标记 degraded（绝不静默拦截）
- 无记录 + 未满成熟期 → skipped_pt_waiting；超期 → 放行
- 有记录 + 有活跃种 → skipped_pt_active；无活跃种（死种）→ 放行
- 关闭活跃性细化 / 记录无 hash → 保守 skipped_pt_active
- 锚点维护：缺失时 touch、入库后 clear
- _decision_for_skip 尊重 verdict 显式携带的 decision
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.plugins.tgmediacenter.services import forward_gate as fg


# --------------------------------------------------------------------- 测试替身


class _StubMatcher:
    """订阅桥替身：返回预设的 (media_source, media_id)。"""

    def __init__(self, pair=("themoviedb", "12345")):
        self.pair = pair
        self.calls = []

    def subscription_identity(self, *, title, year, season):
        self.calls.append((title, year, season))
        return self.pair


class _StubStore:
    """锚点表替身：内存字典。"""

    def __init__(self):
        self.anchors = {}
        self.cleared = []
        self.touched = []

    def first_missing_at(self, key):
        return self.anchors.get(key)

    def touch(self, key):
        self.touched.append(key)
        self.anchors.setdefault(key, datetime.now())

    def clear(self, key):
        self.cleared.append(key)
        self.anchors.pop(key, None)


class _FakePage:
    def __init__(self, items):
        self.items = items


@pytest.fixture
def gate_env(monkeypatch):
    """搭建一个可注入的闸门环境：返回 (ForwardGate, matcher, store, config)。"""
    config = {
        "p9_forward_gate_enabled": True,
        "p9_maturity_hours": 2,
        "p9_check_downloader": True,
    }
    matcher = _StubMatcher()
    store = _StubStore()
    gate = fg.ForwardGate(
        matcher=matcher, store=store, config_getter=lambda: dict(config)
    )
    monkeypatch.setattr(fg, "HISTORY_QUERIES_AVAILABLE", True)
    monkeypatch.setattr(fg, "DOWNLOADER_AVAILABLE", True)
    return gate, matcher, store, config


def _patch_history(monkeypatch, records):
    """替身下载历史查询：把 filters 记下来并返回固定页。"""
    calls = []

    def fake_list_download_history(filters, page=None):
        calls.append(dict(filters))
        return _FakePage([SimpleNamespace(**r) for r in records])

    monkeypatch.setattr(fg, "list_download_history", fake_list_download_history)
    return calls


def _patch_torrents(monkeypatch, torrents, fail=False):
    """替身下载器查询。"""

    class _Svc:
        name = "qb"
        module = None
        instance = None

    def _make(state="downloading", progress=50.0):
        return SimpleNamespace(state=SimpleNamespace(value=state), progress=progress)

    class _Module:
        def list_torrents(self, hashs=None):
            if fail:
                raise RuntimeError("downloader down")
            return torrents

    svc = _Svc()
    svc.module = _Module()
    monkeypatch.setattr(fg, "DownloaderHelper", lambda: SimpleNamespace(
        get_services=lambda: {"qb": svc}))


def _record(hash_="abc", season=None, date=None):
    return {
        "title": "测试剧", "year": "2026", "seasons": season,
        "episodes": "E01", "download_hash": hash_, "date": date,
    }


_META = {"title": "测试剧", "year": "2026", "media_type": "tv", "season": 1}


# --------------------------------------------------------------------- 用例


def test_disabled_gate_returns_none(gate_env):
    """A0 总开关默认关 → check 返回 None（完全维持现状）。"""
    gate, _m, _s, config = gate_env
    config["p9_forward_gate_enabled"] = False
    assert gate.check(_META, missing=True) is None


def test_history_query_failure_fails_open(gate_env, monkeypatch):
    """查询失败 → 放行 + degraded（§8 fail-open，绝不静默拦截）。"""
    gate, _m, _s, _c = gate_env

    def boom(filters, page=None):
        raise RuntimeError("sdk 失配")

    monkeypatch.setattr(fg, "list_download_history", boom)
    result = gate.check(_META, missing=True)
    assert result.passed and result.degraded


def test_no_records_within_maturity_waits(gate_env, monkeypatch):
    """无下载记录 + 有锚点 + 未满 T → skipped_pt_waiting。"""
    gate, _m, store, _c = gate_env
    store.anchors["测试剧|2026|tv|1"] = datetime.now() - timedelta(minutes=30)
    _patch_history(monkeypatch, [])
    result = gate.check(_META, missing=True)
    assert not result.passed
    assert result.decision == fg.DECISION_SKIPPED_PT_WAITING


def test_no_records_past_maturity_passes(gate_env, monkeypatch):
    """无下载记录 + 超过成熟期 → 放行（TG 补）。"""
    gate, _m, store, _c = gate_env
    store.anchors["测试剧|2026|tv|1"] = datetime.now() - timedelta(hours=3)
    _patch_history(monkeypatch, [])
    result = gate.check(_META, missing=True)
    assert result.passed and not result.degraded


def test_no_records_without_anchor_passes(gate_env, monkeypatch):
    """无记录且无锚点（如库迁移失败）→ 降级放行，绝不永久拦截。

    直接调 evaluate：check() 入口必先 touch，无锚点场景只有库异常时才出现。
    """
    gate, _m, _s, _c = gate_env
    _patch_history(monkeypatch, [])
    result = gate.evaluate(_META)
    assert result.passed and result.degraded


def test_records_with_active_torrent_skips(gate_env, monkeypatch):
    """有记录 + 活跃种 → skipped_pt_active。"""
    gate, _m, _s, _c = gate_env
    _patch_history(monkeypatch, [_record(season="S01")])
    _patch_torrents(monkeypatch, [SimpleNamespace(
        state=SimpleNamespace(value="downloading"), progress=42.0)])
    result = gate.check(_META, missing=True)
    assert not result.passed
    assert result.decision == fg.DECISION_SKIPPED_PT_ACTIVE


def test_records_with_dead_torrent_passes(gate_env, monkeypatch):
    """有记录 + 无活跃种（死种/已清）→ 立即放行，不等 T（§12 决策 4）。"""
    gate, _m, _s, _c = gate_env
    _patch_history(monkeypatch, [_record(season="S01")])
    _patch_torrents(monkeypatch, [SimpleNamespace(
        state=SimpleNamespace(value="completed"), progress=100.0)])
    result = gate.check(_META, missing=True)
    assert result.passed and not result.degraded


def test_downloader_failure_fails_open(gate_env, monkeypatch):
    """下载器查询失败 → 放行 + degraded（活种查不到 ≠ PT 没在管）。"""
    gate, _m, _s, _c = gate_env
    _patch_history(monkeypatch, [_record(season="S01")])
    _patch_torrents(monkeypatch, [], fail=True)
    result = gate.check(_META, missing=True)
    assert result.passed and result.degraded


def test_check_downloader_disabled_conservative_skip(gate_env, monkeypatch):
    """关闭活跃性细化 → 有记录即视为在管（保守跳过）。"""
    gate, _m, _s, config = gate_env
    config["p9_check_downloader"] = False
    _patch_history(monkeypatch, [_record(season="S01")])
    result = gate.check(_META, missing=True)
    assert not result.passed
    assert result.decision == fg.DECISION_SKIPPED_PT_ACTIVE


def test_records_without_hash_conservative_skip(gate_env, monkeypatch):
    """记录全无 hash（异常数据）→ 保守视为在管，绝不放行造成重复。"""
    gate, _m, _s, _c = gate_env
    _patch_history(monkeypatch, [_record(hash_="", season="S01")])
    result = gate.check(_META, missing=True)
    assert not result.passed
    assert result.decision == fg.DECISION_SKIPPED_PT_ACTIVE


def test_records_outside_window_ignored(gate_env, monkeypatch):
    """窗口外的旧记录（> T）不算"有记录"→ 走成熟期等待分支。"""
    gate, _m, store, _c = gate_env
    store.anchors["测试剧|2026|tv|1"] = datetime.now() - timedelta(hours=3)
    old = (datetime.now() - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")
    _patch_history(monkeypatch, [_record(season="S01", date=old)])
    result = gate.check(_META, missing=True)
    # 旧记录被窗口滤掉 → 无记录分支；锚点已 3h > 2h → 放行
    assert result.passed


def test_records_of_other_season_ignored(gate_env, monkeypatch):
    """其他季的下载记录不算本季"在管"→ 走成熟期分支。"""
    gate, _m, store, _c = gate_env
    store.anchors["测试剧|2026|tv|1"] = datetime.now() - timedelta(minutes=10)
    _patch_history(monkeypatch, [_record(season="S02")])
    result = gate.check(_META, missing=True)
    assert not result.passed
    assert result.decision == fg.DECISION_SKIPPED_PT_WAITING


def test_check_touches_anchor_on_missing_and_clears_on_exists(gate_env, monkeypatch):
    """锚点维护：确认缺失 → touch；媒体库已有 → clear（规格 §7）。"""
    gate, _m, store, _c = gate_env
    _patch_history(monkeypatch, [_record(season="S01")])
    _patch_torrents(monkeypatch, [])
    gate.check(_META, missing=True)
    assert store.touched == ["测试剧|2026|tv|1"]
    gate.check(_META, missing=False)
    assert store.cleared == ["测试剧|2026|tv|1"]


def test_subscription_bridge_used_for_precise_query(gate_env, monkeypatch):
    """订阅桥：身份对可用时用 media_source+media_id 精确查。"""
    gate, matcher, _s, _c = gate_env
    calls = _patch_history(monkeypatch, [])
    _patch_torrents(monkeypatch, [])
    gate.check(_META, missing=True)
    assert calls and calls[0] == {"media_source": "themoviedb", "media_id": "12345"}
    assert matcher.calls  # 桥确实被调用


def test_fallback_to_title_without_subscription(gate_env, monkeypatch):
    """未命中订阅 → 退回 title 过滤（兜底路径）。"""
    gate, matcher, _s, _c = gate_env
    matcher.pair = (None, None)
    calls = _patch_history(monkeypatch, [])
    _patch_torrents(monkeypatch, [])
    gate.check(_META, missing=True)
    assert calls and calls[0] == {"title": "测试剧"}


# --------------------------------------------------------------------- 决策归一


def test_decision_for_skip_honors_explicit_decision():
    """_decision_for_skip 尊重 verdict 显式携带的 decision（规格 §3.4 顺带修）。"""
    from app.plugins.tgmediacenter.core.pipeline import _decision_for_skip

    decision, reason = _decision_for_skip(
        {"missing": True, "reason": "PT 在途", "decision": "skipped_pt_active"})
    assert decision == "skipped_pt_active"
    assert reason == "PT 在途"


def test_decision_for_skip_backcompat_without_decision():
    """无 decision 字段时走旧逻辑（向后兼容）。"""
    from app.plugins.tgmediacenter.core.pipeline import _decision_for_skip

    assert _decision_for_skip({"missing": None})[0] == "skipped_unknown"
    assert _decision_for_skip({"missing": False, "reason": "未订阅"})[0] == "skipped_not_subscribed"
    assert _decision_for_skip({"missing": False, "reason": "媒体库中已存在"})[0] == "skipped_not_missing"


def test_new_decisions_registered_in_hit_log():
    """两个新决策必须进 DECISIONS 与 DECISION_LABELS（三处同步的后端侧）。"""
    from app.plugins.tgmediacenter.model.hit_log import DECISIONS, DECISION_LABELS

    assert "skipped_pt_active" in DECISIONS
    assert "skipped_pt_waiting" in DECISIONS
    assert DECISION_LABELS["skipped_pt_active"] == "PT 在途"
    assert DECISION_LABELS["skipped_pt_waiting"] == "等 PT 成熟期"
