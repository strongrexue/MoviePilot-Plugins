"""TMDB 数据源参数与归一的回归测试。

**本文件锁住 0.2.0 的真实事故**：日期过滤必须用
``primary_release_date.gte/lte``（电影）/ ``first_air_date.gte/lte``（剧集），
用 ``release_date.gte`` 会被 TMDB 静默忽略，导致拉回一堆几十年以前的老片。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
# 让插件作为独立的 subscribecenter 包可导入（相对导入需要父包存在）
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.sources.tmdb import TmdbSource  # noqa: E402

TODAY = date.today()


class FakeTmdbApi:
    """记录调用参数的 TMDB 模块替身。"""

    def __init__(self, movies=None, tvs=None, raise_on=None):
        self._movies = movies if movies is not None else []
        self._tvs = tvs if tvs is not None else []
        self._raise_on = raise_on or set()
        self.calls = []

    async def async_discover_movies(self, params):
        """记录并返回预设电影。"""
        self.calls.append(("movie", dict(params)))
        if "movie" in self._raise_on:
            raise RuntimeError("TMDB 电影接口炸了")
        return list(self._movies)

    async def async_discover_tvs(self, params):
        """记录并返回预设剧集。"""
        self.calls.append(("tv", dict(params)))
        if "tv" in self._raise_on:
            raise RuntimeError("TMDB 剧集接口炸了")
        return list(self._tvs)


def movie(mid, rel_date, title="片子", vote=7.0):
    """构造一条 TMDB 电影原始结果。"""
    return {
        "id": mid,
        "title": title,
        "original_title": title,
        "release_date": rel_date,
        "vote_average": vote,
        "popularity": 10.0,
    }


def tv_show(mid, air_date, name="剧", vote=7.0):
    """构造一条 TMDB 剧集原始结果。"""
    return {
        "id": mid,
        "name": name,
        "original_name": name,
        "first_air_date": air_date,
        "vote_average": vote,
        "popularity": 10.0,
    }


CONFIG = {"tmdb_future_days": 3, "min_rating_tmdb": 6.0, "timezone": "Asia/Shanghai"}


# --------------------------------------------------------------------- 参数（核心）

@pytest.mark.asyncio
async def test_movie_uses_primary_release_date_bounds():
    """电影必须用 ``primary_release_date.gte/lte`` —— 不是 ``release_date.gte``。

    这是 0.2.0 事故的根因：``release_date.gte`` 被 TMDB 忽略，配合日期升序
    把 release_date 为空的默片排到最前，拉回的全是 1926 年的片子。
    """
    api = FakeTmdbApi(movies=[movie(1, (TODAY + timedelta(days=3)).isoformat())])
    await TmdbSource(api).fetch(CONFIG)

    movie_params = [p for kind, p in api.calls if kind == "movie"]
    assert movie_params, "未调用电影 discover"
    for params in movie_params:
        assert "primary_release_date.gte" in params
        assert "primary_release_date.lte" in params
        assert "release_date.gte" not in params, "用了会被 TMDB 忽略的错误参数名"
        assert "release_date.lte" not in params
        # 上界必须存在，否则无法表达「未来 N 天」
        assert params["primary_release_date.lte"] > params["primary_release_date.gte"]


@pytest.mark.asyncio
async def test_tv_uses_first_air_date_bounds():
    """剧集必须用 ``first_air_date.gte/lte``。"""
    api = FakeTmdbApi(tvs=[tv_show(2, (TODAY + timedelta(days=2)).isoformat())])
    await TmdbSource(api).fetch(CONFIG)

    tv_params = [p for kind, p in api.calls if kind == "tv"]
    assert tv_params, "未调用剧集 discover"
    for params in tv_params:
        assert "first_air_date.gte" in params
        assert "first_air_date.lte" in params


@pytest.mark.asyncio
async def test_window_bounds_match_configured_days():
    """窗口上下界应与配置的天数一致。"""
    api = FakeTmdbApi(movies=[movie(1, (TODAY + timedelta(days=5)).isoformat())])
    await TmdbSource(api).fetch({**CONFIG, "tmdb_future_days": 7})

    params = next(p for kind, p in api.calls if kind == "movie")
    start = date.fromisoformat(params["primary_release_date.gte"])
    end = date.fromisoformat(params["primary_release_date.lte"])
    assert (end - start).days == 7


@pytest.mark.asyncio
async def test_never_sends_server_side_rating_filter():
    """**不得发送任何 ``vote_average.gte`` 下界**。

    未来 30 天内要上映的片子全都还没人评分（``vote_average=0``），
    服务端评分下界会把它们整体滤掉 —— 实测 ``gte=5.0`` 把 1708 部电影压到 4 部、
    229 部剧集压到 0 部（0.2.1 事故）。评分只在流水线里判断，
    且只排除「有评分且明确过低」的条目。
    """
    api = FakeTmdbApi(
        movies=[movie(1, "2026-11-01")],
        tvs=[tv_show(2, "2026-10-25")],
    )
    await TmdbSource(api, max_pages=2).fetch({**CONFIG, "min_rating_tmdb": 6.0})

    assert api.calls
    for kind, params in api.calls:
        assert "vote_average.gte" not in params, f"{kind} 请求里不该有服务端评分过滤"
        assert "vote_count.gte" not in params


@pytest.mark.asyncio
async def test_keeps_unrated_upcoming_items():
    """未评分（vote=0）的新片必须被保留 —— 那正是「即将上映」的主体。"""
    api = FakeTmdbApi(movies=[
        movie(1, "2026-11-01", vote=0.0),   # 还没人评分的新片
        movie(2, "2026-11-02", vote=8.5),   # 已有点评
    ])
    items = await TmdbSource(api, max_pages=1).fetch(CONFIG)
    assert {i.source_id for i in items} == {"1", "2"}
    by_id = {i.source_id: i for i in items}
    assert by_id["1"].rating is None   # 未评分 → None，不是 0 分
    assert by_id["2"].rating == 8.5


@pytest.mark.asyncio
async def test_uses_popularity_then_date_sorting():
    """先关注度、再日期 —— 保证既有热门也有长尾。"""
    api = FakeTmdbApi(movies=[movie(1, (TODAY + timedelta(days=1)).isoformat())])
    await TmdbSource(api, max_pages=1).fetch(CONFIG)

    sorts = [p["sort_by"] for kind, p in api.calls if kind == "movie"]
    assert "popularity.desc" in sorts
    assert any(s.startswith("primary_release_date") for s in sorts)


# --------------------------------------------------------------------- 归一

@pytest.mark.asyncio
async def test_normalizes_movie_fields_and_native_id():
    """电影归一：标题/年份/定档日期/评分，且自带 TMDB ID 作为 L1 身份来源。"""
    api = FakeTmdbApi(movies=[movie(693134, "2026-11-01", title="沙丘", vote=8.3)])
    items = await TmdbSource(api, max_pages=1).fetch(CONFIG)

    assert len(items) == 1
    item = items[0]
    assert item.source == C.SOURCE_TMDB
    assert item.media_type == C.MEDIA_TYPE_MOVIE
    assert item.title == "沙丘"
    assert item.year == "2026"
    assert item.release_date == "2026-11-01"
    assert item.rating == 8.3
    assert item.native_ids == {"tmdb": "693134"}


@pytest.mark.asyncio
async def test_normalizes_tv_fields():
    """剧集归一：用 ``first_air_date`` 作为定档日期。"""
    api = FakeTmdbApi(tvs=[tv_show(338719, "2026-10-20", name="大展宏图")])
    items = await TmdbSource(api, max_pages=1).fetch(CONFIG)

    assert len(items) == 1
    item = items[0]
    assert item.media_type == C.MEDIA_TYPE_TV
    assert item.title == "大展宏图"
    assert item.release_date == "2026-10-20"


@pytest.mark.asyncio
async def test_drops_items_without_release_date():
    """无定档日期的条目直接丢弃（无法判断「即将开播」）。"""
    api = FakeTmdbApi(movies=[movie(1, ""), movie(2, None), movie(3, "2026-11-01")])
    items = await TmdbSource(api, max_pages=1).fetch(CONFIG)

    ids = {i.source_id for i in items}
    assert ids == {"3"}


@pytest.mark.asyncio
async def test_drops_items_without_id_or_title():
    """无 id / 无标题的条目丢弃。"""
    api = FakeTmdbApi(movies=[
        {"id": None, "title": "无 id", "release_date": "2026-11-01"},
        {"id": 9, "title": "", "release_date": "2026-11-01"},
    ])
    assert await TmdbSource(api, max_pages=1).fetch(CONFIG) == []


@pytest.mark.asyncio
async def test_zero_vote_becomes_none():
    """``vote_average=0`` 视为「暂无评分」，不是 0 分（新片普遍如此）。"""
    api = FakeTmdbApi(movies=[movie(1, "2026-11-01", vote=0.0)])
    items = await TmdbSource(api, max_pages=1).fetch(CONFIG)
    assert items[0].rating is None


@pytest.mark.asyncio
async def test_deduplicates_across_sort_orders():
    """同一条目被两种排序都拉回时只保留一份。"""
    same = movie(555, "2026-11-01")
    api = FakeTmdbApi(movies=[same])
    items = await TmdbSource(api, max_pages=2).fetch(CONFIG)
    assert len(items) == 1


# --------------------------------------------------------------------- 容错

@pytest.mark.asyncio
async def test_movie_failure_does_not_break_tv():
    """电影接口失败不影响剧集（单分支隔离）。"""
    api = FakeTmdbApi(
        tvs=[tv_show(2, "2026-10-25")],
        raise_on={"movie"},
    )
    items = await TmdbSource(api).fetch(CONFIG)
    assert {i.source_id for i in items} == {"2"}


@pytest.mark.asyncio
async def test_both_failing_raises_for_pipeline_to_record():
    """两个分支都失败时抛错，让流水线把该源记为失败（而不是静默 0 条）。"""
    api = FakeTmdbApi(raise_on={"movie", "tv"})
    with pytest.raises(RuntimeError):
        await TmdbSource(api).fetch(CONFIG)
