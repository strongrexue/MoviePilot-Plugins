"""TG媒体中心 - MoviePilot V3 插件（TgMediaCenter）。

当前进度：P2 —— 115 网盘推送目标。
- 已实现：① TG 核心凭证（Telethon 运行时、登录向导、会话持久化、对话列表缓存）；
  ② 115 网盘（Cookie 登录态、空间配额、分享转存、磁力/eD2k 离线、分批推送）。
- 待实现：自定义豆瓣源、TG 资源监控、历史消息缓存、TG 通用转发。
"""
from typing import Any, Dict, List, Optional, Tuple
import time

from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .controller import api as api_controller
from .controller import schemas as api_schemas
from .modules.credentials import CredentialsModule
from .modules.pan115 import Pan115Module
from .modules.subscribe import SubscribeModule

try:  # 一次性任务调度接口；缺失时降级为懒连接
    from app.sdk import scheduler as scheduler_sdk
except Exception:  # pragma: no cover
    scheduler_sdk = None  # type: ignore[assignment]


class TgMediaCenter(_PluginBase):
    """TG媒体中心插件入口。"""

    plugin_name = "TG媒体中心"
    plugin_desc = "Telegram 资源监控、历史消息缓存、115 网盘转存、自定义豆瓣源订阅与 TG 通用转发。"
    plugin_icon = "tgmediacenter.png"
    plugin_color = "#229ED9"
    plugin_version = "1.3.2"
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
        self._subscribe: Optional[SubscribeModule] = None

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

        self._credentials = CredentialsModule(self)
        self._pan115 = Pan115Module(self)
        self._subscribe = SubscribeModule(self)
        # 旧版本把 TG 会话串存在配置里；配置会被「保存配置」整份覆盖，需迁到插件数据
        self._credentials.migrate_session_from_config()

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
                "TG媒体中心 TG 客户端连接",
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
            # ③ 订阅服务（MP 榜单走 MP API / 豆瓣榜单走 RSSHub）
            "subscribe_enabled": False,
            "subscribe_rsshub_base": "https://rsshub.app",
            "subscribe_sources": [],
            # ④ TG 资源监控
            "monitor_enabled": False,
            "monitor_rules": [],
            # ⑤ 历史消息缓存
            "cache_enabled": False,
            "cache_chat_ids": [],
            "cache_destination": "smart",
            # ⑥ TG 通用转发
            "forward_enabled": False,
            "forward_rules": [],
            # 定时任务
            "douban_cron": "0 13 * * *",
            "cache_cron": "0 */6 * * *",
            "subscribe_cron": "0 */6 * * *",
            # 通知
            "notify_on_hit": True,
            "notify_on_error": True,
            # 一次性执行
            "onlyonce": False,
        }

    def get_page(self) -> Optional[List[dict]]:
        """详情页由 Vue 远程组件渲染。"""
        return None

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由声明。"""
        return api_controller.get_api(self)

    # ------------------------------------------------------------------ API 端点

    def api_status(self):
        """返回插件与 TG 凭证运行状态。"""
        return api_controller.api_status(self)

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

    # ------------------------------------------------------------------ ③ 订阅服务

    def api_subscribe_sources(self):
        """获取订阅源常量表（MP / 豆瓣双通道）。"""
        return api_controller.api_subscribe_sources(self)

    def api_subscribe_status(self):
        """获取订阅服务状态。"""
        return api_controller.api_subscribe_status(self)

    def api_subscribe_sync(self, request: api_schemas.SubscribeSyncRequest):
        """立即同步订阅源。"""
        return api_controller.api_subscribe_sync(self, request)

    # ------------------------------------------------------------------ 其它扩展点

    def get_database_models(self) -> Optional[List[type]]:
        """返回插件自有数据模型（订阅去重表）。"""
        from .model.subscribe_seen import SubscribeSeen

        return [SubscribeSeen]

    def get_service(self) -> List[Dict[str, Any]]:
        """返回插件定时服务定义（订阅服务周期同步）。"""
        if not self._enabled() or not self._subscribe or not self._subscribe.enabled():
            return []
        return [
            {
                "id": "subscribe_sync",
                "name": "订阅服务同步",
                "trigger": self._config.get("subscribe_cron") or "0 */6 * * *",
                "func": self._run_subscribe_sync,
                "kwargs": {},
            }
        ]

    def _run_subscribe_sync(self) -> None:
        """定时服务入口：同步订阅源（后台执行，无网关超时限制）。"""
        subscribe = self._subscribe
        if subscribe is None:
            return
        try:
            subscribe.sync()
        except Exception as err:  # pragma: no cover
            logger.warning(f"[TgMediaCenter] 订阅服务同步失败：{err}")

    def stop_service(self) -> None:
        """释放插件创建的后台资源。"""
        credentials, self._credentials = self._credentials, None
        if credentials is not None:
            try:
                credentials.stop()
            except Exception as err:  # pragma: no cover
                logger.warning(f"[TgMediaCenter] 停止 TG 运行时失败：{err}")
        # 115 模块为无状态 HTTP 客户端，无需释放连接，仅清引用
        self._pan115 = None
        self._subscribe = None
