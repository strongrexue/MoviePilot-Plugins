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
    recorded_key,
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
    # 默认让宿主发原生「新增订阅」通知（可用 notify_each_subscription 关闭）
    assert call["message"] is True
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
    writer = SubscriptionWriter(backend, daily_limit=30)
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
async def test_completed_history_always_blocks():
    """1.17.2 起**没有开关**：完成过的一律跳过。

    真机事故：``resubscribe_completed`` 默认开着 → 插件加 → 宿主 1~2 分钟判
    「已完成订阅」并移出订阅列表 → 下一轮插件又加回来（《新手上路》6 次、
    《怪物：丽兹·波顿的故事》2 次）。要重下请到发现流水里手动订阅。
    """
    backend = FakeBackend(exists=False, history=True)
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_ALREADY_COMPLETED
    assert "流水" in report.outcomes[0].reason


def test_writer_no_longer_accepts_resubscribe_completed():
    """开关已移除：再传这个参数要立刻报错，避免有人加回来。"""
    backend = FakeBackend()
    with pytest.raises(TypeError):
        SubscriptionWriter(backend, daily_limit=30, resubscribe_completed=True)


# ------------------------------------------------------- 流水去重（订过就别再订回来）

def test_recorded_key_separates_seasons():
    """去重键必须带季号：同一部剧的不同季是不同订阅。"""
    assert recorded_key("themoviedb", "123", 1) != recorded_key("themoviedb", "123", 2)
    assert recorded_key("themoviedb", "123") == recorded_key("themoviedb", "123", 0)
    assert recorded_key("themoviedb", "123", None) == "themoviedb:123:0"
    assert recorded_key("themoviedb", "123", "2") == "themoviedb:123:2"


@pytest.mark.asyncio
async def test_recorded_item_is_not_resubscribed():
    """流水里记着订过 → 就算宿主现在没有这条订阅，也不再自动订。"""
    backend = FakeBackend(exists=False, history=False)
    writer = SubscriptionWriter(
        backend,
        daily_limit=30,
        recorded_keys=lambda: {recorded_key("themoviedb", "693134", None)},
    )
    report = await writer.write([item()], dry_run=False)

    assert backend.add_calls == []
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_RECORDED
    assert "清空流水" in report.outcomes[0].reason


@pytest.mark.asyncio
async def test_recorded_item_is_not_resubscribed_when_precheck_fails():
    """宿主复查抛错时也必须守住流水去重（1.14.7 真机事故）。

    真机日志原文：``reason: 复查失败但写入成功（数据库 worker 当前不可接收任务）``。
    200 条订阅、宿主数据库 worker 忙的时候 ``subscription_exists`` 直接抛错，
    原先的 fail-open 分支跳过了流水去重 → 所有订过的作品又被重订一遍。
    """
    backend = FakeBackend(exists=False, history=False, raise_precheck=True)
    writer = SubscriptionWriter(
        backend,
        daily_limit=30,
        recorded_keys=lambda: {recorded_key("themoviedb", "693134", None)},
    )
    report = await writer.write([item()], dry_run=False)

    assert backend.add_calls == [], "复查失败不能成为绕过去重的理由"
    assert backend.precheck_calls == 0, "流水去重应该排在宿主复查之前"
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_RECORDED


@pytest.mark.asyncio
async def test_unrecorded_item_is_written():
    """流水里没有记录 → 正常订阅。"""
    backend = FakeBackend(exists=False, history=False)
    writer = SubscriptionWriter(
        backend,
        daily_limit=30,
        recorded_keys=lambda: {recorded_key("themoviedb", "999", None)},
    )
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 1
    assert len(backend.add_calls) == 1


@pytest.mark.asyncio
async def test_recorded_season_does_not_block_other_season():
    """第 1 季记过，不妨碍第 2 季订阅。"""
    backend = FakeBackend(exists=False, history=False)
    writer = SubscriptionWriter(
        backend,
        daily_limit=30,
        recorded_keys=lambda: {recorded_key("themoviedb", "693134", 1)},
    )
    report = await writer.write(
        [item(media_type=C.MEDIA_TYPE_TV, season=2, release_date=None)],
        dry_run=False,
    )

    assert report.added_count == 1


@pytest.mark.asyncio
async def test_dedupe_switch_off_ignores_recorded():
    """关掉开关后，流水不再拦截。"""
    backend = FakeBackend(exists=False, history=False)
    writer = SubscriptionWriter(
        backend,
        daily_limit=30,
        dedupe_history=False,
        recorded_keys=lambda: {recorded_key("themoviedb", "693134", None)},
    )
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 1


@pytest.mark.asyncio
async def test_recorded_key_provider_failure_fails_open():
    """读流水失败不该拖垮整轮写入（宁可多订一条）。"""
    def boom():
        raise RuntimeError("插件数据读不出来")

    backend = FakeBackend(exists=False, history=False)
    writer = SubscriptionWriter(backend, daily_limit=30, recorded_keys=boom)
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 1
    assert writer.recorded_key_set() == set()


def test_recorded_key_set_reads_once_per_batch():
    """每批只读一次流水，不是每条都读（200 条订阅不该读 200 次插件数据）。"""
    calls = []

    def provider():
        calls.append(1)
        return {"themoviedb:1:0"}

    writer = SubscriptionWriter(FakeBackend(), daily_limit=0, recorded_keys=provider)
    writer.recorded_key_set()
    assert len(calls) == 1
    assert writer.recorded_key_set() == {"themoviedb:1:0"}


# --------------------------------------------------------------------- 假成功与错季

class SeasonAwareBackend:
    """按季号区分「已存在」的宿主替身。"""

    def __init__(self, existing_seasons=(), verify_result=True, raise_precheck=False):
        self.existing_seasons = set(existing_seasons)
        self.verify_result = verify_result
        self.raise_precheck = raise_precheck
        self._raised = False
        self.calls = []

    async def add(self, title, year, media_source, media_id, media_type,
                  season=None, *, episode_group=None, message=False, exist_ok=False):
        """返回一个订阅 ID，模拟宿主「看起来写成功了」。"""
        self.calls.append(("add", season))
        return 42, MESSAGE_ADDED

    async def subscription_exists(self, media_source, media_id, season=None):
        """写入前抛错、写入后返回预设结果（模拟数据库 worker 忙）。"""
        self.calls.append(("exists", season))
        if self.raise_precheck and not self._raised:
            # 只抛第一次：写入前复查失败，写入后复查返回真实结果
            self._raised = True
            raise RuntimeError("数据库 worker 当前不可接收任务")
        return season in self.existing_seasons

    async def history_exists(self, media_source, media_id, season=None):
        """没有历史记录。"""
        return False


@pytest.mark.asyncio
async def test_phantom_write_is_pending_review_when_verify_misses():
    """宿主返回了 ID 但复查不到 —— 不能算新增（真机 337/338 就是这样消失的）。"""
    backend = SeasonAwareBackend(existing_seasons=(), raise_precheck=True)
    writer = SubscriptionWriter(backend, daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 0
    outcome = report.outcomes[0]
    assert outcome.decision == C.DECISION_PENDING_REVIEW
    assert "复查不到" in outcome.reason


@pytest.mark.asyncio
async def test_verify_failure_keeps_added():
    """复查本身抛错时按写入成功处理，不误报待确认。"""

    class FlakyVerify(SeasonAwareBackend):
        """第一次查询抛错（写入前），之后也抛错（写入后）。"""

        async def subscription_exists(self, media_source, media_id, season=None):
            raise RuntimeError("数据库 worker 当前不可接收任务")

    writer = SubscriptionWriter(FlakyVerify(), daily_limit=30)
    report = await writer.write([item()], dry_run=False)

    assert report.added_count == 1


@pytest.mark.asyncio
async def test_title_season_hint_already_subscribed_is_skipped():
    """标题写第 2 季、宿主已订第 2 季 -> 不再按解析出的第 1 季重订一条。"""
    backend = SeasonAwareBackend(existing_seasons=(2,))
    writer = SubscriptionWriter(backend, daily_limit=30)
    entry = item(title="我的美食向导 第二季", season=1)
    report = await writer.write([entry], dry_run=False)

    assert report.added_count == 0
    outcome = report.outcomes[0]
    assert outcome.decision == C.DECISION_SKIPPED_ALREADY_SUBSCRIBED
    assert "第 2 季" in outcome.reason
