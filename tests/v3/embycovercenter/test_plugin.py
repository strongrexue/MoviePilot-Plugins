"""EmbyCoverCenter 插件骨架与元数据测试。

使用宿主虚拟环境运行：

    ../MoviePilot/.venv/bin/python -m pytest tests/v3/embycovercenter
"""
import re
from pathlib import Path

from app.plugins.embycovercenter import EmbyCoverCenter

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "plugins.v3" / "embycovercenter"


def test_plugin_metadata():
    """插件元数据应与 package.v3.json 保持一致。"""
    assert EmbyCoverCenter.plugin_name == "胖虎封面中心"
    assert EmbyCoverCenter.plugin_version == "1.4.2"
    assert EmbyCoverCenter.plugin_config_prefix == "embycovercenter_"


def test_frontend_version_matches_backend():
    """前端构建版本必须与插件版本一致。

    回归保护：联邦组件入口固定为 remoteEntry.js（无哈希）、宿主加载器也不追加缓存参数，
    因此"插件已更新但浏览器仍用旧组件"是常态。界面靠两版比对提示用户硬刷新，
    一旦两边不同步这个提示就失效了。
    """
    source = (PLUGIN_DIR / "src" / "components" / "version.js").read_text(encoding="utf-8")
    match = re.search(r"FRONTEND_VERSION\s*=\s*'([^']+)'", source)
    assert match, "未能在 version.js 中找到 FRONTEND_VERSION"
    assert match.group(1) == EmbyCoverCenter.plugin_version, (
        "前端 version.js 与插件 plugin_version 不一致，发版时需同步"
    )


def test_dist_frontend_version_matches_backend():
    """构建产物里的 FRONTEND_VERSION 必须与插件版本一致（dist 过期防护）。

    回归保护：1.4.0 发布时 dist 先于 src 版本号提升构建，产物里烤死的还是 1.3.9，
    「前端组件 vX ≠ 后端 vY」横幅硬刷新也无法消除——版本号烤在产物里，与浏览器缓存无关。
    此测试直接核对构建产物，dist 未随源码重建时发版即失败。
    """
    chunks = sorted((PLUGIN_DIR / "dist" / "assets").glob("version-*.js"))
    assert chunks, "dist/assets 下未找到 version-*.js，请先 npm run build"
    assert len(chunks) == 1, f"dist 残留多个版本 chunk（应先 clean 再构建）：{[c.name for c in chunks]}"
    content = chunks[0].read_text(encoding="utf-8")
    match = re.search(r"FRONTEND_VERSION\s*=\s*'([^']+)'", content)
    assert match, "dist 版本 chunk 中未找到 FRONTEND_VERSION"
    assert match.group(1) == EmbyCoverCenter.plugin_version, (
        "dist 构建产物版本过期（先于源码版本构建）：请重新 npm run build 再发布"
    )


def test_render_mode_is_vue():
    """插件使用 Vue 联邦组件渲染。"""
    assert EmbyCoverCenter.get_render_mode() == ("vue", "dist/assets")


def test_default_config_shape():
    """默认配置应包含开关、定时与通知字段。"""
    config = EmbyCoverCenter.default_config()
    for key in ("enabled", "discovery_page_enabled", "selected_servers",
                "auto_refresh_on_webhook", "cover_cron", "notify_on_task_finish"):
        assert key in config
    assert config["discovery_page_enabled"] is False
    assert config["cover_cron"] == "0 4 * * *"


def _bare_plugin(config):
    """只带配置快照的插件实例（get_sidebar_nav 只依赖 _config，不必跑 __init__）。"""
    plugin = EmbyCoverCenter.__new__(EmbyCoverCenter)
    plugin._config = dict(config)
    return plugin


def test_sidebar_nav_off_by_default():
    """默认不注册「发现」分区入口（关闭 / 未启用两种情形都不注册）。"""
    assert _bare_plugin({"enabled": True, "discovery_page_enabled": False}).get_sidebar_nav() == []
    assert _bare_plugin({"enabled": False, "discovery_page_enabled": True}).get_sidebar_nav() == []
    assert _bare_plugin({}).get_sidebar_nav() == []


def test_sidebar_nav_registers_discovery_entry_when_enabled():
    """启用插件并打开「发现页」开关后，注册一条「发现」分区整页入口。"""
    nav = _bare_plugin({"enabled": True, "discovery_page_enabled": True}).get_sidebar_nav()
    assert isinstance(nav, list) and len(nav) == 1
    entry = nav[0]
    assert entry["nav_key"] == "main"
    assert entry["title"] == EmbyCoverCenter.plugin_name
    assert entry["section"] == "discovery"
    assert entry["permission"] == "discovery"
    assert entry["icon"]
    assert isinstance(entry["order"], int)
