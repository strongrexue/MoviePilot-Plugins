"""插件主类与宿主契约的回归测试。

覆盖开发文档里几条「照抄 V2 就会失败」的契约，以及配置一致性与路由声明。
"""
import asyncio
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from controller import schemas as api_schemas  # noqa: E402
from core import constants as C  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------- 元数据

def test_plugin_id_matches_directory_and_config_prefix():
    """插件 ID / 目录名 / 配置前缀必须彼此一致。"""
    assert C.PLUGIN_ID == "SubscribeCenter"
    assert C.PLUGIN_ID.casefold() == PLUGIN_ID
    assert C.PLUGIN_CONFIG_PREFIX == f"{PLUGIN_ID}_"


def test_plugin_metadata_available(plugin_cls):
    """主类元数据齐全。"""
    assert plugin_cls.plugin_name == "胖虎订阅中心"
    assert plugin_cls.plugin_version == C.PLUGIN_VERSION
    assert plugin_cls.plugin_author
    assert plugin_cls.plugin_icon.startswith("https://")
    # 图标必须是完整 URL：裸文件名会走到宿主本地 /plugin_icon/<name> 并 404
    assert plugin_cls.plugin_color.startswith("#")


def test_plugin_version_is_class_level_literal(plugin_cls):
    """``plugin_version`` 必须是**类级字符串字面量**。

    发布门禁 ``.github/scripts/check_plugin_versions.py`` 用 AST 从类体里提取它，
    写成 ``C.PLUGIN_VERSION`` 这类引用会让门禁取不到值、直接发布失败。
    """
    import ast

    init_file = REPO_ROOT / "plugins.v3" / PLUGIN_ID / "__init__.py"
    tree = ast.parse(init_file.read_text(encoding="utf-8"))
    found = None
    for class_node in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for node in class_node.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "plugin_version" for t in node.targets
            ):
                found = node.value
    assert found is not None, "未在类体中找到 plugin_version 赋值"
    assert isinstance(found, ast.Constant) and isinstance(found.value, str), (
        "plugin_version 必须是字符串字面量，否则发布门禁无法提取"
    )
    assert found.value == C.PLUGIN_VERSION


# --------------------------------------------------------------------- 宿主契约

def test_render_mode_returns_tuple(plugin_cls):
    """**get_render_mode 必须返回元组** ``("vue", "dist/assets")``。

    只返回 ``"vue"`` 是原开发文档的错误，会让宿主找不到 ``remoteEntry.js``。
    """
    result = plugin_cls.get_render_mode()
    assert isinstance(result, tuple)
    assert result == ("vue", "dist/assets")


def test_vue_render_mode_requires_built_entry(plugin_cls):
    """声明 vue 渲染模式时，**dist 产物必须存在**。

    这是 0.1.0 真实事故的回归锁：只有后端、没有 dist 时，宿主去加载
    ``dist/assets/remoteEntry.js`` 会 404，插件配置页是空的 ——
    启用开关和保存按钮都不存在，用户根本无法保存配置，插件永远不会启用、
    也永远不会注册定时任务。
    """
    entry = REPO_ROOT / "plugins.v3" / PLUGIN_ID / "dist" / "assets" / "remoteEntry.js"
    assert entry.exists(), (
        "get_render_mode() 声明了 vue，但 dist/assets/remoteEntry.js 不存在；"
        "必须先在插件目录执行 npm run build 并提交 dist/"
    )
    assert entry.stat().st_size > 0


def test_dist_exposes_all_four_modules(plugin_cls):
    """remoteEntry.js 必须真的暴露四个约定入口（配置 / 详情 / 仪表盘 / 发现页）。"""
    entry = REPO_ROOT / "plugins.v3" / PLUGIN_ID / "dist" / "assets" / "remoteEntry.js"
    if not entry.exists():
        pytest.skip("dist 尚未构建")
    text = entry.read_text(encoding="utf-8")
    for name in ("Config", "Page", "Dashboard", "AppPage"):
        assert f"./{name}" in text, f"remoteEntry.js 未暴露 ./{name}"


def test_dist_embeds_matching_frontend_version(plugin_cls):
    """已构建产物里的版本号必须与后端一致（防 dist 过期仍指向旧组件）。"""
    assets = REPO_ROOT / "plugins.v3" / PLUGIN_ID / "dist" / "assets"
    if not assets.exists():
        pytest.skip("dist 尚未构建")
    version = plugin_cls.plugin_version
    found = any(
        f"'{version}'" in path.read_text(encoding="utf-8") for path in assets.glob("*.js")
    )
    assert found, f"dist 产物里没有版本号 {version}，dist 可能过期（需重新 npm run build）"


def test_get_form_and_page_are_vue_mode(plugin):
    """Vue 模式下表单为 ``None``、详情页为 ``None``，只提供默认配置模型。"""
    form, default = plugin.get_form()
    assert form is None
    assert isinstance(default, dict) and default
    assert plugin.get_page() is None


def test_get_state_follows_enabled_flag(plugin_cls):
    """``get_state()`` 反映 ``enabled`` 配置。"""
    instance = plugin_cls()
    instance.init_plugin({"enabled": False})
    assert instance.get_state() is False
    instance.init_plugin({"enabled": True})
    assert instance.get_state() is True


def test_init_plugin_is_repeatable(plugin_cls):
    """``init_plugin`` 必须允许重复调用且不残留状态。"""
    instance = plugin_cls()
    instance.init_plugin({"enabled": True, "daily_limit": 10})
    instance.init_plugin({"enabled": True, "daily_limit": 20})
    instance.stop_service()
    assert instance.config["daily_limit"] == 20


# --------------------------------------------------------------------- 侧栏入口

def test_sidebar_nav_follows_plugin_enabled(plugin_cls):
    """「发现页」入口只看插件总开关（1.9.8 起合并，不再单独配置）。"""
    disabled = plugin_cls()
    disabled.init_plugin({"enabled": False})
    assert disabled.get_sidebar_nav() == []

    enabled = plugin_cls()
    enabled.init_plugin({"enabled": True})
    nav = enabled.get_sidebar_nav()
    assert len(nav) == 1
    assert nav[0]["nav_key"] == "main"
    assert nav[0]["section"] == "discovery"


# --------------------------------------------------------------------- 定时服务

def test_get_service_empty_when_disabled(plugin_cls):
    """插件未启用时不注册定时任务。"""
    instance = plugin_cls()
    instance.init_plugin({"enabled": False})
    assert instance.get_service() == []


def test_get_service_registers_cron_when_enabled(plugin_cls):
    """启用时注册一个 cron 任务，且 ``func`` 必须是同步可调用。"""
    instance = plugin_cls()
    instance.init_plugin({"enabled": True, "cron": "0 3 * * *"})
    services = instance.get_service()
    assert len(services) == 1
    service = services[0]
    assert service["id"] == "subscribecenter_discover"
    assert callable(service["func"])
    # apscheduler 会在自己的线程里调用，因此不能是协程函数
    assert not _is_coroutine_function(service["func"])
    assert service["trigger"] is not None


def test_get_service_stays_empty_on_broken_cron(plugin_cls):
    """非法 cron 不得让整个 ``get_service()`` 抛异常（会拖垮插件加载）。"""
    instance = plugin_cls()
    instance.init_plugin({"enabled": True, "cron": "not a cron"})
    services = instance.get_service()
    assert len(services) == 1  # 已回落默认 cron，而不是抛错


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0 3 * * *", "0 3 * * *"),
        ("*/30 * * * *", "*/30 * * * *"),
        ("", C.DEFAULT_CRON),
        (None, C.DEFAULT_CRON),
        ("bad", C.DEFAULT_CRON),
        ("a b c", C.DEFAULT_CRON),
    ],
)
def test_normalize_cron(plugin_cls, raw, expected):
    """cron 合法则保留，非法回落默认。"""
    assert plugin_cls._normalize_cron(raw) == expected


def _is_coroutine_function(func) -> bool:
    """判断可调用对象是否是协程函数。"""
    import inspect

    return inspect.iscoroutinefunction(getattr(func, "__func__", func))


# --------------------------------------------------------------------- API 路由

def test_api_routes_declared_with_bare_paths(plugin_cls):
    """路由声明用**裸路径**（宿主补 ``/api/v1/plugin/<ID>``），鉴权为 bear。"""
    from app.schemas import Response

    instance = plugin_cls()
    instance.init_plugin({})
    routes = instance.get_api()
    paths = {route["path"] for route in routes}
    assert paths == {
        "/status",
        "/history",
        "/history/clear",
        "/history/subscribe",
        "/calendar",
        "/calendar/day",
        "/auto_toggle",
        "/auto_toggle/apply",
        "/blacklist",
        "/blacklist/test",
        "/blacklist/audit",
        "/blacklist/audit/result",
        "/blacklist/sweep",
        "/card_theme",
        "/card_theme/save",
        "/run_once",
        "/run_once/result",
        "/preview",
        "/preview/result",
        "/system_share",
        "/system_share/save",
        "/mapping_cache",
        "/mapping_cache/fix",
        # 海报代理：浏览器直连 image.tmdb.org 在国内网络下常常不可用
        "/poster",
    }
    for route in routes:
        assert route["path"].startswith("/")
        assert route["auth"] == "bear"
        assert callable(route["endpoint"])
        if route["path"] == "/poster":
            # 图片代理直接返回字节流，不能套 JSON envelope 模型
            assert route["response_model"] is None
            continue
        # 插件路由不进入宿主统一包装，必须自己声明一致的响应模型
        model = route["response_model"]
        assert model is not None
        metadata = getattr(model, "__pydantic_generic_metadata__", {}) or {}
        assert metadata.get("origin") is Response


def test_every_route_has_a_response_model():
    """路由与响应模型映射不得有缺口。

    **新增路由必须同时加到这里和 ``API_RESPONSE_MODELS``** —— 这张表就是
    「谁忘了配响应模型」的清单，也是唯一不依赖插件实例就能跑的哨兵。
    """
    declared = {
        "/status",
        "/history",
        "/history/clear",
        "/history/subscribe",
        "/calendar",
        "/calendar/day",
        "/auto_toggle",
        "/auto_toggle/apply",
        "/blacklist",
        "/blacklist/test",
        "/blacklist/audit",
        "/blacklist/audit/result",
        "/blacklist/sweep",
        "/card_theme",
        "/card_theme/save",
        "/run_once",
        "/run_once/result",
        "/preview",
        "/preview/result",
        "/system_share",
        "/system_share/save",
        "/mapping_cache",
        "/mapping_cache/fix",
    }
    assert declared == set(api_schemas.API_RESPONSE_MODELS)


def test_api_endpoints_are_async(plugin_cls):
    """API 端点在 FastAPI 里运行，应为协程函数（可与流水线共用业务协程）。"""
    import inspect

    instance = plugin_cls()
    for route in instance.get_api():
        assert inspect.iscoroutinefunction(route["endpoint"]), route["path"]


def test_post_endpoints_annotate_request_body_with_model(plugin_cls):
    """POST 端点的请求体必须注解成**具体 pydantic 模型**，不能是 ``Any``。

    FastAPI 按端点签名决定要不要解析 JSON body：注解写 ``Any`` 时整个 body
    会原样以 ``dict`` 传进来，端点里 ``request.title`` 立刻 AttributeError ——
    1.14.0 真机点「自测」报「黑名单自测失败」就是这条（同时中招的还有
    「数据共享」开关和流水的「重新订阅」按钮）。
    """
    import inspect

    from pydantic import BaseModel

    instance = plugin_cls()
    for route in instance.get_api():
        if "POST" not in route["methods"]:
            continue
        for name, param in inspect.signature(route["endpoint"]).parameters.items():
            if param.default is not inspect.Parameter.empty:
                # 有默认值的都是可选查询参数（如 /run_once?source=）
                continue
            annotation = param.annotation
            assert annotation is not inspect.Parameter.empty, (
                f"{route['path']} 的 {name} 缺少类型注解"
            )
            assert isinstance(annotation, type) and issubclass(annotation, BaseModel), (
                f"{route['path']} 的 {name} 必须是 pydantic 模型，实际是 {annotation}"
            )


def test_blacklist_test_endpoint_tolerates_dict_body(plugin):
    """真机回归：1.14.0 的「自测」500 是端点拿到 dict 而不是模型。"""
    import asyncio

    from controller import api as api_controller

    response = asyncio.run(
        api_controller.api_blacklist_test(
            plugin, {"title": "以你的心诠释我的爱", "media_type": "tv"}
        )
    )
    assert response.success is True
    assert response.data.matched is False

    plugin._config.update({"blacklist_enabled": True, "blacklist_words": "同性"})
    hit = asyncio.run(
        api_controller.api_blacklist_test(
            plugin, {"title": "以你的心诠释我的爱", "tags": "2026 / 泰国 / 剧情 同性"}
        )
    )
    assert hit.data.matched is True
    assert "同性" in hit.data.reason


def test_blacklist_test_uses_unsaved_form_rules(plugin):
    """自测必须认页面上**还没保存**的规则（勾完预设不点保存也能测出结果）。"""
    import asyncio

    from controller import api as api_controller

    response = asyncio.run(
        api_controller.api_blacklist_test(
            plugin,
            {
                "title": "以你的心诠释我的爱",
                "tags": "2026 / 泰国 / 剧情 同性",
                "rules": {"blacklist_enabled": True, "blacklist_presets": ["lgbt"]},
            },
        )
    )
    assert response.data.matched is True
    assert response.data.rules >= 1


def test_blacklist_test_hints_why_title_only_misses(plugin):
    """只有片名、没填题材串时，必须说明「测不出同性」的原因。

    否则用户拿《以你的心诠释我的爱》点自测，看到「不会被拦」只会觉得功能坏了
    —— 而真相是题材信息在豆瓣的题材串里，标题本来就没有那个词。
    """
    import asyncio

    from controller import api as api_controller

    response = asyncio.run(
        api_controller.api_blacklist_test(
            plugin,
            {
                "title": "以你的心诠释我的爱",
                "rules": {"blacklist_enabled": True, "blacklist_presets": ["lgbt"]},
            },
        )
    )
    assert response.data.matched is False
    assert "题材串" in response.data.hint


# --------------------------------------------------------------------- 状态接口

def test_status_snapshot_shape(plugin):
    """状态接口字段齐全，且未运行时也不崩。"""
    status = plugin.status_snapshot()
    assert status.plugin_version == C.PLUGIN_VERSION
    assert status.timezone == C.DEFAULT_TIMEZONE
    assert status.daily_limit == C.DEFAULT_DAILY_LIMIT
    # 已取消「首次试运行」，恒为已完成
    assert status.first_run_completed is True
    assert status.written_today == 0
    assert len(status.sources) == len(C.ALL_SOURCES)
    assert {s.source for s in status.sources} == set(C.ALL_SOURCES)


def test_status_marks_unimplemented_sources(plugin):
    """未实现的源要被明确标注，避免用户以为开了就在工作。"""
    status = plugin.status_snapshot()
    implemented = {s.source for s in status.sources if s.implemented}
    assert implemented == set(C.IMPLEMENTED_SOURCES)


def test_enabled_sources_skips_unimplemented(plugin):
    """配置里启用但未实现的源不会进入本次运行。"""
    plugin._config.update(
        {
            "enable_tmdb": True,
            "enable_anilist": True,
            "enable_douban_rss": True,
            "enable_simkl": True,
        }
    )
    # TMDB / AniList / 豆瓣 RSS 已实现；Simkl / JustWatch 尚未实现会被跳过
    # （Bangumi 已降级为标题翻译层，不再作为发现源）
    assert plugin._enabled_sources() == [
        C.SOURCE_TMDB,
        C.SOURCE_ANILIST,
        C.SOURCE_DOUBAN_RSS,
    ]


def test_enabled_sources_respects_switches(plugin):
    """开关关闭的源不进入运行。"""
    plugin._config["enable_tmdb"] = False
    # AniList 现在默认开（番剧+国漫），要一起关掉才是「全关」语义
    plugin._config["enable_anilist"] = False
    plugin._config["enable_douban_rss"] = False
    assert plugin._enabled_sources() == []


# --------------------------------------------------------------------- 流水接口

def test_history_page_filters_and_paginates(plugin):
    """流水支持决策/来源/关键词筛选与分页。"""
    plugin.save_data(
        "run_history",
        [
            {"decision": C.DECISION_ADDED, "source": "tmdb", "title": "沙丘", "reason": ""},
            {"decision": C.DECISION_PENDING_REVIEW, "source": "anilist", "title": "巨人",
             "reason": "无确定性身份"},
            {"decision": C.DECISION_PENDING_REVIEW, "source": "tmdb", "title": "沙丘2",
             "reason": "无确定性身份"},
        ],
    )
    assert plugin.history_page().total == 3
    assert plugin.history_page(decision=C.DECISION_PENDING_REVIEW).total == 2
    assert plugin.history_page(source="tmdb").total == 2
    assert plugin.history_page(keyword="巨人").total == 1
    page = plugin.history_page(page=1, count=2)
    assert len(page.items) == 2 and page.total == 3


def test_mapping_fix_and_view(plugin):
    """人工修正映射可写可查；非法身份被拒。"""
    assert plugin.mapping_cache_view().size == 0
    ok = plugin.mapping_fix(key="t:movie:2026:沙丘", media_source="themoviedb", media_id="693134")
    assert ok["success"] is True
    view = plugin.mapping_cache_view()
    assert view.size == 1
    assert view.entries[0].media_id == "693134"

    bad = plugin.mapping_fix(key="t:movie:2026:坏数据", media_source="themoviedb", media_id="0")
    assert bad["success"] is False


def test_daily_counter_resets_across_days(plugin):
    """跨日后今日写入计数归零。"""
    plugin._save_state({C.STATE_TODAY: "1999-01-01", C.STATE_DAILY_COUNT: 25})
    assert plugin._written_today() == 0

    plugin._bump_daily_counter()
    assert plugin._written_today() == 1
    plugin._bump_daily_counter()
    assert plugin._written_today() == 2



@pytest.mark.asyncio
async def test_run_once_skips_when_busy(plugin):
    """已有流水线在跑时返回 ``skipped=True``，不并发。"""
    held = plugin._bridge._lock.acquire(blocking=False)
    assert held is True
    try:
        result = await plugin.run_once()
        assert result["skipped"] is True
    finally:
        plugin._bridge._lock.release()


@pytest.mark.asyncio
async def test_start_preview_returns_before_pipeline_finishes(plugin, monkeypatch):
    """预览只「启动」就返回，结果靠轮询 —— 同步等会被网关断成 HTTP 502。

    真机（2026-10-22）：「请求被网关中断（HTTP 502）·发现任务可能仍在后台运行」。
    """
    import asyncio

    async def fake_job():
        await asyncio.sleep(0.05)
        return {"items": [{"title": "x"}], "summary": {"fetched": 1}, "rejections": {}}

    monkeypatch.setattr(plugin, "_preview_job", fake_job)
    state = plugin.start_preview()
    assert state["started"] is True
    assert state["running"] is True

    for _ in range(200):
        await asyncio.sleep(0.02)
        if not plugin.preview_state()["running"]:
            break
    done = plugin.preview_state()
    assert done["running"] is False
    assert done["result"]["items"] == [{"title": "x"}]
    assert done["error"] == ""


def test_start_preview_refuses_when_discovery_busy(plugin):
    """发现任务在跑时不抢锁，只回报「未启动」而不是干等。"""
    held = plugin._bridge._lock.acquire(blocking=False)
    assert held is True
    try:
        state = plugin.start_preview()
        assert state["started"] is False
        assert "已有发现任务正在运行" in state["message"]
    finally:
        plugin._bridge._lock.release()


def test_scheduled_entry_is_sync_and_respects_enabled(plugin, monkeypatch):
    """调度入口是同步方法；未启用时直接返回、不跑流水线。"""
    calls = []
    monkeypatch.setattr(plugin, "_pipeline_coroutine", lambda: calls.append(1))
    plugin._config["enabled"] = False
    plugin.run_scheduled()
    assert calls == []


# --------------------------------------------------------------------- 流水去重

def test_recorded_keys_only_counts_real_writes(plugin):
    """只有「真订上了」的记录才算数。

    「待确认」「窗口外」「评分不足」这些都没动过手，不能让它们永久拦着 ——
    否则一部片在窗口外被扫到一次，就再也订不上了。
    """
    plugin.save_data(
        "run_history",
        [
            {"decision": C.DECISION_ADDED, "media_source": "themoviedb",
             "media_id": "1", "season": 1, "title": "订上了"},
            {"decision": C.DECISION_SKIPPED_ALREADY_SUBSCRIBED, "media_source": "themoviedb",
             "media_id": "2", "season": 0, "title": "本来就订着"},
            {"decision": C.DECISION_PENDING_REVIEW, "media_source": "themoviedb",
             "media_id": "3", "season": 0, "title": "待确认"},
            {"decision": C.DECISION_SKIPPED_OUT_OF_WINDOW, "media_source": "themoviedb",
             "media_id": "4", "season": 0, "title": "窗口外"},
            {"decision": C.DECISION_ADDED, "media_source": "", "media_id": "",
             "season": 0, "title": "没有身份"},
        ],
    )
    assert plugin._recorded_keys() == {"themoviedb:1:1", "themoviedb:2:0"}


def test_clear_history_unlocks_recorded(plugin):
    """清空流水 = 解锁：之前订过的不再被拦。"""
    plugin.save_data(
        "run_history",
        [{"decision": C.DECISION_ADDED, "media_source": "themoviedb",
          "media_id": "1", "season": 1, "title": "订上了"}],
    )
    assert plugin._recorded_keys() == {"themoviedb:1:1"}

    result = plugin.clear_history()
    assert result.removed == 1
    assert plugin._recorded_keys() == set()
    assert plugin.history_page().total == 0


def test_clear_history_on_empty_history_is_harmless(plugin):
    """没有流水时点「清空」不能报错。"""
    result = plugin.clear_history()
    assert result.removed == 0 and result.remaining == 0


def _outcome(media_id: str, season: int, decision: str, title: str = "某剧"):
    """造一条落流水的写入结果（只需要身份与决策）。"""
    from core.model import DiscoveredItem, ResolvedIdentity
    from core.writer import WriteOutcome

    item = DiscoveredItem(
        source="tmdb",
        source_id="1",
        title=title,
        media_type=C.MEDIA_TYPE_TV,
        season=season,
        resolved=ResolvedIdentity(media_source="themoviedb", media_id=media_id),
    )
    return WriteOutcome(item=item, decision=decision, success=decision == C.DECISION_ADDED)


def test_recorded_keys_survive_decision_changes(plugin):
    """「订过」的证据不能因为后来的「流水已记录」而丢失。

    真机事故：第一轮 `added` 记进流水；从第二轮起同一部作品每轮都被判
    `skipped_recorded`，而流水同一作品只留最新一条 → `added` 那条被替换掉。
    用户删掉订阅后再跑，去重证据已经没了，于是被重新自动订阅（1.14.5 修）。
    """
    plugin._append_history([_outcome("7", 1, C.DECISION_ADDED)], run_at="2026-10-01 05:00:00")
    assert "themoviedb:7:1" in plugin._recorded_keys()

    # 之后的运行把它记成「流水已记录」，流水里只剩这一条
    plugin._append_history(
        [_outcome("7", 1, C.DECISION_SKIPPED_RECORDED)], run_at="2026-10-02 05:00:00"
    )
    assert plugin.history_page().total == 1
    assert plugin._recorded_keys() >= {"themoviedb:7:1"}


def test_recorded_keys_ignores_history_truncation(plugin):
    """流水被 MAX_HISTORY 截断也不能丢「订过」的证据。"""
    plugin._append_history([_outcome("8", 2, C.DECISION_ADDED)], run_at="2026-10-01 05:00:00")
    # 模拟流水被后来的记录挤掉
    plugin.save_data("run_history", [])
    assert "themoviedb:8:2" in plugin._recorded_keys()


def test_clear_history_clears_recorded_store(plugin):
    """清空流水必须同时清去重表，否则界面空了却依然订不上。"""
    plugin._append_history([_outcome("9", 1, C.DECISION_ADDED)], run_at="2026-10-01 05:00:00")
    assert plugin._recorded_keys() == {"themoviedb:9:1"}

    plugin.clear_history()
    assert plugin._recorded_keys() == set()


def test_second_run_skips_after_user_deleted_subscription(plugin):
    """端到端复刻用户场景：订上 → 用户删掉订阅 → 下一轮不能再自动订回来。

    这条把「插件去重表」和「writer 的查重」接在一起跑：第一轮真写入并把键记进
    去重表，第二轮宿主说「订阅不存在」也不算数，必须判成 skipped_recorded。
    """
    from core.writer import SubscriptionWriter

    class Backend:
        def __init__(self):
            self.adds = 0

        async def subscription_exists(self, media_source, media_id, season=None):
            # 用户已经把订阅删了
            return False

        async def history_exists(self, media_source, media_id, season=None):
            return False

        async def add(self, *args, **kwargs):
            self.adds += 1
            return 42, "新增订阅"

    backend = Backend()
    writer = SubscriptionWriter(
        backend, daily_limit=0, dedupe_history=True, recorded_keys=plugin._recorded_keys
    )
    from core.model import DiscoveredItem, ResolvedIdentity

    item = DiscoveredItem(
        source="tmdb",
        source_id="298546",
        title="新手上路",
        media_type=C.MEDIA_TYPE_TV,
        season=1,
        resolved=ResolvedIdentity(media_source="themoviedb", media_id="298546"),
    )
    first = asyncio.run(writer.write([item], dry_run=False)).outcomes
    assert first[0].decision == C.DECISION_ADDED and backend.adds == 1
    plugin._append_history(first, run_at="2026-10-25 05:00:00")

    # 第二轮：宿主那边已经没有这条订阅了
    second = asyncio.run(writer.write([item], dry_run=False)).outcomes
    assert second[0].decision == C.DECISION_SKIPPED_RECORDED
    assert backend.adds == 1, "删掉订阅后又被订回来了"


# --------------------------------------------------------------------- 配置一致性

def test_default_config_key_set_matches_frontend(plugin_cls):
    """后端 ``default_config()`` 键集合必须与前端 ``configDefaults.js`` 严格一致。

    宿主 ``update_config()`` 是**整份覆盖**：任一侧多/少一个键，
    保存配置时都会被静默清掉。本仓库已有插件为此踩过两次真实事故。
    """
    frontend = REPO_ROOT / "plugins.v3" / PLUGIN_ID / "src" / "components" / "configDefaults.js"
    if not frontend.exists():
        pytest.skip("前端 configDefaults.js 尚未实现（P3 阶段补）")

    backend_keys = set(plugin_cls.default_config())
    frontend_keys = _extract_frontend_keys(frontend.read_text(encoding="utf-8"))
    assert frontend_keys, "未能从 configDefaults.js 解析出任何键"
    assert backend_keys == frontend_keys, (
        f"配置键不一致：后端多 {sorted(backend_keys - frontend_keys)} / "
        f"前端多 {sorted(frontend_keys - backend_keys)}"
    )


def test_frontend_version_matches_backend(plugin_cls):
    """前端 ``FRONTEND_VERSION`` 必须与后端 ``plugin_version`` 一致。"""
    version_file = REPO_ROOT / "plugins.v3" / PLUGIN_ID / "src" / "components" / "version.js"
    if not version_file.exists():
        pytest.skip("前端 version.js 尚未实现（P3 阶段补）")

    import re

    match = re.search(r"FRONTEND_VERSION\s*=\s*'([^']+)'", version_file.read_text(encoding="utf-8"))
    assert match, "version.js 中未找到 FRONTEND_VERSION"
    assert match.group(1) == plugin_cls.plugin_version


def _extract_frontend_keys(source: str) -> set:
    """从 ``configDefaults.js`` 源码里提取顶层配置键名。"""
    import re

    block = re.search(r"configDefaults\s*=\s*\{(.*?)\n\}", source, re.DOTALL)
    scope = block.group(1) if block else source
    return set(re.findall(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:", scope, re.MULTILINE))


def test_poster_route_allows_anonymous_access(plugin_cls):
    """`/poster` 必须允许匿名 —— 否则 <img> 请求一律 401。

    真机 F12：`/api/v1/plugin/SubscribeCenter/poster?path=...` 全部 401
    Unauthorized。原因：`<img>` 发起的请求不会携带 axios 注入的 Bearer token，
    而插件路由默认是 `auth: "bear"`。MP 支持用 `allow_anonymous` 跳过鉴权
    （app/adapters/web/plugin/routes.py）。

    安全性：该路由只代理 TMDB 海报，`_poster_path` 会拒绝非 TMDB 域名。
    """
    instance = plugin_cls()
    instance.init_plugin({})
    routes = {route["path"]: route for route in instance.get_api()}
    assert routes["/poster"].get("allow_anonymous") is True
    # 其余路由不应放开
    for path, route in routes.items():
        if path == "/poster":
            continue
        assert not route.get("allow_anonymous"), f"{path} 不应允许匿名"


def test_history_page_reports_decision_counts(plugin):
    """流水接口要返回各决策条数（前端状态 tab 直接用它）。"""
    plugin.save_data("run_history", [
        {"decision": C.DECISION_ADDED, "source": "tmdb", "title": "A"},
        {"decision": C.DECISION_ADDED, "source": "tmdb", "title": "B"},
        {"decision": C.DECISION_PENDING_REVIEW, "source": "tmdb", "title": "C"},
    ])
    page = plugin.history_page()
    assert page.counts.get(C.DECISION_ADDED) == 2
    assert page.counts.get(C.DECISION_PENDING_REVIEW) == 1
    # 过滤 decision 后 counts 仍是全量口径（tab 要在任何筛选下都显示真实数量）
    filtered = plugin.history_page(decision=C.DECISION_ADDED)
    assert filtered.total == 2
    assert filtered.counts.get(C.DECISION_PENDING_REVIEW) == 1


def test_history_page_reports_source_counts(plugin):
    """流水接口要返回各数据源条数（前端「按源」tab 用）。"""
    plugin.save_data("run_history", [
        {"decision": C.DECISION_ADDED, "source": "tmdb", "title": "A"},
        {"decision": C.DECISION_ADDED, "source": "anilist", "title": "B"},
        {"decision": C.DECISION_PENDING_REVIEW, "source": "anilist", "title": "C"},
    ])
    page = plugin.history_page()
    assert page.source_counts.get("anilist") == 2
    assert page.source_counts.get("tmdb") == 1
    # 按源筛选后，source_counts 仍是全量口径（两个维度可以叠加使用）
    filtered = plugin.history_page(source="anilist")
    assert filtered.total == 2
    assert filtered.source_counts.get("tmdb") == 1


def test_decision_counts_follow_source_filter(plugin):
    """决策 tab 的计数要跟着「源」筛选走。

    真机反馈：选了 AniList + 待确认，状态栏仍显示三个源合计的 17 条。
    正确口径：source 过滤之后再统计 decision 计数。
    """
    plugin.save_data("run_history", [
        {"decision": C.DECISION_PENDING_REVIEW, "source": "anilist", "title": "A"},
        {"decision": C.DECISION_PENDING_REVIEW, "source": "anilist", "title": "B"},
        {"decision": C.DECISION_PENDING_REVIEW, "source": "tmdb", "title": "C"},
        {"decision": C.DECISION_ADDED, "source": "tmdb", "title": "D"},
    ])
    page = plugin.history_page(source="anilist")
    assert page.total == 2
    assert page.counts.get(C.DECISION_PENDING_REVIEW) == 2, "应只统计 AniList 的待确认"
    assert C.DECISION_ADDED not in page.counts
    # 源 tab 的计数仍是全量（否则切换后其它源会消失）
    assert page.source_counts.get("tmdb") == 2


def test_history_keyword_searches_title_and_reason(plugin):
    """关键词搜索：片名与原因都能命中。"""
    plugin.save_data("run_history", [
        {"decision": C.DECISION_PENDING_REVIEW, "source": "anilist", "title": "凡人修仙传 第五季",
         "reason": "TMDB 搜不到匹配的剧集"},
        {"decision": C.DECISION_ADDED, "source": "anilist", "title": "诛仙", "reason": ""},
    ])
    assert plugin.history_page(keyword="凡人").total == 1
    assert plugin.history_page(keyword="搜不到").total == 1
    assert plugin.history_page(keyword="不存在").total == 0


def test_sfc_api_calls_use_imported_helpers():
    """SFC 里调用的 *PluginApi 必须是 api.js 真实导出且已 import 的。

    真机：1.5.0 在 Page.vue 里写了 `fetchPluginApi(...)`，但 api.js 只导出
    getPluginApi / postPluginApi / putPluginApi —— 构建照样通过，
    直到用户点开「订阅总览」才报 `fetchPluginApi is not defined`。
    """
    import io
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[3] / "plugins.v3" / "subscribecenter" / "src"
    api_js = io.open(root / "components" / "api.js", encoding="utf-8").read()
    exported = set(re.findall(r"export\s+(?:async\s+)?function\s+(\w+Api)", api_js))
    assert exported, "api.js 未导出任何 *Api 函数"

    for name in ("Page.vue", "Config.vue"):
        text = io.open(root / "components" / name, encoding="utf-8").read()
        imported = set(re.findall(r"import\s*\{([^}]*)\}\s*from\s*'\./api'", text))
        imported_names = set()
        for group in imported:
            imported_names.update(part.strip() for part in group.split(",") if part.strip())
        for used in set(re.findall(r"\b(\w+PluginApi)\s*\(", text)):
            assert used in exported, f"{name} 调用了不存在的 {used}"
            assert used in imported_names, f"{name} 调用 {used} 但没有 import"


def test_api_card_theme_calls_through():
    """配色接口要能真正调到插件方法（防模块别名/未定义名这类错误）。"""
    import asyncio

    from subscribecenter.controller import api as api_module
    from subscribecenter.controller import schemas as api_schemas

    class _Fake:
        def card_theme_config(self):
            return {
                "colors": {"subscribing": "#FFC107", "pending": "#F97316", "paused": "#9CA3AF"},
                "best_version_outline": False,
                "best_version_color": "#A855F7",
                "applied": True,
            }

        async def apply_card_theme(self, colors=None, best_version_outline=False):
            assert colors == {"subscribing": "#00FF00"} or colors is None
            return {"success": True, "error": ""}

    read = asyncio.run(api_module.api_card_theme(_Fake()))
    assert read.success is True
    assert read.data.colors["subscribing"] == "#FFC107"

    saved = asyncio.run(
        api_module.api_card_theme_save(
            _Fake(),
            api_schemas.CardThemeRequest(
                colors={"subscribing": "#00FF00"}, best_version_outline=True
            ),
        )
    )
    assert saved.success is True

    reset = asyncio.run(
        api_module.api_card_theme_save(_Fake(), api_schemas.CardThemeRequest(reset=True))
    )
    assert reset.success is True


def test_post_endpoints_use_concrete_body_model(plugin_cls):
    """带请求体的 POST 端点必须用**具体模型**标注 request。

    真机：`api_card_theme_save(self, request: Any)` 让 FastAPI 把 request
    当成查询参数，前端一保存就 422「请求参数不正确」。
    """
    import inspect
    from typing import Any  # noqa: F401 - 仅用于比较注解

    instance = plugin_cls()
    for name in ("api_card_theme_save", "api_mapping_fix"):
        func = getattr(instance, name)
        params = inspect.signature(func).parameters
        assert "request" in params, name
        annotation = params["request"].annotation
        assert annotation is not Any, f"{name} 的 request 不能用 Any 标注"
        assert isinstance(annotation, type) and hasattr(annotation, "model_fields"), (
            f"{name} 的 request 必须是 pydantic 模型"
        )
    from subscribecenter.controller import schemas as api_schemas

    assert hasattr(api_schemas.CardThemeRequest, "model_fields")


# ------------------------------------------------------- 体检已有订阅（黑名单补刀）


def _row(sid, name="某剧", season=1, state="R", media_source="themoviedb", media_id="1"):
    """造一条宿主的 ``Subscribe`` 行（只需要体检用到的字段）。"""
    import types

    return types.SimpleNamespace(
        id=sid,
        name=name,
        season=season,
        state=state,
        type="电视剧",
        media_source=media_source,
        media_id=media_id,
    )


def test_blacklist_audit_needs_active_rules(plugin, monkeypatch):
    """没有生效规则时不做任何请求，直接告诉用户「先去配规则」。"""
    monkeypatch.setattr(plugin, "_config", {**plugin._config, "blacklist_enabled": False})
    called = {"n": 0}

    async def fake_rows():
        called["n"] += 1
        return []

    monkeypatch.setattr(plugin, "_subscription_rows", fake_rows)
    result = asyncio.run(plugin.blacklist_audit())
    assert result["active"] is False
    assert result["hits"] == []
    assert called["n"] == 0


def test_blacklist_audit_separates_hits_skipped_and_checked(plugin, monkeypatch):
    """「命中」「没命中」「核不了」必须三分类，不能把查失败的算成通过。"""
    monkeypatch.setattr(
        plugin,
        "_config",
        {
            **plugin._config,
            "blacklist_enabled": True,
            "blacklist_words": "同性",
            "blacklist_tmdb_keywords": False,
        },
    )

    async def fake_rows():
        return [_row(1, "以你的心诠释我的爱"), _row(2, "凡人修仙传"), _row(3, "豆瓣剧", media_source="douban")]

    async def fake_one(row, rules, *, want_keywords):
        base = {
            "id": row.id,
            "name": row.name,
            "season": row.season,
            "state": row.state,
            "reason": "",
            "skipped": "",
        }
        if row.id == 1:
            base["reason"] = "命中排除题材（TMDB 关键词）：lgbt"
        elif row.id == 3:
            base["skipped"] = "来源是 douban，不是 TMDB，未能核对"
        return base

    monkeypatch.setattr(plugin, "_subscription_rows", fake_rows)
    monkeypatch.setattr(plugin, "_audit_one", fake_one)
    result = asyncio.run(plugin.blacklist_audit())
    assert result["total"] == 3
    assert result["checked"] == 2
    assert result["skipped"] == 1
    assert [hit["id"] for hit in result["hits"]] == [1]
    assert result["uncheckable"][0]["id"] == 3
    assert result["unchecked"] == 0


def test_blacklist_sweep_pauses_and_resumes(plugin, monkeypatch):
    """体检的「暂停选中」只改状态、不删订阅：pause → S，resume → R。"""
    seen = {}

    async def fake_apply(changes):
        seen["changes"] = changes
        return [item["id"] for item in changes], []

    monkeypatch.setattr(plugin, "_apply_auto_toggle", fake_apply)
    paused = asyncio.run(plugin.blacklist_sweep(ids=[7, 9], action="pause"))
    assert seen["changes"] == [
        {"id": 7, "name": "", "target": "S"},
        {"id": 9, "name": "", "target": "S"},
    ]
    assert paused["action"] == "pause"
    assert paused["applied"] == 2

    resumed = asyncio.run(plugin.blacklist_sweep(ids=[7], action="resume"))
    assert seen["changes"] == [{"id": 7, "name": "", "target": "R"}]
    assert resumed["action"] == "resume"


def test_blacklist_sweep_requires_ids(plugin):
    """一条都没选就报错，别静默返回成功骗用户。"""
    import pytest

    with pytest.raises(ValueError):
        asyncio.run(plugin.blacklist_sweep(ids=[], action="pause"))


def test_blacklist_audit_runs_in_background(plugin, monkeypatch):
    """体检必须走后台任务：200 条订阅就是 200 次请求，同步跑一定被网关 502。"""

    async def fake_audit(**kwargs):
        return {"active": True, "total": 0, "hits": []}

    monkeypatch.setattr(plugin, "blacklist_audit", fake_audit)
    started = plugin.start_blacklist_audit()
    assert started["started"] is True
    state = plugin.blacklist_audit_state()
    assert "running" in state and "result" in state
