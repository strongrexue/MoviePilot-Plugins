"""TG媒体中心 - MoviePilot V3 插件（TgMediaCenter）.

骨架版本：仅建立生命周期、Vue 联邦渲染声明与 API/模型钩子，
业务模块按设计文档的 P1~P7 阶段逐步填充。
"""
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.plugin import _PluginBase


class TgMediaCenter(_PluginBase):
    """TG媒体中心插件入口。"""

    plugin_name = "TG媒体中心"
    plugin_desc = "Telegram 资源监控、历史消息缓存、115 网盘转存、自定义豆瓣源订阅与 TG 通用转发。"
    plugin_icon = "tgmediacenter.png"
    plugin_color = "#229ED9"
    plugin_version = "1.0.0"
    plugin_author = "strongrexue"
    author_url = "https://github.com/strongrexue"
    plugin_config_prefix = "tgmediacenter_"
    plugin_order = 20
    auth_level = 1

    def __init__(self, *args, **kwargs) -> None:
        """建立当前插件实例独享的运行状态。"""
        super().__init__(*args, **kwargs)
        self._enabled = False

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """读取配置并建立本次运行所需状态；必须允许重复调用。"""
        self.stop_service()
        config = config or {}
        self._enabled = bool(config.get("enabled"))

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明插件使用 Vue 联邦远程组件渲染。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下不返回 Vuetify 表单结构，只提供默认配置模型。"""
        return None, self.default_config()

    @staticmethod
    def default_config() -> Dict[str, Any]:
        """返回插件默认配置。"""
        return {
            "enabled": False,
            # ① TG 核心凭证
            "tg_api_id": "",
            "tg_api_hash": "",
            "tg_phone": "",
            "tg_session_string": "",
            "tg_user_cooldown_seconds": 5,
            "tg_keep_alive_seconds": 60,
            "tg_aggregation_window_seconds": 3.0,
            # ② 115 网盘
            "pan115_enabled": False,
            "pan115_cookie": "",
            "pan115_target_cid": "",
            "pan115_batch_max_size": 20,
            # ③ 自定义豆瓣源
            "douban_enabled": False,
            "douban_rsshub_base": "http://127.0.0.1:1200",
            "douban_cookie": "",
            "douban_wish_rss_urls": [],
            "douban_rules": [],
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
        """返回插件 API 路由声明（骨架阶段为空）。"""
        return []

    def get_database_models(self) -> Optional[List[type]]:
        """返回插件自有数据模型（骨架阶段为空）。"""
        return None

    def get_service(self) -> List[Dict[str, Any]]:
        """返回插件定时服务定义（骨架阶段为空）。"""
        return []

    def stop_service(self) -> None:
        """释放插件创建的后台资源。"""
        self._enabled = False
