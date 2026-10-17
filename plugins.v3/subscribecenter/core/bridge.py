"""调度线程 ↔ asyncio 桥接（开发文档 §7.2）。

**这是骨架里必须先定的东西**，两个入口的形状完全不同：

- ``get_service()`` 注册的任务由 apscheduler 在**自己的线程**里调用，
  该线程**没有事件循环**，``func`` 也不能是 ``async def``；
- ``/run_once`` 这类 FastAPI 端点**已在事件循环内**，直接 ``await`` 即可。

两者必须共用同一套业务协程，因此业务代码不允许感知调用方是谁。

另外：``/run_once`` 与 cron 任务必须**互斥** —— 手动触发与定时触发重叠会放大
「同一批条目并发写入」的风险（开发文档 §7.2）。
"""
import asyncio
import threading
from contextlib import contextmanager
from typing import Awaitable, Callable, Iterator, Optional, TypeVar

T = TypeVar("T")

#: 同一插件实例的流水线互斥锁（进程内即可 —— 插件与宿主同进程）
_PIPELINE_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(owner_id: str) -> threading.Lock:
    """获取（或创建）指定插件实例的流水线互斥锁。"""
    with _LOCKS_GUARD:
        lock = _PIPELINE_LOCKS.get(owner_id)
        if lock is None:
            lock = threading.Lock()
            _PIPELINE_LOCKS[owner_id] = lock
        return lock


def has_running_loop() -> bool:
    """当前线程是否已有可用的事件循环。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def run_sync(coro: Awaitable[T], *, timeout: Optional[float] = None) -> T:
    """在**同步上下文**（调度线程 / 普通线程）里跑完一个协程并返回结果。

    与 ``asyncio.run()`` 的区别：``asyncio.run()`` 会无条件新建并关闭事件循环，
    在已有循环的线程里调用会抛 ``RuntimeError``。插件需要的是「两种上下文都能用」，
    因此本函数按当前线程状态分派：

    - 已在事件循环内 → 直接交给调用方 ``await``（**本函数不适用**，会抛错），
      由 :meth:`PipelineBridge.run` 之类的 async 入口处理；
    - 无事件循环（调度线程）→ 新建一个私有循环跑完再关闭。

    :raises RuntimeError: 在已有事件循环的线程里被调用
    """
    if has_running_loop():
        raise RuntimeError(
            "run_sync() 不能在已有事件循环的线程中调用；请直接 await 业务协程"
        )
    return asyncio.run(_with_timeout(coro, timeout))


async def _with_timeout(coro: Awaitable[T], timeout: Optional[float]) -> T:
    """可选超时包装。"""
    if timeout is None:
        return await coro
    return await asyncio.wait_for(coro, timeout=timeout)


class PipelineBridge:
    """让「同步调度入口」与「异步 API 入口」共用一条业务协程。

    :param owner_id: 插件实例标识（虚拟分身天然隔离，用 ``self.__class__.__name__``）
    """

    def __init__(self, owner_id: str) -> None:
        self._owner_id = owner_id
        self._lock = _lock_for(owner_id)

    @property
    def busy(self) -> bool:
        """当前是否有流水线正在运行。"""
        return self._lock.locked()

    @contextmanager
    def _guard(self) -> Iterator[bool]:
        """非阻塞获取互斥锁；已被占用时 ``acquired=False``。"""
        acquired = self._lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                self._lock.release()

    def run(
        self,
        factory: Callable[[], Awaitable[T]],
        *,
        timeout: Optional[float] = None,
    ) -> Optional[T]:
        """**同步**入口：供 ``get_service()`` 注册的定时任务调用。

        :param factory: 协程工厂（每次调用产生新的协程；不要传已创建的协程对象，
            否则互斥跳过时会留下未 await 的协程告警）
        :return: 业务结果；已在运行时返回 ``None``（本次跳过，不排队）
        """
        if has_running_loop():
            raise RuntimeError(
                "PipelineBridge.run() 是同步入口；在事件循环内请改用 run_async()"
            )
        with self._guard() as acquired:
            if not acquired:
                return None
            return run_sync(factory(), timeout=timeout)

    async def run_async(
        self,
        factory: Callable[[], Awaitable[T]],
        *,
        timeout: Optional[float] = None,
    ) -> Optional[T]:
        """**异步**入口：供 ``/run_once`` 等 FastAPI 端点调用。

        互斥检查与 :meth:`run` 共用同一把锁，因此两种入口彼此互斥。
        由于锁是线程锁，在异步上下文里必须用 ``to_thread`` 之外的方式避免阻塞：
        这里只用 ``acquire(blocking=False)``，不做等待，因此不会阻塞事件循环。
        """
        if not self._lock.acquire(blocking=False):
            return None
        try:
            coro = factory()
            if timeout is None:
                return await coro
            return await asyncio.wait_for(coro, timeout=timeout)
        finally:
            self._lock.release()


__all__ = [
    "PipelineBridge",
    "has_running_loop",
    "run_sync",
]
