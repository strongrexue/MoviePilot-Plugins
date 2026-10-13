"""P8（1.7.0）消息交互：私聊发链接 → 转存 115 → 回执。"""
from __future__ import annotations

import inspect
import sys
import types
from typing import Any, Dict, List

import pytest

from app.plugins.tgmediacenter.modules.interactive import InteractiveModule


class FakePan115:
    """115 模块替身：只暴露交互模块用到的能力。"""

    def __init__(self, result: Dict[str, Any] | None = None,
                 raise_error: bool = False, pan115_error: str = "") -> None:
        self._result = result or {}
        self._raise = raise_error
        self._pan115_error = pan115_error
        self.calls: List[list] = []

    def push(self, links, **kwargs):
        self.calls.append(list(links))
        if self._pan115_error:
            from app.plugins.tgmediacenter.core.pan115_client import Pan115Error

            raise Pan115Error(self._pan115_error)
        if self._raise:
            raise RuntimeError("115 请求失败")
        return self._result


class FakePlugin:
    def __init__(self, config: dict | None = None, pan115: FakePan115 | None = None) -> None:
        self._config = dict(config or {})
        self._pan115 = pan115
        self.messages: list = []

    @property
    def config(self) -> dict:
        return self._config

    def post_message(self, title="", text="") -> None:
        self.messages.append({"title": title, "text": text})


class _Event:
    """宿主 UserMessage 事件替身（payload 走 event_data）。"""

    def __init__(self, data: dict) -> None:
        self.event_data = data


def _ok_result() -> Dict[str, Any]:
    return {
        "total": 1, "processed": 1, "remaining": 0, "succeeded": 1, "failed": 0,
        "skipped": 0, "batches": 1,
        "results": [{"target": "115分享:sws9cl133hx", "source": "x", "ok": True, "message": "转存成功"}],
        "message": "推送完成：成功 1",
    }


def _dup_result() -> Dict[str, Any]:
    return {
        "total": 1, "processed": 1, "remaining": 0, "succeeded": 1, "failed": 0,
        "skipped": 0, "batches": 1,
        "results": [{"target": "115分享:swabc123", "source": "x", "ok": True,
                     "message": "该分享此前已转存过（跳过）"}],
        "message": "推送完成：成功 1",
    }


def _fail_result() -> Dict[str, Any]:
    return {
        "total": 1, "processed": 1, "remaining": 0, "succeeded": 0, "failed": 1,
        "skipped": 0, "batches": 1,
        "results": [{"target": "磁力:magnet:?xt=urn:btih:abc", "source": "x", "ok": False,
                     "message": "离线下载提交失败：链接已失效"}],
        "message": "推送完成：失败 1",
    }


class TestInteractivePush:
    def test_handler_lives_on_plugin_class(self):
        """与订阅事件同款约束：处理器必须定义在插件主类上，否则宿主静默跳过。"""
        from app.plugins.tgmediacenter import TgMediaCenter

        assert inspect.isfunction(TgMediaCenter.on_user_message)
        assert TgMediaCenter.on_user_message.__qualname__ == "TgMediaCenter.on_user_message"

    def test_no_links_no_reply(self):
        """随便说一句话不能有任何回复（否则在机器人里每句话都被打扰）。"""
        plugin = FakePlugin(pan115=FakePan115())
        module = InteractiveModule(plugin)
        assert module.handle(_Event({"text": "你好，今天有什么新片吗"}) ) is None
        assert module.handle(_Event({"text": ""})) is None
        assert module.handle(_Event({})) is None
        assert plugin.messages == []
        assert plugin._pan115.calls == []

    def test_disabled_switch_skips(self):
        plugin = FakePlugin(config={"interactive_push": False}, pan115=FakePan115())
        module = InteractiveModule(plugin)
        assert module.handle(_Event({"text": "https://115.com/s/sws9cl133hx?password=v435"})) is None
        assert plugin.messages == []

    def test_success_receipt(self):
        """发链接 → 转存 → 回执说清"已提交到 115"。"""
        pan115 = FakePan115(result=_ok_result())
        plugin = FakePlugin(pan115=pan115)
        module = InteractiveModule(plugin)
        text = "希望 (2026)\nhttps://115.com/s/sws9cl133hx?password=v435"
        reply = module.handle(_Event({"text": text, "userid": "u1", "channel": "wechat"}))
        assert reply is not None
        # 整段正文传给 115（提取码常在正文里，拆成单条会丢）
        assert pan115.calls == [[text]]
        assert len(plugin.messages) == 1
        assert "链接转存回执" in plugin.messages[0]["title"]
        assert "新转存 1 条" in plugin.messages[0]["text"]
        assert "115分享:sws9cl133hx" in plugin.messages[0]["text"]

    def test_duplicate_receipt(self):
        """1.7.0：已转存过必须说清"本次未重复保存"，不能混在成功里。"""
        plugin = FakePlugin(pan115=FakePan115(result=_dup_result()))
        module = InteractiveModule(plugin)
        reply = module.handle(_Event({"text": "https://115.com/s/swabc123"}))
        assert "已转存过，本次未重复保存" in reply
        assert "新转存 0 条" in reply
        assert "已转存过 1 条" in reply

    def test_failure_receipt_has_reason(self):
        plugin = FakePlugin(pan115=FakePan115(result=_fail_result()))
        module = InteractiveModule(plugin)
        reply = module.handle(_Event({"text": "magnet:?xt=urn:btih:abc"}))
        assert "失败 1 条" in reply
        assert "失败原因：离线下载提交失败：链接已失效" in reply

    def test_pan115_error_message_relayed(self):
        """115 模块的可读错误（未登录 / CID 缺失）要原样进回执。

        1.7.0 真机事故：曾误调目标封装的 available()（Pan115Module 没有该方法，
        AttributeError 被吞）导致明明已登录却回「115 不可用，请扫码登录」。
        """
        pan115 = FakePan115(pan115_error="未登录 115：请在「账号与授权」里扫码登录")
        plugin = FakePlugin(pan115=pan115)
        module = InteractiveModule(plugin)
        reply = module.handle(_Event({"text": "https://115.com/s/swabc123"}))
        assert "115 未能转存" in reply
        assert "请在「账号与授权」里扫码登录" in reply
        assert "115 不可用" not in reply

    def test_push_exception_becomes_reply(self):
        plugin = FakePlugin(pan115=FakePan115(raise_error=True))
        module = InteractiveModule(plugin)
        reply = module.handle(_Event({"text": "https://115.com/s/swabc123"}))
        assert "115 转存失败" in reply

    def test_magnet_and_ed2k_are_supported(self):
        """磁力 / ed2k 同样能触发（转存能力后端现成）。"""
        pan115 = FakePan115(result=_ok_result())
        plugin = FakePlugin(pan115=pan115)
        module = InteractiveModule(plugin)
        assert module.handle(_Event({"text": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"})) is not None
        assert len(pan115.calls) == 1

    def test_plugin_handler_dispatches_to_module(self):
        """主类 handler 把事件交给交互模块，异常不往外抛。"""
        from app.plugins.tgmediacenter import TgMediaCenter

        plugin = FakePlugin(pan115=FakePan115(result=_ok_result()))
        plugin._interactive = InteractiveModule(plugin)
        TgMediaCenter.on_user_message(plugin, _Event({"text": "https://115.com/s/sws9cl133hx"}))
        assert len(plugin.messages) == 1


class TestUserMessageListener:
    def test_registers_and_removes_user_message_listener(self, monkeypatch):
        """宿主有 UserMessage 事件时注册，卸载时移除。"""
        from app.plugins.tgmediacenter import TgMediaCenter

        added: list = []
        removed: list = []

        class FakeEventManager:
            def add_event_listener(self, event_type, handler):
                added.append((event_type, handler))

            def remove_event_listener(self, event_type, handler):
                removed.append((event_type, handler))

        class _FakeEventType:
            UserMessage = "user.message"
            SubscribeAdded = "subscribe.added"

        events_mod = types.ModuleType("app.sdk.events")
        events_mod.eventmanager = FakeEventManager()
        types_mod = types.ModuleType("app.schemas.types")
        types_mod.EventType = _FakeEventType
        monkeypatch.setitem(sys.modules, "app.sdk.events", events_mod)
        monkeypatch.setitem(sys.modules, "app.schemas.types", types_mod)

        plugin = TgMediaCenter.__new__(TgMediaCenter)
        plugin._interactive = None
        assert plugin._install_user_message_listener() is True
        assert added == [("user.message", plugin.on_user_message)]
        plugin._uninstall_user_message_listener()
        assert removed == [("user.message", plugin.on_user_message)]

    def test_missing_event_type_degrades_silently(self, monkeypatch):
        """旧宿主没有 UserMessage 事件：静默降级，不报错。"""
        from app.plugins.tgmediacenter import TgMediaCenter

        class _FakeEventType:
            SubscribeAdded = "subscribe.added"

        events_mod = types.ModuleType("app.sdk.events")
        events_mod.eventmanager = object()
        types_mod = types.ModuleType("app.schemas.types")
        types_mod.EventType = _FakeEventType
        monkeypatch.setitem(sys.modules, "app.sdk.events", events_mod)
        monkeypatch.setitem(sys.modules, "app.schemas.types", types_mod)

        plugin = TgMediaCenter.__new__(TgMediaCenter)
        assert plugin._install_user_message_listener() is False


def test_default_config_has_switch():
    """新配置项必须有默认值（保存是整份覆盖，缺字段会被清空）。"""
    from app.plugins.tgmediacenter import TgMediaCenter

    defaults = TgMediaCenter.default_config()
    assert defaults.get("interactive_push") is True
