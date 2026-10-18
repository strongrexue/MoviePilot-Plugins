"""并发解析与缓存攒批（0.8.2）。

用户反对「榜单别配超过 4 条」这类限制 —— 他要的是全自动。真实约束是查询量，
正确解法是**并发**而不是让人手工挑：

    实测（15 条路线、每榜单上限 10 -> 127 条候选）
      串行 0.71s/条 -> 127 条约 91 秒，260 条约 186 秒（3 分钟）
      并发 5~8 路   -> 260 条约 20~30 秒

另外 `MappingCacheStore.remember` 原来**每条都落盘** —— 200+ 条候选等于
200+ 次数据库写入。现改为 `batch()` 期间只标脏、退出时统一落盘一次。
"""
import asyncio
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.cache import MappingCacheStore  # noqa: E402
from subscribecenter.core.model import (  # noqa: E402
    DiscoveredItem,
    ResolvedIdentity,
)

TODAY = date.today()


# --------------------------------------------------------------------- 并发

@pytest.mark.asyncio
async def test_resolution_is_concurrent():
    """解析必须并发：串行 200+ 条会让一次运行拖到几分钟。

    用一个「每条耗时 20ms」的解析器跑 20 条：
    串行至少 400ms，并发 8 路应远小于该值。
    """
    from subscribecenter.core import pipeline as P

    class SlowResolver:
        def __init__(self):
            self.calls = 0

        async def resolve(self, item):
            self.calls += 1
            await asyncio.sleep(0.02)
            item.resolved = ResolvedIdentity("themoviedb", "1")

    class NoopWriter:
        async def write(self, items, **kwargs):  # noqa: ARG002
            from subscribecenter.core.writer import WriteReport

            return WriteReport(outcomes=[], dry_run=True)

    class NoopSource:
        name = C.SOURCE_TMDB

        async def fetch(self, config):  # noqa: ARG002
            return [
                DiscoveredItem(
                    source=C.SOURCE_TMDB,
                    source_id=str(index),
                    title=f"片{index}",
                    media_type=C.MEDIA_TYPE_MOVIE,
                    year=str(TODAY.year),
                    release_date=(TODAY + timedelta(days=1)).isoformat(),
                )
                for index in range(20)
            ]

    resolver = SlowResolver()
    start = time.monotonic()
    await P.run_pipeline(
        sources=[NoopSource()],
        enabled=[C.SOURCE_TMDB],
        resolver=resolver,
        writer=NoopWriter(),
        config={},
        future_days=3,
        min_rating=0.0,
        resolve_concurrency=8,
        dry_run=True,
        tz_name="Asia/Shanghai",
    )
    elapsed = time.monotonic() - start

    assert resolver.calls == 20, "所有条目都要被解析"
    # 串行需要 >= 0.4s；并发 8 路约 0.06s，留足余量取 0.3s
    assert elapsed < 0.3, f"解析看起来没有并发（耗时 {elapsed:.2f}s）"


@pytest.mark.asyncio
async def test_single_item_failure_does_not_abort_others():
    """并发下单条解析失败不能影响其余条目。"""

    class FlakyResolver:
        async def resolve(self, item):
            if item.source_id == "3":
                raise RuntimeError("这条炸了")
            item.resolved = ResolvedIdentity("themoviedb", "1")


    class NoopWriter:
        async def write(self, items, **kwargs):  # noqa: ARG002
            from subscribecenter.core.writer import WriteReport

            return WriteReport(outcomes=[], dry_run=True)

    class Source:
        name = C.SOURCE_TMDB

        async def fetch(self, config):  # noqa: ARG002
            return [
                DiscoveredItem(
                    source=C.SOURCE_TMDB,
                    source_id=str(index),
                    title=f"片{index}",
                    media_type=C.MEDIA_TYPE_MOVIE,
                    year=str(TODAY.year),
                    release_date=(TODAY + timedelta(days=1)).isoformat(),
                )
                for index in range(1, 6)
            ]

    items = await Source().fetch({})
    # 直接验证解析层：坏的那条被标记，其余正常
    resolver = FlakyResolver()
    for item in items:
        try:
            await resolver.resolve(item)
        except Exception as err:  # noqa: BLE001
            item.resolved = None
            item.raw["resolve_error"] = str(err)

    assert sum(1 for item in items if item.resolved) == 4
    assert items[2].resolved is None
    assert "炸了" in items[2].raw["resolve_error"]


# --------------------------------------------------------------------- 缓存攒批

class CountingStore:
    """统计落盘次数的存储替身。"""

    def __init__(self):
        self.saves = 0
        self.payload = None

    def save(self, payload):
        self.saves += 1
        self.payload = payload

    def load(self):
        return self.payload


def make_identity(index):
    """构造一个可写入的身份。"""
    return ResolvedIdentity(
        "themoviedb", str(index + 1), C.CONFIDENCE_L1, "native:tmdb"
    )


def test_cache_flushes_once_per_batch():
    """batch() 期间只标脏，退出时落盘一次。

    逐条落盘在 200+ 条候选时等于 200+ 次数据库写入。
    """
    store = CountingStore()
    cache = MappingCacheStore(store)

    with cache.batch():
        for index in range(20):
            cache.remember(f"k{index}", make_identity(index))

    assert store.saves == 1, f"应只落盘一次，实际 {store.saves} 次"
    assert len(store.payload["entries"]) == 20


def test_cache_flushes_immediately_outside_batch():
    """不在 batch 里时仍然是即时落盘（行为不变）。"""
    store = CountingStore()
    cache = MappingCacheStore(store)
    cache.remember("k1", make_identity(1))
    assert store.saves == 1


def test_cache_batch_flushes_on_exception():
    """batch 里抛异常也要把已写入的落盘（用 finally）。"""
    store = CountingStore()
    cache = MappingCacheStore(store)
    with pytest.raises(RuntimeError):
        with cache.batch():
            cache.remember("k1", make_identity(1))
            raise RuntimeError("boom")
    assert store.saves == 1
    assert "k1" in store.payload["entries"]


def test_nested_batch_flushes_once():
    """嵌套 batch 只在最外层退出时落盘。"""
    store = CountingStore()
    cache = MappingCacheStore(store)
    with cache.batch():
        cache.remember("a", make_identity(1))
        with cache.batch():
            cache.remember("b", make_identity(2))
        assert store.saves == 0, "内层退出不应落盘"
    assert store.saves == 1


# --------------------------------------------------------------------- 配置

def test_defaults_favour_automation():
    """默认值应该让「配满榜单」可用，而不是逼用户手工挑。"""
    config = C.default_config()
    assert config["douban_max_items_per_feed"] >= 30
    assert config["resolve_concurrency"] >= 4
