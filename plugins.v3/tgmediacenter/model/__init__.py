"""插件自有数据模型包（P4 资源监控起启用）。

模型通过主类 ``get_database_models()`` 声明给宿主，启动时自动建表；
PostgreSQL 下每插件独立 schema，天然按实例隔离。
"""
from __future__ import annotations

from typing import List

from .hit_log import TgHitLog
from .message_cache import TgMessageCache
from .push_task import TgPushTask

# 汇总模型列表：主类 get_database_models() 直接返回
MODELS: List[type] = [TgHitLog, TgMessageCache, TgPushTask]


def get_models() -> List[type]:
    """返回插件自有模型列表（避免调用方直接改 MODULES 常量）。"""
    return list(MODELS)
