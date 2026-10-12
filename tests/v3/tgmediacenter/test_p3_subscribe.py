"""P3（订阅服务）单元测试。

覆盖不依赖网络的纯逻辑：订阅源常量表、RSS 条目归一、过滤、唯一键生成、
同步入口（dry_run / 无订阅源）与路由合同。真实建订阅走宿主 SubscribeChain，
必须在真机验证。
"""
import pytest

from app.plugins.tgmediacenter.core import subscribe_sources as sources_lib
from app.plugins.tgmediacenter.model.subscribe_seen import SubscribeSeen
from app.plugins.tgmediacenter.modules.subscribe import SubscribeModule


# --------------------------------------------------------------------- 订阅源常量表


def test_source_counts_and_channels():
    """MP 榜单 4 个、豆瓣榜单 15 个，通道正确。"""
    mp = sources_lib.sources_by_channel("mp")
    douban = sources_lib.sources_by_channel("douban")
    assert len(mp) == 4
    assert len(douban) == 15
    assert {s.key for s in mp} == {"tmdb_trending", "tmdb_movie", "tmdb_tv", "bangumi_calendar"}
    # 抽查豆瓣几个关键源
    douban_keys = {s.key for s in douban}
    assert "tv_documentary" in douban_keys
    assert "show_domestic" in douban_keys
    assert "recommended_tv" in douban_keys
    assert "tv_coming" in douban_keys


def test_source_keys_unique():
    """所有订阅源 key 全局唯一。"""
    keys = [s.key for s in sources_lib.ALL_SOURCES]
    assert len(keys) == len(set(keys))


def test_rss_url_build():
    """豆瓣源拼接完整 RSSHub 地址。"""
    source = sources_lib.lookup("tv_hot")
    assert sources_lib.rss_url(source, "https://rsshub.app") == "https://rsshub.app/douban/list/tv_hot"
    # 尾部斜杠容错
    assert sources_lib.rss_url(source, "https://rsshub.app/") == "https://rsshub.app/douban/list/tv_hot"


def test_lookup_unknown():
    """未知 key 返回 None。"""
    assert sources_lib.lookup("not_exist") is None


# --------------------------------------------------------------------- 唯一键


def test_unique_key_priority():
    """豆瓣 ID > tmdb > bangumi > 标题哈希。"""
    assert SubscribeSeen.build_unique_key(douban_id="123") == "douban:123"
    assert SubscribeSeen.build_unique_key(tmdb_id="456") == "tmdb:456"
    assert SubscribeSeen.build_unique_key(bangumi_id="789") == "bangumi:789"
    # 豆瓣 ID 优先于其它
    assert SubscribeSeen.build_unique_key(douban_id="123", tmdb_id="456") == "douban:123"


def test_unique_key_title_fallback():
    """无宿主 ID 时退化为标题哈希，且同输入稳定。"""
    a = SubscribeSeen.build_unique_key(title="某电影", year="2026", media_type="电影")
    b = SubscribeSeen.build_unique_key(title="某电影", year="2026", media_type="电影")
    assert a == b
    assert a.startswith("title:")
    # 不同标题不同 key
    c = SubscribeSeen.build_unique_key(title="另一部", year="2026", media_type="电影")
    assert a != c


# --------------------------------------------------------------------- 豆瓣条目归一


def test_douban_normalize_extracts_id_year_rating():
    """豆瓣 RSS 条目归一：抽豆瓣 ID、年份、评分。"""
    from app.plugins.tgmediacenter.services import douban_source

    source = sources_lib.lookup("tv_hot")
    item = {
        "title": "某剧",
        "link": "https://movie.douban.com/subject/35801234/",
        "description": "2026 / 中国大陆 / 剧情 爱情 / 评分：8.5",
    }
    normalized = douban_source._normalize_item(item, source)
    assert normalized is not None
    assert normalized["douban_id"] == "35801234"
    assert normalized["year"] == "2026"
    assert normalized["vote_average"] == 8.5
    assert normalized["title"] == "某剧"


def test_douban_normalize_skips_empty():
    """标题与链接都为空时跳过。"""
    from app.plugins.tgmediacenter.services import douban_source

    source = sources_lib.lookup("tv_hot")
    assert douban_source._normalize_item({}, source) is None


# --------------------------------------------------------------------- 过滤


def test_pass_filter_rating_and_type():
    """评分下限与媒体类型过滤。"""
    module = SubscribeModule(_StubPlugin())
    item = {"title": "x", "year": "2026", "media_type": "tv", "vote_average": 8.0}
    ok, _ = module._pass_filter(item, {"min_rating": 7.0, "media_type": "all"})
    assert ok
    ok, reason = module._pass_filter(item, {"min_rating": 9.0, "media_type": "all"})
    assert not ok and "评分" in reason
    ok, reason = module._pass_filter(item, {"min_rating": 0, "media_type": "movie"})
    assert not ok and "类型" in reason


# --------------------------------------------------------------------- 同步入口


class _StubPlugin:
    plugin_version = "1.3.0"

    def __init__(self, config=None, data=None):
        self._config = dict(config or {})
        self._data = dict(data or {})

    @property
    def config(self):
        return self._config

    def get_data(self, key=None):
        return self._data.get(key)

    def save_data(self, key, value):
        self._data[key] = value

    def del_data(self, key):
        self._data.pop(key, None)

    def save_config(self, **patch):
        self._config.update(patch)

    def get_database(self):
        raise RuntimeError("测试环境无数据库；建订阅行为需真机验证")


def test_sync_without_sources():
    """未启用任何订阅源时给出明确提示。"""
    module = SubscribeModule(_StubPlugin(config={"subscribe_sources": []}))
    result = module.sync()
    assert "未启用" in result["message"]


def test_sync_dry_run_no_db():
    """dry_run 只拉取解析，不碰数据库（但会尝试网络拉取）。"""
    module = SubscribeModule(_StubPlugin())
    # 未启用源 → 直接返回，不触发网络/数据库
    result = module.sync(dry_run=True)
    assert result["created"] == 0


# --------------------------------------------------------------------- 豆瓣 RSS 自解析（1.3.5：不走宿主 RssHelper）


def test_parse_rss_xml_douban_style():
    """标准 RSS 2.0 解析出 title/link/description，且与归一函数衔接。"""
    from app.plugins.tgmediacenter.services import douban_source

    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>豆瓣榜单</title>
    <item>
      <title>韩剧 第八个</title>
      <link>https://movie.douban.com/subject/36912345/</link>
      <description>&lt;p&gt;8.7分&lt;/p&gt;2025 韩剧 奇幻</description>
      <pubDate>12 Oct 2026 21:37:20 GMT</pubDate>
      <guid>https://movie.douban.com/subject/36912345/</guid>
    </item>
    </channel></rss>"""
    items = douban_source._parse_rss_xml(xml)
    assert len(items) == 1
    assert items[0]["title"] == "韩剧 第八个"
    assert "/subject/36912345/" in items[0]["link"]

    source = sources_lib.sources_by_channel("douban")[0]
    normalized = douban_source._normalize_item(items[0], source)
    assert normalized["douban_id"] == "36912345"
    assert normalized["year"] == "2025"
    assert normalized["vote_average"] == 8.7


def test_parse_rss_xml_invalid():
    """非法 XML / 空文本返回空列表而不是抛异常。"""
    from app.plugins.tgmediacenter.services import douban_source

    assert douban_source._parse_rss_xml("") == []
    assert douban_source._parse_rss_xml("not xml") == []
    assert douban_source._parse_rss_xml("<rss><channel></channel></rss>") == []
