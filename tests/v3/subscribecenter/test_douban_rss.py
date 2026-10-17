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
    assert parse_sources(value) == expected


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


def test_parse_skips_items_without_release_date():
    """没有上映日期的条目无法做窗口过滤，直接丢弃。"""
    items = DoubanRssSource.parse(FEED)
    assert "日期unknown" not in {item.title for item in items}


def test_parse_skips_items_without_douban_id():
    """没有豆瓣 id 就无法换算 TMDB，丢弃。"""
    items = DoubanRssSource.parse(FEED)
    assert "无豆瓣链接" not in {item.title for item in items}


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
    dates = [item.release_date for item in items]
    assert dates == sorted(dates)


# --------------------------------------------------------------------- 接线

def test_douban_is_implemented_source():
    """豆瓣 RSS 必须登记为已实现源，否则配置里打开也会被跳过。"""
    assert C.SOURCE_DOUBAN_RSS in C.IMPLEMENTED_SOURCES
