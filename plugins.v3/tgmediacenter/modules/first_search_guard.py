"""新增订阅时跳过 MoviePilot 的「首次全站搜索」（独立开关，默认关）。

背景
----
宿主保存订阅后会把这条订阅排进全站搜索（``subscription_search_task``，
``source='new'``、约 60 秒后到期）。本插件的「订阅回搜」已经从 TG 频道缓存里
找同一部作品，两边都跑等于重复抓取。

为什么不能靠事件（1.13.5 ~ 1.13.7 三版失败的根因）
--------------------------------------------------
1. 宿主广播是**异步**的：``send_event`` 只把事件塞进优先级队列，由后台消费线程
   稍后分发；而 ``notify.py`` 在 ``send_event`` 之后**同步**入队首搜
   （真机日志：事件 41,043 入队，41,051 首搜已排好）。等我们的处理器跑起来，
   任务已经入队，抢跑必输。
2. 就算把状态改成 ``R``，那条已入队的任务在执行时只认 ``S``（暂停）才跳过
   （``searchtask.py::_skip_paused_subscription``），``R`` 不拦 —— 到点照样搜。

所以只能**在入队前**拦：包住宿主唯一的入队入口
``SubscribeSearchOwner._SubscribeChain__queue_new_subscription_search``
（含异步版），对 ``state == 'N'`` 的订阅直接把状态写成 ``R`` 并返回 ``None``
—— 不入队、不写「已安排搜索」活动记录、不产生 60 秒后的那次全站搜索。

与「订阅回搜」的关系
--------------------
**互不依赖**：开关是独立的配置项 ``skip_first_search_enabled``（默认关），
关掉它不影响回搜，关掉回搜也不影响它。

失效纪律
--------
宿主升级后若入队方法改名/消失，``install()`` 返回 False 并留 WARNING，功能整体
失效（绝不误伤宿主原本的入队行为）；插件停用/重载时 ``uninstall()`` 还原方法。
"""
from __future__ import annotations

import threading
from typing import Any

from app.sdk.logging import logger

#: 独立开关（配置键）
CONFIG_KEY = "skip_first_search_enabled"

#: 宿主入队入口。（单下划线开头，不参与 Python 名称改写，可直接 setattr）
MANGLE_SYNC = "_SubscribeChain__queue_new_subscription_search"
MANGLE_ASYNC = "_SubscribeChain__async_queue_new_subscription_search"

_lock = threading.Lock()
_state: dict[str, Any] = {
    "owner": None,      # 被补丁的宿主类
    "sync": None,       # 原始同步入队方法
    "async": None,      # 原始异步入队方法
    "wrapped": None,    # 我们贴上去的同步外壳（还原前校验）
}


def enabled(plugin: Any) -> bool:
    """开关是否打开（``plugin`` 可以是插件实例，也可以直接是配置 dict）。"""
    if isinstance(plugin, dict):
        return bool(plugin.get(CONFIG_KEY))
    return bool((getattr(plugin, "config", None) or {}).get(CONFIG_KEY))


def _wanted(plugin: Any) -> bool:
    """是否该接管：插件本身启用 **且** 开关打开（插件停用时不碰宿主）。"""
    config = plugin if isinstance(plugin, dict) else (getattr(plugin, "config", None) or {})
    return bool(config.get("enabled")) and bool(config.get(CONFIG_KEY))


def installed() -> bool:
    """当前是否已经接管了宿主入队方法。"""
    return _state["owner"] is not None


def _load_host_owner():
    """返回宿主订阅链的搜索 owner 类（宿主版本漂移时由调用方兜异常）。"""
    from app.chain.subscribe.search import SubscribeSearchOwner

    return SubscribeSearchOwner


def activate(subscribe_id: int) -> bool:
    """把新订阅状态从 ``N`` 直接写成 ``R``（**不发事件**，幂等）。

    返回是否真的改了状态。任何异常只记日志，不抛回宿主调用栈。

    :note: 写库而不是走 ``SubscribeOper.update``：后者会广播 ``subscribe.modified``，
        宿主与其它插件收到后会立刻搜这条订阅（1.13.6 的实验结果）。
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
    except Exception as err:  # pragma: no cover - 不能抛回宿主调用栈
        logger.warning(f"[TgMediaCenter] 跳过首次搜索失败（订阅 {subscribe_id}）：{err}")
        return False

    logger.info(
        f"[TgMediaCenter] 新增订阅「{name}」(ID={subscribe_id}) 已置为订阅中，"
        f"跳过宿主首次全站搜索（后续按订阅自身的搜索间隔继续）"
    )
    return True


def install(plugin: Any) -> bool:
    """按开关把守卫挂到宿主入队方法上；返回是否真的挂上。"""
    with _lock:
        _uninstall_locked()
        if not _wanted(plugin):
            logger.debug("[TgMediaCenter] 插件未启用或跳过首搜开关关闭，不接管宿主入队")
            return False
        try:
            owner = _load_host_owner()
        except Exception as err:
            logger.warning(f"[TgMediaCenter] 宿主缺少订阅搜索队列模块，跳过首次搜索不可用：{err}")
            return False

        original_sync = getattr(owner, MANGLE_SYNC, None)
        original_async = getattr(owner, MANGLE_ASYNC, None)
        if original_sync is None:
            logger.warning(
                "[TgMediaCenter] 宿主入队方法 _SubscribeChain__queue_new_subscription_search 不存在"
                "（宿主版本可能已变），跳过首次搜索不可用，宿主原有入队行为不受影响"
            )
            return False

        def guard_sync(self, subscribe_id, *args, **kwargs):
            try:
                if activate(int(subscribe_id)):
                    return None
            except Exception as err:  # pragma: no cover - 守卫失败必须放行原逻辑
                logger.warning(f"[TgMediaCenter] 跳过首次搜索守卫异常（放行宿主原逻辑）：{err}")
            return original_sync(self, subscribe_id, *args, **kwargs)

        try:
            setattr(owner, MANGLE_SYNC, guard_sync)
            if original_async is not None:
                async def guard_async(self, subscribe_id, *args, **kwargs):
                    try:
                        if activate(int(subscribe_id)):
                            return None
                    except Exception as err:  # pragma: no cover
                        logger.warning(f"[TgMediaCenter] 跳过首次搜索守卫异常（放行宿主原逻辑）：{err}")
                    return await original_async(self, subscribe_id, *args, **kwargs)

                setattr(owner, MANGLE_ASYNC, guard_async)
        except Exception as err:  # pragma: no cover - 贴补丁失败就整体回滚
            logger.warning(f"[TgMediaCenter] 接管宿主入队方法失败：{err}")
            _uninstall_locked()
            return False

        _state["owner"] = owner
        _state["sync"] = original_sync
        _state["async"] = original_async
        _state["wrapped"] = guard_sync
        logger.info(
            "[TgMediaCenter] 已接管宿主「新增订阅首次全站搜索」入队："
            f"新增订阅只置为订阅中（state=N→R{'，异步入队同步接管' if original_async else ''}），"
            "不再安排 60 秒后的全站搜索"
        )
        return True


def uninstall() -> None:
    """还原宿主入队方法（插件停用 / 重载时必须调用，绝不留补丁）。"""
    with _lock:
        _uninstall_locked()


def _uninstall_locked() -> None:
    """在锁内还原；只在当前属性确实是我们贴的外壳时才写回，避免踩到别人的补丁。"""
    owner = _state["owner"]
    original_sync = _state["sync"]
    original_async = _state["async"]
    wrapped = _state["wrapped"]
    _state["owner"] = None
    _state["sync"] = None
    _state["async"] = None
    _state["wrapped"] = None
    if owner is None:
        return
    try:
        if wrapped is not None and getattr(owner, MANGLE_SYNC, None) is wrapped:
            setattr(owner, MANGLE_SYNC, original_sync)
        if original_async is not None:
            current_async = getattr(owner, MANGLE_ASYNC, None)
            if current_async is not None and current_async is not original_async:
                setattr(owner, MANGLE_ASYNC, original_async)
    except Exception as err:  # pragma: no cover - 还原失败只影响下次 install 的幂等性
        logger.warning(f"[TgMediaCenter] 还原宿主入队方法失败：{err}")
        return
    logger.debug("[TgMediaCenter] 已还原宿主「新增订阅首次全站搜索」入队方法")


def status() -> dict:
    """当前接管状态（供日志/排障）。"""
    return {
        "installed": installed(),
        "config_key": CONFIG_KEY,
        "host_async_wrapped": _state["async"] is not None,
    }


__all__ = ["CONFIG_KEY", "activate", "enabled", "install", "installed", "status", "uninstall"]
