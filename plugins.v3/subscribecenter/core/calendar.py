"""今日日历：把订阅表里「今天有动作」的条目挑出来。

宿主的订阅表用两个字符串字段表达更新时间：

- ``last_update`` —— 最后一次**入库**的时间（有资源了）
- ``date`` —— 下一集的**播出**时间（还没入库时用它）

两者都是 ``"YYYY-MM-DD HH:MM:SS"`` 形式的字符串，所以这里按前缀比较日期，
不做时区换算（宿主写入时已按本地时区格式化）。

.. note::
   「已入库」优先于「待播」：同一部剧两边都命中时只算已入库，
   否则界面上会出现两条一样的卡片。

.. important::
   任意日期（历史/未来）不能只看订阅的两个时间字段 —— 那只有「最后一次入库」
   和「下一集播出」，查过去会全空。宿主自己的日历页做法是**按 TMDB 每季的
   ``episodes[].air_date`` 铺开**（前端 ``calendar-*.js`` 里调的
   ``tmdb/{id}/{season}``）。所以这里也支持传入「剧集播出索引」：
   ``{(media_id, season): [(air_date, episode_number), ...]}``。
"""
from typing import Any, Dict, Iterable, List, Optional

KIND_UPDATED = "updated"
KIND_PENDING = "pending"

#: 参与日历的订阅状态（N = 未开始，没有播出信息；完成态会移出订阅表）
ACTIVE_STATES = ("R", "P", "S")


def _text(value: Any) -> str:
    return str(value or "")


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _row_to_item(row: Any, kind: str, today: str) -> Dict[str, Any]:
    """把一行订阅转成日历条目（只保留前端要用的字段）。"""
    air = _text(getattr(row, "date", ""))
    return {
        "id": _int(getattr(row, "id", 0)),
        "name": _text(getattr(row, "name", "")),
        "season": _int(getattr(row, "season", 0)),
        "poster": _text(getattr(row, "poster", "")),
        "media_source": _text(getattr(row, "media_source", "")),
        "media_id": _text(getattr(row, "media_id", "")),
        "total_episode": _int(getattr(row, "total_episode", 0)),
        "lack_episode": _int(getattr(row, "lack_episode", 0)),
        "start_episode": _int(getattr(row, "start_episode", 1)),
        "state": _text(getattr(row, "state", "")),
        "best_version": bool(getattr(row, "best_version", 0)),
        "kind": kind,
        "episodes": [],
        "air_time": air[11:16] if len(air) >= 16 else "",
        "air_date": air[:10],
        "today": today,
    }


def build_today(
    rows: Iterable[Any],
    today: str,
    episode_index: Optional[Dict[Any, List[Any]]] = None,
) -> List[Dict[str, Any]]:
    """挑出某一天的日历条目：先「已入库」，再「待播」（去重）。

    :param rows: 订阅行（ORM 对象即可）
    :param today: 目标日期 ``YYYY-MM-DD``
    :param episode_index: 可选 ``{(media_id, season): [(air_date, episode_number), ...]}``，
        用来支持**任意日期**：命中当天播出的集数，即使订阅的 ``date``/``last_update``
        都没落在这一天。
    """
    rows = list(rows)
    index = episode_index or {}

    updated: List[Dict[str, Any]] = []
    updated_ids: set = set()
    for row in rows:
        if _text(getattr(row, "last_update", "")).startswith(today):
            item = _row_to_item(row, KIND_UPDATED, today)
            updated.append(item)
            updated_ids.add(item["id"])

    pending: List[Dict[str, Any]] = []
    for row in rows:
        sid = _int(getattr(row, "id", 0))
        if sid in updated_ids:
            continue
        key = (_text(getattr(row, "media_id", "")), _int(getattr(row, "season", 0)))
        air_eps = [
            number for air_date, number in index.get(key, []) if air_date == today
        ]
        hit = bool(air_eps) or _text(getattr(row, "date", "")).startswith(today)
        if not hit:
            continue
        item = _row_to_item(row, KIND_PENDING, today)
        if air_eps:
            item["episodes"] = sorted(air_eps)
        pending.append(item)

    updated.sort(key=lambda item: item["name"])
    pending.sort(key=lambda item: item["name"])
    return updated + pending


def summarize(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计今日日历的关键计数（给摘要条用）。"""
    updated = [item for item in items if item["kind"] == KIND_UPDATED]
    return {
        "total": len(items),
        "updated": len(updated),
        "pending": len(items) - len(updated),
        "best_version": len([item for item in items if item["best_version"]]),
    }
