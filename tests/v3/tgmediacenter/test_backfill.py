"""存量补扫（modules/cache.py 的 _backfill_* 判定链 + 水位 + 判重）测试。

覆盖：
- scan_messages：after_created / after_id 过滤与视图字段
- 判定链：无链接 / 判重（任意路径推过都跳过）/ 不缺 / 未识别 / P9 拦截 / 入队
- 水位：首次增量建基线不翻历史；扫完推进水位；全量结束后水位=最新
- 并发：运行中不允许重复触发；取消后停止
- 通知：推了才发汇总，没推静默
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.plugins.tgmediacenter.core import push_queue as push_queue_module
from app.plugins.tgmediacenter.model.hit_log import DECISION_HIT, TgHitLog
from app.plugins.tgmediacenter.model.message_cache import TgMessageCache
from app.plugins.tgmediacenter.modules import cache as cache_mod
from app.plugins.tgmediacenter.modules.cache import (
    _BACKFILL_STATE_KEY,
    _BACKFILL_WATERMARK_KEY,
    CACHE_BACKFILL_RULE_ID,
    CacheModule,
)

CHAT = -100123


# --------------------------------------------------------------------- 替身


class _Db:
    """内存 SQLite 插件库（session 是方法，与宿主一致）。"""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        TgMessageCache.__table__.create(self.engine)
        TgHitLog.__table__.create(self.engine)
        self._factory = sessionmaker(bind=self.engine)

    def session(self):
        return self._factory()


class _Plugin:
    def __init__(self, config: dict | None = None) -> None:
        self._config = dict(config or {})
        self._data: dict = {}
        self._db = _Db()
        self._credentials = None
        self.messages: list = []

    @property
    def config(self) -> dict:
        return self._config

    def save_config(self, **patch) -> None:
        self._config.update(patch)

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value

    def get_database(self):
        return self._db

    def post_message(self, title="", text="") -> None:
        self.messages.append({"title": title, "text": text})


class _Matcher:
    """is_missing 替身：按 (title, episode) 查表给结论。"""

    def __init__(self, missing=True, reason="媒体库缺失", source="mediaserver") -> None:
        self.missing = missing
        self.reason = reason
        self.source = source
        self.calls: list = []

    def is_missing(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "missing": self.missing,
            "reason": self.reason,
            "source": self.source,
            "detail": "",
        }


@pytest.fixture
def module():
    """开启缓存 + 补扫的 CacheModule（真库、替身 matcher / 闸门 / 推送队列）。"""
    plugin = _Plugin({
        "enabled": True,
        "cache_enabled": True,
        "cache_chat_ids": [CHAT],
        "cache_destination": "pan115",
        "cache_backfill_enabled": True,
        "cache_backfill_cron": "*/30 * * * *",
    })
    mod = CacheModule(plugin)
    mod._matcher = _Matcher()
    return mod


def _gate(passed=True, reason="放行"):
    return SimpleNamespace(
        check=lambda meta, missing: SimpleNamespace(
            action="pass" if passed else "skip", reason=reason,
            decision=None if passed else "skipped_pt_active", degraded=False, passed=passed,
        )
    )


def _patch_push(monkeypatch, fail=False):
    calls = []

    def fake_enqueue(db, plugin_id, **kwargs):
        calls.append(kwargs)
        return 0 if fail else len(calls)

    monkeypatch.setattr(cache_mod, "push_queue",
                        SimpleNamespace(enqueue_push=fake_enqueue))
    return calls


def _insert_cache(mod, *, message_id=1, title="测试剧", episode=5, created=None,
                  links=None):
    db = mod._db()
    row = TgMessageCache(
        plugin_id=mod._plugin_id(), chat_id=CHAT, message_id=message_id,
        message_date=created or datetime.now(),
        text="x", links_json=json.dumps(links if links is not None else ["https://115.com/s/abc"]),
        parsed_title=title, title_norm=title.lower(), year="2026", season=1,
        episode=episode, episode_end=None, media_type="tv",
        created_at=created or datetime.now(),
    )
    with db.session() as session:
        session.add(row)
        session.commit()
        return int(row.id)


def _hit(mod, *, message_id, rule_id="cache_search", decision=DECISION_HIT):
    with mod._db().session() as session:
        session.add(TgHitLog(
            plugin_id=mod._plugin_id(), rule_id=rule_id, rule_name="x",
            chat_id=CHAT, message_id=message_id, title="t", year="2026",
            season=1, episode=1, media_type="tv", decision=decision,
            destination="pan115", target_id="", detail="",
        ))
        session.commit()


# --------------------------------------------------------------------- scan_messages


def test_scan_messages_filters_and_view(module):
    old = datetime.now() - timedelta(hours=3)
    id_old = _insert_cache(module, message_id=1, created=old)
    id_new = _insert_cache(module, message_id=2, created=datetime.now())
    # after_created 只取新消息
    rows = module._history.scan_messages(
        [CHAT], after_created=datetime.now() - timedelta(minutes=5), limit=10)
    assert [r["id"] for r in rows] == [id_new]
    # after_id 游标翻页
    rows = module._history.scan_messages([CHAT], after_id=id_new, limit=10)
    assert rows == []
    rows = module._history.scan_messages([CHAT], after_id=id_old - 1, limit=10)
    assert [r["id"] for r in rows] == [id_old, id_new]
    assert rows[0]["created_at"] and rows[0]["episode"] == 5


def test_scan_messages_other_chat_excluded(module):
    _insert_cache(module, message_id=1)
    rows = module._history.scan_messages([-100999], limit=10)
    assert rows == []


# --------------------------------------------------------------------- 判定链


def test_backfill_pushes_missing(module, monkeypatch):
    calls = _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=10)
    result = module.start_backfill(full=True)
    assert result["started"]
    _wait(module)
    assert len(calls) == 1
    assert calls[0]["rule_id"] == CACHE_BACKFILL_RULE_ID
    assert calls[0]["destination"] == "pan115"
    # 落了补扫流水
    with module._db().session() as session:
        rows = list(session.execute(select(TgHitLog)).scalars().all())
    assert len(rows) == 1 and rows[0].rule_id == CACHE_BACKFILL_RULE_ID
    # 推了才发通知
    assert len(module._plugin.messages) == 1
    assert module._plugin.messages[0]["title"].endswith("存量补扫")


def test_backfill_dedup_any_rule(module, monkeypatch):
    """判重口径：任意路径（回搜/监控/补扫）推过都跳过，不局限补扫本人。"""
    _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=11)
    _hit(module, message_id=11, rule_id="monitor_r1")
    module.start_backfill(full=True)
    _wait(module)
    state = module.backfill_state()
    assert state["pushed"] == 0 and state["skipped"] == 1


def test_backfill_skips_no_links_and_unrecognized(module, monkeypatch):
    _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=12, links=[])
    _insert_cache(module, message_id=13, title="")
    module.start_backfill(full=True)
    _wait(module)
    assert module.backfill_state()["pushed"] == 0


def test_backfill_skips_when_not_missing(module, monkeypatch):
    _patch_push(monkeypatch)
    module._matcher = _Matcher(missing=False, source="mediaserver", reason="媒体库已存在")
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=14)
    module.start_backfill(full=True)
    _wait(module)
    assert module.backfill_state()["pushed"] == 0


def test_backfill_p9_gate_blocks(module, monkeypatch):
    """媒体库缺但 PT 在途（前向闸门拦截）→ 跳过。"""
    _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=False, reason="PT 在途（1 个活跃种，最高进度 40%）")
    _insert_cache(module, message_id=15)
    module.start_backfill(full=True)
    _wait(module)
    state = module.backfill_state()
    assert state["pushed"] == 0 and state["skipped"] == 1


def test_backfill_enqueue_failure_counts_skipped(module, monkeypatch):
    _patch_push(monkeypatch, fail=True)
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=16)
    module.start_backfill(full=True)
    _wait(module)
    assert module.backfill_state()["pushed"] == 0


def test_backfill_passes_meta_to_gate(module, monkeypatch):
    """闸门收到的 meta 必须带齐 title/year/media_type/season/episode（集粒度）。"""
    _patch_push(monkeypatch)
    seen = {}
    gate = SimpleNamespace(check=lambda meta, missing: (seen.update(meta), SimpleNamespace(
        action="pass", reason="", decision=None, degraded=False, passed=True))[1])
    module._p9_gate = gate
    _insert_cache(module, message_id=17)
    module.start_backfill(full=True)
    _wait(module)
    assert seen == {"title": "测试剧", "year": "2026", "media_type": "tv",
                    "season": 1, "episode": 5}


# --------------------------------------------------------------------- 水位与并发


def test_first_increment_builds_baseline_only(module, monkeypatch):
    """首次增量：只建水位基线，不翻历史缓存。"""
    calls = _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=20)
    module.run_backfill_job()
    _wait(module)
    assert calls == []
    assert module.backfill_state()["watermark"]


def test_increment_only_scans_new_rows(module, monkeypatch):
    """水位之后的新消息才被补扫；旧消息留给全量。"""
    calls = _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    old = datetime.now() - timedelta(hours=5)
    _insert_cache(module, message_id=30, created=old)
    module.run_backfill_job()  # 建基线
    _wait(module)
    _insert_cache(module, message_id=31, created=datetime.now())
    module.run_backfill_job()  # 增量
    _wait(module)
    assert len(calls) == 1
    assert calls[0]["message_id"] == 31


def test_full_scan_updates_watermark_to_latest(module, monkeypatch):
    module._p9_gate = _gate(passed=True)
    _patch_push(monkeypatch)
    old = datetime.now() - timedelta(days=2)
    id_row = _insert_cache(module, message_id=40, created=old)
    module.start_backfill(full=True)
    _wait(module)
    watermark = module.backfill_state()["watermark"]
    assert watermark  # 全量结束后水位推进到最新入库时间
    assert watermark >= module._history.scan_messages([CHAT], limit=1)[0]["created_at"]


def test_start_backfill_rejects_concurrent(module, monkeypatch):
    _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    module._backfill_state["running"] = True
    result = module.start_backfill(full=True)
    assert not result["started"]
    module._backfill_state["running"] = False


def test_cancel_backfill_stops_loop(module, monkeypatch):
    """取消后 worker 不再处理后续批次（首条处理后置取消标记）。"""
    calls = _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    for mid in range(50, 55):
        _insert_cache(module, message_id=mid)
    original = module._backfill_one

    def first_then_cancel(item):
        outcome = original(item)
        module._backfill_cancel.set()
        return outcome

    monkeypatch.setattr(module, "_backfill_one", first_then_cancel)
    module.start_backfill(full=True)
    _wait(module)
    assert module.backfill_state()["pushed"] <= 1


def test_start_backfill_requires_cache_enabled(module, monkeypatch):
    _patch_push(monkeypatch)
    module._plugin._config["cache_chat_ids"] = []
    result = module.start_backfill(full=True)
    assert not result["started"]


def test_state_persisted_across_rebuild(module, monkeypatch):
    """运行摘要落插件数据，重建模块后仍可读（跨重启）。"""
    _patch_push(monkeypatch)
    module._p9_gate = _gate(passed=True)
    _insert_cache(module, message_id=60)
    module.start_backfill(full=True)
    _wait(module)
    rebuilt = CacheModule(module._plugin)
    state = rebuilt.backfill_state()
    assert state["last_run_at"] and state["last_run_pushed"] == 1


# --------------------------------------------------------------------- 工具


def _wait(module, timeout: float = 5.0) -> None:
    """等后台补扫线程收尾（start 已启动线程；cancel/异常路径同样收敛）。"""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not module._backfill_state.get("running"):
            return
        time.sleep(0.01)
    raise AssertionError("补扫线程未在超时内结束")
