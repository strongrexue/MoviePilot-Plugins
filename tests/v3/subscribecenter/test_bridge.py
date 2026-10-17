"""调度线程 ↔ asyncio 桥接的回归测试（开发文档 §7.2）。

这是骨架里最容易写错的一层：``get_service()`` 注册的 ``func`` 由 apscheduler
在**没有事件循环的线程**里调用，而 ``/run_once`` 端点在事件循环内。
"""
import asyncio
import sys
import threading
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core.bridge import PipelineBridge, has_running_loop, run_sync  # noqa: E402

# --------------------------------------------------------------------- 环境探测

def test_has_running_loop_false_in_sync_context():
    """普通同步上下文没有事件循环。"""
    assert has_running_loop() is False


@pytest.mark.asyncio
async def test_has_running_loop_true_in_async_context():
    """异步上下文能探测到事件循环。"""
    assert has_running_loop() is True


# --------------------------------------------------------------------- run_sync

def test_run_sync_executes_coroutine():
    """同步上下文能跑完协程并拿到结果。"""

    async def work():
        await asyncio.sleep(0)
        return "done"

    assert run_sync(work()) == "done"


def test_run_sync_works_in_worker_thread():
    """调度线程（非主线程、无循环）同样可用 —— 这是定时任务的真实形态。"""
    result = {}

    async def work():
        return threading.current_thread().name

    def runner():
        result["name"] = run_sync(work())

    thread = threading.Thread(target=runner, name="apscheduler-worker")
    thread.start()
    thread.join(timeout=10)
    assert result["name"] == "apscheduler-worker"


@pytest.mark.asyncio
async def test_run_sync_refuses_inside_loop():
    """已有事件循环时必须拒绝，避免嵌套运行事件循环。"""

    async def work():
        return 1

    # 先取协程再断言抛错；用 try/finally 关闭未消费的协程，避免 RuntimeWarning
    coro = work()
    try:
        with pytest.raises(RuntimeError, match="不能在已有事件循环"):
            run_sync(coro)
    finally:
        coro.close()


# --------------------------------------------------------------------- 桥接互斥

def test_bridge_run_is_mutually_exclusive():
    """同步入口在已有运行在跑时返回 ``None``，不排队。"""
    bridge = PipelineBridge("test-exclusive-sync")
    started = threading.Event()
    release = threading.Event()
    results = {}

    async def work():
        started.set()
        await asyncio.to_thread(release.wait, 5)
        return "first"

    def holder():
        results["first"] = bridge.run(work)

    thread = threading.Thread(target=holder)
    thread.start()
    assert started.wait(timeout=5)

    # 第二次调用（同一实例）必须被互斥跳过
    assert bridge.run(work) is None
    assert bridge.busy is True

    release.set()
    thread.join(timeout=10)
    assert results["first"] == "first"
    assert bridge.busy is False


@pytest.mark.asyncio
async def test_bridge_async_entry_is_mutually_exclusive_with_sync():
    """异步入口与同步入口共用同一把锁。"""
    bridge = PipelineBridge("test-exclusive-cross")
    acquired = threading.Event()
    release = threading.Event()

    def holder():
        async def work():
            acquired.set()
            await asyncio.to_thread(release.wait, 5)
            return "sync"

        bridge.run(work)

    thread = threading.Thread(target=holder)
    thread.start()
    assert acquired.wait(timeout=5)

    async def async_work():
        return "async"

    assert await bridge.run_async(async_work) is None

    release.set()
    thread.join(timeout=10)
    assert bridge.busy is False


@pytest.mark.asyncio
async def test_bridge_async_entry_returns_value():
    """异步入口在空闲时正常返回结果。"""
    bridge = PipelineBridge("test-async-value")

    async def work():
        return 7

    assert await bridge.run_async(work) == 7
    assert bridge.busy is False


def test_different_instances_do_not_block_each_other():
    """虚拟分身隔离：不同实例标识各有独立锁。"""
    a = PipelineBridge("test-instance-a")
    b = PipelineBridge("test-instance-b")
    assert a._lock is not b._lock


def test_bridge_releases_lock_on_exception():
    """业务异常不得让锁泄漏（否则后续运行永久跳过）。"""
    bridge = PipelineBridge("test-exception")

    async def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        bridge.run(boom)
    assert bridge.busy is False


def test_bridge_run_refuses_inside_loop():
    """同步入口在事件循环内调用时必须报错，提示改用异步入口。"""
    bridge = PipelineBridge("test-sync-in-loop")

    async def work():
        return 1

    async def scenario():
        return bridge.run(work)

    with pytest.raises(RuntimeError, match="同步入口"):
        asyncio.run(scenario())
