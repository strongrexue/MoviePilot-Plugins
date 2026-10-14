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
        self._data: dict = {}

    @property
    def config(self) -> dict:
        return self._config

    def post_message(self, title="", text="") -> None:
        self.messages.append({"title": title, "text": text})

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value


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
        # 1.7.5：改为逐条链接传给 115（剔除台账已命中链接）；提取码在解析时
        # 已并入 URL 查询参数，不会丢
        assert pan115.calls == [["https://115.com/s/sws9cl133hx?password=v435"]]
        assert len(plugin.messages) == 1
        assert "链接转存回执" in plugin.messages[0]["title"]
        assert "新转存 1 条" in plugin.messages[0]["text"]
        assert "115分享:sws9cl133hx" in plugin.messages[0]["text"]

    def test_success_receipt_media_label(self):
        """1.7.5：回执块标题带媒体名（115 分享标题，由 pan115 结果 label 提供）。"""
        url = "https://115.com/s/sws9cl133hx?password=v435"
        result = _ok_result()
        # 真实实现里 source = 传给 push 的那条链接（回填用）
        result["results"][0]["source"] = url
        result["results"][0]["label"] = "战斗之魂[Re] 绝界之空.2026.S01E02.1080p.大魔.GB"
        plugin = FakePlugin(pan115=FakePan115(result=result))
        module = InteractiveModule(plugin)
        reply = module.handle(_Event({"text": url}))
        assert "战斗之魂[Re] 绝界之空.2026.S01E02.1080p.大魔.GB" in reply
        assert "新转存 1 条" in reply
        # 台账已记录本次成功：再发同链接直接判已转存过，不再调 115
        assert len(plugin._pan115.calls) == 1
        reply2 = module.handle(_Event({"text": url}))
        assert "已转存过" in reply2
        assert "本次未重复保存" in reply2
        assert len(plugin._pan115.calls) == 1

    def test_share_password_from_body_survives_dedup_split(self):
        """1.7.5：提取码写在正文里时，逐条传链接也要带上（否则 115 要提取码）。"""
        pan115 = FakePan115(result=_ok_result())
        plugin = FakePlugin(pan115=pan115)
        module = InteractiveModule(plugin)
        text = "某剧 S01E01\nhttps://115.com/s/swbodycd\n提取码：v435"
        module.handle(_Event({"text": text}))
        assert pan115.calls == [["https://115.com/s/swbodycd?password=v435"]]

    def test_dedup_switch_off_allows_repush(self):
        """关闭「私聊转存查重」后，已转存过的链接也会再次实际转存。"""
        pan115 = FakePan115(result=_ok_result())
        plugin = FakePlugin(config={"interactive_dedup": False}, pan115=pan115)
        module = InteractiveModule(plugin)
        url = "https://115.com/s/sws9cl133hx?password=v435"
        module.handle(_Event({"text": url}))
        module.handle(_Event({"text": url}))
        assert len(pan115.calls) == 2

    def test_duplicate_receipt(self):
        """1.7.0：已转存过必须说清"本次未重复保存"，不能混在成功里。"""
        plugin = FakePlugin(pan115=FakePan115(result=_dup_result()))
        module = InteractiveModule(plugin)
        reply = module.handle(_Event({"text": "https://115.com/s/swabc123"}))
        assert "已转存过，本次未重复保存" in reply
        assert "已转存过 1 条" in reply
        # 新转存为 0 时不再列「新转存 0 条」（1.7.5：头部只列非零项）
        assert "新转存" not in reply

    def test_ledger_hit_receipt_without_115_call(self):
        """1.7.5：台账命中（此前监控/回搜转存成功过）→ 不调 115，直接回已转存过。"""
        pan115 = FakePan115(result=_ok_result())
        plugin = FakePlugin(pan115=pan115)
        module = InteractiveModule(plugin)
        from app.plugins.tgmediacenter.core import transfer_ledger

        transfer_ledger.record(plugin, [{
            "kind": "share", "code": "swalready", "url": "https://115.com/s/swalready",
            "label": "旧资源 (2025) S01E01",
        }])
        reply = module.handle(_Event({"text": "https://115.com/s/swalready"}))
        assert pan115.calls == []
        assert "旧资源 (2025) S01E01" in reply
        assert "已转存过" in reply
        assert "本次未重复保存" in reply
        assert "首次转存" in reply


class TestTransferLedger:
    def test_identity_normalization(self):
        """同一分享不同镜像/提取码视为同一条；磁力按 btih；ed2k 全链小写。"""
        from app.plugins.tgmediacenter.core import transfer_ledger

        assert (transfer_ledger.link_identity("share", code="SwAbc123")
                == transfer_ledger.link_identity("share", code="swabc123"))
        assert (transfer_ledger.link_identity("magnet",
                url="magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567&dn=x")
                == "magnet:0123456789abcdef0123456789abcdef01234567")
        lower = transfer_ledger.link_identity("ed2k", url="ed2k://|file|A.MP4|1|HASH|/")
        assert lower == "ed2k:ed2k://|file|a.mp4|1|hash|/"

    def test_record_lookup_and_prune(self):
        """记录后可查；超出容量/时效的旧条目被裁剪。"""
        import time as _time

        from app.plugins.tgmediacenter.core import transfer_ledger

        plugin = FakePlugin()
        transfer_ledger.record(plugin, [
            {"kind": "share", "code": "swA", "url": "https://115.com/s/swa", "label": "剧A"},
            {"kind": "ed2k", "url": "ed2k://|file|B.MP4|1|H|/", "label": "剧B"},
        ])
        hits = transfer_ledger.lookup(plugin, [
            transfer_ledger.link_identity("share", code="swa"),
            transfer_ledger.link_identity("ed2k", url="ed2k://|file|b.mp4|1|h|/"),
        ])
        assert len(hits) == 2
        labels = {hit["label"] for hit in hits.values()}
        assert labels == {"剧A", "剧B"}
        # 重复记录不新增
        assert transfer_ledger.record(plugin, [
            {"kind": "share", "code": "swa", "label": "剧A"},
        ]) == 0
        # 过期条目被裁剪
        data = plugin.get_data("pan115_transfer_ledger_v1")
        key = next(iter(data))
        data[key]["ts"] = _time.time() - 91 * 86400
        plugin.save_data("pan115_transfer_ledger_v1", data)
        plugin._data["pan115_transfer_ledger_v1"] = transfer_ledger._prune(
            plugin.get_data("pan115_transfer_ledger_v1")
        )
        assert len(plugin.get_data("pan115_transfer_ledger_v1")) == 1

    def test_ed2k_and_magnet_labels(self):
        """eD2k / 磁力从链接本身取文件名；describe 不再出现双前缀。"""
        from app.plugins.tgmediacenter.core import links as link_utils

        ed2k = ("ed2k://|file|幻想水浒传.2026.S01E02.第2集.1080p.Baha.WEB-DL.H.264.AAC.mp4"
                "|2545.64 MB|509225597|a49aaa3271f6971bf692a1bf51333b52|/")
        items = link_utils.make_items([ed2k])
        desc = items[0].describe()
        # 文件名直接展示（超长截断），不再出现「ed2k:ed2k://」双前缀
        assert desc.startswith("ed2k:幻想水浒传.2026.S01E02")
        assert not desc.startswith("ed2k:ed2k")
        assert desc.endswith("…")
        magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=%E5%89%A7A"
        items = link_utils.make_items([magnet])
        assert items[0].describe() == "磁力:剧A"
        bare = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
        items = link_utils.make_items([bare])
        assert items[0].describe() == "磁力:btih:0123456789ab"

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
