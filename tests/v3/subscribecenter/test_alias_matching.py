"""豆瓣/TMDB 译名差异的兜底匹配（0.8.6）。

真机实测：豆瓣译名与 TMDB 中文名经常不同，而 TMDB 的搜索索引里**没有**
豆瓣那个译名 —— 但 TMDB 的**原始搜索**靠 alternative_titles / 原名能搜到：

    豆瓣「闹鬼酒店」  -> 裸搜 TMDB 返回「酒店有鬼」(255752)
    豆瓣「虚无的十字架」-> 裸搜 TMDB 返回「空洞的十字架」(326140)
    豆瓣「人生交换」  -> 裸搜 TMDB 返回「交换人生」(333359)

问题出在宿主的 `TmdbApi.async_search_tvs`：它在结果上又加了一层
`if title not in item_name: continue`，把这些跨语言结果全丢掉了。
所以这里必须走原始 `/3/search/tv`、`/3/search/movie`。

标题比对在这种场景必然失败，改用「唯一同年候选」判据：
同类型 + 年份差 ≤1 + 只有一个候选。
"""
import sys
from datetime import date
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.host import HostTmdbResolver  # noqa: E402
from subscribecenter.core.identity import (  # noqa: E402
    IdentityResolver,
    match_by_unique_year,
)
from subscribecenter.core.model import DiscoveredItem  # noqa: E402

TODAY = date.today()


def show(**overrides):
    """构造一条剧集条目。"""
    data = {
        "source": C.SOURCE_DOUBAN_RSS,
        "source_id": "title:x",
        "title": "虚无的十字架",
        "media_type": C.MEDIA_TYPE_TV,
        "year": "2026",
        "release_date": None,
        "date_unknown": True,
        "native_ids": {},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


def candidate(tmdb_id, title, year, media_type="tv", original=None):
    """构造一个候选。"""
    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "original_title": original,
        "year": year,
        "media_type": media_type,
    }


# --------------------------------------------------------------------- 严格兜底

def test_unique_same_year_candidate_is_accepted():
    """同类型、同年、唯一候选 -> 命中（豆瓣/TMDB 译名不同的典型场景）。"""
    hit = match_by_unique_year([candidate(326140, "空洞的十字架", "2026")], show())
    assert hit is not None
    assert hit["tmdb_id"] == 326140


def test_year_delta_of_one_is_accepted():
    """年份差 1 年可接受（档期/上星年份口径不同）。"""
    hit = match_by_unique_year([candidate(255752, "酒店有鬼", "2025")], show())
    assert hit is not None


def test_year_delta_too_large_is_rejected():
    """差 2 年以上一律拒绝 —— 那是另一部作品。"""
    assert match_by_unique_year([candidate(1, "同名剧", "2023")], show()) is None


def test_ambiguity_is_rejected():
    """多个候选都符合 -> 歧义，放弃（宁缺毋滥）。"""
    candidates = [
        candidate(1, "A", "2026"),
        candidate(2, "B", "2026"),
    ]
    assert match_by_unique_year(candidates, show()) is None


def test_candidate_without_year_is_ignored():
    """候选没有年份就不参与（无法校验）。"""
    assert match_by_unique_year([candidate(1, "某剧", None)], show()) is None


def test_wrong_media_type_is_ignored():
    """类型不符不参与。"""
    assert match_by_unique_year(
        [candidate(1, "某剧", "2026", media_type="movie")], show()
    ) is None


def test_item_without_year_cannot_use_this_fallback():
    """条目自己没有年份时不能用这套判据。"""
    assert match_by_unique_year([candidate(1, "某剧", "2026")], show(year=None)) is None


# --------------------------------------------------------------------- 搜索绕过

def test_search_raw_does_not_use_host_filtered_search():
    """``search_raw`` 必须走原始 TMDB 接口。

    宿主 ``async_search_tvs`` 会丢弃「条目名不包含查询词」的结果，
    而跨语言译名恰恰都是这种情况。
    """
    import inspect

    source = inspect.getsource(HostTmdbResolver.search_raw)
    assert "/search/tv" in source and "/search/movie" in source
    # 只检查**调用**形态（docstring 里会提到这个方法名）
    assert ".async_search_tvs(" not in source, "又用回了带名称过滤的宿主搜索"


def test_douban_aliases_exists():
    """豆瓣别名查询必须存在（拿 aka / original_title 用）。"""
    assert hasattr(HostTmdbResolver, "douban_aliases")


# --------------------------------------------------------------------- 端到端

class RawTmdb:
    """主搜索空手、裸搜与宽松匹配能命中的替身。"""

    def __init__(self, candidates):
        self.candidates = candidates
        self.terms = []

    async def search(self, title, year, media_type, *, limit=5):
        return ()

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        return None

    async def search_raw(self, term, media_type):
        self.terms.append(term)
        return tuple(self.candidates)

    async def douban_aliases(self, title, media_type, year=None):
        return []

    async def resolve_target_season(self, tmdb_id, media_type, season_hint=None, **kwargs):
        return (True, 1, None)


@pytest.mark.asyncio
async def test_resolver_uses_unique_year_fallback():
    """端到端：标题完全不像，靠「唯一同年」救回。"""
    tmdb = RawTmdb([candidate(326140, "空洞的十字架", "2026")])
    item = await IdentityResolver(tmdb).resolve(show())

    assert item.resolved is not None
    assert item.resolved.media_id == "326140"
    assert "relaxed_unique_year" in item.resolved.reason
    assert tmdb.terms[0] == "虚无的十字架", "应先用条目标题本身做原始搜索"


@pytest.mark.asyncio
async def test_resolver_rejects_ambiguous_fallback():
    """端到端：两个同年候选 -> 不猜，保持待确认。"""
    tmdb = RawTmdb(
        [candidate(1, "A", "2026"), candidate(2, "B", "2026")]
    )
    item = await IdentityResolver(tmdb).resolve(show())
    assert item.resolved is None
