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
from .core import autotoggle, card_theme
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
#: 会把「已订阅」替换成后来的「流水已记录」），又会被按天清理掉（``HISTORY_KEEP_DAYS``）。
#: 把去重证据放在流水里，等于让「订过」的记忆取决于最近几次运行 —— 真机表现就是
#: 「流水里明明记过，删掉订阅后又被自动订回来」（1.14.5 修的就是这个）。
DATA_KEY_RECORDED = "recorded_keys"

#: 「按播出日自动启停」里**只改字段/状态**的动作：走宿主订阅写入口（发事件）。
_AUTO_TOGGLE_MUTABLE_ACTIONS = (
    "pause",
    "resume",
    "mark_complete",
    "set_best",
)
#: 「按播出日自动启停」里**会删订阅**的动作：走宿主删除命令，且不可回滚。
_AUTO_TOGGLE_DESTRUCTIVE_ACTIONS = (
    "complete",
    "delete",
)

#: 「无下载处理」选「完成」时要写进订阅历史表的列。
#:
#: 宿主的删除命令**不写历史**（``app/application/subscription/delete.py`` 只
#: stage_delete），所以选「完成」必须由插件先补一条，否则订阅是「订过又消失」，
#: 在历史页面上查不到。这里只列 ``SubscribeHistory`` 真有的列，写的时候还要
#: 再过一遍 ``hasattr``，避免宿主升级删列时整条写失败。
_AUTO_TOGGLE_HISTORY_FIELDS = (
    "activity_key",
    "name",
    "year",
    "type",
    "search_interval",
    "keyword",
    "media_source",
    "media_id",
    "music_type",
    "total_tracks",
    "season",
    "poster",
    "backdrop",
    "vote",
    "description",
    "filter",
    "include",
    "exclude",
    "quality",
    "resolution",
    "effect",
    "audio_quality",
    "audio_format",
    "min_bitrate",
    "min_bit_depth",
    "min_sample_rate",
    "total_episode",
    "start_episode",
    "username",
    "sites",
    "best_version",
    "best_version_full",
    "current_priority",
    "episode_priority",
    "save_path",
    "search_imdbid",
    "custom_words",
    "media_category_id",
    "media_category",
    "classification_rule_id",
    "classification_policy_revision",
    "classification_source",
    "filter_groups",
    "episode_group",
)

#: 流水**按天**保留：只留最近 N 天的记录（1.17.0 起不再用固定条数截断）。
#:
#: 固定 500 条的问题：豆瓣全榜一天 300+ 条，两三天就把一周前的新增挤掉，
#: 「上周订过什么」在界面上就查不到了；反过来频率低的用户又留着几个月前的脏数据。
HISTORY_KEEP_DAYS = 30
#: 硬上限：即使按天保留，也不能让单次异常（比如一天跑几十轮）把数据撑爆。
#: 按每条记录约 300 字节算，3000 条约 0.9MB。
HISTORY_HARD_LIMIT = 3000


class SubscribeCenter(_PluginBase):
    """胖虎订阅中心插件入口。"""

    plugin_name = C.PLUGIN_NAME
    plugin_desc = C.PLUGIN_DESCRIPTION
    plugin_icon = C.PLUGIN_ICON
    plugin_color = C.PLUGIN_COLOR
    #: 必须是**类级字符串字面量** —— 发布门禁 ``check_plugin_versions.py``
    #: 用 AST 提取它并与 ``package.v3.json`` 的 ``version`` 比对，
    #: 写成 ``C.PLUGIN_VERSION`` 这类引用会让门禁取不到值。
    plugin_version = "1.18.7"
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
            # 未播集太远就不订（见 DEFAULT_UPCOMING_MAX_DAYS 的说明）
            upcoming_max_days=self._int_config(
                "upcoming_max_days", C.DEFAULT_UPCOMING_MAX_DAYS
            ),
        )
        daily_limit = self._int_config("daily_limit", C.DEFAULT_DAILY_LIMIT)
        self._writer = SubscriptionWriter(
            HostSubscribeBackend(),
            daily_limit=daily_limit,
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

    async def api_gaps(self) -> Any:
        """读「订阅中但缺了几集」清单（还在保留窗口内、未入库的集）。"""
        return await api_controller.api_gaps(self)

    async def api_gaps_search(
        self, request: api_schemas.GapsSearchRequest
    ) -> Any:
        """对缺集列表里的一部订阅触发一次宿主「补全搜索」。

        **注解必须写具体模型**：写成 ``Any`` 会让 FastAPI 把 POST body 当查询
        参数解析（1.14.0 真机踩过），这里必须要 ``request.subscribe_id``。
        """
        return await api_controller.api_gaps_search(self, request)

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
            "best_keep_days_tv": min(
                max(
                    self._int_config(
                        "auto_toggle_best_version_keep_days_tv",
                        C.DEFAULT_AUTO_TOGGLE_BEST_KEEP,
                    ),
                    0,
                ),
                365,
            ),
            "best_keep_days_movie": min(
                max(
                    self._int_config(
                        "auto_toggle_best_version_keep_days_movie",
                        C.DEFAULT_AUTO_TOGGLE_BEST_KEEP,
                    ),
                    0,
                ),
                365,
            ),
            "best_preopen_days": min(
                max(
                    self._int_config(
                        "auto_toggle_best_preopen_days",
                        C.DEFAULT_BEST_PREOPEN_DAYS,
                    ),
                    0,
                ),
                14,
            ),
            "best_preopen_enabled": bool(
                self._config.get(
                    "auto_toggle_best_preopen",
                    C.DEFAULT_AUTO_TOGGLE_BEST_PREOPEN,
                )
            ),
            "movie_enabled": bool(self._config.get("auto_toggle_movie_enabled", True)),
            "movie_theatrical_offset_days": min(
                max(
                    self._int_config(
                        "auto_toggle_movie_theatrical_offset_days",
                        C.DEFAULT_MOVIE_THEATRICAL_OFFSET_DAYS,
                    ),
                    0,
                ),
                365,
            ),
            "library_check": bool(self._config.get("auto_toggle_library_check")),
            "backfill_notes": bool(
                self._config.get(
                    "auto_toggle_backfill_notes",
                    C.DEFAULT_AUTO_TOGGLE_BACKFILL_NOTES,
                )
            ),
            "follow_refresh": bool(
                self._config.get(
                    "auto_toggle_follow_refresh", C.DEFAULT_AUTO_TOGGLE_FOLLOW_REFRESH
                )
            ),
            "best_mode": self._best_toggle_mode(),
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
                    from app.schemas.types import MediaType

                    #: 这里**不能**构造 MediaInfo 当第一个参数：宿主
                    #: ``async_recognize_media(meta=...)`` 的 meta 要的是
                    #: MetaInfo（解析出来的元信息，有 ``name`` 字段），传错对象
                    #: 会在 TMDB 模块里踩 ``meta.name`` AttributeError。正确做法
                    #: 是把来源与 ID 作关键字参交给宿主自己换算（与
                    #: ``_movie_tmdb_id`` 一致）。
                    media = await MediaChain().async_recognize_media(
                        mtype=MediaType.MOVIE,
                        media_source=media_source,
                        media_id=media_id,
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
            from app.schemas.types import MediaType

            #: 同 ``resolve_tmdb_id``：meta 位置不接受 MediaInfo，用关键字参。
            media = await MediaChain().async_recognize_media(
                mtype=MediaType.MOVIE,
                media_source=media_source,
                media_id=media_id,
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
        self, rows: Any
    ) -> Tuple[Dict[int, set], Dict[str, Any]]:
        """按宿主维护的 ``lack_episode`` 推出「库里已入库哪些集」的索引。

        为什么不再自己探库：MoviePilot 的订阅刷新任务本来就在逐集核库，结论写在
        ``Subscribe.lack_episode`` 上 —— 它等于目标范围里**还没拿到手**的集数。
        我们照着再问一遍媒体服务器纯属白烧：真机实测每条 1.7 秒，200 条要 6 分钟，
        并发高了还会把 NAS 打挂。读宿主已经算好的账，零成本，口径也和宿主一致。

        只拿到「缺几集」、拿不到「缺哪几集」，所以按**前 N 集已入库**处理 ——
        与宿主自己顺序追更的假设一致。方向是安全的：``lack_episode`` 偏大（宿主
        还没核对完、或新建订阅直接置成总集数）只会让我们以为缺得更多 → 继续搜，
        **不会误暂停**。

        拿不到可信数字的订阅（电影、总集数未知）不进索引，``decide`` 会返回
        「还没核对到」并保持不动。

        .. important::
           洗版订阅**必须**进索引。早期这里把 ``best_version=1`` 的订阅 ``continue``
           掉了（注释写「洗版跟库里有没有这一集无关」），结果 ``decide`` 在播出期
           拿不到 ``library_present`` → 一律返回 ``library_unknown`` 保持不动，
           自动启停对全部洗版订阅失效（真机：尚公主第 25 集下完不暂停）。
           「洗到顶没有」是另一回事，由 ``best_version_done`` 看
           ``episode_priority``，与这里不冲突 —— 洗版订阅的 ``lack_episode``
           本来就是按「有没有下到任一版本」算的（宿主 ``compute_lack_episode``）。
        """
        from .core import autotoggle

        index: Dict[int, set] = {}
        tv_rows = 0
        for row in rows:
            if autotoggle.media_kind(row) != "tv":
                continue
            tv_rows += 1
            sid = int(getattr(row, "id", 0) or 0)
            if sid <= 0:
                continue
            present = autotoggle.library_present_from_lack(row)
            if present is None:
                continue
            index[sid] = present

        stats: Dict[str, Any] = {
            "mode": "mp",
            "known": len(index),
            "unknown": max(0, tv_rows - len(index)),
        }
        return index, stats

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
        # 入库情况：直接读宿主维护的 lack_episode，不再自己问媒体服务器
        library_index: Dict[int, set] = {}
        library_stats: Dict[str, Any] = {}
        if cfg["library_check"]:
            library_index, library_stats = await self._library_present_index(rows)
        data = autotoggle.plan(
            rows,
            index,
            today_date,
            lookahead_days=cfg["lookahead_days"],
            keep_days=cfg["keep_days"],
            best_keep_days_tv=cfg["best_keep_days_tv"],
            best_keep_days_movie=cfg["best_keep_days_movie"],
            best_preopen_days=cfg["best_preopen_days"],
            best_preopen_enabled=cfg["best_preopen_enabled"],
            best_mode=cfg["best_mode"],
            owned=owned if isinstance(owned, dict) else None,
            release_index=release_index,
            movie_enabled=cfg["movie_enabled"],
            movie_theatrical_offset_days=cfg["movie_theatrical_offset_days"],
            library_index=library_index,
            library_check=cfg["library_check"],
            season_index=self.__dict__.get("_season_info_cache") or {},
        )
        data["config"] = cfg
        data["library"] = library_stats
        data["last_run"] = dict(state.get("last_run") or {})
        data["owned"] = len(
            [item for item in (owned or {}).values() if isinstance(item, dict)]
        )
        return data

    async def gaps_data(self) -> Dict[str, Any]:
        """「订阅中但缺了几集」清单（不写库、不探针）。

        只复用**已缓存**的媒体库实探结果；不开实时探针 —— 列表页是一次普通
        GET，串行核对几百条会被网关 502 掐断。缺集口径与自动启停一致：只在
        ``keep_days`` 保留窗口内、且被实探确认**不在库**的集才算缺口；**没有
        实探证据的订阅一律不列**（宁可漏报不误报，真缺的等自动启停下一轮
        实探补上）。
        """
        from .core import autotoggle
        from .core import calendar as calendar_core

        cfg = self._auto_toggle_config()
        today_date = today(self._tz())
        today_text = today_date.isoformat()
        rows = await self._auto_toggle_rows()
        index = await self._episode_air_index(rows, today_text)

        # 入库情况：读宿主维护的 lack_episode（与自动启停预览同口径）
        confirmed: Dict[int, set] = {}
        if cfg["library_check"]:
            confirmed, _ = await self._library_present_index(rows)

        items: List[Dict[str, Any]] = []
        for row in rows:
            media_id = str(getattr(row, "media_id", "") or "")
            season = int(getattr(row, "season", 0) or 0)
            if not media_id.isdigit():
                continue
            episodes = index.get((media_id, season if season > 0 else calendar_core.MOVIE_KEY))
            if episodes is None:
                episodes = index.get((media_id, season))
            if not episodes:
                continue
            gaps = autotoggle.in_window_gaps(
                row,
                episodes,
                today_date,
                keep_days=cfg["keep_days"],
                confirmed=confirmed.get(int(getattr(row, "id", 0) or 0)),
            )
            if not gaps:
                continue
            items.append(
                {
                    "id": int(getattr(row, "id", 0) or 0),
                    "name": str(getattr(row, "name", "") or ""),
                    "year": str(getattr(row, "year", "") or ""),
                    "season": season,
                    "state": str(getattr(row, "state", "") or ""),
                    "poster": str(getattr(row, "poster", "") or ""),
                    "media_source": str(getattr(row, "media_source", "") or ""),
                    "media_id": media_id,
                    "gaps": [
                        {"air_date": day, "episode": number, "days_left": left}
                        for day, number, left in gaps
                    ],
                    # 整部剧最早出窗口的那个缺口：排序/界面「还剩几天」用
                    "min_days_left": min(left for _, _, left in gaps),
                }
            )
        items.sort(key=lambda item: (item["min_days_left"], item["name"]))
        return {
            "today": today_text,
            "keep_days": cfg["keep_days"],
            "total": len(items),
            "items": items,
        }

    async def gaps_search(self, *, subscribe_id: int) -> Dict[str, Any]:
        """对一部订阅触发一次宿主「手动搜索（按标题）」。

        不再走 ``SubscribeChain().search``（订阅搜索是队列式后台执行、吃订阅站点范围
        RssSites、且一次太久）；改为调宿主「搜索结果页」同款的手动模糊搜索
        ``SearchChain().async_search_by_title``：
        - ``sites`` 不传 → 自然用 MP 设定里的**搜索站点范围（IndexerSites）**；
        - ``cache_local=True`` → 结果自动落到 MP 的**「搜索结果」页**，用户在
          界面自己看、自己点下载，站点速度也看得见；
        - 只搜这一部（用订阅自己的标题），不连搜多部，避免覆盖缓存、顶爆站点流控。
        """
        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

        from .core import autotoggle

        # 取这一部订阅的标题和类型（不含就退出，给个明确提示）
        async with async_session_scope() as session:
            row = (
                await session.execute(
                    select(Subscribe).where(Subscribe.id == subscribe_id)
                )
            ).scalar_one_or_none()
        title = str(getattr(row, "name", "") or "").strip()
        if not title:
            return {
                "subscribe_id": subscribe_id,
                "message": "没有可用的标题，无法手动搜索",
            }
        kind = autotoggle.media_kind(row)
        mtype = None
        if kind == "movie":
            from app.schemas.types import MediaType

            mtype = MediaType.MOVIE
        elif kind == "tv":
            from app.schemas.types import MediaType

            mtype = MediaType.TV

        from app.chain.search.facade import SearchChain

        chain = SearchChain()
        results = await chain.async_search_by_title(
            title=title,
            page=0,
            sites=None,  # 不传 → 用搜索站点范围 IndexerSites
            cache_local=True,  # 落到 MP「搜索结果」页
            mtype=mtype,
        )
        count = len(results)
        return {
            "subscribe_id": subscribe_id,
            "message": (
                f"已按《{title}》在搜索站点范围逐站搜索，找到 {count} 个资源，"
                "请到 MoviePilot「搜索结果」页查看并手动下载"
            ),
        }

    async def auto_toggle_run(self, *, reason: str = "manual") -> Dict[str, Any]:
        """执行一次自动启停：先算计划，再逐条写状态，最后更新接管表。

        :param reason: ``cron`` / ``manual`` —— 只用于记录，不影响判定
        """
        import time

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
        if isinstance(probe_cache, dict):
            #: 兼容旧数据：以前这里存实探缓存，现在不再产生，遇到就顺手清掉。
            state.pop("library_probe", None)
        owned = autotoggle.next_owned(
            state.get("owned"),
            planned,
            today_text=today_text,
            applied_ids=applied,
        )
        applied_ids = set(applied)

        def _count(action: str) -> int:
            return len(
                [
                    item
                    for item in changes
                    if item.get("action") == action
                    and int(item.get("id") or 0) in applied_ids
                ]
            )

        paused = _count(autotoggle.ACTION_PAUSE)
        resumed = _count(autotoggle.ACTION_RESUME)
        opened = _count(autotoggle.ACTION_SET_BEST)
        marked = _count(autotoggle.ACTION_MARK_COMPLETE)
        completed = _count(autotoggle.ACTION_COMPLETE)
        deleted = _count(autotoggle.ACTION_DELETE)
        run_at = local_now_text(self._tz())

        #: 集数修正（backfill）：洗版订阅页面「N/M 集」只算订阅自己下过的集，
        #: 库里早就存在的老集不记账 → 显示成「明明有 25 集只写 2 集」。这里在
        #: 每轮自动启停末尾顺带把账修平。单独计数，不进 changes/通知。
        backfilled, backfill_failed = await self._backfill_note_episodes(
            cfg, state, planned
        )

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
            "opened": opened,
            "marked": marked,
            "completed": completed,
            "deleted": deleted,
            "failed": len(failed),
            "backfilled": backfilled,
            "backfill_failed": backfill_failed,
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
            "opened": opened,
            "marked": marked,
            "completed": completed,
            "deleted": deleted,
            "failed": failed,
            "backfilled": backfilled,
            "backfill_failed": backfill_failed,
            "truncated": bool(planned.get("truncated")),
            "kept": planned.get("kept", 0),
            "skipped": planned.get("skipped", 0),
            "reasons": planned.get("reasons") or {},
            "owned": len(owned),
            "last_run": state["last_run"],
            #: 逐条通知用的明细：只留**真正改成功**的那几条
            "changed": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "season": item.get("season"),
                    "action": item.get("action"),
                    "reason_label": item.get("reason_label"),
                    "detail": item.get("detail"),
                    "poster": item.get("poster"),
                    "kind": item.get("kind"),
                }
                for item in changes
                if int(item.get("id") or 0) in applied_ids
                and item.get("action") in autotoggle.WRITE_ACTIONS
            ],
        }
        logger.info(
            f"[SubscribeCenter] 播出日自动启停（{reason}）："
            f"计划 {result['planned']} 条，暂停 {paused}，恢复 {resumed}，"
            f"开洗版 {opened}，标记洗版完成 {marked}，完成 {completed}，删除 {deleted}，"
            f"失败 {len(failed)}，集数修正 {backfilled}，接管中 {len(owned)}"
        )
        if cfg["notify"] and (
            paused or resumed or opened or marked or completed or deleted or failed
        ):
            self._notify_auto_toggle(result)
        return result

    async def _backfill_note_episodes(
        self,
        cfg: Dict[str, Any],
        state: Dict[str, Any],
        planned: Dict[str, Any],
    ) -> Tuple[int, int]:
        """集数修正：把洗版订阅「库里有但没记账」的集补进 ``note``。

        洗版订阅页面「N/M 集」的数字只算订阅**自己下过**的集（宿主
        ``compute_lack_episode`` 对洗版只看 ``note`` ∪ ``episode_priority``，
        不看媒体库），媒体库里早就存在的老集不记账 → 用户看到的就是
        「明明有 25 集只写 2 集」。这里每轮挑最多 ``C.BACKFILL_LIMIT`` 条
        洗版电视剧订阅（同一订阅 ``C.BACKFILL_COOLDOWN_DAYS`` 天内不重复
        探测，``last_update`` 最旧优先），逐条向媒体服务器实探一次，把
        「库里有 ∧ 已播出 ∧ 在目标集范围 ∧ note 还没有」的集号交给宿主自己的
        ``SubscribeChain.backfill_existing_episodes`` 写入 —— 宿主写完会顺带
        重算 ``lack_episode``，显示与库对齐。

        成本：每条订阅 = 1 次局域网媒体服务器调用（毫秒~秒级），远小于一次
        订阅搜索；全程静默，不发通知（``changed`` 明细不含它）。

        :return: ``(补账成功条数, 失败条数)``
        """
        from .core import autotoggle

        if not cfg.get("backfill_notes"):
            return 0, 0

        #: 全程 best-effort：任何一步炸了（查表失败/宿主 API 变更）都不能
        #: 拖垮整轮自动启停，静默记一条 debug 即可。
        backfilled = 0
        failed = 0
        #: 冷却表先取出来：即使整段中途炸掉，收尾也能原样写回，不至于
        #: 引用一个从未绑定的局部变量。
        cooldown = state.get("backfill_at")
        if not isinstance(cooldown, dict):
            cooldown = {}
        try:
            today_text = str(
                planned.get("today") or today(self._tz()).isoformat()
            )
            rows = await self._auto_toggle_rows()
            candidates = autotoggle.backfill_candidates(
                rows,
                today_text=today_text,
                cooldown_at=cooldown,
                limit=C.BACKFILL_LIMIT,
                cooldown_days=C.BACKFILL_COOLDOWN_DAYS,
            )
            if not candidates:
                state["backfill_at"] = cooldown
                return 0, 0

            #: 已播集号来自本轮刚填过的播出表缓存（``_episode_air_index`` 在
            #: ``auto_toggle_plan`` 里已经为全部行拉过 TMDB 数据），不再二次请求。
            cache = self.__dict__.get("_season_cache") or {}

            for target in candidates:
                sid = int(target.get("id") or 0)
                media_id = str(target.get("media_id") or "")
                season = int(target.get("season") or 0)
                row = next(
                    (item for item in rows if int(getattr(item, "id", 0) or 0) == sid),
                    None,
                )
                if row is None or not media_id.isdigit():
                    continue
                #: 缓存键与 ``_episode_air_index`` 完全一致：带剧集组时是
                #: ``(media_id, "g:组名")``，否则 ``(media_id, 季号)``。查不到
                #: 播出表时 ``air_pairs=None`` → ``backfill_episodes`` 直接不写，
                #: 宁可不修也不乱修。
                group = str(getattr(row, "episode_group", "") or "").strip()
                entry = cache.get((media_id, f"g:{group}" if group else season))
                air_pairs = entry[1] if entry and len(entry) > 1 else None
                #: 先记探测日再探库：探失败（媒体服务器没接/识别不出）的订阅
                #: 也没必要每一轮（一天几十次）都重探一遍。
                cooldown[str(sid)] = today_text
                try:
                    present = await self._backfill_probe_library(row)
                except Exception as err:  # noqa: BLE001 - 单条失败不影响整轮
                    logger.debug(
                        f"[SubscribeCenter] 集数修正探库失败 {target.get('name')}："
                        f"{err}"
                    )
                    failed += 1
                    continue
                episodes = autotoggle.backfill_episodes(
                    row, air_pairs, today_text=today_text, present=present
                )
                if not episodes:
                    continue
                try:
                    updated = await self._backfill_apply_note(sid, episodes)
                except Exception as err:  # noqa: BLE001
                    logger.debug(
                        f"[SubscribeCenter] 集数修正写账失败 {target.get('name')}："
                        f"{err}"
                    )
                    failed += 1
                    continue
                if updated:
                    backfilled += 1
                    logger.info(
                        f"[SubscribeCenter] 集数修正：{target.get('name')} "
                        f"S{season} 补记 {len(episodes)} 集（{episodes[0]}"
                        f"{'-' if len(episodes) > 1 else ''}{episodes[-1] if len(episodes) > 1 else ''}）"
                    )
        except Exception as err:  # noqa: BLE001 - 整段是 best-effort
            logger.debug(f"[SubscribeCenter] 集数修正中断：{err}")
        state["backfill_at"] = cooldown
        return backfilled, failed

    async def _backfill_probe_library(self, row: Any) -> Optional[List[int]]:
        """实探单条订阅：媒体库里本季实际存在哪些集号。

        :return: 集号列表（可能为空 = 库里一集都没有，也是有效答案）；
            ``None`` = 探不到（识别失败/没有媒体服务器），调用方不写账。
        """
        from app.application.subscription.contract import build_subscribe_meta
        from app.chain.media import MediaChain
        from app.chain.subscribe import SubscribeChain
        from app.chain.subscribe.identity import subscribe_recognize_kwargs

        def _probe() -> Optional[List[int]]:
            try:
                meta = build_subscribe_meta(row)
            except ValueError:
                return None
            mediainfo = MediaChain().recognize_media(
                meta=meta,
                mtype=meta.type,
                **subscribe_recognize_kwargs(row),
                episode_group=getattr(row, "episode_group", None),
                cache=False,
            )
            if not mediainfo:
                return None
            exists = SubscribeChain().media_exists(mediainfo=mediainfo)
            if not exists:
                return None
            season = getattr(row, "season", None)
            season_number = int(season) if season is not None else 1
            return list((exists.seasons or {}).get(season_number) or [])

        return await asyncio.to_thread(_probe)

    async def _backfill_apply_note(self, sid: int, episodes: List[int]) -> bool:
        """把补账集号交给宿主写入并让它重算缺集数（宿主自带事务+事件）。"""
        from app.application.subscription.mutation import SubscriptionActor
        from app.chain.subscribe import SubscribeChain
        from app.startup.composition.subscription import (
            subscription_mutation_scope,
        )

        actor = SubscriptionActor(name="SubscribeCenter", is_superuser=True)

        async with subscription_mutation_scope() as service:
            snapshot = await service.get_accessible(sid, actor)
        if snapshot is None:
            return False
        #: ``backfill_existing_episodes`` 是同步方法且内部自开
        #: ``sync_subscription_mutation_scope`` 写库（含 outbox 事件），
        #: 放线程里跑，不阻塞事件循环，也不和上面的 async scope 嵌套。
        summary = await asyncio.to_thread(
            SubscribeChain().backfill_existing_episodes,
            snapshot,
            list(episodes),
            None,
            "subscribecenter",
        )
        return bool(summary and summary.get("accepted"))

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
        #: 改字段/改状态的走宿主订阅写入口；删除类（写历史后删、直接删）
        #: 走宿主的删除命令，两者事务边界不同，必须分开。
        mutable = [
            item
            for item in changes
            if str(item.get("action") or "") in _AUTO_TOGGLE_MUTABLE_ACTIONS
        ]
        destructive = [
            item
            for item in changes
            if str(item.get("action") or "") in _AUTO_TOGGLE_DESTRUCTIVE_ACTIONS
        ]
        if not mutable and not destructive:
            return applied, failed

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
                await self._apply_with_scope(scope, actor, mutable, applied, failed)
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
            #: 删除类不走 mutation scope（事务边界不同），单独逐条执行
            await self._apply_auto_toggle_destructive(destructive, applied, failed)
            return applied, failed

        # ---- 降级路径：每条一个短事务，状态照改，但没有 outbox 事件
        from app.db import async_session_scope
        from app.db.oper.subscribe import SubscribeOper

        for item in mutable:
            sid = int(item.get("id") or 0)
            action = str(item.get("action") or "")
            payload = self._auto_toggle_payload(item, action)
            if not sid or not payload:
                failed.append(
                    {"id": sid, "name": item.get("name"), "error": "目标状态非法：无法构造写入内容"}
                )
                continue
            try:
                async with async_session_scope() as session:
                    oper = SubscribeOper(session)
                    if action == autotoggle.ACTION_MARK_COMPLETE:
                        #: 降级路径同样要「合并」分集优先级，不能整份覆盖
                        row = await oper.async_get(sid)
                        merged = self._auto_toggle_payload(item, action, row)
                        if merged:
                            payload = merged
                    updated = await oper.async_stage_update(sid, payload)
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
        await self._apply_auto_toggle_destructive(destructive, applied, failed)
        return applied, failed

    @staticmethod
    def _auto_toggle_episode_priority(row: Any, episodes: List[int]) -> Dict[str, int]:
        """把「要标记为完成」的集号并进现有的 ``episode_priority``。

        宿主的分集洗版完成判定是 ``all(episode_priority[str(ep)] == 100)``
        （``app/application/subscription/priority.py:377-393``），所以只写 100
        就是替它按下「这些集洗完了」。**必须合并而不是整份覆盖** —— 覆盖会把
        之前已经洗到顶的集号清零，反而让它重新去搜。
        """
        current = getattr(row, "episode_priority", None) if row is not None else None
        merged = dict(current) if isinstance(current, dict) else {}
        for episode in episodes:
            merged[str(episode)] = 100
        return merged

    def _auto_toggle_payload(
        self, item: Dict[str, Any], action: str, row: Any = None
    ) -> Dict[str, Any]:
        """按动作构造写库内容（``{}`` 表示这个动作不用写字段）。

        - ``pause`` / ``resume``：只改 ``state``，与以前完全一致；
        - ``set_best``：把普通订阅改成洗版订阅。**只写 ``best_version``，不写
          ``best_version_full``**（1.18.5 用户要求「转洗版的时候不要勾选全集洗版」）。
          只写 ``best_version`` 走的是「分集洗版」：宿主 ``is_best_version_complete``
          按 ``episode_priority`` 逐集判，洗完的集写 100、没洗到的集留着继续搜，
          逐集收工。勾了全集洗版反而更糟 —— 目标是整季包一次性判完成，只要有一集
          到不了 100，这条订阅就永远卡在洗版里不结束。
        - ``mark_complete``：写宿主认的「洗版已完成」标记。全集洗版只写
          ``current_priority=100``；分集洗版把计划里列出的集号写进
          ``episode_priority``，并**顺带**写 ``current_priority=100``（宿主
          判断分集完成只看 ``episode_priority``，但把这个字段也置满能避免
          某些版本在「按优先级比较」时又把订阅捞回搜索队列）。
        """
        if action in ("pause", "resume"):
            target = str(item.get("target") or "")
            return {"state": target} if target in ("R", "S") else {}
        if action == autotoggle.ACTION_SET_BEST:
            # 只开分集洗版：不写 best_version_full（见上面的说明）
            return {"best_version": 1}
        if action != autotoggle.ACTION_MARK_COMPLETE:
            return {}
        if bool(item.get("best_full")):
            return {"current_priority": 100}
        episodes = [
            int(number)
            for number in (item.get("target_episodes") or [])
            if str(number).strip().lstrip("-").isdigit()
        ]
        if not episodes:
            return {"current_priority": 100}
        return {
            "current_priority": 100,
            "episode_priority": self._auto_toggle_episode_priority(row, episodes),
        }

    async def _apply_auto_toggle_destructive(
        self,
        items: List[Dict[str, Any]],
        applied: List[int],
        failed: List[Dict[str, Any]],
    ) -> None:
        """执行「写完成历史后删」「直接删」两条不可回滚的动作。

        删除走宿主的 ``delete_subscribe_scope`` + ``DeleteSubscribeCommand``：
        它在一个事务里暂存删除与 outbox 事件，并负责通知宿主侧统计。
        ``complete`` 在删之前先用 ``SubscribeHistoryOper`` 补一条完成历史 ——
        宿主的删除命令**不会**替你写历史，不补就等于「订过又消失」，
        而我们的「订过就不再订」正是靠历史与 ``recorded_keys`` 记的。
        """
        if not items:
            return
        delete_scope = None
        try:
            from app.startup.composition.subscription import delete_subscribe_scope

            delete_scope = delete_subscribe_scope
        except Exception as err:  # noqa: BLE001 - 老宿主没有这层，走降级
            logger.warning(
                f"[SubscribeCenter] 未找到 delete_subscribe_scope，降级为直删库：{err}"
            )

        for item in items:
            sid = int(item.get("id") or 0)
            action = str(item.get("action") or "")
            if not sid:
                failed.append(
                    {"id": sid, "name": item.get("name"), "error": "订阅 ID 无效"}
                )
                continue
            try:
                if action == autotoggle.ACTION_COMPLETE:
                    await self._stage_auto_toggle_history(sid)
                deleted = await self._delete_auto_toggle_row(sid, delete_scope)
            except Exception as err:  # noqa: BLE001 - 单条失败不影响其余
                failed.append({"id": sid, "name": item.get("name"), "error": str(err)})
                continue
            if not deleted:
                failed.append(
                    {
                        "id": sid,
                        "name": item.get("name"),
                        "error": "宿主未找到该订阅（可能已被删除）",
                    }
                )
                continue
            applied.append(sid)

    async def _stage_auto_toggle_history(self, sid: int) -> None:
        """在删除订阅前补一条「已完成」历史，供宿主历史页查看。

        为什么不直接调 ``SubscribeHistoryOper.add()``：它内部走
        ``_stage_create`` → ``_execute_sync_write``，而我们手上是
        ``AsyncSession``，那条路会**另开一个同步事务**，与这里的读不在同一
        快照里。``stage_add`` 又硬要求同步 Session。所以这里只用它的
        ``_persistable``（列过滤 + 强制把 ``date`` 写成当前时间），模型自己
        ``add`` 进当前异步会话。
        """
        from app.db import async_session_scope
        from app.db.models.subscribehistory import SubscribeHistory
        from app.db.oper.subscribe import SubscribeOper
        from app.db.oper.subscribehistory import SubscribeHistoryOper

        async with async_session_scope() as session:
            row = await SubscribeOper(session).async_get(sid)
            if row is None:
                return
            payload = {
                key: getattr(row, key)
                for key in _AUTO_TOGGLE_HISTORY_FIELDS
                if hasattr(row, key)
            }
            values = SubscribeHistoryOper._persistable(payload)
            session.add(SubscribeHistory(**values))
            await session.commit()

    async def _delete_auto_toggle_row(self, sid: int, delete_scope: Any) -> bool:
        """删一条订阅；宿主命令拿不到时降级为直删库。"""
        if delete_scope is not None:
            from app.application.subscription.delete import SubscribeDeletionActor

            actor = SubscribeDeletionActor(
                username="SubscribeCenter", is_superuser=True
            )
            async with delete_scope() as command:
                status = await command.execute_with_status(sid, actor)
            return str(status) == "deleted"
        from app.db import async_session_scope
        from app.db.oper.subscribe import SubscribeOper

        async with async_session_scope() as session:
            oper = SubscribeOper(session)
            row = await oper.async_get(sid)
            if row is None:
                return False
            await oper.async_delete(sid)
            await session.commit()
        return True

    async def _apply_with_scope(
        self,
        scope: Any,
        actor: Any,
        changes: List[Dict[str, Any]],
        applied: List[int],
        failed: List[Dict[str, Any]],
    ) -> None:
        """走宿主的 ``subscription_mutation_scope`` 逐条写订阅。

        暂停/恢复只改状态；「标记洗版完成」写宿主认的完成标记。两者都走
        ``update``，才能在同一事务里发出 ``SubscribeModified`` 事件。

        单条失败只记错，不影响其余；但**提交**失败会抛出，由调用方按整批
        回滚处理（``applied`` 里此时记的都不算数）。
        """
        async with scope() as service:
            for item in changes:
                sid = int(item.get("id") or 0)
                action = str(item.get("action") or "")
                payload = self._auto_toggle_payload(item, action)
                if not sid or not payload:
                    failed.append(
                        {
                            "id": sid,
                            "name": item.get("name"),
                            "error": f"目标状态非法：{action!r}",
                        }
                    )
                    continue
                try:
                    if action == autotoggle.ACTION_MARK_COMPLETE and not bool(
                        item.get("best_full")
                    ):
                        #: 分集洗版要先读现有优先级再合并，否则会覆盖掉已完成的集。
                        #: ``get_accessible`` 返回的就是订阅快照本身（不是包一层的
                        #: 结果对象），直接把它交给 payload 构造函数取
                        #: ``episode_priority`` 即可。
                        existing = await service.get_accessible(sid, actor)
                        merged = self._auto_toggle_payload(item, action, existing)
                        if merged:
                            payload = merged
                    mutation = await service.update(sid, payload, actor)
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
        """发送自动启停通知：**一部一条**，带海报、原因、处理、后续。

        以前只报「暂停 N 条 / 恢复 N 条」，看不出是哪几部、为什么，等于没说。
        现在按订阅逐条发：标题写清「剧名 S1 原因」，正文写原因/处理/后续，
        带上海报并链接到订阅页，点开就能看到那一部。
        """
        items = [item for item in (result.get("changed") or []) if isinstance(item, dict)]
        for item in items:
            try:
                self.post_message(
                    mtype=self._notify_type_subscribe(),
                    title=self._auto_toggle_title(item),
                    text=self._auto_toggle_text(item),
                    image=str(item.get("poster") or "") or None,
                    link=self._auto_toggle_link(item),
                )
            except Exception as err:  # noqa: BLE001 - 通知失败不影响主流程
                logger.warning(f"[SubscribeCenter] 发送自动启停通知失败：{err}")
        failed = result.get("failed") or []
        if failed:
            lines = [f"· {self._failed_label(row)}" for row in failed[:10]]
            if len(failed) > 10:
                lines.append(f"…等 {len(failed)} 条")
            try:
                self.post_message(
                    title="胖虎订阅中心 播出日自动启停（有失败）",
                    text="\n".join(lines),
                )
            except Exception as err:  # noqa: BLE001 - 通知失败不影响主流程
                logger.warning(f"[SubscribeCenter] 发送自动启停失败通知失败：{err}")

    @staticmethod
    def _notify_type_subscribe():
        """宿主通知类型 ``订阅``（取不到就退回默认，别因为枚举变化丢了通知）。"""
        try:
            from app.schemas import NotificationType

            return NotificationType.Subscribe
        except Exception:  # noqa: BLE001 - 老版本可能没有这个枚举
            return None

    @staticmethod
    def _auto_toggle_title(item: Dict[str, Any]) -> str:
        """``朱色假面 S1 已播集全部入库`` 这样的标题。"""
        name = str(item.get("name") or "未知订阅")
        season = int(item.get("season") or 0)
        label = str(item.get("reason_label") or "")
        season_text = f" S{season}" if season > 0 else ""
        return f"{name}{season_text} {label}".strip()

    @staticmethod
    def _auto_toggle_text(item: Dict[str, Any]) -> str:
        """正文：原因 / 处理 / 后续，一眼看完。"""
        action = str(item.get("action") or "")
        #: 三种动作各有一句话，别再用「是暂停吗」这种二选一，
        #: 否则「已标记洗版完成」会被写成「已恢复订阅」，看着像状态被改了。
        handling = {
            "pause": (
                "已暂停订阅",
                "条件不再满足时会自动恢复",
            ),
            "resume": (
                "已恢复订阅",
                "条件再次满足时仍会自动暂停",
            ),
            "set_best": (
                # 1.18.5 起转洗版**不勾全集**（用户要求逐集洗），文案别再写「全集」。
                "已改为洗版订阅（逐集，不收全集）",
                "最后一集下完也只会继续等更高码版本，不会被当成普通订阅提前归档",
            ),
            "mark_complete": (
                "已标记洗版完成（不暂停、不删除）",
                "宿主的完成流程接手后不再重复搜索这几个集",
            ),
            "complete": (
                "已写入完成历史并删除订阅",
                "去「订阅历史」里能看到它，之后不会再被自动订阅",
            ),
            "delete": (
                "已删除订阅（未写完成历史）",
                "之后仍可能被重新发现并订阅",
            ),
        }
        handle, follow = handling.get(action, ("未做处理", "—"))
        lines = [
            f"原因：{item.get('reason_label') or '—'}",
            f"说明：{item.get('detail') or '—'}",
            f"处理：{handle}",
            f"后续：{follow}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _auto_toggle_link(item: Dict[str, Any]) -> str:
        """跳到 MP 订阅页对应的 tab。"""
        page = "movie" if str(item.get("kind") or "") == "movie" else "tv"
        return f"#/subscribe/{page}?tab=mysub"

    @staticmethod
    def _failed_label(row: Any) -> str:
        """失败条目的一句话（``name`` 可能带 ``season``）。"""
        if not isinstance(row, dict):
            return str(row)
        name = str(row.get("name") or row.get("id") or "未知")
        error = str(row.get("error") or row.get("message") or "写入失败")
        return f"{name}：{error}"

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

    # ---------------- 跟随订阅刷新
    def _refresh_progress(self) -> tuple:
        """读宿主「订阅刷新」任务的最近完成时间，以及它是否正在跑。

        只认订阅刷新：RSS 模式的 job id 是 ``subscribe_refresh``，spider 模式是
        ``subscribe_refresh|HH:MM`` 共 32 个。其余任务一概不看。

        为什么走调度器而不是自己探库：宿主刷新时 ``refresh_subscribe_progress``
        已经探过库、把结果写进 ``lack_episode``，刷新结束那一刻这个账最新。
        """
        try:
            #: 宿主自己的接口层（``app/api/endpoints/dashboard.py``）就是从
            #: ``app.application.scheduling`` 取调度器的；``app.scheduler`` 包里
            #: 没有 ``get_scheduler``（真机踩过：ImportError，静默失败）。
            from app.application.scheduling import get_scheduler

            scheduler = get_scheduler()
        except Exception as err:  # noqa: BLE001 - 调度器不可用时静默跳过
            logger.debug(f"[SubscribeCenter] 读取调度器失败：{err}")
            return None, False
        if scheduler is None:
            return None, False
        job_ids = ["subscribe_refresh"]
        try:
            for info in scheduler.list() or []:
                job_id = str(self._field(info, "id") or "")
                if job_id.startswith("subscribe_refresh"):
                    job_ids.append(job_id)
        except Exception as err:  # noqa: BLE001 - 拿不到任务列表就只问默认那个
            logger.debug(f"[SubscribeCenter] 列出调度任务失败：{err}")
        latest = None
        running = False
        for job_id in dict.fromkeys(job_ids):
            try:
                progress = scheduler.get_progress(job_id)
            except Exception as err:  # noqa: BLE001
                logger.debug(f"[SubscribeCenter] 读取任务进度失败（{job_id}）：{err}")
                continue
            if progress is None:
                continue
            status = str(self._field(progress, "status") or "")
            #: ``get_progress`` 的状态是英文（running/success/failed），但不同版本
            #: / 列表接口会混进中文（正在运行/等待），两种都认。
            if status in ("running", "waiting", "正在运行", "等待"):
                running = True
                continue
            finished = self._field(progress, "finished_at")
            if finished:
                text = str(finished)
                if latest is None or text > latest:
                    latest = text
        return latest, running

    def auto_toggle_follow_tick(self) -> None:
        """**同步**入口：每分钟看一眼宿主订阅刷新有没有跑完。

        两段式：先记下「看到刷新完成了」，下一次心跳（约 1 分钟后）才真正跑，
        让宿主的库事务落完。30 分钟内已经跑过就不再跑 —— spider 模式一天刷
        32 次，不去抖会跟着跑 32 轮。
        """
        import time

        cfg = self._auto_toggle_config()
        if not cfg["enabled"] or not cfg["follow_refresh"]:
            return
        finished, running = self._refresh_progress()
        if not finished or running:
            return
        state = self._auto_toggle_state()
        seen = state.get("refresh_follow")
        seen = dict(seen) if isinstance(seen, dict) else {}
        if str(seen.get("finished_at") or "") != finished:
            state["refresh_follow"] = {"finished_at": finished, "seen_at": time.time()}
            self._save_auto_toggle_state(state)
            logger.info(
                f"[SubscribeCenter] 订阅刷新已完成（{finished}），下一分钟跑自动启停"
            )
            return
        seen_at = seen.get("seen_at")
        if not isinstance(seen_at, (int, float)):
            return
        if time.time() - float(seen_at) < C.FOLLOW_REFRESH_SETTLE_SECONDS:
            return
        ran_at = seen.get("ran_at")
        if isinstance(ran_at, (int, float)):
            if time.time() - float(ran_at) < C.FOLLOW_REFRESH_DEBOUNCE_MINUTES * 60:
                return
        if self._auto_toggle_running()["running"]:
            logger.info("[SubscribeCenter] 自动启停：上一轮还在跑，跟随刷新跳过")
            return
        # 先记下「这次要跑了」再执行：万一执行体中途崩掉，也不会在下一分钟
        # 立刻再跑一遍。
        seen["ran_at"] = time.time()
        state["refresh_follow"] = seen
        self._save_auto_toggle_state(state)
        try:
            result = self._bridge.run(
                lambda: self.auto_toggle_run(reason="refresh"), timeout=1800
            )
        except Exception as err:  # noqa: BLE001 - 定时任务不能把异常抛给调度器
            logger.error(f"[SubscribeCenter] 跟随订阅刷新失败：{err}", exc_info=True)
            return
        if result is None:
            logger.info("[SubscribeCenter] 自动启停：已有任务在跑，跟随刷新跳过")

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

    async def _tmdb_tv_status(self, media_id: str, now: float, ttl: float) -> str:
        """取整部剧的完结状态（``Ended`` / ``Canceled`` / ``Returning Series``）。

        为什么要单独问一次：``TmdbEpisode`` / ``TmdbSeason`` 两个模型里**都没有**
        ``status`` 字段（见宿主 ``app/schemas/tmdb.py``），只有整部剧的详情里有。
        它只在「本季播出表里已经没有未来集」时才有意义，所以调用方按需触发，
        并行不浪费请求。

        取不到就返回空串 —— 判定侧把空串当「不知道」，回落到其它两个兜底条件，
        不会因为一次请求失败就把还在播的剧判成季终。
        """
        cache = self.__dict__.setdefault("_tv_status_cache", {})
        key = str(media_id)
        hit = cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        status = ""
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi
            from app.schemas.types import MediaType

            info = await TmdbApi().async_get_info(mtype=MediaType.TV, tmdbid=int(key))
            if isinstance(info, dict):
                status = str(info.get("status") or "").strip()
        except Exception as err:  # noqa: BLE001 - 取不到按「不知道」处理
            logger.debug(f"[SubscribeCenter] 取剧集状态失败 {key}：{err}")
        cache[key] = (now, status)
        return status

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
                    cache[key] = (now, [(basis, 0)], {})
                    self._note_movie_kind(media_id, kind)
                return

            # ---- 剧集 / 剧集组 ----
            async with semaphore:
                raw_list: List[Any] = []
                try:
                    from app.chain.tmdb import TmdbChain

                    if isinstance(season_key, str) and season_key.startswith("g:"):
                        raw_list = list(
                            await TmdbChain().async_tmdb_episodes(
                                tmdbid=int(media_id),
                                season=0,
                                episode_group=season_key[2:],
                            )
                            or []
                        )
                    else:
                        raw_list = list(
                            await TmdbChain().async_tmdb_episodes(
                                tmdbid=int(media_id), season=int(season_key)
                            )
                            or []
                        )
                except Exception as err:  # noqa: BLE001 - 链不可用时回退
                    logger.debug(f"[SubscribeCenter] 链取季失败 {key}：{err}")

                if not raw_list:
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
                                raw_list.extend(
                                    list(
                                        self._field(season_item, "episodes", []) or []
                                    )
                                )
                        else:
                            detail = await asyncio.to_thread(
                                tmdb.get_tv_season_detail,
                                int(media_id),
                                int(season_key),
                            )
                            raw_list = list(self._field(detail, "episodes", []) or [])
                    except Exception as err:  # noqa: BLE001
                        logger.debug(f"[SubscribeCenter] 回退取季失败 {key}：{err}")

                if not raw_list:
                    return

                episodes: List[tuple] = []
                extra: set = set()
                numbers: set = set()
                for item in raw_list:
                    number = int(self._field(item, "episode_number") or 0)
                    if number <= 0:
                        continue
                    numbers.add(number)
                    day = str(self._field(item, "air_date") or "")[:10]
                    if day:
                        episodes.append((day, number))
                    else:
                        #: TMDB 常见「最后一集先建条目、日期还空着」：以前这里
                        #: 直接丢掉，播出表看起来就是「已播完」，季终判定跟着错。
                        #: 集号大于最后已播集的，本质就是「还没播的未来集」。
                        extra.add(number)
                if not episodes:
                    return
                episodes.sort()
                last_number = max(numbers) if numbers else 0
                last_aired = max(number for _, number in episodes)
                last_type = ""
                for item in raw_list:
                    if int(self._field(item, "episode_number") or 0) == last_aired:
                        last_type = str(self._field(item, "episode_type") or "")
                        break
                info = {
                    "total": last_number,
                    "extra": sorted(number for number in extra if number > last_aired),
                    #: 季中休更标记：最后一集是「mid_season」说明本季没真完
                    "mid_season": last_type == "mid_season",
                    "finale_episode": last_type == "finale",
                    "status": "",
                }
                if not any(day > date_text for day, _ in episodes):
                    #: 表里已经没有未来集了，才值得花一次请求问「这部剧完结了没」。
                    #: 反过来只要还有未来集就一定没完结，不必问。
                    info["status"] = await self._tmdb_tv_status(media_id, now, ttl)
                cache[key] = (now, episodes, info)

        if targets:
            await asyncio.gather(*(fetch(key) for key in targets))

        index: Dict[Any, List[Any]] = {}
        season_info: Dict[Any, Dict[str, Any]] = self.__dict__.setdefault(
            "_season_info_cache", {}
        )
        for row in rows:
            media_id = str(getattr(row, "media_id", "") or "")
            group = str(getattr(row, "episode_group", "") or "").strip()
            key = (media_id, f"g:{group}" if group else int(getattr(row, "season", 0) or 0))
            # build_today 用 (media_id, season) 查索引：这里统一按 season 再登记一份
            legacy_key = (media_id, int(getattr(row, "season", 0) or 0))
            if key in cache:
                entry = cache[key]
                index[legacy_key] = entry[1]
                info = entry[2] if len(entry) > 2 else {}
                if info:
                    season_info[legacy_key] = info
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

    async def api_history_clear(
        self, request: Optional[api_schemas.HistoryClearRequest] = None
    ) -> Any:
        """清空发现流水（可按来源/判决/关键词只清一部分）。

        注解必须是**具体的 pydantic 模型**：写成 ``Any`` 时 FastAPI 会把整个
        body 当 query 参数，前端拿到 422「请求参数不正确」（1.7.1 真机）。
        """
        return await api_controller.api_history_clear(self, request)

    async def api_presets(self) -> Any:
        """返回可用的场景预设清单。"""
        return await api_controller.api_presets(self)

    async def api_preset_apply(self, request: api_schemas.PresetRequest) -> Any:
        """套用一个场景预设（``reset`` = 恢复出厂默认）。"""
        return await api_controller.api_preset_apply(self, request)

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

        # 跟随订阅刷新：只盯宿主「订阅刷新」任务，它一跑完就补一轮自动启停。
        # 每分钟只读一次调度器内存里的进度，不发任何网络请求。
        if auto_cfg["enabled"] and auto_cfg["follow_refresh"]:
            try:
                services.append(
                    {
                        "id": "subscribecenter_autotoggle_follow",
                        "name": "胖虎订阅中心 跟随订阅刷新",
                        "trigger": CronTrigger(minute="*"),
                        "func": self.auto_toggle_follow_tick,
                    }
                )
            except Exception as err:  # pragma: no cover
                logger.warning(f"[SubscribeCenter] 跟随刷新任务注册失败：{err}")

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
                # 电影发行日兜底：来源没给日期时用 TMDB 发行日补上，
                # 再按「发行日 + 宽限期」判窗口（关掉就回到旧的「无日期跳过」）
                movie_release_lookup=(
                    self._movie_release_lookup
                    if self._config.get("movie_release_fallback", True)
                    else None
                ),
                movie_grace_days=max(
                    0,
                    self._int_config(
                        "movie_release_grace_days", C.DEFAULT_MOVIE_RELEASE_GRACE
                    ),
                ),
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

    # ---------------------------------------------------------- 电影发行日兜底

    async def _movie_tmdb_id(
        self, media_source: str, media_id: str
    ) -> Optional[int]:
        """把条目上的 ``media_id`` 换成 TMDB ID。

        豆瓣榜单条目的 ``media_id`` 解析后通常已经是 TMDB ID，但自定义源
        可能给的是来源自己的 ID —— 直接拿去查 TMDB 会查到另一部片子，
        那会把别人的发行日当成它的，属于最坏的一种错。
        """
        value = str(media_id or "").strip()
        if not value.isdigit():
            return None
        if media_source in ("", "themoviedb"):
            return int(value)
        try:
            from app.chain.media import MediaChain
            from app.schemas.types import MediaType

            media = await MediaChain().async_recognize_media(
                mtype=MediaType.MOVIE, media_source=media_source, media_id=value
            )
            tmdb_id = self._field(media, "tmdb_id")
            return int(tmdb_id) if tmdb_id else None
        except Exception as err:  # noqa: BLE001 - 识别失败就跳过这部
            logger.debug(
                f"[SubscribeCenter] 电影识别失败 {media_source}:{value}：{err}"
            )
            return None

    async def _movie_release_lookup(
        self, media_source: str, media_id: str
    ) -> Optional[Tuple[str, str]]:
        """电影发行日兜底：``(YYYY-MM-DD, 类型中文名)``，查不到返回 ``None``。

        只对「来源没给日期」的电影调用（豆瓣榜单类 RSS 只有片名），
        量级 = 每轮榜单里的电影数，且进程内缓存 12 小时。

        优先级与自动启停完全一致（``autotoggle.movie_basis``）：数字发行 →
        实体 → 院线 → 首映 → 电视 → 顶层 ``release_date``。**必须优先数字发行**：
        院线首映日往往比数字版早几周，拿它判窗口会把刚上线数字版的片子
        判成「已过去」—— 而那时才是站点真正出种的时候。

        失败一律返回 ``None``：该片继续按「来源没日期」跳过，绝不猜。
        """
        from .core import autotoggle

        key = f"{media_source}:{media_id}"
        cache = self.__dict__.setdefault("_movie_release_lookup_cache", {})
        hit = cache.get(key)
        if hit and time.time() - hit[0] < 12 * 3600:
            return hit[1]

        result: Optional[Tuple[str, str]] = None
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi
            from app.schemas.types import MediaType

            tmdb_id = await self._movie_tmdb_id(media_source, media_id)
            if tmdb_id:
                info = await TmdbApi().async_get_info(MediaType.MOVIE, tmdb_id)
                records = autotoggle.release_records(info)
                date_text, kind = autotoggle.movie_basis(records, best_version=False)
                if date_text:
                    result = (
                        date_text,
                        autotoggle.RELEASE_KIND_LABELS.get(kind, kind or "发行日"),
                    )
        except Exception as err:  # noqa: BLE001 - 单部查不到只影响它自己
            logger.debug(
                f"[SubscribeCenter] 电影发行日查询失败 {key}：{err}"
            )

        if len(cache) > 2000:
            cache.clear()
        cache[key] = (time.time(), result)
        return result

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
        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

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

        try:
            from .sources.qqvideo import QqVideoSource

            sources.append(QqVideoSource())
        except Exception as err:  # noqa: BLE001 - 单源构造失败不阻塞其他源
            logger.warning(f"[SubscribeCenter] 腾讯视频源不可用：{err}")

        try:
            from .sources.bilibili import BilibiliSource

            sources.append(BilibiliSource())
        except Exception as err:  # noqa: BLE001 - 单源构造失败不阻塞其他源
            logger.warning(f"[SubscribeCenter] B 站番剧源不可用：{err}")
        return sources

    def _enabled_sources(self) -> List[str]:
        """返回配置中已启用**且已实现**的源标识。"""
        mapping = {
            C.SOURCE_TMDB: "enable_tmdb",
            C.SOURCE_ANILIST: "enable_anilist",
            C.SOURCE_DOUBAN_RSS: "enable_douban_rss",
            C.SOURCE_QQ_VIDEO: "enable_qq_video",
            C.SOURCE_BILIBILI: "enable_bilibili",
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
        # 各源贡献：总数字看不出「哪个源在出活」，豆瓣全榜一天 300+ 条、
        # 腾讯 84 条，混在一起时用户无从判断该关哪个。
        breakdown = data.get("source_breakdown") or []
        if breakdown:
            logger.info(
                "[来源明细] "
                + "；".join(
                    f"{C.source_label(row['source'])} 发现 {row['fetched']} / 采纳 "
                    f"{row['added']} / 跳过 {row['skipped']}"
                    + (f" / 待确认 {row['pending']}" if row.get("pending") else "")
                    + (f" / 出错 {_short_error(row.get('error'))}" if row.get("error") else "")
                    for row in breakdown
                )
            )
        timings = data.get("timings") or {}
        if timings:
            logger.info(
                f"[耗时] 合计 {timings.get('total', 0)}s（拉取 {timings.get('fetch', 0)}s / "
                f"解析 {timings.get('resolve', 0)}s / 过滤 {timings.get('filter', 0)}s / "
                f"写入 {timings.get('write', 0)}s）"
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

        # 各源贡献：只报总数时用户无法判断「哪个源在出活」——豆瓣全榜与腾讯
        # 同时开着，只看到「新增 3 条」根本不知道是谁贡献的。
        breakdown = data.get("source_breakdown") or []
        contributors = [row for row in breakdown if int(row.get("added") or 0) > 0]
        if contributors:
            parts = [
                f"{C.source_label(row['source'])} {int(row['added'])}"
                for row in contributors
            ]
            lines.append("来源：" + " / ".join(parts))

        if data.get("failed_sources"):
            errors = data.get("source_errors") or {}
            detail = [
                f"{C.source_label(source)}（{_short_error(errors.get(source)) or '原因见日志'}）"
                for source in data["failed_sources"]
            ]
            lines.append("失败：" + "；".join(detail))
        if data.get("limit_hit"):
            lines.append("已触达每日写入上限")
        timings = data.get("timings") or {}
        if timings.get("total"):
            lines.append(
                "耗时：{total}s（拉取 {fetch}s / 解析 {resolve}s / 过滤 {filter}s / 写入 {write}s）".format(
                    total=timings.get("total", 0),
                    fetch=timings.get("fetch", 0),
                    resolve=timings.get("resolve", 0),
                    filter=timings.get("filter", 0),
                    write=timings.get("write", 0),
                )
            )
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
                (C.SOURCE_QQ_VIDEO, "enable_qq_video"),
                (C.SOURCE_BILIBILI, "enable_bilibili"),
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
            records = [r for r in records if _history_matches(r, keyword=keyword)]
        # 决策 tab 的计数：在 source / keyword 过滤**之后**、decision 过滤**之前**
        # 统计 —— 这样「选 AniList 后，待确认显示的是 AniList 的条数」，
        # 而不是三个源的合计（真机反馈的就是这个）。
        counts = _decision_counts(records)
        if decision:
            records = [r for r in records if r.get("decision") == decision]
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

    # ------------------------------------------------------------------ 场景预设

    def preset_list(self) -> List[Dict[str, str]]:
        """可用的场景预设（前端按钮直接渲染这份）。"""
        from .core.presets import describe

        return describe()

    def apply_preset(self, *, name: str) -> Dict[str, Any]:
        """套用一个场景预设（``reset`` = 恢复出厂）。

        只改**和场景强相关**的配置项，RSSHub 域名 / cron / 通知 / 自动启停等
        用户自己配过的内容原样保留 —— 预设是「帮我选好追什么」，不是整份覆盖。
        写库后顺手重建调度：窗口/阈值变了，下一轮就该按新参数跑。
        """
        from .core.presets import apply as apply_preset_config
        from .core.presets import title_of

        updated = apply_preset_config(dict(self._config), name)
        # 走 save_config 而不是 update_config：前者是合并写入，不会丢掉
        # 预设没提到的键（宿主 update_config 是整份覆盖）。
        patch = {key: value for key, value in updated.items() if self._config.get(key) != value}
        self.save_config(**patch)
        # 不重建调度：预设不动 cron，只改发现参数，下一轮自然按新配置跑。
        # 重建会连带跑一遍「空转检测」，可能把刚开的源又关掉。
        logger.info(
            "[SubscribeCenter] 已套用预设「%s」，改动 %s 项：%s"
            % (title_of(name), len(patch), ", ".join(sorted(patch)))
        )
        return {
            "success": True,
            "name": name,
            "title": title_of(name),
            "changed": len(patch),
            "config": dict(self._config),
        }

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

    def clear_history(
        self,
        *,
        source: str = "",
        decision: str = "",
        keyword: str = "",
        key: str = "",
        older_than_days: int = 0,
    ) -> api_schemas.HistoryClearResult:
        """清空发现流水（也可以只清一部分）。

        :param source: 只清这个来源（``tmdb`` / ``anilist`` / ``douban_rss`` …）
        :param decision: 只清这种判决（``added`` / ``pending_review`` …）
        :param keyword: 只清标题/原因命中的记录
        :param key: 只清这一条（流水行的「删掉」按钮，取 :func:`_record_key`）
        :param older_than_days: 只清 N 天前的记录（``0`` = 不限）

        全部留空等价于「整表清空」。

        被清掉的记录**同时**从持久去重表里移除：去重表才是「流水记过就别再订」
        的实际依据 —— 只清显示用的流水会变成「界面上空了，但依然订不上」。
        """
        records = self._history()
        targets: List[Dict[str, Any]] = records
        if key:
            targets = [record for record in records if _record_key(record) == key]
        elif source or decision or keyword or older_than_days > 0:
            targets = [
                record
                for record in records
                if _history_matches(
                    record,
                    source=source,
                    decision=decision,
                    keyword=keyword,
                    older_than_days=older_than_days,
                    today_text=today(self._tz()).isoformat(),
                )
            ]
        removed = len(targets)
        if not removed:
            return api_schemas.HistoryClearResult(removed=0, remaining=len(records))

        doomed = {id(record) for record in targets}
        remaining = [record for record in records if id(record) not in doomed]
        self.save_data(DATA_KEY_HISTORY, remaining)

        from .core.writer import recorded_key

        dropped: Set[str] = set()
        for record in targets:
            media_source = record.get("media_source")
            media_id = record.get("media_id")
            if media_source and media_id:
                dropped.add(recorded_key(media_source, media_id, record.get("season")))
        if dropped:
            stored = self.get_data(DATA_KEY_RECORDED)
            if isinstance(stored, (list, tuple, set)):
                kept = [str(item) for item in stored if item and str(item) not in dropped]
                self.save_data(DATA_KEY_RECORDED, kept)

        if not remaining:
            # 整表清了才动 last_run：部分清理时它仍对应真实跑过的这一轮
            state = self._state()
            if "last_run" in state:
                state.pop("last_run", None)
                self._save_state(state)
        logger.info(
            "[SubscribeCenter] 发现流水已清理 %s 条（剩余 %s 条）" % (removed, len(remaining))
        )
        return api_schemas.HistoryClearResult(removed=removed, remaining=len(remaining))

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
            from app.sdk.queries import (
                QueryPageRequest,
                SubscriptionFilter,
                async_list_subscriptions,
            )

            from .core.host import media_source_enum

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
        records = _prune_history(records, today_text=today(self._tz()).isoformat())
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
    "skipped_unverified": 2,
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


def _short_error(text: Any, limit: int = 60) -> str:
    """把异常文本压成一句人能读的原因（通知里只放一句）。

    源抛出来的往往是 ``HTTPStatusError: Server error '503 Service Unavailable'
    for url 'https://rsshub...'``，全文塞进通知会占满一屏，只取第一行前 N 个字。
    """
    raw = str(text or "").strip()
    if not raw:
        return ""
    first = raw.splitlines()[0].strip()
    # 去掉常见的异常类名前缀（``ValueError: xxx`` → ``xxx``）
    if ": " in first and " " not in first.split(": ", 1)[0].strip():
        first = first.split(": ", 1)[1].strip()
    return first if len(first) <= limit else first[: limit - 1] + "…"


def _history_matches(
    record: Dict[str, Any],
    *,
    source: str = "",
    decision: str = "",
    keyword: str = "",
    older_than_days: int = 0,
    today_text: str = "",
) -> bool:
    """一条流水是否命中筛选条件（分页与「分 tab 清理」共用同一套判断）。

    共用是为了避免「界面筛出 30 条，点清空却删了别的」—— 筛选口径必须
    与清理口径完全一致。
    """
    if source and str(record.get("source") or "") != source:
        return False
    if decision and str(record.get("decision") or "") != decision:
        return False
    if keyword:
        needle = str(keyword).strip().casefold()
        if (
            needle not in str(record.get("title") or "").casefold()
            and needle not in str(record.get("reason") or "").casefold()
        ):
            return False
    if older_than_days > 0:
        from datetime import date, timedelta

        text = str(record.get("run_at") or record.get("discovered_at") or "")[:10]
        if not text:
            return False
        try:
            cutoff = (
                date.fromisoformat(today_text[:10] or date.today().isoformat())
                - timedelta(days=int(older_than_days))
            ).isoformat()
        except ValueError:
            return False
        if text >= cutoff:
            return False
    return True


def _record_date(record: Dict[str, Any]) -> str:
    """流水记录的日期（``YYYY-MM-DD``），取不到就返回空串。"""
    for key in ("run_at", "discovered_at"):
        text = str(record.get(key) or "")
        if len(text) >= 10:
            return text[:10]
    return ""


def _prune_history(
    records: List[Dict[str, Any]],
    *,
    keep_days: int = HISTORY_KEEP_DAYS,
    hard_limit: int = HISTORY_HARD_LIMIT,
    today_text: str = "",
) -> List[Dict[str, Any]]:
    """按天清理流水，再套一个硬上限。

    :param keep_days: 保留最近几天（``<=0`` 表示不按天清理，只受 ``hard_limit`` 约束）
    :param hard_limit: 硬上限条数（``<=0`` 表示不限）
    :param today_text: 今天（``YYYY-MM-DD``），留空则取系统当前日期

    为什么不再用「固定 500 条」：豆瓣全榜一天 300+ 条，两三天就把一周前的记录
    挤掉了，用户回头查「上周订过什么」就查不到；而跑得少的用户又会一直留着
    几个月前的记录。按天保留才是用户能理解的口径。
    """
    if not records:
        return []
    rows = list(records)
    if keep_days > 0:
        from datetime import date, timedelta

        if today_text:
            base = today_text[:10]
        else:
            base = date.today().isoformat()
        try:
            cutoff = (date.fromisoformat(base) - timedelta(days=max(0, keep_days))).isoformat()
        except ValueError:
            cutoff = ""
        if cutoff:
            # 没有日期的老记录一律保留：宁可多留，也不能凭「读不出日期」就把证据删了
            rows = [row for row in rows if not _record_date(row) or _record_date(row) >= cutoff]
    if hard_limit > 0 and len(rows) > hard_limit:
        rows = rows[-hard_limit:]
    return rows


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
