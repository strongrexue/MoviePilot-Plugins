"""去重、过滤与额度逻辑的回归测试（开发文档 §7.1 / §9）。"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core import constants as C  # noqa: E402
from core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from core.pipeline import (  # noqa: E402
    dedupe_cross_source,
    dedupe_within_source,
    filter_by_popularity,
    filter_by_rating,
    filter_by_window,
    select_items,
)

TODAY = date.today()


def resolved(media_id="111", confidence=C.CONFIDENCE_L1):
    """构造一个确定性身份。"""
    return ResolvedIdentity(
        media_source="themoviedb", media_id=media_id, confidence=confidence
    )


def item(**overrides):
    """构造一条测试条目。

    默认标题按 ``source_id`` 生成唯一值 —— 源内去重现在会按
    「标题 + 年份 + 类型」兜底合并（豆瓣不同路线结构不同，同一部剧拿到的
    source_id 会不一样），同名条目会被正确合并成一条。
    """
    data = {
        "source": C.SOURCE_TMDB,
        "source_id": "1",
        "title": f"片{overrides.get('source_id', '1')}",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": "2026",
        "release_date": (TODAY + timedelta(days=5)).isoformat(),
        "rating": 8.0,
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 源内去重

def test_dedupe_within_source_keeps_first_occurrence():
    """同 ``source+source_id`` 只保留先出现的。"""
    a = item(source_id="x", title="第一条")
    b = item(source_id="x", title="第二条")
    c = item(source_id="y", title="第三条")
    result = dedupe_within_source([a, b, c])
    assert [i.title for i in result] == ["第一条", "第三条"]


def test_dedupe_within_source_is_per_source():
    """不同源的同名 ID 不算重复。"""
    a = item(source=C.SOURCE_TMDB, source_id="x")
    b = item(source=C.SOURCE_BANGUMI, source_id="x")
    assert len(dedupe_within_source([a, b])) == 2


# --------------------------------------------------------------------- 跨源去重

def test_dedupe_cross_source_merges_same_identity():
    """同一 TMDB 身份来自不同源 → 只保留一条。"""
    tmdb_item = item(source=C.SOURCE_TMDB, source_id="1", resolved=resolved("111"))
    bangumi_item = item(source=C.SOURCE_BANGUMI, source_id="9", resolved=resolved("111"))
    kept, dropped = dedupe_cross_source([tmdb_item, bangumi_item])
    assert len(kept) == 1
    assert len(dropped) == 1


def test_dedupe_cross_source_prefers_earlier_release_then_higher_rating():
    """同身份多条：保留定档更早的；日期相同则保留评分更高的。"""
    late = item(source_id="1", resolved=resolved("111"),
                release_date=(TODAY + timedelta(days=20)).isoformat())
    early = item(source_id="2", resolved=resolved("111"),
                 release_date=(TODAY + timedelta(days=3)).isoformat())
    kept, _ = dedupe_cross_source([late, early])
    assert kept[0].release_date == early.release_date

    low = item(source_id="3", resolved=resolved("222"), rating=6.1,
               release_date=(TODAY + timedelta(days=4)).isoformat())
    high = item(source_id="4", resolved=resolved("222"), rating=9.1,
                release_date=(TODAY + timedelta(days=4)).isoformat())
    kept2, _ = dedupe_cross_source([low, high])
    assert kept2[0].rating == 9.1


def test_dedupe_cross_source_does_not_merge_unresolved():
    """无确定性身份的条目不参与合并（否则会丢失排查线索）。"""
    a = item(source_id="1", title="甲", resolved=None)
    b = item(source_id="2", title="乙", resolved=None)
    kept, dropped = dedupe_cross_source([a, b])
    assert len(kept) == 2 and not dropped


def test_dedupe_cross_source_keeps_distinct_identities():
    """不同身份不合并。"""
    a = item(source_id="1", resolved=resolved("111"))
    b = item(source_id="2", resolved=resolved("222"))
    kept, dropped = dedupe_cross_source([a, b])
    assert len(kept) == 2 and not dropped


# --------------------------------------------------------------------- 评分过滤

@pytest.mark.parametrize(
    "rating,threshold,expected",
    [
        (8.0, 6.0, True),
        (6.0, 6.0, True),      # 边界含等号
        (5.9, 6.0, False),
        (None, 6.0, True),     # 无评分不拦截（由窗口与身份把关）
    ],
)
def test_filter_by_rating(rating, threshold, expected):
    """评分过滤：只有明确低于阈值才拦截。"""
    assert filter_by_rating(item(rating=rating), threshold) is expected


def test_filter_by_rating_tolerates_bad_values():
    """评分字段异常时不拦截（不因脏数据丢条目）。"""
    assert filter_by_rating(item(rating="bad"), 6.0) is True


# --------------------------------------------------------------------- 关注度过滤

def test_filter_by_popularity_rejects_cold_titles():
    """关注度过低拦截 —— 新片没评分时 popularity 是唯一可用的质量信号。

    0.2.2 真实事故：写入的 29 条全是 Black Ink / Ghost Lake 这类 popularity<5
    的同日上映冷门片，把每日 30 条额度吃光。
    """
    assert filter_by_popularity(item(popularity=3.0), 10.0) is False
    assert filter_by_popularity(item(popularity=15.0), 10.0) is True
    assert filter_by_popularity(item(popularity=10.0), 10.0) is True


def test_filter_by_popularity_passes_missing_value():
    """popularity 缺失时放行（不同源字段可用性不同，不能因此丢条目）。"""
    assert filter_by_popularity(item(popularity=None), 10.0) is True


def test_select_items_applies_popularity_floor():
    """``min_popularity > 0`` 时低关注度条目被拦下并给出原因。"""
    hot = item(source_id="hot", resolved=resolved("1"), popularity=88.0)
    cold = item(source_id="cold", resolved=resolved("2"), popularity=2.0)
    passed, rejected = select_items(
        [hot, cold], future_days=30, min_rating=6.0, min_popularity=10.0, now=TODAY
    )
    assert [i.source_id for i in passed] == ["hot"]
    assert rejected[0].decision == C.DECISION_SKIPPED_POPULARITY
    assert "关注度" in rejected[0].reason


def test_select_items_popularity_zero_disables_filter():
    """``min_popularity=0`` 表示不过滤。"""
    cold = item(source_id="cold", resolved=resolved("2"), popularity=0.5)
    passed, _ = select_items(
        [cold], future_days=30, min_rating=6.0, min_popularity=0.0, now=TODAY
    )
    assert len(passed) == 1


def test_select_items_orders_by_popularity_desc():
    """候选写入顺序按关注度降序 —— 额度先花在受关注的作品上。

    原来按日期升序写，等于把每日额度先给「今天上映的冷门片」。
    """
    low = item(source_id="low", resolved=resolved("1"), popularity=5.0,
               release_date=(TODAY + timedelta(days=1)).isoformat())
    high = item(source_id="high", resolved=resolved("2"), popularity=90.0,
                release_date=(TODAY + timedelta(days=20)).isoformat())
    mid = item(source_id="mid", resolved=resolved("3"), popularity=30.0,
               release_date=(TODAY + timedelta(days=10)).isoformat())
    passed, _ = select_items([low, high, mid], future_days=30, min_rating=6.0, now=TODAY)
    assert [i.source_id for i in passed] == ["high", "mid", "low"]


# --------------------------------------------------------------------- 窗口过滤

def test_filter_by_window_accepts_inside_window():
    """窗口内接受。"""
    assert filter_by_window(item(release_date=(TODAY + timedelta(days=1)).isoformat()),
                            30, now=TODAY)


def test_filter_by_window_rejects_missing_date():
    """无定档日期一律拦截 —— 无法判断「即将开播」。"""
    assert not filter_by_window(item(release_date=None), 30, now=TODAY)
    assert not filter_by_window(item(release_date=""), 30, now=TODAY)


def test_filter_by_window_rejects_past_and_too_far():
    """过去与超窗都拦截。"""
    assert not filter_by_window(item(release_date=(TODAY - timedelta(days=1)).isoformat()),
                                30, now=TODAY)
    assert not filter_by_window(item(release_date=(TODAY + timedelta(days=31)).isoformat()),
                                30, now=TODAY)


# --------------------------------------------------------------------- 组合选择

def test_select_items_reports_reasons_per_item():
    """被拦下的条目必须带可读原因，便于流水线落日志。"""
    good = item(source_id="g", resolved=resolved("1"),
                release_date=(TODAY + timedelta(days=2)).isoformat(), rating=8.0)
    low = item(source_id="l", resolved=resolved("2"),
               release_date=(TODAY + timedelta(days=2)).isoformat(), rating=3.0)
    out = item(source_id="o", resolved=resolved("3"),
               release_date=(TODAY + timedelta(days=90)).isoformat(), rating=8.0)
    nodate = item(source_id="n", resolved=resolved("4"), release_date=None, rating=8.0)

    passed, rejected = select_items(
        [good, low, out, nodate], future_days=30, min_rating=6.0, now=TODAY
    )
    assert [i.source_id for i in passed] == ["g"]
    decisions = {o.item.source_id: o.decision for o in rejected}
    assert decisions["l"] == C.DECISION_SKIPPED_RATING
    assert decisions["o"] == C.DECISION_SKIPPED_OUT_OF_WINDOW
    # 无日期进待确认，而不是静默丢弃
    assert decisions["n"] == C.DECISION_PENDING_REVIEW
    assert all(o.reason for o in rejected)


def test_select_items_marks_cross_source_duplicate():
    """跨源重复的条目被标记为 duplicate 并说明保留对象。"""
    a = item(source=C.SOURCE_TMDB, source_id="1", resolved=resolved("111"))
    b = item(source=C.SOURCE_BANGUMI, source_id="2", resolved=resolved("111"))
    passed, rejected = select_items([a, b], future_days=30, min_rating=6.0, now=TODAY)
    assert len(passed) == 1
    duplicates = [o for o in rejected if o.decision == C.DECISION_SKIPPED_DUPLICATE]
    assert len(duplicates) == 1
    assert "111" in duplicates[0].reason


def test_select_items_is_order_stable():
    """同一批输入多次选择结果一致（便于测试与人工核对）。"""
    items = [
        item(source_id="b", resolved=resolved("2"),
             release_date=(TODAY + timedelta(days=9)).isoformat()),
        item(source_id="a", resolved=resolved("1"),
             release_date=(TODAY + timedelta(days=2)).isoformat()),
    ]
    first, _ = select_items(items, future_days=30, min_rating=6.0, now=TODAY)
    second, _ = select_items(list(reversed(items)), future_days=30, min_rating=6.0, now=TODAY)
    assert [i.source_id for i in first] == [i.source_id for i in second] == ["a", "b"]


def test_select_items_empty_input():
    """空输入不报错。"""
    passed, rejected = select_items([], future_days=30, min_rating=6.0, now=TODAY)
    assert passed == [] and rejected == []


# --------------------------------------------------------- 无日期（榜单类来源）

def test_date_unknown_tv_passes_window():
    """无定档日期的**剧集**放行窗口过滤。

    榜单类 RSS（/douban/list/*、/douban/tv/coming）实测全部没有日期；
    正在连载的剧本来就没有「上映日」。是否值得订由「TMDB 还有没有未播集」
    判定（在 IdentityResolver 里完成），比时间窗口更准。
    """
    show = item(
        media_type=C.MEDIA_TYPE_TV,
        release_date=None,
        date_unknown=True,
        resolved=ResolvedIdentity("themoviedb", "555"),
    )
    passed, rejected = select_items([show], future_days=3, min_rating=0.0, now=TODAY)
    assert [i.source_id for i in passed] == [show.source_id]
    assert not rejected


def test_date_unknown_movie_is_skipped():
    """无定档日期的**电影**跳过 —— 无从判断是否即将上映。

    榜单里的电影往往是老片（重映/口碑榜），订了就是浪费每日额度。
    「TMDB 发行日兜底」也查不到日期时，仍然走这条路（见
    ``test_fill_movie_release_dates_*``）。
    """
    film = item(
        media_type=C.MEDIA_TYPE_MOVIE,
        release_date=None,
        date_unknown=True,
        resolved=ResolvedIdentity("themoviedb", "666"),
    )
    passed, rejected = select_items([film], future_days=3, min_rating=0.0, now=TODAY)
    assert not passed
    assert rejected[0].decision == C.DECISION_SKIPPED_NO_DATE
    assert "电影" in rejected[0].reason


# --------------------------------------------------- 电影发行日兜底（1.14.8）

def test_grace_window_lets_recent_movie_through():
    """电影发行日刚过去几天：宽限期内放行，0 宽限则拒绝。

    真机事故：《空枪》数字发行 2026-10-23，当天被「日期已过去」拒掉，
    可那时候站点上才刚刚有资源 —— 卡死「必须在未来」等于永远订不到。
    """
    recent = item(release_date=(TODAY - timedelta(days=2)).isoformat())
    assert filter_by_window(recent, 3, now=TODAY) is False
    assert filter_by_window(recent, 3, now=TODAY, past_days=7) is True

    # 老片不会被宽限期捞进来
    old = item(release_date=(TODAY - timedelta(days=30)).isoformat())
    assert filter_by_window(old, 3, now=TODAY, past_days=7) is False


def test_grace_window_is_movie_only():
    """宽限期只给电影：剧集「已过去」就是过去，交给未播集判定兜底。"""
    show = item(
        media_type=C.MEDIA_TYPE_TV,
        release_date=(TODAY - timedelta(days=2)).isoformat(),
    )
    assert filter_by_window(show, 3, now=TODAY, past_days=7) is False


def test_fill_movie_release_dates_only_undated_movies():
    """只给「来源没给日期」的电影补日期，剧集与已有日期的一律不碰。"""
    import asyncio

    from core.pipeline import fill_movie_release_dates

    undated = item(
        release_date=None,
        date_unknown=True,
        resolved=ResolvedIdentity("themoviedb", "777"),
    )
    dated = item(source_id="2")
    show = item(
        source_id="3",
        media_type=C.MEDIA_TYPE_TV,
        release_date=None,
        date_unknown=True,
    )

    asked = []

    async def lookup(media_source, media_id):
        asked.append((media_source, media_id))
        return ("2026-10-23", "数字发行")

    filled = asyncio.run(fill_movie_release_dates([undated, dated, show], lookup))

    assert filled == 1
    assert asked == [("themoviedb", "777")]
    assert undated.release_date == "2026-10-23"
    assert undated.release_date_source == "TMDB 数字发行"
    assert undated.date_unknown is False
    assert show.date_unknown is True  # 剧集不补
    assert dated.release_date == (TODAY + timedelta(days=5)).isoformat()


def test_fill_movie_release_dates_is_fail_closed():
    """查不到 / 抛异常 / 开关关闭时，条目保持「无日期」，绝不放行。"""
    import asyncio

    from core.pipeline import fill_movie_release_dates

    async def boom(*args):
        raise RuntimeError("tmdb down")

    async def nothing(*args):
        return None

    for lookup, enabled in ((boom, True), (nothing, True), (boom, False)):
        film = item(release_date=None, date_unknown=True)
        filled = asyncio.run(
            fill_movie_release_dates([film], lookup, enabled=enabled)
        )
        assert filled == 0
        assert film.release_date is None
        assert film.date_unknown is True

    # lookup 为 None（兜底关闭）时一条都不查
    film = item(release_date=None, date_unknown=True)
    assert asyncio.run(fill_movie_release_dates([film], None)) == 0


def test_filled_movie_then_passes_window_with_grace():
    """补出日期之后，走的是「发行日 + 宽限期」的窗口判定，而不是直接放行。"""
    film = item(release_date=None, date_unknown=True)
    film.release_date = (TODAY - timedelta(days=2)).isoformat()
    film.release_date_source = "TMDB 数字发行"
    film.date_unknown = False

    without, rejected = select_items(
        [film], future_days=3, min_rating=0.0, now=TODAY, movie_grace_days=0
    )
    assert not without
    assert rejected[0].decision == C.DECISION_SKIPPED_NOT_FUTURE
    assert "TMDB 数字发行" in rejected[0].reason

    passed, _ = select_items(
        [film], future_days=3, min_rating=0.0, now=TODAY, movie_grace_days=7
    )
    assert [i.source_id for i in passed] == [film.source_id]
