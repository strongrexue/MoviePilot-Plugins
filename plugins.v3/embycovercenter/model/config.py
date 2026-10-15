"""EmbyCoverCenter 配置常量与默认值。

`default_config()` 是配置的唯一事实来源：`__init__.py` 的 `get_form()`/`init_plugin()`
与前端 `src/components/Config.vue` 的表单字段都必须与它保持一致。
"""
from __future__ import annotations

from typing import Any, Dict

# 自动封面任务默认 cron（每天 04:00）。
DEFAULT_COVER_CRON = "0 4 * * *"


def default_config() -> Dict[str, Any]:
    """返回插件默认配置。"""
    return {
        # 总开关
        "enabled": False,
        # 是否在 MP 左侧「发现」分区注册整页入口
        "discovery_page_enabled": False,
        # 参与封面的媒体服务器名称；空 = 全部已启用服务器
        "selected_servers": [],
        # 封面系统
        "auto_refresh_on_webhook": True,
        "cover_cron": DEFAULT_COVER_CRON,
        # 通知（走宿主通知渠道）
        "notify_on_task_finish": True,
    }
