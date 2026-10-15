"""自动封面任务（M4）单元测试：封面方案解析、目标交集、webhook 解析与防抖、服务注册。

跑法（无宿主 venv 时由 tests/v3/conftest.py 打桩）：

    python -m pytest tests/v3/embycovercenter -q
"""
import json
import sys
import types

import pytest

from app.plugins.embycovercenter import EmbyCoverCenter
from app.plugins.embycovercenter.service import cover_auto
from app.plugins.embycovercenter.service.emby_gateway import GatewayError


class _FakePlugin:
    """cover_auto 只依赖 _config / get_state / cover_engine / post_message。"""

    plugin_name = "胖虎封面中心"

    def __init__(self, config=None, data_path=None):
        self._config = dict(config or {})
        self._data_path = data_path
        self.posted = []
        self.drawn = []

    def get_state(self):
        return bool(self._config.get("enabled"))

    @property
    def config(self):
        return self._config

    def get_data_path(self):
        return self._data_path

    def post_message(self, title="", text=""):
        self.posted.append((title, text))


class _FakeEngine:
    def __init__(self):
        self.drawn = []

    def draw(self, config, assets):
        self.drawn.append((dict(config), assets))
        return "ZmFrZQ=="  # base64("fake")，base64_mime 会判定为 image/jpeg


@pytest.fixture(autouse=True)
def _clear_debounce():
    """防抖位图是模块级状态，测试间必须清理。"""
    cover_auto._WEBHOOK_LAST.clear()
    yield
    cover_auto._WEBHOOK_LAST.clear()


# --------------------------------------------------------------------------- 副标题词典


def test_english_name_for_dictionary():
    """内置中英词典命中与未命中回退。"""
    assert cover_auto.english_name_for("电影") == "Movies"
    assert cover_auto.english_name_for("4K电影") == "4K Movies"  # 键小写匹配
    assert cover_auto.english_name_for(" 剧集 ") == "TV Shows"  # 去空白
    assert cover_auto.english_name_for("我的私人片单") == ""
    assert cover_auto.english_name_for("") == ""


# --------------------------------------------------------------------------- 封面方案解析


def test_resolve_design_follows_cover_design(tmp_path):
    """未选模板预设时跟随封面设计（cover_layout + cover_config）。"""
    plugin = _FakePlugin(
        {"cover_layout": "海报墙", "cover_config": {"poster_count": 12, "title": "旧标题"}},
        data_path=tmp_path,
    )
    layout, style = cover_auto.resolve_design(plugin, plugin.config)
    assert layout == "海报墙"
    assert style == {"poster_count": 12, "title": "旧标题"}


def test_resolve_design_uses_template(tmp_path):
    """选择模板预设时读模板文件的 layout + config。"""
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "我的方案.json").write_text(
        json.dumps({"name": "我的方案", "layout": "极简", "config": {"poster_count": 8}}, ensure_ascii=False),
        encoding="utf-8",
    )
    plugin = _FakePlugin(
        {"auto_cover_template": "我的方案.json", "cover_layout": "海报墙", "cover_config": {}},
        data_path=tmp_path,
    )
    layout, style = cover_auto.resolve_design(plugin, plugin.config)
    assert layout == "极简"
    assert style == {"poster_count": 8}


def test_resolve_design_missing_template(tmp_path):
    """模板不存在时抛 ValueError（整轮任务据此终止并通知）。"""
    plugin = _FakePlugin({"auto_cover_template": "不存在.json"}, data_path=tmp_path)
    with pytest.raises(ValueError):
        cover_auto.resolve_design(plugin, plugin.config)


# --------------------------------------------------------------------------- 目标交集


def test_selected_targets_intersects_selected_servers(monkeypatch):
    """auto_cover_libraries 与 selected_servers 取交集，未知库 ID 落选。"""
    ref = object()

    def fake_resolve(server):
        assert server in ("Emby", "Jelly")
        return ref

    def fake_list_libraries(ref_arg):
        assert ref_arg is ref
        return [
            {"id": "lib1", "name": "电影"},
            {"id": "lib2", "name": "剧集"},
        ]

    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", fake_resolve)
    monkeypatch.setattr(cover_auto.emby_assets, "list_libraries", fake_list_libraries)
    plugin = _FakePlugin(
        {
            "selected_servers": ["Emby"],
            "auto_cover_libraries": {"Emby": ["lib1", "ghost"], "Jelly": ["lib1"]},
        }
    )
    targets = cover_auto.selected_targets(plugin, plugin.config)
    assert [(t["server"], t["library_id"], t["name"]) for t in targets] == [("Emby", "lib1", "电影")]


def test_selected_targets_allows_all_servers_when_unset(monkeypatch):
    """selected_servers 为空 = 全部服务器都参与。"""
    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "list_libraries",
        lambda ref: [{"id": "lib1", "name": "电影"}, {"id": "lib2", "name": "剧集"}],
    )
    plugin = _FakePlugin({"auto_cover_libraries": {"Emby": ["lib2"]}})
    targets = cover_auto.selected_targets(plugin, plugin.config)
    assert len(targets) == 1 and targets[0]["library_id"] == "lib2"


def test_selected_targets_skips_unreachable_server(monkeypatch):
    """服务器解析失败时记日志跳过，不拖垮整轮任务。"""

    def boom(server):
        raise GatewayError(f"未找到媒体服务器：{server}")

    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", boom)
    plugin = _FakePlugin({"auto_cover_libraries": {"坏服务器": ["lib1"]}})
    assert cover_auto.selected_targets(plugin, plugin.config) == []


# --------------------------------------------------------------------------- 整轮执行


def test_run_auto_cover_renders_and_notifies(monkeypatch, tmp_path):
    """整轮流程：标题=库名、副标题按 词典→库名、渲染后上传 Primary，并按通知设置推送。"""
    uploaded = []
    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "list_libraries",
        lambda ref: [{"id": "lib1", "name": "电影"}],
    )
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "fetch_assets",
        lambda ref, library_id, mode="random", poster_count=6, backdrop_count=1: {"posters": []},
    )
    monkeypatch.setattr(
        cover_auto.emby_gateway,
        "post_raw",
        lambda ref, path, data, content_type, query=None: uploaded.append((path, data, content_type)),
    )

    plugin = _FakePlugin(
        {
            "enabled": True,
            "cover_layout": "经典平铺",
            "cover_config": {"poster_count": 3},
            "assets_mode": "latest",
            "notify_on_task_finish": True,
            "auto_cover_libraries": {"Emby": ["lib1"]},
        },
        data_path=tmp_path,
    )
    engine = _FakeEngine()
    plugin.cover_engine = lambda: engine

    summary = cover_auto.run_auto_cover(plugin)

    assert summary["total"] == 1 and summary["ok"] == 1 and summary["failed"] == 0
    assert uploaded and uploaded[0][0] == "Items/lib1/Images/Primary"
    drawn_config, drawn_assets = engine.drawn[0]
    assert drawn_config["engine"] == "经典平铺"
    assert drawn_config["title"] == "电影"
    assert drawn_config["subtitle"] == "Movies"  # 内置词典命中
    assert drawn_config["poster_count"] == 3  # 封面设计 config 的数量优先
    assert drawn_assets == {"posters": []}
    assert len(plugin.posted) == 1
    title, text = plugin.posted[0]
    assert "自动封面任务" in title
    assert "成功 1" in text


def test_run_auto_cover_prefers_manual_english_name(monkeypatch, tmp_path):
    """副标题优先取 library_en_names 手填值。"""
    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "list_libraries",
        lambda ref: [{"id": "lib1", "name": "电影"}],
    )
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "fetch_assets",
        lambda ref, library_id, mode="random", poster_count=6, backdrop_count=1: {},
    )
    monkeypatch.setattr(cover_auto.emby_gateway, "post_raw", lambda *a, **k: None)

    plugin = _FakePlugin(
        {
            "cover_layout": "经典平铺",
            "cover_config": {},
            "library_en_names": {"lib1": "My Movies"},
            "auto_cover_libraries": {"Emby": ["lib1"]},
        },
        data_path=tmp_path,
    )
    engine = _FakeEngine()
    plugin.cover_engine = lambda: engine
    cover_auto.run_auto_cover(plugin)
    assert engine.drawn[0][0]["subtitle"] == "My Movies"


def test_run_auto_cover_notify_off(monkeypatch, tmp_path):
    """notify_on_task_finish 关闭时不发通知。"""
    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_auto.emby_assets, "list_libraries", lambda ref: [{"id": "lib1", "name": "电影"}]
    )
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "fetch_assets",
        lambda ref, library_id, mode="random", poster_count=6, backdrop_count=1: {},
    )
    monkeypatch.setattr(cover_auto.emby_gateway, "post_raw", lambda *a, **k: None)
    plugin = _FakePlugin(
        {
            "cover_layout": "经典平铺",
            "cover_config": {},
            "notify_on_task_finish": False,
            "auto_cover_libraries": {"Emby": ["lib1"]},
        },
        data_path=tmp_path,
    )
    plugin.cover_engine = lambda: _FakeEngine()
    summary = cover_auto.run_auto_cover(plugin)
    assert summary["total"] == 1
    assert plugin.posted == []


def test_run_auto_cover_invalid_template_notifies(monkeypatch, tmp_path):
    """封面方案（模板）无效时整轮终止并通知原因。"""
    plugin = _FakePlugin(
        {"auto_cover_template": "不存在.json", "notify_on_task_finish": True},
        data_path=tmp_path,
    )
    plugin.cover_engine = lambda: _FakeEngine()
    summary = cover_auto.run_auto_cover(plugin)
    assert summary["total"] == 0 and summary.get("error")
    assert len(plugin.posted) == 1
    title, text = plugin.posted[0]
    assert title.startswith("❌") and "执行失败" in text
    assert "模板不存在" in text  # 原因进入详情字段


# --------------------------------------------------------------------------- 入库事件


class _FakeEvent:
    def __init__(self, event_data):
        self.event_data = event_data


def _patch_webhook_chain(monkeypatch, library_id="lib1", calls=None):
    """把 resolve / ancestors / 后台刷新整条链替换为可断言的桩。"""
    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_auto,
        "_library_of_item",
        lambda ref, item_id: calls.append(("locate", item_id)) or library_id,
    )
    monkeypatch.setattr(
        cover_auto,
        "_refresh_one_quietly",
        lambda plugin, ref, server, lib: calls.append(("refresh", server, lib)),
    )


def test_webhook_triggers_refresh_for_selected_library(monkeypatch):
    """入库事件命中选中媒体库 → 后台刷新一次。"""
    calls = []
    _patch_webhook_chain(monkeypatch, calls=calls)
    plugin = _FakePlugin(
        {
            "enabled": True,
            "auto_refresh_on_webhook": True,
            "auto_cover_libraries": {"Emby": ["lib1"]},
        }
    )
    event = _FakeEvent({"event": "item.add", "Item": {"Id": "item9"}, "Server": {"Name": "Emby"}})
    plugin.plugin_name = EmbyCoverCenter.plugin_name
    cover_auto.handle_webhook(plugin, event)
    assert calls == [("locate", "item9"), ("refresh", "Emby", "lib1")]


def test_webhook_ignores_non_add_events(monkeypatch):
    """事件名不含 new / add（如移除、播放）不触发。"""
    calls = []
    monkeypatch.setattr(
        cover_auto.emby_gateway,
        "resolve",
        lambda server: calls.append(("resolve",)) or (_ for _ in ()).throw(AssertionError("不应解析服务器")),
    )
    plugin = _FakePlugin(
        {"enabled": True, "auto_refresh_on_webhook": True, "auto_cover_libraries": {"Emby": ["lib1"]}}
    )
    for event_name in ("item.removed", "playback.start", "", "userinfo"):
        cover_auto.handle_webhook(plugin, _FakeEvent({"event": event_name, "Item": {"Id": "i"}}))
    assert calls == []


def test_webhook_ignores_unselected_library_or_server(monkeypatch):
    """条目不在选中媒体库 / 服务器不在目标集时不触发。"""
    calls = []
    _patch_webhook_chain(monkeypatch, library_id="libX", calls=calls)
    plugin = _FakePlugin(
        {
            "enabled": True,
            "auto_refresh_on_webhook": True,
            "auto_cover_libraries": {"Emby": ["lib1"]},
        }
    )
    cover_auto.handle_webhook(
        plugin, _FakeEvent({"event": "item.new", "Item": {"Id": "i"}, "Server": {"Name": "Emby"}})
    )
    assert calls == [("locate", "i")]  # 定位到 libX 不在选中集，无 refresh

    calls.clear()
    cover_auto.handle_webhook(
        plugin, _FakeEvent({"event": "item.new", "Item": {"Id": "i"}, "Server": {"Name": "别的服务器"}})
    )
    assert calls == []


def test_webhook_debounces_same_library(monkeypatch):
    """同一 (服务器, 媒体库) 在防抖窗口内只触发一次。"""
    calls = []
    _patch_webhook_chain(monkeypatch, calls=calls)
    plugin = _FakePlugin(
        {
            "enabled": True,
            "auto_refresh_on_webhook": True,
            "auto_cover_libraries": {"Emby": ["lib1"]},
        }
    )
    for _ in range(5):
        cover_auto.handle_webhook(
            plugin, _FakeEvent({"event": "item.add", "Item": {"Id": "i"}, "Server": {"Name": "Emby"}})
        )
    assert calls.count(("refresh", "Emby", "lib1")) == 1


def test_webhook_gated_by_switches(monkeypatch):
    """插件停用或 auto_refresh_on_webhook 关闭时不触发。"""
    calls = []
    monkeypatch.setattr(
        cover_auto.emby_gateway,
        "resolve",
        lambda server: calls.append("resolve"),
    )
    base = {"auto_refresh_on_webhook": True, "auto_cover_libraries": {"Emby": ["lib1"]}}
    disabled = _FakePlugin({**base, "enabled": False})
    cover_auto.handle_webhook(
        disabled, _FakeEvent({"event": "item.add", "Item": {"Id": "i"}, "Server": {"Name": "Emby"}})
    )
    switch_off = _FakePlugin({**base, "enabled": True, "auto_refresh_on_webhook": False})
    cover_auto.handle_webhook(
        switch_off, _FakeEvent({"event": "item.add", "Item": {"Id": "i"}, "Server": {"Name": "Emby"}})
    )
    assert calls == []


def test_webhook_defensive_event_data_shapes(monkeypatch):
    """字段名变体（item.id / ItemId / server）与单服务器兜底都能取到。"""
    calls = []
    _patch_webhook_chain(monkeypatch, calls=calls)
    plugin = _FakePlugin(
        {
            "enabled": True,
            "auto_refresh_on_webhook": True,
            "auto_cover_libraries": {"Emby": ["lib1"]},
        }
    )
    cover_auto.handle_webhook(
        plugin, _FakeEvent({"Event": "NewLibraryItem", "item": {"id": "i2"}, "server": "Emby"})
    )
    cover_auto.handle_webhook(plugin, _FakeEvent({"event": "item.add", "ItemId": "i3"}))  # 单服务器兜底
    assert ("locate", "i2") in calls
    assert ("locate", "i3") in calls


# --------------------------------------------------------------------------- 提速：磁盘缓存与并行


def test_engine_disk_cache_avoids_redownload(tmp_path, monkeypatch):
    """素材磁盘缓存：新引擎实例（内存缓存为空）命中磁盘后不再发 HTTP。

    素材 URL 带 Emby 图片 tag（内容寻址），这是自动封面第二轮提速的根据。
    """
    import sys
    from io import BytesIO as _BytesIO

    from PIL import Image as _Image

    from app.plugins.embycovercenter.service.render_engine import PosterEngine

    buffer = _BytesIO()
    _Image.new("RGB", (4, 4), (200, 30, 30)).save(buffer, format="JPEG")
    payload = buffer.getvalue()  # 引擎下载路径拿原始字节

    calls = []

    class _Res:
        status_code = 200
        content = payload

    class _FakeHttp:
        def get_res(self, url=None, **kwargs):
            calls.append(url)
            return _Res()

    network = types.ModuleType("app.sdk.network")
    network.RequestUtils = lambda timeout=None: _FakeHttp()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.sdk.network", network)

    plugin = _FakePlugin(data_path=tmp_path)
    engine = PosterEngine(plugin)
    url = "http://emby/Items/1/Images/Primary?tag=abc"

    first = engine.download_img(url)
    assert first is not None and len(calls) == 1
    engine.download_img(url)  # 内存缓存命中
    assert len(calls) == 1

    # 新实例（内存缓存为空）→ 磁盘缓存命中，仍不发 HTTP
    engine2 = PosterEngine(plugin)
    second = engine2.download_img(url)
    assert len(calls) == 1
    assert second is not None and second.size == first.size


def test_run_auto_cover_parallel_keeps_all_results(monkeypatch, tmp_path):
    """并行执行后汇总仍完整：顺序无关、成功/失败计数正确。"""
    monkeypatch.setattr(cover_auto.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "list_libraries",
        lambda ref: [{"id": f"lib{i}", "name": f"库{i}"} for i in range(1, 7)],
    )
    monkeypatch.setattr(
        cover_auto.emby_assets,
        "fetch_assets",
        lambda ref, library_id, mode="random", poster_count=6, backdrop_count=1: {},
    )
    monkeypatch.setattr(cover_auto.emby_gateway, "post_raw", lambda *a, **k: None)

    plugin = _FakePlugin(
        {
            "cover_layout": "经典平铺",
            "cover_config": {},
            "notify_on_task_finish": False,
            "auto_cover_libraries": {"Emby": [f"lib{i}" for i in range(1, 7)]},
        },
        data_path=tmp_path,
    )
    plugin.cover_engine = lambda: _FakeEngine()
    summary = cover_auto.run_auto_cover(plugin)
    assert summary["total"] == 6 and summary["ok"] == 6 and summary["failed"] == 0
    assert {item["library"] for item in summary["items"]} == {f"库{i}" for i in range(1, 7)}


# --------------------------------------------------------------------------- 服务注册与接线


def _ensure_apscheduler_stub():
    """无宿主 venv 时给 apscheduler 打桩（get_service 依赖 CronTrigger.from_crontab）。"""
    try:
        import apscheduler.triggers.cron  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    root = types.ModuleType("apscheduler")
    triggers = types.ModuleType("apscheduler.triggers")
    cron = types.ModuleType("apscheduler.triggers.cron")

    class CronTrigger:
        @classmethod
        def from_crontab(cls, expression, timezone=None):
            fields = str(expression).split()
            if len(fields) != 5:
                raise ValueError(f"Wrong number of fields; got {len(fields)}, expected 5")
            return cls()

    cron.CronTrigger = CronTrigger
    root.triggers = triggers
    triggers.cron = cron
    sys.modules["apscheduler"] = root
    sys.modules["apscheduler.triggers"] = triggers
    sys.modules["apscheduler.triggers.cron"] = cron


def test_get_service_registers_only_when_enabled():
    """auto_cover_enabled 开启才注册定时任务；Cron 非法时降级为空。"""
    _ensure_apscheduler_stub()
    plugin = EmbyCoverCenter.__new__(EmbyCoverCenter)
    plugin._config = {"enabled": True, "auto_cover_enabled": False, "cover_cron": "0 4 * * *"}
    assert plugin.get_service() == []
    plugin._config = {"enabled": False, "auto_cover_enabled": True, "cover_cron": "0 4 * * *"}
    assert plugin.get_service() == []
    plugin._config = {"enabled": True, "auto_cover_enabled": True, "cover_cron": "0 4 * * *"}
    services = plugin.get_service()
    assert len(services) == 1
    assert services[0]["id"] == "embycovercenter_auto_cover"
    assert services[0]["func"] == plugin.run_auto_cover_job
    plugin._config = {"enabled": True, "auto_cover_enabled": True, "cover_cron": "not a cron"}
    assert plugin.get_service() == []


def test_webhook_handler_is_on_plugin_class():
    """回归锁：事件处理器必须定义在插件主类上（tgmediacenter 1.4.4 教训），
    否则宿主事件分发静默跳过、监听注册成功却永不触发。"""
    assert callable(getattr(EmbyCoverCenter, "on_webhook_message", None))


def test_get_api_registers_auto_cover_run():
    """/auto_cover/run 路由必须登记响应模型（V3 响应适配约定）。"""
    plugin = EmbyCoverCenter.__new__(EmbyCoverCenter)
    routes = {route["path"]: route for route in plugin.get_api()}
    assert "/auto_cover/run" in routes
    assert routes["/auto_cover/run"]["methods"] == ["POST"]
