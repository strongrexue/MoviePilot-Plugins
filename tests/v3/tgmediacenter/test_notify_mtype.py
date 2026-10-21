"""通知类型（notify_mtype）测试：1.13.22。

覆盖：
- 常量与归一函数：默认「插件」、九类白名单原样返回、非法值回落默认；
- ``Notifier.send``：把归一后的中文名作为 ``mtype`` 传给宿主 ``post_message``；
- 兼容降级：宿主 / 替身的 ``post_message`` 不收 ``mtype`` 时仍能发出（旧行为）；
- ``CacheModule._notify``：缓存回搜通知同样带类型；
- 缺省配置（老配置里没有这个键）按「插件」处理。

宿主真实 ``post_message`` 的签名以真机为准，这里用签名不同的替身模拟两侧。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.plugins.tgmediacenter.core.notify import (
    DEFAULT_NOTIFY_MTYPE,
    NOTIFY_MTYPES,
    Notifier,
    deliver,
    notify_mtype,
)
from app.plugins.tgmediacenter.modules.cache import CacheModule


# ---------------------------------------------------------------------- 归一函数


class TestNotifyMtype:
    def test_default_is_plugin(self):
        assert DEFAULT_NOTIFY_MTYPE == "插件"
        assert "插件" in NOTIFY_MTYPES

    def test_all_host_types_are_whitelisted(self):
        # 与宿主 app.schemas.types.MessageType 的九个中文值一一对应
        assert NOTIFY_MTYPES == (
            "资源下载",
            "整理入库",
            "订阅",
            "站点",
            "媒体服务器",
            "手动处理",
            "插件",
            "智能体",
            "其它",
        )

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_falls_back_to_default(self, value):
        assert notify_mtype(value) == "插件"

    @pytest.mark.parametrize("value", list(NOTIFY_MTYPES))
    def test_whitelisted_value_kept(self, value):
        assert notify_mtype(value) == value

    @pytest.mark.parametrize("value", ["订阅提醒", "download", "插件 ", "Plugin", 123])
    def test_unknown_falls_back_to_default(self, value):
        assert notify_mtype(value) == "插件"

    def test_whitespace_is_stripped(self):
        assert notify_mtype("  订阅  ") == "订阅"


# ---------------------------------------------------------------------- 发送链路


class _PluginWithMtype:
    """宿主 3.x 风格的替身：post_message 收 mtype 关键字。"""

    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {})
        self.messages: list = []

    def post_message(self, title: str = "", text: str = "", mtype=None) -> None:
        self.messages.append({"title": title, "text": text, "mtype": mtype})


class _LegacyPlugin:
    """旧版 / 极简替身：只收 title 与 text。"""

    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {})
        self.messages: list = []

    def post_message(self, title: str = "", text: str = "") -> None:
        self.messages.append({"title": title, "text": text})


class TestNotifierMtype:
    def test_send_passes_default_mtype(self):
        plugin = _PluginWithMtype()
        assert Notifier(plugin).send("标题", "正文") is True
        assert plugin.messages == [{"title": "标题", "text": "正文", "mtype": "插件"}]

    def test_send_passes_configured_mtype(self):
        plugin = _PluginWithMtype({"notify_mtype": "订阅"})
        Notifier(plugin).send("标题", "正文")
        assert plugin.messages[0]["mtype"] == "订阅"

    def test_send_normalizes_unknown_mtype(self):
        plugin = _PluginWithMtype({"notify_mtype": "瞎写的类型"})
        Notifier(plugin).send("标题", "正文")
        assert plugin.messages[0]["mtype"] == "插件"

    def test_mtype_getter(self):
        assert Notifier(_PluginWithMtype({})).mtype() == "插件"
        assert Notifier(_PluginWithMtype({"notify_mtype": "站点"})).mtype() == "站点"
        assert Notifier(_PluginWithMtype({"notify_mtype": ""})).mtype() == "插件"

    def test_legacy_post_message_still_receives_notification(self):
        """宿主不给 mtype 形参时降级为只发标题正文，不丢通知。"""
        plugin = _LegacyPlugin({"notify_mtype": "订阅"})
        assert Notifier(plugin).send("标题", "正文") is True
        assert plugin.messages == [{"title": "标题", "text": "正文"}]

    def test_var_keyword_signature_is_treated_as_supported(self):
        class _KwargsPlugin:
            def __init__(self) -> None:
                self.config: dict = {}
                self.calls: list = []

            def post_message(self, **kwargs) -> None:
                self.calls.append(kwargs)

        plugin = _KwargsPlugin()
        Notifier(plugin).send("标题", "正文")
        assert plugin.calls == [{"title": "标题", "text": "正文", "mtype": "插件"}]

    def test_exception_is_swallowed(self):
        class _Boom:
            def __init__(self) -> None:
                self.config: dict = {}

            def post_message(self, title="", text="", mtype=None) -> None:
                raise RuntimeError("渠道炸了")

        assert Notifier(_Boom()).send("标题", "正文") is False


class TestDeliver:
    def test_deliver_with_mtype(self):
        plugin = _PluginWithMtype()
        deliver(plugin.post_message, "标题", "正文", "站点")
        assert plugin.messages == [{"title": "标题", "text": "正文", "mtype": "站点"}]

    def test_deliver_without_mtype(self):
        plugin = _LegacyPlugin()
        deliver(plugin.post_message, "标题", "正文", "站点")
        assert plugin.messages == [{"title": "标题", "text": "正文"}]

    def test_deliver_non_inspectable_callable(self):
        """签名探不到（内建 / 动态）时按不支持处理，仍尝试发送。"""
        seen: list = []

        class _Dynamic:
            def __init__(self) -> None:
                self.config: dict = {}

        plugin = _Dynamic()
        plugin.post_message = lambda **kw: seen.append(kw)  # VAR_KEYWORD → 支持
        deliver(plugin.post_message, "T", "X", "插件")
        assert seen and seen[0]["mtype"] == "插件"


# ---------------------------------------------------------------------- 缓存回搜通知


class _CachePlugin:
    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {"notify_on_search": True})
        self.messages: list = []

    def get_data(self, key, default=None):
        return default

    def save_data(self, key, value) -> None:
        pass

    def post_message(self, title: str = "", text: str = "", mtype=None) -> None:
        self.messages.append({"title": title, "text": text, "mtype": mtype})


class TestCacheNotifyMtype:
    def test_cache_notify_carries_default_mtype(self):
        plugin = _CachePlugin({"notify_on_search": True})
        CacheModule(plugin)._notify("缓存回搜", "正文")
        assert plugin.messages == [{"title": "缓存回搜", "text": "正文", "mtype": "插件"}]

    def test_cache_notify_carries_configured_mtype(self):
        plugin = _CachePlugin({"notify_on_search": True, "notify_mtype": "订阅"})
        CacheModule(plugin)._notify("缓存回搜", "正文")
        assert plugin.messages[0]["mtype"] == "订阅"

    def test_cache_notify_respects_switch(self):
        plugin = _CachePlugin({"notify_on_search": False, "notify_mtype": "订阅"})
        CacheModule(plugin)._notify("缓存回搜", "正文")
        assert plugin.messages == []

    def test_cache_notify_legacy_signature(self):
        class _LegacyCachePlugin(_CachePlugin):
            def post_message(self, title: str = "", text: str = "") -> None:
                self.messages.append({"title": title, "text": text})

        plugin = _LegacyCachePlugin({"notify_on_search": True})
        CacheModule(plugin)._notify("缓存回搜", "正文")
        assert plugin.messages == [{"title": "缓存回搜", "text": "正文"}]


# ---------------------------------------------------------------------- 默认配置


def test_default_config_has_notify_mtype():
    from app.plugins.tgmediacenter import TgMediaCenter

    assert TgMediaCenter.default_config()["notify_mtype"] == "插件"


def test_overview_exposes_notify_mtype():
    """详情页聚合里的通知块带上类型，供前端展示。"""
    from app.plugins.tgmediacenter.controller import api as controller_api

    plugin = SimpleNamespace(
        config={},
        plugin_version="1.13.22",
        get_state=lambda: True,
        get_data=lambda key, default=None: default,
        _credentials=None,
        _pan115=None,
        _cache=None,
        _monitor=None,
        _forward=None,
    )
    data = controller_api.api_overview(plugin).data
    assert data.notify.mtype == "插件"
