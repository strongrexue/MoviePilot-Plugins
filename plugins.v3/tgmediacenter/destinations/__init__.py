"""推送目标工厂。"""
from __future__ import annotations

from typing import Any, Optional

from .base import Destination, DestinationError
from .none import NoneDestination
from .pan115 import Pan115Destination
from .tg_forward import TgForwardDestination

# 前端选项与后端保持一致
DESTINATION_OPTIONS = [
    {"value": "smart", "title": "智能（115 可用则转存，否则仅记录）"},
    {"value": "pan115", "title": "115 网盘（分享转存 / 磁力 eD2k 离线）"},
    {"value": "tg_forward", "title": "TG 转发（转发原消息到目标会话）"},
    {"value": "none", "title": "仅记录（不推送）"},
]
DESTINATION_VALUES = tuple(item["value"] for item in DESTINATION_OPTIONS)


def resolve_destination(name: str, plugin: Any, gate: Any = None) -> Destination:
    """把规则里的 destination 解析为具体目标。

    ``smart``：115 已启用且已登录 → 115；否则仅记录。
    """
    key = str(name or "").strip().lower() or "smart"
    if key == "none":
        return NoneDestination()
    if key == "pan115":
        return Pan115Destination(plugin)
    if key == "tg_forward":
        return TgForwardDestination(plugin, gate)
    if key == "smart":
        pan115 = Pan115Destination(plugin)
        if pan115.available():
            return pan115
        return NoneDestination()
    raise DestinationError(f"未知推送目标：{name}")


def describe_destination(name: str) -> str:
    """目标取值的中文说明（用于状态与流水展示）。"""
    for item in DESTINATION_OPTIONS:
        if item["value"] == str(name or "").strip().lower():
            return item["title"]
    return str(name or "")
