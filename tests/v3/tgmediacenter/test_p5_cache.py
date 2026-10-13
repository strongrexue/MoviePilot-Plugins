"""P5 历史消息缓存测试。

覆盖：写入幂等与位点推进 / 归一标题检索与全文兜底 / 时间窗口解析 /
位点增量同步 / 统计与清空 / 订阅快照对比与回搜推送（含基线与去重）/
缓存设置归一 / 状态接口 / 流水线缓存写入与关心会话判定 / API 层。

宿主依赖（MetaVideo / list_subscriptions / 插件 DB / TG 运行时）在测试里用
可注入的替身驱动——真机行为仍以部署验证为准。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.plugins.tgmediacenter.controller import api as controller_api
from app.plugins.tgmediacenter.controller import schemas as api_schemas
from app.plugins.tgmediacenter.core import history_cache as history_module
from app.plugins.tgmediacenter.core import pipeline as pipeline_module
from app.plugins.tgmediacenter.core.cooldown import CooldownGate
from app.plugins.tgmediacenter.core.history_cache import (
    MODE_ABSOLUTE,
    MODE_ALL,
    MODE_RELATIVE,
    HistoryCacheService,
)
from app.plugins.tgmediacenter.model.hit_log import DECISION_HIT, TgHitLog
from app.plugins.tgmediacenter.model.message_cache import TgMessageCache
from app.plugins.tgmediacenter.model.push_task import STATUS_PENDING, TgPushTask
from app.plugins.tgmediacenter.modules.cache import CACHE_SEARCH_RULE_ID, CacheModule
from app.plugins.tgmediacenter.modules.monitor import MonitorModule
from app.plugins.tgmediacenter.services import matcher as matcher_module
from app.plugins.tgmediacenter.services import recognizer as recognizer_module
from app.plugins.tgmediacenter.services.matcher import MediaMatcher

CHAT_A = -1004316104321
CHAT_B = -1003751539830
LINK = "https://115.com/s/swabc123?password=abcd"


def _text(title_line: str, link: str = LINK) -> str:
    """拼一条真实格式的频道消息（标题行 + 链接行，链接必须在独立行）。"""
    return f"{title_line}\n🔗 链接: {link}"


# ---------------------------------------------------------------------- 测试替身


class FakeType:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeMetaVideo:
    """``名称 (年份) S01E02`` → 剧集；``名称 (年份)`` → 电影（贴近真实播报格式）。"""

    def __init__(self, title: str, subtitle=None, isfile: bool = False) -> None:
        self.org_string = title
        self.subtitle = subtitle
        self.isfile = isfile
        self.resource_type = ""
        self.resource_pix = ""
        self.video_encode = ""
        self.year = ""
        self.begin_season = None
        self.begin_episode = None
        self.end_episode = None
        match = re.search(r"S(\d+)E(\d+)(?:-E?(\d+))?", title, re.IGNORECASE)
        year = re.search(r"(19|20)\d{2}", title)
        if year:
            self.year = year.group(0)
        clean = re.sub(r"S\d+E\d+(?:-E?\d+)?", "", title, flags=re.IGNORECASE)
        clean = re.sub(r"[（(]?(?:19|20)\d{2}[）)]?", "", clean)
        self.name = clean.strip(" .·-_（）()")
        if match:
            self.begin_season = int(match.group(1))
            self.begin_episode = int(match.group(2))
            if match.group(3):
                self.end_episode = int(match.group(3))
            self.type = FakeType("电视剧")
        else:
            self.type = FakeType("电影")


class FakeDatabase:
    """内存 SQLite 插件数据库句柄（session 是方法，与宿主一致）。"""

    def __init__(self) -> None:
        # StaticPool + check_same_thread=False：同一内存库跨线程/跨 session 共享连接，
        # 否则后台同步线程新建的连接看不到主连接里建好的表。
        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        TgMessageCache.__table__.create(self.engine)
        TgHitLog.__table__.create(self.engine)
        TgPushTask.__table__.create(self.engine)
        self._factory = sessionmaker(bind=self.engine)

    def session(self):
        return self._factory()


class FakePlugin:
    """鸭子类型的插件对象：配置 / 数据 / 数据库 / 通知。"""

    def __init__(self, config: dict | None = None) -> None:
        self._config = dict(config or {})
        self._data: dict = {}
        self._db = FakeDatabase()
        self._credentials = None
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
    """缺失判断替身（订阅门禁语义）。"""

    def __init__(self, missing=True) -> None:
        self.missing = missing
        self.calls = 0

    def is_missing(self, **kwargs):
        self.calls += 1
        if self.missing:
            return {"missing": True, "reason": "订阅缺 3 集", "source": "subscription", "detail": ""}
        return {"missing": False, "reason": "订阅已存在且无缺集", "source": "subscription", "detail": ""}


class FakeSubscription:
    def __init__(self, name, year="", season=None, media_source="themoviedb", media_id="", lack_episode=2):
        self.name = name
        self.year = year
        self.season = season
        self.media_source = media_source
        self.media_id = media_id
        self.lack_episode = lack_episode
        self.state = "R"


class FakeQueryPage:
    def __init__(self, items) -> None:
        self.items = list(items)
        self.total = len(self.items)


class FakeRuntime:
    """TG 运行时替身：``call`` 直接返回预置批次（不真的跑协程）。"""

    def __init__(self, batches) -> None:
        self._batches = list(batches)
        self.calls = 0

    @property
    def client(self):
        return object()

    def call(self, coro, timeout=0):
        try:
            coro.close()
        except Exception:
            pass
        if self.calls < len(self._batches):
            batch = self._batches[self.calls]
        else:
            batch = {"messages": []}
        self.calls += 1
        return batch


def _msg(message_id: int, title_line: str, *, hours_ago: float = 0.0, link: str = LINK) -> dict:
    """构造一条已处理好的拉取结果（与 _fetch_batch 的输出结构一致）。"""
    date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours_ago)
    text = _text(title_line, link)
    return {
        "id": message_id,
        "date": date,
        "text": text,
        "meta": recognizer_module.recognize(text),
        "links": [link],
    }


@pytest.fixture()
def fake_metavideo(monkeypatch):
    monkeypatch.setattr(recognizer_module, "META_AVAILABLE", True)
    monkeypatch.setattr(recognizer_module, "MetaVideo", FakeMetaVideo)
    return FakeMetaVideo


@pytest.fixture()
def plugin():
    return FakePlugin({
        "enabled": True,
        "cache_enabled": True,
        "cache_chat_ids": [CHAT_A],
    })


@pytest.fixture()
def cache(plugin):
    module = CacheModule(plugin)
    plugin._cache = module
    return module


@pytest.fixture()
def service(plugin):
    return HistoryCacheService(plugin)


def _count(plugin, model=TgMessageCache) -> int:
    with plugin.get_database().session() as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar() or 0)


def _pending_tasks(plugin) -> list:
    with plugin.get_database().session() as session:
        return list(session.execute(select(TgPushTask)).scalars().all())


# ---------------------------------------------------------------------- 写入


class TestRecord:
    def test_record_is_idempotent(self, plugin, service, fake_metavideo):
        text = _text("📺 电视剧：青与碧 (2026) S01E02")
        assert service.record(CHAT_A, 1001, text) is True
        # 同频道同消息再写一次：幂等跳过
        assert service.record(CHAT_A, 1001, text) is False
        assert _count(plugin) == 1

    def test_record_does_not_advance_cursor(self, plugin, service, fake_metavideo):
        """实时写入不得推进同步位点：否则回溯从频道最新处开始，历史全部漏掉（1.4.0 实测踩坑）。"""
        service.record(CHAT_A, 1001, _text("青与碧 (2026) S01E02"))
        assert service.cursor_of(CHAT_A) == 0
        # 位点仍只前进不后退
        service.set_cursor(CHAT_A, 900)
        service.record(CHAT_A, 500, _text("青与碧 (2026) S01E01"))
        assert service.cursor_of(CHAT_A) == 900

    def test_record_skips_empty_text(self, plugin, service):
        assert service.record(CHAT_A, 1002, "   ") is False
        assert _count(plugin) == 0

    def test_record_keeps_raw_text_when_purified_empty(self, plugin, service, fake_metavideo):
        # 整条都是广告行 → 净化后为空，但要保留原文（否则检索不到）
        assert service.record(CHAT_A, 1003, "加入群组 https://t.me/xxx") is True
        with plugin.get_database().session() as session:
            row = session.execute(select(TgMessageCache)).scalars().first()
        assert "加入群组" in row.text


# ---------------------------------------------------------------------- 检索


class TestSearch:
    def test_search_matches_normalized_title(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 2001, _text("青与碧 (2026) S01E02"))
        items = service.search("青与碧")
        assert len(items) == 1
        assert items[0]["message_id"] == 2001
        assert items[0]["title"] == "青与碧"
        assert items[0]["episode"] == 2

    def test_search_falls_back_to_full_text(self, plugin, service, fake_metavideo):
        # 识别失败的脏消息（标题为空）也要能被全文搜到
        service.record(CHAT_A, 2002, _text("Https: 115 Com 玉簟秋 S01 全集"))
        items = service.search("玉簟秋")
        assert len(items) == 1
        assert items[0]["message_id"] == 2002

    def test_search_by_title_uses_contains(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 2003, _text("青与碧 (2026) S01E03"))
        hits = service.search_by_title("青与碧")
        assert [item["message_id"] for item in hits] == [2003]

    def test_search_returns_empty_for_unknown(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 2004, _text("青与碧 (2026) S01E04"))
        assert service.search("不存在的片名") == []
        assert service.search("") == []


# ---------------------------------------------------------------------- 同步


class TestSync:
    def test_time_window_relative(self):
        since, until = HistoryCacheService._time_window(MODE_RELATIVE, 7, "", "")
        assert until is None
        assert since is not None
        delta = datetime.now(timezone.utc).replace(tzinfo=None) - since
        assert 6.9 < delta.total_seconds() / 86400 < 7.1

    def test_time_window_absolute(self):
        since, until = HistoryCacheService._time_window(MODE_ABSOLUTE, 30, "2026-01-01", "2026-01-31")
        assert since.isoformat().startswith("2026-01-01")
        assert until.hour == 23 and until.minute == 59

    def test_time_window_all(self):
        assert HistoryCacheService._time_window(MODE_ALL, 30, "", "") == (None, None)

    def test_sync_pulls_batches_and_advances_cursor(self, plugin, fake_metavideo):
        service = HistoryCacheService(plugin)
        runtime = FakeRuntime([
            {"messages": [_msg(1, _text("青与碧 (2026) S01E01")),
                          _msg(2, _text("青与碧 (2026) S01E02"))]},
            {"messages": []},
        ])
        started = service.start_sync([CHAT_A], mode=MODE_ALL, runtime=runtime, batch=2)
        assert started["started"] is True
        service._thread.join(timeout=10)
        assert _count(plugin) == 2
        assert service.cursor_of(CHAT_A) == 2
        progress = service.progress()
        assert progress["running"] is False
        assert progress["inserted"] == 2

    def test_sync_skips_blank_text_but_advances(self, plugin, fake_metavideo):
        """无正文消息不入库（与真实拉取口径一致），但位点照常推进防重复扫描。"""
        service = HistoryCacheService(plugin)
        runtime = FakeRuntime([
            {"messages": [{"id": 5, "date": None, "text": "   ", "meta": None, "links": []}]},
            {"messages": []},
        ])
        service.start_sync([CHAT_A], mode=MODE_ALL, runtime=runtime, batch=1)
        service._thread.join(timeout=10)
        assert _count(plugin) == 0
        assert service.cursor_of(CHAT_A) == 5

    def test_sync_filters_by_since(self, plugin, fake_metavideo):
        service = HistoryCacheService(plugin)
        old = _msg(10, _text("老资源 (2020) S01E01"), hours_ago=24 * 40)
        fresh = _msg(11, _text("新资源 (2026) S01E01"), hours_ago=2)
        runtime = FakeRuntime([{"messages": [old, fresh]}])
        service.start_sync([CHAT_A], mode=MODE_RELATIVE, days=30, runtime=runtime, batch=50)
        service._thread.join(timeout=10)
        assert _count(plugin) == 1
        with plugin.get_database().session() as session:
            row = session.execute(select(TgMessageCache)).scalars().first()
        assert row.message_id == 11
        # 早于下界的消息位点仍推进，避免下次重复扫描
        assert service.cursor_of(CHAT_A) == 11

    def test_sync_requires_runtime(self, plugin):
        service = HistoryCacheService(plugin)
        result = service.start_sync([CHAT_A], mode=MODE_ALL, runtime=None)
        assert result["started"] is False
        assert "TG 未连接" in result["message"]

    def test_sync_rejects_empty_targets(self, plugin):
        service = HistoryCacheService(plugin)
        assert service.start_sync([], mode=MODE_ALL, runtime=FakeRuntime([]))["started"] is False

    def test_sync_continues_when_full_batch_has_media_only(self, plugin, fake_metavideo):
        """满批里混入纯媒体消息：终止判断按原始扫描数，不得提前收工（1.4.0 实测踩坑）。"""
        service = HistoryCacheService(plugin)
        runtime = FakeRuntime([
            # 第 1 批：原始 2 条（1 条纯媒体），scanned=2 == batch → 必须继续
            {"messages": [_msg(1, _text("青与碧 (2026) S01E01"))],
             "scanned": 2, "max_id": 2},
            # 第 2 批：原始 2 条全无正文，scanned=2 → 继续且位点按原始 ID 推进
            {"messages": [], "scanned": 2, "max_id": 4},
            # 第 3 批：空 → 收工
            {"messages": []},
        ])
        service.start_sync([CHAT_A], mode=MODE_ALL, runtime=runtime, batch=2)
        service._thread.join(timeout=10)
        assert _count(plugin) == 1
        assert service.cursor_of(CHAT_A) == 4
        progress = service.progress()
        assert progress["processed"] == 4
        assert progress["inserted"] == 1


# ---------------------------------------------------------------------- 维护


class TestMaintenance:
    def test_stats_reports_counts_and_cursor(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 3001, _text("青与碧 (2026) S01E01"))
        service.set_cursor(CHAT_A, 3001)  # 位点由同步推进，record 不再碰它
        stats = service.stats([CHAT_A, CHAT_B])
        by_id = {item["chat_id"]: item for item in stats}
        assert by_id[CHAT_A]["count"] == 1
        assert by_id[CHAT_A]["cursor"] == 3001
        assert by_id[CHAT_B]["count"] == 0

    def test_clear_removes_rows_and_cursor(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 3002, _text("青与碧 (2026) S01E02"))
        service.set_cursor(CHAT_A, 3002)
        assert service.clear([CHAT_A]) == 1
        assert _count(plugin) == 0
        assert service.cursor_of(CHAT_A) == 0

    def test_total_count(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 3003, _text("青与碧 (2026) S01E03"))
        assert service.total_count() == 1


# ---------------------------------------------------------------------- 订阅回搜


@pytest.fixture()
def subscriptions(monkeypatch):
    """可切换的订阅列表替身。"""
    state = {"items": []}

    def _list():
        return FakeQueryPage(state["items"])

    monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
    monkeypatch.setattr(matcher_module, "list_subscriptions", _list)
    return state


class TestSubscriptionSearch:
    def test_first_run_only_builds_baseline(self, cache, subscriptions, plugin, fake_metavideo):
        subscriptions["items"] = [FakeSubscription("青与碧", year="2026", media_id="123")]
        plugin._cache.history().record(CHAT_A, 4001, _text("青与碧 (2026) S01E01"))
        result = cache.check_subscriptions(trigger="测试")
        assert result["baseline"] is True
        assert result["pushed"] == 0
        assert _count(plugin, TgPushTask) == 0

    def test_baseline_covers_all_pages(self, cache, subscriptions, plugin, fake_metavideo, monkeypatch):
        """宿主无参调用只返回第一页 50 条：基线必须翻页读全量（1.4.0 实测踩坑）。"""
        all_subs = [
            FakeSubscription(f"批量剧集{i:03d}", year="2026", media_id=str(1000 + i))
            for i in range(120)
        ]

        def _paged(filters=None, page=None):
            request = page or {}
            num = int(request.get("page", 1))
            size = int(request.get("count", 50))
            return FakeQueryPage(all_subs[(num - 1) * size: num * size])

        monkeypatch.setattr(matcher_module, "list_subscriptions", _paged)
        result = cache.check_subscriptions(trigger="测试")
        assert result["baseline"] is True
        assert result["subscriptions"] == 120

    def test_subscription_gate_sees_beyond_first_page(self, monkeypatch):
        """订阅门禁必须翻页读全量：排在第 51 个之后的订阅不能被误判「未订阅」。"""
        all_subs = [
            FakeSubscription(f"填充{i:03d}", year="2020", media_id=str(i))
            for i in range(60)
        ]
        all_subs.append(FakeSubscription("青与碧", year="2026", season=1, lack_episode=3, media_id="999"))

        def _paged(filters=None, page=None):
            request = page or {}
            num = int(request.get("page", 1))
            size = int(request.get("count", 50))
            return FakeQueryPage(all_subs[(num - 1) * size: num * size])

        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", _paged)
        result = MediaMatcher().is_missing(
            title="青与碧", year="2026", season=1, require_subscription=True,
        )
        assert result["missing"] is True
        assert "未订阅" not in result["reason"]

    def test_new_subscription_triggers_search_and_push(self, cache, subscriptions, plugin, fake_metavideo):
        # 第一次：建立基线
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        # 缓存里已有目标资源
        cache.history().record(CHAT_A, 4101, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_A, 4102, _text("无关资源 (2026) S01E01", "https://115.com/s/swabc888"))
        # 第二次：订阅列表新增《青与碧》
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", year="2026", media_id="2"),
        ]
        cache._matcher = FakeMatcher(missing=True)
        result = cache.check_subscriptions(trigger="测试")
        assert result["new"] == 1
        assert result["pushed"] == 1
        tasks = _pending_tasks(plugin)
        assert len(tasks) == 1
        assert tasks[0].status == STATUS_PENDING
        assert tasks[0].rule_id == CACHE_SEARCH_RULE_ID
        assert tasks[0].message_id == 4101
        # 命中流水可复盘
        with plugin.get_database().session() as session:
            hits = list(session.execute(select(TgHitLog)).scalars().all())
        assert len(hits) == 1
        assert hits[0].decision == DECISION_HIT
        assert "缓存回搜" in hits[0].detail

    def test_already_pushed_message_not_pushed_twice(self, cache, subscriptions, plugin, fake_metavideo):
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4201, _text("青与碧 (2026) S01E01"))
        cache._matcher = FakeMatcher(missing=True)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 1
        # 删掉订阅再重新加回（快照键变化 → 视为新增），命中流水去重仍然拦住
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 0
        assert _count(plugin, TgPushTask) == 1

    def test_subscription_without_links_is_skipped(self, cache, subscriptions, plugin, fake_metavideo):
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4301, "青与碧 (2026) S01E01 无链接版本")
        cache._matcher = FakeMatcher(missing=True)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        assert result["details"][0]["skipped"] == 1

    def test_missing_check_blocks_already_owned(self, cache, subscriptions, plugin, fake_metavideo):
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4401, _text("青与碧 (2026) S01E01"))
        cache._matcher = FakeMatcher(missing=False)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 0
        assert _count(plugin, TgPushTask) == 0

    def test_notification_sent_when_pushed(self, cache, subscriptions, plugin, fake_metavideo):
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4501, _text("青与碧 (2026) S01E01"))
        cache._matcher = FakeMatcher(missing=True)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        cache.check_subscriptions(trigger="测试")
        assert plugin.messages
        assert "缓存回搜" in plugin.messages[-1]["title"]

    def test_disabled_module_skips_check(self, plugin, fake_metavideo):
        plugin.save_config(cache_enabled=False)
        module = CacheModule(plugin)
        plugin._cache = module
        assert module.check_subscriptions(trigger="测试")["checked"] is False


# ---------------------------------------------------------------------- 设置与状态


class TestSettingsAndStatus:
    def test_settings_normalizes_invalid_values(self, plugin, cache):
        saved = cache.save_settings({
            "enabled": True,
            "chat_ids": [str(CHAT_A), "abc", CHAT_A, CHAT_B],
            "destination": "不存在的目标",
            "sync_mode": "乱七八糟",
            "sync_days": 0,
            "batch_size": 9999,
        })
        assert saved["chat_ids"] == [CHAT_A, CHAT_B]
        assert saved["destination"] == "smart"
        assert saved["sync_mode"] == MODE_RELATIVE
        # 0 视为"未设置"回落到默认 30 天；批量上限收敛到 500
        assert saved["sync_days"] == 30
        assert saved["batch_size"] == 500
        assert saved["enabled"] is True

    def test_save_settings_normalizes_cron(self, plugin, cache):
        # 5 段式才接受；非法值退回默认（非法 cron 会拖垮宿主定时注册）
        saved = cache.save_settings({"cron": "*/30 * * * *", "subscribe_cron": "不是 cron"})
        assert saved["cron"] == "*/30 * * * *"
        assert saved["subscribe_cron"] == "*/5 * * * *"
        assert plugin.config["cache_cron"] == "*/30 * * * *"

    def test_is_cached_chat_respects_enabled(self, plugin, cache):
        assert cache.is_cached_chat(CHAT_A) is True
        assert cache.is_cached_chat(CHAT_B) is False
        plugin.save_config(cache_enabled=False)
        assert cache.is_cached_chat(CHAT_A) is False

    def test_status_payload_matches_schema(self, plugin, cache, fake_metavideo):
        cache.history().record(CHAT_A, 5001, _text("青与碧 (2026) S01E01"))
        payload = cache.status()
        assert payload["chats"] == 1
        assert payload["total"] == 1
        assert payload["channels"][0]["count"] == 1
        validated = api_schemas.CacheStatusData.model_validate(payload)
        assert validated.channels[0].chat_id == CHAT_A
        assert validated.subscribe.enabled is True

    def test_sync_without_channels_reports(self, plugin):
        plugin.save_config(cache_enabled=True, cache_chat_ids=[])
        module = CacheModule(plugin)
        plugin._cache = module
        assert module.sync()["started"] is False


# ---------------------------------------------------------------------- 流水线接线


class TestPipelineWiring:
    def _pipeline(self, plugin):
        # 生产里由 init_plugin 创建缓存模块；流水线的事件入口要读它判定「关心会话」
        plugin._cache = CacheModule(plugin)
        monitor = MonitorModule(plugin)
        plugin._monitor = monitor
        return pipeline_module.MessagePipeline(plugin, monitor, MediaMatcher(), CooldownGate(0.0))

    def test_cache_only_chat_is_processed(self, plugin, fake_metavideo):
        """只有缓存、没有监控规则的频道也要写缓存。"""
        plugin.save_config(cache_enabled=True, cache_chat_ids=[CHAT_A], monitor_enabled=True, monitor_rules=[])
        pipeline = self._pipeline(plugin)
        pipeline._process_batch(
            CHAT_A,
            [{"chat_id": CHAT_A, "message_id": 6001,
              "text": _text("青与碧 (2026) S01E01")}],
        )
        assert _count(plugin) == 1
        assert pipeline.stats()["cache_written"] == 1

    def test_monitor_only_chat_is_not_cached(self, plugin, fake_metavideo):
        plugin.save_config(
            cache_enabled=True, cache_chat_ids=[CHAT_B],
            monitor_enabled=True,
            monitor_rules=[{
                "id": "r1", "name": "规则", "source_ids": [CHAT_A], "destination": "none",
                "match_only_if_missing": False, "enabled": True,
            }],
        )
        pipeline = self._pipeline(plugin)
        pipeline._process_batch(
            CHAT_A,
            [{"chat_id": CHAT_A, "message_id": 6002,
              "text": _text("青与碧 (2026) S01E02")}],
        )
        # 只监控的频道不写缓存，但会产生命中流水（决策为入队或跳过）
        assert _count(plugin, TgMessageCache) == 0

    def test_interested_chat_ids_union(self, plugin, fake_metavideo):
        plugin.save_config(
            cache_enabled=True, cache_chat_ids=[CHAT_B],
            monitor_enabled=True,
            monitor_rules=[{
                "id": "r1", "name": "规则", "source_ids": [CHAT_A], "destination": "none",
                "match_only_if_missing": False, "enabled": True,
            }],
        )
        pipeline = self._pipeline(plugin)
        assert sorted(pipeline._interested_chat_ids()) == sorted([CHAT_A, CHAT_B])
        assert pipeline._purposes(CHAT_A) == ["监控"]
        assert pipeline._purposes(CHAT_B) == ["缓存"]

    def test_event_from_unrelated_chat_is_ignored(self, plugin, fake_metavideo):
        plugin.save_config(cache_enabled=True, cache_chat_ids=[CHAT_A])
        pipeline = self._pipeline(plugin)

        class FakeMessage:
            id = 6003

        class FakeEvent:
            chat_id = -1005555555
            raw_text = _text("青与碧 (2026) S01E03")
            message = FakeMessage()

        pipeline._handle_event(FakeEvent())
        stats = pipeline.stats()
        assert stats["events_unwatched"] == 1
        assert stats["messages_enqueued"] == 0


# ---------------------------------------------------------------------- API 层


class TestCacheApi:
    def test_settings_endpoint_roundtrip(self, plugin, cache):
        data = controller_api.api_cache_settings(plugin).data
        assert data.enabled is True
        assert data.chat_ids == [CHAT_A]

        request = api_schemas.CacheSettingsRequest(chat_ids=[CHAT_B], sync_days=7)
        saved = controller_api.api_cache_settings_save(plugin, request).data
        assert saved.chat_ids == [CHAT_B]
        assert saved.sync_days == 7

    def test_status_endpoint(self, plugin, cache, fake_metavideo):
        payload = controller_api.api_cache_status(plugin).data
        assert payload.enabled is True
        assert isinstance(payload.channels, list)

    def test_search_endpoint_requires_keyword(self, plugin, cache):
        with pytest.raises(HTTPException) as err:
            controller_api.api_cache_search(plugin, api_schemas.CacheSearchRequest(keyword=""))
        assert err.value.status_code == 400

    def test_search_endpoint(self, plugin, cache, fake_metavideo):
        cache.history().record(CHAT_A, 7001, _text("青与碧 (2026) S01E01"))
        data = controller_api.api_cache_search(
            plugin, api_schemas.CacheSearchRequest(keyword="青与碧")
        ).data
        assert data.total == 1
        assert data.items[0].message_id == 7001

    def test_sync_endpoint_reports_unavailable(self, plugin, cache):
        data = controller_api.api_cache_sync(plugin, api_schemas.CacheSyncRequest()).data
        assert data.started is False
        assert "TG 未连接" in data.message

    def test_cancel_endpoint_when_idle(self, plugin, cache):
        data = controller_api.api_cache_cancel(plugin).data
        assert data.stopped is False
        assert "没有" in data.message

    def test_clear_endpoint(self, plugin, cache, fake_metavideo):
        cache.history().record(CHAT_A, 7002, _text("青与碧 (2026) S01E02"))
        data = controller_api.api_cache_clear(plugin, api_schemas.CacheClearRequest(chat_ids=[CHAT_A])).data
        assert data.deleted == 1

    def test_check_subscriptions_endpoint(self, plugin, cache, subscriptions, fake_metavideo):
        subscriptions["items"] = [FakeSubscription("青与碧", media_id="9")]
        data = controller_api.api_cache_check_subscriptions(plugin).data
        assert data.checked is True
        assert data.subscriptions == 1


# ---------------------------------------------------------------------- 表结构与迁移


class TestBigintAndMatcherStatus:
    def test_push_task_columns_are_bigint(self):
        """push_task 的 chat_id/message_id 必须 BigInteger：TG 频道 ID（约 ±1e12）
        超出 int32，Postgres 入队会 NumericValueOutOfRange（1.4.1 真机踩坑）。"""
        from sqlalchemy import BigInteger

        assert isinstance(TgPushTask.__table__.c.chat_id.type, BigInteger)
        assert isinstance(TgPushTask.__table__.c.message_id.type, BigInteger)

    def test_migration_is_safe_noop_on_sqlite(self, plugin):
        """sqlite 类型宽松：迁移函数直接跳过且不抛错。"""
        from app.plugins.tgmediacenter.model.migration import ensure_bigint_columns

        ensure_bigint_columns(plugin.get_database())
        ensure_bigint_columns(None)  # db 缺省也不抛

    def test_status_includes_matcher_sources(self, plugin, cache, subscriptions):
        """状态接口带缺失判断数据源（媒体服务器名 + 订阅总量），供前端徽章展示。"""
        subscriptions["items"] = [
            FakeSubscription(f"剧集{i}", year="2026", media_id=str(i)) for i in range(3)
        ]
        status = cache.status()
        assert status["matcher"]["queries_available"] is True
        assert status["matcher"]["subscriptions"] == 3


# ---------------------------------------------------------------------- 订阅事件（实时回搜）


class FakeEventManager:
    """记录注册与移除的事件总线替身。"""

    def __init__(self) -> None:
        self.added: list = []
        self.removed: list = []

    def add_event_listener(self, event_type, handler) -> None:
        self.added.append((event_type, handler))

    def remove_event_listener(self, event_type, handler) -> None:
        self.removed.append((event_type, handler))


class _FakeEventType:
    SubscribeAdded = "subscribe.added"


@pytest.fixture()
def fake_eventmanager(monkeypatch):
    import sys
    import types

    manager = FakeEventManager()
    events_mod = types.ModuleType("app.sdk.events")
    events_mod.eventmanager = manager
    types_mod = types.ModuleType("app.schemas.types")
    types_mod.EventType = _FakeEventType
    monkeypatch.setitem(sys.modules, "app.sdk.events", events_mod)
    monkeypatch.setitem(sys.modules, "app.schemas.types", types_mod)
    return manager


class TestSubscribeEvent:
    def test_install_and_uninstall(self, cache, fake_eventmanager):
        assert cache.install_event_listener() is True
        assert cache.event_listener_installed is True
        assert len(fake_eventmanager.added) == 1
        # 幂等：重复安装不再注册
        assert cache.install_event_listener() is True
        assert len(fake_eventmanager.added) == 1
        handler = fake_eventmanager.added[0][1]
        cache.uninstall_event_listener()
        assert cache.event_listener_installed is False
        assert fake_eventmanager.removed == [fake_eventmanager.added[0]]
        assert handler is not None

    def test_install_degrades_without_host_bus(self, cache):
        """宿主无事件总线时静默降级为仅定时，不抛异常。"""
        assert cache.install_event_listener() is False
        assert cache.event_listener_installed is False
        # 卸载也不会出事
        cache.uninstall_event_listener()

    def test_event_triggers_debounced_check(
        self, cache, plugin, subscriptions, monkeypatch, fake_metavideo, fake_eventmanager
    ):
        import time

        import app.plugins.tgmediacenter.modules.cache as cache_module

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=True)
        subscriptions["items"] = [FakeSubscription("青与碧", year="2026", media_id="123")]
        cache.install_event_listener()
        assert cache.subscribe_state()["event_listener"] is True

        # 连发两次事件 → 防抖合并为一次检查
        cache._on_subscribe_added(None)
        cache._on_subscribe_added(None)
        deadline = time.monotonic() + 5
        while cache.subscribe_state()["last_check_at"] == "" and time.monotonic() < deadline:
            time.sleep(0.02)
        state = cache.subscribe_state()
        assert state["last_check_at"] != ""
        assert state["last_check_new"] == 0  # 首次运行只建立基线，不计新增

    def test_event_ignored_when_subscribe_disabled(self, cache, plugin, fake_eventmanager, monkeypatch):
        import app.plugins.tgmediacenter.modules.cache as cache_module

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=False)
        cache._on_subscribe_added(None)
        assert cache._evt_timer is None

    def test_status_reports_event_listener(self, cache, plugin, fake_eventmanager):
        plugin.save_config(cache_subscribe_enabled=True)
        cache.install_event_listener()
        assert cache.status()["subscribe"]["event_listener"] is True
