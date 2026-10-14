"""胖虎媒体中心 - MoviePilot V3 插件（TgMediaCenter）。

当前进度：P8 —— 消息交互（私聊发 115 / 磁力 / eD2k 链接直接转存并回执）；
P7 打磨已完成（运行详情与仪表盘、通知接入、限流退避收口、测试与真实加载验证）。
- 已实现：① TG 核心凭证（Telethon 运行时、登录向导、会话持久化、对话列表缓存）；
  ② 115 网盘（扫码登录态、空间配额、分享转存、磁力/eD2k 离线、分批推送、成功/失败通知）；
  ④ TG 资源监控（事件接入、聚合窗口、宿主识别、缺失判断、推送队列）；
  ⑤ 历史消息缓存（实时写入、位点增量/时间范围同步、检索统计、订阅触发回搜）；
  ⑥ TG 通用转发（关键词/扩展名匹配、内容转换、置顶，与监控共用事件流水线与全局冷却）；
  ⑦ 运行详情页与仪表盘（/overview 聚合）+ 插件级共享冷却门（读写共用 FloodWait 退避）；
  ⑧ 消息交互（监听宿主用户消息事件，私聊发链接即转存 115 并回执：新转存 / 已转存过 / 失败原因）；
  ⑩ P9 重复获取治理（P9-1：宿主能力探针 + 反向开关「暂停新增订阅搜索」，默认关）。
"""
from typing import Any, Dict, List, Optional, Tuple
import time

from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .controller import api as api_controller
from .controller import schemas as api_schemas
from .core.cooldown import CooldownGate
from .model import get_models
from .model.migration import ensure_schema
from .modules.cache import CacheModule
from .modules.credentials import CredentialsModule
from .modules.forward import ForwardModule
from .modules.interactive import InteractiveModule
from .modules.monitor import MonitorModule
from .modules.pan115 import Pan115Module

try:  # 一次性任务调度接口；缺失时降级为懒连接
    from app.sdk import scheduler as scheduler_sdk
except Exception:  # pragma: no cover
    scheduler_sdk = None  # type: ignore[assignment]


class TgMediaCenter(_PluginBase):
    """胖虎媒体中心插件入口。"""

    plugin_name = "胖虎媒体中心"
    plugin_desc = "Telegram 资源监控、历史消息缓存、115 网盘转存与 TG 通用转发。"
    plugin_icon = "https://raw.githubusercontent.com/strongrexue/MoviePilot-Plugins/main/icons/tgmediacenter.png"
    plugin_color = "#229ED9"
    plugin_version = "1.9.1"
    plugin_author = "strongrexue"
    author_url = "https://github.com/strongrexue"
    plugin_config_prefix = "tgmediacenter_"
    plugin_order = 20
    auth_level = 1

    def __init__(self, *args, **kwargs) -> None:
        """建立当前插件实例独享的配置快照与模块容器。"""
        super().__init__(*args, **kwargs)
        self._config: Dict[str, Any] = {}
        self._credentials: Optional[CredentialsModule] = None
        self._pan115: Optional[Pan115Module] = None
        self._monitor: Optional[MonitorModule] = None
        self._cache: Optional[CacheModule] = None
        self._forward: Optional[ForwardModule] = None
        self._interactive: Optional[InteractiveModule] = None

    # ------------------------------------------------------------------ 配置快照

    @property
    def config(self) -> Dict[str, Any]:
        """返回当前生效配置。"""
        return self._config

    def save_config(self, **patch: Any) -> None:
        """合并写入配置。

        宿主 ``update_config()`` 是整份覆盖，因此统一走本方法：先合并当前快照，
        再整体写回，避免只写部分字段时丢掉其它配置。
        """
        merged = dict(self._config)
        merged.update(patch)
        self._config = merged
        self.update_config(merged)

    def drop_config(self, *keys: str) -> None:
        """从配置中移除指定键。

        用于把**后端自管状态**从用户配置里迁出：前端配置表单会整份回写配置，
        留在配置里的自管状态（如 TG 会话串）会被覆盖丢失。
        """
        merged = dict(self._config)
        removed = [key for key in keys if key in merged]
        if not removed:
            return
        for key in removed:
            merged.pop(key, None)
        self._config = merged
        self.update_config(merged)

    def _enabled(self) -> bool:
        """当前配置是否已启用插件。"""
        return bool(self._config.get("enabled"))

    # ------------------------------------------------------------------ 生命周期

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """读取配置、重建模块并安排 TG 客户端延迟连接；必须允许重复调用。"""
        self.stop_service()

        merged = self.default_config()
        merged.update(config or {})
        self._config = merged

        # P7 退避收口：全局冷却门改为**插件级单例**——转发/置顶（写）与刷新对话/
        # 回溯历史（读）共享同一份 FloodWait 退避状态（FloodWait 是账号级的，
        # 读触发之后写同样会被拒）。
        self._gate = CooldownGate(self._cooldown_seconds())
        self._credentials = CredentialsModule(self)
        self._pan115 = Pan115Module(self)
        # 缓存模块先建：监控流水线的「关心会话」是「监控 ∪ 转发 ∪ 缓存」，事件入口要用到它
        self._cache = CacheModule(self)
        # 监听宿主「新增订阅」事件：新增订阅后秒级触发缓存回搜（定时检查仍作兜底）
        self._install_subscribe_listener()
        # ⑧ 监听宿主「用户消息」事件：私聊发 115 / 磁力 / ed2k 链接即转存并回执
        self._interactive = InteractiveModule(self)
        self._install_user_message_listener()
        # ⑥ 转发模块与 ④ 监控模块共用同一条事件流水线（后者持有流水线生命周期）
        self._forward = ForwardModule(self)
        self._monitor = MonitorModule(self)
        # 旧版本把 TG 会话串存在配置里；配置会被「保存配置」整份覆盖，需迁到插件数据
        self._credentials.migrate_session_from_config()
        # 存量库追平：push_task 的 chat_id/message_id 升 BIGINT（1.4.1 及以前是
        # 32 位 Integer，TG 频道 ID 超出 int32 导致入队失败）；hit_log 补 kind 列。
        try:
            ensure_schema(self.get_database())
        except Exception as err:  # pragma: no cover - 迁移失败不阻断启动
            logger.warning(f"[TgMediaCenter] 插件表结构迁移失败：{err}")

        # ④ 资源监控 / ⑥ 通用转发：启用且有监听规则时启动流水线（TG 未连接也会先起来，
        # 处理器注册由流水线健康检查在运行时就绪后自动补上）。
        # 只开缓存（不开监控 / 转发）时同样要起流水线——缓存写入是流水线的下游。
        try:
            want_monitor = self._monitor.enabled() and self._monitor.watched_chat_ids()
            want_forward = self._forward.enabled() and self._forward.watched_chat_ids()
            want_cache = self._cache.enabled() and self._cache.chat_ids()
            if want_monitor or want_forward or want_cache:
                self._monitor.start()
        except Exception as err:  # pragma: no cover - 监控启动失败不影响其余能力
            logger.warning(f"[TgMediaCenter] 启动资源监控流水线失败：{err}")

        # 建立连接是网络操作，交给一次性任务执行，不阻塞插件加载。
        # 只要有 API 凭证就提前连接（**不要求已登录**）：首次发码若现连 Telegram，
        # 经代理很容易超过同步接口的网关超时（表现为 502，而码其实已经发出）。
        if self._enabled() and self._credentials.api_configured():
            self._schedule_connect()

    def _schedule_connect(self, delay_seconds: int = 5) -> None:
        """让宿主调度器在稍后建立 TG 连接。"""
        add_once = getattr(scheduler_sdk, "add_plugin_once_job", None) if scheduler_sdk else None
        if add_once is None:
            logger.info("[TgMediaCenter] 调度接口不可用，TG 连接改为首次调用时建立")
            return
        try:
            add_once(
                self.__class__.__name__,
                "telegram_connect",
                self._ensure_telegram_runtime,
                "胖虎媒体中心 TG 客户端连接",
                delay_seconds=delay_seconds,
            )
        except Exception as err:  # pragma: no cover - 调度失败不影响其余能力
            logger.warning(f"[TgMediaCenter] 安排 TG 连接任务失败：{err}")

    def ensure_background_connect(self) -> None:
        """在后台安排一次 TG 连接（去抖：30 秒内只调度一次）。

        用于"会话已保存但客户端未连接"的自愈：打开配置页或点刷新状态即触发，
        不阻塞接口返回。连接在后台线程完成，下次刷新状态即可看到已登录。
        """
        now = time.time()
        requested_at = float(getattr(self, "_connect_requested_at", 0.0) or 0.0)
        if now - requested_at < 30:
            return
        self._connect_requested_at = now
        self._schedule_connect(delay_seconds=1)

    def _ensure_telegram_runtime(self) -> None:
        """一次性任务入口：建立运行时并连接。

        后台执行没有网关超时限制，可以给更宽松的预算。
        """
        credentials = self._credentials
        if credentials is None:
            return
        try:
            credentials.ensure_runtime(connect_timeout=45)
        except Exception as err:
            logger.info(f"[TgMediaCenter] TG 客户端预连接失败（后续调用会按需重试）：{err}")

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled()

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明插件使用 Vue 联邦远程组件渲染。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下不返回 Vuetify 表单结构，只提供默认配置模型。"""
        return None, TgMediaCenter.default_config()

    @staticmethod
    def default_config() -> Dict[str, Any]:
        """返回插件默认配置。"""
        return {
            "enabled": False,
            # ① TG 核心凭证
            "tg_api_id": "",
            "tg_api_hash": "",
            "tg_phone": "",
            # 仅用于从旧版本迁移；实际会话串保存在插件数据中（配置会被整份覆盖）
            "tg_session_string": "",
            "tg_user_cooldown_seconds": 5,
            "tg_keep_alive_seconds": 60,
            "tg_aggregation_window_seconds": 3.0,
            # ② 115 网盘
            "pan115_enabled": False,
            "pan115_cookie": "",
            "pan115_target_cid": "",
            "pan115_batch_max_size": 20,
            # ③ 已废弃：自定义豆瓣源（原 P3）已取消，配置项一并移除（1.8.1）
            # ④ TG 资源监控
            "monitor_enabled": False,
            "monitor_rules": [],
            # ⑤ 历史消息缓存
            "cache_enabled": False,
            "cache_chat_ids": [],
            "cache_destination": "smart",
            "cache_sync_mode": "relative",
            "cache_sync_days": 30,
            "cache_batch_size": 200,
            "cache_subscribe_enabled": True,
            # ⑥ TG 通用转发
            "forward_enabled": False,
            "forward_rules": [],
            # 定时任务
            "cache_cron": "0 */6 * * *",
            "cache_subscribe_cron": "*/30 * * * *",
            # 通知
            "notify_on_hit": True,
            "notify_on_error": True,
            "notify_on_search": True,
            # ⑧ 消息交互：私聊机器人发链接直接转存 115 并回执
            "interactive_push": True,
            # 私聊转存查重：转存成功过的链接（台账）不再重复转存（1.7.5）
            "interactive_dedup": True,
            # ⑨ 发现页入口（1.8.0）：开启后在 MP 左侧「发现」分区注册一个整页入口，
            # 页面即本插件的运行详情 / 仪表盘；默认关，避免给不用的人凭空多一项导航
            "discovery_page_enabled": False,
            # ⑩ P9 重复获取治理（1.9.0；反向 R0 开关 1.9.1 真机验证无收益后移除——
            # 暂停 new_subscribe_search 后新增订阅照旧被搜索，首次搜索是事件驱动）
            # 前向闸门 A：缺失确认之后再加一层「PT 路是否在管」判定；默认关 = 完全维持现状
            "p9_forward_gate_enabled": False,
            # 成熟期 T（小时）：PT 完全没记录时，等多久才让 TG 补（RSS 间隔 20min 下 2h 已足够）
            "p9_maturity_hours": 2,
            # 下载器活跃性细化：用下载历史里的 hash 查种子，区分「在途」与「死种」
            "p9_check_downloader": True,
            # 一次性执行
            "onlyonce": False,
        }

    def get_page(self) -> Optional[List[dict]]:
        """详情页由 Vue 远程组件渲染。"""
        return None

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """MP 左侧「发现」分区的整页入口（1.8.0）。

        页面由前端 ``AppPage`` 远程组件渲染，内容就是本插件的运行详情 / 仪表盘。
        默认关闭：只有插件已启用、且用户打开配置页顶部的「发现页」开关时才注册，
        避免给不用的人凭空多一个导航项。
        """
        if not self._enabled() or not self._config.get("discovery_page_enabled"):
            return []
        return [
            {
                "nav_key": "main",
                "title": self.plugin_name,
                "icon": "mdi-send-circle-outline",
                "section": "discovery",
                "permission": "discovery",
                "order": 21,
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由声明。"""
        return api_controller.get_api(self)

    # ------------------------------------------------------------------ API 端点

    def api_status(self):
        """返回插件与 TG 凭证运行状态。"""
        return api_controller.api_status(self)

    def api_overview(self):
        """返回详情页 / 仪表盘聚合状态。"""
        return api_controller.api_overview(self)

    def api_telegram_send_code(self, request: api_schemas.TgSendCodeRequest):
        """发送 TG 登录验证码。"""
        return api_controller.api_telegram_send_code(self, request)

    def api_telegram_sign_in(self, request: api_schemas.TgSignInRequest):
        """完成 TG 登录或两步验证。"""
        return api_controller.api_telegram_sign_in(self, request)

    def api_telegram_logout(self):
        """退出 TG 登录。"""
        return api_controller.api_telegram_logout(self)

    def api_telegram_dialogs(self):
        """返回缓存的对话列表。"""
        return api_controller.api_telegram_dialogs(self)

    def api_telegram_connect(self):
        """连接 / 重连 TG 客户端。"""
        return api_controller.api_telegram_connect(self)

    # ------------------------------------------------------------------ ② 115 网盘

    def api_pan115_status(self):
        """返回 115 模块状态。"""
        return api_controller.api_pan115_status(self)

    def api_pan115_check(self):
        """测试 115 连接并读取账号与配额。"""
        return api_controller.api_pan115_check(self)

    def api_pan115_logout(self):
        """清除 115 Cookie 与状态。"""
        return api_controller.api_pan115_logout(self)

    def api_pan115_verify_dir(self, request: api_schemas.Pan115VerifyDirRequest):
        """校验 115 目标目录 CID。"""
        return api_controller.api_pan115_verify_dir(self, request)

    def api_pan115_push(self, request: api_schemas.Pan115PushRequest):
        """批量推送链接到 115。"""
        return api_controller.api_pan115_push(self, request)

    def api_pan115_qr_start(self, request: api_schemas.Pan115QrStartRequest):
        """获取 115 扫码登录二维码。"""
        return api_controller.api_pan115_qr_start(self, request)

    def api_pan115_qr_poll(self):
        """查询 115 扫码登录状态。"""
        return api_controller.api_pan115_qr_poll(self)

    def api_pan115_qr_cancel(self):
        """取消 115 扫码登录。"""
        return api_controller.api_pan115_qr_cancel(self)

    def api_telegram_refresh_dialogs(self):
        """刷新并返回对话列表。"""
        return api_controller.api_telegram_refresh_dialogs(self)

    # ------------------------------------------------------------------ ④ TG 资源监控

    def api_monitor_rules(self):
        """读取监控规则。"""
        return api_controller.api_monitor_rules(self)

    def api_monitor_rules_save(self, request: api_schemas.MonitorRulesSaveRequest):
        """保存监控规则。"""
        return api_controller.api_monitor_rules_save(self, request)

    def api_monitor_hits(self, page: int = 1, page_size: int = 20, decision: str = "",
                         keyword: str = ""):
        """分页查询命中流水。"""
        return api_controller.api_monitor_hits(self, page=page, page_size=page_size,
                                               decision=decision, keyword=keyword)

    def api_monitor_hits_clear(self, request: api_schemas.MonitorHitsClearRequest):
        """清理监控命中流水（清空或按筛选删除）。"""
        return api_controller.api_monitor_hits_clear(self, request)

    def api_monitor_status(self):
        """监控运行状态。"""
        return api_controller.api_monitor_status(self)

    def api_monitor_test(self, request: api_schemas.MonitorTestRequest):
        """用一段文本测试规则处理结果。"""
        return api_controller.api_monitor_test(self, request)

    # ------------------------------------------------------------------ ⑤ 历史消息缓存

    def api_cache_settings(self):
        """读取消息缓存设置。"""
        return api_controller.api_cache_settings(self)

    def api_cache_settings_save(self, request: api_schemas.CacheSettingsRequest):
        """保存消息缓存设置。"""
        return api_controller.api_cache_settings_save(self, request)

    def api_cache_status(self):
        """缓存状态与统计。"""
        return api_controller.api_cache_status(self)

    def api_cache_sync(self, request: api_schemas.CacheSyncRequest):
        """触发缓存同步。"""
        return api_controller.api_cache_sync(self, request)

    def api_cache_cancel(self):
        """停止正在进行的缓存同步。"""
        return api_controller.api_cache_cancel(self)

    def api_cache_clear(self, request: api_schemas.CacheClearRequest):
        """清空指定频道的缓存。"""
        return api_controller.api_cache_clear(self, request)

    def api_cache_search(self, request: api_schemas.CacheSearchRequest):
        """检索缓存消息。"""
        return api_controller.api_cache_search(self, request)

    def api_cache_check_subscriptions(self):
        """立即检查新增订阅并回搜缓存。"""
        return api_controller.api_cache_check_subscriptions(self)

    # ------------------------------------------------------------------ ⑥ TG 通用转发

    def api_forward_rules(self):
        """读取通用转发规则。"""
        return api_controller.api_forward_rules(self)

    def api_forward_rules_save(self, request: api_schemas.ForwardRulesSaveRequest):
        """保存通用转发规则。"""
        return api_controller.api_forward_rules_save(self, request)

    def api_forward_status(self):
        """转发运行状态。"""
        return api_controller.api_forward_status(self)

    def api_forward_hits(self, page: int = 1, page_size: int = 20, decision: str = "",
                         keyword: str = ""):
        """分页查询转发流水。"""
        return api_controller.api_forward_hits(self, page=page, page_size=page_size,
                                               decision=decision, keyword=keyword)

    def api_forward_hits_clear(self, request: api_schemas.MonitorHitsClearRequest):
        """清理转发命中流水（清空或按筛选删除）。"""
        return api_controller.api_forward_hits_clear(self, request)

    def api_forward_test(self, request: api_schemas.ForwardTestRequest):
        """用一段文本测试转发规则。"""
        return api_controller.api_forward_test(self, request)

    # ------------------------------------------------------------------ ⑩ P9 重复获取治理

    def api_p9_guard(self):
        """宿主能力探针（只读）。"""
        return api_controller.api_p9_guard(self)

    # ------------------------------------------------------------------ 宿主事件

    def on_subscribe_added(self, event) -> None:
        """宿主「新增订阅」广播事件：交给缓存模块做防抖精准回搜。

        处理器**必须定义在插件主类上**：宿主事件分发只通过插件实例解析器
        （``plugin_id = owner_class.__name__``）绑定运行实例；定义在普通类
        （如 CacheModule）上的绑定方法会被判定「未绑定显式 resolver」静默跳过，
        这也是 1.4.3 事件没生效的原因。
        """
        cache = getattr(self, "_cache", None)
        if cache is None:
            return
        try:
            cache.on_subscribe_event(event)
        except Exception as err:  # pragma: no cover - 事件回调不能抛回宿主
            logger.warning(f"[TgMediaCenter] 处理订阅事件失败：{err}")

    def on_user_message(self, event) -> None:
        """宿主「收到用户外来消息」广播事件：消息里有链接就转存 115 并回执。

        与 ``on_subscribe_added`` 同理，处理器**必须定义在插件主类上**，否则宿主
        事件分发会静默跳过（详见该方法注释）。
        """
        interactive = getattr(self, "_interactive", None)
        if interactive is None:
            return
        try:
            interactive.handle(event)
        except Exception as err:  # pragma: no cover - 事件回调不能抛回宿主
            logger.warning(f"[TgMediaCenter] 处理用户消息失败：{err}")

    def _install_user_message_listener(self) -> bool:
        """注册宿主用户消息事件监听（宿主无该事件时静默降级）。"""
        try:
            from app.sdk.events import eventmanager
            from app.schemas.types import EventType
        except Exception as err:  # pragma: no cover - 宿主未提供事件总线
            logger.debug(f"[TgMediaCenter] 宿主事件总线不可用，消息转存不启用：{err}")
            return False
        # 事件名随宿主版本演进：拿不到就当不支持，不能用异常类兜
        event_type = getattr(EventType, "UserMessage", None)
        if event_type is None:  # pragma: no cover - 旧宿主无此事件
            logger.debug("[TgMediaCenter] 宿主未提供 UserMessage 事件，消息转存不启用")
            return False
        try:
            eventmanager.add_event_listener(event_type, self.on_user_message)
        except Exception as err:  # pragma: no cover
            logger.warning(f"[TgMediaCenter] 注册用户消息监听失败：{err}")
            return False
        self._user_message_eventmanager = eventmanager
        self._user_message_event_type = event_type
        return True

    def _uninstall_user_message_listener(self) -> None:
        """移除宿主用户消息事件监听。"""
        manager = getattr(self, "_user_message_eventmanager", None)
        event_type = getattr(self, "_user_message_event_type", None)
        self._user_message_eventmanager = None
        self._user_message_event_type = None
        if manager is not None and event_type is not None:
            try:
                manager.remove_event_listener(event_type, self.on_user_message)
            except Exception as err:  # pragma: no cover
                logger.debug(f"[TgMediaCenter] 移除用户消息监听失败：{err}")

    def _install_subscribe_listener(self) -> bool:
        """注册宿主新增订阅事件监听（旧宿主无事件总线时静默降级为仅定时）。"""
        try:
            from app.sdk.events import eventmanager
            from app.schemas.types import EventType
        except Exception as err:  # pragma: no cover - 宿主未提供事件总线
            logger.debug(f"[TgMediaCenter] 宿主事件总线不可用，订阅回搜仅按定时执行：{err}")
            return False
        try:
            eventmanager.add_event_listener(EventType.SubscribeAdded, self.on_subscribe_added)
        except Exception as err:  # pragma: no cover
            logger.warning(f"[TgMediaCenter] 注册订阅事件监听失败：{err}")
            return False
        self._subscribe_eventmanager = eventmanager
        self._subscribe_event_type = EventType.SubscribeAdded
        cache = getattr(self, "_cache", None)
        if cache is not None:
            cache.mark_event_listener(True)
        return True

    def _uninstall_subscribe_listener(self) -> None:
        """移除宿主订阅事件监听并取消待执行的防抖回搜。"""
        manager = getattr(self, "_subscribe_eventmanager", None)
        event_type = getattr(self, "_subscribe_event_type", None)
        self._subscribe_eventmanager = None
        self._subscribe_event_type = None
        if manager is not None and event_type is not None:
            try:
                manager.remove_event_listener(event_type, self.on_subscribe_added)
            except Exception as err:  # pragma: no cover
                logger.debug(f"[TgMediaCenter] 移除订阅事件监听失败：{err}")
        cache = getattr(self, "_cache", None)
        if cache is not None:
            cache.cancel_event_timer()
            cache.mark_event_listener(False)

    # ------------------------------------------------------------------ 其它扩展点

    def get_database_models(self) -> Optional[List[type]]:
        """返回插件自有数据模型（P4 起：命中流水 + 推送任务）。"""
        try:
            return get_models()
        except Exception as err:  # pragma: no cover - 模型导入失败不应拖垮插件加载
            logger.warning(f"[TgMediaCenter] 加载插件数据模型失败：{err}")
            return None

    def get_service(self) -> List[Dict[str, Any]]:
        """返回插件定时服务定义。

        监控流水线自带 worker 线程（聚合窗口 + 推送队列扫描），不需要宿主定时任务；
        这里注册两个缓存相关周期任务：
        - 缓存增量同步（``cache_cron``，默认每 6 小时）：按位点补齐断线窗口漏掉的消息；
        - 订阅回搜兜底检查（``cache_subscribe_cron``，默认每 30 分钟）：对比订阅快照，
          新增订阅自动回搜缓存并推送。实时路径是宿主「新增订阅」事件
          （``on_subscribe_added``），定时检查只兜底——插件离线期间新增的订阅事件
          不会补发，且事件总线不可用时要还能发现新增。

        :note: ``trigger`` 必须是 ``CronTrigger`` 对象；本方法整体兜底，
            任何异常都只记录日志并降级为空列表（注册异常会拖垮 TG 自愈）。
        """
        services: List[Dict[str, Any]] = []
        cache = self._cache
        if cache is None:
            return services
        try:
            from apscheduler.triggers.cron import CronTrigger
        except Exception as err:  # pragma: no cover - 宿主缺调度依赖
            logger.info(f"[TgMediaCenter] 调度依赖不可用，缓存定时任务降级：{err}")
            return services
        try:
            if not (self._enabled() and cache.enabled()):
                return services
            if cache.chat_ids():
                cron = cache.cron()
                services.append({
                    "func": cache.run_scheduled_sync,
                    "trigger": CronTrigger.from_crontab(cron),
                    "name": "胖虎媒体中心 缓存增量同步",
                    "id": "tgmediacenter_cache_sync",
                })
            if cache.subscribe_enabled():
                cron = cache.subscribe_cron()
                services.append({
                    "func": cache.run_subscription_job,
                    "trigger": CronTrigger.from_crontab(cron),
                    "name": "胖虎媒体中心 订阅回搜",
                    "id": "tgmediacenter_cache_subscribe",
                })
        except Exception as err:  # pragma: no cover - 定时任务注册失败不影响插件加载
            logger.warning(f"[TgMediaCenter] 注册缓存定时任务失败：{err}")
            return []
        return services

    def stop_service(self) -> None:
        """释放插件创建的后台资源。"""
        monitor, self._monitor = self._monitor, None
        if monitor is not None:
            try:
                monitor.stop()
            except Exception as err:  # pragma: no cover
                logger.warning(f"[TgMediaCenter] 停止资源监控流水线失败：{err}")
        # 转发模块无自有线程（复用监控流水线），仅清引用，必须在流水线停止之后
        self._forward = None
        # 先摘事件监听（其中会取消防抖回搜），再释放缓存模块
        self._uninstall_subscribe_listener()
        self._uninstall_user_message_listener()
        self._interactive = None
        cache = getattr(self, "_cache", None)
        self._cache = None
        if cache is not None:
            try:
                cache.cancel_sync()
            except Exception as err:  # pragma: no cover
                logger.warning(f"[TgMediaCenter] 停止缓存同步失败：{err}")
        credentials, self._credentials = self._credentials, None
        if credentials is not None:
            try:
                credentials.stop()
            except Exception as err:  # pragma: no cover
                logger.warning(f"[TgMediaCenter] 停止 TG 运行时失败：{err}")
        # 115 模块为无状态 HTTP 客户端，无需释放连接，仅清引用
        self._pan115 = None
        # 冷却门只是内存状态（间隔 + FloodWait 截止时刻），清引用即可
        self._gate = None

    def _cooldown_seconds(self) -> int:
        """TG 个人号全局冷却间隔（秒），配置非法时回落 5 秒。"""
        try:
            value = int((self._config or {}).get("tg_user_cooldown_seconds", 5) or 5)
        except (TypeError, ValueError):
            value = 5
        return max(0, value)
