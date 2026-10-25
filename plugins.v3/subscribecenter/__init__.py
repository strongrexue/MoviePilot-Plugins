"""胖虎订阅中心 - MoviePilot V3 插件主类（SubscribeCenter）。

定位（开发文档 §1）：**只做三件事：发现 → 去重 → 写订阅。**
版本控制、洗版、下载优先级全部由宿主订阅下载优先级规则接管，插件不介入。

当前进度：**v0.1.0 / P0+P1** —— 骨架 + TMDB 源 + 订阅写入 + 身份 L1 直通。
Bangumi / 豆瓣 RSS / Simkl / 前端联邦组件 尚未实现（见开发文档 §16）。

关键宿主契约（MoviePilot v3.1.6，均已对源码核验）：

- ``get_render_mode()`` 必须返回 ``("vue", "dist/assets")`` 元组；
- ``get_service()`` 的 ``func`` 是同步可调用，由 apscheduler 在自己的线程里调用，
  **不在事件循环内** → 必须经 :class:`~.core.bridge.PipelineBridge` 桥接；
- ``get_sidebar_nav()`` 不是基类方法，而是契约钩子，由宿主 ``getattr`` 调用；
- 写入订阅走 ``SubscribeChain().async_add()``，身份是 ``media_source``+``media_id``。
"""
import asyncio
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .controller import api as api_controller
from .controller import schemas as api_schemas
from .core import card_theme
from .core import constants as C
from .core.bridge import PipelineBridge
from .core.cache import MappingCacheStore
from .core.identity import IdentityResolver
from .core.pipeline import RunSummary, SourceAdapter, run_pipeline
from .core.window import local_now_text, today
from .core.writer import SubscriptionWriter, WriteOutcome
from .sources.tmdb import TmdbSource

#: 插件数据键
DATA_KEY_CACHE = "mapping_cache"
DATA_KEY_STATE = "runtime_state"
DATA_KEY_HISTORY = "run_history"
DATA_KEY_CARD_THEME = "card_theme"
#: 「按播出日自动启停」的接管表与上次运行摘要。
#:
#: 只放**本插件自己暂停过**的订阅 ID。没有这张表就分不清「订阅是用户手动暂停的」
#: 和「是我们暂停的」—— 前者绝不能被自动恢复，否则会违背用户意图。
DATA_KEY_AUTO_TOGGLE = "auto_toggle"
#: 「我订过」的键集合（``来源:ID:季``），只增不减，清空流水时才清。
#:
#: 为什么不直接查流水：流水是**给眼睛看的**，一条作品只留最新状态（``_collapse_history``
#: 会把「已订阅」替换成后来的「流水已记录」），又会被 ``MAX_HISTORY`` 截断。
#: 把去重证据放在流水里，等于让「订过」的记忆取决于最近几次运行 —— 真机表现就是
#: 「流水里明明记过，删掉订阅后又被自动订回来」（1.14.5 修的就是这个）。
DATA_KEY_RECORDED = "recorded_keys"

#: 内存中保留的流水条数上限（落盘时会截断）
MAX_HISTORY = 500


class SubscribeCenter(_PluginBase):
    """胖虎订阅中心插件入口。"""

    plugin_name = C.PLUGIN_NAME
    plugin_desc = C.PLUGIN_DESCRIPTION
    plugin_icon = C.PLUGIN_ICON
    plugin_color = C.PLUGIN_COLOR
    #: 必须是**类级字符串字面量** —— 发布门禁 ``check_plugin_versions.py``
    #: 用 AST 提取它并与 ``package.v3.json`` 的 ``version`` 比对，
    #: 写成 ``C.PLUGIN_VERSION`` 这类引用会让门禁取不到值。
    plugin_version = "1.14.6"
    plugin_author = C.PLUGIN_AUTHOR
    author_url = C.AUTHOR_URL
    plugin_config_prefix = C.PLUGIN_CONFIG_PREFIX
    plugin_order = C.PLUGIN_ORDER
    auth_level = C.AUTH_LEVEL

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """建立实例独享的配置快照与模块容器。"""
        super().__init__(*args, **kwargs)
        self._config: Dict[str, Any] = {}
        #: 身份映射缓存（存储经 save_data 注入）
        self._cache = MappingCacheStore(_PluginCacheStore(self))
        self._resolver: Optional[IdentityResolver] = None
        self._writer: SubscriptionWriter = SubscriptionWriter(_NullSubscribeBackend(), daily_limit=0)
        #: 调度 ↔ asyncio 桥接（互斥锁按插件实例隔离）
        self._bridge = PipelineBridge(self.__class__.__name__)
        #: 各源最近一次运行状态
        self._source_state: Dict[str, Dict[str, Any]] = {}
        self._last_summary: Dict[str, Any] = {}
        self._last_run: Optional[str] = None

    # ------------------------------------------------------------------ 配置快照

    @property
    def config(self) -> Dict[str, Any]:
        """返回当前生效配置。"""
        return self._config

    @staticmethod
    def default_config() -> Dict[str, Any]:
        """返回插件默认配置（键集合必须与前端 configDefaults 严格一致）。"""
        return C.default_config()

    def save_config(self, **patch: Any) -> None:
        """合并写入配置。

        宿主 ``update_config()`` 是**整份覆盖**，因此统一走本方法：先合并当前快照，
        再整体写回，避免只写部分字段时丢掉其它配置。
        """
        merged = dict(self._config)
        merged.update(patch)
        self._config = merged
        self.update_config(merged)

    def _enabled(self) -> bool:
        """当前配置是否已启用插件。"""
        return bool(self._config.get("enabled"))

    # ------------------------------------------------------------------ 生命周期

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """读取配置、重建适配器；必须允许重复调用。"""
        self.stop_service()

        merged = self.default_config()
        merged.update(config or {})
        self._config = merged

        # 存量配置迁移：把「改了默认值」的键推到老用户配置上。
        # 不做这一步的话，用户库里的旧值会在 merge 后胜出 —— 改默认值等于白改
        # （真机踩过：窗口从 30 改成 8 后，用户库里仍是 30）。
        self._migrate_config()

        # 一次性开关：读取后立刻置回默认值，避免长期生效
        self._consume_one_shot_flags()

        # 空转检测：启用了但没有任何监听内容的源自动关闭（借鉴自动订阅助手）
        self._empty_spectrum_check()

        # 宿主适配器延迟到运行时构造：模块导入期不得接触宿主内部（官方硬性要求）
        from .core.host import HostSubscribeBackend, HostTmdbResolver

        self._resolver = IdentityResolver(
            HostTmdbResolver(),
            self._cache,
            # 默认不采用跨源换算回来的季号（国产动画多为 TMDB 单季多集）
            use_converted_season=bool(self._config.get("bangumi_split_season")),
            prefer_episode_group=bool(self._config.get("prefer_episode_group", True)),
        )
        daily_limit = self._int_config("daily_limit", C.DEFAULT_DAILY_LIMIT)
        self._writer = SubscriptionWriter(
            HostSubscribeBackend(),
            daily_limit=daily_limit,
            resubscribe_completed=bool(
                self._config.get("resubscribe_completed", True)
            ),
            notify_each=True,
            dedupe_history=bool(self._config.get("dedupe_by_history", True)),
            recorded_keys=self._recorded_keys,
        )
        self._last_run = self._state().get("last_run")

    def _migrate_config(self) -> None:
        """把「改了默认值」的配置键推到存量配置上并落库。

        背景：``init_plugin`` 是「默认值 merge 存量配置」，用户库里存着旧值时
        旧值胜出，所以只改 ``default_config()`` 的默认值**对老用户无效**。
        真机踩过：窗口默认 30 -> 8 后，用户库里仍是 30，白等一轮。

        迁移规则登记在 ``core/constants.py`` 的 :func:`config_migrations`，
        只覆盖「数值默认值调整」这类安全键，不动用户可能主动改过的开关。
        """
        try:
            migrated, changed, changes = C.migrate_config(dict(self._config))
            self._config = migrated
            if not changed:
                return
            self.update_config(self._config)
            logger.info(
                "[SubscribeCenter] 存量配置已迁移到 v%s：%s"
                % (C.CONFIG_VERSION, "；".join(changes))
            )
        except Exception as err:  # noqa: BLE001 - 迁移失败不应影响插件加载
            logger.warning(f"[SubscribeCenter] 配置迁移失败：{err}")

    def _empty_spectrum_check(self) -> List[str]:
        """启用了却不可能产出任何内容的源 → 自动关闭，并记下原因给前端提示。

        判定依据（各源不同）：

        - **TMDB**：窗口天数 <= 0 → 永远筛不出条目
        - **AniList**：窗口天数 <= 0 → 同上
        - **豆瓣榜单**：没有一条「已启用且带地址」的榜单 → 抓不到任何 feed

        纠正后写回配置（``update_config``），并把提示存进运行时状态，
        由前端状态栏展示；同一份配置只纠正一次，避免与宿主重载互相触发。
        """
        config = dict(self._config)
        issues: List[str] = []

        def _int(key: str, default: int = 0) -> int:
            try:
                return int(config.get(key, default) or 0)
            except (TypeError, ValueError):
                return default

        if config.get("enable_tmdb") and _int("tmdb_future_days") <= 0:
            issues.append("TMDB：窗口天数为 0，永远不会产出条目 → 已自动关闭")
            config["enable_tmdb"] = False
        if config.get("enable_anilist") and _int("anilist_future_days") <= 0:
            issues.append("AniList：窗口天数为 0，永远不会产出条目 → 已自动关闭")
            config["enable_anilist"] = False
        if config.get("enable_hot_media"):
            if not (config.get("hot_media_movie_enabled", True)
                    or config.get("hot_media_tv_enabled", True)):
                issues.append("热门媒体：电影与剧集都没有勾选 → 已自动关闭")
                config["enable_hot_media"] = False
        if config.get("enable_douban_rss"):
            try:
                from .sources.douban_rss import parse_sources

                active = parse_sources(config.get("douban_rss_sources"))
            except Exception:  # noqa: BLE001 - 解析失败按「没有榜单」处理
                active = []
            if not active:
                issues.append(
                    "豆瓣榜单：没有启用任何带地址的榜单 → 已自动关闭"
                    "（去勾选内置榜单，或添加一条自定义 RSS 地址）"
                )
                config["enable_douban_rss"] = False

        state = self._state()
        if issues:
            # 只纠正一次：写回后配置已变，下次 init 不会再命中这些分支
            self._config = config
            logger.warning(f"[SubscribeCenter] 空转检测：{'；'.join(issues)}")
            try:
                self.update_config(config)
            except Exception as err:  # pragma: no cover - 写配置失败不影响运行
                logger.warning(f"[SubscribeCenter] 空转检测写回配置失败：{err}")
            state["config_issues"] = issues
        else:
            state.pop("config_issues", None)
        self._save_state(state)
        return issues

    def _consume_one_shot_flags(self) -> None:
        """处理并复位一次性开关。

        目前只有一个：``reset_daily_counter`` —— 把「今日已写入条数」清零，
        用于同一天反复测试。**用完立刻置回 False 并写回配置**，
        否则每日写入上限会永久失效。
        """
        if not self._config.get("reset_daily_counter"):
            return
        try:
            state = self._state()
            state[C.STATE_DAILY_COUNT] = 0
            state[C.STATE_TODAY] = today(self._tz()).isoformat()
            self._save_state(state)
            self._config["reset_daily_counter"] = False
            self.update_config(self._config)
            logger.info(
                "[SubscribeCenter] 已按「清零今日写入计数」开关重置额度"
                "（测试用，开关已自动关闭）"
            )
        except Exception as err:  # noqa: BLE001 - 测试辅助失败不应影响插件加载
            logger.warning(f"[SubscribeCenter] 清零今日写入计数失败：{err}")

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled()

    @staticmethod
    def get_render_mode() -> Tuple[str, Optional[str]]:
        """声明 Vue 联邦渲染模式与构建产物目录。

        .. important::
           契约是 ``Tuple[str, Optional[str]]`` —— 必须返回元组，
           只返回 ``"vue"`` 会让宿主找不到 ``remoteEntry.js``。
       """
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下不返回 Vuetify 表单结构，只提供默认配置模型。"""
        return None, self.default_config()

    def get_page(self) -> Optional[List[dict]]:
        """详情页由 Vue 远程组件渲染。"""
        return None

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """MP 左侧「发现」分区的整页入口。

        默认关闭：只有插件已启用、且用户打开配置页的「发现页」开关时才注册，
        避免给不用的人凭空多一个导航项。
        """
        if not self._enabled():
            return []
        return [
            {
                "nav_key": "main",
                "title": self.plugin_name,
                "icon": "mdi-radar",
                "section": "discovery",
                "permission": "discovery",
                "order": C.PLUGIN_ORDER,
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由声明。"""
        return api_controller.get_api(self)

    # ------------------------------------------------------------------ API 端点委托
    #
    # 宿主按「插件实例上的绑定方法」解析 endpoint，因此必须在主类上定义薄委托；
    # 实现体统一放在 controller/api.py，主类不承载业务逻辑。

    async def api_status(self) -> Any:
        """返回插件运行状态与各源情况。"""
        return await api_controller.api_status(self)

    async def api_history(
        self,
        page: int = 1,
        count: int = 20,
        decision: str = "",
        source: str = "",
        keyword: str = "",
    ) -> Any:
        """分页查询发现/写入流水。"""
        return await api_controller.api_history(
            self, page=page, count=count, decision=decision, source=source, keyword=keyword
        )

    async def system_share(self) -> Dict[str, Any]:
        """读取宿主的「订阅数据共享」（``SUBSCRIBE_STATISTIC_SHARE``）。

        .. important::
           它是宿主的**运行设置**（``app/runtime/config.py`` 里的 ``SUBSCRIBE_STATISTIC_SHARE``），
           不是 ``SystemConfigKey`` 成员。早期用 ``getattr(SystemConfigKey, ...)``
           会直接 AttributeError → 前端「未知错误」，故改走 runtime 端口。
        """
        return {"enabled": self._share_enabled()}

    async def set_system_share(self, enabled: bool) -> Dict[str, Any]:
        """一键开关「订阅数据共享」（热门媒体依赖它）。"""
        from app.runtime.settings import update_runtime_setting

        ok, message = update_runtime_setting("SUBSCRIBE_STATISTIC_SHARE", bool(enabled))
        if ok is False:
            raise RuntimeError(str(message or "宿主拒绝修改该设置"))
        logger.info(f"[SubscribeCenter] 订阅数据共享已设为 {bool(enabled)}（{message or 'ok'}）")
        return {"enabled": self._share_enabled()}

    @staticmethod
    def _share_enabled() -> bool:
        """读取宿主运行设置里的订阅数据共享开关。"""
        try:
            from app.runtime.settings import get_runtime_setting

            return bool(get_runtime_setting("SUBSCRIBE_STATISTIC_SHARE", False))
        except Exception as err:  # pragma: no cover - 宿主无该端口时按关闭处理
            logger.debug(f"[SubscribeCenter] 读取订阅数据共享失败：{err}")
            return False

    async def api_system_share(self) -> Any:
        """读取订阅数据共享状态。"""
        return await api_controller.api_system_share(self)

    async def api_auto_toggle(self) -> Any:
        """预览「按播出日自动启停」会动哪些订阅（不写库）。"""
        return await api_controller.api_auto_toggle(self)

    async def api_auto_toggle_apply(self) -> Any:
        """立刻执行一次自动启停（会写订阅状态）。"""
        return await api_controller.api_auto_toggle_apply(self)

    async def api_blacklist(self) -> Any:
        """读取排除规则元数据（内置题材预设 + TMDB 类型名）。"""
        return await api_controller.api_blacklist(self)

    async def api_blacklist_test(
        self, request: api_schemas.BlacklistTestRequest
    ) -> Any:
        """自测一条内容会不会被排除规则拦下。

        **注解必须写具体模型**：FastAPI 靠端点签名判断要不要解析 JSON body，
        注解写成 ``Any`` 时 body 会以 dict 传进来，``request.title`` 直接炸
        （1.14.0 真机「自测」500 就是这个原因）。
        """
        return await api_controller.api_blacklist_test(self, request)

    async def api_blacklist_audit(self) -> Any:
        """启动「已有订阅体检」（后台跑），立刻返回状态。"""
        return await api_controller.api_blacklist_audit(self)

    async def api_blacklist_audit_result(self) -> Any:
        """读体检进度 / 结果。"""
        return await api_controller.api_blacklist_audit_result(self)

    async def api_blacklist_sweep(
        self, request: api_schemas.BlacklistSweepRequest
    ) -> Any:
        """把体检选中的订阅批量暂停 / 恢复（注解必须是具体模型，理由同上）。"""
        return await api_controller.api_blacklist_sweep(self, request)

    async def api_system_share_save(
        self, request: api_schemas.SystemShareRequest
    ) -> Any:
        """设置订阅数据共享开关。"""
        return await api_controller.api_system_share_save(self, request)


    async def calendar_month(self, month_text: str = "") -> Dict[str, Any]:
        """整月日历（复刻 MoviePilot 日历页）：返回 {日期: 条目}。"""
        import re as _re

        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

        from .core import calendar as calendar_core

        picked = str(month_text or "").strip()
        if not _re.fullmatch(r"\d{4}-\d{2}", picked):
            picked = today(self._tz()).strftime("%Y-%m")

        async with async_session_scope() as session:
            rows = (
                await session.execute(
                    select(Subscribe).where(Subscribe.state.in_(calendar_core.ACTIVE_STATES))
                )
            ).scalars().all()

        first_day = f"{picked}-01"
        index = await self._episode_air_index(rows, first_day)
        data = calendar_core.build_month(
            rows, picked, index, movie_kinds=self._movie_kind_map()
        )
        return data

    async def calendar_today(self, date_text: str = "") -> Dict[str, Any]:
        """某天的日历：默认今天，可传 YYYY-MM-DD 查历史 / 未来。"""
        import re as _re

        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

        from .core import calendar as calendar_core

        picked = str(date_text or "").strip()
        if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", picked):
            picked = ""
        today_text = picked or today(self._tz()).isoformat()
        async with async_session_scope() as session:
            rows = (
                await session.execute(
                    select(Subscribe).where(Subscribe.state.in_(calendar_core.ACTIVE_STATES))
                )
            ).scalars().all()

        episode_index = await self._episode_air_index(rows, today_text)
        # 「今天会不会被搜」只有今天才有意义，历史/未来日期不传
        flags = (
            await self._auto_toggle_flags()
            if today_text == today(self._tz()).isoformat()
            else None
        )
        items = calendar_core.build_today(
            rows,
            today_text,
            episode_index,
            search_flags=flags,
            movie_kinds=self._movie_kind_map(),
        )
        summary = calendar_core.summarize(items)
        return {
            "today": today_text,
            **summary,
            "items": items,
        }

    # -------------------------------------------------------- 按播出日自动启停

    def _auto_toggle_config(self) -> Dict[str, Any]:
        """自动启停的生效配置（已做边界收敛）。

        为什么要在读的时候再收敛一遍：配置是用户手输的，``keep_days=3650``
        会让功能形同关闭、``lookahead_days=-5`` 会让「即将播出」永远为空，
        这两种都只该是笔误，不该变成难查的行为异常。
        """
        return {
            "enabled": bool(self._config.get("auto_toggle_enabled")),
            "cron": self._normalize_cron(
                self._config.get("auto_toggle_cron"), C.DEFAULT_AUTO_TOGGLE_CRON
            ),
            "lookahead_days": min(
                max(self._int_config("auto_toggle_lookahead_days", 0), 0), 30
            ),
            "keep_days": min(max(self._int_config("auto_toggle_keep_days", 3), 0), 90),
            "best_keep_days": min(
                max(
                    self._int_config(
                        "auto_toggle_best_version_keep_days",
                        C.DEFAULT_AUTO_TOGGLE_BEST_KEEP,
                    ),
                    0,
                ),
                365,
            ),
            "movie_enabled": bool(self._config.get("auto_toggle_movie_enabled", True)),
            "library_check": bool(self._config.get("auto_toggle_library_check")),
            "library_probe_budget": min(
                max(
                    self._int_config(
                        "auto_toggle_library_probe_budget_seconds",
                        C.DEFAULT_AUTO_TOGGLE_PROBE_BUDGET,
                    ),
                    0,
                ),
                3600,
            ),
            "library_probe_interval": min(
                max(
                    self._float_config(
                        "auto_toggle_library_probe_interval",
                        C.DEFAULT_AUTO_TOGGLE_PROBE_INTERVAL,
                    ),
                    0.0,
                ),
                60.0,
            ),
            "best_mode": self._best_toggle_mode(),
            "max_changes": min(
                max(self._int_config("auto_toggle_max_changes", 0), 0), 2000
            ),
            "notify": bool(self._config.get("auto_toggle_notify")),
        }

    def _best_toggle_mode(self) -> str:
        """洗版判定模式：播出期也按「未洗到顶」判，还是只在季终后判。

        默认 ``after_finale``：宿主在播出期只下「首个可用版本」，真正的洗版
        （原盘/REMUX）是季终之后才陆续有资源。播出期就按洗版判，等于让所有
        洗版订阅长期 ``R``，跟「按播出日暂停」的初衷正好相反。
        """
        from .core import autotoggle

        value = str(self._config.get("auto_toggle_best_version_mode") or "").strip()
        if value in autotoggle.BEST_MODES:
            return value
        return autotoggle.BEST_MODE_AFTER_FINALE

    def _auto_toggle_state(self) -> Dict[str, Any]:
        """读取接管表与上次运行摘要。"""
        value = self.get_data(DATA_KEY_AUTO_TOGGLE)
        return dict(value) if isinstance(value, dict) else {}

    def _save_auto_toggle_state(self, state: Dict[str, Any]) -> None:
        """写入接管表与上次运行摘要。"""
        self.save_data(DATA_KEY_AUTO_TOGGLE, state)

    async def _movie_release_index(self, rows: Any) -> Dict[str, List[tuple]]:
        """给电影订阅取 TMDB 发行记录（数字 / 实体 / 影院…），6 小时缓存。

        为什么不用日历里那个 ``release_date``：它是 TMDB 顶层字段，基本等于
        首映/院线日期，而订电影等的是**数字版**出种、洗版等的是**实体碟**
        出种，两者比首映日晚几周到几个月。拿首映日当基准，电影订阅会正好在
        真正出种的那几周被判成「窗口已过」而暂停 —— 那是这个功能最伤人的
        一种错法。

        最多并发 4 个请求；任何一部失败只影响它自己（``release_records``
        为空 → 判定时按「取不到发行日期」跳过，不会误暂停）。
        """
        import asyncio
        import time

        from .core import autotoggle

        cache = self.__dict__.setdefault("_release_cache", {})
        ttl = 6 * 3600
        now = time.time()

        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi
            from app.schemas.types import MediaType

            tmdb = TmdbApi()
        except Exception as err:  # noqa: BLE001 - 宿主缺 TMDB 时电影一律不动
            logger.debug(f"[SubscribeCenter] 自动启停取不到 TMDB：{err}")
            return {}

        targets: List[tuple] = []
        for row in rows:
            if autotoggle.media_kind(row) != "movie":
                continue
            media_id = str(getattr(row, "media_id", "") or "")
            if not media_id.isdigit():
                continue
            if media_id in cache and now - cache[media_id][0] < ttl:
                continue
            targets.append((media_id, str(getattr(row, "media_source", "") or "")))

        if targets:
            semaphore = asyncio.Semaphore(4)

            async def resolve_tmdb_id(media_id: str, media_source: str) -> Optional[int]:
                """把订阅上的 ``media_id`` 换成 TMDB ID。

                订阅的 ``media_id`` 是**来源自己的** ID（豆瓣订阅存的是豆瓣 ID），
                直接拿去查 TMDB 会查到一部完全不相干的电影 —— 那会按别人家的
                发行日暂停你的订阅，属于最坏的一种错。
                """
                if media_source in ("", "themoviedb"):
                    return int(media_id)
                try:
                    from app.chain.media import MediaChain
                    from app.schemas.types import MediaInfo, MediaType

                    media = await MediaChain().async_recognize_media(
                        MediaInfo(
                            media_source=media_source,
                            media_id=media_id,
                            type=MediaType.MOVIE,
                        )
                    )
                    tmdb_id = self._field(media, "tmdb_id")
                    return int(tmdb_id) if tmdb_id else None
                except Exception as err:  # noqa: BLE001 - 识别失败就跳过这部
                    logger.debug(
                        f"[SubscribeCenter] 电影识别失败 {media_source}:{media_id}：{err}"
                    )
                    return None

            async def fetch(target: tuple) -> None:
                media_id, media_source = target
                async with semaphore:
                    records: List[tuple] = []
                    try:
                        tmdb_id = await resolve_tmdb_id(media_id, media_source)
                        if tmdb_id:
                            info = await tmdb.async_get_info(MediaType.MOVIE, tmdb_id)
                            records = autotoggle.release_records(info)
                    except Exception as err:  # noqa: BLE001 - 单部失败不影响其它
                        logger.debug(
                            f"[SubscribeCenter] 电影发行日期查询失败 {media_id}：{err}"
                        )
                    cache[media_id] = (now, records)

            await asyncio.gather(*(fetch(target) for target in targets))

        return {
            media_id: cache[media_id][1]
            for media_id in list(cache)
            if now - cache[media_id][0] < ttl
        }

    async def _movie_legacy_release(self, media_source: str, media_id: str) -> str:
        """发行记录的兜底：TMDB 顶层 ``release_date``（先试链识别，再试 API）。

        只有 ``release_dates`` 拿不到时才走这里。顶层字段基本等于院线首映，
        不如数字发行日准，但总比让电影从日历里消失好。
        """
        import asyncio

        try:
            from app.chain.media import MediaChain
            from app.schemas.types import MediaInfo, MediaType

            media = await MediaChain().async_recognize_media(
                MediaInfo(
                    media_source=media_source, media_id=media_id, type=MediaType.MOVIE
                )
            )
            release = str(self._field(media, "release_date") or "")[:10]
            if release:
                return release
        except Exception as err:  # noqa: BLE001 - 链不可用时回退 API
            logger.debug(
                f"[SubscribeCenter] 电影识别失败 {media_source}:{media_id}：{err}"
            )
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi
            from app.schemas.types import MediaType

            info = await asyncio.to_thread(
                TmdbApi().get_info, MediaType.MOVIE, int(media_id)
            )
            return str(self._field(info, "release_date") or "")[:10]
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[SubscribeCenter] 电影取详情失败 {media_id}：{err}")
            return ""

    def _note_movie_kind(self, media_id: str, kind: str) -> None:
        """记下这部电影用的是哪种发行日（给日历标「数字发行 / 实体发行」）。"""
        if kind:
            self.__dict__.setdefault("_movie_kind_cache", {})[media_id] = kind

    def _movie_kind_map(self) -> Dict[str, str]:
        return dict(self.__dict__.get("_movie_kind_cache") or {})

    async def _auto_toggle_flags(self) -> Optional[Dict[int, Dict[str, Any]]]:
        """今天的「会不会被搜」标记，与预览共用同一份判定。

        只给「今天」的日历用：查历史/未来日期时「今天会不会搜」没有意义。
        自动启停没开时返回 None，日历干脆不显示这个标记。
        """
        from .core import autotoggle

        if not self._auto_toggle_config()["enabled"]:
            return None
        try:
            data = await self.auto_toggle_plan()
        except Exception as err:  # noqa: BLE001 - 判定失败不能让日历空白
            logger.debug(f"[SubscribeCenter] 日历取自动启停判定失败：{err}")
            return None
        flags: Dict[int, Dict[str, Any]] = {}
        for item in data.get("items") or []:
            try:
                sid = int(item.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if not sid:
                continue
            target = str(item.get("target") or "")
            state = str(item.get("state") or "")
            if target in (autotoggle.STATE_RUN, autotoggle.STATE_PAUSED):
                searched = target == autotoggle.STATE_RUN
            else:
                # 被判「跳过」的（P 态、电影开关关掉、无播出表…）按宿主当前
                # 状态算：R/P 仍会被刷新搜到，S 不会。
                searched = state in (autotoggle.STATE_RUN, autotoggle.STATE_PENDING)
            flags[sid] = {
                "searched": searched,
                "note": "" if searched else str(item.get("reason_label") or ""),
            }
        return flags

    async def _library_present_index(
        self,
        rows: Any,
        episode_index: Any,
        today_date: Any,
        *,
        probe: bool = False,
        cached: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[int, set], Dict[str, Any]]:
        """媒体库已入库集号索引 ``{订阅 ID: {集号}}``，以及一份统计。

        三级数据源，**都只减误报、不会误暂停**（``decide`` 里是并集）：

        1. **媒体库快照**（免费）：宿主同步任务把每部剧的 ``{季: [集号]}`` 记在
           ``MediaServerItem.seasoninfo``，一次 SQL 拿到全部，零媒体服务器请求。
        2. **上次核对结果**（免费）：上一轮探针的结论存在插件数据里，预览直接沿用 ——
           否则「预览」自己也要发几百个请求，网页早被网关掐断了。
        3. **实时探针**（慢）：仅 ``probe=True``（后台执行 / 定时任务）时才发。
           快照没覆盖的、且真有已播未入库的集的订阅，按时间预算逐条问宿主
           ``DownloadChain().get_no_exists_info``（每条要发两次媒体服务器请求，
           全量并发正是上一版把 NAS 打挂的原因）。

        .. important::
           探针**绝不能**放在 HTTP 请求里：200 条串行核对要好几分钟，网关会
           直接 502。预览永远只读，慢的那部分留给后台。
        """
        cached = cached if isinstance(cached, dict) else {}
        cfg = self._auto_toggle_config()
        snapshot: Dict[int, set] = {}
        try:
            snapshot = await self._library_snapshot_index(rows)
        except Exception as err:  # noqa: BLE001 - 快照取不到就只靠探针
            logger.debug(f"[SubscribeCenter] 媒体库快照读取失败：{err}")

        index: Dict[int, set] = {sid: set(eps) for sid, eps in snapshot.items()}
        reused: Dict[int, set] = {}
        for key, value in (cached.get("items") or {}).items():
            try:
                sid = int(key)
            except (TypeError, ValueError):
                continue
            episodes = {int(item) for item in (value or []) if int(item) > 0}
            if episodes:
                reused[sid] = episodes
                index.setdefault(sid, set()).update(episodes)

        stats: Dict[str, Any] = {
            "snapshot": len(snapshot),
            "cached": len(reused),
            "cached_at": str(cached.get("at") or ""),
            "probed": 0,
            "candidates": 0,
            "budget_seconds": cfg["library_probe_budget"],
            "interval": cfg["library_probe_interval"],
            "elapsed": 0,
            "deferred": 0,
        }
        try:
            candidates = self._probe_candidates(
                rows, episode_index, today_date, known=index
            )
        except Exception as err:  # noqa: BLE001 - 候选算不出来就当没有
            logger.debug(f"[SubscribeCenter] 媒体库核对候选计算失败：{err}")
            return index, stats
        stats["candidates"] = len(candidates)

        if not probe or cfg["library_probe_budget"] <= 0 or not candidates:
            # 预览 / 预算 0 / 没有待核对 → 一个请求都不发
            stats["deferred"] = len(candidates)
            return index, stats

        try:
            probed, probe_stats = await self._probe_missing_episodes(
                rows,
                episode_index,
                today_date,
                budget_seconds=cfg["library_probe_budget"],
                interval=cfg["library_probe_interval"],
                known=index,
            )
        except Exception as err:  # noqa: BLE001 - 探针失败不能让整轮崩
            logger.warning(f"[SubscribeCenter] 媒体库探针失败：{err}")
            return index, stats

        for sid, episodes in probed.items():
            index[sid] = set(index.get(sid) or set()) | set(episodes)
        stats.update(probe_stats)
        #: 本轮探针结果交给调用方落盘，供下次预览沿用
        self.__dict__["_auto_toggle_library_probe"] = {
            "at": local_now_text(self._tz()),
            "items": {str(sid): sorted(episodes) for sid, episodes in probed.items()},
        }
        return index, stats

    async def _library_snapshot_index(self, rows: Any) -> Dict[int, set]:
        """从 ``MediaServerItem.seasoninfo`` 读「库里有什么」，纯 DB，零请求。"""
        from app.db import async_session_scope
        from app.db.models.mediaserver import MediaServerItem
        from sqlalchemy import select

        from .core import autotoggle

        wanted: Dict[str, List[Any]] = {}
        for row in rows:
            if autotoggle.media_kind(row) != "tv":
                continue
            media_id = str(getattr(row, "media_id", "") or "")
            if not media_id.isdigit():
                continue
            wanted.setdefault(media_id, []).append(row)
        if not wanted:
            return {}

        async with async_session_scope() as session:
            items = (
                await session.execute(
                    select(MediaServerItem).where(
                        MediaServerItem.media_id.in_(list(wanted))
                    )
                )
            ).scalars().all()

        index: Dict[int, set] = {}
        for item in items:
            media_id = str(getattr(item, "media_id", "") or "")
            source = str(getattr(item, "media_source", "") or "")
            for row in wanted.get(media_id, []):
                row_source = str(getattr(row, "media_source", "") or "")
                if source and row_source and source != row_source:
                    continue
                season = int(getattr(row, "season", 0) or 0)
                episodes = autotoggle.seasoninfo_episodes(
                    getattr(item, "seasoninfo", None), season
                )
                if not episodes:
                    continue
                sid = int(getattr(row, "id", 0) or 0)
                if sid > 0:
                    index.setdefault(sid, set()).update(episodes)
        return index

    def _probe_candidates(
        self, rows: Any, episode_index: Any, today_date: Any, *, known: Dict[int, set]
    ) -> List[Any]:
        """挑出「值得问媒体库」的订阅，返回排好序的 ``(优先级, 最老缺集, row)``。

        只挑确有已播未入库的集的 TV 订阅：没有缺集的问了也白问，洗版订阅问的是
        「洗到顶没有」与库里有没有这一集无关。排序把**没有下载记录的排在前面**
        （缺集纯属推测，最需要核对），同类里「最老的缺集」优先。
        """
        from .core import autotoggle

        candidates: List[Any] = []
        for row in rows:
            if autotoggle.media_kind(row) != "tv":
                continue
            if autotoggle.is_best_version(row):
                # 洗版问的是「洗到顶没有」，跟库里有没有这一集无关
                continue
            media_id = str(getattr(row, "media_id", "") or "")
            if not media_id.isdigit():
                continue
            season = int(getattr(row, "season", 0) or 0)
            episodes = episode_index.get(
                (media_id, season if season > 0 else calendar_core.MOVIE_KEY)
            )
            if episodes is None:
                episodes = episode_index.get((media_id, season))
            pending = autotoggle.pending_episodes(row, episodes, today_date)
            if not pending:
                continue
            sid = int(getattr(row, "id", 0) or 0)
            covered = known.get(sid) or set()
            unknown = [pair for pair in pending if pair[1] not in covered]
            if not unknown:
                continue
            candidates.append(
                (
                    0 if not autotoggle.has_download_record(row) else 1,
                    min(pair[0] for pair in unknown),
                    row,
                )
            )

        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates

    async def _probe_missing_episodes(
        self,
        rows: Any,
        episode_index: Any,
        today_date: Any,
        *,
        budget_seconds: int,
        interval: float,
        known: Dict[int, set],
    ) -> Tuple[Dict[int, set], Dict[str, Any]]:
        """按时间预算逐条向媒体服务器核对，返回新确认的集号。

        候选与排序见 :meth:`_probe_candidates`。串行 + 间隔 + 时间预算，
        到点就停，剩下的下一轮再来。
        """
        import asyncio
        import time

        candidates = self._probe_candidates(
            rows, episode_index, today_date, known=known
        )

        stats: Dict[str, Any] = {
            "candidates": len(candidates),
            "probed": 0,
            "elapsed": 0,
            "deferred": 0,
        }
        if budget_seconds <= 0 or not candidates:
            # 0 秒 = 只读快照；没有候选也不用空转
            stats["deferred"] = len(candidates)
            return {}, stats

        started = time.monotonic()
        out: Dict[int, set] = {}
        probed = 0
        for _, _, row in candidates:
            if probed:
                await asyncio.sleep(max(0.0, float(interval)))
            if time.monotonic() - started >= budget_seconds:
                break
            present = await self._probe_one(row)
            probed += 1
            if present is not None:
                sid = int(getattr(row, "id", 0) or 0)
                if sid > 0:
                    out[sid] = present

        stats["probed"] = probed
        stats["elapsed"] = int(time.monotonic() - started)
        stats["deferred"] = max(0, len(candidates) - probed)
        if stats["deferred"]:
            logger.info(
                f"[SubscribeCenter] 媒体库核对用满 {stats['elapsed']} 秒预算，"
                f"本轮核对 {probed} 条，另有 {stats['deferred']} 条留待下一轮"
            )
        return out, stats

    async def _probe_one(self, row: Any) -> Optional[set]:
        """问一次宿主「这部剧这一季库里有哪几集」，失败返回 ``None``。

        为什么自己填 ``mediainfo.seasons``：宿主 ``get_no_exists_info`` 在
        ``seasons`` 为空时会**同步**再识别一次媒体（多一次 TMDB 请求），而订阅表
        里已经有季号和集数，直接填进去就能省掉。

        .. warning::
           宿主会按 ``meta.sea`` 过滤季：该季被过滤掉时返回的 ``no_exists``
            里没有这一季，看起来跟「全在库」一模一样。所以这里必须确认返回里
            **确实有这一季**，否则一律按「问不出结论」处理。
        """
        import asyncio

        try:
            from app.chain.download import DownloadChain
            from app.domain.metainfo import MetaInfo
            from app.schemas.context import MediaInfo
            from app.schemas.media import build_media_key, resolve_media_identity
            from app.schemas.types import MediaType
        except Exception as err:  # noqa: BLE001 - 宿主结构变了就安静跳过
            logger.debug(f"[SubscribeCenter] 媒体库核对不可用：{err}")
            return None

        name = str(getattr(row, "name", "") or "").strip()
        season = int(getattr(row, "season", 0) or 0)
        total = int(getattr(row, "total_episode", 0) or 0)
        start = int(getattr(row, "start_episode", 0) or 1)
        if not name or season <= 0 or total <= 0:
            return None
        if start <= 0:
            start = 1

        media_id = str(getattr(row, "media_id", "") or "")
        media_source = getattr(row, "media_source", None)
        try:
            meta = MetaInfo(name)
            meta.type = MediaType.TV
            meta.begin_season = season
            meta.end_season = None
            meta.media_source = media_source
            meta.media_id = media_id
            media = MediaInfo(
                type=MediaType.TV,
                title=name,
                year=str(getattr(row, "year", "") or "") or None,
                season=season,
                media_source=media_source,
                media_id=media_id,
                episode_group=getattr(row, "episode_group", None),
            )
            media.seasons = {season: list(range(start, start + total))}
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[SubscribeCenter] 构造核对参数失败 {name}：{err}")
            return None

        try:
            exists, no_exists = await asyncio.to_thread(
                DownloadChain().get_no_exists_info,
                meta,
                media,
                None,
                {season: total},
            )
        except Exception as err:  # noqa: BLE001 - 单条失败不影响其它
            logger.debug(f"[SubscribeCenter] 媒体库核对失败 {name}：{err}")
            return None

        full = set(range(start, start + total))
        if exists:
            return full
        if not isinstance(no_exists, dict) or not no_exists:
            return None

        try:
            key = build_media_key(resolve_media_identity(media)) or media_id
        except Exception:  # noqa: BLE001
            key = media_id
        entry = None
        for candidate in (key, media_id):
            if candidate and candidate in no_exists:
                entry = no_exists[candidate]
                break
        if not isinstance(entry, dict):
            return None
        season_entry = entry.get(season) or entry.get(str(season))
        if season_entry is None:
            return None
        missing = {
            int(item)
            for item in (getattr(season_entry, "episodes", None) or [])
            if str(item).strip().lstrip("-").isdigit()
        }
        return full - missing

    async def _auto_toggle_rows(self) -> List[Any]:
        """读出「本功能管得着」的订阅（``R`` / ``P`` / ``S``）。

        单独抽成方法：单测里直接替掉它就能绕开宿主 DB，不必给 ``app.db`` 打桩。
        """
        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

        from .core import autotoggle

        async with async_session_scope() as session:
            return (
                (
                    await session.execute(
                        select(Subscribe).where(
                            Subscribe.state.in_(autotoggle.WRITABLE_STATES)
                        )
                    )
                )
                .scalars()
                .all()
            )

    async def auto_toggle_plan(self, *, probe: bool = False) -> Dict[str, Any]:
        """算出「今天该启用 / 该暂停 / 不动」的清单，**不写库**。

        预览与真跑共用它 —— 用户点「预览」看到的和随后真跑的必须是同一套判定，
        否则调参就成了猜谜。

        :param probe: 是否真的去问媒体服务器。**预览必须为 False** ——
            200 条串行核对要几分钟，放在 HTTP 请求里会被网关 502 掐断；
            只有后台执行 / 定时任务才传 True。
        """
        from .core import autotoggle

        cfg = self._auto_toggle_config()
        today_date = today(self._tz())
        today_text = today_date.isoformat()
        rows = await self._auto_toggle_rows()

        # 复用日历那套「按 TMDB 每季 air_date 建的索引」（6 小时缓存）
        index = await self._episode_air_index(rows, today_text)
        # 电影没有播出表，只有发行日；不开电影时连请求都不发
        release_index = (
            await self._movie_release_index(rows) if cfg["movie_enabled"] else {}
        )
        state = self._auto_toggle_state()
        owned = state.get("owned")
        # 媒体库核对：快照 + 上次核对结果永远免费；实时探针只在 probe=True 时发
        library_index: Dict[int, set] = {}
        library_stats: Dict[str, Any] = {}
        if cfg["library_check"]:
            cached = state.get("library_probe")
            library_index, library_stats = await self._library_present_index(
                rows,
                index,
                today_date,
                probe=probe,
                cached=cached if isinstance(cached, dict) else None,
            )
        data = autotoggle.plan(
            rows,
            index,
            today_date,
            lookahead_days=cfg["lookahead_days"],
            keep_days=cfg["keep_days"],
            best_keep_days=cfg["best_keep_days"],
            best_mode=cfg["best_mode"],
            owned=owned if isinstance(owned, dict) else None,
            max_changes=cfg["max_changes"],
            release_index=release_index,
            movie_enabled=cfg["movie_enabled"],
            library_index=library_index,
        )
        data["config"] = cfg
        data["library"] = library_stats
        data["last_run"] = dict(state.get("last_run") or {})
        data["owned"] = len(
            [item for item in (owned or {}).values() if isinstance(item, dict)]
        )
        return data

    async def auto_toggle_run(self, *, reason: str = "manual") -> Dict[str, Any]:
        """执行一次自动启停：先算计划，再逐条写状态，最后更新接管表。

        :param reason: ``cron`` / ``manual`` —— 只用于记录，不影响判定
        """
        import time

        from .core import autotoggle

        cfg = self._auto_toggle_config()
        started_at = local_now_text(self._tz())
        # 先挂「正在跑」的牌子：前端据此轮询进度，也能防止用户连点两次
        # （进程崩了留下的牌子由 _auto_toggle_running() 按 30 分钟过期）
        state = self._auto_toggle_state()
        state["last_run"] = {
            **(state.get("last_run") or {}),
            "running": True,
            "started_at": started_at,
            "started_ts": time.time(),
            "reason": reason,
        }
        self._save_auto_toggle_state(state)
        try:
            return await self._auto_toggle_run_inner(
                reason=reason, started_at=started_at, cfg=cfg, state=state
            )
        finally:
            # 同一个 state 字典上摘牌子：重读一次会把执行体刚写的
            # ``owned`` / ``last_run`` 覆盖掉（``_auto_toggle_state()`` 返回
            # 的是插件数据里的那份快照）。
            last = dict(state.get("last_run") or {})
            last["running"] = False
            last.pop("started_ts", None)
            state["last_run"] = last
            self._save_auto_toggle_state(state)

    async def _auto_toggle_run_inner(
        self, *, reason: str, started_at: str, cfg: Dict[str, Any], state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """真正的执行体（``auto_toggle_run`` 负责挂/摘「正在跑」的牌子）。"""
        from .core import autotoggle

        planned = await self.auto_toggle_plan(probe=True)
        changes = planned.get("changes") or []
        today_text = str(planned.get("today") or today(self._tz()).isoformat())

        applied: List[int] = []
        failed: List[Dict[str, Any]] = []
        if changes:
            applied, failed = await self._apply_auto_toggle(changes)

        probe_cache = self.__dict__.pop("_auto_toggle_library_probe", None)
        if isinstance(probe_cache, dict) and probe_cache.get("items"):
            state["library_probe"] = probe_cache
        owned = autotoggle.next_owned(
            state.get("owned"),
            planned,
            today_text=today_text,
            applied_ids=applied,
        )
        applied_ids = set(applied)
        paused = len(
            [
                item
                for item in changes
                if item.get("action") == autotoggle.ACTION_PAUSE
                and int(item.get("id") or 0) in applied_ids
            ]
        )
        resumed = len(
            [
                item
                for item in changes
                if item.get("action") == autotoggle.ACTION_RESUME
                and int(item.get("id") or 0) in applied_ids
            ]
        )
        run_at = local_now_text(self._tz())
        state["owned"] = owned
        state["last_run"] = {
            "at": run_at,
            "started_at": started_at,
            "today": today_text,
            "reason": reason,
            "running": False,
            "planned": len(changes),
            "applied": len(applied),
            "paused": paused,
            "resumed": resumed,
            "failed": len(failed),
            "truncated": bool(planned.get("truncated")),
        }
        self._save_auto_toggle_state(state)

        result = {
            "today": today_text,
            "reason": reason,
            "planned": len(changes),
            "applied": len(applied),
            "paused": paused,
            "resumed": resumed,
            "failed": failed,
            "truncated": bool(planned.get("truncated")),
            "kept": planned.get("kept", 0),
            "skipped": planned.get("skipped", 0),
            "reasons": planned.get("reasons") or {},
            "owned": len(owned),
            "last_run": state["last_run"],
        }
        logger.info(
            f"[SubscribeCenter] 播出日自动启停（{reason}）："
            f"计划 {result['planned']} 条，暂停 {paused}，恢复 {resumed}，"
            f"失败 {len(failed)}，接管中 {len(owned)}"
        )
        if cfg["notify"] and (paused or resumed or failed):
            self._notify_auto_toggle(result)
        return result

    async def _apply_auto_toggle(
        self, changes: List[Dict[str, Any]]
    ) -> Tuple[List[int], List[Dict[str, Any]]]:
        """把计划里的状态改动写进宿主，返回 (成功 ID, 失败明细)。

        .. important::
           必须走宿主给「非 HTTP 入口」准备的 ``subscription_mutation_scope``：
           它在同一事务里暂存 ``SubscribeModified`` 事件（outbox），前端订阅列表
           与后续匹配才会立刻看到新状态。直接改库虽然也生效，但**不发事件**，
           属于绕过宿主契约的写法，只在宿主版本没有这个模块时降级使用。
        """
        applied: List[int] = []
        failed: List[Dict[str, Any]] = []

        actor = None
        try:
            from app.application.subscription.mutation import SubscriptionActor

            #: 插件代表「系统」写订阅：superuser 绕过 username 归属校验
            #: （宿主的 can_access 只认「本人」或超级用户）。
            actor = SubscriptionActor(name="SubscribeCenter", is_superuser=True)
        except Exception as err:  # noqa: BLE001 - 宿主结构不同，走降级
            logger.warning(f"[SubscribeCenter] 宿主缺少订阅写入口：{err}")

        scope = None
        if actor is not None:
            try:
                from app.startup.composition.subscription import (
                    subscription_mutation_scope as scope,
                )
            except Exception as err:  # noqa: BLE001
                logger.warning(
                    f"[SubscribeCenter] 未找到 subscription_mutation_scope，降级为直写库：{err}"
                )

        if scope is not None and actor is not None:
            try:
                await self._apply_with_scope(scope, actor, changes, applied, failed)
            except Exception as err:  # noqa: BLE001 - 提交失败 = 整批回滚
                logger.error(f"[SubscribeCenter] 自动启停提交失败，整批回滚：{err}")
                # 事务已回滚 → 一条都没落地，接管表按「全失败」处理，
                # 否则下一轮会以为这些订阅是我们暂停的，反而放弃接管。
                return [], [
                    {
                        "id": int(item.get("id") or 0),
                        "name": item.get("name"),
                        "error": f"提交失败：{err}",
                    }
                    for item in changes
                ]
            return applied, failed

        # ---- 降级路径：每条一个短事务，状态照改，但没有 outbox 事件
        from app.db import async_session_scope
        from app.db.oper.subscribe import SubscribeOper

        for item in changes:
            sid = int(item.get("id") or 0)
            target = str(item.get("target") or "")
            if not sid or target not in ("R", "S"):
                failed.append(
                    {"id": sid, "name": item.get("name"), "error": f"目标状态非法：{target!r}"}
                )
                continue
            try:
                async with async_session_scope() as session:
                    updated = await SubscribeOper(session).async_stage_update(
                        sid, {"state": target}
                    )
                    await session.commit()
                if updated is None:
                    failed.append(
                        {
                            "id": sid,
                            "name": item.get("name"),
                            "error": "宿主未找到该订阅（可能已被删除）",
                        }
                    )
                    continue
                applied.append(sid)
            except Exception as err:  # noqa: BLE001
                failed.append({"id": sid, "name": item.get("name"), "error": str(err)})
        return applied, failed

    async def _apply_with_scope(
        self,
        scope: Any,
        actor: Any,
        changes: List[Dict[str, Any]],
        applied: List[int],
        failed: List[Dict[str, Any]],
    ) -> None:
        """走宿主的 ``subscription_mutation_scope`` 逐条改状态。

        单条失败只记错，不影响其余；但**提交**失败会抛出，由调用方按整批
        回滚处理（``applied`` 里此时记的都不算数）。
        """
        async with scope() as service:
            for item in changes:
                sid = int(item.get("id") or 0)
                target = str(item.get("target") or "")
                if not sid or target not in ("R", "S"):
                    failed.append(
                        {
                            "id": sid,
                            "name": item.get("name"),
                            "error": f"目标状态非法：{target!r}",
                        }
                    )
                    continue
                try:
                    mutation = await service.update_status(sid, target, actor)
                except Exception as err:  # noqa: BLE001 - 单条失败不影响其余
                    failed.append({"id": sid, "name": item.get("name"), "error": str(err)})
                    continue
                if mutation is None:
                    failed.append(
                        {
                            "id": sid,
                            "name": item.get("name"),
                            "error": "宿主未找到该订阅（可能已被删除）",
                        }
                    )
                    continue
                applied.append(sid)

    def _notify_auto_toggle(self, result: Dict[str, Any]) -> None:
        """发送自动启停通知（只在真有改动时发）。"""
        lines = [
            f"恢复订阅：{result.get('resumed', 0)} 条",
            f"暂停订阅：{result.get('paused', 0)} 条",
        ]
        if result.get("truncated"):
            lines.append(
                f"已达单次上限（计划 {result.get('planned', 0)} 条），剩余下次再改"
            )
        if result.get("failed"):
            lines.append(f"失败：{len(result['failed'])} 条")
        lines.append(f"当前接管中：{result.get('owned', 0)} 条")
        try:
            self.post_message(title="胖虎订阅中心 播出日自动启停", text="\n".join(lines))
        except Exception as err:  # noqa: BLE001 - 通知失败不影响主流程
            logger.warning(f"[SubscribeCenter] 发送自动启停通知失败：{err}")

    def _auto_toggle_running(self) -> Dict[str, Any]:
        """后台是否正在跑（崩溃残留的牌子按 30 分钟过期）。"""
        import time

        last = self._auto_toggle_state().get("last_run") or {}
        if not isinstance(last, dict) or not last.get("running"):
            return {"running": False}
        try:
            started = float(last.get("started_ts") or 0)
        except (TypeError, ValueError):
            started = 0.0
        if started and time.time() - started < 1800:
            return {
                "running": True,
                "started_at": str(last.get("started_at") or ""),
                "reason": str(last.get("reason") or ""),
            }
        # 牌子挂了半小时还没摘 → 上次进程是被杀掉的，视为没在跑
        return {"running": False}

    async def auto_toggle_apply(self) -> Dict[str, Any]:
        """API 入口：**在后台**跑一次自动启停，立刻返回。

        .. important::
           真正的执行要串行核对媒体库（几分钟），放在 HTTP 请求里会被网关
           502 掐断。所以这里只负责挂线程，前端轮询 ``/auto_toggle`` 的
           ``last_run.running`` 看进度。
        """
        import threading

        running = self._auto_toggle_running()
        if running["running"]:
            raise RuntimeError("上一轮自动启停还在后台跑，请稍后再试")
        if self._bridge.busy:
            raise RuntimeError("发现任务正在运行，请稍后再试")
        try:
            thread = threading.Thread(
                target=self._auto_toggle_background,
                name="subscribecenter-autotoggle",
                daemon=True,
            )
            thread.start()
        except Exception as err:  # noqa: BLE001 - 起不了线程要如实告诉用户
            logger.error(f"[SubscribeCenter] 启动自动启停后台线程失败：{err}")
            raise RuntimeError(f"无法启动后台任务：{err}") from err
        return {
            "started": True,
            "running": True,
            "message": "已在后台开始执行，可以关掉这个窗口；刷新能看到进度",
        }

    def _auto_toggle_background(self) -> None:
        """后台线程体：经桥接在独立事件循环里跑一遍（与发现流水互斥）。"""
        try:
            result = self._bridge.run(
                lambda: self.auto_toggle_run(reason="manual"), timeout=1800
            )
        except Exception as err:  # noqa: BLE001 - 线程里必须自己吞异常
            logger.error(f"[SubscribeCenter] 后台自动启停失败：{err}", exc_info=True)
            return
        if result is None:
            logger.info("[SubscribeCenter] 自动启停：已有任务在跑，本次跳过")

    def auto_toggle_scheduled(self) -> None:
        """**同步**入口：由 apscheduler 在自己的线程里调用。

        该线程没有事件循环，必须经 :class:`PipelineBridge` 桥接；与「每日发现」
        共用同一把互斥锁 —— 两者都会改订阅表，不能同时跑。
        """
        if not self._auto_toggle_config()["enabled"]:
            logger.info("[SubscribeCenter] 自动启停未启用，跳过")
            return
        if self._auto_toggle_running()["running"]:
            logger.info("[SubscribeCenter] 自动启停：上一轮还在跑，本次跳过")
            return
        try:
            result = self._bridge.run(
                lambda: self.auto_toggle_run(reason="cron"), timeout=1800
            )
        except Exception as err:  # noqa: BLE001 - 定时任务不能把异常抛给调度器
            logger.error(f"[SubscribeCenter] 播出日自动启停失败：{err}", exc_info=True)
            return
        if result is None:
            logger.info("[SubscribeCenter] 自动启停：已有任务在跑，本次跳过")

    @staticmethod
    def _field(obj: Any, name: str, default: Any = None) -> Any:
        """兼容 dict 与 pydantic 对象两种形态地取字段。

        真机教训：``TmdbChain.async_tmdb_episodes`` 返回的是 ``TmdbEpisode`` 对象，
        用 ``ep.get("air_date")`` 会抛 ``AttributeError``，整月日历直接空掉。
        """
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    async def _episode_air_index(self, rows: Any, date_text: str) -> Dict[Any, List[Any]]:
        """按 TMDB 每季的 ``episodes[].air_date`` 建「播出索引」。

        宿主自己的日历页就是这么做的（前端 ``calendar-*.js`` 调
        ``tmdb/{id}/{season}``）：只有这样才能查**历史与未来**，
        光看订阅的 ``date`` / ``last_update`` 只有「下一次」。

        每季结果缓存 6 小时，最多并发 6 个请求；任何一部失败只影响它自己。
        """
        import asyncio
        import time

        from .core import calendar as calendar_core

        cache = self.__dict__.setdefault("_season_cache", {})
        ttl = 6 * 3600
        now = time.time()

        from .core import autotoggle

        # 电影的「播出日」= 发行日：与自动启停共用同一份 TMDB 发行记录（同一份
        # 6 小时缓存）。以前这里用 TMDB 顶层 ``release_date``（≈院线首映），
        # 结果是日历上「今天上映」而订阅其实还暂停着等数字版，两边对不上。
        movie_rows = [row for row in rows if autotoggle.media_kind(row) == "movie"]
        release_map: Dict[str, List[Any]] = {}
        if movie_rows:
            release_map = await self._movie_release_index(movie_rows)
        best_by_media = {
            str(getattr(row, "media_id", "") or ""): autotoggle.is_best_version(row)
            for row in movie_rows
        }

        targets: List[tuple] = []
        for row in rows:
            media_id = str(getattr(row, "media_id", "") or "")
            source = str(getattr(row, "media_source", "") or "")
            season = int(getattr(row, "season", 0) or 0)
            if not media_id.isdigit():
                continue
            if season <= 0:
                key = (media_id, calendar_core.MOVIE_KEY)
                if key in cache and now - cache[key][0] < ttl:
                    continue
                targets.append((media_id, calendar_core.MOVIE_KEY, source))
                continue
            # 有剧集组时按组取（MoviePilot 日历也是带 episode_group 请求的）
            group = str(getattr(row, "episode_group", "") or "").strip()
            key = (media_id, f"g:{group}" if group else season)
            if key in cache and now - cache[key][0] < ttl:
                continue
            targets.append((media_id, key[1], source))

        semaphore = asyncio.Semaphore(6)

        async def fetch(target: tuple) -> None:
            media_id, season_key, media_source = target
            key = (media_id, season_key)

            # ---- 电影：按发行日（数字 / 实体，与自动启停同源）----
            if season_key == calendar_core.MOVIE_KEY:
                basis, kind = autotoggle.movie_basis(
                    release_map.get(media_id),
                    best_version=bool(best_by_media.get(media_id)),
                )
                if not basis:
                    # release_dates 缺失时才退回院线日期 —— 宁可日期旧一点，
                    # 也别让这部电影从日历上整个消失。
                    basis = await self._movie_legacy_release(media_source, media_id)
                    kind = ""
                if basis:
                    cache[key] = (now, [(basis, 0)])
                    self._note_movie_kind(media_id, kind)
                return

            # ---- 剧集 / 剧集组 ----
            async with semaphore:
                episodes: List[tuple] = []
                try:
                    from app.chain.tmdb import TmdbChain

                    if isinstance(season_key, str) and season_key.startswith("g:"):
                        raw = await TmdbChain().async_tmdb_episodes(
                            tmdbid=int(media_id), season=0, episode_group=season_key[2:]
                        )
                    else:
                        raw = await TmdbChain().async_tmdb_episodes(
                            tmdbid=int(media_id), season=int(season_key)
                        )
                    episodes = [
                        (
                            str(self._field(ep, "air_date") or "")[:10],
                            int(self._field(ep, "episode_number") or 0),
                        )
                        for ep in raw or []
                        if self._field(ep, "air_date")
                    ]
                except Exception as err:  # noqa: BLE001 - 链不可用时回退
                    logger.debug(f"[SubscribeCenter] 链取季失败 {key}：{err}")

                if not episodes:
                    try:
                        #: 回退走模块层：这里必须自己建 ``TmdbApi`` ——
                        #: 同名变量早先只存在于循环外的局部作用域，漏了就
                        #: 抛 ``name 'tmdb' is not defined``，整季播出表变空。
                        from app.modules.themoviedb.tmdbapi import TmdbApi

                        tmdb = TmdbApi()
                        if isinstance(season_key, str) and season_key.startswith("g:"):
                            group_seasons = await asyncio.to_thread(
                                tmdb.get_tv_group_seasons, season_key[2:]
                            )
                            for season_item in group_seasons or []:
                                episodes.extend(
                                    (
                                        str(self._field(ep, "air_date") or "")[:10],
                                        int(self._field(ep, "episode_number") or 0),
                                    )
                                    for ep in self._field(season_item, "episodes", []) or []
                                    if self._field(ep, "air_date")
                                )
                        else:
                            detail = await asyncio.to_thread(
                                tmdb.get_tv_season_detail, int(media_id), int(season_key)
                            )
                            episodes = [
                                (
                                    str(self._field(ep, "air_date") or "")[:10],
                                    int(self._field(ep, "episode_number") or 0),
                                )
                                for ep in self._field(detail, "episodes", []) or []
                                if self._field(ep, "air_date")
                            ]
                    except Exception as err:  # noqa: BLE001
                        logger.debug(f"[SubscribeCenter] 回退取季失败 {key}：{err}")

                if episodes:
                    cache[key] = (now, episodes)

        if targets:
            await asyncio.gather(*(fetch(key) for key in targets))

        index: Dict[Any, List[Any]] = {}
        for row in rows:
            media_id = str(getattr(row, "media_id", "") or "")
            group = str(getattr(row, "episode_group", "") or "").strip()
            key = (media_id, f"g:{group}" if group else int(getattr(row, "season", 0) or 0))
            # build_today 用 (media_id, season) 查索引：这里统一按 season 再登记一份
            legacy_key = (media_id, int(getattr(row, "season", 0) or 0))
            if key in cache:
                index[legacy_key] = cache[key][1]
        return index

    async def api_calendar_day(self, date: str = "") -> Any:
        """单日日历接口（默认今天）。"""
        return await api_controller.api_calendar_day(self, date=date)

    async def api_calendar(self, month: str = "") -> Any:
        """日历接口（整月，month=YYYY-MM）。"""
        return await api_controller.api_calendar(self, month=month)

    async def api_card_theme(self) -> Any:
        """读取订阅卡片配色。"""
        return await api_controller.api_card_theme(self)

    async def api_card_theme_save(self, request: api_schemas.CardThemeRequest) -> Any:
        """保存订阅卡片配色（写入宿主自定义 CSS）。"""
        return await api_controller.api_card_theme_save(self, request)

    async def api_run_once(self, source: str = "") -> Any:
        """启动一次发现任务（后台跑，前端轮询 /run_once/result）。"""
        return await api_controller.api_run_once(self, source=source)

    async def api_run_once_result(self) -> Any:
        """读取发现任务的进度 / 结果。"""
        return await api_controller.api_run_once_result(self)

    async def api_history_clear(self) -> Any:
        """清空发现流水（清掉之后之前订过的作品才会被重新发现）。"""
        return await api_controller.api_history_clear(self)

    async def api_history_subscribe(
        self, request: api_schemas.HistorySubscribeRequest
    ) -> Any:
        """从发现流水手动补订阅（重新订阅 / 加入订阅）。"""
        return await api_controller.api_history_subscribe(self, request)

    async def api_preview(self) -> Any:
        """启动只读预览（后台跑，前端轮询 /preview/result）。"""
        return await api_controller.api_preview(self)

    async def api_preview_result(self) -> Any:
        """读取预览进度 / 结果。"""
        return await api_controller.api_preview_result(self)

    async def api_mapping_cache(self) -> Any:
        """查看身份映射缓存。"""
        return await api_controller.api_mapping_cache(self)

    async def api_mapping_fix(self, request: api_schemas.MappingFixRequest) -> Any:
        """人工修正一条身份映射。"""
        return await api_controller.api_mapping_fix(self, request)

    async def api_poster(self, path: str = "") -> Any:
        """代理 TMDB 海报（浏览器不可直连 image.tmdb.org）。"""
        return await api_controller.api_poster(self, path=path)

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时任务：一个全局任务 + 每个数据源可选的独立任务。

        :note: ``trigger`` 必须是 ``CronTrigger`` 对象；本方法整体兜底 ——
            任何异常都只记日志并降级为空列表（注册异常会拖垮插件加载）。
        :note: cron 在**注册时**读取，用户改配置后必须重新保存配置才会重建任务。
        """
        if not self._enabled():
            return []
        try:
            from apscheduler.triggers.cron import CronTrigger
        except Exception as err:  # pragma: no cover - 调度依赖缺失时降级
            logger.warning(f"[SubscribeCenter] 注册定时任务失败：{err}")
            return []

        services: List[Dict[str, Any]] = []
        cron = self._normalize_cron(self._config.get("cron"))
        if cron:
            try:
                services.append(
                    {
                        "id": "subscribecenter_discover",
                        "name": "胖虎订阅中心 每日发现",
                        "trigger": CronTrigger.from_crontab(cron),
                        "func": self.run_scheduled,
                    }
                )
            except Exception as err:  # pragma: no cover
                logger.warning(f"[SubscribeCenter] 全局定时任务注册失败：{err}")

        # 按播出日自动启停：独立任务、独立开关（与「每日发现」互不依赖）
        auto_cfg = self._auto_toggle_config()
        if auto_cfg["enabled"]:
            try:
                services.append(
                    {
                        "id": "subscribecenter_autotoggle",
                        "name": "胖虎订阅中心 播出日自动启停",
                        "trigger": CronTrigger.from_crontab(auto_cfg["cron"]),
                        "func": self.auto_toggle_scheduled,
                    }
                )
            except Exception as err:  # pragma: no cover
                logger.warning(f"[SubscribeCenter] 自动启停定时注册失败：{err}")

        # 每源独立定时：留空表示该源跟随全局任务，不单独调度
        for key, source, label in self._per_source_cron_jobs():
            raw = str(self._config.get(key) or "").strip()
            if not raw:
                continue
            try:
                crontab = self._normalize_cron(raw)
                services.append(
                    {
                        "id": f"subscribecenter_{source}",
                        "name": f"胖虎订阅中心 {label}",
                        "trigger": CronTrigger.from_crontab(crontab),
                        "func": lambda only_sources=[source]: self.run_scheduled(
                            only_sources=only_sources
                        ),
                    }
                )
            except Exception as err:  # pragma: no cover
                logger.warning(
                    f"[SubscribeCenter] {label} 独立定时注册失败（{raw}）：{err}"
                )
        return services

    @staticmethod
    def _per_source_cron_jobs() -> List[tuple]:
        """（配置键，源标识，显示名）——每源独立定时用。"""
        return [
            ("cron_tmdb", C.SOURCE_TMDB, "TMDB"),
            ("cron_anilist", C.SOURCE_ANILIST, "AniList"),
            ("cron_douban_rss", C.SOURCE_DOUBAN_RSS, "豆瓣榜单"),
            ("cron_hot_media", C.SOURCE_HOT_MEDIA, "热门媒体"),
        ]

    def stop_service(self) -> None:
        """释放插件资源；必须可重复、安全调用。

        v0.1.0 无自建线程/连接，只需清引用（流水线互斥锁是进程内的轻量状态，
        保留可避免重载后出现两把锁）。
        """
        self._resolver = None
        self._last_summary = {}

    # ------------------------------------------------------------------ 运行入口

    def run_scheduled(self, only_sources: Optional[List[str]] = None) -> None:
        """**同步**入口：由 apscheduler 在自己的线程里调用。

        该线程没有事件循环，因此必须经 :class:`PipelineBridge` 桥接。
        已有运行在跑时直接跳过（不排队）。
        """
        if not self._enabled():
            logger.info("[SubscribeCenter] 插件未启用，跳过本次定时发现")
            return
        started = local_now_text(self._tz())
        scope = "、".join(only_sources) if only_sources else "全部数据源"
        logger.info(f"[SubscribeCenter] 定时发现开始（{started}，{scope}）")
        summary = self._bridge.run(
            lambda: self._pipeline_coroutine(
                force_dry_run=False, only_sources=only_sources
            ),
            timeout=600,
        )
        if summary is None:
            logger.info("[SubscribeCenter] 已有流水线在运行，本次定时发现跳过")
            return
        self._after_run(summary)

    async def run_once(self, source: str = "") -> Dict[str, Any]:
        """**异步**入口：供 ``POST /run_once`` 调用。

        与定时任务共用同一把互斥锁；已在运行时返回 ``skipped=True``。
        """
        only = [source] if source else None
        summary = await self._bridge.run_async(
            lambda: self._pipeline_coroutine(force_dry_run=False, only_sources=only),
            timeout=600,
        )
        return self._run_once_payload(summary)

    def _run_once_payload(self, summary: Optional[RunSummary]) -> Dict[str, Any]:
        """把一次真实运行的 ``RunSummary`` 转成前端要的载荷（并落流水）。"""
        if summary is None:
            return {"accepted": True, "skipped": True, "summary": self._last_summary}
        self._after_run(summary)
        return {"accepted": True, "skipped": False, "summary": summary.to_summary()}

    async def preview(self) -> Dict[str, Any]:
        """**只读预览**：跑完整流水线但不写入，返回「会订哪些」。

        这是调参的主要工具 —— 每次改门槛/窗口都真跑一次会消耗每日额度、
        还要在真机上来回试。预览不写订阅、不计入额度，直接把候选列出来。

        :return: ``{"skipped": bool, "summary": {...}, "items": [...], "rejections": {...}}``
        """
        summary = await self._bridge.run_async(
            lambda: self._pipeline_coroutine(force_dry_run=True), timeout=600
        )
        return self._preview_payload(summary)

    def _preview_payload(self, summary: Optional[RunSummary]) -> Dict[str, Any]:
        """把一次预览的 ``RunSummary`` 转成前端要的载荷。"""
        if summary is None:
            return {"skipped": True, "summary": self._last_summary, "items": []}

        # 预览只留流水，不动今日计数
        self._after_run(summary, is_preview=True)

        items: List[Dict[str, Any]] = []
        outcomes = summary.report.outcomes if summary.report else []
        # 只把「会写入」的条目算进会订列表。
        #
        # 真机 bug：旧实现把**所有** writer 产出都塞进 items —— 包括
        # skipped_already_subscribed / skipped_finished / pending_review，
        # 于是界面显示「会订 215 条」，而实际只有 0 条会写（那 215 条里
        # 79 条已订阅、118 条已播完、18 条待确认）。
        writable_decisions = {C.DECISION_ADDED, C.DECISION_SKIPPED_DRY_RUN}
        for outcome in outcomes:
            if outcome.decision not in writable_decisions:
                continue
            item = outcome.item
            identity = item.resolved
            items.append(
                {
                    "title": item.title,
                    "year": item.year,
                    "media_type": item.media_type,
                    "release_date": item.release_date,
                    "popularity": item.popularity,
                    "rating": item.rating,
                    "language": str((item.raw or {}).get("original_language") or ""),
                    "source": item.source,
                    "confidence": item.confidence,
                    "media_source": identity.media_source if identity else "",
                    "media_id": identity.media_id if identity else "",
                    "decision": outcome.decision,
                    "reason": outcome.reason,
                }
            )
        items.sort(key=lambda row: -(row.get("popularity") or 0.0))

        data = summary.to_summary()
        return {
            "skipped": False,
            "summary": data,
            "items": items,
            "rejections": data.get("rejected_reasons") or {},
        }

    # ------------------------------------------------ 后台任务（绕开网关超时）
    #
    # 真机：预览要拉四个源、再逐条解析身份，动辄一两分钟；而宿主前面的网关
    # 几十秒就断，浏览器只会看到「HTTP 502 请求被网关中断」。这类请求不能
    # 同步等结果，改成「POST 启动 → 立即返回 → GET 轮询」，网关只看到秒级响应。

    def _task_slot(self, name: str) -> Dict[str, Any]:
        """取（或建）一个后台任务槽，跨请求保存进度与结果。"""
        slots = self.__dict__.setdefault("_task_slots", {})
        return slots.setdefault(
            name,
            {
                "running": False,
                "started_at": "",
                "started_ts": 0.0,
                "error": "",
                "result": {},
            },
        )

    def _task_state(self, name: str) -> Dict[str, Any]:
        """读任务状态；超过 1 小时的「运行中」视为崩溃残留并自动复位。"""
        slot = self._task_slot(name)
        if slot.get("running") and time.time() - float(slot.get("started_ts") or 0.0) > 3600:
            slot["running"] = False
            slot["error"] = slot.get("error") or "上一次运行超过 1 小时未结束，状态已复位"
        return {
            "name": name,
            "running": bool(slot.get("running")),
            "started": bool(slot.get("running")),
            "started_at": str(slot.get("started_at") or ""),
            "error": str(slot.get("error") or ""),
            "result": dict(slot.get("result") or {}),
            "message": "",
        }

    def _start_task(self, name: str, factory: Any) -> Dict[str, Any]:
        """启动后台任务并立即返回（同一任务不并发，也不与定时任务抢锁）。"""
        state = self._task_state(name)
        if state["running"]:
            return {**state, "started": False, "message": "上一次还在跑，请稍等"}
        if self._bridge.busy:
            return {
                **state,
                "running": True,
                "started": False,
                "message": "已有发现任务正在运行，本次未启动",
            }
        slot = self._task_slot(name)
        slot.update(
            {
                "running": True,
                "started_at": local_now_text(self._tz()),
                "started_ts": time.time(),
                "error": "",
                "result": {},
            }
        )
        started_at = slot["started_at"]

        def runner() -> None:
            """后台线程：bridge.run 自带互斥，异常必须自己兜住。"""
            try:
                slot["result"] = self._bridge.run(factory, timeout=1800) or {}
            except Exception as err:  # noqa: BLE001 - 线程里没人接异常
                slot["error"] = f"{type(err).__name__}: {err}"
                logger.error(f"[SubscribeCenter] 后台任务 {name} 失败：{err}", exc_info=True)
            finally:
                slot["running"] = False

        threading.Thread(
            target=runner, name=f"subscribecenter-{name}", daemon=True
        ).start()
        return {
            "name": name,
            "running": True,
            "started": True,
            "started_at": started_at,
            "error": "",
            "result": {},
            "message": "已在后台开始，稍后自动刷新结果",
        }

    def start_preview(self) -> Dict[str, Any]:
        """启动只读预览（后台跑，立即返回）。"""
        return self._start_task("preview", lambda: self._preview_job())

    async def _preview_job(self) -> Dict[str, Any]:
        """后台线程里的预览协程：不经过 bridge（锁已由 ``run`` 持有）。"""
        summary = await self._pipeline_coroutine(force_dry_run=True)
        return self._preview_payload(summary)

    def preview_state(self) -> Dict[str, Any]:
        """读取预览进度 / 结果。"""
        return self._task_state("preview")

    def start_run_once(self, source: str = "") -> Dict[str, Any]:
        """启动一次真实发现（后台跑，立即返回）。"""
        only = [source] if source else None
        return self._start_task("run_once", lambda: self._run_once_job(only))

    async def _run_once_job(self, only: Optional[List[str]]) -> Dict[str, Any]:
        summary = await self._pipeline_coroutine(
            force_dry_run=False, only_sources=only
        )
        return self._run_once_payload(summary)

    def run_once_state(self) -> Dict[str, Any]:
        """读取「立即运行一次」的进度 / 结果。"""
        return self._task_state("run_once")

    async def _pipeline_coroutine(
        self, *, force_dry_run: bool = False, only_sources: Optional[List[str]] = None
    ) -> RunSummary:
        """构造并执行一次流水线（三种入口共用的唯一实现）。

        :param force_dry_run: 强制只读（预览用）。预览**不消耗**每日写入额度。
        :param only_sources: 只跑这些源（每源独立定时用）；None = 全部已启用源。
        """
        resolver = self._resolver
        if resolver is None:
            # init_plugin 未跑过（例如直接调 API）：按需重建，避免 AttributeError
            from .core.host import HostTmdbResolver

            resolver = IdentityResolver(HostTmdbResolver(), self._cache)
            self._resolver = resolver


        # 映射缓存攒批落盘：一次运行可能解析 200+ 条，逐条落盘等于 200+ 次
        # 数据库写入。batch() 期间只标脏，退出时统一写一次。
        with self._cache.batch():
            adapters = self._build_sources()
            if only_sources:
                wanted = {str(item) for item in only_sources}
                adapters = [
                    adapter for adapter in adapters if adapter.name in wanted
                ]
            return await run_pipeline(
                sources=adapters,
                enabled=self._enabled_sources(),
                resolver=resolver,
                writer=self._writer,
                config=self._config,
                future_days=self._int_config("tmdb_future_days", C.DEFAULT_FUTURE_DAYS),
                min_rating=self._float_config("min_rating_tmdb", C.DEFAULT_MIN_RATING),
                min_popularity=self._float_config("min_popularity", C.DEFAULT_MIN_POPULARITY),
                # 豆瓣「想看人数」门槛（独立于 TMDB popularity，量纲是人数）
                min_want=self._float_config("douban_min_want", 0.0),
                resolve_concurrency=self._int_config("resolve_concurrency", 8),
                # 窗口与评分门槛**按源独立**：TMDB 与 Bangumi 的配置项不同，
                # 共用一个值会把窗口更窄的源错误放行（真机踩过）。
                future_days_by_source=self._future_days_by_source(),
                min_rating_by_source=self._min_rating_by_source(),
                min_popularity_by_source=self._min_popularity_by_source(),
                # 黑名单第三层（TMDB keyword）只在配置打开时才会被调用
                keyword_lookup=self._tmdb_keywords,
                dry_run=force_dry_run,
                already_written_today=self._written_today(),
                tz_name=self._tz(),
        )

    async def _tmdb_keywords(self, media_type: str, media_id: str) -> List[str]:
        """查一条 TMDB 关键词（「排除题材」第三层用）。

        只有 ``blacklist_tmdb_keywords`` 打开时才会被流水线调用，而且只对
        「已通过全部其它过滤、即将写入」的条目 —— 每条多一次 TMDB 详情请求，
        不能摊到几百条候选上。

        为什么需要这一层：TMDB 的类型表里**没有「同性」**（见
        ``core/blacklist.py`` 的 GENRE_NAMES），豆瓣 RSS 能用 ``category``
        里的中文字样兜住，但纯 TMDB 源没有那段文本，只能靠 keyword。

        查询结果按 ``媒体类型:ID`` 缓存在进程内 —— 同一部剧同一次运行里
        可能被判定多次（预览 + 正式）时不再重复请求。
        """
        cache = self.__dict__.setdefault("_tmdb_keyword_cache", {})
        key = f"{media_type}:{media_id}"
        if key in cache:
            return cache[key]
        tmdb_id = str(media_id or "").strip()
        if not tmdb_id.isdigit():
            cache[key] = []
            return []
        if media_type == C.MEDIA_TYPE_TV:
            path = f"/tv/{tmdb_id}/keywords"
        else:
            path = f"/movie/{tmdb_id}/keywords"
        try:
            from .core.host import HostTmdbResolver

            payload = await HostTmdbResolver._tmdb_get(path)
        except Exception as err:  # noqa: BLE001 - 查不到就放行，交给其它层
            logger.debug(f"[SubscribeCenter] 查 TMDB 关键词失败 {path}：{err}")
            cache[key] = []
            return []
        # 电影接口回 ``keywords``，剧集接口回 ``results`` —— 两个都认
        entries = (payload or {}).get("keywords") or (payload or {}).get("results") or []
        keywords = [
            str(entry.get("name") or "")
            for entry in entries
            if isinstance(entry, dict) and entry.get("name")
        ]
        if len(cache) > 5000:
            cache.clear()
        cache[key] = keywords
        return keywords

    # ---------------------------------------------------------- 排除规则（黑名单）

    def blacklist_rules(self) -> Any:
        """当前生效的排除规则（总开关关闭时返回的空规则 ``active=False``）。"""
        from .core import blacklist as blacklist_core

        return blacklist_core.rules_from_config(self._config or {})

    def blacklist_meta(self) -> Dict[str, Any]:
        """给前端渲染用的元数据：内置题材预设 + TMDB 类型中英对照。

        预设**只有用户勾选才生效**（``blacklist_presets`` 默认空），这里只负责
        把「会匹配哪些词」如实摊开给用户看 —— 黑名单是静默生效的规则，
        不把词摊开等于让人蒙着眼排除。
        """
        from .core import blacklist as blacklist_core

        config = self._config or {}
        return {
            "enabled": bool(config.get("blacklist_enabled")),
            "presets": [
                {
                    "key": preset["key"],
                    "label": preset["label"],
                    "hint": preset.get("hint", ""),
                    "words": list(preset["words"]),
                }
                for preset in blacklist_core.PRESETS
            ],
            "genre_names": {
                str(genre_id): name
                for genre_id, name in blacklist_core.GENRE_NAMES.items()
            },
        }

    def blacklist_test(
        self,
        *,
        title: str = "",
        original_title: str = "",
        media_type: str = "tv",
        tags: str = "",
        genre_ids: Optional[List[int]] = None,
        keywords: Optional[List[str]] = None,
        rules_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """自测一条内容会不会被排除规则拦下（配置页「试一下」用）。

        走的是和流水线**完全相同**的判定函数（``check_item`` / ``check_keywords``），
        不做任何简化 —— 否则自测通过、真跑被拦，等于没测。

        ``rules_config`` 传的是**页面上当前填的**（可能还没保存）规则：
        自测若只认已保存的配置，勾完预设不点保存就会得到「不会被拦」，
        用户会以为功能坏了。
        """
        from .core import blacklist as blacklist_core
        from .core.model import DiscoveredItem

        rules = blacklist_core.rules_from_config(
            rules_config if isinstance(rules_config, dict) and rules_config else (self._config or {})
        )
        item = DiscoveredItem(
            source="blacklist_test",
            source_id="blacklist_test",
            title=str(title or ""),
            media_type=str(media_type or C.MEDIA_TYPE_TV),
            original_title=str(original_title or "") or None,
            raw={
                "genre": str(tags or ""),
                "genre_ids": [
                    int(str(entry).strip())
                    for entry in (genre_ids or [])
                    if str(entry).strip().isdigit()
                ],
            },
        )
        reason = blacklist_core.check_item(rules, item)
        if not reason and keywords:
            reason = blacklist_core.check_keywords(rules, keywords)
        rule_count = len(rules.words) + len(rules.movie_genres) + len(rules.tv_genres)
        hint = ""
        if not reason:
            if rule_count <= 0:
                hint = (
                    "当前没有任何生效规则：先在「排除类型」里勾类型，"
                    "或勾选「排除题材」里的预设，再加自定义词。"
                )
            elif not str(tags or "").strip() and not genre_ids:
                hint = (
                    "只在片名里找题材词，测不出「同性」这类命中 —— 豆瓣来源的题材串"
                    "里才会带这个词。把「题材串」填成「2026 / 泰国 / 剧情 同性」再试；"
                    "纯 TMDB 来源请打开「额外查 TMDB 关键词」。"
                )
        return {
            "matched": bool(reason),
            "reason": reason,
            "rules": rule_count,
            "hint": hint,
        }

    # -------------------------------------------------- 体检：已有订阅 vs 排除规则
    #
    # 真机反馈：勾好黑名单、发现流水里也写着「命中排除题材」，宿主的订阅列表里
    # 却**确实有这部剧**。原因是黑名单只挂在「自动发现 → 写订阅」这条线上，
    # 只拦将要写入的条目；已经存在的订阅（早先订的、重装后恢复数据库带回来的、
    # 或从发现流水手动点「加入订阅」的）它一概不管。
    #
    # 体检就是补这一刀：把已有订阅逐条按**同一套规则**判一遍，只出报告不动手；
    # 要不要暂停由用户在页面上勾着决定。

    async def _subscription_rows(self) -> List[Any]:
        """读宿主全部订阅（含暂停/待定），供体检使用。

        单独抽出来（不在 ``blacklist_audit`` 里内联查询）是为了单测能直接
        替换成假数据，不必给 ``app.db`` 打桩。
        """
        from sqlalchemy import select

        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe

        async with async_session_scope() as session:
            result = await session.execute(select(Subscribe))
            return list(result.scalars().all())

    async def _audit_one(
        self,
        row: Any,
        rules: Any,
        *,
        want_keywords: bool,
    ) -> Dict[str, Any]:
        """核对一条已有订阅；返回 ``{id, name, ..., reason}``。

        ``reason`` 为空表示「没命中」；``skipped`` 非空表示「这条没法核」
        （来源不是 TMDB、查详情失败等），必须和「没命中」区分开 —— 否则
        一条查失败的订阅会被当成「体检通过」，用户白高兴。
        """
        from .core import autotoggle
        from .core import blacklist as blacklist_core
        from .core import constants as C2

        sid = int(getattr(row, "id", 0) or 0)
        name = str(getattr(row, "name", "") or "")
        entry: Dict[str, Any] = {
            "id": sid,
            "name": name,
            "season": int(getattr(row, "season", 0) or 0),
            "state": str(getattr(row, "state", "") or ""),
            "media_source": str(getattr(row, "media_source", "") or ""),
            "media_id": str(getattr(row, "media_id", "") or ""),
            "reason": "",
            "skipped": "",
            "poster": "",
        }
        kind = autotoggle.media_kind(row)
        if kind not in ("tv", "movie"):
            entry["skipped"] = "不是剧集/电影订阅"
            return entry
        source = entry["media_source"]
        if source != "themoviedb":
            # 豆瓣/AniList 订阅存的是它们自己的 ID，要核对得先花一次识别请求；
            # 体检是「先看一遍」的功能，不做隐式转换，如实说「核不了」。
            entry["skipped"] = f"来源是 {source or '未知'}，不是 TMDB，未能核对"
            return entry
        tmdb_id = entry["media_id"]
        if not tmdb_id.isdigit():
            entry["skipped"] = "缺少 TMDB ID"
            return entry

        media_type = C2.MEDIA_TYPE_TV if kind == "tv" else C2.MEDIA_TYPE_MOVIE
        entry["media_type"] = media_type
        path = f"{'/tv' if kind == 'tv' else '/movie'}/{tmdb_id}"
        payload: Dict[str, Any] = {}
        try:
            from .core.host import HostTmdbResolver

            payload = await HostTmdbResolver._tmdb_get(path) or {}
        except Exception as err:  # noqa: BLE001 - 查不到就如实标「未核对」
            entry["skipped"] = f"查 TMDB 详情失败：{err}"
            return entry

        genres = [
            entry.get("id")
            for entry in (payload.get("genres") or [])
            if isinstance(entry, dict) and entry.get("id")
        ]
        original = str(
            payload.get("original_name") or payload.get("original_title") or ""
        )
        entry["original_title"] = original
        poster = str(payload.get("poster_path") or "")
        if poster:
            entry["poster"] = poster

        keywords: List[str] = []
        if want_keywords:
            try:
                keywords = await self._tmdb_keywords(media_type, tmdb_id)
            except Exception:  # noqa: BLE001 - 关键词查不到就只按类型/标题判
                keywords = []

        entry["genres"] = genres
        entry["keywords"] = keywords[:20]
        entry["reason"] = blacklist_core.check_parts(
            rules,
            name=name,
            original=original,
            media_type=media_type,
            genre_ids=genres,
            keywords=keywords,
        )
        return entry

    async def blacklist_audit(self, *, budget_seconds: int = 240) -> Dict[str, Any]:
        """按当前排除规则体检**已有订阅**（只读，不改任何东西）。

        每条订阅要查一次 TMDB 详情（拿 genres / 原名），开了
        ``blacklist_tmdb_keywords`` 还要再查一次关键词，所以整体放进后台任务
        并带时间预算：到点就把剩下的标成「未核对」，下次再跑。

        「查不了」与「没命中」严格分开 —— 见 :meth:`_audit_one` 的 ``skipped``。
        """
        from .core import blacklist as blacklist_core

        rules = self.blacklist_rules()
        result: Dict[str, Any] = {
            "active": bool(rules.active),
            "rules": len(rules.words) + len(rules.movie_genres) + len(rules.tv_genres),
            "tmdb_keywords": bool(rules.tmdb_keywords),
            "total": 0,
            "checked": 0,
            "skipped": 0,
            "unchecked": 0,
            "hits": [],
            "uncheckable": [],
            "elapsed": 0.0,
            "budget_seconds": int(budget_seconds or 0),
            "truncated": False,
            "at": local_now_text(self._tz()),
        }
        if not rules.active:
            result["message"] = "当前没有任何排除规则，先在上面配好规则再体检"
            return result

        started = time.monotonic()
        rows = await self._subscription_rows()
        result["total"] = len(rows)
        if not rows:
            result["message"] = "宿主里还没有任何订阅"
            result["elapsed"] = round(time.monotonic() - started, 1)
            return result

        semaphore = asyncio.Semaphore(4)
        want_keywords = bool(rules.tmdb_keywords)
        budget = float(budget_seconds or 0)
        exhausted = {"flag": False}

        async def one(row: Any) -> Optional[Dict[str, Any]]:
            if exhausted["flag"]:
                return None
            async with semaphore:
                if exhausted["flag"]:
                    return None
                try:
                    entry = await self._audit_one(row, rules, want_keywords=want_keywords)
                except Exception as err:  # noqa: BLE001 - 单条失败不影响其余
                    entry = {
                        "id": int(getattr(row, "id", 0) or 0),
                        "name": str(getattr(row, "name", "") or ""),
                        "season": int(getattr(row, "season", 0) or 0),
                        "state": str(getattr(row, "state", "") or ""),
                        "reason": "",
                        "skipped": f"核对异常：{err}",
                    }
                if budget > 0 and time.monotonic() - started > budget:
                    exhausted["flag"] = True
                return entry

        entries = [
            entry for entry in await asyncio.gather(*(one(row) for row in rows))
            if entry is not None
        ]
        result["checked"] = sum(1 for entry in entries if not entry.get("skipped"))
        result["skipped"] = sum(1 for entry in entries if entry.get("skipped"))
        result["hits"] = [entry for entry in entries if entry.get("reason")]
        result["uncheckable"] = [
            entry for entry in entries if entry.get("skipped")
        ][:50]
        missing = result["total"] - len(entries)
        result["unchecked"] = max(0, missing)
        result["truncated"] = bool(missing) or exhausted["flag"]
        result["elapsed"] = round(time.monotonic() - started, 1)
        result["at"] = local_now_text(self._tz())
        if result["truncated"]:
            result["message"] = (
                f"到 {result['budget_seconds']} 秒预算上限，还有 {result['unchecked']} 条没核；"
                "再点一次会接着核（已核过的仍会重核，结果只读不落库）"
            )
        return result

    def start_blacklist_audit(self) -> Dict[str, Any]:
        """启动体检（后台线程），立刻返回状态。"""
        return self._start_task("blacklist_audit", lambda: self.blacklist_audit())

    def blacklist_audit_state(self) -> Dict[str, Any]:
        """读体检进度 / 结果。"""
        return self._task_state("blacklist_audit")

    async def blacklist_sweep(
        self, *, ids: List[int], action: str = "pause"
    ) -> Dict[str, Any]:
        """把体检出来的订阅批量暂停（``S``）或恢复（``R``）。

        只改状态、不删订阅 —— 删订阅不可逆（宿主会把记录移进订阅历史），
        而「暂停」随时能改回来，用户点错也不至于丢东西。
        """
        target = "S" if str(action or "pause") == "pause" else "R"
        wanted = [int(sid) for sid in (ids or []) if int(sid or 0) > 0]
        if not wanted:
            raise ValueError("没有选中任何订阅")
        changes = [{"id": sid, "name": "", "target": target} for sid in wanted]
        applied, failed = await self._apply_auto_toggle(changes)
        return {
            "action": "pause" if target == "S" else "resume",
            "requested": len(wanted),
            "applied": len(applied),
            "failed": len(failed),
            "errors": failed[:20],
        }

    def _future_days_by_source(self) -> Dict[str, int]:
        """返回各数据源的发现窗口天数（天）。"""
        default_days = self._int_config("tmdb_future_days", C.DEFAULT_FUTURE_DAYS)
        return {
            C.SOURCE_TMDB: default_days,
            C.SOURCE_ANILIST: self._int_config("anilist_future_days", C.DEFAULT_FUTURE_DAYS),
            C.SOURCE_DOUBAN_RSS: self._int_config("douban_future_days", C.DEFAULT_FUTURE_DAYS),
        }

    def _min_popularity_by_source(self) -> Dict[str, float]:
        """返回各数据源的最低关注度门槛。

        **必须按源区分**：TMDB 的 popularity 中位数只有 3（>=15 才算热门），
        而 AniList 的 popularity 冷门番也有上千 —— 共用一个 15 等于对
        AniList 完全不过滤，会把一堆冷门番订进来。
        """
        default_popularity = self._float_config("min_popularity", C.DEFAULT_MIN_POPULARITY)
        return {
            C.SOURCE_TMDB: default_popularity,
            C.SOURCE_ANILIST: self._float_config(
                "anilist_min_popularity", 1000.0
            ),
        }

    def _min_rating_by_source(self) -> Dict[str, float]:
        """返回各数据源的最低评分门槛。

        TMDB 与 Bangumi 的评分量纲不同（Bangumi 社区评分普遍偏高），
        共用一个门槛不合理，因此按源独立配置。
        """
        default_rating = self._float_config("min_rating_tmdb", C.DEFAULT_MIN_RATING)
        return {
            C.SOURCE_TMDB: default_rating,
            C.SOURCE_ANILIST: self._float_config("min_rating_anilist", C.DEFAULT_MIN_RATING),
            C.SOURCE_DOUBAN_RSS: self._float_config("min_rating_douban", C.DEFAULT_MIN_RATING),
        }

    def _build_sources(self) -> List[SourceAdapter]:
        """构造已实现的数据源适配器列表。

        .. note::
           TMDB 源用模块层 ``TmdbApi`` 而不是 ``TmdbChain.tmdb_discover``：
           后者的日期过滤参数 ``release_date.gte`` 会被 TMDB 静默忽略（0.2.0 真实事故，
           详见 ``sources/tmdb.py`` 的模块文档）。
        """
        sources: List[SourceAdapter] = []
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi

            sources.append(TmdbSource(TmdbApi()))
        except Exception as err:  # noqa: BLE001 - 宿主缺 TMDB 时该源不可用，不阻塞其他源
            logger.warning(f"[SubscribeCenter] TMDB 源不可用：{err}")

        try:
            from .sources.anilist import AniListSource

            sources.append(AniListSource())
        except Exception as err:  # noqa: BLE001 - 单源构造失败不阻塞其他源
            logger.warning(f"[SubscribeCenter] AniList 源不可用：{err}")

        try:
            from .sources.hot_media import HotMediaSource

            sources.append(HotMediaSource())
        except Exception as err:  # noqa: BLE001 - 单源构造失败不阻塞其他源
            logger.warning(f"[SubscribeCenter] 热门媒体源不可用：{err}")

        try:
            from .sources.douban_rss import DoubanRssSource

            sources.append(DoubanRssSource())
        except Exception as err:  # noqa: BLE001 - 单源构造失败不阻塞其他源
            logger.warning(f"[SubscribeCenter] 豆瓣 RSS 源不可用：{err}")
        return sources

    def _enabled_sources(self) -> List[str]:
        """返回配置中已启用**且已实现**的源标识。"""
        mapping = {
            C.SOURCE_TMDB: "enable_tmdb",
            C.SOURCE_ANILIST: "enable_anilist",
            C.SOURCE_DOUBAN_RSS: "enable_douban_rss",
        }
        enabled: List[str] = []
        for source, key in mapping.items():
            if not self._config.get(key):
                continue
            if source not in C.IMPLEMENTED_SOURCES:
                logger.info(
                    f"[SubscribeCenter] 数据源 {source} 已在配置中启用，但当前版本（"
                    f"{C.PLUGIN_VERSION}）尚未实现，本次跳过"
                )
                continue
            enabled.append(source)
        return enabled

    # ------------------------------------------------------------------ 运行后处理

    def _after_run(self, summary: RunSummary, *, is_preview: bool = False) -> None:
        """落流水、更新状态、记录日志、按需通知。

        :param is_preview: 只读预览。**不累加每日写入计数**，也不影响通知。
        """
        data = summary.to_summary()
        self._last_summary = data
        self._last_run = summary.finished_at or local_now_text(self._tz())

        # 各源状态
        for result in summary.sources:
            self._source_state[result.source] = {
                "enabled": result.source in self._enabled_sources(),
                "implemented": result.source in C.IMPLEMENTED_SOURCES,
                "last_run": self._last_run,
                "last_count": len(result.items),
                "last_error": result.error,
            }

        # 流水（写入结果 + 被过滤的条目）
        outcomes: List[WriteOutcome] = list(summary.prefiltered)
        if summary.report:
            outcomes.extend(summary.report.outcomes)
            if not is_preview:
                for _ in summary.report.added:
                    self._bump_daily_counter()

        self._append_history(outcomes, run_at=self._last_run)

        state = self._state()
        state["last_run"] = self._last_run
        state["last_summary"] = data
        self._save_state(state)

        self._log_summary(summary)
        if self._config.get("notify"):
            self._notify_summary(summary, is_preview=is_preview)

    def _log_summary(self, summary: RunSummary) -> None:
        """输出结构化摘要日志（开发文档 §12）。"""
        added = summary.report.added if summary.report else []
        for outcome in added:
            item = outcome.item
            resolved = item.resolved
            identity = f"{resolved.media_source} {resolved.media_id}" if resolved else "—"
            logger.info(
                f"[新增] {item.title_year} ({identity}) 来源={item.source} "
                f"放送={item.release_date} 身份={item.confidence} 订阅ID={outcome.subscribe_id}"
            )
        skipped = list(summary.prefiltered)
        if summary.report:
            skipped = [o for o in summary.report.outcomes if not o.added] + skipped
        for outcome in skipped[:60]:
            tag = "待确认" if outcome.decision == C.DECISION_PENDING_REVIEW else "跳过"
            logger.info(
                f"[{tag}] {outcome.item.title_year} 原因={outcome.reason or outcome.decision}"
            )
        if len(skipped) > 60:
            logger.info(f"[跳过] 另有 {len(skipped) - 60} 条未逐条列出")
        for name in summary.failed_sources:
            logger.warning(f"[失败] 数据源 {name}")
        data = summary.to_summary()
        logger.info(
            f"[SubscribeCenter] 本次运行完成：拉取 {data.get('fetched', 0)} 条 / "
            f"新增 {data.get('added', 0)} 条 / 跳过 {data.get('skipped', 0)} 条 / "
            f"待确认 {data.get('pending_review', 0)} 条"
            + ("（dry-run，未写入）" if summary.dry_run else "")
            + ("（触达每日上限）" if data.get("limit_hit") else "")
        )
        # 把本次新增的标题也打出来：只看数字无法判断「订得对不对」，
        # 而这个问题在真机上已经踩过两次（订了 29 部冷门片）。
        titles = self._added_titles(summary)
        if titles:
            logger.info(f"[新增明细] {'；'.join(titles)}")

    @staticmethod
    def _added_titles(summary: RunSummary, limit: int = 20) -> List[str]:
        """返回本次真正新增的条目标题（最多 ``limit`` 条）。"""
        added = summary.report.added if summary.report else []
        result = [outcome.item.title_year for outcome in added[:limit]]
        if len(added) > limit:
            result.append(f"…另有 {len(added) - limit} 条")
        return result

    def _notify_summary(self, summary: RunSummary, *, is_preview: bool = False) -> None:
        """发送运行摘要通知。

        .. important::
           标题统一为「胖虎订阅中心」；正文按模式分两种：

           - **dry-run / 预览**：给全量明细（会订 / 拉取 / 源内去重 / 跳过 / 待确认）
             —— 调参时需要这些数字判断门槛是否合适。
           - **真跑**：只报一行「新增 N 条」—— 日常只关心有没有新增，
             细节去「运行详情」页看。

           历史：早期版本真跑也报 5 行，太啰嗦；后来一度把 dry-run 也压成一行，
           又导致调参时看不到明细。现在按模式分开。
        """
        data = summary.to_summary()
        dry = bool(summary.dry_run)

        would_add = 0
        if summary.report:
            would_add = sum(
                1
                for outcome in summary.report.outcomes
                if outcome.decision == C.DECISION_SKIPPED_DRY_RUN
            )

        if dry:
            label = "预览" if is_preview else "dry-run"
            lines = [
                f"{label}：会订 {would_add} 条（未写入）",
                f"拉取：{data.get('fetched', 0)} 条",
                f"源内去重：{data.get('deduped_out', 0)} 条",
                f"跳过：{data.get('skipped', 0)} 条",
                f"待确认：{data.get('pending_review', 0)} 条",
            ]
        else:
            # 真跑只报一行结论
            lines = [f"新增：{data.get('added', 0)} 条"]

        if data.get("failed_sources"):
            lines.append(f"失败源：{', '.join(data['failed_sources'])}")
        if data.get("limit_hit"):
            lines.append("已触达每日写入上限")
        try:
            self.post_message(
                title="胖虎订阅中心",
                text="\n".join(lines),
            )
        except Exception as err:  # noqa: BLE001 - 通知失败不影响主流程
            logger.warning(f"[SubscribeCenter] 发送通知失败：{err}")

    # ------------------------------------------------------------------ 状态与流水

    async def poster_bytes(self, path: str) -> Optional[tuple]:
        """抓取 TMDB 海报字节（供 /poster 路由代理给浏览器）。

        浏览器直连 ``image.tmdb.org`` 在国内网络下常常不可用，
        所以图片也走服务端 + PROXY 设置。
        """
        from .core.host import fetch_poster_bytes

        return await fetch_poster_bytes(path)

    def status_snapshot(self) -> api_schemas.PluginStatus:
        """组装状态接口所需数据。"""
        state = self._state()
        sources = [
            api_schemas.SourceState(
                source=source,
                enabled=bool(self._config.get(key)),
                implemented=source in C.IMPLEMENTED_SOURCES,
                last_run=(self._source_state.get(source) or {}).get("last_run"),
                last_count=int((self._source_state.get(source) or {}).get("last_count") or 0),
                last_error=str((self._source_state.get(source) or {}).get("last_error") or ""),
            )
            for source, key in (
                (C.SOURCE_TMDB, "enable_tmdb"),
                (C.SOURCE_ANILIST, "enable_anilist"),
                (C.SOURCE_DOUBAN_RSS, "enable_douban_rss"),
                (C.SOURCE_HOT_MEDIA, "enable_hot_media"),
            )
        ]
        return api_schemas.PluginStatus(
            config_issues=[str(item) for item in (state.get("config_issues") or [])],
            plugin_version=self.plugin_version,
            enabled=self._enabled(),
            dry_run=False,
            # 不再有「首次试运行」，恒为已完成（前端据此不显示提示）
            first_run_completed=True,
            busy=self._bridge.busy,
            today=today(self._tz()).isoformat(),
            daily_limit=self._int_config("daily_limit", C.DEFAULT_DAILY_LIMIT),
            written_today=self._written_today(),
            last_run=self._last_run,
            last_summary=self._last_summary,
            sources=sources,
            mapping_cache_size=self._cache.size,
            timezone=self._tz(),
        )

    @staticmethod
    async def _read_custom_css() -> str:
        """读宿主的 ``UserCustomCSS``。

        优先走宿主的系统配置服务；某些调用路径下该服务尚未装配，
        再用 ORM 直接读 ``systemconfig`` 表兜底。
        """
        from app.schemas.types import SystemConfigKey

        try:
            from app.application.configuration import get_configured_system_config

            return str(get_configured_system_config().get(SystemConfigKey.UserCustomCSS) or "")
        except Exception:  # noqa: BLE001 - 服务未装配时走 ORM
            pass

        from app.db import async_session_scope
        from app.db.models.systemconfig import SystemConfig
        from sqlalchemy import select

        async with async_session_scope() as session:
            # 主键是自增 id，不是 key —— 必须按 key 过滤
            row = (
                await session.execute(
                    select(SystemConfig).where(
                        SystemConfig.key == SystemConfigKey.UserCustomCSS.value
                    )
                )
            ).scalars().first()
            return str(getattr(row, "value", "") or "") if row else ""

    @staticmethod
    async def _write_custom_css(value: Optional[str]) -> None:
        """写宿主的 ``UserCustomCSS``（同样带 ORM 兜底）。"""
        from app.schemas.types import SystemConfigKey

        try:
            from app.application.configuration import get_configured_system_config

            await get_configured_system_config().async_set(
                SystemConfigKey.UserCustomCSS, value
            )
            return
        except Exception:  # noqa: BLE001 - 服务未装配时走 ORM
            pass

        from app.db import async_session_scope
        from app.db.models.systemconfig import SystemConfig
        from sqlalchemy import select

        async with async_session_scope() as session:
            row = (
                await session.execute(
                    select(SystemConfig).where(
                        SystemConfig.key == SystemConfigKey.UserCustomCSS.value
                    )
                )
            ).scalars().first()
            if row is None:
                session.add(
                    SystemConfig(key=SystemConfigKey.UserCustomCSS.value, value=value)
                )
            else:
                row.value = value
            await session.commit()

    def card_theme_config(self) -> Dict[str, Any]:
        """当前配色设置（未设置时返回默认色）。"""
        stored = self.get_data(DATA_KEY_CARD_THEME)
        stored = stored if isinstance(stored, dict) else {}
        return {
            "colors": card_theme.normalize_colors(stored.get("colors")),
            "applied": bool(stored.get("applied", False)),
            "restart_hint": False,
        }

    async def apply_card_theme(self, colors: Any = None) -> Dict[str, Any]:
        """把状态配色写进宿主的自定义 CSS（``UserCustomCSS``）。

        只在标记块内替换，**不动用户自己写的 CSS**；``colors`` 传 None
        表示恢复默认（删掉我们那段）。
        """
        normalized = card_theme.normalize_colors(colors) if colors is not None else None
        try:
            current = await self._read_custom_css()
            if normalized is None:
                merged = card_theme.strip_block(current).rstrip()
                if merged:
                    merged += chr(10)
            else:
                merged = card_theme.merge_css(current, normalized)
            # 恢复默认时写空串（不是 None）——宿主的设置服务对 None 的缓存语义
            # 容易让人以为"没清掉"，空串更明确
            await self._write_custom_css(merged)
        except Exception as err:  # noqa: BLE001 - 写设置失败要报给前端
            logger.error(f"[SubscribeCenter] 写入卡片配色失败：{err}", exc_info=True)
            return {"success": False, "error": str(err)}

        self.save_data(
            DATA_KEY_CARD_THEME,
            {
                "colors": normalized or card_theme.DEFAULT_COLORS,
                "applied": normalized is not None,
            },
        )
        return {"success": True, "error": ""}

    def history_page(
        self,
        *,
        page: int = 1,
        count: int = 20,
        decision: str = "",
        source: str = "",
        keyword: str = "",
    ) -> api_schemas.HistoryPage:
        """分页返回流水，支持按决策/来源/关键词筛选。"""
        records = list(reversed(self._history()))
        source_counts = _source_counts(records)
        if source:
            records = [r for r in records if r.get("source") == source]
        if keyword:
            needle = str(keyword).strip().casefold()
            records = [
                r
                for r in records
                if needle in str(r.get("title") or "").casefold()
                or needle in str(r.get("reason") or "").casefold()
            ]
        # 决策 tab 的计数：在 source / keyword 过滤**之后**、decision 过滤**之前**
        # 统计 —— 这样「选 AniList 后，待确认显示的是 AniList 的条数」，
        # 而不是三个源的合计（真机反馈的就是这个）。
        counts = _decision_counts(records)
        if decision:
            records = [r for r in records if r.get("decision") == decision]
        if keyword:
            needle = str(keyword).strip().casefold()
            records = [
                r
                for r in records
                if needle in str(r.get("title") or "").casefold()
                or needle in str(r.get("reason") or "").casefold()
            ]
        page = max(1, int(page or 1))
        count = max(1, min(200, int(count or 20)))
        start = (page - 1) * count
        window = records[start : start + count]
        return api_schemas.HistoryPage(
            items=[api_schemas.HistoryRecord(**_history_item(r)) for r in window],
            total=len(records),
            page=page,
            count=count,
            counts=counts,
            source_counts=source_counts,
        )

    def mapping_cache_view(self) -> api_schemas.MappingCacheView:
        """返回映射缓存内容。"""
        entries = [
            api_schemas.MappingEntry(**entry) for entry in self._cache.snapshot()
        ]
        return api_schemas.MappingCacheView(size=self._cache.size, entries=entries)

    def mapping_fix(self, *, key: str, media_source: str, media_id: str) -> Dict[str, Any]:
        """人工修正一条映射。"""
        ok = self._cache.fix(key, media_source, media_id)
        return {"success": ok, "key": key}

    # ------------------------------------------------------------------ 持久化

    def _state(self) -> Dict[str, Any]:
        """读取运行时状态（插件数据，不进配置）。"""
        value = self.get_data(DATA_KEY_STATE)
        return dict(value) if isinstance(value, dict) else {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        """写入运行时状态。"""
        self.save_data(DATA_KEY_STATE, state)

    def _history(self) -> List[Dict[str, Any]]:
        """读取流水列表。"""
        value = self.get_data(DATA_KEY_HISTORY)
        return list(value) if isinstance(value, list) else []

    def _recorded_keys(self) -> Set[str]:
        """「我订过」的键集合，供写入前查重。

        两个来源取并集：

        1. ``DATA_KEY_RECORDED`` —— 只增不减的持久记录（1.14.5 起的主来源）；
        2. 流水里 ``added`` / ``skipped_already_subscribed`` / ``skipped_recorded``
           的记录（兼容升级前已有的流水，让它立刻生效）。

        **不能只靠流水**：流水同一部作品只留最新一条（后来的「流水已记录」
        会把「已订阅」那条替换掉），还会被 ``MAX_HISTORY`` 截断 —— 真机表现就是
        「流水里记过，删掉订阅后又被订回来」。

        键里带季号（见 :func:`core.writer.recorded_key`）：同一部剧的第二季是
        另一条订阅，不能被第一季的记录拦住。
        """
        from .core.writer import recorded_key

        keys: Set[str] = set()
        stored = self.get_data(DATA_KEY_RECORDED)
        if isinstance(stored, (list, tuple, set)):
            keys.update(str(item) for item in stored if item)
        for record in self._history():
            decision = str(record.get("decision") or "")
            if decision not in (
                C.DECISION_ADDED,
                C.DECISION_SKIPPED_ALREADY_SUBSCRIBED,
                C.DECISION_SKIPPED_RECORDED,
            ):
                continue
            media_source = record.get("media_source")
            media_id = record.get("media_id")
            if not media_source or not media_id:
                continue
            keys.add(recorded_key(media_source, media_id, record.get("season")))
        return keys

    def _remember_recorded(self, outcomes: List[WriteOutcome]) -> None:
        """把「真的订过」的条目记进持久去重表（只增不减）。

        只有 ``added`` 与 ``skipped_already_subscribed`` 算数：前者是我们写进去的，
        后者是宿主那边本来就有（用户或宿主要它）。「待确认」「窗口外」「评分不够」
        「命中排除规则」都没有订过，不能因为它们出现过就永久拒绝。
        """
        from .core.writer import recorded_key

        stored = self.get_data(DATA_KEY_RECORDED)
        current: Set[str] = set()
        if isinstance(stored, (list, tuple, set)):
            current.update(str(item) for item in stored if item)
        changed = False
        for outcome in outcomes:
            if outcome.decision not in (
                C.DECISION_ADDED,
                C.DECISION_SKIPPED_ALREADY_SUBSCRIBED,
            ):
                continue
            identity = outcome.item.resolved
            if not identity or not identity.media_source or not identity.media_id:
                continue
            key = recorded_key(
                identity.media_source, identity.media_id, outcome.item.season
            )
            if key not in current:
                current.add(key)
                changed = True
        if changed:
            self.save_data(DATA_KEY_RECORDED, sorted(current))

    def clear_history(self) -> api_schemas.HistoryClearResult:
        """清空发现流水。

        这是「不再自动重订」的**唯一解锁方式**：流水里的记录删了，下一轮发现
        才会把之前订过的作品重新当成新发现。顺手也把「已处理」的运行时状态
        清掉，否则页面上的计数与实际记录对不上。
        """
        removed = len(self._history())
        self.save_data(DATA_KEY_HISTORY, [])
        # 去重表必须一起清：它是「流水记过就别再订」的实际依据，
        # 只清显示用的流水会变成「界面上空了，但依然订不上」。
        self.save_data(DATA_KEY_RECORDED, [])
        state = self._state()
        if "last_run" in state:
            # last_run 只是摘要，里面的 added 计数已经没有对应的记录了
            state.pop("last_run", None)
            self._save_state(state)
        logger.info("[SubscribeCenter] 发现流水已清空（%s 条）" % removed)
        return api_schemas.HistoryClearResult(removed=removed, remaining=0)

    async def subscribe_from_history(self, *, key: str) -> api_schemas.HistorySubscribeResult:
        """把一条发现流水手动补成订阅（「重新订阅 / 加入订阅」按钮）。

        与每日自动发现的区别（都是故意的）：

        - **不看**窗口/评分/每日额度 —— 用户点名要的，这些门槛就该让路；
        - **不看** ``finished`` 与流水去重 —— 重新订阅已完结的剧是常见操作；
        - 订阅已存在时**不改它的状态**，只把当前状态报给界面（用户可能就是想
          让一个暂停的订阅继续跑，那该由他自己决定，不该被插件顺手改掉）；
        - 真的写成功后**补一条流水**，让「流水记过的不再自动重订」对这次操作也生效。
        """
        from .core.model import DiscoveredItem, ResolvedIdentity
        from .core.writer import WriteOutcome

        key = str(key or "").strip()
        if not key:
            raise ValueError("缺少流水键")

        record = next(
            (item for item in reversed(self._history()) if _record_key(item) == key),
            None,
        )
        if record is None:
            return api_schemas.HistorySubscribeResult(
                key=key, action="skipped", message="流水里没有这条记录（可能已被清空）"
            )

        media_source = str(record.get("media_source") or "")
        media_id = str(record.get("media_id") or "")
        title = str(record.get("title") or "").strip()
        if not media_source or not media_id:
            return api_schemas.HistorySubscribeResult(
                key=key,
                action="skipped",
                message="这条流水没有确定性身份（待确认状态），无法直接订阅",
            )
        if not title:
            return api_schemas.HistorySubscribeResult(
                key=key, action="skipped", message="这条流水没有标题，无法订阅"
            )

        raw_season = record.get("season")
        try:
            season = int(raw_season) if str(raw_season or "").strip() else None
        except (TypeError, ValueError):
            season = None
        is_tv = str(record.get("media_type") or "") == C.MEDIA_TYPE_TV
        media_type = C.MEDIA_TYPE_TV if is_tv else C.MEDIA_TYPE_MOVIE
        year = str(record.get("year") or "")
        episode_group = record.get("episode_group")

        from .core.host import HostSubscribeBackend

        backend = HostSubscribeBackend()
        try:
            exists = await backend.subscription_exists(media_source, media_id, season)
        except Exception as err:  # noqa: BLE001 - 查不到就按「不存在」继续，由 add 幂等兜底
            logger.debug(f"[SubscribeCenter] 手动订阅查重失败：{err}")
            exists = False

        if exists:
            state = await self._subscription_state(media_source, media_id, season)
            label = {"R": "订阅中", "P": "待定", "S": "已暂停", "N": "新建"}.get(
                state, state or "已存在"
            )
            return api_schemas.HistorySubscribeResult(
                key=key,
                action="subscribed",
                state=state,
                message=f"宿主已有该订阅（{label}），没有重复添加；状态请到宿主的订阅页调整",
            )

        try:
            subscribe_id, message = await backend.add(
                title,
                year,
                media_source,
                media_id,
                media_type,
                season,
                episode_group=str(episode_group) if episode_group else None,
                message=True,
                exist_ok=True,
            )
        except Exception as err:  # noqa: BLE001 - 交给上层转成 500，带上原因
            raise RuntimeError(f"写入订阅失败：{err}") from err

        if not subscribe_id:
            return api_schemas.HistorySubscribeResult(
                key=key, action="skipped", message=message or "宿主没有返回订阅 ID"
            )

        run_at = local_now_text(self._tz())
        item = DiscoveredItem(
            source=str(record.get("source") or ""),
            source_id=str(record.get("source_id") or ""),
            title=title,
            media_type=media_type,
            year=year or None,
            release_date=record.get("release_date"),
            season=season,
            rating=record.get("rating"),
            episode_group=str(episode_group) if episode_group else None,
            resolved=ResolvedIdentity(
                media_source=media_source,
                media_id=media_id,
                confidence=str(record.get("confidence") or C.CONFIDENCE_L1),
                reason="手动补订阅",
            ),
            raw={"poster": record.get("poster") or "", "country": record.get("country")},
            discovered_at=run_at,
        )
        outcome = WriteOutcome(
            item=item,
            decision=C.DECISION_ADDED,
            success=True,
            subscribe_id=int(subscribe_id),
            message=message or "手动加入订阅",
            reason="从发现流水手动加入",
        )
        self._append_history([outcome], run_at=run_at)
        logger.info(
            f"[SubscribeCenter] 手动补订阅：{title}（{media_source}:{media_id}）-> {subscribe_id}"
        )
        return api_schemas.HistorySubscribeResult(
            key=key,
            action="added",
            subscribe_id=int(subscribe_id),
            state="",
            message=message or "已加入订阅",
            record=api_schemas.HistoryRecord(**_history_item(outcome.to_dict())),
        )

    async def _subscription_state(
        self, media_source: str, media_id: str, season: Optional[int]
    ) -> str:
        """查订阅当前状态（``R`` / ``P`` / ``S`` / ``N``），查不到返回空串。"""
        try:
            from .core.host import media_source_enum
            from app.sdk.queries import (
                QueryPageRequest,
                SubscriptionFilter,
                async_list_subscriptions,
            )

            source_enum = media_source_enum(media_source)
            if source_enum is None:
                return ""
            page = await async_list_subscriptions(
                SubscriptionFilter(
                    media_source=source_enum, media_id=str(media_id), season=season
                ),
                QueryPageRequest(page=1, count=1),
            )
            items = getattr(page, "items", None) or []
            return str(getattr(items[0], "state", "") or "") if items else ""
        except Exception as err:  # noqa: BLE001 - 状态只是展示用，查不到就留空
            logger.debug(f"[SubscribeCenter] 查订阅状态失败：{err}")
            return ""

    def _append_history(self, outcomes: List[WriteOutcome], *, run_at: str) -> None:
        """写入流水：**同一部作品只保留最新一条**，再截断到上限。

        真机反馈：每次运行都把同一批作品再记一遍，页面上「发现流水」全是重复条目
        （同一部剧按运行次数出现 N 次），根本看不清这部剧现在是什么状态。

        去重键：`media_source:media_id`（有确定性身份时）；没有身份时退回
        `source:标题:年份`。命中已有记录就**替换**成最新状态（并把时间更新为
        本次运行），而不是追加 —— 于是列表里每部作品只会出现一次。
        """
        records = self._history()

        def _work_key(record: Dict[str, Any]) -> str:
            """作品级键：标题 + 年份（用于合并「待确认」与「已订阅」两条记录）。

            同一条目在未解析出身份时只有标题，解析成功后才有 media_id ——
            只按 media_id 去重会留下两条记录，界面上就出现「既待确认又已订阅」。
            """
            # 用**去掉季号/年份的归一化标题**做键：待确认常常是
            # 「完美世界 第七季」，而订阅成功后记录可能写「完美世界」，
            # 用原始标题会合不上（真机：已订阅却仍显示待确认）。
            from .core.identity import normalize_title, strip_season_suffix

            title = normalize_title(strip_season_suffix(str(record.get("title") or "")))
            return f"w:{title}"

        def _key(record: Dict[str, Any]) -> str:
            return _record_key(record)

        index: Dict[str, int] = {}
        for position, record in enumerate(records):
            index[_key(record)] = position

        for outcome in outcomes:
            record = outcome.to_dict()
            record["run_at"] = run_at
            key = _key(record)
            work_key = _work_key(record)
            existing = index.get(key)
            if existing is None:
                # 同一作品另一个形态（待确认 / 已订阅）已存在 -> 就地替换掉它，
                # 避免界面上「既待确认又已订阅」。
                existing = next(
                    (
                        position
                        for position, old in enumerate(records)
                        if _work_key(old) == work_key
                        and _key(old) != key
                        and (not old.get("media_id") or not record.get("media_id"))
                    ),
                    None,
                )
                if existing is not None:
                    index.pop(_key(records[existing]), None)
            if existing is not None:
                # 就地替换：保留「最新状态」，避免同一作品堆成多行
                records[existing] = record
            else:
                index[key] = len(records)
                records.append(record)

        # 逐条合并依赖写入顺序，不可靠（真机：待确认与已订阅两条并存）。
        # 这里在**全部写完之后**统一收敛一次，保证同一作品只留一条。
        records = _collapse_history(records)
        if len(records) > MAX_HISTORY:
            records = records[-MAX_HISTORY:]
        self.save_data(DATA_KEY_HISTORY, records)
        # 顺手把「订过」记进去重表：流水会被合并/截断，去重证据不能跟着丢。
        self._remember_recorded(outcomes)

    def _written_today(self) -> int:
        """返回今日已写入条数（跨日自动归零）。"""
        state = self._state()
        if str(state.get(C.STATE_TODAY) or "") != today(self._tz()).isoformat():
            return 0
        try:
            return max(0, int(state.get(C.STATE_DAILY_COUNT) or 0))
        except (TypeError, ValueError):
            return 0

    def _bump_daily_counter(self) -> None:
        """今日写入计数 +1（跨日重置）。"""
        state = self._state()
        current_day = today(self._tz()).isoformat()
        if str(state.get(C.STATE_TODAY) or "") != current_day:
            state[C.STATE_TODAY] = current_day
            state[C.STATE_DAILY_COUNT] = 0
        state[C.STATE_DAILY_COUNT] = self._written_today() + 1
        self._save_state(state)

    # ------------------------------------------------------------------ 工具

    def _tz(self) -> str:
        """插件时区名称。"""
        return str(self._config.get("timezone") or C.DEFAULT_TIMEZONE)

    def _int_config(self, key: str, default: int) -> int:
        """宽松读取整型配置。"""
        try:
            return int(self._config.get(key))
        except (TypeError, ValueError):
            return default

    def _float_config(self, key: str, default: float) -> float:
        """宽松读取浮点配置。"""
        try:
            return float(self._config.get(key))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_cron(value: Any, default: str = C.DEFAULT_CRON) -> str:
        """校验 5 段式 cron；非法值回落 ``default``，避免拖垮 ``get_service()``。"""
        text = str(value or "").strip()
        if len(text.split()) == 5:
            return text
        if text:
            logger.warning(
                f"[SubscribeCenter] cron 表达式非法（{text!r}），已回落默认 {default}"
            )
        return default


# --------------------------------------------------------------------- 辅助实现

class _PluginCacheStore:
    """把插件数据接口适配成 :class:`~..core.cache.CacheStore`。"""

    def __init__(self, plugin: SubscribeCenter) -> None:
        self._plugin = plugin

    def load(self) -> Any:
        """读取缓存载荷。"""
        return self._plugin.get_data(DATA_KEY_CACHE)

    def save(self, payload: Any) -> None:
        """写入缓存载荷。"""
        self._plugin.save_data(DATA_KEY_CACHE, payload)


class _NullSubscribeBackend:
    """默认后端：未初始化时任何查询都视为「不存在」。

    存在的意义是让 ``status_snapshot()`` 等只读接口在 ``init_plugin()`` 之前
    被调用时不会崩（宿主可能先调 API 再初始化插件）。
    """

    async def add(self, *args: Any, **kwargs: Any) -> Tuple[None, str]:
        """未初始化时拒绝写入。"""
        return None, "插件尚未初始化"

    async def subscription_exists(self, media_source: str, media_id: str) -> bool:
        """未初始化时按「不存在」处理。"""
        return False

    async def history_exists(self, media_source: str, media_id: str) -> bool:
        """未初始化时按「不存在」处理。"""
        return False


#: 流水记录中「缺失时按空值补齐」的字段（避免历史版本流水缺键导致校验失败）
_HISTORY_TEXT_FIELDS = (
    "decision", "message", "reason", "source", "source_id", "title",
    "media_type", "confidence", "run_at",
)
_HISTORY_OPTIONAL_FIELDS = (
    "subscribe_id", "year", "release_date", "season", "rating",
    "media_source", "media_id", "review_score", "poster", "country",
    "episode_group",
)


def _decision_counts(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计各决策条数（喂给前端顶部 tab）。"""
    counts: Dict[str, int] = {}
    for record in records:
        decision = str(record.get("decision") or "")
        if not decision:
            continue
        counts[decision] = counts.get(decision, 0) + 1
    return counts


#: 决策优先级：数值越小越「有信息量」，收敛时保留它
_DECISION_RANK = {
    "added": 0,
    "skipped_already_subscribed": 1,
    "skipped_already_completed": 1,
    "skipped_finished": 2,
    "skipped_out_of_window": 3,
    "skipped_popularity": 3,
    "skipped_rating": 3,
    "skipped_duplicate": 4,
    "pending_review": 9,
}


def _collapse_history(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同一作品只保留一条记录（按「最有信息量」的决策）。

    真机：完美世界 第七季 同时存在 `pending_review`（无 media_id）与
    `skipped_already_subscribed`（有 media_id）两条 —— 界面上就出现
    「已订阅却还在待确认」。逐条合并依赖写入顺序，不可靠；
    改成写完后按作品键统一收敛。

    作品键 = **去掉季号/尾年份的归一化标题**（国漫在「待确认」阶段标题常带
    「第七季」，订阅成功后可能不带，用原始标题会合不上）。
    """
    from .core.identity import normalize_title, strip_season_suffix

    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for record in records:
        base = normalize_title(strip_season_suffix(str(record.get("title") or "")))
        key = base or str(record.get("title") or "")
        if key not in best:
            best[key] = record
            order.append(key)
            continue
        current = best[key]
        rank_new = _DECISION_RANK.get(str(record.get("decision") or ""), 5)
        rank_old = _DECISION_RANK.get(str(current.get("decision") or ""), 5)
        # 决策相近时优先保留带 media_id 的那条（说明身份已解析）
        if (rank_new, 0 if record.get("media_id") else 1) < (
            rank_old,
            0 if current.get("media_id") else 1,
        ):
            best[key] = record
    return [best[key] for key in order]


def _source_counts(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计各数据源条数（喂给前端「按源」tab）。"""
    counts: Dict[str, int] = {}
    for record in records:
        source = str(record.get("source") or "")
        if not source:
            continue
        counts[source] = counts.get(source, 0) + 1
    return counts


def _record_key(record: Dict[str, Any]) -> str:
    """一条流水的稳定键（前端拿它来点「重新订阅 / 加入订阅」）。

    有确定性身份时用 ``来源:ID``（这时同一部剧的不同季会撞成同一个键，
    所以订阅时季号要**从记录里单独取**，不能塞进键里）；没有身份时退回
    ``来源:标题:年份``。
    """
    media_source = str(record.get("media_source") or "")
    media_id = str(record.get("media_id") or "")
    if media_source and media_id:
        return f"{media_source}:{media_id}"
    return "{}:{}:{}".format(
        record.get("source") or "",
        record.get("title") or "",
        record.get("year") or "",
    )


def _history_item(record: Dict[str, Any]) -> Dict[str, Any]:
    """把流水记录裁剪成 :class:`~.controller.schemas.HistoryRecord` 的字段。

    缺失的文本字段补空串、可选字段补 ``None`` —— 旧版本写入的流水可能没有新键，
    不能因此让整个分页接口 500。
    """
    item: Dict[str, Any] = {key: str(record.get(key) or "") for key in _HISTORY_TEXT_FIELDS}
    item["success"] = bool(record.get("success"))
    for key in _HISTORY_OPTIONAL_FIELDS:
        item[key] = record.get(key)
    # 前端点「重新订阅 / 加入订阅」时回传的键
    item["key"] = _record_key(record)
    return item


__all__ = ["SubscribeCenter"]
