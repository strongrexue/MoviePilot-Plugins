"""豆瓣源的独立配置：窗口 + 想看人数门槛（0.8.1）。

用户实测反馈两点：

1. 豆瓣应该像 Bangumi 一样有**独立的发现窗口**，而不是借用 TMDB 的
   （日志里「定档日期 2026-10-23 超出 3 天窗口」其实来自 tmdb_future_days）。
2. 希望加一个「想看人数」门槛，从榜单里捞片时滤掉冷门。

观看数只有 coming 类路线提供（``想看：27357``），榜单类路线没有该字段，
因此**缺失时必须放行**，否则整个榜单源会静默失效。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from subscribecenter.core.pipeline import select_items  # noqa: E402

TODAY = date.today()


def douban_item(**overrides):
    """构造一条豆瓣条目。"""
    data = {
        "source": C.SOURCE_DOUBAN_RSS,
        "source_id": "37322586",
        "title": "某片",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": str(TODAY.year),
        "release_date": (TODAY + timedelta(days=1)).isoformat(),
        "rating": None,
        "resolved": ResolvedIdentity("themoviedb", "999"),
        "raw": {"want": 27357},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 窗口

def test_douban_window_is_independent():
    """豆瓣窗口必须是独立的配置项。"""
    config = C.default_config()
    assert "douban_future_days" in config
    assert config["douban_future_days"] == C.DEFAULT_FUTURE_DAYS == 3


def test_douban_window_can_differ_from_tmdb():
    """按源窗口：豆瓣放宽到 14 天时，同一条目在 TMDB 窗口下仍被拦。"""
    far = (TODAY + timedelta(days=10)).isoformat()
    film = douban_item(release_date=far)

    # TMDB 窗口 3 天、豆瓣窗口 14 天 -> 通过
    passed, _ = select_items(
        [film],
        future_days=3,
        min_rating=0.0,
        future_days_by_source={C.SOURCE_TMDB: 3, C.SOURCE_DOUBAN_RSS: 14},
        now=TODAY,
    )
    assert len(passed) == 1

    # 两个源都用 3 天 -> 被拦
    passed2, rejected = select_items(
        [douban_item(release_date=far)],
        future_days=3,
        min_rating=0.0,
        future_days_by_source={C.SOURCE_TMDB: 3, C.SOURCE_DOUBAN_RSS: 3},
        now=TODAY,
    )
    assert not passed2
    assert rejected[0].decision == C.DECISION_SKIPPED_OUT_OF_WINDOW


# --------------------------------------------------------------------- 想看门槛

def test_min_want_filters_cold_titles():
    """想看人数低于门槛要拦下，并给出明确原因。"""
    passed, rejected = select_items(
        [douban_item(raw={"want": 52})],
        future_days=3,
        min_rating=0.0,
        min_want=1000,
        now=TODAY,
    )
    assert not passed
    assert rejected[0].decision == C.DECISION_SKIPPED_WANT
    assert "52" in rejected[0].reason


def test_min_want_passes_hot_titles():
    """想看人数足够则通过。"""
    passed, _ = select_items(
        [douban_item(raw={"want": 27357})],
        future_days=3,
        min_rating=0.0,
        min_want=1000,
        now=TODAY,
    )
    assert len(passed) == 1


def test_min_want_passes_when_missing():
    """**缺失想看数时放行**。

    榜单类路线（/douban/list/*）没有想看数；若按「缺失即拦」处理，
    用户配的十几个榜单会全部静默失效。
    """
    passed, _ = select_items(
        [douban_item(raw={"want": None})],
        future_days=3,
        min_rating=0.0,
        min_want=1000,
        now=TODAY,
    )
    assert len(passed) == 1


def test_min_want_zero_disables_filter():
    """门槛为 0 时不过滤（默认行为）。"""
    passed, _ = select_items(
        [douban_item(raw={"want": 1})],
        future_days=3,
        min_rating=0.0,
        min_want=0,
        now=TODAY,
    )
    assert len(passed) == 1


def test_min_want_only_applies_to_douban_raw():
    """没有 raw.want 的源不受影响（门槛不会误伤 TMDB/Bangumi）。"""
    tmdb_item = DiscoveredItem(
        source=C.SOURCE_TMDB,
        source_id="1",
        title="某片",
        media_type=C.MEDIA_TYPE_MOVIE,
        year=str(TODAY.year),
        release_date=(TODAY + timedelta(days=1)).isoformat(),
        resolved=ResolvedIdentity("themoviedb", "111"),
    )
    passed, _ = select_items(
        [tmdb_item], future_days=3, min_rating=0.0, min_want=1000, now=TODAY
    )
    assert len(passed) == 1


@pytest.mark.parametrize("want,expected_pass", [(999, False), (1000, True), (1001, True)])
def test_min_want_boundary(want, expected_pass):
    """边界：等于门槛算通过（`<` 才拦）。"""
    passed, _ = select_items(
        [douban_item(raw={"want": want})],
        future_days=3,
        min_rating=0.0,
        min_want=1000,
        now=TODAY,
    )
    assert bool(passed) is expected_pass
