"""按源独立阈值 + Bangumi 续作换算的回归测试（0.6.1）。

三个真机暴露的缺陷：

1. **TV 续作的身份换算被年份校验误杀** —— TMDB 剧集年份是「第一季首播年」，
   Bangumi 续作条目的年份是「该季年」，两者必然不等。真机上
   《赛博朋克：边缘行者 2》(2026) 换算到 TMDB 剧集 (2022) 被拒，退化成待确认。
2. **阈值没有按源分开** —— Bangumi 条目被 TMDB 的 `min_rating_tmdb` 管着；
   `bangumi_future_days` 在界面上不可见，实际生效值靠默认。
3. **前端「已实现」列表过期** —— 启用 Bangumi 后仍显示「当前版本已启用也不会运行」。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.model import ResolvedIdentity  # noqa: E402
from subscribecenter.core.pipeline import select_items  # noqa: E402

TODAY = date.today()


def item(**overrides):
    """构造一条测试条目。"""
    from subscribecenter.core.model import DiscoveredItem

    data = {
        "source": C.SOURCE_TMDB,
        "source_id": "1",
        "title": "片",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": str(TODAY.year),
        "release_date": (TODAY + timedelta(days=1)).isoformat(),
        "rating": 8.0,
        "resolved": ResolvedIdentity("themoviedb", "111"),
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 按源评分

def test_rating_threshold_is_per_source():
    """Bangumi 用 ``min_rating_bangumi``，TMDB 用 ``min_rating_tmdb``。

    两边评分量纲不同（Bangumi 社区分普遍偏高），共用一个门槛会误杀。
    """
    bangumi = item(
        source=C.SOURCE_BANGUMI, source_id="9", rating=7.0,
        native_ids={"bangumi": "9"},
        resolved=ResolvedIdentity("themoviedb", "222", C.CONFIDENCE_L2),
    )
    tmdb = item(source=C.SOURCE_TMDB, source_id="1", rating=7.0)

    passed, rejected = select_items(
        [bangumi, tmdb],
        future_days=3,
        min_rating=6.0,
        min_rating_by_source={C.SOURCE_TMDB: 8.0, C.SOURCE_BANGUMI: 6.0},
        now=TODAY,
    )
    # TMDB 7.0 < 8.0 被拦；Bangumi 7.0 >= 6.0 通过
    assert [i.source for i in passed] == [C.SOURCE_BANGUMI]
    assert rejected[0].decision == C.DECISION_SKIPPED_RATING
    assert "tmdb" in rejected[0].reason


def test_rating_threshold_falls_back_to_default():
    """映射里没有该源时回落通用门槛。"""
    passed, rejected = select_items(
        [item(rating=7.0)],
        future_days=3,
        min_rating=6.0,
        min_rating_by_source={C.SOURCE_BANGUMI: 9.9},
        now=TODAY,
    )
    assert len(passed) == 1 and not rejected


# --------------------------------------------------------------------- 按源窗口

def test_window_is_per_source():
    """Bangumi 窗口可以比 TMDB 宽/窄，互不影响。"""
    day10 = (TODAY + timedelta(days=10)).isoformat()
    bangumi = item(
        source=C.SOURCE_BANGUMI, source_id="9", release_date=day10,
        native_ids={"bangumi": "9"},
        resolved=ResolvedIdentity("themoviedb", "222", C.CONFIDENCE_L2),
    )
    tmdb = item(source=C.SOURCE_TMDB, source_id="1", release_date=day10)

    passed, _rejected = select_items(
        [bangumi, tmdb],
        future_days=3,
        min_rating=0.0,
        future_days_by_source={C.SOURCE_TMDB: 3, C.SOURCE_BANGUMI: 14},
        now=TODAY,
    )
    # Bangumi 窗口 14 天 -> 通过；TMDB 窗口 3 天 -> 拦下
    assert [i.source for i in passed] == [C.SOURCE_BANGUMI]


def test_window_reason_reports_source_specific_days():
    """跳过原因要写明该源自己的窗口天数，便于排查。"""
    far = (TODAY + timedelta(days=10)).isoformat()
    _passed, rejected = select_items(
        [item(release_date=far)],
        future_days=3,
        min_rating=0.0,
        future_days_by_source={C.SOURCE_TMDB: 5},
        now=TODAY,
    )
    assert "5 天" in rejected[0].reason


# --------------------------------------------------------------------- 换算季号/年份

@pytest.mark.asyncio
async def test_tv_year_mismatch_is_accepted():
    """**剧集年份不匹配时必须接受** —— TMDB 剧集年份是首季年，续作年份必然不同。"""
    from subscribecenter.core.identity import IdentityResolver

    class _Tmdb:
        async def search(self, title, year, media_type, *, limit=5):
            return ()

        async def convert_to_tmdb(self, media_source, media_id, media_type):
            # 宿主把 2026 年的续作换算到 2022 年首播的 TMDB 剧集
            return {"tmdb_id": "105994", "year": "2022", "season": 2}

    from subscribecenter.core.model import DiscoveredItem

    found = DiscoveredItem(
        source=C.SOURCE_BANGUMI, source_id="513878", title="边缘行者 2",
        media_type=C.MEDIA_TYPE_TV, year="2026", release_date="2026-10-20",
        native_ids={"bangumi": "513878"},
    )
    resolved = await IdentityResolver(_Tmdb()).resolve(found)

    assert resolved.resolved is not None, "剧集续作被年份校验误杀了"
    assert resolved.resolved.media_id == "105994"
    assert resolved.resolved.confidence == C.CONFIDENCE_L2
    # 默认不按季拆分（season 保持 None -> 宿主按默认季订阅）
    assert resolved.season is None
    assert "season(2)" in resolved.resolved.reason


@pytest.mark.asyncio
async def test_movie_year_mismatch_still_rejected():
    """电影仍然要做年份硬校验（同名片不同年是最常见的误写来源）。"""
    from subscribecenter.core.identity import IdentityResolver
    from subscribecenter.core.model import DiscoveredItem

    class _Tmdb:
        async def search(self, title, year, media_type, *, limit=5):
            return ()

        async def convert_to_tmdb(self, media_source, media_id, media_type):
            return {"tmdb_id": "999", "year": "1999"}

    found = DiscoveredItem(
        source=C.SOURCE_DOUBAN_RSS, source_id="1", title="某片",
        media_type=C.MEDIA_TYPE_MOVIE, year="2026", release_date="2026-10-20",
        native_ids={"douban": "1"},
    )
    assert (await IdentityResolver(_Tmdb()).resolve(found)).resolved is None


# --------------------------------------------------------------------- 前端一致性

def test_bangumi_split_season_defaults_off():
    """按季拆分必须**默认关**。

    国产动画在 TMDB 通常是「单季多集」：《牧神记》= 第 1 季 110 集，
    第 105 集 = 2026-10-18 正好对应 Bangumi「牧神记5」开播日。
    传 season=5 会去找不存在的季，结果什么都订不到。
    """
    assert C.default_config()["bangumi_split_season"] is False


def test_anilist_controls_exposed_in_ui():
    """AniList 的窗口 / 热度 / 国漫开关必须有独立控件。

    真机教训：0.9.0 重做版面时把开关循环写成只渲染第一项，三个开关
    在界面上凭空消失。这里逐项锁定。
    """
    source = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Config.vue"
    )
    if not source.exists():
        pytest.skip("前端尚未构建")
    text = source.read_text(encoding="utf-8")
    for key in ("anilist_future_days", "anilist_min_popularity", "anilist_include_donghua"):
        assert key in text, f"界面上缺少 {key} 控件"


def test_frontend_implemented_list_matches_backend():
    """前端「已实现」列表必须与后端 `IMPLEMENTED_SOURCES` 同步。

    不同步的直接后果：启用某个源后界面仍显示「当前版本已启用也不会运行」，
    用户会以为它没生效（真机踩过）。
    """
    source = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Config.vue"
    )
    if not source.exists():
        pytest.skip("前端尚未构建")
    text = source.read_text(encoding="utf-8")
    for name in C.IMPLEMENTED_SOURCES:
        assert f"'{name}'" in text, f"前端 IMPLEMENTED 列表缺少 {name}"


def test_frontend_has_no_bangumi_source_switch():
    """Bangumi 已降级为标题翻译层，界面上不应再有它的数据源开关。"""
    source = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Config.vue"
    )
    if not source.exists():
        pytest.skip("前端尚未构建")
    text = source.read_text(encoding="utf-8")
    assert "enable_bangumi" not in text
