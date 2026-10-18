"""新增订阅时跳过 MoviePilot 的「首次全站搜索」。

背景：宿主 ``chain/subscribe/notify.py`` 在广播 ``SubscribeAdded`` 事件**之后**
会把新订阅入队一次全站搜索（``subscription_search_task``，``source='new'``、
``state='queued'``）。而本插件在同一个事件里会做 TG 频道缓存回搜 ——
两条路都跑就等于重复抓取（PT 下完 TG 又转存一份）。

做法（不碰宿主任何设置）：

1. 删掉刚入队的那条搜索任务 → 抑制「点完订阅立刻全站搜」
2. 把订阅状态 ``N`` → ``R`` → 抑制宿主「新增订阅搜索」任务（它只扫 ``state='N'``），
   同时让订阅进入正常生命周期，后续由宿主的定时搜索负责

.. important::
   宿主有 3 个搜索入口（``scheduler/catalog.py``）：
   ``new_subscribe_search``（扫 N）、``subscribe_search``（扫 R，按间隔）、
   ``subscribe_search_queue``（恢复队列）。只删队列不改状态的话，
   过一会儿 N 扫描还是会把刚跳过的订阅搜一遍。
"""
import threading
from typing import Any, Dict

from app.sdk.logging import logger
from sqlalchemy import delete, select

#: 宿主入队发生在事件之后，所以稍等再清理，避免和入队抢跑
CLEANUP_DELAY_SECONDS = 1.5

#: 同时最多等待多少个待清理的订阅（批量新增时合并）
_pending_lock = threading.Lock()
_pending: set = set()
_timer: Dict[str, Any] = {"handle": None}


def _cleanup(subscribe_ids: list) -> None:
    """删除首次搜索任务，并把 N 状态推进到 R。"""
    from app.db import ScopedSession
    from app.db.models.subscribe import Subscribe
    from app.db.models.subscriptionsearch import SubscriptionSearchTask

    removed = 0
    promoted = 0
    with ScopedSession() as session:
        for sid in subscribe_ids:
            result = session.execute(
                delete(SubscriptionSearchTask).where(
                    SubscriptionSearchTask.subscription_id == sid,
                    SubscriptionSearchTask.source == "new",
                    SubscriptionSearchTask.state == "queued",
                )
            )
            removed += int(getattr(result, "rowcount", 0) or 0)
            row = session.execute(
                select(Subscribe).where(Subscribe.id == sid)
            ).scalars().first()
            if row is not None and str(getattr(row, "state", "")) == "N":
                row.state = "R"
                promoted += 1
        session.commit()
    if removed or promoted:
        logger.info(
            f"[TgMediaCenter] 跳过宿主首次全站搜索：删除队列 {removed} 条、"
            f"状态 N→R {promoted} 条（共 {len(subscribe_ids)} 个订阅）"
        )


def _run_pending() -> None:
    with _pending_lock:
        ids = sorted(_pending)
        _pending.clear()
        _timer["handle"] = None
    if ids:
        try:
            _cleanup(ids)
        except Exception as err:  # pragma: no cover - 清理失败不能影响主流程
            logger.warning(f"[TgMediaCenter] 跳过首次搜索失败：{err}")


def schedule(subscribe_id: int) -> None:
    """登记一个订阅，防抖后统一清理。"""
    if not subscribe_id:
        return
    with _pending_lock:
        _pending.add(int(subscribe_id))
        handle = _timer.get("handle")
        if handle is not None:
            handle.cancel()
        timer = threading.Timer(CLEANUP_DELAY_SECONDS, _run_pending)
        timer.daemon = True
        _timer["handle"] = timer
        timer.start()


__all__ = ["schedule", "CLEANUP_DELAY_SECONDS"]
