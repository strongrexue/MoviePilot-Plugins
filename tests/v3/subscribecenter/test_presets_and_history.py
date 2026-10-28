"""场景预设 + 流水按天保留 + 分 tab 清理（1.17.0）。

这组测试守的是三件在真机上很难复核的事：

1. 预设只改「追什么」，不能把用户的 RSSHub 域名 / cron 悄悄改掉；
2. 流水按天清理，而不是按固定 500 条截断（豆瓣全榜一天 300+ 条，
   固定条数会把一周前的记录挤掉）；
3. 分 tab 清理必须**同步**清掉对应的去重键 —— 否则出现「界面清了，
   但依然订不上」。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter import (  # noqa: E402
    HISTORY_KEEP_DAYS,
    _prune_history,
)
from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core import pipeline, writer  # noqa: E402
from subscribecenter.core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from subscribecenter.core.presets import (  # noqa: E402
    PRESETS,
    build_douban_lists,
    describe,
)
from subscribecenter.core.presets import (
    apply as apply_preset,
)

# --------------------------------------------------------------------- 预设

def test_presets_cover_three_scenarios():
    """三个场景都要在，且描述不为空（前端按钮直接吃这份）。"""
    items = describe()
    keys = [item["key"] for item in items]
    assert keys == list(PRESETS)
    assert set(keys) == {"anime", "domestic", "movie"}
    for item in items:
        assert item["title"] and item["desc"]


def test_preset_anime_turns_on_anilist_and_bilibili():
    """追番场景：AniList + B 站，TMDB/豆瓣全榜让路。"""
    config = dict(C.default_config())
    updated = apply_preset(config, "anime")
    assert updated["enable_anilist"] is True
    assert updated["anilist_include_donghua"] is True
    assert updated["enable_bilibili"] is True
    assert updated["enable_tmdb"] is False
    assert updated["enable_qq_video"] is False
    # 豆瓣只留动画榜，其余关掉（省掉白跑的 RSS + TMDB 请求）
    enabled = [e["url"] for e in updated["douban_rss_sources"] if e["enabled"]]
    assert enabled == ["/douban/list/tv_animation"]


def test_preset_movie_enables_release_fallback():
    """院线新片：豆瓣榜单不给日期，必须靠 TMDB 发行日兜底。"""
    updated = apply_preset(dict(C.default_config()), "movie")
    assert updated["movie_release_fallback"] is True
    assert updated["tmdb_future_days"] == 30
    assert updated["enable_qq_video"] is True
    assert updated["qq_video_channels"] == ["movie"]


def test_preset_keeps_environment_settings():
    """预设不得改掉用户配的环境项（RSSHub 域名 / cron / 通知）。"""
    config = dict(C.default_config())
    config.update(
        {
            "rsshub_domain": "http://192.168.50.134:1200",
            "cron": "0 4 * * *",
            "notify": False,
            "daily_limit": 99,
        }
    )
    updated = apply_preset(config, "domestic")
    assert updated["rsshub_domain"] == "http://192.168.50.134:1200"
    assert updated["cron"] == "0 4 * * *"
    assert updated["notify"] is False
    # 与场景强相关的项才会被覆盖
    assert updated["daily_limit"] == 30


def test_preset_reset_restores_defaults_but_keeps_domain():
    config = dict(C.default_config())
    config.update({"enable_qq_video": True, "rsshub_domain": "http://nas:1200"})
    reset = apply_preset(config, "reset")
    assert reset["enable_qq_video"] is C.default_config()["enable_qq_video"]
    assert reset["rsshub_domain"] == "http://nas:1200"


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        apply_preset(dict(C.default_config()), "nope")


def test_build_douban_lists_only_enables_requested():
    entries = build_douban_lists(["/douban/movie/coming"])
    enabled = [e["url"] for e in entries if e["enabled"]]
    assert enabled == ["/douban/movie/coming"]
    # 其余条目仍在列表里（前端要能手动勾回来），只是 enabled=False
    assert len(entries) > len(enabled)


def test_plugin_apply_preset_persists_only_changed_keys(plugin, monkeypatch):
    """套用预设只写「变了的键」—— 合并写入，不整份覆盖。"""
    saved = {}

    def _save_config(**kwargs):
        saved.update(kwargs)
        plugin.__dict__.setdefault("_config", {}).update(kwargs)

    monkeypatch.setattr(plugin, "save_config", _save_config)
    result = plugin.apply_preset(name="anime")
    assert result["success"] is True
    assert result["title"]
    assert result["changed"] == len(saved) >= 1
    # 只写变动项：环境项不该出现在 patch 里
    assert "rsshub_domain" not in saved
    assert saved["enable_bilibili"] is True


# --------------------------------------------------------------------- 流水按天保留

def _record(media_id: str, run_at: str, *, source="tmdb", decision=C.DECISION_ADDED,
            media_source="themoviedb", season=1):
    return {
        "decision": decision,
        "source": source,
        "title": f"剧{media_id}",
        "year": "2026",
        "media_source": media_source,
        "media_id": media_id,
        "season": season,
        "run_at": run_at,
    }


def test_prune_history_keeps_recent_and_undated(plugin):
    """按天清理：老记录删掉，新记录与「读不出日期」的一律保留。"""
    records = [
        _record("1", "2026-09-01 05:00:00"),  # 太老
        _record("2", "2026-10-28 05:00:00"),  # 今天
        {"decision": C.DECISION_ADDED, "title": "无日期"},  # 老数据
    ]
    kept = _prune_history(records, keep_days=30, today_text="2026-10-28")
    ids = [row.get("media_id") for row in kept]
    assert ids == ["2", None]


def test_prune_history_hard_limit(plugin):
    """即使不按天清理，也不能无限增长。"""
    records = [_record(str(i), "2026-10-28 05:00:00") for i in range(10)]
    kept = _prune_history(records, keep_days=0, hard_limit=4)
    assert [row["media_id"] for row in kept] == ["6", "7", "8", "9"]


def test_append_history_prunes_old_records(plugin):
    """落流水时就按天清理，而不是攒到 500 条再截断。"""
    old = "2020-01-01 05:00:00"
    plugin.save_data("run_history", [_record("99", old)])
    plugin._append_history([], run_at="2026-10-28 05:00:00")
    remaining = [row.get("media_id") for row in plugin._history()]
    assert "99" not in remaining
    assert HISTORY_KEEP_DAYS >= 1


# --------------------------------------------------------------------- 分 tab 清理

def test_clear_history_by_source_keeps_others(plugin):
    """按来源清：只删这个源的记录，其它源原样保留。"""
    plugin.save_data(
        "run_history",
        [
            _record("1", "2026-10-28 05:00:00", source="tmdb"),
            _record("2", "2026-10-28 05:00:00", source="anilist", media_source="anilist"),
        ],
    )
    result = plugin.clear_history(source="anilist")
    assert result.removed == 1
    assert result.remaining == 1
    assert [row["media_id"] for row in plugin._history()] == ["1"]


def test_clear_history_drops_matching_recorded_key(plugin):
    """清掉某条记录，必须同步清掉它的去重键，否则「清了还订不上」。"""
    plugin.save_data(
        "run_history",
        [
            _record("1", "2026-10-28 05:00:00", source="tmdb"),
            _record("2", "2026-10-28 05:00:00", source="anilist", media_source="anilist"),
        ],
    )
    plugin.save_data("recorded_keys", ["themoviedb:1:1", "anilist:2:1"])
    plugin.clear_history(source="tmdb")
    assert plugin.get_data("recorded_keys") == ["anilist:2:1"]


def test_clear_history_by_key_removes_single_record(plugin):
    plugin.save_data(
        "run_history",
        [
            _record("1", "2026-10-28 05:00:00"),
            _record("2", "2026-10-28 05:00:00"),
        ],
    )
    result = plugin.clear_history(key="themoviedb:2")
    assert result.removed == 1
    assert [row["media_id"] for row in plugin._history()] == ["1"]


def test_clear_history_by_decision(plugin):
    plugin.save_data(
        "run_history",
        [
            _record("1", "2026-10-28 05:00:00", decision=C.DECISION_PENDING_REVIEW),
            _record("2", "2026-10-28 05:00:00", decision=C.DECISION_ADDED),
        ],
    )
    result = plugin.clear_history(decision=C.DECISION_PENDING_REVIEW)
    assert result.removed == 1
    assert [row["media_id"] for row in plugin._history()] == ["2"]


def test_clear_history_older_than_days(plugin):
    plugin.save_data(
        "run_history",
        [
            _record("1", "2026-01-01 05:00:00"),
            _record("2", "2026-10-28 05:00:00"),
        ],
    )
    result = plugin.clear_history(older_than_days=30)
    assert result.removed == 1
    assert [row["media_id"] for row in plugin._history()] == ["2"]


def test_clear_history_empty_selection_is_noop(plugin):
    """筛选没命中时不能把整表清空（最危险的误操作）。"""
    plugin.save_data("run_history", [_record("1", "2026-10-28 05:00:00")])
    result = plugin.clear_history(source="nonexistent")
    assert result.removed == 0
    assert result.remaining == 1
    assert len(plugin._history()) == 1


# --------------------------------------------------------------------- 运行摘要

def test_summary_reports_source_breakdown_and_timings():
    """运行摘要要能回答「哪个源在出活」「慢在哪一步」。"""

    def item(source: str, title: str) -> DiscoveredItem:
        return DiscoveredItem(
            source=source,
            source_id="1",
            title=title,
            media_type=C.MEDIA_TYPE_TV,
            resolved=ResolvedIdentity(media_source="themoviedb", media_id=title),
        )

    summary = pipeline.RunSummary(started_at="2026-10-28 05:00:00", finished_at="2026-10-28 05:01:00")
    summary.sources = [
        pipeline.SourceResult(source=C.SOURCE_DOUBAN_RSS, items=[item("douban_rss", "1"), item("douban_rss", "2")]),
        pipeline.SourceResult(source=C.SOURCE_QQ_VIDEO, items=[item("qq_video", "3")], error="HTTP 503"),
    ]
    summary.report = writer.WriteReport(
        outcomes=[
            writer.WriteOutcome(item=item("douban_rss", "1"), decision=C.DECISION_ADDED, success=True),
            writer.WriteOutcome(item=item("douban_rss", "2"), decision=C.DECISION_SKIPPED_RATING),
            writer.WriteOutcome(item=item("qq_video", "3"), decision=C.DECISION_PENDING_REVIEW),
        ]
    )
    summary.timings = {"fetch": 1.5, "resolve": 20.0, "filter": 0.2, "write": 1.1, "total": 22.8}
    data = summary.to_summary()
    rows = {row["source"]: row for row in data["source_breakdown"]}
    assert rows[C.SOURCE_DOUBAN_RSS]["fetched"] == 2
    assert rows[C.SOURCE_DOUBAN_RSS]["added"] == 1
    assert rows[C.SOURCE_DOUBAN_RSS]["skipped"] == 1
    assert rows[C.SOURCE_QQ_VIDEO]["pending"] == 1
    assert data["source_errors"] == {C.SOURCE_QQ_VIDEO: "HTTP 503"}
    assert data["timings"]["resolve"] == 20.0
