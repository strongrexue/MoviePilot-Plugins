"""配置迁移与只读预览的回归测试（0.4.0）。

两个真机踩过的问题：

1. **改默认值对老用户无效** —— ``init_plugin`` 是「默认值 merge 存量配置」，
   用户库里存着旧值时旧值胜出。把窗口默认值从 30 改成 8 后，用户库里仍是 30。
2. **调参要靠反复真跑** —— 每次改门槛都要消耗每日额度、并在真机上来回试。
   只读预览解决这个：跑完整流程但不写、不计额度。
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402

# --------------------------------------------------------------------- 配置迁移

def test_config_version_declared_both_sides():
    """配置结构版本必须两侧都有（前端整份回写会覆盖后端值）。"""
    assert C.default_config()["config_version"] == C.CONFIG_VERSION
    frontend = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "configDefaults.js"
    )
    if frontend.exists():
        assert "config_version" in frontend.read_text(encoding="utf-8")


def test_migration_upgrades_stale_window():
    """v1 存量配置的 30 天窗口要被升级成新默认值 8。

    这是真机踩过的坑：窗口默认值改了，用户库里还是 30，白等一轮。
    """
    config, changed, changes = C.migrate_config({"tmdb_future_days": 30})
    assert changed is True
    assert config["tmdb_future_days"] == C.DEFAULT_FUTURE_DAYS == 8
    assert config["config_version"] == C.CONFIG_VERSION
    assert any("tmdb_future_days" in change for change in changes)


def test_migration_preserves_user_tuned_values():
    """迁移只动登记过的键，**不动用户自己调过的值**。

    用户把 min_popularity 手动改成 15，迁移后必须还是 15。
    """
    config, _changed, _changes = C.migrate_config({
        "tmdb_future_days": 30,
        "min_popularity": 15,
        "daily_limit": 50,
        "filter_original_language": False,
    })
    assert config["min_popularity"] == 15
    assert config["daily_limit"] == 50
    assert config["filter_original_language"] is False


def test_migration_is_idempotent():
    """重复迁移不产生变更（避免每次加载都写库）。"""
    first, changed, _ = C.migrate_config({"tmdb_future_days": 30})
    assert changed is True
    second, changed_again, _ = C.migrate_config(dict(first))
    assert changed_again is False
    assert second["tmdb_future_days"] == 8


def test_migration_marks_version_for_fresh_install():
    """全新安装（无 config_version）也要被标成当前版本。"""
    config, changed, _ = C.migrate_config(dict(C.default_config()) | {"config_version": None})
    assert config["config_version"] == C.CONFIG_VERSION


def test_migration_handles_unknown_version_gracefully():
    """脏值（字符串/负数）不应崩溃。"""
    config, _changed, _changes = C.migrate_config({"config_version": "abc"})
    assert config["config_version"] == C.CONFIG_VERSION


# --------------------------------------------------------------------- 只读预览

def test_preview_route_declared():
    """``/preview`` 路由与响应模型都要登记（插件路由不进宿主统一包装）。"""
    from subscribecenter.controller import schemas as api_schemas

    assert "/preview" in api_schemas.API_RESPONSE_MODELS


@pytest.mark.asyncio
async def test_preview_does_not_bump_daily_counter(plugin, monkeypatch):
    """**预览不消耗每日写入额度** —— 这是它能用来调参的前提。"""
    monkeypatch.setattr(plugin, "_build_sources", lambda: [])

    plugin._save_state({
        C.STATE_TODAY: __import__("datetime").date.today().isoformat(),
        C.STATE_DAILY_COUNT: 5,
    })
    before = plugin._written_today()

    await plugin.preview()

    assert plugin._written_today() == before, "预览不该累加今日写入计数"


@pytest.mark.asyncio
async def test_preview_returns_item_list(plugin, monkeypatch):
    """预览要返回候选明细（供界面列表展示）。"""
    monkeypatch.setattr(plugin, "_build_sources", lambda: [])
    result = await plugin.preview()
    assert result["skipped"] is False
    assert isinstance(result["items"], list)
    assert "summary" in result
    assert "rejections" in result


@pytest.mark.asyncio
async def test_preview_never_writes(plugin, monkeypatch):
    """预览即使 dry_run=False 也不得写入。"""
    written = []

    class _Spy:
        async def add(self, **kwargs):
            written.append(kwargs)
            return 1, "新增订阅成功"

        async def subscription_exists(self, *_a, **_k):
            return False

        async def history_exists(self, *_a, **_k):
            return False

    from subscribecenter.core.writer import SubscriptionWriter

    monkeypatch.setattr(plugin, "_writer", SubscriptionWriter(_Spy(), daily_limit=30))
    monkeypatch.setattr(plugin, "_build_sources", lambda: [])

    plugin._config["dry_run"] = False
    await plugin.preview()
    assert written == [], "预览绝不允许写订阅"


@pytest.mark.asyncio
async def test_preview_shares_lock_with_run_once(plugin):
    """预览与真实运行互斥 —— 避免同时打宿主。"""
    held = plugin._bridge._lock.acquire(blocking=False)
    assert held is True
    try:
        result = await plugin.preview()
        assert result["skipped"] is True
    finally:
        plugin._bridge._lock.release()
