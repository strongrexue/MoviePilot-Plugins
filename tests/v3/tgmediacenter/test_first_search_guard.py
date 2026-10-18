"""跳过宿主「新增订阅首次全站搜索」的回归测试（1.13.8）。

这一版把实现从「监听 SubscribeAdded 事件后补救」改成「在宿主入队前拦截」，
测试因此全部围绕**补丁的接线是否正确**，而不是事件时序：

- 开关关闭 → 绝不动宿主；
- 开关打开 → 入队被拦（返回 None、宿主原方法不执行）、状态不是 N 时放行原逻辑、
    守卫自身抛异常时 fail-open 放行；
- 宿主方法缺失（升级改名）→ 降级返回 False，不留半套补丁；
- 还原后方法对象与原对象是同一个（插件停用/重载不留残留）。

宿主 `_load_host_owner()` 在测试里换成假类，因此**不需要真实宿主**也能跑。
"""
import asyncio
import types
from pathlib import Path

import pytest

from app.plugins.tgmediacenter.modules import first_search_guard as guard

MANGLE_SYNC = "_SubscribeChain__queue_new_subscription_search"
MANGLE_ASYNC = "_SubscribeChain__async_queue_new_subscription_search"

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "tgmediacenter"


class _Recorder:
    """记录「宿主原方法被调用了几次」。"""

    def __init__(self) -> None:
        self.sync_calls = []
        self.async_calls = []


def _fake_owner(recorder: _Recorder, *, with_async: bool = True):
    """造一个带宿主同款入队方法的类（方法名逐字照抄，含双下划线）。"""

    class FakeOwner:
        def _SubscribeChain__queue_new_subscription_search(self, subscribe_id, *args, **kwargs):
            recorder.sync_calls.append(int(subscribe_id))
            return f"enqueued-{subscribe_id}"

    if with_async:

        async def _async_method(self, subscribe_id, *args, **kwargs):
            recorder.async_calls.append(int(subscribe_id))
            return f"async-enqueued-{subscribe_id}"

        setattr(FakeOwner, MANGLE_ASYNC, _async_method)
    return FakeOwner


def _plugin(enabled: bool):
    """插件实例替身：只要 config 快照就够。"""
    return types.SimpleNamespace(config={"skip_first_search_enabled": enabled, "enabled": True})


@pytest.fixture(autouse=True)
def _clean_guard():
    """每个用例前后都还原，避免补丁泄漏到别的用例/别的测试文件。"""
    guard.uninstall()
    yield
    guard.uninstall()


def test_switch_off_does_not_touch_host(monkeypatch):
    """开关关闭：install 返回 False，宿主方法一个字节都不改。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    original = getattr(owner, MANGLE_SYNC)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)

    assert guard.install(_plugin(False)) is False
    assert getattr(owner, MANGLE_SYNC) is original
    assert guard.installed() is False


def test_plugin_disabled_does_not_touch_host(monkeypatch):
    """插件本身停用时，即使开关是开的也不接管（停用插件不干预宿主）。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    original = getattr(owner, MANGLE_SYNC)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)

    stub = types.SimpleNamespace(
        config={"enabled": False, "skip_first_search_enabled": True}
    )
    assert guard.install(stub) is False
    assert getattr(owner, MANGLE_SYNC) is original


def test_install_intercepts_enqueue(monkeypatch):
    """开关打开 + 订阅是 N：返回 None，宿主原入队方法不执行。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)
    monkeypatch.setattr(guard, "activate", lambda sid: True)

    assert guard.install(_plugin(True)) is True
    assert guard.installed() is True

    result = owner()._SubscribeChain__queue_new_subscription_search(42)
    assert result is None
    assert recorder.sync_calls == []


def test_non_new_subscription_passes_through(monkeypatch):
    """状态不是 N（activate 返回 False）：放行宿主原逻辑，返回值原样透出。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)
    monkeypatch.setattr(guard, "activate", lambda sid: False)

    assert guard.install(_plugin(True)) is True
    assert owner()._SubscribeChain__queue_new_subscription_search(7) == "enqueued-7"
    assert recorder.sync_calls == [7]


def test_activate_failure_fails_open(monkeypatch):
    """守卫自己抛异常：必须放行宿主原逻辑（绝不因为守卫挂掉而影响宿主）。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)

    def boom(_sid):
        raise RuntimeError("数据库暂时不可用")

    monkeypatch.setattr(guard, "activate", boom)

    assert guard.install(_plugin(True)) is True
    assert owner()._SubscribeChain__queue_new_subscription_search(9) == "enqueued-9"
    assert recorder.sync_calls == [9]


def test_async_enqueue_is_intercepted_too(monkeypatch):
    """异步创建订阅走的是另一个入队方法，同样要拦。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)
    monkeypatch.setattr(guard, "activate", lambda sid: True)

    assert guard.install(_plugin(True)) is True
    result = asyncio.run(owner()._SubscribeChain__async_queue_new_subscription_search(11))
    assert result is None
    assert recorder.async_calls == []


def test_install_twice_does_not_stack_wrappers(monkeypatch):
    """重复 install（重载插件）不能叠壳，否则原方法会被调多次。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)
    monkeypatch.setattr(guard, "activate", lambda sid: False)

    assert guard.install(_plugin(True)) is True
    assert guard.install(_plugin(True)) is True
    assert owner()._SubscribeChain__queue_new_subscription_search(5) == "enqueued-5"
    assert recorder.sync_calls == [5]


def test_uninstall_restores_original_method(monkeypatch):
    """还原后宿主方法必须是与原来同一个对象（而不是另一层外壳）。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    original = getattr(owner, MANGLE_SYNC)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)

    assert guard.install(_plugin(True)) is True
    assert getattr(owner, MANGLE_SYNC) is not original
    guard.uninstall()
    assert getattr(owner, MANGLE_SYNC) is original
    assert guard.installed() is False
    # 幂等：再还原一次不炸
    guard.uninstall()
    assert getattr(owner, MANGLE_SYNC) is original


def test_missing_host_method_degrades_without_patch(monkeypatch):
    """宿主升级改了方法名：install 返回 False，且不留下任何补丁。"""
    class OwnerWithoutQueue:
        pass

    monkeypatch.setattr(guard, "_load_host_owner", lambda: OwnerWithoutQueue)
    assert guard.install(_plugin(True)) is False
    assert guard.installed() is False
    assert not hasattr(OwnerWithoutQueue, MANGLE_SYNC)


def test_host_module_missing_degrades(monkeypatch):
    """宿主没有订阅搜索队列模块：同样只降级，不抛异常。"""
    def boom():
        raise ImportError("no module named app.chain.subscribe.search")

    monkeypatch.setattr(guard, "_load_host_owner", boom)
    assert guard.install(_plugin(True)) is False


def test_enabled_accepts_plugin_and_dict():
    """开关读取兼容插件实例与配置 dict。"""
    assert guard.enabled(_plugin(True)) is True
    assert guard.enabled(_plugin(False)) is False
    assert guard.enabled({"skip_first_search_enabled": True}) is True
    assert guard.enabled({}) is False
    assert guard.enabled(types.SimpleNamespace(config=None)) is False


def test_status_reports_install_state(monkeypatch):
    """状态查询给排障用。"""
    recorder = _Recorder()
    owner = _fake_owner(recorder)
    monkeypatch.setattr(guard, "_load_host_owner", lambda: owner)
    assert guard.status()["installed"] is False
    guard.install(_plugin(True))
    status = guard.status()
    assert status["installed"] is True
    assert status["host_async_wrapped"] is True
    assert status["config_key"] == "skip_first_search_enabled"


def test_event_handler_only_does_cache_search():
    """1.13.8 还原：SubscribeAdded 处理器只做缓存回搜，不再碰订阅状态。

    回归锁：1.13.5~1.13.7 把「跳过首搜」塞进了事件处理器（还加了
    ``_subscribe_id_of``），既无效又让两件事耦合；这里禁止它再长回去。
    """
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    start = source.index("def on_subscribe_added")
    end = source.index("def on_user_message", start)
    body = source[start:end]
    assert "first_search_guard.activate" not in body, "事件处理器不应再调用状态改写"
    assert "activate(" not in body, "事件处理器不应再改写订阅状态"
    assert "_subscribe_id_of" not in source, "该辅助方法应随 1.13.8 一起删除"


def test_lifecycle_installs_and_restores():
    """init_plugin 安装、stop_service 还原：宿主进程里不留补丁。"""
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert "first_search_guard.install(self)" in source
    stop_start = source.index("def stop_service")
    stop_body = source[stop_start:stop_start + 600]
    assert "first_search_guard.uninstall()" in stop_body
