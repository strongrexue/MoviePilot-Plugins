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

    def post_message(self, title="", text="", mtype=None) -> None:
        self.messages.append({"title": title, "text": text, "mtype": mtype})


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
    def __init__(
        self, name, year="", season=None, media_source="themoviedb",
        media_id="", lack_episode=2, sub_id=0,
    ):
        self.id = sub_id
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


class FakeMediaServerModule:
    """媒体服务器模块替身：只实现 media_exists，记录调用次数。"""

    def __init__(self, result) -> None:
        self._result = result
        self.calls = 0

    def media_exists(self, mediainfo, itemid=None, server=None):
        self.calls += 1
        return self._result


class _FakeEmbyInstance:
    """镜像真机结构：ServiceInfo.instance 是服务器对象，没有 media_exists。"""


class FakeMediaServerService:
    def __init__(self, module) -> None:
        self.module = module
        self.instance = _FakeEmbyInstance()
        self.name = "emby"


class FakeMediaServerHelper:
    def __init__(self, module) -> None:
        self._module = module

    def iterate_module_instances(self):
        return iter([FakeMediaServerService(self._module)])


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
        # 用户输入的日期按本地时间理解：本地 01-01 00:00 换算成库内 UTC 口径
        assert since == datetime(2026, 1, 1).astimezone(timezone.utc).replace(tzinfo=None)
        assert until == datetime(2026, 1, 31, 23, 59, 59).astimezone(timezone.utc).replace(tzinfo=None)

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


# ---------------------------------------------------------------------- 时区口径


def _local_utc_offset() -> timedelta:
    """当前运行环境的 UTC 偏移（东八区为 +8 小时）。"""
    return datetime.now(timezone.utc).astimezone().utcoffset() or timedelta(0)


class TestTimezoneDisplay:
    """库内 UTC 无时区时间 → 本地时间展示（1.6.6 真机反馈：缓存管理「最新消息」慢 8 小时）。"""

    def test_utc_to_local_naive_shifts_by_local_offset(self):
        utc_naive = datetime(2026, 10, 13, 9, 29, 16)
        local = history_module.utc_to_local_naive(utc_naive)
        expected = utc_naive.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        assert local == expected
        # 展示值必须比库内 UTC 值大一个本地时区偏移（东八区环境即 +8 小时）
        assert local - utc_naive == _local_utc_offset()
        # 带时区的入参同样按 UTC 解释
        assert history_module.utc_to_local_naive(
            datetime(2026, 10, 13, 9, 29, 16, tzinfo=timezone.utc)
        ) == local
        # None / 非 datetime 安全透传
        assert history_module.utc_to_local_naive(None) is None
        assert history_module.utc_to_local_naive("2026-10-13") is None

    def test_stats_latest_date_is_local(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 3101, _text("青与碧 (2026) S01E01"))
        with plugin.get_database().session() as session:
            stored = session.execute(select(TgMessageCache.message_date)).scalar_one()
        assert stored.tzinfo is None  # 库内是 UTC 无时区时间
        shown = service.stats([CHAT_A])[0]["latest_date"]
        assert shown == stored.replace(tzinfo=timezone.utc).astimezone().replace(
            tzinfo=None).isoformat(timespec="seconds")
        # 展示值比库内 UTC 值大一个本地时区偏移（东八区即 +8 小时；截断到秒后比较）
        assert datetime.fromisoformat(shown) - stored.replace(microsecond=0) == _local_utc_offset()

    def test_search_message_date_is_local(self, plugin, service, fake_metavideo):
        service.record(CHAT_A, 3102, _text("青与碧 (2026) S01E02"))
        with plugin.get_database().session() as session:
            stored = session.execute(select(TgMessageCache.message_date)).scalar_one()
        shown = service.search("青与碧")[0]["message_date"]
        assert datetime.fromisoformat(shown) - stored.replace(microsecond=0) == _local_utc_offset()

    def test_parse_date_treats_input_as_local(self):
        # 用户输入的日期按本地时间理解，再换算成库内 UTC 口径
        parsed = history_module._parse_date("2026-01-01")
        assert parsed == datetime(2026, 1, 1).astimezone(timezone.utc).replace(tzinfo=None)
        # 显式带时区的输入按原样尊重
        assert history_module._parse_date("2026-01-01T00:00:00+00:00") == datetime(2026, 1, 1)
        # 截止日期仍是本地当天 23:59:59
        until = history_module._parse_date("2026-01-31", end_of_day=True)
        assert until == datetime(2026, 1, 31, 23, 59, 59).astimezone(timezone.utc).replace(tzinfo=None)
        assert history_module._parse_date("") is None
        assert history_module._parse_date("不是日期") is None


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

    def test_fallback_check_runs_when_new_subscription_search_off(
        self, cache, subscriptions, plugin, fake_metavideo
    ):
        """兜底检查与「新增订阅回搜」开关互不依赖（1.13.21）。

        关闭事件开关后，定时/手动兜底仍要能靠快照 diff 发现新增订阅——
        插件离线期间新增的订阅只可能被兜底捞到。
        """
        plugin.save_config(cache_subscribe_enabled=False)
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        assert cache.check_subscriptions(trigger="测试")["baseline"] is True

        cache.history().record(CHAT_A, 4401, _text("青与碧 (2026) S01E01"))
        cache._matcher = FakeMatcher(missing=True)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", year="2026", media_id="2"),
        ]
        result = cache.check_subscriptions(trigger="测试")
        assert result["new"] == 1
        assert result["pushed"] == 1
        assert _count(plugin, TgPushTask) == 1

    def test_scheduled_fallback_job_ignores_event_switch(self, cache, plugin, subscriptions):
        """定时入口本身也不看事件开关（否则 cron 注册了却什么都不做）。"""
        plugin.save_config(cache_subscribe_enabled=False)
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.run_subscription_job()
        # 首次运行建基线：未抛错且状态里留下检查时间
        assert cache.subscribe_state()["last_check_at"]

    def test_service_registers_fallback_without_event_switch(self, cache, plugin):
        """get_service 不应再被「新增订阅回搜」开关挡住兜底任务。"""
        from types import SimpleNamespace

        from app.plugins.tgmediacenter import TgMediaCenter

        plugin.save_config(cache_enabled=True, cache_subscribe_enabled=False)
        stub = SimpleNamespace(_cache=cache, _enabled=lambda: True)
        services = TgMediaCenter.get_service(stub)
        ids = [item.get("id") for item in services]
        assert "tgmediacenter_cache_subscribe" in ids

    def test_subscribe_state_exposes_both_channels(self, cache, plugin):
        """状态里要能分别看出事件开关与兜底 cron。"""
        plugin.save_config(cache_subscribe_enabled=False, cache_subscribe_cron="*/20 * * * *")
        state = cache.subscribe_state()
        assert state["event_enabled"] is False
        assert state["fallback_cron"] == "*/20 * * * *"

    def test_search_notification_follows_switch(self, cache, subscriptions, plugin, fake_metavideo):
        """回搜结果通知受「回搜到资源后通知我」开关控制（默认开，关掉后只回搜不打扰）。"""

        def _run(message_id: int) -> int:
            subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
            cache.check_subscriptions(trigger="测试")  # 建立基线
            cache.history().record(CHAT_A, message_id, _text("青与碧 (2026) S01E01"))
            cache._matcher = FakeMatcher(missing=True)
            subscriptions["items"] = [
                FakeSubscription("老片", media_id="1"),
                FakeSubscription("青与碧", year="2026", media_id="2"),
            ]
            before = len(plugin.messages)
            assert cache.check_subscriptions(trigger="测试")["pushed"] == 1
            return len(plugin.messages) - before

        # 默认开启：回搜到并推送后发一条汇总
        assert _run(4301) == 1
        assert "缓存回搜" in plugin.messages[-1]["title"]
        # 关掉开关：回搜照常执行，只是不打扰
        plugin.save_config(notify_on_search=False)
        assert cache.notify_enabled() is False
        assert _run(4302) == 0

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

    def test_skip_reasons_reported_but_not_notified(self, cache, subscriptions, plugin, fake_metavideo):
        """1.13.25：一条都没推时**不再发通知**（用户要求），但明细口径照旧保留。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4601, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_A, 4602, _text("青与碧 (2026) S01E02"))
        cache._matcher = FakeMatcher(missing=False)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        before = len(plugin.messages)
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        detail = result["details"][0]
        assert detail["candidates"] == 2
        assert detail["skipped"] == 2
        # 明细/日志口径保留计数（排障仍在）
        assert detail["reason_text"] == "订阅无缺集 2"
        # 1.13.25：没推东西就不发通知，运行详情页查明细
        assert len(plugin.messages) == before

    def test_no_push_block_layout_with_year_and_source_line(self, cache, subscriptions, plugin, fake_metavideo):
        """1.13.25：跳过块不再进通知；明细里片名+年份、来源照旧可查。"""
        class FullMatcher:
            def is_missing(self, **kwargs):
                return {"missing": False, "reason": "订阅已存在且无缺集",
                        "source": "subscription", "detail": ""}

        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4655, _text("青与碧 (2026) S01E01"))
        cache._matcher = FullMatcher()
        # 订阅没写年份：块名用候选识别年份兜底
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        before = len(plugin.messages)
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        detail = result["details"][0]
        assert detail["candidate_year"] == "2026"
        assert detail["channels"] == [CHAT_A]
        assert len(plugin.messages) == before  # 没推就不发通知

    def test_not_subscribed_reason_hidden_from_notification(self, cache, subscriptions, plugin, fake_metavideo):
        """1.7.4：「未订阅」不在通知里展示；1.13.25 起整条跳过通知都不再发。

        候选是标题包含匹配捞出来的，识别片名/年份/季没对上订阅就记未订阅；
        这些判定只进命中流水与运行详情页。
        """
        class MixedMatcher:
            def __init__(self) -> None:
                self.calls = 0

            def is_missing(self, **kwargs):
                self.calls += 1
                if self.calls <= 2:
                    return {"missing": False, "reason": "未订阅",
                            "source": "subscription", "detail": ""}
                return {"missing": False, "reason": "订阅已存在且无缺集",
                        "source": "subscription", "detail": ""}

        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4651, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_A, 4652, _text("青与碧 (2026) S01E02"))
        cache.history().record(CHAT_A, 4653, _text("青与碧 (2026) S01E03"))
        cache._matcher = MixedMatcher()
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        before = len(plugin.messages)
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        # 明细/日志里的 reason_text 保留未订阅（排障口径不变）
        assert result["details"][0]["reason_text"] == "未订阅 2、订阅无缺集 1"
        assert len(plugin.messages) == before

    def test_notification_with_only_hidden_reasons(self, cache, subscriptions, plugin, fake_metavideo):
        """1.13.25：「未订阅」全部隐藏 + 没有推送 → 整条通知都不发。"""
        class NotSubscribedMatcher:
            def is_missing(self, **kwargs):
                return {"missing": False, "reason": "未订阅",
                        "source": "subscription", "detail": ""}

        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4661, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_A, 4662, _text("青与碧 (2026) S01E02"))
        cache._matcher = NotSubscribedMatcher()
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        before = len(plugin.messages)
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 0
        assert len(plugin.messages) == before

    def test_skip_reason_marks_media_library_hit(self, cache, subscriptions, plugin, fake_metavideo, monkeypatch):
        """真机口径：媒体库已有的候选要归类成"媒体库已存在"（而不是笼统的跳过）。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4701, _text("青与碧 (2026) S01E01"))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: [1]}

        module = FakeMediaServerModule(Exist())
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        cache._matcher = MediaMatcher()
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", year="2026", season=1, media_id="2"),
        ]
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        assert result["details"][0]["reason_text"] == "媒体库已存在 1"
        assert module.calls == 1

    def test_push_notification_reports_library_miss_reason(self, cache, subscriptions, plugin, fake_metavideo):
        """1.4.6：全推出去时必须说清"为什么判定媒体库没有"（真机：库里明明有）。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4801, _text("青与碧 (2026) S01E01"))

        class FakeLibraryMissing:
            def is_missing(self, **kwargs):
                return {
                    "missing": True,
                    "reason": "媒体库中不存在",
                    "source": "mediaserver",
                    "note": "媒体库中没有同名剧集条目（宿主按片名+年份精确匹配失败）",
                    "detail": "「青与碧」在已配置媒体服务器中未找到",
                }

        cache._matcher = FakeLibraryMissing()
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", media_id="2"),
        ]
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 1
        assert result["details"][0]["media_note"]
        text = plugin.messages[-1]["text"]
        assert "媒体库未收录" in text
        assert "没有同名剧集条目" in text

    def test_search_notification_pushed_block_format(self, cache, subscriptions, plugin, fake_metavideo):
        """1.6.10：命中并推送的资源按消息分块，块内带年份 / 链接 / 来源，且去「· 」。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4501, _text("青与碧 (2026) S01E01"))
        cache._matcher = FakeMatcher(missing=True)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", year="2026", media_id="2"),
        ]
        cache.check_subscriptions(trigger="测试")
        title = plugin.messages[-1]["title"]
        text = plugin.messages[-1]["text"]
        assert "缓存回搜" in title
        # 去「· 」、首字对齐
        assert "· " not in text
        # 媒体名带年份
        assert "青与碧 (2026)" in text
        # 真实链接
        assert LINK in text
        # 来源（测试无对话缓存，退回原始频道 ID）
        assert f"来源：{CHAT_A}" in text
        # 1.7.6：去「命中并推送 N 条资源」头行，正文直接从媒体块开始
        assert "命中并推送" not in text
        assert "新增订阅" not in text

    def test_search_notification_multi_channel_blocks(self, cache, subscriptions, plugin, fake_metavideo):
        """1.6.10：同片名命中多个频道时，按消息分块、每块自带来源，链接归属清晰。"""
        # 缓存可配多个频道：放开到 A + B，否则回搜只会搜 CHAT_A
        plugin.save_config(cache_chat_ids=[CHAT_A, CHAT_B])
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4501, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_B, 4502, _text("青与碧 (2026) S01E02", "https://115.com/s/swabc888"))
        cache._matcher = FakeMatcher(missing=True)
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", year="2026", media_id="2"),
        ]
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 2
        text = plugin.messages[-1]["text"]
        # 1.7.6：无头行，两条推送块直接排列
        assert "命中并推送" not in text
        assert "新增订阅" not in text
        assert "· " not in text
        # 两块各自带来源
        assert f"来源：{CHAT_A}" in text
        assert f"来源：{CHAT_B}" in text
        # 两条链接都在，分属两个频道
        assert LINK in text
        assert "https://115.com/s/swabc888" in text

    def test_search_notification_mixed_pushed_and_skipped(self, cache, subscriptions, plugin, fake_metavideo):
        """1.13.25：只报推出去的；跳过（无需推送）那部分不再进通知正文。"""
        plugin.save_config(cache_chat_ids=[CHAT_A])
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4661, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_A, 4662, _text("你好时光 (2026) S01E01"))

        class SelectiveMatcher:
            """青与碧缺集（推送），你好时光不缺（跳过）。"""

            def is_missing(self, **kwargs):
                if "青与碧" in str(kwargs.get("title") or ""):
                    return {"missing": True, "reason": "订阅缺 3 集",
                            "source": "subscription", "detail": ""}
                return {"missing": False, "reason": "订阅已存在且无缺集",
                        "source": "subscription", "detail": ""}

        cache._matcher = SelectiveMatcher()
        subscriptions["items"] = [
            FakeSubscription("老片", media_id="1"),
            FakeSubscription("青与碧", year="2026", media_id="2"),
            FakeSubscription("你好时光", year="2026", media_id="3"),
        ]
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 1
        text = plugin.messages[-1]["text"]
        # 无头行（1.7.6）
        assert "新增订阅" not in text
        assert "命中并推送" not in text
        # 只列推送块，跳过块（无需推送）不出现
        lines = text.split("\n")
        push_idx = next(i for i, ln in enumerate(lines) if ln.startswith("📺 青与碧 (2026) S01E01"))
        assert push_idx >= 0
        assert "你好时光" not in text
        assert "无需推送" not in text
        assert "" not in lines

    def test_disabled_module_skips_check(self, plugin, fake_metavideo):
        plugin.save_config(cache_enabled=False)
        module = CacheModule(plugin)
        plugin._cache = module
        assert module.check_subscriptions(trigger="测试")["checked"] is False


# ---------------------------------------------------------------------- 洗版回搜（1.13.24）


class TestReshuffleSearch:
    """洗版回搜：定时兜底跳过媒体库判定、遍历全部订阅、按任意路径流水去重。"""

    def test_off_by_default_and_keeps_old_behaviour(self, cache, subscriptions, plugin, fake_metavideo):
        assert cache.reshuffle_enabled() is False
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        assert cache.check_subscriptions(trigger="测试")["baseline"] is True
        # 老订阅有新资源也不回搜（常规口径只看快照 diff 的新增订阅）
        cache.history().record(CHAT_A, 4801, _text("老片 (2026) S01E01"))
        result = cache.check_subscriptions(trigger="测试")
        assert result.get("reshuffle") is None
        assert result["pushed"] == 0

    def test_searches_all_subscriptions_without_library_check(
        self, cache, subscriptions, plugin, fake_metavideo
    ):
        """开了洗版：老订阅（不在快照 diff 里）同样回搜，且**不问媒体库**。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")  # 建基线
        cache.history().record(CHAT_A, 4811, _text("老片 (2026) S01E01"))

        class ExplodingMatcher:
            def is_missing(self, **kwargs):  # 洗版路径不许调用媒体库判定
                raise AssertionError("洗版回搜不应调用 is_missing")

        cache._matcher = ExplodingMatcher()
        plugin.save_config(cache_reshuffle_enabled=True)
        result = cache.check_subscriptions(trigger="测试")
        assert result["reshuffle"] is True
        assert result["pushed"] == 1
        assert _count(plugin, TgPushTask) == 1
        assert "洗版回搜" in plugin.messages[-1]["title"]

    def test_media_library_hit_still_pushed(self, cache, subscriptions, plugin, fake_metavideo, monkeypatch):
        """洗版的意义就是「库里有了也照推」：媒体库判定为不缺时必须照样入队。"""
        subscriptions["items"] = [FakeSubscription("青与碧", year="2026", season=1, media_id="2")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4821, _text("青与碧 (2026) S01E01"))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: [1]}

        module = FakeMediaServerModule(Exist())
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        cache._matcher = MediaMatcher()
        plugin.save_config(cache_reshuffle_enabled=True)
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 1
        assert module.calls == 0  # 连库都没查

    def test_dedupes_by_any_path_hit(self, cache, subscriptions, plugin, fake_metavideo):
        """监控/补扫推过的消息不再洗版重推（按任意 rule_id 的命中流水去重）。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4831, _text("老片 (2026) S01E01"))
        # 模拟监控规则已经推过这条消息（不同 rule_id）
        with plugin.get_database().session() as session:
            session.add(TgHitLog(
                plugin_id="FakePlugin",
                rule_id="mon_other_rule",
                rule_name="别的规则",
                chat_id=CHAT_A,
                message_id=4831,
                decision=DECISION_HIT,
            ))
            session.commit()
        plugin.save_config(cache_reshuffle_enabled=True)
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        assert result["details"][0]["reasons"] == {"已推送过": 1}
        assert _count(plugin, TgPushTask) == 0

    def test_no_push_cap_all_subscriptions_pushed_in_one_run(
        self, cache, subscriptions, plugin, fake_metavideo
    ):
        """1.13.25：不再限制单轮入队条数——一轮定时就把全部命中推出去。"""
        subscriptions["items"] = [
            FakeSubscription("青与碧", year="2026", media_id="2"),
            FakeSubscription("你好时光", year="2026", media_id="3"),
            FakeSubscription("老片", year="2025", media_id="4"),
        ]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4841, _text("青与碧 (2026) S01E01"))
        cache.history().record(CHAT_A, 4842, _text("青与碧 (2026) S01E02", "https://115.com/s/swabc888"))
        cache.history().record(CHAT_A, 4843, _text("你好时光 (2026) S01E01"))
        cache.history().record(CHAT_A, 4844, _text("老片 (2025) S01E01"))
        plugin.save_config(cache_reshuffle_enabled=True)

        result = cache.check_subscriptions(trigger="测试")
        assert result["reshuffle"] is True
        assert result["pushed"] == 4  # 全部一次推完，没有上限截断
        assert "单轮上限" not in result["message"]
        assert _count(plugin, TgPushTask) == 4
        # 再跑一轮：流水去重，一条都不重复推
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 0
        assert _count(plugin, TgPushTask) == 4

    def test_skipped_subscription_not_notified(self, cache, subscriptions, plugin, fake_metavideo):
        """1.13.25：洗版一轮里全是「已推送过」时不发通知（用户要求）。"""
        subscriptions["items"] = [FakeSubscription("老片", media_id="1")]
        cache.check_subscriptions(trigger="测试")
        cache.history().record(CHAT_A, 4851, _text("老片 (2026) S01E01"))
        plugin.save_config(cache_reshuffle_enabled=True)
        assert cache.check_subscriptions(trigger="测试")["pushed"] == 1
        before = len(plugin.messages)
        # 第二轮同一批候选全部「已推送过」→ 不发任何通知
        second = cache.check_subscriptions(trigger="测试")
        assert second["pushed"] == 0
        assert second["details"][0]["reasons"] == {"已推送过": 1}
        assert len(plugin.messages) == before

    def test_snapshot_still_maintained(self, cache, subscriptions, plugin, fake_metavideo):
        """洗版模式下也要维护快照，关掉开关后能按常规口径继续跑。"""
        from app.plugins.tgmediacenter.modules.cache import _SUB_SNAPSHOT_KEY

        subscriptions["items"] = [FakeSubscription("青与碧", year="2026", media_id="2")]
        plugin.save_config(cache_reshuffle_enabled=True)
        cache.check_subscriptions(trigger="测试")
        assert (plugin.get_data(_SUB_SNAPSHOT_KEY) or {})
        plugin.save_config(cache_reshuffle_enabled=False)
        # 关掉后快照已是最新 → 没有新增订阅
        assert cache.check_subscriptions(trigger="测试")["new"] == 0

    def test_settings_and_state_roundtrip(self, plugin, cache):
        saved = cache.save_settings({"reshuffle_enabled": True})
        assert saved["reshuffle_enabled"] is True
        assert plugin.config["cache_reshuffle_enabled"] is True
        assert cache.subscribe_state()["reshuffle"] is True
        assert api_schemas.CacheSettingsData.model_validate(saved).reshuffle_enabled is True
        payload = cache.status()
        assert api_schemas.CacheStatusData.model_validate(payload).subscribe.reshuffle is True
        assert cache.save_settings({"reshuffle_enabled": False})["reshuffle_enabled"] is False

    def test_push_batch_settings_roundtrip_and_normalize(self, plugin, cache):
        """1.13.25：每批条数 / 批间隔可存可读，非法值收敛到合法区间。"""
        saved = cache.save_settings({"push_batch_size": 25, "push_batch_interval": 45})
        assert saved["push_batch_size"] == 25
        assert saved["push_batch_interval"] == 45
        assert plugin.config["cache_push_batch_size"] == 25
        assert plugin.config["cache_push_batch_interval"] == 45
        assert api_schemas.CacheSettingsData.model_validate(saved).push_batch_size == 25
        # 越界收敛：0 → 下限、9999 → 上限
        low = cache.save_settings({"push_batch_size": 0, "push_batch_interval": 1})
        assert low["push_batch_size"] == 1
        assert low["push_batch_interval"] == 5
        high = cache.save_settings({"push_batch_size": 9999, "push_batch_interval": 99999})
        assert high["push_batch_size"] == 200
        assert high["push_batch_interval"] == 3600
        # 非法字符串回默认
        bad = cache.save_settings({"push_batch_size": "abc", "push_batch_interval": "xyz"})
        assert bad["push_batch_size"] == 10
        assert bad["push_batch_interval"] == 15

    def test_empty_subscription_list_reports_cleanly(self, cache, subscriptions, plugin):
        plugin.save_config(cache_reshuffle_enabled=True)
        result = cache.check_subscriptions(trigger="测试")
        assert result["pushed"] == 0
        assert result["message"] == "没有订阅可回搜"


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
        assert saved["subscribe_cron"] == "*/30 * * * *"
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


class _FakeEvent:
    """宿主广播事件替身（payload 走 event_data）。"""

    def __init__(self, data: dict) -> None:
        self.event_data = data


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


def _wait_event_search(cache, runs: int = 1, timeout: float = 5.0) -> None:
    """等待第 runs 次事件回搜真正执行完。"""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cache.event_runs >= runs:
            with cache._lock:
                busy = cache._state.get("checking")
            if not busy:
                time.sleep(0.05)  # 让统计落盘
                return
        time.sleep(0.02)
    raise AssertionError(f"事件回搜未在 {timeout}s 内执行完（runs={cache.event_runs}）")


class TestSubscribeEvent:
    def test_handler_lives_on_plugin_class(self):
        """事件处理器必须定义在插件主类上：宿主只通过插件实例解析器绑定运行实例
        （plugin_id = owner_class.__name__），普通类的绑定方法会被静默跳过。"""
        inspect = __import__("inspect")
        from app.plugins.tgmediacenter import TgMediaCenter

        assert inspect.isfunction(TgMediaCenter.on_subscribe_added)
        assert TgMediaCenter.on_subscribe_added.__qualname__ == "TgMediaCenter.on_subscribe_added"

    @staticmethod
    def _plugin_instance(cache):
        """插件主类实例（不跑 __init__，只挂缓存模块）。"""
        from app.plugins.tgmediacenter import TgMediaCenter

        instance = TgMediaCenter.__new__(TgMediaCenter)
        instance._cache = cache
        instance._subscribe_eventmanager = None
        instance._subscribe_event_type = None
        return instance

    def test_install_registers_plugin_method(self, cache, fake_eventmanager):
        """注册给宿主的是主类绑定方法（owner_class 可被宿主 plugins resolver 解析）。"""
        plugin = self._plugin_instance(cache)
        assert plugin._install_subscribe_listener() is True
        assert len(fake_eventmanager.added) == 1
        event_type, handler = fake_eventmanager.added[0]
        assert event_type == "subscribe.added"
        assert handler.__self__ is plugin
        assert type(handler.__self__).__name__ == "TgMediaCenter"
        assert cache.event_listener_installed is True
        # 卸载：同一引用被移除
        plugin._uninstall_subscribe_listener()
        assert fake_eventmanager.removed == [(event_type, handler)]
        assert cache.event_listener_installed is False

    def test_uninstall_without_install_is_safe(self, cache):
        """未安装（宿主无事件总线）时卸载不抛异常。"""
        plugin = self._plugin_instance(cache)
        plugin._uninstall_subscribe_listener()
        assert cache.event_listener_installed is False

    def test_install_degrades_without_host_bus(self, cache):
        """宿主无事件总线时静默降级为仅定时，不抛异常。"""
        plugin = self._plugin_instance(cache)
        assert plugin._install_subscribe_listener() is False
        assert cache.event_listener_installed is False
        plugin._uninstall_subscribe_listener()

    def test_event_searches_subscription_by_id(
        self, cache, plugin, subscriptions, monkeypatch, fake_metavideo
    ):
        """新增订阅事件：按 subscribe_id 定位订阅并回搜（不依赖快照「新增」判断）。"""
        import app.plugins.tgmediacenter.modules.cache as cache_module
        from app.plugins.tgmediacenter.modules.cache import _SUB_SNAPSHOT_KEY

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=True)
        # 缓存里已有该片资源
        cache.history().record(CHAT_A, 7001, _text("美人余 (2026) S01E01", "https://115.com/s/aaa?password=1"))
        # 快照里已存在该订阅：事件路径仍应回搜（删了重加的场景）
        plugin.save_data(_SUB_SNAPSHOT_KEY, {"themoviedb|777|": {"name": "美人余", "year": "2026"}})
        subscriptions["items"] = [FakeSubscription("美人余", year="2026", media_id="777", sub_id=42)]

        cache.on_subscribe_event(_FakeEvent({"subscribe_id": 42, "mediainfo": {"title": "美人余", "year": "2026"}}))
        _wait_event_search(cache)

        assert _count(plugin, TgPushTask) == 1
        state = cache.subscribe_state()
        assert state["last_check_new"] == 1
        assert state["last_check_pushed"] == 1

    def test_event_falls_back_to_mediainfo(
        self, cache, plugin, subscriptions, monkeypatch, fake_metavideo
    ):
        """订阅 ID 在宿主订阅查询里还看不到时，用事件 mediainfo 兜底回搜。"""
        import app.plugins.tgmediacenter.modules.cache as cache_module

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=True)
        cache.history().record(CHAT_A, 7002, _text("美人余 (2026) S01E02", "https://115.com/s/bbb?password=2"))
        # 订阅在列表里，但 ID 与事件对不上（模拟事务/缓存窗口）→ 用 mediainfo 兜底
        subscriptions["items"] = [FakeSubscription("美人余", year="2026", media_id="777", sub_id=42)]

        cache.on_subscribe_event(_FakeEvent({
            "subscribe_id": 999,
            "mediainfo": {"title": "美人余", "year": "2026", "media_source": "themoviedb", "media_id": "777"},
        }))
        _wait_event_search(cache)

        assert _count(plugin, TgPushTask) == 1
        assert cache.subscribe_state()["last_check_pushed"] == 1

    def test_event_builds_baseline_first(
        self, cache, plugin, subscriptions, monkeypatch, fake_metavideo
    ):
        """无基线时先建完整基线，避免把事件订阅并入快照后其余存量订阅被误判为新增。"""
        import app.plugins.tgmediacenter.modules.cache as cache_module
        from app.plugins.tgmediacenter.modules.cache import _SUB_SNAPSHOT_KEY

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=True)
        cache.history().record(CHAT_A, 7003, _text("美人余 (2026) S01E01", "https://115.com/s/ccc?password=3"))
        subscriptions["items"] = [
            FakeSubscription("美人余", year="2026", media_id="777", sub_id=42),
            FakeSubscription("别的剧", year="2025", media_id="888", sub_id=43),
        ]

        cache.on_subscribe_event(_FakeEvent({"subscribe_id": 42, "mediainfo": {"title": "美人余"}}))
        _wait_event_search(cache)

        saved = plugin.get_data(_SUB_SNAPSHOT_KEY) or {}
        assert "themoviedb|777|" in saved
        assert "themoviedb|888|" in saved  # 存量订阅也进了基线，不会下次被当新增
        assert _count(plugin, TgPushTask) == 1

    def test_event_dedupes_against_hit_log(
        self, cache, plugin, subscriptions, monkeypatch, fake_metavideo
    ):
        """已推送过的资源被命中流水拦住，不会重复入队。"""
        import app.plugins.tgmediacenter.modules.cache as cache_module

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=True)
        cache.history().record(CHAT_A, 7004, _text("美人余 (2026) S01E01", "https://115.com/s/ddd?password=4"))
        subscriptions["items"] = [FakeSubscription("美人余", year="2026", media_id="777", sub_id=42)]

        cache.on_subscribe_event(_FakeEvent({"subscribe_id": 42, "mediainfo": {"title": "美人余"}}))
        _wait_event_search(cache)
        assert _count(plugin, TgPushTask) == 1
        # 再次事件（例如删除后重新添加）：命中流水拦掉，不重复推送
        cache.on_subscribe_event(_FakeEvent({"subscribe_id": 42, "mediainfo": {"title": "美人余"}}))
        _wait_event_search(cache, runs=2)
        assert _count(plugin, TgPushTask) == 1

    def test_event_ignored_when_subscribe_disabled(self, cache, plugin, monkeypatch):
        import app.plugins.tgmediacenter.modules.cache as cache_module

        monkeypatch.setattr(cache_module, "_EVENT_DEBOUNCE_SECONDS", 0.05)
        plugin.save_config(cache_subscribe_enabled=False)
        cache.on_subscribe_event(_FakeEvent({"subscribe_id": 1, "mediainfo": {"title": "美人余"}}))
        assert cache._evt_timer is None
        assert cache._pending_events == []

    def test_status_reports_event_listener(self, cache, fake_eventmanager):
        plugin = self._plugin_instance(cache)
        plugin._install_subscribe_listener()
        assert cache.status()["subscribe"]["event_listener"] is True
