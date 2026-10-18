"""今日日历：只挑今天的条目，已入库优先，待播去重。"""
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugins.v3"))

from subscribecenter.core import calendar as cal  # noqa: E402

TODAY = "2026-10-02"


def _row(**kwargs):
    base = dict(
        id=1, name="测试剧", season=1, poster="p.jpg", media_source="tmdb", media_id="1",
        total_episode=12, lack_episode=4, start_episode=1, state="R", best_version=0,
        last_update="", date="",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_only_today_items_are_kept():
    rows = [
        _row(id=1, name="今天的", last_update=f"{TODAY} 20:00:00"),
        _row(id=2, name="昨天的", last_update="2026-10-01 20:00:00"),
        _row(id=3, name="明天待播", date="2026-10-03 20:00:00"),
    ]
    items = cal.build_today(rows, TODAY)
    assert [item["name"] for item in items] == ["今天的"]


def test_updated_wins_over_pending_for_same_row():
    rows = [_row(id=7, name="两边都命中", last_update=f"{TODAY} 10:00:00", date=f"{TODAY} 22:00:00")]
    items = cal.build_today(rows, TODAY)
    assert len(items) == 1
    assert items[0]["kind"] == cal.KIND_UPDATED


def test_pending_kind_and_air_time():
    rows = [_row(id=9, name="今晚播", date=f"{TODAY} 21:30:00", last_update="")]
    items = cal.build_today(rows, TODAY)
    assert items[0]["kind"] == cal.KIND_PENDING
    assert items[0]["air_time"] == "21:30"
    assert items[0]["air_date"] == TODAY


def test_empty_strings_do_not_match():
    rows = [_row(id=5, last_update="", date="")]
    assert cal.build_today(rows, TODAY) == []


def test_summarize_counts():
    items = [
        {"kind": cal.KIND_UPDATED, "best_version": True},
        {"kind": cal.KIND_UPDATED, "best_version": False},
        {"kind": cal.KIND_PENDING, "best_version": False},
    ]
    summary = cal.summarize(items)
    assert summary == {"total": 3, "updated": 2, "pending": 1, "best_version": 1}


def test_sorted_by_name_within_kind():
    rows = [
        _row(id=2, name="B 剧", last_update=f"{TODAY} 09:00:00"),
        _row(id=1, name="A 剧", last_update=f"{TODAY} 09:00:00"),
        _row(id=3, name="0 待播", date=f"{TODAY} 23:00:00"),
    ]
    items = cal.build_today(rows, TODAY)
    assert [item["name"] for item in items] == ["A 剧", "B 剧", "0 待播"]
