"""TgMediaCenter 插件骨架与元数据测试。

使用宿主虚拟环境运行：

    ../MoviePilot/.venv/bin/python -m pytest tests/v3/tgmediacenter
"""
import re
from pathlib import Path

from app.plugins.tgmediacenter import TgMediaCenter

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "plugins.v3" / "tgmediacenter"


def test_plugin_metadata():
    """插件元数据应与 package.v3.json 保持一致。"""
    assert TgMediaCenter.plugin_name == "TG媒体中心"
    assert TgMediaCenter.plugin_version == "1.4.2"
    assert TgMediaCenter.plugin_config_prefix == "tgmediacenter_"


def test_frontend_version_matches_backend():
    """前端构建版本必须与插件版本一致。

    回归保护：联邦组件入口固定为 remoteEntry.js（无哈希）、宿主加载器也不追加缓存参数，
    因此"插件已更新但浏览器仍用旧组件"是常态。界面靠两版比对提示用户硬刷新，
    一旦两边不同步这个提示就失效了。
    """
    source = (PLUGIN_DIR / "src" / "components" / "version.js").read_text(encoding="utf-8")
    match = re.search(r"FRONTEND_VERSION\s*=\s*'([^']+)'", source)
    assert match, "未能在 version.js 中找到 FRONTEND_VERSION"
    assert match.group(1) == TgMediaCenter.plugin_version, (
        "前端 version.js 与插件 plugin_version 不一致，发版时需同步"
    )


def test_render_mode_is_vue():
    """插件使用 Vue 联邦组件渲染。"""
    assert TgMediaCenter.get_render_mode() == ("vue", "dist/assets")


def test_default_config_shape():
    """默认配置应包含六个模块开关与 P1 的 TG 凭证字段。"""
    config = TgMediaCenter.default_config()
    for key in ("enabled", "pan115_enabled", "douban_enabled",
                "monitor_enabled", "cache_enabled", "forward_enabled"):
        assert key in config
    for key in ("tg_api_id", "tg_api_hash", "tg_phone", "tg_session_string",
                "tg_user_cooldown_seconds", "tg_keep_alive_seconds",
                "tg_aggregation_window_seconds"):
        assert key in config
    assert config["cache_destination"] == "smart"
    assert config["tg_user_cooldown_seconds"] == 5
