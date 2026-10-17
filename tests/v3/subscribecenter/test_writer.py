"""订阅写入的回归测试（开发文档 §7.3 / §7.6）。

覆盖三条最容易踩的宿主契约：

1. ``add()`` 幂等 —— 靠 ``message`` 区分「新增」与「已存在」；
2. **必须查 ``SubscribeHistory``** —— 宿主 ``async_add()`` 不做这个检查；
3. 每日上限、dry-run、身份不可写三种情况都不得写入。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core import constants as C  # noqa: E402
from core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from core.writer import (  # noqa: E402
    MESSAGE_ADDED,
    MESSAGE_EXISTS,
    SubscriptionWriter,
)

#: 相对**真实今天**计算，避免测试与系统日期耦合（写死日期会随运行日漂移而失效）
TODAY = date.today()


class FakeBackend:
    """可编程的宿主订阅替身。"""

    def __init__(self, *, exists=False, history=False, add_result=None, raise_precheck=False,
                 raise_add=False):
        self._exists = exists
        self._history = history
        self._add_result = add_result
        self._raise_precheck = raise_precheck
        self._raise_add = raise_add
        self.add_calls = []
        self.precheck_calls = 0

    async def add(self, title, year, media_source, media_id, media_type,
                  season=None, *, episode_group=None, message=False, exist_ok=False):
        """记录调用并返回预设结果。"""
        self.add_calls.append(
            {
                "title": title,
                "year": year,
                "media_source": media_source,
                "media_id": media_id,
                "media_type": media_type,
                "season": season,
                "episode_group": episode_group,
                "message": message,
                "exist_ok": exist_ok,
            }
        )
        if self._raise_add:
            raise RuntimeError("宿主抛错")
        if self._add_result is not None:
            return self._add_result
        return 42, MESSAGE_ADDED

    async def subscription_exists(self, media_source, media_id, season=None):
        """活跃订阅查询。"""
        self.precheck_calls += 1
        if self._raise_precheck:
            raise RuntimeError("查询失败")
        return self._exists

    async def history_exists(self, media_source, media_id, season=None):
        """订阅历史查询。"""
        if self._raise_precheck:
            raise RuntimeError("查询失败")
        return self._history


def item(**overrides):
    """构造一条带确定性身份的测试条目。"""
    data = {
        "source": C.SOURCE_TMDB,
        "source_id": "1",
        "title": "沙丘",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": "2026",
        "release_date": (TODAY + timedelta(days=5)).isoformat(),
        "rating": 8.0,
        "resolved": ResolvedIdentity("themoviedb", "693134", C.CONFIDENCE_L1, "native:tmdb"),
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 正常写入

@pytest.mark.asyncio
async def test_writes_with_paired_identity_fields():
    """写入必须用 ``media_source`` + ``media_id`` 成对字段，``year`` 是字符串。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 1
    assert len(backend.add_calls) == 1
    call = backend.add_calls[0]
    assert call["media_source"] == "themoviedb"
    assert call["media_id"] == "693134"
    assert call["year"] == "2026"
    assert isinstance(call["year"], str)
    assert call["title"] == "沙丘"
    # 逐条静默：汇总通知由插件在末尾发
    assert call["message"] is False
    assert call["exist_ok"] is False


@pytest.mark.asyncio
async def test_idempotent_hit_is_not_counted_as_added():
    """``message == 订阅已存在`` 时幂等命中，**不算新增**。"""
    backend = FakeBackend(add_result=(99, MESSAGE_EXISTS))
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 0
    outcome = report.outcomes[0]
    assert outcome.decision == C.DECISION_SKIPPED_ALREADY_SUBSCRIBED
    assert outcome.subscribe_id == 99


@pytest.mark.asyncio
async def test_zero_subscribe_id_is_not_a_success():
    """宿主返回 ``sid=0/None`` 表示未写入成功。"""
    backend = FakeBackend(add_result=(0, "新增订阅失败"))
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)
    assert report.added_count == 0
    assert report.outcomes[0].decision == C.DECISION_PENDING_REVIEW


# --------------------------------------------------------------------- 写入前复查

@pytest.mark.asyncio
async def test_skips_when_active_subscription_exists():
    """宿主已有活跃订阅 → 跳过，且**不调用 add()**。"""
    backend = FakeBackend(exists=True)
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_ALREADY_SUBSCRIBED


@pytest.mark.asyncio
async def test_skips_when_subscription_history_exists():
    """**宿主已完成过** → 跳过。

    这是宿主 ``async_add()`` 不做的检查：订阅完成后记录移入
    ``SubscribeHistory``，只查 ``Subscribe`` 会把已拿到过的片子当新片重订
    （开发文档 §7.6）。
    """
    backend = FakeBackend(exists=False, history=True)
    # 只有显式关掉「重新订阅已完成」时，历史才用于拦截
    writer = SubscriptionWriter(
        backend, daily_limit=30, resubscribe_completed=False
    )
    report = await writer.write([item()], dry_run=False)

    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_ALREADY_COMPLETED


@pytest.mark.asyncio
async def test_precheck_failure_fails_open_and_still_writes():
    """复查查询失败时 fail-open：仍交给 add()，由身份幂等兜底。"""
    backend = FakeBackend(raise_precheck=True)
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert len(backend.add_calls) == 1
    assert report.added_count == 1


@pytest.mark.asyncio
async def test_add_failure_does_not_abort_batch():
    """单条写入异常不影响后续条目。"""
    backend = FakeBackend(raise_add=True)
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item(source_id="1"), item(source_id="2")], dry_run=False)

    assert len(report.outcomes) == 2
    assert report.added_count == 0
    assert all(o.decision == C.DECISION_PENDING_REVIEW for o in report.outcomes)


# --------------------------------------------------------------------- 安全闸门

@pytest.mark.asyncio
async def test_l4_identity_never_written():
    """**L4 永不写入** —— 只进待确认列表。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    l4 = item(resolved=ResolvedIdentity("themoviedb", "999", C.CONFIDENCE_L4, "fuzzy"))
    report = await writer.write([l4], dry_run=False)

    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_PENDING_REVIEW
    assert len(report.pending_review) == 1


@pytest.mark.asyncio
async def test_unresolved_item_never_written():
    """完全没有身份的条目同样只进待确认。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item(resolved=None)], dry_run=False)
    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_PENDING_REVIEW


@pytest.mark.asyncio
async def test_dry_run_never_writes():
    """dry-run 只判定不写入。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=True)

    assert backend.add_calls == []
    assert report.dry_run is True
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_DRY_RUN
    assert report.added_count == 0


@pytest.mark.asyncio
async def test_past_release_date_never_written():
    """定档已过去的条目不得写入。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    past = item(release_date=(TODAY - timedelta(days=3)).isoformat())
    report = await writer.write([past], dry_run=False, tz_name="Asia/Shanghai")
    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_NOT_FUTURE


@pytest.mark.asyncio
async def test_decades_old_release_date_rejected():
    """**兜底闸门**：几十年前的老片绝不能写入。

    真机出现过 2003 年的《戴帽子的猫》被列为新增。上游已有多道窗口过滤，
    这里再加一道 —— 这类错误最伤信任，值得冗余。
    """
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    old = item(release_date="2003-11-21")
    report = await writer.write([old], dry_run=False, tz_name="Asia/Shanghai")
    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_NOT_FUTURE
    assert "2003-11-21" in report.outcomes[0].reason


@pytest.mark.asyncio
async def test_far_future_release_date_rejected():
    """定档日期过远（超过兜底上限）也要拒写。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    far = item(release_date=(TODAY + timedelta(days=400)).isoformat())
    report = await writer.write([far], dry_run=False, tz_name="Asia/Shanghai")
    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_OUT_OF_WINDOW


@pytest.mark.asyncio
async def test_within_self_check_window_is_written():
    """兜底窗口内的正常条目不受影响。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    ok = item(release_date=(TODAY + timedelta(days=7)).isoformat())
    report = await writer.write([ok], dry_run=False, tz_name="Asia/Shanghai")
    assert report.added_count == 1


# --------------------------------------------------------------------- 已播完

@pytest.mark.asyncio
async def test_finished_series_gets_explicit_decision():
    """匹配到已播完的剧集要明确跳过，不能订。

    真机事故：Bangumi《ゲルぴよ 第2期》开播 2026-10-21，但匹配到的 TMDB
    309774 只有第 1 季（10 集，2026-01~03 全播完）。不传季号时宿主按第 1 季
    订阅 —— 等于订了一部 7 个月前就完结的番，只会去搜那 10 集老资源。
    """
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    finished = item(finished=True)
    report = await writer.write([finished], dry_run=False)

    assert backend.add_calls == []
    outcome = report.outcomes[0]
    assert outcome.decision == C.DECISION_SKIPPED_FINISHED
    assert "已无未播出内容" in outcome.reason


@pytest.mark.asyncio
async def test_unfinished_series_is_written():
    """还有未播内容的剧集不受影响。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item(finished=False)], dry_run=False)
    assert report.added_count == 1


# --------------------------------------------------------------------- 特别篇

@pytest.mark.asyncio
async def test_special_items_get_explicit_decision():
    """特别篇要给明确决策，不能报成「无确定性身份」。

    真机踩过：3 条 Bangumi 特别篇显示「无确定性身份（L4）」，
    看起来像插件的匹配有 bug，实际是这类内容 TMDB 没有独立条目。
    """
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    special = item(resolved=None, special=True)
    report = await writer.write([special], dry_run=False)

    assert backend.add_calls == []
    outcome = report.outcomes[0]
    assert outcome.decision == C.DECISION_SKIPPED_SPECIAL
    assert "特别篇" in outcome.reason
    assert "需要可手动订阅" in outcome.reason


@pytest.mark.asyncio
async def test_normal_item_not_treated_as_special():
    """普通条目不受影响。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item(special=False)], dry_run=False)
    assert report.added_count == 1


# --------------------------------------------------------------------- 每日上限

@pytest.mark.asyncio
async def test_daily_limit_caps_writes():
    """每日上限：超出的条目改写为上限跳过，且**不写入**。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=2)
    items = [item(source_id=str(i), resolved=ResolvedIdentity("themoviedb", str(1000 + i)))
             for i in range(5)]
    report = await writer.write(items, dry_run=False)

    assert report.added_count == 2
    assert len(backend.add_calls) == 2
    assert report.limit_hit is True
    limited = [o for o in report.outcomes if o.decision == C.DECISION_SKIPPED_DAILY_LIMIT]
    assert len(limited) == 3


@pytest.mark.asyncio
async def test_daily_limit_respects_already_written_today():
    """今日已写入的条数要占用额度。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=3)
    items = [item(source_id=str(i), resolved=ResolvedIdentity("themoviedb", str(2000 + i)))
             for i in range(5)]
    report = await writer.write(items, dry_run=False, already_written_today=3)

    assert report.added_count == 0
    assert backend.add_calls == []
    assert report.limit_hit is True


@pytest.mark.asyncio
async def test_daily_limit_zero_means_unlimited():
    """``daily_limit<=0`` 表示不限制。"""
    backend = FakeBackend()
    writer = SubscriptionWriter(backend, daily_limit=0)
    items = [item(source_id=str(i), resolved=ResolvedIdentity("themoviedb", str(3000 + i)))
             for i in range(3)]
    report = await writer.write(items, dry_run=False)
    assert report.added_count == 3


def test_write_report_summary_shape():
    """汇总字典字段齐全（供通知与状态接口复用）。"""
    from core.writer import WriteReport

    summary = WriteReport().to_summary()
    for key in ("total", "added", "skipped", "pending_review", "limit_hit", "dry_run"):
        assert key in summary


@pytest.mark.asyncio
async def test_resubscribes_completed_by_default():
    """**默认允许重新订阅已完成过的条目**。

    真机诉求：宿主把订阅标成完成会移入 subscribehistory，但用户可能已经从
    媒体库删掉文件、想重新下。默认因此忽略历史。

    安全性：真正「已经播完」的剧会先被 finished 判定拦住（TMDB 无未播集），
    所以不会每轮都重复建订阅。
    """
    backend = FakeBackend(exists=False, history=True)
    writer = SubscriptionWriter(backend, daily_limit=30)  # 默认 resubscribe_completed=True
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 1, "默认应该重新订阅"


@pytest.mark.asyncio
async def test_history_still_blocks_when_resubscribe_disabled():
    """关掉「重新订阅」后，历史仍然用于拦截。"""
    backend = FakeBackend(exists=False, history=True)
    writer = SubscriptionWriter(backend, daily_limit=30, resubscribe_completed=False)
    report = await writer.write([item()], dry_run=False)

    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_ALREADY_COMPLETED
