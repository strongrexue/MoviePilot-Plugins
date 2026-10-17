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
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .controller import api as api_controller
from .controller import schemas as api_schemas
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
    plugin_version = "1.5.3"
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
            notify_each=bool(self._config.get("notify_each_subscription", True)),
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
        if not self._enabled() or not self._config.get("discovery_page_enabled"):
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

    async def api_subscriptions(self) -> Any:
        """订阅总览：宿主订阅按状态分组 + 明细。"""
        return await api_controller.api_subscriptions(self)

    async def api_run_once(self) -> Any:
        """手动触发一次发现任务。"""
        return await api_controller.api_run_once(self)

    async def api_preview(self) -> Any:
        """只读预览：跑一次但不写入。"""
        return await api_controller.api_preview(self)

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
        """注册每日发现定时任务。

        :note: ``trigger`` 必须是 ``CronTrigger`` 对象；本方法整体兜底 ——
            任何异常都只记日志并降级为空列表（注册异常会拖垮插件加载）。
        :note: cron 在**注册时**读取，用户改配置后必须重新保存配置才会重建任务。
        """
        if not self._enabled():
            return []
        try:
            from apscheduler.triggers.cron import CronTrigger

            cron = self._normalize_cron(self._config.get("cron"))
            return [
                {
                    "id": "subscribecenter_discover",
                    "name": "胖虎订阅中心 每日发现",
                    "trigger": CronTrigger.from_crontab(cron),
                    "func": self.run_scheduled,
                }
            ]
        except Exception as err:  # pragma: no cover - 调度依赖缺失时降级
            logger.warning(f"[SubscribeCenter] 注册定时任务失败：{err}")
            return []

    def stop_service(self) -> None:
        """释放插件资源；必须可重复、安全调用。

        v0.1.0 无自建线程/连接，只需清引用（流水线互斥锁是进程内的轻量状态，
        保留可避免重载后出现两把锁）。
        """
        self._resolver = None
        self._last_summary = {}

    # ------------------------------------------------------------------ 运行入口

    def run_scheduled(self) -> None:
        """**同步**入口：由 apscheduler 在自己的线程里调用。

        该线程没有事件循环，因此必须经 :class:`PipelineBridge` 桥接。
        已有运行在跑时直接跳过（不排队）。
        """
        if not self._enabled():
            logger.info("[SubscribeCenter] 插件未启用，跳过本次定时发现")
            return
        started = local_now_text(self._tz())
        logger.info(f"[SubscribeCenter] 定时发现开始（{started}）")
        summary = self._bridge.run(
            lambda: self._pipeline_coroutine(force_dry_run=False), timeout=600
        )
        if summary is None:
            logger.info("[SubscribeCenter] 已有流水线在运行，本次定时发现跳过")
            return
        self._after_run(summary)

    async def run_once(self) -> Dict[str, Any]:
        """**异步**入口：供 ``POST /run_once`` 调用。

        与定时任务共用同一把互斥锁；已在运行时返回 ``skipped=True``。
        """
        summary = await self._bridge.run_async(
            lambda: self._pipeline_coroutine(force_dry_run=False), timeout=600
        )
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

    async def _pipeline_coroutine(self, *, force_dry_run: bool = False) -> RunSummary:
        """构造并执行一次流水线（三种入口共用的唯一实现）。

        :param force_dry_run: 强制只读（预览用）。预览**不消耗**每日写入额度。
        """
        resolver = self._resolver
        if resolver is None:
            # init_plugin 未跑过（例如直接调 API）：按需重建，避免 AttributeError
            from .core.host import HostTmdbResolver

            resolver = IdentityResolver(HostTmdbResolver(), self._cache)
            self._resolver = resolver

        first_run = not bool(self._state().get(C.STATE_FIRST_RUN_DONE))
        if first_run:
            logger.info(
                "[SubscribeCenter] 首次运行：强制 dry-run，只记录不写入。"
                "确认结果后在前端「确认开始写入」再放开。"
            )

        # 映射缓存攒批落盘：一次运行可能解析 200+ 条，逐条落盘等于 200+ 次
        # 数据库写入。batch() 期间只标脏，退出时统一写一次。
        with self._cache.batch():
            return await run_pipeline(
                sources=self._build_sources(),
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
                dry_run=bool(self._config.get("dry_run")) or force_dry_run,
                first_run=first_run,
                already_written_today=self._written_today(),
                tz_name=self._tz(),
        )

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

        # 首次运行标记：只有**真正跑完一次**才置位
        state = self._state()
        if summary.first_run:
            state[C.STATE_FIRST_RUN_DONE] = True
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
            )
        ]
        return api_schemas.PluginStatus(
            plugin_version=self.plugin_version,
            enabled=self._enabled(),
            dry_run=bool(self._config.get("dry_run")),
            first_run_completed=bool(state.get(C.STATE_FIRST_RUN_DONE)),
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

    async def subscription_overview(self) -> Dict[str, Any]:
        """读取宿主订阅表，按状态统计并返回明细（供「订阅总览」标签页）。

        这里用 **ORM 直连**（``app.db.async_session_scope`` + ``Subscribe``），
        不走宿主 SDK 的 ``async_list_subscriptions`` —— 后者依赖
        「插件数据查询服务」，在某些调用路径下尚未配置就会直接抛
        ``插件数据查询服务尚未配置``（真机：接口 500，前端只显示「未知错误」）。
        ORM 读取只依赖数据库连接，稳定得多。
        """
        from app.db import async_session_scope
        from app.db.models.subscribe import Subscribe
        from sqlalchemy import select

        items: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {}
        try:
            async with async_session_scope() as session:
                rows = (
                    await session.execute(
                        select(Subscribe)
                        .order_by(Subscribe.id.desc())
                        .limit(C.SUBSCRIBE_OVERVIEW_LIMIT)
                    )
                ).scalars().all()
        except Exception as err:  # noqa: BLE001 - 查询失败不该炸整个页面
            logger.error(f"[SubscribeCenter] 读取订阅总览失败：{err}", exc_info=True)
            return {"total": 0, "counts": {}, "items": [], "error": str(err)}

        for row in rows:
            state = _display_state(row)
            counts[state] = counts.get(state, 0) + 1
            items.append(
                {
                    "id": getattr(row, "id", None),
                    "name": getattr(row, "name", None),
                    "year": getattr(row, "year", None),
                    "season": getattr(row, "season", None),
                    "total_episode": getattr(row, "total_episode", None),
                    "lack_episode": getattr(row, "lack_episode", None),
                    "state": state,
                    "media_source": getattr(row, "media_source", None),
                    "media_id": getattr(row, "media_id", None),
                    "poster": getattr(row, "poster", None),
                    "last_update": getattr(row, "last_update", None),
                }
            )
        return {"total": len(items), "counts": counts, "items": items}

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
            media_source = str(record.get("media_source") or "")
            media_id = str(record.get("media_id") or "")
            if media_source and media_id:
                return f"{media_source}:{media_id}"
            return "{}:{}:{}".format(
                record.get("source") or "",
                record.get("title") or "",
                record.get("year") or "",
            )

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
    def _normalize_cron(value: Any) -> str:
        """校验 5 段式 cron；非法值回落默认，避免拖垮 ``get_service()``。"""
        text = str(value or "").strip()
        if len(text.split()) == 5:
            return text
        if text:
            logger.warning(
                f"[SubscribeCenter] cron 表达式非法（{text!r}），已回落默认 {C.DEFAULT_CRON}"
            )
        return C.DEFAULT_CRON


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


def _display_state(row: Any) -> str:
    """把订阅行折算成界面展示用的状态码。

    宿主的状态码只有 N/R/P/S，而界面上「订阅完成」是靠集数推导的
    （``total_episode > 0 且 lack_episode == 0``）—— 计数与卡片着色必须用
    同一个口径，否则筛选条上的数字和卡片颜色会对不上。
    """
    state = str(getattr(row, "state", None) or "N")
    if state == "S":
        return "S"
    try:
        total = int(getattr(row, "total_episode", None) or 0)
        lack = int(getattr(row, "lack_episode", None) or 0)
    except (TypeError, ValueError):
        return state
    if total > 0 and lack == 0:
        return "D"
    return state


def _source_counts(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计各数据源条数（喂给前端「按源」tab）。"""
    counts: Dict[str, int] = {}
    for record in records:
        source = str(record.get("source") or "")
        if not source:
            continue
        counts[source] = counts.get(source, 0) + 1
    return counts


def _history_item(record: Dict[str, Any]) -> Dict[str, Any]:
    """把流水记录裁剪成 :class:`~.controller.schemas.HistoryRecord` 的字段。

    缺失的文本字段补空串、可选字段补 ``None`` —— 旧版本写入的流水可能没有新键，
    不能因此让整个分页接口 500。
    """
    item: Dict[str, Any] = {key: str(record.get(key) or "") for key in _HISTORY_TEXT_FIELDS}
    item["success"] = bool(record.get("success"))
    for key in _HISTORY_OPTIONAL_FIELDS:
        item[key] = record.get(key)
    return item


__all__ = ["SubscribeCenter"]
