"""TgMediaCenter 插件骨架测试。

使用宿主虚拟环境运行：

    ../MoviePilot/.venv/bin/python -m pytest tests/v3/tgmediacenter
"""
from app.plugins.tgmediacenter import TgMediaCenter


def test_plugin_metadata():
    """插件元数据应与 package.v3.json 保持一致。"""
    assert TgMediaCenter.plugin_name == "TG媒体中心"
    assert TgMediaCenter.plugin_version == "1.0.0"
    assert TgMediaCenter.plugin_config_prefix == "tgmediacenter_"


def test_render_mode_is_vue():
    """插件使用 Vue 联邦组件渲染。"""
    assert TgMediaCenter.get_render_mode() == ("vue", "dist/assets")


def test_default_config_shape():
    """默认配置应包含六个模块的开关。"""
    config = TgMediaCenter.default_config()
    for key in ("enabled", "pan115_enabled", "douban_enabled",
                "monitor_enabled", "cache_enabled", "forward_enabled"):
        assert key in config
    assert config["cache_destination"] == "smart"
    assert TgMediaCenter.get_form.__func__ is not None
