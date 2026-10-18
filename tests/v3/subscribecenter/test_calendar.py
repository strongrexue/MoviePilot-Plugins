"""日历：只按 TMDB 每季的 air_date 铺开（与 MoviePilot 日历同口径）。

真机教训：用订阅表的 ``last_update`` 判断「那天入库了什么」会把整月撑爆 ——
那是「最后一次搜索时间」，批量跑一次几十上百条订阅会全被刷成同一天
（实测一天 200 条，MP 原生只有 38 条）。
"""
import asyncio
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugins.v3"))

from subscribecenter.core import calendar as cal  # noqa: E402

DAY = "2026-10-18"


def _row(**kwargs):
    base = dict(
        id=1, name="测试剧", season=1, poster="p.jpg", media_source="tmdb", media_id="100",
        total_episode=20, lack_episode=8, start_episode=1, state="R", best_version=0,
        last_update="", date="", episode_group="",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _index(media_id="100", season=1, pairs=((DAY, 5),)):
    return {(media_id, season): list(pairs)}


def test_only_air_date_hits():
    rows = [_row(id=1, name="今天播", media_id="100"), _row(id=2, name="别的日子", media_id="200")]
    index = _index() | {("200", 1): [("2026-10-20", 3)]}
    items = cal.build_today(rows, DAY, index)
    assert [item["name"] for item in items] == ["今天播"]
    assert items[0]["episodes"] == [5]


def test_last_update_is_ignored():
    """``last_update`` 是搜索时间，不能当成「那天入库」。"""
    rows = [_row(id=1, name="批量刷新过的", media_id="999", last_update=f"{DAY} 10:00:00")]
    assert cal.build_today(rows, DAY, {}) == []


def test_date_field_is_ignored():
    """``date`` 只是下一集播出，查不到历史。"""
    rows = [_row(id=1, name="下一集在这天", media_id="998", date=f"{DAY} 20:00:00")]
    assert cal.build_today(rows, DAY, {}) == []


def test_library_state_uses_episode_number():
    rows = [_row(id=1, name="连载", media_id="77", total_episode=20, lack_episode=15)]
    early = cal.build_today(rows, DAY, _index("77", 1, ((DAY, 3),)))[0]
    late = cal.build_today(rows, DAY, _index("77", 1, ((DAY, 12),)))[0]
    assert early["kind"] == cal.KIND_UPDATED
    assert late["kind"] == cal.KIND_PENDING


def test_no_downloaded_episode_is_pending():
    rows = [_row(id=1, name="全新", media_id="66", total_episode=12, lack_episode=12)]
    item = cal.build_today(rows, DAY, _index("66", 1, ((DAY, 1),)))[0]
    assert item["kind"] == cal.KIND_PENDING


def test_multiple_episodes_same_day():
    rows = [_row(id=1, name="连播", media_id="55", total_episode=20, lack_episode=2)]
    item = cal.build_today(rows, DAY, _index("55", 1, ((DAY, 2), (DAY, 3))))[0]
    assert item["episodes"] == [2, 3]
    assert item["kind"] == cal.KIND_UPDATED


def test_summarize_counts():
    items = [
        {"kind": cal.KIND_UPDATED, "best_version": True},
        {"kind": cal.KIND_UPDATED, "best_version": False},
        {"kind": cal.KIND_PENDING, "best_version": False},
    ]
    assert cal.summarize(items) == {"total": 3, "updated": 2, "pending": 1, "best_version": 1}


def test_sorted_updated_first_then_name():
    rows = [
        _row(id=3, name="B 待播", media_id="3", total_episode=10, lack_episode=10),
        _row(id=1, name="A 已入库", media_id="1", total_episode=10, lack_episode=2),
        _row(id=2, name="C 待播", media_id="2", total_episode=10, lack_episode=10),
    ]
    index = {("1", 1): [("2026-09-01", 1)], ("2", 1): [("2026-09-01", 1)], ("3", 1): [("2026-09-01", 1)]}
    items = cal.build_today(rows, "2026-09-01", index)
    assert [item["name"] for item in items] == ["A 已入库", "B 待播", "C 待播"]


def test_month_keeps_all_items_per_day():
    rows = [_row(id=i, name=f"剧{i}", media_id=str(100 + i)) for i in range(1, 26)]
    index = {(str(100 + i), 1): [("2026-10-19", 1)] for i in range(1, 26)}
    data = cal.build_month(rows, "2026-10", index)
    assert len(data["days"]["2026-10-19"]) == 25
    assert data["today"]


def test_month_empty_when_no_index():
    rows = [_row(id=1, name="X", media_id="1")]
    data = cal.build_month(rows, "2026-10", {})
    assert data["days"] == {}
    assert data["total"] == 0


def test_build_month_works_inside_event_loop():
    async def run():
        rows = [_row(id=1, name="X", media_id="1")]
        return cal.build_month(rows, "2026-10", _index("1", 1))

    data = asyncio.run(run())
    assert data["month"] == "2026-10"
