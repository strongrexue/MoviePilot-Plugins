"""新增订阅时跳过 MoviePilot 的「首次全站搜索」。

宿主的执行顺序（``app/chain/subscribe/notify.py``）::

    1) 发通知
    2) 广播 SubscribeAdded 事件        ← 本插件在这里把状态 N 改成 R
    3) 入队「首次全站搜索」             ← 此时 state 已不是 N，宿主直接跳过

``_SubscribeChain__queue_new_subscription_search`` 的第一句判断就是::

    if subscribe is None or subscribe.state != "N":
        return None

所以**不需要**删队列、也不需要定时器等任何东西 —— 在事件里把状态推进到 ``R``
（"已开始处理"）就够了，并且订阅随即进入正常生命周期，后续由宿主
「订阅定时搜索」按间隔补搜。

.. note::
   这个做法来自插件市场已有的 ``subscribenoautosearch``（作者 tafei）：
   用宿主的 ``SubscribeOper.update(subscribe_id, {"state": "R"})``。
   第一版我用「延迟 1.5 秒删 subscription_search_task」实现，真机无效 ——
   删队列时机太晚且列值不可靠。
"""
from typing import Any

from app.sdk.logging import logger


def activate(subscribe_id: int) -> bool:
    """把新订阅状态从 ``N`` 推进到 ``R``（幂等，非 N 状态不动）。

    返回是否真的改了状态。任何异常只记日志，不抛回宿主事件总线。
    """
    if not subscribe_id:
        return False
    try:
        from app.db.subscribe_oper import SubscribeOper

        oper = SubscribeOper()
        subscribe = oper.get(int(subscribe_id))
        if not subscribe:
            return False
        if str(getattr(subscribe, "state", "")) != "N":
            return False
        oper.update(int(subscribe_id), {"state": "R"})
    except Exception as err:  # pragma: no cover - 事件回调不能抛回宿主
        logger.warning(f"[TgMediaCenter] 跳过首次搜索失败（订阅 {subscribe_id}）：{err}")
        return False

    name: Any = getattr(subscribe, "name", "") or f"订阅 #{subscribe_id}"
    logger.info(
        f"[TgMediaCenter] 新增订阅「{name}」(ID={subscribe_id}) 已置为订阅中，"
        f"跳过宿主首次全站搜索（交给 TG 回搜与定时任务）"
    )
    return True


__all__ = ["activate"]
