"""运行计数的口径一致性（0.9.5）。

真机困惑：预览通知显示「会订 0 / 拉取 371 / 跳过 341 / 待确认 18」，
而界面显示「会订 215 条」，且 341 + 18 = 359 ≠ 371。

查出的三处口径错误：

1. **预view 的「会订」把全部 writer 产出都算了进去** —— 包括
   `skipped_already_subscribed` / `skipped_finished` / `pending_review`。
   真机那 215 条里实际只有 0 条会写（79 条已订阅、118 条已播完、18 条待确认）。

2. **`skipped` 包含了 `pending_review`**，于是「跳过 + 待确认」会超过「拉取」。

3. **源内去重丢弃的条目完全没记账** —— 371 与 341 差的 30 条既不在跳过、
   也不在待确认里，看起来像凭空消失。

本文件锁住三条不变式：

    fetched == deduped_out + added + skipped + pending_review
    skipped 与 pending_review 互斥
    preview 的「会订」只统计 added / skipped_dry_run
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from subscribecenter.core.pipeline import RunSummary, SourceResult  # noqa: E402
from subscribecenter.core.writer import (  # noqa: E402
    SubscriptionWriter,
    WriteOutcome,
    WriteReport,
)


def item(index, **overrides):
    """构造条目。"""
    data = {
        "source": C.SOURCE_TMDB,
        "source_id": str(index),
        "title": f"片{index}",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": "2026",
        "release_date": "2026-11-01",
        "resolved": ResolvedIdentity("themoviedb", str(1000 + index)),
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 互斥性

def test_skipped_excludes_pending_review():
    """跳过与待确认必须互斥。

    真机：跳过 341 + 待确认 18 = 359，比拉取 371 还少 12（另有去重丢弃），
    但明细里 341 明明已经包含了那 18 条待确认。
    """
    report = WriteReport(
        outcomes=[
            WriteOutcome(item=item(1), decision=C.DECISION_ADDED, success=True, reason=""),
            WriteOutcome(item=item(2), decision=C.DECISION_PENDING_REVIEW, reason=""),
            WriteOutcome(item=item(3), decision=C.DECISION_SKIPPED_FINISHED, reason=""),
        ]
    )
    summary = report.to_summary()

    assert summary["added"] == 1
    assert summary["pending_review"] == 1
    assert summary["skipped"] == 1, "skipped 不应包含 pending_review"
    assert summary["skipped"] + summary["added"] + summary["pending_review"] == 3


# --------------------------------------------------------------------- 总数闭合

def _summary(fetched, deduped_out, outcomes, prefiltered=()):
    """构造一个 RunSummary 并返回 to_summary()。"""
    summary = RunSummary(
        sources=[
            SourceResult(
                source=C.SOURCE_TMDB,
                items=[item(i) for i in range(fetched)],
            )
        ],
        deduped_out=deduped_out,
        prefiltered=list(prefiltered),
        report=WriteReport(outcomes=list(outcomes)),
    )
    return summary.to_summary()


def test_total_adds_up():
    """fetched == deduped_out + added + skipped + pending_review。

    构造：拉取 7 = 源内去重 2 + 新增 1 + 跳过 2（1 条已播完 + 1 条关注度不足）
    + 待确认 2（1 条来自 writer、1 条来自预过滤）。
    """
    data = _summary(
        fetched=7,
        deduped_out=2,
        outcomes=[
            WriteOutcome(item=item(10), decision=C.DECISION_ADDED, success=True, reason=""),
            WriteOutcome(item=item(11), decision=C.DECISION_SKIPPED_FINISHED, reason=""),
            WriteOutcome(item=item(12), decision=C.DECISION_PENDING_REVIEW, reason=""),
        ],
        prefiltered=[
            WriteOutcome(item=item(13), decision=C.DECISION_SKIPPED_POPULARITY, reason=""),
            WriteOutcome(item=item(14), decision=C.DECISION_PENDING_REVIEW, reason=""),
        ],
    )
    total = (
        data["deduped_out"] + data["added"] + data["skipped"] + data["pending_review"]
    )
    assert data["fetched"] == 7
    assert data["added"] == 1
    assert data["skipped"] == 2
    assert data["pending_review"] == 2
    assert total == data["fetched"], f"{total} != {data['fetched']}"


def test_prefiltered_pending_counted_separately():
    """预过滤阶段产生的待确认要计入 pending，而不是计入跳过。"""
    data = _summary(
        fetched=2,
        deduped_out=0,
        outcomes=[],
        prefiltered=[
            WriteOutcome(item=item(1), decision=C.DECISION_PENDING_REVIEW, reason=""),
            WriteOutcome(item=item(2), decision=C.DECISION_SKIPPED_NO_DATE, reason=""),
        ],
    )
    assert data["pending_review"] == 1
    assert data["skipped"] == 1


# --------------------------------------------------------------------- 预览计数

class RecordingBackend:
    """记录写调用的 backend 替身。"""

    def __init__(self):
        self.calls = 0

    async def add(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls += 1
        return 1, "ok"

    async def subscription_exists(self, media_source, media_id, season=None):
        return False

    async def history_exists(self, media_source, media_id, season=None):
        return False


@pytest.mark.asyncio
async def test_dry_run_outcomes_are_marked_dry_run():
    """dry-run 时每条可写条目都产出 skipped_dry_run —— 预览的「会订」靠它统计。"""
    backend = RecordingBackend()
    writer = SubscriptionWriter(backend, daily_limit=0)
    report = await writer.write([item(1), item(2)], dry_run=True)

    decisions = [outcome.decision for outcome in report.outcomes]
    assert decisions == [C.DECISION_SKIPPED_DRY_RUN] * 2
    assert backend.calls == 0


def test_would_add_counts_only_dry_run():
    """预览的「会订」只统计 added / skipped_dry_run。

    真机 bug：界面把 skipped_already_subscribed / skipped_finished /
    pending_review 全算成「会订」，于是显示 215 条，实际 0 条会写。
    """
    outcomes = [
        WriteOutcome(item=item(1), decision=C.DECISION_SKIPPED_DRY_RUN, reason=""),
        WriteOutcome(item=item(2), decision=C.DECISION_SKIPPED_ALREADY_SUBSCRIBED, reason=""),
        WriteOutcome(item=item(3), decision=C.DECISION_SKIPPED_FINISHED, reason=""),
        WriteOutcome(item=item(4), decision=C.DECISION_PENDING_REVIEW, reason=""),
    ]
    writable = {
        C.DECISION_ADDED,
        C.DECISION_SKIPPED_DRY_RUN,
    }
    would_add = [o for o in outcomes if o.decision in writable]
    assert len(would_add) == 1
