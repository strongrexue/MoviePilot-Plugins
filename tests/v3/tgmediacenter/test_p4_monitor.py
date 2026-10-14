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
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.plugins.tgmediacenter.core import pipeline as pipeline_module
from app.plugins.tgmediacenter.controller import api as controller_api
from app.plugins.tgmediacenter.controller import schemas as api_schemas
from app.plugins.tgmediacenter.core.cooldown import CooldownGate, describe_flood_wait
from app.plugins.tgmediacenter.destinations import (
    DESTINATION_VALUES,
    DestinationError,
    resolve_destination,
)
from app.plugins.tgmediacenter.destinations.base import PushResult
from app.plugins.tgmediacenter.model.hit_log import (
    DECISION_HIT,
    DECISION_LABELS,
    DECISION_SKIPPED_KEYWORD,
    DECISION_SKIPPED_NO_LINK,
    DECISION_SKIPPED_NOT_MISSING,
    DECISION_SKIPPED_NOT_SUBSCRIBED,
    DECISION_SKIPPED_UNKNOWN,
    DECISION_SKIPPED_UNRECOGNIZED,
    KIND_FORWARD,
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

FRONTEND_DECISION_JS = (
    Path(__file__).resolve().parents[3]
    / "plugins.v3" / "tgmediacenter" / "src" / "components" / "decision.js"
)


def _frontend_decision_labels() -> dict:
    """从 ``src/components/decision.js`` 解析决策中文映射（跨端一致性的前端一侧）。"""
    text = FRONTEND_DECISION_JS.read_text(encoding="utf-8")
    block = text.split("const DECISION_LABELS = {", 1)[1].split("}", 1)[0]
    return {m.group(1): m.group(2) for m in re.finditer(r"(\w+):\s*'([^']+)'", block)}


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


# ---------------------------------------------- 媒体库查询分层（1.4.6）用的替身


class FakeExist:
    """宿主 ``ExistMediaInfo`` 的最小替身。"""

    def __init__(self, seasons=None, itemid="", server="emby") -> None:
        self.seasons = dict(seasons or {})
        self.itemid = itemid
        self.server = server


class FakeLibrary:
    def __init__(self, id="lib-1", type="电视剧", name="剧集") -> None:
        self.id = id
        self.item_id = id
        self.type = type
        self.name = name


class FakeLibraryItem:
    """媒体库条目（``get_items`` 的产出）。"""

    def __init__(self, item_id, title, year="", item_type="Series", original_title="") -> None:
        self.item_id = item_id
        self.id = item_id
        self.title = title
        self.original_title = original_title
        self.year = year
        self.item_type = item_type


class FakeItemInfo:
    def __init__(self, year="") -> None:
        self.year = year


class FakeEmbyClient:
    """Emby 客户端替身：只带分层查询用到的公开方法。"""

    def __init__(self, items=None, item_years=None, episodes=("", {}), libraries=None) -> None:
        self._items = list(items or [])
        self._item_years = dict(item_years or {})
        self._episodes = episodes
        self._libraries = [FakeLibrary()] if libraries is None else list(libraries)
        self.library_calls = 0
        self.library_items_calls = 0
        self.episode_probe_calls = 0

    def get_librarys(self, *args, **kwargs):
        self.library_calls += 1
        return list(self._libraries)

    def get_items_count(self, parent, *args, **kwargs):
        return len(self._items)

    def get_items(self, parent, *args, **kwargs):
        self.library_items_calls += 1
        return iter(list(self._items))

    def get_iteminfo(self, itemid):
        year = self._item_years.get(str(itemid))
        return FakeItemInfo(year=year) if year is not None else None

    def get_tv_episodes(self, **kwargs):
        self.episode_probe_calls += 1
        return self._episodes


class FakeHelperWithInstance:
    """把指定模块 + 自造客户端实例装配成 MediaServerHelper。"""

    def __init__(self, module, instance) -> None:
        self._module = module
        self._instance = instance

    def iterate_module_instances(self):
        class _Service:
            name = "emby"
            module = self._module
            instance = self._instance

        return iter([_Service()])


class FakeYearSensitiveModule:
    """真机 Emby 行为镜像：带年份查不到，不带年份才查得到。"""

    def __init__(self, exist=None) -> None:
        self._exist = exist
        self.calls = 0
        self.years = []

    def media_exists(self, mediainfo, itemid=None, server=None):
        self.calls += 1
        self.years.append(getattr(mediainfo, "year", None))
        if itemid:
            return self._exist
        return self._exist if not getattr(mediainfo, "year", None) else None


class FakeLibraryOnlyModule:
    """只在给定 itemid 时命中（模拟"必须靠条目索引才找得到"的库）。"""

    def __init__(self, exist=None) -> None:
        self._exist = exist
        self.calls = 0
        self.itemids = []

    def media_exists(self, mediainfo, itemid=None, server=None):
        self.calls += 1
        self.itemids.append(itemid)
        return self._exist if itemid else None


class FakeNameMatchingModule:
    """模拟宿主 Emby：库内有一组条目名，只有 ``Name`` **完全相等**才命中。

    1.7.9 起插件改用「名称变体」做定向查询，命中判据回到宿主原生口径，
    因此这条替身按「名字集合」建模，而不是按 item_id 建模。
    """

    def __init__(self, names=None, exist=None) -> None:
        self._names = set(names or ())
        self._exist = exist
        self.calls = 0
        self.names_tried = []

    def media_exists(self, mediainfo, itemid=None, server=None):
        self.calls += 1
        name = str(getattr(mediainfo, "title", "") or "")
        self.names_tried.append(name)
        if itemid:
            return self._exist
        return self._exist if name in self._names else None



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

    def test_require_subscription_gates_unsubscribed(self, monkeypatch):
        """方案 A 订阅门禁：订阅数据源可用但资源未订阅 → 判「未订阅」，不落媒体库。"""
        matcher = self._matcher_with_subscriptions(monkeypatch, [
            FakeSubscription("其他剧集", year="2023", season=1, lack_episode=0),
        ])
        module = FakeMediaServerModule(None)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        result = matcher.is_missing(
            title="测试剧集", year="2023", media_type="tv", season=1, episode=2,
            require_subscription=True,
        )
        assert result["missing"] is False
        assert result["reason"] == "未订阅"
        assert result["source"] == "subscription"
        # 关键：门禁生效时压根不该去查媒体服务器
        assert module.calls == 0

    def test_require_subscription_off_falls_back_to_mediaserver(self, monkeypatch):
        """未开启订阅门禁（默认）时，未订阅资源仍按媒体库判断——旧行为保持不变。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        module = FakeMediaServerModule(None)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        result = MediaMatcher().is_missing(title="测试电影", year="2023", media_type="movie")
        assert result["missing"] is True
        assert result["source"] == "mediaserver"
        # 1.4.6 起：按年份未命中会再按"仅片名"复核一次（宿主按年份精确匹配，
        # 资源名年份与库内年份常有偏差）；1.7.9 起还会用少量「片名 (年份)」
        # 等候选名各做一次定向查询（定向查询，不拉全库）。因此这里是一个
        # 有界的小次数，而不是 1 次。
        assert 2 <= module.calls <= 6

    def test_require_subscription_skipped_when_queries_unavailable(self, monkeypatch):
        """订阅数据源不可用时门禁不生效（没配订阅不能全盘拦截），仍按媒体库判断。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        module = FakeMediaServerModule(None)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        result = MediaMatcher().is_missing(
            title="测试电影", year="2023", media_type="movie", require_subscription=True,
        )
        assert result["missing"] is True
        assert result["source"] == "mediaserver"

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
        # 年份未命中 → 再按"仅片名"复核；1.7.9 起再加少量候选名定向查询
        assert 2 <= module.calls <= 6

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

    def test_subscription_lack_does_not_override_media_library(self, monkeypatch):
        """核心回归（1.4.4 真机踩坑）：新建订阅 lack_episode 默认等于总集数，
        不能据此判"缺"——媒体库已有 S01E10 就该判不缺，而不是把全部候选推出去。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([
            FakeSubscription("美人余", year="2026", season=1, lack_episode=34),
        ]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: list(range(1, 11))}  # 库里 E01-E10

        module = FakeMediaServerModule(Exist())
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        result = MediaMatcher().is_missing(
            title="美人余", year="2026", media_type="tv", season=1, episode=10,
            require_subscription=True,
        )
        assert result["missing"] is False
        assert result["source"] == "mediaserver"
        assert module.calls == 1

    def test_subscription_lack_falls_back_when_media_library_unavailable(self, monkeypatch):
        """媒体库不可用时才用订阅的缺集数兜底（此时没有更权威的数据源）。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([
            FakeSubscription("测试剧集", year="2023", season=1, lack_episode=3),
        ]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", False)
        result = MediaMatcher().is_missing(
            title="测试剧集", year="2023", media_type="tv", season=1, episode=2,
            require_subscription=True,
        )
        assert result["missing"] is True
        assert result["source"] == "subscription"
        assert "缺 3 集" in result["reason"]

    def test_media_lookup_cached_across_episodes(self, monkeypatch):
        """逐集判断共用一次 media_exists：34 条候选不该打 34 次媒体服务器。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)

        class Exist:
            seasons = {1: list(range(1, 11))}

        module = FakeMediaServerModule(Exist())
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        matcher = MediaMatcher()
        for episode in range(1, 11):
            verdict = matcher.is_missing(
                title="美人余", media_type="tv", season=1, episode=episode,
            )
            assert verdict["missing"] is False
        assert module.calls == 1

    def test_media_lookup_not_queried_when_subscription_complete(self, monkeypatch):
        """订阅 lack_episode=0 的快速通道保留：此时不必查媒体库。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([
            FakeSubscription("测试剧集", year="2023", season=1, lack_episode=0),
        ]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        module = FakeMediaServerModule(None)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(module))
        result = MediaMatcher().is_missing(
            title="测试剧集", year="2023", media_type="tv", season=1, episode=2,
        )
        assert result["missing"] is False
        assert module.calls == 0

    def test_media_lookup_without_instance_returns_unknown(self, monkeypatch):
        """媒体服务器没实例时不能当成"不存在"（宿主会返回 None），要退回订阅判断。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([
            FakeSubscription("测试剧集", year="2023", season=1, lack_episode=2),
        ]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "MediaServerHelper", lambda: FakeMediaServerHelper(None))
        result = MediaMatcher().is_missing(
            title="测试剧集", year="2023", media_type="tv", season=1, episode=2,
        )
        assert result["missing"] is True
        assert result["source"] == "subscription"

    def test_capabilities_do_not_raise(self):
        caps = MediaMatcher().capabilities()
        assert "subscriptions" in caps and "mediaserver" in caps


class TestMediaLibraryLayers:
    """媒体库查询分层（1.4.6）：宿主 Emby 系按"片名+年份"精确匹配，
    资源名年份/名称与库内不一致时会被判成"库里没有"→ 整部剧全推出去。
    分层放宽必须能兜住，且放宽的命中不能更松到误判"已有"。"""

    def _patch(self, monkeypatch, module, instance):
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", False)
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", True)
        monkeypatch.setattr(
            matcher_module, "MediaServerHelper", lambda: FakeHelperWithInstance(module, instance)
        )

    def test_year_mismatch_falls_back_to_title_only(self, monkeypatch):
        """资源名年份（2026）与库内刮削年份不一致：仅片名命中即算已有。"""
        exist = FakeExist({1: list(range(1, 11))})
        module = FakeYearSensitiveModule(exist)
        self._patch(monkeypatch, module, FakeEmbyClient())
        result = MediaMatcher().is_missing(
            title="林间鸽踪", year="2026", media_type="tv", season=1, episode=5
        )
        assert result["missing"] is False
        assert result["source"] == "mediaserver"
        assert module.years == ["2026", None]  # 先按年份、再放宽到仅片名

    def test_title_only_hit_rejected_when_library_year_differs(self, monkeypatch):
        """同名不同年（翻拍）：仅片名命中但库内年份不符 → 不采用，避免漏推。"""
        exist = FakeExist({1: list(range(1, 11))}, itemid="s1")
        module = FakeYearSensitiveModule(exist)
        instance = FakeEmbyClient(item_years={"s1": "2019"}, episodes=("", {}))
        self._patch(monkeypatch, module, instance)
        result = MediaMatcher().is_missing(
            title="红楼梦", year="2026", media_type="tv", season=1, episode=5
        )
        assert result["missing"] is True
        assert "2019" in result["detail"]

    def test_name_variant_matches_suffixed_library_name(self, monkeypatch):
        """库内命名带年份后缀（"林间鸽踪 (2026)"）：按名称变体定向查询命中。

        1.7.9：取代 1.4.6 的「全量条目索引」——不再把整个库拉下来建索引，
        而是拿「片名 (年份)」等少量候选名各查一次。
        """
        exist = FakeExist({1: list(range(1, 11))})
        module = FakeNameMatchingModule({"林间鸽踪 (2026)"}, exist)
        self._patch(monkeypatch, module, FakeEmbyClient())
        result = MediaMatcher().is_missing(
            title="林间鸽踪", year="2026", media_type="tv", season=1, episode=5
        )
        assert result["missing"] is False
        assert "林间鸽踪 (2026)" in module.names_tried  # 用了带后缀的候选名

    def test_name_variant_rejects_incompatible_year(self, monkeypatch):
        """候选名命中但库内年份不符（翻拍）：不采用，避免漏推。"""
        exist = FakeExist({1: list(range(1, 11))}, itemid="s1")
        module = FakeNameMatchingModule({"林间鸽踪 (2026)"}, exist)
        instance = FakeEmbyClient(item_years={"s1": "2019"})
        self._patch(monkeypatch, module, instance)
        result = MediaMatcher().is_missing(
            title="林间鸽踪", year="2026", media_type="tv", season=1, episode=5
        )
        assert result["missing"] is True
        assert "2019" in result["detail"]

    def test_name_variant_probe_is_bounded(self, monkeypatch):
        """候选名探测有明确上限，不随库规模或片名异常而膨胀。"""
        module = FakeNameMatchingModule(set())
        self._patch(monkeypatch, module, FakeEmbyClient())
        MediaMatcher().is_missing(
            title="某剧", year="2026", media_type="tv", season=1, episode=1
        )
        # 片名+年份(1) + 仅片名(1) + 至多 4 个候选名
        assert module.calls <= 6

    def test_lookup_never_pulls_whole_library(self, monkeypatch):
        """1.7.9 回归锁：媒体库兜底只做定向查询，绝不 get_librarys / get_items 全量拉取。

        旧实现会在拿不到条目数时静默全量拉取（30 万级库 → 分钟级卡顿）。
        """
        module = FakeNameMatchingModule(set())
        instance = FakeEmbyClient()
        self._patch(monkeypatch, module, instance)
        result = MediaMatcher().is_missing(
            title="不存在的剧", year="2026", media_type="tv", season=1, episode=1
        )
        assert result["missing"] is True
        assert instance.library_calls == 0        # 没有列库
        assert instance.library_items_calls == 0  # 没有全量拉取条目

    def test_diagnosis_reports_series_without_episodes(self, monkeypatch):
        """库里有条目但一集都没入库：原因要写清楚（否则用户只看到"没找到"）。"""
        module = FakeLibraryOnlyModule(None)
        instance = FakeEmbyClient(episodes=("s1", {}))
        self._patch(monkeypatch, module, instance)
        result = MediaMatcher().is_missing(
            title="林间鸽踪", year="2026", media_type="tv", season=1, episode=1
        )
        assert result["missing"] is True
        assert "没有任何已入库的集" in result["detail"]

    def test_diagnosis_reports_no_matching_series(self, monkeypatch):
        module = FakeLibraryOnlyModule(None)
        instance = FakeEmbyClient(episodes=("", {}))
        self._patch(monkeypatch, module, instance)
        result = MediaMatcher().is_missing(
            title="林间鸽踪", year="2026", media_type="tv", season=1, episode=1
        )
        assert "没有同名剧集条目" in result["detail"]

    def test_diagnosis_survives_instance_without_probe(self, monkeypatch):
        """实例没有探测方法时不能炸（不同媒体服务器方法面不同）。"""
        module = FakeLibraryOnlyModule(None)
        self._patch(monkeypatch, module, _FakeEmbyInstance())
        result = MediaMatcher().is_missing(
            title="林间鸽踪", year="2026", media_type="tv", season=1, episode=1
        )
        assert result["missing"] is True
        assert result["source"] == "mediaserver"


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

    def test_only_if_missing_unsubscribed_skips(self, plugin, monitor, pipeline, monkeypatch):
        """方案 A：订阅可用但该资源未订阅 → 仅缺失判「未订阅」跳过，而非「媒体库已存在」。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([
            FakeSubscription("其他剧集", year="2023", season=1, lack_episode=0),
        ]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", False)
        monitor.save_rules([base_rule(match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p\nhttps://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_SKIPPED_NOT_SUBSCRIBED
        assert query_all(TgPushTask, plugin) == []

    def test_only_if_missing_hit_when_subscription_lacks(self, plugin, monitor, pipeline, monkeypatch):
        """已订阅且有缺集 → 命中推送（门禁不该误伤已订阅资源）。"""
        monkeypatch.setattr(matcher_module, "QUERIES_AVAILABLE", True)
        monkeypatch.setattr(matcher_module, "list_subscriptions", lambda: FakeQueryPage([
            FakeSubscription("测试剧集", year="", season=1, lack_episode=3),
        ]))
        monkeypatch.setattr(matcher_module, "MEDIASERVER_AVAILABLE", False)
        monitor.save_rules([base_rule(match_only_if_missing=True)])
        self._process(pipeline, CHAT_A, "测试剧集.S01E02.2160p\nhttps://115.com/s/swtest?password=abcd")
        logs = query_all(TgHitLog, plugin)
        assert logs[0].decision == DECISION_HIT
        assert query_all(TgPushTask, plugin)

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

    def test_recent_sources_mark_watched(self, plugin, monitor, pipeline):
        """来源记录只收被监听会话：状态卡「来源 ID」行全是监听中的频道。"""
        monitor.save_rules([base_rule(source_ids=[CHAT_A])])

        class FakeMsg:
            id = 9

        class FakeEvent:
            def __init__(self, chat_id):
                self.chat_id = chat_id
                self.raw_text = "x"
                self.message = FakeMsg()

        pipeline._handle_event(FakeEvent(CHAT_A))
        pipeline._handle_event(FakeEvent(CHAT_A))
        pipeline._handle_event(FakeEvent(CHAT_B))

        stats = pipeline.stats()
        sources = {item["chat_id"]: item for item in stats["recent_sources"]}
        assert sources[CHAT_A]["count"] == 2
        assert sources[CHAT_A]["watched"] is True
        assert sources[CHAT_A]["last_at"]
        # 非监听会话不进来源记录（只计 events_unwatched 计数）
        assert CHAT_B not in sources
        assert stats["events_unwatched"] == 1
        # 便于前端直接展示监听 ID 清单
        assert monitor.status()["watched_chat_ids"] == [CHAT_A]

    def test_registered_telethon_handler_is_coroutine(self, plugin, monitor, pipeline):
        """注册给 telethon 的回调必须是协程函数。

        telethon 内部是 ``await callback(event)``（client/updates.py 的
        ``_dispatch_update``）：注册同步回调会让**每条新消息**都抛
        ``TypeError: 'NoneType' object can't be awaited`` 并打印
        「Unhandled exception on _handle_event」——1.7.2 修复的真机日志刷屏。
        """
        import asyncio
        import inspect

        class FakeClient:
            def __init__(self):
                self.handlers = []

            def add_event_handler(self, callback, event=None):
                self.handlers.append(callback)

        class FakeRuntime:
            def __init__(self, client):
                self.client = client

            def is_running(self):
                return True

            def call(self, coro, timeout=None):
                try:
                    return asyncio.run(coro)
                except Exception:
                    # _resolve_watched 在假客户端上必然失败，不影响本断言
                    return False

        client = FakeClient()
        plugin._credentials = type("Creds", (), {"_runtime": FakeRuntime(client)})()
        pipeline._handler = None
        pipeline._register_handler()

        assert client.handlers, "应注册一个 TG 事件回调"
        callback = client.handlers[0]
        assert inspect.iscoroutinefunction(callback), (
            "telethon 会对回调做 await，同步回调会每条消息报 TypeError"
        )
        # 同步处理逻辑本身保持同步（跑在 TG loop 线程里做库读写）
        assert not inspect.iscoroutinefunction(pipeline._handle_event)

    def test_recent_sources_capped(self, plugin, monitor, pipeline):
        """来源记录有上限，不会随海量监听会话无限增长。"""
        many_ids = [100000 + index for index in range(pipeline_module._MAX_RECENT_SOURCES + 10)]
        monitor.save_rules([base_rule(source_ids=many_ids)])
        limit = pipeline_module._MAX_RECENT_SOURCES
        for chat_id in many_ids:

            class FakeMsg:
                id = 1

            class FakeEvent:
                raw_text = "x"
                message = FakeMsg()

                def __init__(self, cid):
                    self.chat_id = cid

            pipeline._handle_event(FakeEvent(chat_id))
        assert len(pipeline._recent_sources) <= limit

    def test_watched_detail_in_stats(self, plugin, monitor, pipeline):
        """stats 暴露监听会话反查结果，未反查时为空列表。"""
        monitor.save_rules([base_rule(source_ids=[CHAT_A])])
        assert pipeline.stats()["watched_detail"] == []

        class FakeEntity:
            title = "测试频道"

        class FakeClient:
            async def get_entity(self, chat_id):
                if chat_id == CHAT_A:
                    return FakeEntity()
                raise ValueError("Could not find the input entity")

        import asyncio
        asyncio.run(pipeline._resolve_watched(FakeClient()))
        detail = pipeline.stats()["watched_detail"]
        assert len(detail) == 1
        assert detail[0]["chat_id"] == CHAT_A
        assert detail[0]["resolved"] is True
        assert detail[0]["title"] == "测试频道"

        # 反查失败的 ID 也要留在列表里并带错误信息（前端展示"反查失败"）
        monitor.save_rules([base_rule(source_ids=[CHAT_A, CHAT_B])])
        asyncio.run(pipeline._resolve_watched(FakeClient()))
        detail = {item["chat_id"]: item for item in pipeline.stats()["watched_detail"]}
        assert detail[CHAT_A]["resolved"] is True
        assert detail[CHAT_B]["resolved"] is False
        assert detail[CHAT_B]["error"]

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

    def test_push_result_annotates_hit_log(self, plugin, monitor, pipeline, monkeypatch):
        """推送终态要回写命中流水：流水里"已入推送队列 #N"能看到结局。"""
        monitor.save_rules([base_rule(destination="none")])
        pipeline._process_batch(CHAT_A, [{
            "chat_id": CHAT_A, "message_id": 1,
            "text": "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd",
        }])
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _FakeDest(PushResult(ok=True, message="完成转存")))
        view = pipeline._claim_pending_tasks()[0]
        pipeline._execute_push(view)
        logs = query_all(TgHitLog, plugin)
        assert "推送成功：完成转存" in logs[0].detail
        assert pipeline.stats()["push_done"] == 1

    def test_push_failure_annotates_hit_log(self, plugin, monitor, pipeline, monkeypatch):
        monitor.save_rules([base_rule(destination="none")])
        pipeline._process_batch(CHAT_A, [{
            "chat_id": CHAT_A, "message_id": 1,
            "text": "测试剧集.S01E02\nhttps://115.com/s/swtest?password=abcd",
        }])
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _FakeDest(PushResult(ok=False, message="Cookie 失效", retryable=False)))
        view = pipeline._claim_pending_tasks()[0]
        pipeline._execute_push(view)
        logs = query_all(TgHitLog, plugin)
        assert "推送失败：Cookie 失效" in logs[0].detail

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


class _BatchDest:
    """支持合并下发（``supports_batch``）的目标替身：一次调用处理全部链接并回报逐条结果。"""

    supports_batch = True

    def __init__(self, fail_links=()):
        self.calls = []
        self._fail = set(fail_links)

    def push(self, task):
        links = list(task.get("links") or [])
        self.calls.append(links)
        failed = [link for link in links if link in self._fail]
        results = [
            {"source": link, "ok": link not in self._fail,
             "message": "转存成功" if link not in self._fail else "转存失败"}
            for link in links
        ]
        return PushResult(
            ok=not failed,
            message=f"成功 {len(links) - len(failed)}，失败 {len(failed)}",
            retryable=False,
            detail={"results": results},
        )


# ---------------------------------------------------------------------- 合并下发


class TestPushCoalescing:
    """同一目标的多条待推送任务应合并成一次调用（1.4.4 真机：16 行"第 1/1 批"）。"""

    def _enqueue(self, plugin, links, message_id):
        from app.plugins.tgmediacenter.core import push_queue

        values = [links] if isinstance(links, str) else list(links)
        return push_queue.enqueue_push(
            plugin.get_database(), "FakePlugin",
            rule_id="r-coalesce", chat_id=CHAT_A, message_id=message_id,
            destination="pan115", links=values, text="测试", title="测试剧集",
        )

    def test_same_destination_tasks_merged_into_single_call(self, plugin, pipeline, monkeypatch):
        for index in range(3):
            self._enqueue(plugin, f"https://115.com/s/swtest{index}?password=abcd", 100 + index)
        dest = _BatchDest()
        monkeypatch.setattr(pipeline_module, "resolve_destination", lambda name, plug, gate: dest)

        groups = pipeline._group_tasks(pipeline._claim_pending_tasks())
        assert len(groups) == 1 and len(groups[0]) == 3
        pipeline._execute_push_group(groups[0])

        assert len(dest.calls) == 1  # 一次调用处理 3 条链接
        assert len(dest.calls[0]) == 3
        rows = query_all(TgPushTask, plugin)
        assert all(row.status == STATUS_DONE for row in rows)

    def test_without_batch_flag_tasks_stay_separate(self, plugin, pipeline, monkeypatch):
        for index in range(3):
            self._enqueue(plugin, f"https://115.com/s/swtest{index}?password=abcd", 200 + index)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _FakeDest(PushResult(ok=True, message="完成")))
        groups = pipeline._group_tasks(pipeline._claim_pending_tasks())
        assert [len(group) for group in groups] == [1, 1, 1]

    def test_group_caps_links_per_call(self, plugin, pipeline, monkeypatch):
        for index in range(3):
            self._enqueue(
                plugin,
                [f"https://115.com/s/sw{index}{n}?password=abcd" for n in range(8)],
                300 + index,
            )
        monkeypatch.setattr(pipeline_module, "resolve_destination", lambda name, plug, gate: _BatchDest())
        groups = pipeline._group_tasks(pipeline._claim_pending_tasks())
        # 8 + 8 = 16 ≤ 20，第三个任务的 8 条会另起一组
        assert [len(group) for group in groups] == [2, 1]

    def test_failed_link_only_affects_its_task(self, plugin, pipeline, monkeypatch):
        bad = "https://115.com/s/swfail?password=abcd"
        self._enqueue(plugin, "https://115.com/s/swok1?password=abcd", 400)
        self._enqueue(plugin, bad, 401)
        dest = _BatchDest(fail_links=[bad])
        monkeypatch.setattr(pipeline_module, "resolve_destination", lambda name, plug, gate: dest)
        groups = pipeline._group_tasks(pipeline._claim_pending_tasks())
        pipeline._execute_push_group(groups[0])

        rows = {row.message_id: row for row in query_all(TgPushTask, plugin)}
        assert rows[400].status == STATUS_DONE
        # 整批只有这一条失败（succeeded 为 0）→ 值得重试，错误信息留下证据
        assert rows[401].status == STATUS_PENDING and rows[401].retries == 1
        assert "成功 0，失败 1" in rows[401].error

    def test_group_without_per_link_results_falls_back_to_batch_verdict(self, plugin, pipeline, monkeypatch):
        self._enqueue(plugin, "https://115.com/s/swok?password=abcd", 500)
        self._enqueue(plugin, "https://115.com/s/swok?password=abcd", 501)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plug, gate: _BatchDestNoDetail())
        groups = pipeline._group_tasks(pipeline._claim_pending_tasks())
        pipeline._execute_push_group(groups[0])
        rows = query_all(TgPushTask, plugin)
        assert all(row.status == STATUS_DONE for row in rows)

    def test_unreported_link_not_marked_done(self, plugin, pipeline, monkeypatch):
        """有逐条结果但某条链接没被回报 = 没处理：不能因为整批 ok 就"假完成"。"""
        good = "https://115.com/s/swgood?password=abcd"
        other = "https://115.com/s/swother?password=abcd"
        self._enqueue(plugin, good, 600)
        self._enqueue(plugin, other, 601)

        class PartialDest:
            supports_batch = True

            def push(self, task):
                return PushResult(
                    ok=True, message="部分", retryable=False,
                    detail={"results": [{"source": good, "ok": True, "message": "转存成功"}]},
                )

        monkeypatch.setattr(pipeline_module, "resolve_destination", lambda name, plug, gate: PartialDest())
        groups = pipeline._group_tasks(pipeline._claim_pending_tasks())
        pipeline._execute_push_group(groups[0])
        rows = {row.message_id: row for row in query_all(TgPushTask, plugin)}
        assert rows[600].status == STATUS_DONE
        assert rows[601].status == STATUS_PENDING and rows[601].retries == 1
        assert "成功 0，失败 1" in rows[601].error


class _BatchDestNoDetail:
    """声明支持合并但不回报逐条结果：worker 用整批结论兜底。"""

    supports_batch = True

    def __init__(self):
        self.calls = 0

    def push(self, task):
        self.calls += 1
        return PushResult(ok=True, message="完成", retryable=False)


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
        # 真机踩坑：筛选项文案来自后端，流水徽章文案来自前端 decision.js，两处必须一致
        not_subscribed = next(
            item for item in data.decisions if item.value == DECISION_SKIPPED_NOT_SUBSCRIBED
        )
        assert not_subscribed.title == "未订阅"

    def test_decision_labels_consistent_across_layers(self, monitor):
        """决策中文文案三层同源：后端选项 = hit_log.DECISION_LABELS = 前端 decision.js。"""
        data = controller_api.api_monitor_rules(monitor._plugin).data
        backend = {item.value: item.title for item in data.decisions}
        assert backend == dict(DECISION_LABELS)
        assert _frontend_decision_labels() == dict(DECISION_LABELS)

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
                    season=1, episode=5,
                    # 第二条带多集区间（S01E05-E06），媒体列拼完整名用
                    episode_end=6 if index == 1 else None,
                    decision=DECISION_HIT if index else DECISION_SKIPPED_KEYWORD,
                    destination="none",
                ))
            session.commit()
        page1 = controller_api.api_monitor_hits(monitor._plugin, page=1, page_size=2).data
        assert page1.total == 3 and len(page1.items) == 2 and page1.page == 1
        filtered = controller_api.api_monitor_hits(monitor._plugin, decision=DECISION_SKIPPED_KEYWORD).data
        assert filtered.total == 1
        # episode_end 要原样带出来（老库迁移补列后同样可读）
        with_end = [item for item in page1.items if item.episode_end == 6]
        assert len(with_end) == 1 and with_end[0].episode == 5 and with_end[0].season == 1

    def test_hits_keyword_filter(self, plugin, monitor):
        """关键词筛选：片名 / 规则名 / 说明 任一命中即列出，且能与决策筛选叠加。"""
        for message_id, (title, rule_name, detail, decision) in enumerate([
            ("玉簟秋", "资源监控", "", DECISION_HIT),
            ("青与碧", "资源监控", "同系列，含玉簟秋彩蛋", DECISION_SKIPPED_KEYWORD),
            ("别的片", "玉簟秋专线", "", DECISION_SKIPPED_KEYWORD),
        ], start=1):
            with plugin.get_database().session() as session:
                session.add(TgHitLog(
                    plugin_id="FakePlugin", rule_id="r-test", rule_name=rule_name,
                    chat_id=CHAT_A, message_id=message_id, title=title, detail=detail,
                    decision=decision, destination="none",
                ))
                session.commit()
        assert controller_api.api_monitor_hits(monitor._plugin, keyword="玉簟秋").data.total == 3
        assert controller_api.api_monitor_hits(monitor._plugin, keyword="青与碧").data.total == 1
        combined = controller_api.api_monitor_hits(
            monitor._plugin, keyword="玉簟秋", decision=DECISION_HIT
        ).data
        assert combined.total == 1 and combined.items[0].title == "玉簟秋"
        # 空关键词即不过滤
        assert controller_api.api_monitor_hits(monitor._plugin, keyword="  ").data.total == 3

    def test_clear_hits_respects_filter_and_kind(self, plugin, monitor):
        """清理流水：不带条件清空本来源，带条件只删筛选结果，且不波及另一种来源。"""
        for message_id, (title, kind) in enumerate([
            ("玉簟秋", "monitor"), ("青与碧", "monitor"), ("玉簟秋", "monitor"),
            ("玉簟秋", KIND_FORWARD),
        ], start=1):
            with plugin.get_database().session() as session:
                session.add(TgHitLog(
                    plugin_id="FakePlugin", rule_id="r-test", rule_name="规则",
                    chat_id=CHAT_A, message_id=message_id, title=title, kind=kind,
                    decision=DECISION_HIT, destination="none",
                ))
                session.commit()

        cleared = controller_api.api_monitor_hits_clear(
            monitor._plugin, api_schemas.MonitorHitsClearRequest(keyword="玉簟秋")
        )
        assert cleared.data.deleted == 2
        assert "已删除 2 条" in cleared.message
        assert controller_api.api_monitor_hits(monitor._plugin).data.total == 1
        # 转发流水不受监控清理影响（同表不同 kind）
        assert monitor.hits(kind=KIND_FORWARD)["total"] == 1

        # 不带条件 = 清空该来源剩余全部
        emptied = controller_api.api_monitor_hits_clear(
            monitor._plugin, api_schemas.MonitorHitsClearRequest()
        )
        assert emptied.data.deleted == 1
        assert controller_api.api_monitor_hits(monitor._plugin).data.total == 0
        assert monitor.hits(kind=KIND_FORWARD)["total"] == 1

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
        assert [model.__name__ for model in models] == ["TgHitLog", "TgMessageCache", "TgPushTask"]

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
