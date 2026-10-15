"""胖虎封面中心 - MoviePilot V3 插件（EmbyCoverCenter）。

当前进度：M1 骨架 —— 生命周期、配置读写、四个渲染入口（配置 / 详情 / 仪表盘 /
侧栏整页）与插件 API 注册（`/ping`、`/status`）已打通；封面系统与 Emby 任务中心
在后续里程碑落到 `service/` 内。

设计依据见仓库文档；开发与发版规则见本插件 README「开发与发版」。
"""
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .controller import api as api_controller
from .controller import schemas as api_schemas
from .model.config import default_config
from .service import assets_meta, mediaserver
from .service.render_engine import PosterEngine


class EmbyCoverCenter(_PluginBase):
    """Emby 媒体库封面生成 + Emby 任务中心。"""

    plugin_name = "胖虎封面中心"
    plugin_desc = "Emby 媒体库封面生成、封面任务与 Emby 计划任务中心，通知走 MoviePilot 通知渠道。"
    plugin_icon = "https://raw.githubusercontent.com/strongrexue/MoviePilot-Plugins/main/icons/embycovercenter.png"
    plugin_color = "#52B54B"
    plugin_version = "1.4.4"
    plugin_author = "strongrexue"
    author_url = "https://github.com/strongrexue"
    plugin_config_prefix = "embycovercenter_"
    plugin_order = 20
    auth_level = 1

    def __init__(self, *args, **kwargs) -> None:
        """建立当前插件实例独享的配置快照。"""
        super().__init__(*args, **kwargs)
        self._config: Dict[str, Any] = {}
        self._cover_engine = None

    # ------------------------------------------------------------------ 配置快照

    @property
    def config(self) -> Dict[str, Any]:
        """返回当前生效配置。"""
        return self._config

    @property
    def selected_servers(self) -> List[str]:
        """返回用户选择参与封面的媒体服务器名称列表。"""
        return list(self._config.get("selected_servers") or [])

    @staticmethod
    def default_config() -> Dict[str, Any]:
        """返回插件默认配置（前端表单字段与之一致）。"""
        return default_config()

    # ------------------------------------------------------------------ 生命周期

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """读取配置并建立运行状态；必须允许重复调用。"""
        self.stop_service()
        raw = dict(config or {})
        merged = default_config()
        merged.update(raw)
        self._config = merged
        # 首次安装（无配置）或存在历史遗留字段时，回写规范化后的配置；
        # 内容一致则不写，避免每次加载都触发一次配置写入。
        if raw != merged:
            self.update_config(merged)
        # 资源子目录（字体 / 模板 / 布局）只建目录，不写回插件源码目录；
        # 默认模板预设首次初始化时从插件包拷入数据目录（只补缺失）。
        assets_meta.ensure_dirs(self)
        copied = assets_meta.seed_default_templates(self)
        if copied:
            logger.info(f"[EmbyCoverCenter] 已补全默认模板 {copied} 个文件")
        fonts = assets_meta.seed_default_fonts(self)
        if fonts:
            logger.info(f"[EmbyCoverCenter] 已补全默认字体 {fonts} 个文件")

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return bool(self._config.get("enabled"))

    def stop_service(self) -> None:
        """释放后台资源（引擎线程池与图片缓存）。"""
        engine = getattr(self, "_cover_engine", None)
        if engine is not None:
            try:
                engine.close()
            except Exception as error:  # pragma: no cover - 释放失败不阻塞卸载
                logger.warning(f"[EmbyCoverCenter] 释放渲染引擎失败: {error}")
            self._cover_engine = None

    # ------------------------------------------------------------------ 宿主扩展点

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """当前不注册远程命令。"""
        return []

    @staticmethod
    def get_agent_tools() -> List[type]:
        """当前不注册 Agent 工具。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """注册插件动态 API。"""
        return api_controller.get_api(self)

    def get_service(self) -> List[Dict[str, Any]]:
        """M1 暂不注册定时服务；封面任务在 M4 接入。"""
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦远程组件渲染。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下不返回 Vuetify 表单，只提供默认配置模型。"""
        return None, default_config()

    def get_page(self) -> Optional[List[dict]]:
        """Vue 模式下详情页由远程组件渲染。"""
        return None

    def get_dashboard(self, key: str, **kwargs: Any):
        """返回仪表盘列配置与展示属性（Vue 模式下页面元素为 None）。"""
        return (
            {"cols": 12, "md": 6},
            {"refresh": 300, "border": True, "title": self.plugin_name, "subtitle": "封面与 Emby 任务概览"},
            None,
        )

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """声明一个仪表盘卡片。"""
        return [{"key": "dashboard1", "name": self.plugin_name}]

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """按配置注册「发现」分区的整页入口。"""
        if not self.get_state() or not self._config.get("discovery_page_enabled"):
            return []
        return [
            {
                "nav_key": "main",
                "title": self.plugin_name,
                "icon": "mdi-image-multiple-outline",
                "section": "discovery",
                "permission": "discovery",
                "order": 20,
            }
        ]

    # ------------------------------------------------------------------ API 转发

    def api_ping(self):
        """连通性探针。"""
        return api_controller.api_ping(self)

    def api_status(self):
        """返回插件与媒体服务器状态。"""
        return api_controller.api_status(self)

    def api_emby_tasks(self, server: str = ""):
        """返回 Emby 计划任务列表。"""
        return api_controller.api_emby_tasks(self, server=server)

    def api_emby_task_detail(self, task_id: str, server: str = ""):
        """返回 Emby 单个计划任务与触发器。"""
        return api_controller.api_emby_task_detail(self, task_id=task_id, server=server)

    def api_emby_task_triggers_save(self, task_id: str, request: api_schemas.EmbyTriggerSaveRequest):
        """保存 Emby 计划任务触发器。"""
        return api_controller.api_emby_task_triggers_save(self, task_id=task_id, request=request)

    def api_emby_task_run(self, task_id: str, server: str = ""):
        """立即运行 Emby 计划任务。"""
        return api_controller.api_emby_task_run(self, task_id=task_id, server=server)

    def api_emby_task_stop(self, task_id: str, server: str = ""):
        """停止 Emby 计划任务。"""
        return api_controller.api_emby_task_stop(self, task_id=task_id, server=server)

    def list_servers(self) -> List[Dict[str, Any]]:
        """返回已启用媒体服务器摘要（复用宿主 MediaServerHelper）。"""
        return mediaserver.list_servers()

    def cover_engine(self) -> PosterEngine:
        """返回封面渲染引擎；**同一实例复用**，避免每次预览都重新加载布局与清空图片缓存。"""
        engine = getattr(self, "_cover_engine", None)
        if engine is None:
            engine = PosterEngine(self)
            self._cover_engine = engine
        return engine

    # ------------------------------------------------------------------ 封面 API 转发

    def api_libraries(self, server: str = ""):
        """获取媒体库列表。"""
        return api_controller.api_libraries(self, server=server)

    def api_layouts(self):
        """获取封面布局与参数字段。"""
        return api_controller.api_layouts(self)

    def api_fonts(self):
        """获取可用字体。"""
        return api_controller.api_fonts(self)

    def api_font_upload(self, request: api_schemas.FontUploadRequest):
        """上传字体（base64）。"""
        return api_controller.api_font_upload(self, request=request)

    def api_font_delete(self, request: api_schemas.NameRequest):
        """删除字体。"""
        return api_controller.api_font_delete(self, request=request)

    def api_templates(self):
        """获取模板预设。"""
        return api_controller.api_templates(self)

    def api_template_save(self, request: api_schemas.TemplateSaveRequest):
        """保存模板预设。"""
        return api_controller.api_template_save(self, request=request)

    def api_template_delete(self, request: api_schemas.NameRequest):
        """删除模板预设。"""
        return api_controller.api_template_delete(self, request=request)

    def api_template_upload(self, request: api_schemas.TemplateUploadRequest):
        """上传模板文件（base64）。"""
        return api_controller.api_template_upload(self, request=request)

    def api_preview(self, request: api_schemas.CoverPreviewRequest):
        """生成封面预览。"""
        return api_controller.api_preview(self, request=request)

    def api_apply(self, request: api_schemas.CoverApplyRequest):
        """应用封面到媒体库。"""
        return api_controller.api_apply(self, request=request)

    def api_asset_font(self, name: str):
        """原生返回字体文件。"""
        return api_controller.api_asset_font(self, name=name)

    def api_asset_template_preview(self, filename: str):
        """原生返回模板预览图。"""
        return api_controller.api_asset_template_preview(self, filename=filename)
