"""媒体服务器发现（薄门面）。

统一转发到 ``emby_gateway``，避免两处实现同一份服务器枚举逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import emby_gateway


def list_servers() -> List[Dict[str, Any]]:
    """返回已启用媒体服务器摘要（名称 / 类型 / 是否连接）。"""
    return emby_gateway.list_servers()
