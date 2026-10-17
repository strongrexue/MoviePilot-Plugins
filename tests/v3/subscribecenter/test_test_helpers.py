"""测试辅助开关与新增明细的回归测试（0.2.4）。"""
import sys
from pathlib import Path

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core import constants as C  # noqa: E402
from core.window import today as core_today  # noqa: E402


def test_reset_switch_is_declared_in_both_sides():
    """测试开关必须同时存在于后端默认配置与前端快照（整份覆盖语义）。"""
    assert "reset_daily_counter" in C.default_config()
    assert C.default_config()["reset_daily_counter"] is False

    frontend = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "configDefaults.js"
    )
    if frontend.exists():
        assert "reset_daily_counter" in frontend.read_text(encoding="utf-8")


def test_one_shot_flags_declared():
    """一次性开关集合里必须包含清零开关（保证读取后复位）。"""
    assert "reset_daily_counter" in C.ONE_SHOT_FLAGS


def test_reset_switch_clears_counter_and_self_disables(plugin_cls):
    """勾选清零开关后：今日计数归零，且开关自动复位为 False。

    自动复位是关键 —— 否则每日写入上限会永久失效。
    """
    instance = plugin_cls()
    instance.init_plugin({"enabled": True})
    # 伪造「今日已写 30 条」
    instance._save_state({C.STATE_TODAY: core_today(instance._tz()).isoformat(), C.STATE_DAILY_COUNT: 30})
    assert instance._written_today() == 30

    # 模拟用户勾选开关并保存
    instance.init_plugin({"enabled": True, "reset_daily_counter": True})

    assert instance._written_today() == 0, "计数未清零"
    assert instance.config["reset_daily_counter"] is False, "开关没有自动复位"


def test_reset_switch_absent_keeps_counter(plugin_cls):
    """不勾选时计数不受影响。"""
    instance = plugin_cls()
    instance.init_plugin({"enabled": True})
    instance._save_state({C.STATE_TODAY: core_today(instance._tz()).isoformat(), C.STATE_DAILY_COUNT: 7})
    instance.init_plugin({"enabled": True})
    assert instance._written_today() == 7


def test_added_titles_lists_actually_written_items():
    """摘要要能列出本次新增的标题 —— 只看数字判断不了订得对不对。"""
    from core.model import DiscoveredItem, ResolvedIdentity
    from core.pipeline import RunSummary
    from core.writer import WriteOutcome, WriteReport

    summary = RunSummary()
    items = [
        DiscoveredItem(
            source="tmdb", source_id=str(i), title=f"片子{i}", year="2026",
            resolved=ResolvedIdentity("themoviedb", str(i + 1)),
        )
        for i in range(3)
    ]
    summary.report = WriteReport(
        outcomes=[
            WriteOutcome(item=item, decision=C.DECISION_ADDED, success=True)
            for item in items
        ]
    )

    titles = _added_titles(summary)
    assert len(titles) == 3
    assert titles[0] == "片子0 (2026)"


def test_added_titles_truncates_with_notice():
    """新增过多时截断并说明剩余数量。"""
    from core.model import DiscoveredItem, ResolvedIdentity
    from core.pipeline import RunSummary
    from core.writer import WriteOutcome, WriteReport

    summary = RunSummary()
    summary.report = WriteReport(
        outcomes=[
            WriteOutcome(
                item=DiscoveredItem(
                    source="tmdb", source_id=str(i), title=f"片{i}",
                    resolved=ResolvedIdentity("themoviedb", str(i + 1)),
                ),
                decision=C.DECISION_ADDED,
                success=True,
            )
            for i in range(30)
        ]
    )
    titles = _added_titles(summary, limit=20)
    assert len(titles) == 21
    assert titles[-1].startswith("…另有 10 条")


def test_added_titles_empty_when_nothing_added():
    """没有新增时返回空列表。"""
    from core.pipeline import RunSummary
    from core.writer import WriteReport

    summary = RunSummary()
    summary.report = WriteReport()
    assert _added_titles(summary) == []


# --------------------------------------------------------------------- 辅助

def _added_titles(summary, limit=20):
    """调用插件主类的纯静态方法。"""
    import app.plugins.subscribecenter as mod

    return mod.SubscribeCenter._added_titles(summary, limit)
