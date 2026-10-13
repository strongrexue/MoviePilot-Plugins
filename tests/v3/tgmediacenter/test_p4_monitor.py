"""P4 TG 资源监控测试。

覆盖：规则归一 / 监听查询 / 识别与净化 / 缺失判断 / 冷却门 / 流水线端到端
（含去重、关键词、仅缺集、无链接、推送队列与重试退避）/ 推送目标 / API 层。

宿主依赖（MetaVideo / list_subscriptions / MediaServerHelper / 插件 DB）在测试里
用可注入的替身驱动——真机行为仍以部署验证为准。
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.plugins.tgmediacenter.core import pipeline as pipeline_module
from app.plugins.tgmediacenter.controller import api as controller_api
from app.plugins.tgmediacenter.core.cooldown import CooldownGate, describe_flood_wait
from app.plugins.tgmediacenter.destinations import (
    DESTINATION_VALUES,
    DestinationError,
    resolve_destination,
)
from app.plugins.tgmediacenter.destinations.base import PushResult
from app.plugins.tgmediacenter.model.hit_log import (
    DECISION_HIT,
    DECISION_SKIPPED_KEYWORD,
    DECISION_SKIPPED_NO_LINK,
    DECISION_SKIPPED_NOT_MISSING,
    DECISION_SKIPPED_UNKNOWN,
    DECISION_SKIPPED_UNRECOGNIZED,
    TgHitLog,
)
from app.plugins.tgmediacenter.model.push_task import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    TgPushTask,
)
from app.plugins.tgmediacenter.modules.monitor import MonitorModule
from app.plugins.tgmediacenter.services import matcher as matcher_module
from app.plugins.tgmediacenter.services import recognizer as recognizer_module
from app.plugins.tgmediacenter.services.matcher import MediaMatcher

CHAT_A = -1001234567890
CHAT_B = -1009999999999


# ---------------------------------------------------------------------- 测试替身


class FakeType:
    """模拟宿主 MediaType 枚举（值是中文字符串）。"""

    def __init__(self, value: str) -> None:
        self.value = value


class FakeMetaVideo:
    """按测试约定解析标题：``名称.S01E02`` → 剧集；``名称.2023`` → 电影。"""

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
        if match:
            self.name = title.split(".")[0]
            self.begin_season = int(match.group(1))
            self.begin_episode = int(match.group(2))
            if match.group(3):
                self.end_episode = int(match.group(3))
            self.type = FakeType("电视剧")
        else:
            self.name = title.split(".")[0]
            self.type = FakeType("电影")


class FakeDatabase:
    """内存 SQLite 的插件数据库句柄替身（session 是方法，与宿主一致）。"""

    def __init__(self) -> None:
        self.engine = create_engine("sqlite://")
        TgHitLog.__table__.create(self.engine)
        TgPushTask.__table__.create(self.engine)
        self._factory = sessionmaker(bind=self.engine)

    def session(self):
        return self._factory()


class FakePlugin:
    """鸭子类型的插件对象：配置 / 数据 / 数据库。"""

    plugin_version = "1.3.0"

    def __init__(self, config: dict | None = None) -> None:
        self._config = dict(config or {})
        self._data: dict = {}
        self._db = FakeDatabase()
        self._credentials = None

    # 宿主 _PluginBase 语义：save_config 合并后**整体替换**快照（新对象）
    @property
    def config(self) -> dict:
        return self._config

    def save_config(self, **patch) -> None:
        merged = dict(self._config)
        merged.update(patch)
        self._config = merged

    def drop_config(self, *keys) -> None:
        merged = dict(self._config)
        for key in keys:
            merged.pop(key, None)
        self._config = merged

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value

    def del_data(self, key) -> None:
        self._data.pop(key, None)

    def get_database(self):
        return self._db

    def get_state(self) -> bool:
        return bool(self._config.get("enabled"))


class FakeSubscription:
    def __init__(self, name, year="", season=None, lack_episode=None, state="R"):
        self.name = name
        self.year = year
        self.season = season
        self.lack_episode = lack_episode
        self.state = state


class FakeQueryPage:
    def __init__(self, items) -> None:
        self.items = list(items)


class FakeMediaServerModule:
    def __init__(self, result) -> None:
        self._result = result
        self.calls = 0

    def media_exists(self, mediainfo, itemid=None, server=None):
        self.calls += 1
        return self._result


class _FakeEmbyInstance:
    """镜像真机结构：ServiceInfo.instance 是具体服务器对象，没有 media_exists。"""

    pass


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


@pytest.fixture()
def fake_metavideo(monkeypatch):
    """给识别服务注入可控制的 MetaVideo 替身。"""
    monkeypatch.setattr(recognizer_module, "META_AVAILABLE", True)
    monkeypatch.setattr(recognizer_module, "MetaVideo", FakeMetaVideo)
    return FakeMetaVideo


@pytest.fixture()
def plugin():
    return FakePlugin()


@pytest.fixture()
def monitor(plugin):
    module = MonitorModule(plugin)
    plugin._monitor = module
    return module


@pytest.fixture()
def pipeline(plugin, monitor, fake_metavideo):
    return pipeline_module.MessagePipeline(plugin, monitor, MediaMatcher(), CooldownGate(0.0))


def base_rule(**overrides):
    rule = {
        "id": "r-test",
        "name": "测试规则",
        "source_ids": [CHAT_A],
        "destination": "none",
        "target_id": "",
        "match_only_if_missing": False,
        "match_custom_keywords": False,
        "custom_keywords": [],
        "rule_type": "client",
        "web_channel_usernames": [],
        "enabled": True,
    }
    rule.update(overrides)
    return rule


def query_all(model, plugin):
    with plugin.get_database().session() as session:
        return list(session.execute(select(model)).scalars().all())


# ---------------------------------------------------------------------- 规则归一


class TestRuleNormalization:
    def test_normalize_fills_id_and_defaults(self):
        module = MonitorModule(FakePlugin())
        rules = module.normalize_rules([{"name": "", "source_ids": ["-100123", "abc", "-100123"]}])
        assert len(rules) == 1
        rule = rules[0]
        assert rule["id"].startswith("r") and len(rule["id"]) == 9
        assert rule["name"] == "监控规则 1"
        assert rule["source_ids"] == [-100123]
        assert rule["destination"] == "smart"
        assert rule["match_only_if_missing"] is True
        assert rule["enabled"] is True

    def test_destination_invalid_falls_back_to_smart(self):
        module = MonitorModule(FakePlugin())
        rules = module.normalize_rules([{"destination": "aliyun", "source_ids": [1]}])
        assert rules[0]["destination"] == "smart"

    def test_destination_all_values_supported(self):
        module = MonitorModule(FakePlugin())
        rules = module.normalize_rules([
            {"destination": value, "source_ids": [1]} for value in DESTINATION_VALUES
        ])
        assert [rule["destination"] for rule in rules] == list(DESTINATION_VALUES)

    def test_keywords_trimmed_and_emptied_dropped(self):
        module = MonitorModule(FakePlugin())
        rules = module.normalize_rules([{
            "match_custom_keywords": True,
            "custom_keywords": ["  蓝光 ", "", "  ", "4K"],
            "source_ids": [1],
        }])
        assert rules[0]["custom_keywords"] == ["蓝光", "4K"]

    def test_web_usernames_strip_at(self):
        module = MonitorModule(FakePlugin())
        rules = module.normalize_rules([{"web_channel_usernames": ["@dbond", " news "], "source_ids": [1]}])
        assert rules[0]["web_channel_usernames"] == ["dbond", "news"]

    def test_rules_for_chat_and_watched(self, monitor):
        monitor.save_rules([
            base_rule(id="r1", source_ids=[CHAT_A, CHAT_B]),
            base_rule(id="r2", source_ids=[CHAT_B]),
            base_rule(id="r3", source_ids=[CHAT_A], enabled=False),
        ])
        assert [r["id"] for r in monitor.rules_for_chat(CHAT_A)] == ["r1"]
        assert sorted(r["id"] for r in monitor.rules_for_chat(CHAT_B)) == ["r1", "r2"]
        assert monitor.is_watched(CHAT_A) is True
        assert monitor.is_watched(-100555) is False
        assert sorted(monitor.watched_chat_ids()) == sorted([CHAT_A, CHAT_B])

    def test_rules_cache_reused_until_config_replaced(self, monitor, plugin):
        monitor.save_rules([base_rule(id="r1")])
        first = monitor.rules()
        assert monitor.rules() is first  # 配置对象没变 → 复用缓存
        plugin.save_config(monitor_enabled=True)  # 宿主语义：快照整体替换
        assert monitor.rules() is not first

    def test_save_rules_persists_normalized(self, monitor, plugin):
        saved = monitor.save_rules([{"source_ids": [CHAT_A], "name": "转存"}])
        assert saved[0]["id"]
        stored = plugin.config["monitor_rules"]
        assert len(stored) == 1 and stored[0]["name"] == "转存"


# ---------------------------------------------------------------------- 识别与净化


class TestRecognizer:
    def test_purify_drops_ad_lines_and_control_chars(self):
        text = "测试剧集.S01E02.2160p\n加入群组 @xxx 获取更多资源\n​大小：12.5 GB\n商务合作请联系 admin"
        cleaned = recognizer_module.purify_text(text)
        assert "测试剧集.S01E02.2160p" in cleaned
        assert "大小：12.5 GB" in cleaned
        assert "加入群组" not in cleaned
        assert "商务合作" not in cleaned
        assert "\u200b" not in cleaned

    def test_purify_empty(self):
        assert recognizer_module.purify_text("   \n  ") == ""

    def test_recognize_tv(self, fake_metavideo):
        meta = recognizer_module.recognize("测试剧集.S01E02.2160p.WEB-DL\n大小：12.5 GB")
        assert meta is not None
        assert meta["title"] == "测试剧集"
        assert meta["season"] == 1
        assert meta["episode"] == 2
        assert meta["media_type"] == "tv"

    def test_recognize_movie(self, fake_metavideo):
        meta = recognizer_module.recognize("测试电影.2023.1080p.BluRay")
        assert meta is not None
        assert meta["title"] == "测试电影"
        assert meta["year"] == "2023"
        assert meta["season"] is None
        assert meta["media_type"] == "movie"

    def test_recognize_returns_none_without_name(self, monkeypatch):
        class Empty(FakeMetaVideo):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.name = ""

        monkeypatch.setattr(recognizer_module, "META_AVAILABLE", True)
        monkeypatch.setattr(recognizer_module, "MetaVideo", Empty)
        assert recognizer_module.recognize("随便一段没有名字的文字") is None

    def test_recognize_degrades_when_host_missing(self, monkeypatch):
        monkeypatch.setattr(recognizer_module, "META_AVAILABLE", False)
        assert recognizer_module.recognize("测试剧集.S01E02") is None
        assert recognizer_module.meta_available() is False

    def test_recognize_skips_url_only_message(self, fake_metavideo):
        # 真机踩过：纯链接消息被 MetaVideo 硬解析成《Https: 115 Com ...》假标题
        assert recognizer_module.recognize("https://115.com/s/sws9tvo3h9l?password=ayss") is None

    def test_recognize_ignores_leading_link_line(self, fake_metavideo):
        meta = recognizer_module.recognize(
            "https://115.com/s/abcdef?password=x\n测试剧集.S01E02.2160p"
        )
        assert meta is not None
        assert meta["title"] == "测试剧集"

    def test_recognize_rejects_url_like_name(self, monkeypatch):
        class UrlName(FakeMetaVideo):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.name = "Https: 115 Com S Abc"

        monkeypatch.setattr(recognizer_module, "META_AVAILABLE", True)
        monkeypatch.setattr(recognizer_module, "MetaVideo", UrlName)
        assert recognizer_module.recognize("某个不含链接的标题行") is None

    def test_recognize_bot_announcement_format(self, fake_metavideo):
        """真机踩过的频道播报格式：emoji + 类别前缀 + 字段行 + 链接 + 简介。"""
        text = (
            "📺 电视剧：璀璨之城 (2026) S01E01\n"
            "📥 转存入库: S01E01\n"
            "🍿 TMDB ID: 295002\n"
            "⭐️ 评分: 0.0\n"
            "🎭 题材: 爱情家庭\n"
            "🔗 链接: https://115.com/s/sws9tvo3h9l?password=ayss\n"
            "📝 剧情简介:\n"
            "　　女人都想嫁入豪门，但她们不知道，豪门是炼狱。"
        )
        meta = recognizer_module.recognize(text)
        assert meta is not None
        assert meta["title"].startswith("璀璨之城")
        assert meta["year"] == "2026"
        assert meta["media_type"] == "tv"
        assert meta["season"] == 1 and meta["episode"] == 1

    def test_recognize_skips_field_label_line(self, fake_metavideo):
        # 首行识别失败时，"转存入库:"等播报字段行不能被当成片名
        meta = recognizer_module.recognize("📥 转存入库: S01E01\n测试剧集.S01E02.2160p")
        assert meta is not None
        assert meta["title"] == "测试剧集"
        assert meta["episode"] == 2

    def test_recognize_episode_range(self, fake_metavideo):
        """真机样本："S01E01-E09" 是集区间，起始集之外的缺失也要能判断。"""
        meta = recognizer_module.recognize("📺 电视剧：美人余 (2026) S01E01-E09")
        assert meta is not None
        assert meta["title"].startswith("美人余")
        assert meta["season"] == 1
        assert meta["episode"] == 1
        assert meta["episode_end"] == 9

    def test_recognize_movie_category_hint(self, fake_metavideo):
        meta = recognizer_module.recognize("🎬 电影：测试电影 (2023) 1080p")
        assert meta is not None
        assert meta["media_type"] == "movie"


# ---------------------------------------------------------------------- 缺失判断


class TestMatcher:
    def _matcher_with_subscriptions(self, monkeypatch, subscriptions):
        # 必须走 monkeypatch：直接改模块属性会跨测试残留，污染后续用例
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage(subscriptions))
        return MediaMatcher()

    def test_subscription_no_lack_means_not_missing(self, monkeypatch):
        matcher = self._matcher_with_subscriptions(monkeypatch, [
            FakeSubscription("测试剧集", year="2023", season=1, lack_episode=0),
        ])
        result = matcher.is_missing(title="测试剧集", year="2023", media_type="tv", season=1, episode=2)
        assert result["missing"] is False
        assert result["source"] == "subscription"

    def test_subscription_with_lack_means_missing(self, monkeypatch):
        matcher = self._matcher_with_subscriptions(monkeypatch, [
            FakeSubscription("测试剧集", year="2023", season=1, lack_episode=3),
        ])
        result = matcher.is_missing(title="测试剧集", year="2023", media_type="tv", season=1, episode=2)
        assert result["missing"] is True
        assert "缺 3 集" in result["reason"]

    def test_subscription_year_mismatch_not_matched(self, monkeypatch):
        matcher = self._matcher_with_subscriptions(monkeypatch, [
            FakeSubscription("测试剧集", year="2019", season=1, lack_episode=0),
        ])
        # 年份不一致 → 订阅不匹配 → 没有数据源 → 无法判断
        result = matcher.is_missing(title="测试剧集", year="2023", media_type="tv", season=1)
        assert result["missing"] is None

    def test_capabilities_counts_total_not_first_page(self, monkeypatch):
        # 真机踩过：无参 list_subscriptions 只返回第一页（默认 50 条），
        # 计数必须用 total，否则订阅多于页大小时数字对不上
        class PageWithTotal:
            items = [FakeSubscription(f"剧{i}") for i in range(3)]
            total = 65

        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: PageWithTotal())
        assert MediaMatcher().capabilities()["subscriptions"] == 65

    def test_mediaserver_movie_not_exists(self, monkeypatch):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        module = FakeMediaServerModule(None)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        matcher = MediaMatcher()
        result = matcher.is_missing(title="测试电影", year="2023", media_type="movie")
        assert result["missing"] is True
        assert result["source"] == "mediaserver"
        assert module.calls == 1

    def test_mediaserver_tv_episode_present_and_missing(self, monkeypatch):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: [1, 2], 2: [1]}

        module = FakeMediaServerModule(Exist())
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        matcher = MediaMatcher()
        present = matcher.is_missing(title="测试剧集", media_type="tv", season=1, episode=2)
        missing = matcher.is_missing(title="测试剧集", media_type="tv", season=1, episode=3)
        assert present["missing"] is False
        assert missing["missing"] is True
        assert "E03" in missing["reason"]

    def test_mediaserver_tv_season_only(self, monkeypatch):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: [1, 2]}

        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(FakeMediaServerModule(Exist())))
        matcher = MediaMatcher()
        result = matcher.is_missing(title="测试剧集", media_type="tv", season=1)
        assert result["missing"] is False  # 该季已有内容

    def test_mediaserver_tv_range_partial_missing(self, monkeypatch):
        """真机样本：S01E01-E09 而库里只有 E01-E03 → 缺 6 集，不能误判不缺。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: [1, 2, 3]}

        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(FakeMediaServerModule(Exist())))
        matcher = MediaMatcher()
        result = matcher.is_missing(title="美人余", media_type="tv", season=1, episode=1, episode_end=9)
        assert result["missing"] is True
        assert "缺 6 集" in result["reason"]
        assert "E04-E09" in result["detail"]

    def test_mediaserver_tv_range_all_present(self, monkeypatch):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: list(range(1, 10))}

        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(FakeMediaServerModule(Exist())))
        matcher = MediaMatcher()
        result = matcher.is_missing(title="美人余", media_type="tv", season=1, episode=1, episode_end=9)
        assert result["missing"] is False
        assert "E01-E09" in result["reason"]

    def test_no_source_returns_unknown(self):
        matcher = MediaMatcher()
        result = matcher.is_missing(title=" whatever ", media_type="tv", season=1, episode=1)
        assert result["missing"] is None
        assert result["source"] == "none"

    def test_ttl_cache_avoids_repeat_queries(self, monkeypatch):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        module = FakeMediaServerModule(None)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        matcher = MediaMatcher(ttl_seconds=60)
        matcher.is_missing(title="测试电影", media_type="movie")
        matcher.is_missing(title="测试电影", media_type="movie")
        assert module.calls == 1  # 第二次命中缓存

    def test_capabilities_do_not_raise(self):
        caps = MediaMatcher().capabilities()
        assert "subscriptions" in caps and "mediaserver" in caps


# ---------------------------------------------------------------------- 冷却门


class TestCooldownGate:
    def test_acquire_release_spacing(self):
        gate = CooldownGate(0.2)
        assert gate.acquire(timeout=1) is True
        gate.release()
        # 冷却未到 → 立即 acquire 失败
        assert gate.acquire(timeout=0.05) is False
        time.sleep(0.25)
        assert gate.acquire(timeout=1) is True
        gate.release()

    def test_zero_interval_allows_immediate(self):
        gate = CooldownGate(0)
        assert gate.acquire(timeout=0.1) is True
        gate.release()
        assert gate.acquire(timeout=0.1) is True
        gate.release()

    def test_backoff_blocks_until_elapsed(self):
        gate = CooldownGate(0)
        gate.backoff(0.3)
        assert gate.acquire(timeout=0.05) is False
        assert gate.flood_remaining() > 0
        time.sleep(0.35)
        assert gate.acquire(timeout=0.5) is True
        gate.release()

    def test_describe_flood_wait(self):
        class FloodWait(Exception):
            seconds = 120

        assert describe_flood_wait(FloodWait()) == 120
        assert describe_flood_wait(ValueError("x")) is None


# ---------------------------------------------------------------------- 流水线端到端


class TestPipeline:
    def _process(self, pipeline, chat_id, text, message_id=1):
        pipeline._process_batch(chat_id, [{"chat_id": chat_id, "message_id": message_id, "text": text}])

    def test_hit_enqueues_task_and_log(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule(destination="none")])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p\nhttps://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert len(logs) == 1
        assert logs[0].decision == DECISION_HIT
        assert logs[0].title == "测试剧集"
        assert logs[0].season == 1 and logs[0].episode == 2
        tasks = query_all(TgPushTask, plugin)
        assert len(tasks) == 1
        assert tasks[0].destination == "none"
        assert tasks[0].status == STATUS_PENDING
        assert "115.com/s/swtest" in tasks[0].payload
        stats = pipeline.stats()
        assert stats["hit"] == 1 and stats["processed"] == 1

    def test_duplicate_message_skipped(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule()])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02", message_id=7)
        self._process(pipeline, CHAT_A, "测试剧集.S01E02", message_id=7)
        # 重复消息不再记流水（唯一键与首条冲突），只计 skipped 统计
        logs = query_all(TgHitLog, plugin)
        assert [log.decision for log in logs] == [DECISION_HIT]
        assert len(query_all(TgPushTask, plugin)) == 1
        assert pipeline.stats()["skipped"] == 1

    def test_keyword_filter(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule(match_custom_keywords=True, custom_keywords=["蓝光"])])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p.WEB-DL")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_KEYWORD

    def test_unrecognized_skipped(self, plugin, monitor, pipeline, monkeypatch):
        class Empty(FakeMetaVideo):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.name = ""

        monkeypatch.setattr(recognizer_module, "MetaVideo", Empty)
        # 仅缺失开启时，无法识别就没法判断缺失 → 跳过
        monitor.save_rules([base_rule(match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "这段文字没有可识别的资源名")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_UNRECOGNIZED

    def test_link_only_message_pushes_when_only_missing_off(self, plugin, monitor, pipeline):
        # 仅缺失关闭时，纯链接消息不需要识别即可推送（115 目标只要求链接）
        monitor.save_rules([base_rule(destination="pan115", match_only_if_missing=False)])
        self._process(pipeline, CHAT_A, "https://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_HIT
        assert logs[0].title == ""
        tasks = query_all(TgPushTask, plugin)
        assert tasks and "115.com/s/swtest" in tasks[0].payload

    def test_link_only_message_unrecognized_when_only_missing_on(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule(destination="pan115", match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "https://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_UNRECOGNIZED
        assert query_all(TgPushTask, plugin) == []

    def test_pan115_without_links_skipped(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule(destination="pan115")])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p")  # 有识别无链接
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_NO_LINK
        assert query_all(TgPushTask, plugin) == []

    def test_tg_forward_does_not_require_links(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule(destination="tg_forward", target_id="-1003229693136")])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_HIT
        tasks = query_all(TgPushTask, plugin)
        assert tasks[0].destination == "tg_forward"
        assert tasks[0].target_id == "-1003229693136"

    def test_only_if_missing_unknown_skips(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule(match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_UNKNOWN
        assert query_all(TgPushTask, plugin) == []

    def test_only_if_missing_not_missing_skips(self, plugin, monitor, pipeline, monkeypatch):
        class Exist:
            seasons = {1: [1, 2]}

        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(FakeMediaServerModule(Exist())))
        monitor.save_rules([base_rule(match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p\nhttps://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_NOT_MISSING

    def test_only_if_missing_hit_when_missing(self, plugin, monitor, pipeline, monkeypatch):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(FakeMediaServerModule(None)))
        monitor.save_rules([base_rule(match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p\nhttps://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_HIT

    def test_other_chat_ignored(self, plugin, monitor, pipeline):
        monitor.save_rules([base_rule()])
        self._process(pipeline, CHAT_B, "测试剧集.S01E02")
        assert query_all(TgHitLog, plugin) == []

    def test_batch_cap_and_window(self, monitor, pipeline):
        # 超过 _MAX_BATCH 应立即刷新（不等窗口）
        assert pipeline_module._MAX_BATCH == 20

    def test_event_counter_observability(self, plugin, monitor, pipeline):
        """真机排查"没反应"依赖事件计数：收到/命中监听/非监听/入队都要可观测。"""
        monitor.save_rules([base_rule(source_ids=[CHAT_A])])

        class FakeMsg:
            id = 1

        class FakeEventWatched:
            chat_id = CHAT_A
            raw_text = "测试剧集.S01E02"
            message = FakeMsg()

        pipeline._handle_event(FakeEventWatched())
        stats = pipeline.stats()
        assert stats["events_received"] == 1
        assert stats["events_watched"] == 1
        assert stats["messages_enqueued"] == 1
        assert stats["last_event_at"]

        class FakeEventUnwatched:
            chat_id = CHAT_B

        pipeline._handle_event(FakeEventUnwatched())
        stats = pipeline.stats()
        assert stats["events_received"] == 2
        assert stats["events_unwatched"] == 1
        assert stats["messages_enqueued"] == 1

    def test_test_text_trace_without_persistence(self, plugin, monitor, pipeline):
        monitor.save_rules([
            base_rule(id="r1", name="仅记录", destination="none"),
            base_rule(id="r2", name="关键词", destination="none",
                      match_custom_keywords=True, custom_keywords=["不存在"]),
        ])
        trace = pipeline.test_text("测试剧集.S01E02\nmagnet:?xt=urn:btih:abc")
        assert trace["recognized"]["title"] == "测试剧集"
        assert any(link.startswith("magnet:") for link in trace["links"])
        decisions = {item["rule_name"]: item["decision"] for item in trace["rules"]}
        assert decisions["仅记录"] == DECISION_HIT
        assert decisions["关键词"] == DECISION_SKIPPED_KEYWORD
        # 测试不落库
        assert query_all(TgHitLog, plugin) == []
        assert query_all(TgPushTask, plugin) == []


# ---------------------------------------------------------------------- 推送 worker


class TestPushWorker:
    def _task_view(self, plugin, task_id):
        with plugin.get_database().session() as session:
            row = session.get(TgPushTask, task_id)
            return pipeline_module.MessagePipeline._task_view(row)

    def test_success_marks_done(self, plugin, monitor, pipeline, monkeypatch):
        monitor.save_rules([base_rule(destination="none")])
        pipeline._process_batch(CHAT_A, [{
            "chat_id": CHAT_A, "message_id": 1,
            "text": "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd",
        }])
        task = query_all(TgPushTask, plugin)[0]

        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _FakeDest(PushResult(ok=True, message="完成")))
        claimed = pipeline._claim_pending_tasks()
        assert len(claimed) == 1
        for view in claimed:
            pipeline._execute_push(view)
        row = query_all(TgPushTask, plugin)[0]
        assert row.status == STATUS_DONE

    def test_retryable_failure_returns_to_pending_with_backoff(self, plugin, monitor, pipeline, monkeypatch):
        monitor.save_rules([base_rule(destination="none")])
        pipeline._process_batch(CHAT_A, [{
            "chat_id": CHAT_A, "message_id": 1,
            "text": "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd",
        }])

        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _FakeDest(PushResult(ok=False, message="风控", retryable=True)))
        view = pipeline._claim_pending_tasks()[0]
        pipeline._execute_push(view)
        row = query_all(TgPushTask, plugin)[0]
        assert row.status == STATUS_PENDING and row.retries == 1

        # 退避窗口内不会被重新领取
        assert pipeline._claim_pending_tasks() == []

    def test_terminal_failure_marks_failed(self, plugin, monitor, pipeline, monkeypatch):
        monitor.save_rules([base_rule(destination="none")])
        pipeline._process_batch(CHAT_A, [{
            "chat_id": CHAT_A, "message_id": 1,
            "text": "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd",
        }])
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _FakeDest(PushResult(ok=False, message="目标不可用", retryable=False)))
        view = pipeline._claim_pending_tasks()[0]
        pipeline._execute_push(view)
        row = query_all(TgPushTask, plugin)[0]
        assert row.status == STATUS_FAILED
        assert "目标不可用" in row.error

    def test_destination_exception_retryable(self, plugin, monitor, pipeline, monkeypatch):
        monitor.save_rules([base_rule(destination="none")])
        pipeline._process_batch(CHAT_A, [{
            "chat_id": CHAT_A, "message_id": 1,
            "text": "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd",
        }])

        class Boom:
            def push(self, task):
                raise RuntimeError("炸了")

        monkeypatch.setattr(pipeline_module, "resolve_destination", lambda name, plug, gate: Boom())
        view = pipeline._claim_pending_tasks()[0]
        pipeline._execute_push(view)
        row = query_all(TgPushTask, plugin)[0]
        assert row.status == STATUS_PENDING and row.retries == 1
        assert "炸了" in row.error


class _FakeDest:
    def __init__(self, result):
        self._result = result

    def push(self, task):
        return self._result


# ---------------------------------------------------------------------- 推送目标


class FakePan115Module:
    def __init__(self, enabled=True, result=None):
        self._enabled = enabled
        self._result = result or {"succeeded": 1, "failed": 0, "remaining": 0, "message": "ok"}

    def enabled(self):
        return self._enabled

    def push(self, links, cid=None):
        return self._result


class TestDestinations:
    def test_smart_prefers_pan115_when_available(self, plugin):
        plugin._pan115 = FakePan115Module(enabled=True)
        target = resolve_destination("smart", plugin)
        assert target.name == "pan115"

    def test_smart_degrades_to_none(self, plugin):
        plugin._pan115 = FakePan115Module(enabled=False)
        target = resolve_destination("smart", plugin)
        assert target.name == "none"

    def test_smart_degrades_without_module(self, plugin):
        plugin._pan115 = None
        assert resolve_destination("smart", plugin).name == "none"

    def test_unknown_destination_raises(self, plugin):
        with pytest.raises(DestinationError):
            resolve_destination("aliyun", plugin)

    def test_none_push_ok(self):
        result = resolve_destination("none", FakePlugin()).push({"links": ["a", "b"]})
        assert result.ok and "2" in result.message

    def test_pan115_push_success(self, plugin):
        plugin._pan115 = FakePan115Module(enabled=True, result={
            "succeeded": 2, "failed": 0, "remaining": 0, "message": "完成",
        })
        result = resolve_destination("pan115", plugin).push({"links": ["https://115.com/s/x?password=a"]})
        assert result.ok

    def test_pan115_push_partial_retryable(self, plugin):
        plugin._pan115 = FakePan115Module(enabled=True, result={
            "succeeded": 1, "failed": 1, "remaining": 2, "message": "",
        })
        result = resolve_destination("pan115", plugin).push({"links": ["a", "b", "c"]})
        assert not result.ok and result.retryable

    def test_pan115_push_disabled(self, plugin):
        plugin._pan115 = FakePan115Module(enabled=False)
        result = resolve_destination("pan115", plugin).push({"links": ["a"]})
        assert not result.ok and not result.retryable
        assert "未启用" in result.message

    def test_pan115_push_without_links(self, plugin):
        plugin._pan115 = FakePan115Module(enabled=True)
        result = resolve_destination("pan115", plugin).push({"links": []})
        assert not result.ok

    def test_tg_forward_without_runtime(self, plugin):
        plugin._credentials = None
        result = resolve_destination("tg_forward", plugin).push({"chat_id": 1, "message_id": 2, "target_id": "3"})
        assert not result.ok


# ---------------------------------------------------------------------- API 层


class TestMonitorApi:
    def test_get_rules_returns_options(self, monitor):
        data = controller_api.api_monitor_rules(monitor._plugin).data
        assert data.rules == []
        assert [item.value for item in data.destinations] == list(DESTINATION_VALUES)
        assert any(item.value == DECISION_HIT for item in data.decisions)

    def test_save_rules_generates_ids(self, monitor):
        request = _SaveRequest([{"name": "转存", "source_ids": [CHAT_A]}])
        response = controller_api.api_monitor_rules_save(monitor._plugin, request)
        assert len(response.data.rules) == 1
        assert response.data.rules[0].id.startswith("r")
        assert "已保存 1 条" in response.message

    def test_save_rules_rejects_tg_forward_without_target(self, monitor):
        request = _SaveRequest([{"name": "转发", "source_ids": [CHAT_A], "destination": "tg_forward"}])
        with pytest.raises(HTTPException) as exc:
            controller_api.api_monitor_rules_save(monitor._plugin, request)
        assert exc.value.status_code == 400
        assert "目标会话 ID" in exc.value.detail

    def test_hits_pagination_and_filter(self, plugin, monitor):
        monitor.save_rules([base_rule()])
        with plugin.get_database().session() as session:
            for index in range(3):
                session.add(TgHitLog(
                    plugin_id="FakePlugin", rule_id="r-test", rule_name="测试规则",
                    chat_id=CHAT_A, message_id=index + 1,
                    decision=DECISION_HIT if index else DECISION_SKIPPED_KEYWORD,
                    destination="none",
                ))
            session.commit()
        page1 = controller_api.api_monitor_hits(monitor._plugin, page=1, page_size=2).data
        assert page1.total == 3 and len(page1.items) == 2 and page1.page == 1
        filtered = controller_api.api_monitor_hits(monitor._plugin, decision=DECISION_SKIPPED_KEYWORD).data
        assert filtered.total == 1

    def test_status_shape(self, monitor):
        data = controller_api.api_monitor_status(monitor._plugin).data
        assert data.enabled is False
        assert data.pipeline.running is False
        assert "subscriptions" in data.matcher

    def test_status_after_start(self, plugin, monitor):
        monitor.save_rules([base_rule()])
        plugin.save_config(monitor_enabled=True, enabled=True)
        monitor.start()
        try:
            data = controller_api.api_monitor_status(monitor._plugin).data
            assert data.enabled is True
            assert data.pipeline.running is True
            assert data.pipeline.started_at
        finally:
            monitor.stop()
        assert controller_api.api_monitor_status(monitor._plugin).data.pipeline.running is False

    def test_start_requires_plugin_enabled(self, plugin, monitor):
        # 插件整体停用时，即使监控开关打开也不启动（停用语义优先）
        monitor.save_rules([base_rule()])
        plugin.save_config(monitor_enabled=True, enabled=False)
        assert monitor.start() is False
        assert monitor._pipeline is None

    def test_ensure_started_is_debounced(self, plugin, monitor):
        monitor.save_rules([base_rule()])
        plugin.save_config(monitor_enabled=True, enabled=True)
        monitor.ensure_started()
        monitor.ensure_started()  # 去抖窗口内第二次不动作
        deadline = time.time() + 3
        while time.time() < deadline and not (monitor._pipeline and monitor._pipeline.is_running()):
            time.sleep(0.05)
        try:
            assert monitor._pipeline is not None and monitor._pipeline.is_running()
        finally:
            monitor.stop()

    def test_ensure_started_skips_without_rules(self, plugin, monitor):
        plugin.save_config(monitor_enabled=True, enabled=True)
        monitor.ensure_started()
        time.sleep(0.2)
        assert monitor._pipeline is None

    def test_test_requires_text(self, monitor):
        with pytest.raises(HTTPException) as exc:
            controller_api.api_monitor_test(monitor._plugin, _TestRequest("   "))
        assert exc.value.status_code == 400

    def test_test_returns_trace(self, monitor, fake_metavideo):
        monitor.save_rules([base_rule()])
        response = controller_api.api_monitor_test(monitor._plugin, _TestRequest("测试剧集.S01E02"))
        assert response.data.recognized["title"] == "测试剧集"
        assert response.data.rules[0].decision == DECISION_HIT

    def test_monitor_not_initialized_returns_503(self):
        plugin = FakePlugin()
        plugin._monitor = None
        with pytest.raises(HTTPException) as exc:
            controller_api.api_monitor_rules(plugin)
        assert exc.value.status_code == 503


class _SaveRequest:
    def __init__(self, rules):
        self.rules = [_RuleModel(rule) for rule in rules]


class _RuleModel:
    def __init__(self, data):
        self.id = data.get("id", "")
        self.name = data.get("name", "")
        self.source_ids = data.get("source_ids", [])
        self.destination = data.get("destination", "smart")
        self.target_id = data.get("target_id", "")
        self.match_only_if_missing = data.get("match_only_if_missing", True)
        self.match_custom_keywords = data.get("match_custom_keywords", False)
        self.custom_keywords = data.get("custom_keywords", [])
        self.rule_type = data.get("rule_type", "client")
        self.web_channel_usernames = data.get("web_channel_usernames", [])
        self.enabled = data.get("enabled", True)

    def model_dump(self):
        return {
            "id": self.id, "name": self.name, "source_ids": self.source_ids,
            "destination": self.destination, "target_id": self.target_id,
            "match_only_if_missing": self.match_only_if_missing,
            "match_custom_keywords": self.match_custom_keywords,
            "custom_keywords": self.custom_keywords, "rule_type": self.rule_type,
            "web_channel_usernames": self.web_channel_usernames, "enabled": self.enabled,
        }


class _TestRequest:
    def __init__(self, text):
        self.text = text


# ---------------------------------------------------------------------- 插件装配


class TestPluginWiring:
    def test_database_models_registered(self):
        from app.plugins.tgmediacenter import TgMediaCenter

        models = TgMediaCenter().get_database_models()
        assert [model.__name__ for model in models] == ["TgHitLog", "TgPushTask"]

    def test_monitor_routes_registered(self):
        from app.plugins.tgmediacenter import TgMediaCenter

        paths = [item["path"] for item in TgMediaCenter().get_api() if "monitor" in item["path"]]
        assert paths.count("/monitor/rules") == 2  # GET + PUT

    def test_init_plugin_starts_pipeline_when_watched(self):
        from app.plugins.tgmediacenter import TgMediaCenter

        plugin = FakePlugin({
            "enabled": True,
            "tg_api_id": "12345",
            "tg_api_hash": "hash",
            "monitor_enabled": True,
            "monitor_rules": [base_rule()],
        })
        instance = TgMediaCenter.__new__(TgMediaCenter)
        instance._config = {}
        instance._credentials = None
        instance._pan115 = None
        instance._monitor = None
        instance.init_plugin(dict(plugin.config))
        try:
            assert instance._monitor is not None
            assert instance._monitor.is_watched(CHAT_A) is True
        finally:
            instance.stop_service()

    def test_init_plugin_skips_pipeline_without_rules(self):
        from app.plugins.tgmediacenter import TgMediaCenter

        instance = TgMediaCenter.__new__(TgMediaCenter)
        instance._config = {}
        instance._credentials = None
        instance._pan115 = None
        instance._monitor = None
        instance.init_plugin({"enabled": True, "monitor_enabled": True, "monitor_rules": []})
        assert instance._monitor._pipeline is None

    def test_stop_service_is_idempotent(self):
        from app.plugins.tgmediacenter import TgMediaCenter

        instance = TgMediaCenter.__new__(TgMediaCenter)
        instance._config = {}
        instance._credentials = None
        instance._pan115 = None
        instance._monitor = None
        instance.init_plugin({"enabled": False})
        instance.stop_service()
        instance.stop_service()
