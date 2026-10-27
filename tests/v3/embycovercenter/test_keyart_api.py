"""主视觉（keyart）上传/列表/删除 + 预览副标题补齐的回归测试。"""
import base64
import io

import pytest
from PIL import Image

from app.plugins.embycovercenter.controller import api as api_controller
from app.plugins.embycovercenter.service import assets_meta


class _FakePlugin:
    def __init__(self, data_path):
        self._data_path = data_path

    def get_data_path(self):
        return self._data_path


def _png_bytes(size=(64, 36), color=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _data_url(raw: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


# ------------------------------------------------------------------ keyart 存储层


def test_ensure_dirs_creates_keyart_directory(tmp_path):
    """初始化时要顺手建好 keyart 目录，否则上传要用户手动建文件夹。"""
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    assert assets_meta.keyart_dir(plugin).is_dir()
    assert assets_meta.list_keyart(plugin) == []


def test_save_list_delete_keyart(tmp_path):
    """上传 → 列表 → 删除的完整链路。"""
    plugin = _FakePlugin(tmp_path)
    saved = assets_meta.save_keyart_base64(plugin, "国产剧.png", _data_url(_png_bytes()))
    assert saved == "国产剧.png"
    assert assets_meta.list_keyart(plugin) == ["国产剧.png"]
    assert assets_meta.keyart_path(plugin, "国产剧.png").is_file()
    assert assets_meta.delete_keyart(plugin, "国产剧.png") is True
    assert assets_meta.list_keyart(plugin) == []
    assert assets_meta.delete_keyart(plugin, "国产剧.png") is False


def test_keyart_rejects_non_image_payload(tmp_path):
    """伪造的 base64 必须被拦下，不能把垃圾写进 keyart 目录。"""
    plugin = _FakePlugin(tmp_path)
    with pytest.raises(ValueError, match="不是有效的图片"):
        assets_meta.save_keyart_base64(
            plugin, "bad.png", "data:image/png;base64," + base64.b64encode(b"not-an-image").decode()
        )
    with pytest.raises(ValueError):
        assets_meta.save_keyart_base64(plugin, "empty.png", "")


def test_keyart_rejects_bad_names_and_extensions(tmp_path):
    """路径穿越与非白名单扩展名一律拒绝。"""
    plugin = _FakePlugin(tmp_path)
    raw = _png_bytes()
    for name in ("../evil.png", "a/b.png", "a\\b.png", ".hidden.png"):
        with pytest.raises(ValueError):
            assets_meta.save_keyart(plugin, name, raw)
    with pytest.raises(ValueError):
        assets_meta.save_keyart(plugin, "evil.exe", raw)


def test_keyart_missing_file_raises(tmp_path):
    """读取不存在的主视觉时抛 ValueError（API 层转 400/404，不吞成空图）。"""
    plugin = _FakePlugin(tmp_path)
    with pytest.raises(ValueError, match="不存在"):
        assets_meta.keyart_path(plugin, "ghost.png")


# ------------------------------------------------------------------ API 层


def test_keyart_api_round_trip(tmp_path):
    """三个端点：GET 列表 / POST 上传 / POST 删除。"""
    plugin = _FakePlugin(tmp_path)
    listed = api_controller.api_keyart(plugin)
    assert listed.data.files == []

    request = api_controller.api_schemas.KeyartUploadRequest(
        name="日番.png", data=_data_url(_png_bytes())
    )
    uploaded = api_controller.api_keyart_upload(plugin, request)
    assert uploaded.data.files == ["日番.png"]

    deleted = api_controller.api_keyart_delete(
        plugin, api_controller.api_schemas.NameRequest(name="日番.png")
    )
    assert deleted.data.files == []


def test_keyart_delete_missing_returns_404(tmp_path):
    """删除不存在的主视觉返回 404，而不是静默成功。"""
    plugin = _FakePlugin(tmp_path)
    with pytest.raises(api_controller.HTTPException) as exc:
        api_controller.api_keyart_delete(
            plugin, api_controller.api_schemas.NameRequest(name="ghost.png")
        )
    assert exc.value.status_code == 404


def test_keyart_routes_are_registered():
    """路由必须登记在 get_api() 与 API_RESPONSE_MODELS 里（否则框架起不来）。"""
    from app.plugins.embycovercenter.controller import schemas

    for path in ("/keyart", "/keyart/upload", "/keyart/delete"):
        assert path in schemas.API_RESPONSE_MODELS, f"未登记响应模型：{path}"

    class _RoutePlugin:
        def __getattr__(self, item):
            if item.startswith("api_"):
                return lambda *args, **kwargs: None
            raise AttributeError(item)

    routes = {route["path"]: route for route in api_controller.get_api(_RoutePlugin())}
    assert routes["/keyart"]["methods"] == ["GET"]
    assert routes["/keyart/upload"]["methods"] == ["POST"]
    assert routes["/keyart/delete"]["methods"] == ["POST"]


# ------------------------------------------------------------------ 预览副标题


class _PreviewRequest:
    def __init__(self, **kwargs):
        self.server = ""
        self.library_id = "lib1"
        self.layout = "经典平铺"
        self.config = {}
        self.mode = "random"
        self.poster_count = 6
        self.backdrop_count = 1
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_prepare_config_fills_subtitle_from_dictionary(monkeypatch):
    """手动预览也要有副标题：手填 > 内置英文名 > 库名。

    历史行为：``_prepare_config`` 只补 title，所有布局的副标题在预览时都是空的
    （只有自动封面走 cover_auto 才有值）。
    """
    monkeypatch.setattr(api_controller, "_library_name", lambda ref, library_id: "华语电影")
    config = api_controller._prepare_config(_PreviewRequest(), object())
    assert config["title"] == "华语电影"
    assert config["subtitle"] == "Chinese Movies"


def test_prepare_config_keeps_manual_subtitle(monkeypatch):
    """用户在配置里手填的副标题不能被词典覆盖。"""
    monkeypatch.setattr(api_controller, "_library_name", lambda ref, library_id: "日番")
    config = api_controller._prepare_config(
        _PreviewRequest(config={"title": "自定标题", "subtitle": "My Subtitle"}), object()
    )
    assert config["title"] == "自定标题"
    assert config["subtitle"] == "My Subtitle"


def test_prepare_config_uses_per_library_override(monkeypatch):
    """library_en_names 里该库的手填英文名优先于内置词典。"""
    monkeypatch.setattr(api_controller, "_library_name", lambda ref, library_id: "国产剧")
    config = api_controller._prepare_config(
        _PreviewRequest(config={"library_en_names": {"lib1": "CDrama"}}), object()
    )
    assert config["subtitle"] == "CDrama"


def test_prepare_config_falls_back_to_library_name(monkeypatch):
    """词典没有的库名直接当副标题（不返回空串）。"""
    monkeypatch.setattr(api_controller, "_library_name", lambda ref, library_id: "我的私人收藏")
    config = api_controller._prepare_config(_PreviewRequest(), object())
    assert config["subtitle"] == "我的私人收藏"
