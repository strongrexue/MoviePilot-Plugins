"""1.18.7 回归：跨事件循环信号量 + 未播集守门失守标记。

真机事故（2026-11-10 08:00 定时轮）：

- ``core/host.py`` 里三个 ``asyncio.Semaphore`` 是**模块级全局单例**，
  第一次在哪个事件循环里用就绑死到那个 loop。定时任务与 API 跑在不同
  loop，跨 loop 复用抛
  ``RuntimeError: <asyncio.locks.Semaphore object ...> is bound to a different event loop``。
- ``resolve_target_season`` 对这个异常是 fail-open（可订 + 默认季），
  于是整轮 50 次「季号裁决失败」，2016 年的《一禅小和尚》、无播出信息的
  《重庆号》被当成「即将开播」订了进来。
- 而剧集没有开播日期是常态，writer 里的「定档日期」兜底又只认非空的
  ``release_date`` —— 守门一失守就是单点故障，没有任何第二道闸。

两处修复：

1. 信号量按**当前事件循环**分池（``WeakKeyDictionary``），每个 loop 各自
   一份，绝不串用；
2. IdentityResolver 在守门 fail-open 时显式标记 ``season_verified=False``，
   writer 对「来源没给开播日期 + 守门没跑成」的剧集拒写，记为
   ``skipped_unverified``（不是「已播完」，下一轮裁决恢复后仍会重新判定）。

本文件锁住这两条：既要拦住漏进，也不能反过来把正常剧集全拦掉。
"""
import asyncio
import importlib
import inspect
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core import host  # noqa: E402
from subscribecenter.core.identity import IdentityResolver  # noqa: E402
from subscribecenter.core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from subscribecenter.core.writer import (  # noqa: E402
    MESSAGE_ADDED,
    SubscriptionWriter,
)

TODAY = date.today()


# --------------------------------------------------------------------- 修复 1：信号量

def test_no_module_level_semaphore_singletons():
    """旧的三个全局单例必须删干净 —— 留一个就还可能跨 loop 绑死。"""
    for name in ("_SEASON_SEMAPHORE", "_DOUBAN_SEMAPHORE", "_POSTER_SEMAPHORE"):
        assert not hasattr(host, name), f"{name} 仍在 {host.__name__} 里（旧全局单例）"
    assert hasattr(host, "_LOOP_SEMAPHORES")
    assert isinstance(host._LOOP_SEMAPHORES, __import__("weakref").WeakKeyDictionary)


def test_semaphore_source_uses_running_loop():
    """``_semaphore`` 必须按「当前运行中的 loop」取，且并发上限不变。"""
    source = inspect.getsource(host._semaphore)
    assert "get_running_loop()" in source
    assert "_LOOP_SEMAPHORES.get(loop)" in source
    assert host._SEMAPHORE_LIMITS == {"season": 4, "douban": 2, "poster": 4}


@pytest.mark.parametrize("kind", ["season", "douban", "poster"])
def test_semaphore_isolated_between_event_loops(kind):
    """同一个 loop 内复用，不同 loop 各一份（这正是修复的核心）。"""
    async def grab():
        sem = host._semaphore(kind)
        assert host._semaphore(kind) is sem, "同一 loop 内应复用同一把锁"
        return sem

    loop_a = asyncio.new_event_loop()
    loop_b = asyncio.new_event_loop()
    try:
        a = loop_a.run_until_complete(grab())
        b = loop_b.run_until_complete(grab())
        assert a is not b, f"{kind} 信号量被两个事件循环复用了（1.18.7 真机故障）"
    finally:
        loop_a.close()
        loop_b.close()


def test_semaphore_bound_in_one_loop_is_usable_in_another():
    """忠实复现真机：在 A loop 把锁占满并绑死，B loop 仍能正常取用。

    旧实现下 B loop 拿到的是 A 那把（已锁满、绑在 A），``acquire()`` 会抛
    ``RuntimeError: ... is bound to a different event loop``；新实现拿到的是
    自己的新锁，立即放行。
    """
    async def saturate_a():
        sem = host._season_semaphore()
        for _ in range(host._SEMAPHORE_LIMITS["season"]):
            await sem.acquire()
        # 第五次必然进等待队列，强制 Semaphore 绑定当前 loop
        pending = asyncio.ensure_future(sem.acquire())
        await asyncio.sleep(0)
        return sem, pending

    async def use_b():
        sem = host._season_semaphore()
        # 旧实现：这里会抛 "bound to a different event loop"
        await asyncio.wait_for(sem.acquire(), 0.2)
        sem.release()

    loop_a = asyncio.new_event_loop()
    loop_b = asyncio.new_event_loop()
    try:
        loop_a.run_until_complete(saturate_a())
        loop_b.run_until_complete(use_b())  # 不抛异常即通过
    finally:
        loop_a.close()
        loop_b.close()


# --------------------------------------------------------------------- 修复 2：守门标记

class FakeTmdb:
    """可控的 TMDB 替身：预设置裁决结果或抛错。"""

    def __init__(self, verdict=(True, 2, None), raises=None):
        self.verdict = verdict
        self.raises = raises
        self.season_calls = []

    async def search(self, title, year, media_type, *, limit=5):
        return ()

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        return {}

    async def resolve_target_season(
        self, tmdb_id, media_type, season_hint=None, **kwargs
    ):
        self.season_calls.append((tmdb_id, media_type, season_hint))
        if self.raises is not None:
            raise self.raises
        return self.verdict


def tv_item(**overrides):
    """一条「来源没给开播日期」的剧集（真机重庆号 / 一禅小和尚的形态）。"""
    data = {
        "source": C.SOURCE_DOUBAN_RSS,
        "source_id": "340224",
        "title": "重庆号",
        "media_type": C.MEDIA_TYPE_TV,
        "year": "2026",
        "release_date": None,
        "date_unknown": True,
        "native_ids": {"tmdb": "340224"},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


def test_season_verified_defaults_true():
    """手工构造 / 测试替身默认算「已确认」，不能被新守卫误伤。"""
    item = tv_item()
    assert item.season_verified is True
    # writable 仍只看 special/finished/resolved，新字段不参与
    item.resolved = ResolvedIdentity("themoviedb", "340224", C.CONFIDENCE_L1)
    assert item.writable is True


@pytest.mark.asyncio
async def test_gate_exception_marks_unverified_but_stays_fail_open():
    """守门抛错：标记未确认，但仍保持 fail-open（不把内容判成已播完）。"""
    item = await IdentityResolver(
        FakeTmdb(raises=RuntimeError("bound to a different event loop"))
    ).resolve(tv_item())

    assert item.resolved is not None
    assert item.season_verified is False
    assert item.finished is False
    assert item.writable is True


@pytest.mark.asyncio
async def test_gate_typeerror_fallback_also_marks_unverified():
    """老适配器不认 upcoming_max_days 关键字时走内层兜底，同样要标记。"""
    class OldAdapter(FakeTmdb):
        async def resolve_target_season(
            self, tmdb_id, media_type, season_hint=None, *, prefer_episode_group=True
        ):
            raise RuntimeError("老适配器炸了")

    item = await IdentityResolver(OldAdapter()).resolve(tv_item())
    assert item.season_verified is False
    assert item.finished is False


@pytest.mark.asyncio
async def test_fail_open_no_season_marks_unverified():
    """host 的 fail-open 返回 (True, None, None) —— 正是 1.18.7 真机形态。"""
    item = await IdentityResolver(FakeTmdb(verdict=(True, None, None))).resolve(
        tv_item()
    )
    assert item.season_verified is False
    assert item.finished is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verdict",
    [
        (True, 2, None),          # 正常给出季号
        (True, 2, "group-123"),   # 季号 + 剧集组
        (True, None, "group-9"),  # 只有剧集组（被压成单季的番剧）
    ],
)
async def test_normal_verdict_keeps_verified(verdict):
    """正常裁决必须保持 True —— 不能把正常剧集一起拦掉。"""
    item = await IdentityResolver(FakeTmdb(verdict=verdict)).resolve(tv_item())
    assert item.season_verified is True
    assert item.finished is False


@pytest.mark.asyncio
async def test_finished_verdict_does_not_need_unverified_flag():
    """明确判「已播完」时 finished 生效，与 season_verified 无关。"""
    item = await IdentityResolver(FakeTmdb(verdict=(False, None, None))).resolve(
        tv_item()
    )
    assert item.finished is True
    assert item.writable is False


# --------------------------------------------------------------------- writer 守卫

class FakeBackend:
    """最小宿主订阅替身：记录 add 调用。"""

    def __init__(self):
        self.add_calls = []

    async def add(self, title, year, media_source, media_id, media_type,
                  season=None, *, episode_group=None, message=False, exist_ok=False):
        self.add_calls.append((media_source, media_id, season))
        return 42, MESSAGE_ADDED

    async def subscription_exists(self, media_source, media_id, season=None):
        return False

    async def history_exists(self, media_source, media_id, season=None):
        return False


def resolved_tv(**overrides):
    """已解析身份的 TV 条目（跳过 IdentityResolver，直接测 writer）。"""
    return tv_item(
        resolved=ResolvedIdentity("themoviedb", "340224", C.CONFIDENCE_L1),
        **overrides,
    )


@pytest.mark.asyncio
async def test_writer_blocks_undated_tv_when_season_unverified():
    """核心回归：无日期 + 守门没跑成 -> 拒写，且不碰宿主 add()。"""
    backend = FakeBackend()
    report = await SubscriptionWriter(backend, daily_limit=30).write(
        [resolved_tv(season_verified=False)], dry_run=False
    )

    assert report.added_count == 0
    assert backend.add_calls == []
    outcome = report.outcomes[0]
    assert outcome.decision == C.DECISION_SKIPPED_UNVERIFIED
    assert "未播集裁决未跑成" in outcome.reason
    assert outcome.success is False


@pytest.mark.asyncio
async def test_writer_allows_undated_tv_when_season_verified():
    """反向保护：守门跑成了就必须正常写入（不能一刀切拦掉所有无日期剧集）。"""
    backend = FakeBackend()
    report = await SubscriptionWriter(backend, daily_limit=30).write(
        [resolved_tv(season_verified=True)], dry_run=False
    )

    assert report.added_count == 1
    assert report.outcomes[0].decision == C.DECISION_ADDED
    assert len(backend.add_calls) == 1


@pytest.mark.asyncio
async def test_writer_allows_dated_tv_even_when_unverified():
    """有定档日期的剧集由日期兜底把关，不受新守卫影响。"""
    backend = FakeBackend()
    entry = resolved_tv(
        season_verified=False,
        release_date=(TODAY + timedelta(days=3)).isoformat(),
        date_unknown=False,
    )
    report = await SubscriptionWriter(backend, daily_limit=30).write(
        [entry], dry_run=False
    )

    assert report.added_count == 1
    assert len(backend.add_calls) == 1


@pytest.mark.asyncio
async def test_writer_never_blocks_movie_with_unverified_flag():
    """守卫只针对剧集；电影有自己的「无日期跳过」路径，不能被误伤。"""
    backend = FakeBackend()
    film = resolved_tv(
        media_type=C.MEDIA_TYPE_MOVIE,
        season_verified=False,
        release_date=(TODAY + timedelta(days=3)).isoformat(),
    )
    report = await SubscriptionWriter(backend, daily_limit=30).write(
        [film], dry_run=False
    )

    assert report.outcomes[0].decision != C.DECISION_SKIPPED_UNVERIFIED
    assert report.added_count == 1


@pytest.mark.asyncio
async def test_1187_end_to_end_gate_failure_blocks_old_show():
    """完整复现真机链路：跨 loop 报错 -> 守门 fail-open -> writer 拦下老片。"""
    item = await IdentityResolver(
        FakeTmdb(raises=RuntimeError("is bound to a different event loop"))
    ).resolve(tv_item(title="一禅小和尚", year="2016"))
    # IdentityResolver 的 L1 路径只解析身份，writer 还要一个可写身份
    assert item.resolved is not None
    assert item.season_verified is False

    backend = FakeBackend()
    report = await SubscriptionWriter(backend, daily_limit=30).write(
        [item], dry_run=False
    )

    assert backend.add_calls == [], "老片仍被写进了订阅（1.18.7 事故重演）"
    assert report.outcomes[0].decision == C.DECISION_SKIPPED_UNVERIFIED


# --------------------------------------------------------------------- 常量 / 前端 / 排序

def test_decision_constant_and_rank():
    """新决策要有稳定字符串，且在历史合并里与「已播完」同级。"""
    assert C.DECISION_SKIPPED_UNVERIFIED == "skipped_unverified"
    plugin = importlib.import_module("app.plugins.subscribecenter")
    assert plugin._DECISION_RANK["skipped_unverified"] == 2
    assert plugin._DECISION_RANK["skipped_unverified"] == plugin._DECISION_RANK[
        "skipped_finished"
    ]


@pytest.mark.parametrize(
    "filename",
    ["Page.vue", "Config.vue"],
)
def test_frontend_labels_include_unverified(filename):
    """流水页 / 预览页都要能显示这个新决策，不能显示成裸 key。"""
    text = (
        REPO_ROOT / "plugins.v3" / PLUGIN_ID / "src" / "components" / filename
    ).read_text(encoding="utf-8")
    assert "skipped_unverified:" in text, f"{filename} 缺少 skipped_unverified 文案"
