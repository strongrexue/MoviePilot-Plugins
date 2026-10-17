"""豆瓣 RSS 数据源的回归测试（0.7.0）。

真机实测确认（RSSHub `diygod/rsshub:latest`）：

- 可用路线：``/douban/movie/coming``、``/douban/movie/playing``、``/douban/movie/weekly``
- 已 404：``/douban/movie/ustop250``、``/douban/movie/new``（新版 RSSHub 移除）
- 条目结构::

    <title>生日快乐</title>
    <link>https://movie.douban.com/subject/37322586/</link>
    <description>… <li>上映日期：2026-10-23(中国大陆)</li> … <li>想看：27357</li> …</description>

- 宿主容器**没有 feedparser**（实测），所以用标准库 ``xml.etree`` 解析。

本文件锁住最易回归的几点：上映日期解析、豆瓣 id 提取、
以及「不拿想看数冒充 popularity」这条接入契约。
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.sources.douban_rss import (  # noqa: E402
    DoubanRssSource,
    parse_sources,
)

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>豆瓣电影-即将上映</title>
  <item>
    <title>生日快乐</title>
    <description>&lt;img src=&quot;x.jpg&quot;&gt;&lt;li&gt;类型：剧情&lt;/li&gt;
      &lt;li&gt;上映日期：2026-10-23(中国大陆)&lt;/li&gt;&lt;li&gt;想看：27357&lt;/li&gt;</description>
    <link>https://movie.douban.com/subject/37322586/</link>
    <category>剧情</category>
  </item>
  <item>
    <title>愤怒的老虎</title>
    <description>&lt;li&gt;上映日期：2026-11-06(中国大陆)&lt;/li&gt;&lt;li&gt;想看：1,234&lt;/li&gt;</description>
    <link>https://movie.douban.com/subject/36000001/</link>
    <category>惊悚</category>
  </item>
  <item>
    <title>日期unknown</title>
    <description>&lt;li&gt;类型：剧情&lt;/li&gt;</description>
    <link>https://movie.douban.com/subject/36000002/</link>
  </item>
  <item>
    <title>无豆瓣链接</title>
    <description>&lt;li&gt;上映日期：2026-10-25&lt;/li&gt;</description>
    <link>https://example.com/x</link>
  </item>
</channel></rss>"""


class FakeResponse:
    """最小响应替身。"""

    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class FakeClient:
    """按 URL 返回预设内容的客户端替身。"""

    def __init__(self, mapping=None, status_code=200, raise_exc=None):
        self._mapping = mapping or {}
        self._status = status_code
        self._raise = raise_exc
        self.calls = []

    async def get(self, url):
        """记录并返回预设响应。"""
        self.calls.append(url)
        if self._raise:
            raise self._raise
        return FakeResponse(self._mapping.get(url, FEED), self._status)


CONFIG = {"douban_rss_sources": ["http://nas:1200/douban/movie/coming"]}


# --------------------------------------------------------------------- 地址解析

@pytest.mark.parametrize(
    "value,expected",
    [
        (["http://a/1"], ["http://a/1"]),
        ("http://a/1", ["http://a/1"]),
        ("http://a/1\nhttp://b/2", ["http://a/1", "http://b/2"]),
        ("http://a/1,http://b/2", ["http://a/1", "http://b/2"]),
        ("http://a/1，http://b/2", ["http://a/1", "http://b/2"]),
        ("  http://a/1  \n\n", ["http://a/1"]),
        ("", []),
        (None, []),
        ([], []),
        # 重复地址只留一个
        ("http://a/1\nhttp://a/1", ["http://a/1"]),
    ],
)
def test_parse_sources(value, expected):
    """地址支持 list / 逗号 / 换行（含全角逗号）。"""
    # parse_sources 现在返回归一化后的 dict 列表（每榜独立配置），这里只比 URL
    assert [entry["url"] for entry in parse_sources(value)] == expected


# --------------------------------------------------------------------- 解析

def test_parse_extracts_release_date_and_douban_id():
    """上映日期与豆瓣 subject id 都要能提出来。"""
    items = DoubanRssSource.parse(FEED, "http://nas:1200/douban/movie/coming")
    first = items[0]

    assert first.source == C.SOURCE_DOUBAN_RSS
    assert first.source_id == "37322586"
    assert first.native_ids == {"douban": "37322586"}
    assert first.title == "生日快乐"
    assert first.release_date == "2026-10-23"
    assert first.year == "2026"
    assert first.media_type == C.MEDIA_TYPE_MOVIE


def test_popularity_must_stay_none():
    """**不得把豆瓣「想看数」塞进 popularity**。

    想看数动辄上万，与 TMDB popularity 量纲完全不同；塞进去会让
    「最低关注度」门槛（默认 15）形同虚设。按接入契约只留在 raw 里。
    """
    items = DoubanRssSource.parse(FEED)
    assert all(item.popularity is None for item in items)
    assert items[0].raw["want"] == 27357
    # 千分位逗号要正确处理
    assert items[1].raw["want"] == 1234


def test_items_without_date_are_marked_date_unknown():
    """没有上映日期的条目**保留但标记** date_unknown。

    榜单类路线（/douban/list/*、/douban/tv/coming）实测**全部没有日期**，
    若直接丢弃则这些路线产出为 0（用户配了 15 条榜单全废）。
    正确做法：标记出来，剧集改用「TMDB 还有没有未播集」判定，
    电影由流水线以「无上映日期」跳过。
    """
    items = {item.title: item for item in DoubanRssSource.parse(FEED)}
    unknown = items["日期unknown"]
    assert unknown.date_unknown is True
    assert unknown.release_date is None
    # 有日期的条目不受影响
    assert items["生日快乐"].date_unknown is False


def test_items_without_douban_id_use_title_as_source_id():
    """榜单类没有 `<link>`（实测 /douban/list/tv_hot 的 link 是空的）。

    此时用标题造一个稳定的源内 id，且**不填 native_ids** ——
    强制走标题搜索 TMDB 而不是跨源换算（实测榜单标题的精确匹配率很高：
    tv_hot 15/15、tv_japanese 10/15）。
    """
    items = {item.title: item for item in DoubanRssSource.parse(FEED)}
    no_id = items["无豆瓣链接"]
    assert no_id.source_id == "title:无豆瓣链接"
    assert no_id.native_ids == {}
    # 有 id 的仍用豆瓣 id
    assert items["生日快乐"].source_id == "37322586"


def test_parse_keeps_genre_and_feed():
    """类型与来源频道留在 raw 里便于排查。"""
    items = DoubanRssSource.parse(FEED, "http://nas:1200/douban/movie/coming")
    assert items[0].raw["genre"] == "剧情"
    assert items[0].raw["feed"] == "豆瓣电影-即将上映"


def test_tv_route_marks_media_type():
    """URL 里含 /tv/ 时按剧集处理（为后续豆瓣剧集路线预留）。"""
    items = DoubanRssSource.parse(FEED, "http://nas:1200/douban/tv/coming")
    assert items[0].media_type == C.MEDIA_TYPE_TV


def test_parse_raises_on_broken_xml():
    """结构损坏要抛出，让流水线把该源标记失败。"""
    with pytest.raises(RuntimeError, match="RSS 解析失败"):
        DoubanRssSource.parse("<rss><channel>坏")


def test_special_titles_are_flagged():
    """特别篇要标出来（海报复用 bangumi 那套标记）。"""
    feed = FEED.replace("生日快乐", "某片 特别篇")
    items = DoubanRssSource.parse(feed)
    assert items[0].special is True


# --------------------------------------------------------------------- 榜单结构

#: 真实榜单条目结构（/douban/list/tv_hot 实测：link 为空、guid 是标题）
LIST_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>豆瓣剧集-实时热门</title>
  <item>
    <title>嫁金钗</title>
    <description>&lt;p&gt;嫁金钗&lt;/p&gt;&lt;p&gt;2026 / 中国大陆 / 剧情 爱情 古装 / 杨龙 / 田曦薇 闫桉&lt;/p&gt;</description>
    <link/>
    <guid isPermaLink="false">嫁金钗</guid>
  </item>
  <item>
    <title>银翼杀手2099</title>
    <description>&lt;p&gt;2026 / 美国 / 科幻&lt;/p&gt;</description>
    <link/>
  </item>
</channel></rss>"""


def test_list_feed_items_carry_year_from_category():
    """榜单条目没有日期，但 category 里带了年份。

    年份只取**开头**的四位年：像「银翼杀手2099」这种片名里的数字
    绝不能被当成上映年份。
    """
    items = {item.title: item for item in DoubanRssSource.parse(LIST_FEED, "http://nas/douban/list/tv_hot")}
    assert items["嫁金钗"].year == "2026"
    assert items["银翼杀手2099"].year == "2026"  # 不是 2099
    assert items["嫁金钗"].date_unknown is True
    assert items["嫁金钗"].media_type == C.MEDIA_TYPE_TV


def test_list_route_without_tv_is_movie():
    """URL 不含 /tv/ 时按电影处理（榜单电影会被流水线按无日期跳过）。"""
    items = DoubanRssSource.parse(LIST_FEED, "http://nas/douban/list/movie_weekly_best")
    assert items[0].media_type == C.MEDIA_TYPE_MOVIE


def test_show_route_is_tv():
    """综艺类路线（/list/show_domestic）按剧集处理。"""
    items = DoubanRssSource.parse(LIST_FEED, "http://nas/douban/list/show_domestic")
    assert items[0].media_type == C.MEDIA_TYPE_TV


def test_per_feed_limit_is_applied():
    """每个榜单只取前 N 条（榜单按名次排列，取前 N 即最热的）。

    实测 /douban/list/tv_hot 有 241 条，不限量会吃光每日额度。
    """
    full = DoubanRssSource.parse(LIST_FEED)
    assert len(full) == 2
    assert len(DoubanRssSource.parse(LIST_FEED, limit=1)) == 1


@pytest.mark.asyncio
async def test_fetch_applies_configured_limit():
    """配置里的 douban_max_items_per_feed 生效。"""
    items = await DoubanRssSource(FakeClient()).fetch(
        {**CONFIG, "douban_max_items_per_feed": 1}
    )
    # 只有一个 URL，每条 feed 只取 1 条
    assert len(items) == 1


# --------------------------------------------------------------------- 抓取

@pytest.mark.asyncio
async def test_fetch_uses_configured_urls():
    """按配置的地址抓取。"""
    client = FakeClient()
    await DoubanRssSource(client).fetch(CONFIG)
    assert client.calls == ["http://nas:1200/douban/movie/coming"]


@pytest.mark.asyncio
async def test_fetch_requires_configured_urls():
    """没配地址要**明确报错**，不能静默返回空（否则等于源隐形失效）。"""
    with pytest.raises(RuntimeError, match="未配置地址"):
        await DoubanRssSource(FakeClient()).fetch({"douban_rss_sources": []})


@pytest.mark.asyncio
async def test_fetch_raises_when_all_urls_fail():
    """全部地址失败才算该源失败。"""
    client = FakeClient(status_code=502)
    with pytest.raises(RuntimeError, match="HTTP 502"):
        await DoubanRssSource(client).fetch(CONFIG)


@pytest.mark.asyncio
async def test_fetch_tolerates_partial_failure():
    """部分地址失败时保留已拿到的内容（不因一个源挂掉丢全部）。"""

    class PartialClient(FakeClient):
        async def get(self, url):
            self.calls.append(url)
            if "broken" in url:
                raise RuntimeError("连不上")
            return FakeResponse(FEED)

    client = PartialClient()
    items = await DoubanRssSource(client).fetch(
        {"douban_rss_sources": ["http://broken/1", "http://nas:1200/douban/movie/coming"]}
    )
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_fetch_dedupes_across_feeds():
    """多个 RSS 有交集时按豆瓣 id 去重。"""
    client = FakeClient()
    items = await DoubanRssSource(client).fetch(
        {
            "douban_rss_sources": [
                "http://nas:1200/douban/movie/coming",
                "http://nas:1200/douban/movie/playing",
            ]
        }
    )
    ids = [item.source_id for item in items]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_fetch_sorts_by_release_date():
    """输出按上映日排序，便于预览阅读。"""
    items = await DoubanRssSource(FakeClient()).fetch(CONFIG)
    # 有日期的排前面（升序），无日期的排后面
    dated = [item.release_date for item in items if item.release_date]
    assert dated == sorted(dated)
    flags = [item.release_date is None for item in items]
    assert flags == sorted(flags), "无日期条目应排在末尾"


# --------------------------------------------------------------------- 接线

def test_douban_is_implemented_source():
    """豆瓣 RSS 必须登记为已实现源，否则配置里打开也会被跳过。"""
    assert C.SOURCE_DOUBAN_RSS in C.IMPLEMENTED_SOURCES


# ------------------------------------------------- 每榜独立配置（1.1.0）

def test_parse_sources_keeps_per_list_params():
    """每榜参数（条数/窗口/想看/开关）必须保留。"""
    from subscribecenter.sources.douban_rss import parse_sources

    parsed = parse_sources([
        {"name": "即将上映", "url": "http://x/movie/coming", "max_items": 10,
         "future_days": 30, "min_want": 500},
        {"name": "关掉的", "url": "http://x/list/tv_hot", "enabled": False},
    ])
    assert len(parsed) == 1, "停用的榜单不应进入抓取"
    entry = parsed[0]
    assert entry["name"] == "即将上映"
    assert entry["max_items"] == 10
    assert entry["future_days"] == 30
    assert entry["min_want"] == 500


def test_list_name_derived_from_url():
    """自定义 URL 也应推导出可读名字，界面上才看得懂是哪条榜单。"""
    from subscribecenter.sources.douban_rss import list_name_of

    assert list_name_of("http://h:1200/douban/movie/coming") == "电影即将上映"
    assert list_name_of("http://h:1200/douban/list/tv_domestic") == "近期热门国产剧"
    assert list_name_of("http://h:1200/douban/whatever") == "whatever"


def test_migration_converts_url_list_to_entries():
    """老配置（裸 URL 列表）升级为每榜配置，且不丢失原有地址。"""
    from subscribecenter.core.constants import _migrate_douban_lists

    migrated = _migrate_douban_lists([
        "http://h:1200/douban/movie/coming",
        "http://h:1200/douban/list/tv_hot",
    ])
    assert [e["url"] for e in migrated] == [
        "http://h:1200/douban/movie/coming",
        "http://h:1200/douban/list/tv_hot",
    ]
    assert all(e["enabled"] for e in migrated)
    assert migrated[0]["name"] == "电影即将上映"


# ------------------------------------------- RSSHub 域名总控（1.2.0）

def test_build_feed_url_joins_domain_and_route():
    """榜单只存路由，实际请求 = 域名 + 路由（换 RSSHub 只改一处）。"""
    from subscribecenter.sources.douban_rss import build_feed_url

    assert (
        build_feed_url("http://192.168.50.134:1200", "/douban/movie/coming")
        == "http://192.168.50.134:1200/douban/movie/coming"
    )
    # 域名带尾斜杠、路由不带前斜杠都要能拼对
    assert (
        build_feed_url("http://h:1200/", "douban/tv/coming")
        == "http://h:1200/douban/tv/coming"
    )
    # 没写协议的域名自动补 https
    assert build_feed_url("rsshub.app", "/douban/movie/coming") == (
        "https://rsshub.app/douban/movie/coming"
    )
    # 完整 URL 原样返回（自定义外部 RSS）
    assert build_feed_url("http://h:1200", "https://other/x.xml") == "https://other/x.xml"
    assert build_feed_url("http://h:1200", "") == ""


def test_simkl_and_justwatch_are_gone():
    """未实现的两个源已彻底移除（配置、源集合、前端都不该再有）。"""
    from subscribecenter.core import constants as C

    assert "simkl" not in C.ALL_SOURCES
    assert "justwatch" not in C.ALL_SOURCES
    assert "enable_simkl" not in C.default_config()
    assert "enable_justwatch" not in C.default_config()


def test_default_rsshub_domain_present():
    """RSSHub 域名总控必须有默认值。"""
    from subscribecenter.core import constants as C

    assert C.default_config().get("rsshub_domain")
