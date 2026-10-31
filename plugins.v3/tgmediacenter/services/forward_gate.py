"""下载历史查询（洗版规则的「下载历史(PT)」基线来源）。

1.13.34 起 P9 前向闸门整体退役，本模块只保留「按标题/身份查宿主下载历史」这一
组只读能力，供 ``modules/cache.py`` 的洗版基线比对使用。

纪律（沿用原 P9 规格 §8/§9）：
- **一律 fail-open 且留痕**：sdk 是宿主能力，MP 升级可能失配；取不到历史只会让
  洗版少一道参考，绝不能因此拦截推送。
- **禁止全量拉取**：按标题过滤查询，分页上限只防异常宿主。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger

# 下载历史单次查询页大小与翻页上限（身份过滤后不会多；上限只防异常宿主）
_HISTORY_PAGE_SIZE = 50
_HISTORY_MAX_PAGES = 4

# ---------------------------------------------------------------------------
# 依赖探测（无宿主环境降级，不抛异常）
try:  # 宿主只读查询：下载历史
    from app.sdk.queries import list_download_history

    HISTORY_QUERIES_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境
    list_download_history = None  # type: ignore[assignment]
    HISTORY_QUERIES_AVAILABLE = False

_WARNED_MISSING: set = set()


def _warn_once(message: str) -> None:
    if message in _WARNED_MISSING:
        return
    _WARNED_MISSING.add(message)
    logger.warning(message)


def _snapshot_to_dict(item: Any) -> Dict[str, Any]:
    """把宿主的历史快照（pydantic 模型或 dict）转成普通字典。"""
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        try:
            return dict(item.model_dump())
        except Exception:  # pragma: no cover - 老版本 pydantic
            pass
    if hasattr(item, "dict"):
        try:
            return dict(item.dict())
        except Exception:  # pragma: no cover
            pass
    data: Dict[str, Any] = {}
    for name in getattr(item, "__dict__", {}) or {}:
        data[name] = getattr(item, name, None)
    return data


def list_history_records(filters: Dict[str, Any]) -> "Optional[List[Dict[str, Any]]]":
    """按过滤器分页拉取下载历史；``None`` = 查询失败（调用方按无记录处理）。"""
    if not HISTORY_QUERIES_AVAILABLE or list_download_history is None:
        return None
    try:
        collected: List[Dict[str, Any]] = []
        for page_num in range(1, _HISTORY_MAX_PAGES + 1):
            try:
                page = list_download_history(
                    filters, {"page": page_num, "count": _HISTORY_PAGE_SIZE}
                )
            except TypeError:
                # 测试桩或老签名不支持分页参数
                page = list_download_history(filters)
            items = list(getattr(page, "items", None) or [])
            collected.extend(_snapshot_to_dict(item) for item in items)
            if len(items) < _HISTORY_PAGE_SIZE:
                break
        return collected
    except Exception as err:
        _warn_once(f"[tgmediacenter] 下载历史查询失败（洗版仅用已推送基线）：{err}")
        return None


__all__: Tuple[str, ...] = (
    "HISTORY_QUERIES_AVAILABLE",
    "list_history_records",
)
