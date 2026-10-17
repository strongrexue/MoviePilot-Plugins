"""episode group 精确订阅（0.8.3）。

真机问题：《药屋少女的呢喃》在 TMDB 被压成 **1 季 60 集**连续编号
（第 49~60 集才是第 3 季）。若按 season=1 订阅，宿主要去补前 48 集旧番 ——
真机实测订阅记录里 `total_episode=60, lack_episode=33`，等于把整部老番重扫。

TMDB 的 `episode_group`（type=6「Seasons」）里 Season 3 = 12 集，
带 `episode_group` + `season=3` 订阅后宿主只追这 12 集。

真机实测（220542）：
    药屋少女的呢喃 第三季   提示=3 -> 可订, 季=3, group=6782169d78cfcd77ed4e89be
    药屋少女的呢喃 第二季   提示=2 -> 可订, 季=1, group=None（该季已播完，不采用）
    牧神记5               提示=5 -> 可订, 季=1, group=None（无分组，行为不变）
"""
import sys
from datetime import date
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.identity import IdentityResolver  # noqa: E402
from subscribecenter.core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from subscribecenter.core.writer import SubscriptionWriter  # noqa: E402

TODAY = date.today()
GROUP = "6782169d78cfcd77ed4e89be"


class GroupTmdb:
    """按预设返回 3 元组裁决的 TMDB 替身。"""

    def __init__(self, writable=True, season=1, group=None):
        self.writable = writable
        self.season = season
        self.group = group
        self.kwargs = None

    async def search(self, title, year, media_type, *, limit=5):
        return (
            {
                "tmdb_id": 220542,
                "title": title,
                "year": year,
                "media_type": media_type,
            },
        )

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        return {"tmdb_id": "220542", "year": None}

    async def resolve_target_season(self, tmdb_id, media_type, season_hint=None, **kwargs):
        self.kwargs = kwargs
        return (self.writable, self.season, self.group)


def anime(**overrides):
    """构造一条番剧条目。"""
    data = {
        "source": C.SOURCE_DOUBAN_RSS,
        "source_id": "37421775",
        "title": "药屋少女的呢喃 第三季",
        "media_type": C.MEDIA_TYPE_TV,
        "year": "2026",
        "release_date": None,
        "date_unknown": True,
        "native_ids": {"douban": "37421775"},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 解析层

@pytest.mark.asyncio
async def test_episode_group_is_carried_to_item():
    """裁决返回 group 时要落到条目上（否则订阅时丢失）。"""
    resolver = IdentityResolver(GroupTmdb(season=3, group=GROUP))
    item = await resolver.resolve(anime())

    assert item.resolved is not None
    assert item.season == 3
    assert item.episode_group == GROUP


@pytest.mark.asyncio
async def test_no_group_when_not_needed():
    """普通分季剧集不该带 group。"""
    resolver = IdentityResolver(GroupTmdb(season=2, group=None))
    item = await resolver.resolve(
        anime(title="赛博朋克：边缘行者 第二季", native_ids={"douban": "37421775"})
    )
    assert item.season == 2
    assert item.episode_group is None


@pytest.mark.asyncio
async def test_group_preference_is_passed_through():
    """配置开关要传给宿主（关掉则不查分组）。"""
    tmdb = GroupTmdb(season=3, group=GROUP)
    resolver = IdentityResolver(tmdb, prefer_episode_group=False)
    await resolver.resolve(anime())
    assert tmdb.kwargs.get("prefer_episode_group") is False


@pytest.mark.asyncio
async def test_two_tuple_verdict_still_works():
    """兼容只返回二元组的实现（早期接口）。"""

    class TwoTupleTmdb(GroupTmdb):
        async def resolve_target_season(self, tmdb_id, media_type, season_hint=None, **kwargs):
            return (True, 2)

    item = await IdentityResolver(TwoTupleTmdb()).resolve(anime())
    assert item.season == 2
    assert item.episode_group is None


# --------------------------------------------------------------------- 写入层

class RecordingBackend:
    """记录 add 调用参数的 backend 替身。"""

    def __init__(self):
        self.calls = []

    async def add(self, title, year, media_source, media_id, media_type,
                  season=None, *, episode_group=None, message=False, exist_ok=False):
        """记录并返回成功。"""
        self.calls.append(
            {"title": title, "season": season, "episode_group": episode_group}
        )
        return 1001, "新增订阅成功"

    async def subscription_exists(self, media_source, media_id, season=None):
        return False

    async def history_exists(self, media_source, media_id, season=None):
        return False


@pytest.mark.asyncio
async def test_writer_passes_episode_group_to_backend():
    """writer 必须把 episode_group 传下去 —— 否则等于没做。"""
    backend = RecordingBackend()
    writer = SubscriptionWriter(backend, daily_limit=0)

    item = anime(
        resolved=ResolvedIdentity("themoviedb", "220542", C.CONFIDENCE_L2),
        season=3,
        episode_group=GROUP,
    )
    report = await writer.write([item], dry_run=False)

    assert report.added_count == 1
    assert backend.calls[0]["season"] == 3
    assert backend.calls[0]["episode_group"] == GROUP


@pytest.mark.asyncio
async def test_writer_sends_none_when_no_group():
    """没有分组时传 None（不要让宿主误以为要按分组订阅）。"""
    backend = RecordingBackend()
    writer = SubscriptionWriter(backend, daily_limit=0)
    item = anime(
        resolved=ResolvedIdentity("themoviedb", "105248", C.CONFIDENCE_L2),
        season=2,
    )
    await writer.write([item], dry_run=False)
    assert backend.calls[0]["episode_group"] is None


# --------------------------------------------------------------------- 配置

def test_prefer_episode_group_defaults_on():
    """默认开启 —— 否则药屋少女这类番会去补几十集旧番。"""
    config = C.default_config()
    assert config["prefer_episode_group"] is True


def test_daily_limit_has_no_hard_cap():
    """每日写入上限必须可以任意设置（0 = 不限）。

    原来前端把 max 写死成 50，用户没法放开测试。
    """
    source = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Config.vue"
    )
    if not source.exists():
        pytest.skip("前端尚未构建")
    text = source.read_text(encoding="utf-8")
    assert 'max="50"' not in text, "写入上限仍被硬限制在 50"
    assert "0 = 不限" in text


def test_max_daily_limit_constant_removed():
    """死常量 MAX_DAILY_LIMIT 已移除（后端从未使用，留在源码里会误导）。"""
    assert not hasattr(C, "MAX_DAILY_LIMIT")
