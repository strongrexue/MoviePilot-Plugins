"""隐形字符清洗 + 同名歧义消解（0.8.7）。

真机反馈的 5 条待确认，逐条查出的三个原因：

1. **标题带零宽字符**：豆瓣「豫见她们 第2季」实际是
   ``'豫见她们 第2季\\u200b'``，尾部一个 U+200B —— 季号剥不掉，
   拿着带隐藏字符的整串搜 TMDB，命中率必然为 0。

2. **同名歧义**：搜「信号」返回 11 条（心动的信号 / 信号 / 心脏信号 …），
   搜「半熟恋人」返回两条同名（2021 / 2012），搜「绑架游戏」有两条都是 2026。
   旧规则「多条命中即放弃」。

3. **续作的年份口径不同**：豆瓣「信号 第二季」写 2026，而 TMDB 那条
   《信号》首播 2016 —— 年份永远是十几年的差。

修法：按标题匹配后，依次用「恰好一条年份在 ±2 内」→「恰好一条有该季未播集」
→「恰好一条存在该季」消歧，都不满足才放弃。
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.host import HostTmdbResolver  # noqa: E402
from subscribecenter.core.identity import (  # noqa: E402
    IdentityResolver,
    sanitize_title,
    strip_season_suffix,
)
from subscribecenter.core.model import DiscoveredItem  # noqa: E402

# --------------------------------------------------------------------- 隐形字符

@pytest.mark.parametrize(
    "raw",
    [
        "豫见她们 第2季\u200b",
        "豫见她们 第2季\ufeff",
        "豫见她们\u200b 第2季",
        "豫见她们\u00a0第2季",
    ],
)
def test_sanitize_removes_invisible_characters(raw):
    """零宽/异常空白必须清掉。"""
    assert sanitize_title(raw) == "豫见她们 第2季"


def test_season_stripping_works_after_sanitize():
    """带零宽字符的标题也要能剥出季号（真机失败的根因）。"""
    assert strip_season_suffix("豫见她们 第2季\u200b") == "豫见她们"
    assert strip_season_suffix("信号 第二季\u200b") == "信号"


def test_douban_titles_are_sanitized_at_ingest():
    """豆瓣源产出条目前也应清洗（防御性）。"""
    from subscribecenter.sources.douban_rss import DoubanRssSource

    feed = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
    <item><title>某剧\u200b</title><link/><guid>g</guid>
    <description>&lt;p&gt;2026 / 中国&lt;/p&gt;</description></item>
    </channel></rss>"""
    items = DoubanRssSource.parse(feed, "http://nas/douban/list/tv_hot")
    assert items and "\u200b" not in items[0].title


# --------------------------------------------------------------------- 消歧

class SeasonTmdb:
    """按预设返回季号裁决的替身。"""

    def __init__(self, verdicts, exists=None):
        self.verdicts = verdicts  # tmdb_id -> (可订, 季)
        self.exists = exists or {}  # tmdb_id -> set(存在的季)
        self.checked = []

    async def search(self, title, year, media_type, *, limit=5):
        return ()

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        return None

    async def search_raw(self, term, media_type):
        return ()

    async def douban_aliases(self, title, media_type, year=None):
        return []

    async def resolve_target_season(self, tmdb_id, media_type, season_hint=None, **kwargs):
        self.checked.append(str(tmdb_id))
        return self.verdicts.get(str(tmdb_id), (False, None, None))

    async def season_exists(self, tmdb_id, media_type, season):
        return int(season) in self.exists.get(str(tmdb_id), set())


def show(title="信号 第二季", year="2026"):
    """构造条目。"""
    return DiscoveredItem(
        source=C.SOURCE_DOUBAN_RSS,
        source_id="title:x",
        title=title,
        media_type=C.MEDIA_TYPE_TV,
        year=year,
        release_date=None,
        date_unknown=True,
        native_ids={},
    )


def candidate(tmdb_id, title, year):
    """构造候选。"""
    return {"tmdb_id": tmdb_id, "title": title, "year": year, "media_type": "tv"}


@pytest.mark.asyncio
async def test_disambiguate_by_upcoming_season():
    """多个同名候选里，只有一条「该季有未播集」-> 选它。

    真机：搜「信号」11 条，正确条目是首播 2016 的韩剧《信号》，靠第 2 季消歧。
    """
    tmdb = SeasonTmdb({"64840": (True, 2)})
    resolver = IdentityResolver(tmdb)
    candidates = [candidate(103147, "心动的信号", "2018"), candidate(64840, "信号", "2016")]

    result = await resolver._disambiguate_by_season(candidates, show())
    assert result is not None
    assert result[0]["tmdb_id"] == 64840
    assert result[1] == 2


@pytest.mark.asyncio
async def test_disambiguate_by_existing_but_finished_season():
    """该季**存在但已播完**也要能唯一定位。

    真机：半熟恋人第五季 30 集已在 2026-06~08 播完。若在这里放弃，
    就会误报成「TMDB 搜不到」；定位成功后由 finished 闸门标注「已播完」。
    """
    tmdb = SeasonTmdb({"154420": (False, None, None)}, exists={"154420": {5}})
    resolver = IdentityResolver(tmdb)
    candidates = [candidate(154420, "半熟恋人", "2021"), candidate(107729, "半熟恋人", "2012")]

    result = await resolver._disambiguate_by_season(candidates, show("半熟恋人 第五季"))
    assert result is not None
    assert result[0]["tmdb_id"] == 154420


@pytest.mark.asyncio
async def test_disambiguate_gives_up_when_still_ambiguous():
    """两条都符合 -> 放弃（宁缺毋滥）。"""
    tmdb = SeasonTmdb({}, exists={"1": {2}, "2": {2}})
    resolver = IdentityResolver(tmdb)
    candidates = [candidate(1, "同名剧", "2020"), candidate(2, "同名剧", "2021")]
    assert await resolver._disambiguate_by_season(candidates, show("同名剧 第二季")) is None


@pytest.mark.asyncio
async def test_disambiguate_requires_season_hint():
    """标题里没有季号时不做这套消歧。"""
    tmdb = SeasonTmdb({"1": (True, 1)})
    resolver = IdentityResolver(tmdb)
    candidates = [candidate(1, "某剧", "2026")]
    assert await resolver._disambiguate_by_season(candidates, show("某剧")) is None


def test_season_exists_is_available():
    """消歧依赖 season_exists，缺了会退化成「搜不到」。"""
    assert hasattr(HostTmdbResolver, "season_exists")
