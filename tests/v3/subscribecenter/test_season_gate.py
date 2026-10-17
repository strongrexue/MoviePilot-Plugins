"""季号守门必须**源无关**地生效（0.6.7 定下的架构不变量）。

背景：从 0.6.0 到 0.6.7 在「季号」上返工 6 次。根本原因不是想不清楚，
而是想用单一规则去覆盖两种截然不同的媒体建模方式：

  国产动画 -> 单季多集（Bangumi「牧神记5」= TMDB 第 1 季第 105 集起）
  日番     -> 严格分季（Bangumi「边缘行者 2」= TMDB 第 2 季）

结论（**新增数据源必须遵循**）：不要解析来源方的季号语义，而是把来源标题
里的季号当**提示**，由 TMDB 的「哪一季还有未播集」裁决。

因此这道守门刻意放在 `IdentityResolver`（源无关层），而不是各个 source
适配器里 —— 任何新源只要能产出 `DiscoveredItem`，就自动继承这套判定。
本文件锁住这个不变量：一旦有人把守门挪进某个源、或加了按 source 分支，
测试会失败。
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.identity import IdentityResolver  # noqa: E402
from subscribecenter.core.model import DiscoveredItem  # noqa: E402

#: 所有「未来可能新增」的源都要经过同一道守门
ALL_SOURCES = [
    C.SOURCE_BANGUMI,
    C.SOURCE_DOUBAN_RSS,
    C.SOURCE_SIMKL,
]


class FakeTmdb:
    """记录守门调用、并按预设裁决的 TMDB 替身。"""

    def __init__(self, writable=True, season=1):
        self.writable = writable
        self.season = season
        self.season_calls = []

    async def search(self, title, year, media_type, *, limit=5):
        """返回一条候选，让 L3 路径能命中。"""
        return (
            {
                "tmdb_id": 555,
                "title": title,
                "year": year,
                "media_type": media_type,
            },
        )

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        """走换算路径。"""
        return {"tmdb_id": "555", "year": None}

    async def resolve_target_season(self, tmdb_id, media_type, season_hint=None):
        """记录调用并返回预设裁决。"""
        self.season_calls.append((tmdb_id, media_type, season_hint))
        return (self.writable, self.season)


def make_item(source, **overrides):
    """构造一条测试条目。"""
    data = {
        "source": source,
        "source_id": "1",
        "title": "某番 第2期",
        "media_type": C.MEDIA_TYPE_TV,
        "year": "2026",
        "release_date": "2026-10-20",
        "native_ids": {},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 源无关

@pytest.mark.asyncio
@pytest.mark.parametrize("source", ALL_SOURCES)
async def test_season_gate_runs_for_every_source(source):
    """任何源的 TV 条目都要过季号守门（新增源自动继承）。"""
    tmdb = FakeTmdb(writable=True, season=2)
    item = await IdentityResolver(tmdb).resolve(
        make_item(source, title="某番 第2期", native_ids={})
    )

    assert item.resolved is not None
    assert tmdb.season_calls, f"{source} 的条目没有走季号守门"
    assert item.season == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ALL_SOURCES)
async def test_finished_verdict_blocks_every_source(source):
    """「没有未播内容」对任何源都意味着不可订。"""
    tmdb = FakeTmdb(writable=False, season=None)
    item = await IdentityResolver(tmdb).resolve(make_item(source, native_ids={}))

    assert item.finished is True
    assert item.writable is False


# --------------------------------------------------------------------- 各解析层

@pytest.mark.asyncio
async def test_gate_applies_on_l1_native_identity():
    """L1（源自带 TMDB id）也要过守门 —— 它同样可能是旧季。"""
    tmdb = FakeTmdb(writable=False, season=None)
    item = await IdentityResolver(tmdb).resolve(
        make_item(C.SOURCE_BANGUMI, native_ids={"tmdb": "999"})
    )
    assert item.resolved is not None
    assert item.finished is True
    assert tmdb.season_calls


@pytest.mark.asyncio
async def test_gate_applies_on_conversion_path():
    """跨源换算（L2）同样要过守门。"""
    tmdb = FakeTmdb(writable=True, season=3)
    item = await IdentityResolver(tmdb).resolve(
        make_item(C.SOURCE_DOUBAN_RSS, native_ids={"douban": "123"})
    )
    assert item.resolved is not None
    assert item.season == 3


@pytest.mark.asyncio
async def test_gate_applies_on_search_path():
    """L3 搜索命中也同样要过守门。"""
    tmdb = FakeTmdb(writable=False, season=None)
    item = await IdentityResolver(tmdb).resolve(
        make_item(C.SOURCE_SIMKL, title="某番", native_ids={})
    )
    assert item.resolved is not None
    assert item.finished is True


# --------------------------------------------------------------------- 边界

@pytest.mark.asyncio
async def test_gate_skips_movies():
    """电影没有「季」的概念，不调用守门。"""
    tmdb = FakeTmdb()
    item = await IdentityResolver(tmdb).resolve(
        make_item(C.SOURCE_DOUBAN_RSS, media_type=C.MEDIA_TYPE_MOVIE, native_ids={"douban": "1"})
    )
    assert item.resolved is not None
    assert not tmdb.season_calls


@pytest.mark.asyncio
async def test_gate_skips_unresolved_items():
    """没解析出身份的条目（待确认）不调用守门，也不抛错。"""

    class NoHit(FakeTmdb):
        async def search(self, title, year, media_type, *, limit=5):
            return ()

    tmdb = NoHit()
    item = await IdentityResolver(tmdb).resolve(make_item(C.SOURCE_SIMKL, native_ids={}))
    assert item.resolved is None
    assert not tmdb.season_calls


@pytest.mark.asyncio
async def test_gate_failure_is_fail_open():
    """守门本身出错时**不拦内容**（宁可多订一条，也不因一次 API 抖动丢条目）。"""

    class Boom(FakeTmdb):
        async def resolve_target_season(self, tmdb_id, media_type, season_hint=None):
            raise RuntimeError("TMDB 抽风")

    item = await IdentityResolver(Boom()).resolve(
        make_item(C.SOURCE_BANGUMI, native_ids={"tmdb": "999"})
    )
    assert item.resolved is not None
    assert item.finished is False
    assert item.writable is True


def test_season_hint_is_only_a_hint():
    """季号提示不是指令：`extract_season_hint` 只提供线索，裁决权在 TMDB。"""
    from subscribecenter.core.identity import extract_season_hint

    # 提示存在
    assert extract_season_hint("牧神记5") == 5
    assert extract_season_hint("赛博朋克：边缘行者 2") == 2
    # 无季号
    assert extract_season_hint("牧神记") is None
    # 纯数字片名不能被当成季号
    assert extract_season_hint("1917") is None
