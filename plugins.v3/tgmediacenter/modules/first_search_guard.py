"""新增订阅时跳过 MoviePilot 的「首次全站搜索」。

宿主的搜索有两条触发路径，必须**同时**堵住：

1. ``chain/subscribe/notify.py`` 在广播 ``SubscribeAdded`` 之后把新订阅入队搜索
   （``_SubscribeChain__queue_new_subscription_search``），而它第一句就是
   ``if subscribe.state != "N": return None``。
2. ``SubscribeOper.update(...)`` 会通过应用层 mutation **发出** ``subscribe.modified``
   广播事件，宿主/其它插件收到后会立刻搜这条订阅（真机日志：
   ``subscribe.modified → search.py 开始搜索订阅``）。

所以正确做法是：**直接改数据库里的 state，不发任何事件**。
``SubscribeOper`` 那条路（插件市场的 subscribenoautosearch 也是这么做）
会触发第 2 条路径，实测仍然会被搜。

.. note::
   两个条件同时满足：
   - 不发 ``subscribe.modified`` → 不触发第 2 条
   - 数据库里 state 已是 ``R`` → 宿主入队前检查时跳过第 1 条
"""
from typing import Any

from app.sdk.logging import logger


def activate(subscribe_id: int) -> bool:
    """把新订阅状态从 ``N`` 直接写成 ``R``（**不发事件**，幂等）。

    返回是否真的改了状态。任何异常只记日志，不抛回宿主事件总线。
    """
    if not subscribe_id:
        return False
    try:
        from app.db import ScopedSession
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

        with ScopedSession() as session:
            row = session.execute(
                select(Subscribe).where(Subscribe.id == int(subscribe_id))
            ).scalars().first()
            if row is None or str(getattr(row, "state", "")) != "N":
                return False
            name: Any = getattr(row, "name", "") or f"订阅 #{subscribe_id}"
            row.state = "R"
            session.commit()
    except Exception as err:  # pragma: no cover - 事件回调不能抛回宿主
        logger.warning(f"[TgMediaCenter] 跳过首次搜索失败（订阅 {subscribe_id}）：{err}")
        return False

    logger.info(
        f"[TgMediaCenter] 新增订阅「{name}」(ID={subscribe_id}) 已置为订阅中，"
        f"跳过宿主首次全站搜索（不发 subscribe.modified，交给 TG 回搜与定时任务）"
    )
    return True


__all__ = ["activate"]
