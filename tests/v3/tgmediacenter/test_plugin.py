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
    assert TgMediaCenter.plugin_name == "胖虎媒体中心"
    assert TgMediaCenter.plugin_version == "1.13.24"
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
    for key in ("enabled", "pan115_enabled",
                "monitor_enabled", "cache_enabled", "forward_enabled"):
        assert key in config
    for key in ("tg_api_id", "tg_api_hash", "tg_phone", "tg_session_string",
                "tg_user_cooldown_seconds", "tg_keep_alive_seconds",
                "tg_aggregation_window_seconds"):
        assert key in config
    # 1.13.9：命中推送目标固定 115 网盘（界面不再提供选择）
    assert config["cache_destination"] == "pan115"
    assert config["tg_user_cooldown_seconds"] == 5
    # 1.13.18：发现页入口并入「启用」开关，配置里不再有独立键
    assert "discovery_page_enabled" not in config
    # 1.13.8：跳过宿主首搜是独立开关，默认关，且与「订阅回搜」开关互不依赖
    assert config["skip_first_search_enabled"] is False
    assert config["cache_subscribe_enabled"] is True


def _bare_plugin(config):
    """只带配置快照的插件实例（get_sidebar_nav 只依赖 _config，不必跑 __init__）。"""
    plugin = TgMediaCenter.__new__(TgMediaCenter)
    plugin._config = dict(config)
    return plugin


def test_sidebar_nav_follows_enabled_switch():
    """1.13.18：发现页入口跟着「启用」开关走（停用不注册，启用即注册）。"""
    assert _bare_plugin({"enabled": False}).get_sidebar_nav() == []
    assert _bare_plugin({}).get_sidebar_nav() == []
    # 旧配置里残留的 discovery_page_enabled 不再影响结果
    assert _bare_plugin({"enabled": False, "discovery_page_enabled": True}).get_sidebar_nav() == []


def test_sidebar_nav_registers_discovery_entry_when_enabled():
    """1.13.18：插件启用即注册一条「发现」分区整页入口。"""
    nav = _bare_plugin({"enabled": True}).get_sidebar_nav()
    assert isinstance(nav, list) and len(nav) == 1
    entry = nav[0]
    assert entry["nav_key"] == "main"
    assert entry["title"] == TgMediaCenter.plugin_name
    assert entry["section"] == "discovery"
    assert entry["permission"] == "discovery"
    assert entry["icon"]
    assert isinstance(entry["order"], int)
