"""EmbyCoverCenter 配置常量与默认值。

`default_config()` 是配置的唯一事实来源：`__init__.py` 的 `get_form()`/`init_plugin()`
与前端 `src/components/Config.vue` 的表单字段都必须与它保持一致。
"""
from __future__ import annotations

from typing import Any, Dict

# 自动封面任务默认 cron（每天 04:00）。
DEFAULT_COVER_CRON = "0 4 * * *"
# 默认布局（与内置布局模块名一致）。
DEFAULT_COVER_LAYOUT = "经典平铺"


def default_config() -> Dict[str, Any]:
    """返回插件默认配置。"""
    return {
        # 总开关
        "enabled": False,
        # 是否在 MP 左侧「发现」分区注册整页入口
        "discovery_page_enabled": False,
        # 参与封面的媒体服务器名称；空 = 全部已启用服务器
        "selected_servers": [],
        # 封面：默认布局与布局参数（cover_config 由前端按布局 schema 填充）
        "cover_layout": DEFAULT_COVER_LAYOUT,
        "cover_config": {},
        "assets_mode": "random",
        "poster_count": 6,
        "backdrop_count": 1,
        # 各媒体库手填的英文名（副标题覆盖值）：{ 媒体库ID: 英文名 }
        "library_en_names": {},
        # 自动封面任务：开关 / 目标媒体库（{ 服务器名: [库ID,...] }）/ 封面方案
        # （模板预设文件名；空串 = 跟随封面设计）；执行频率沿用 cover_cron
        "auto_cover_enabled": False,
        "auto_cover_libraries": {},
        "auto_cover_template": "",
        # 封面系统
        "auto_refresh_on_webhook": True,
        "cover_cron": DEFAULT_COVER_CRON,
        # 通知（走宿主通知渠道）
        "notify_on_task_finish": True,
    }
