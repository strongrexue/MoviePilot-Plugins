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
    """某一天有哪些剧在播（复刻 MoviePilot 日历的数据口径）。

    .. important::
       **只看 TMDB 每季的 ``episodes[].air_date``**，不用订阅表的
       ``last_update`` / ``date``：

       - ``last_update`` 是「最后一次搜索/刷新时间」，批量跑一次会把几十上百条
         订阅全部刷成同一天 → 用它判断会把整月撑爆（真机实测一天 200 条，MP 只有 38 条）
       - ``date`` 只是「下一集播出」，查历史/未来都覆盖不到

       入库状态按**集号 vs 已入库集数**（``total_episode - lack_episode``）判断，
       与 MP 前端 ``libraryState`` 口径一致。
    """
    rows = list(rows)
    index = episode_index or {}
    items: List[Dict[str, Any]] = []

    for row in rows:
        media_id = _text(getattr(row, "media_id", ""))
        season = _int(getattr(row, "season", 0))
        air_eps = [number for air_date, number in index.get((media_id, season), []) if air_date == today]
        if not air_eps:
            continue

        downloaded = _int(getattr(row, "total_episode", 0)) - _int(
            getattr(row, "lack_episode", 0)
        )
        done = downloaded > 0 and max(air_eps) <= downloaded
        item = _row_to_item(row, KIND_UPDATED if done else KIND_PENDING, today)
        item["episodes"] = sorted(air_eps)
        items.append(item)

    items.sort(key=lambda item: (item["kind"] != KIND_UPDATED, item["name"]))
    return items


def summarize(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计今日日历的关键计数（给摘要条用）。"""
    updated = [item for item in items if item["kind"] == KIND_UPDATED]
    return {
        "total": len(items),
        "updated": len(updated),
        "pending": len(items) - len(updated),
        "best_version": len([item for item in items if item["best_version"]]),
    }


def month_bounds(month: str) -> List[str]:
    """返回该月所有日期（YYYY-MM-DD）；month 形如 2026-10。"""
    import calendar as _calendar
    from datetime import date as _date

    year_text, month_text = month.split("-")
    year, mon = int(year_text), int(month_text)
    days = _calendar.monthrange(year, mon)[1]
    return [_date(year, mon, day).isoformat() for day in range(1, days + 1)]


def build_month(
    rows: Iterable[Any],
    month: str,
    episode_index: Optional[Dict[Any, List[Any]]] = None,
) -> Dict[str, Any]:
    """整月日历：{日期: [条目]}，只有有内容的天才出现在结果里。"""
    rows = list(rows)
    days: Dict[str, List[Dict[str, Any]]] = {}
    for day in month_bounds(month):
        items = build_today(rows, day, episode_index)
        if items:
            days[day] = items
    # 不截断：以前截到 20 条会让「+N」永远显示 +15，和 MP 的真实折叠数对不上。
    # 一个月几百条对 JSON 来说没问题（实测 <1MB）。
    from datetime import date as _date

    return {
        "month": month,
        # 服务器本地「今天」：前端用它高亮，避免用浏览器 UTC 日期算偏一天
        "today": _date.today().isoformat(),
        "days": days,
        "total": sum(len(items) for items in days.values()),
        "per_day_limit": 5,
    }
