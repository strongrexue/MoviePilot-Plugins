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
    """构造一条测试条目。"""
    data = {
        "source": C.SOURCE_TMDB,
        "source_id": "1",
        "title": "沙丘",
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
