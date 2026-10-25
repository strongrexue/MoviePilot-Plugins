"""日期窗口与时区归一（纯逻辑，无宿主依赖）。

开发文档 §6.5：所有日期统一转为 ``Asia/Shanghai`` 后再比较。

设计要点：对外只暴露「日期字符串」（``YYYY-MM-DD``），不返回 ``date`` 对象，
避免调用方把日期当成带时刻的时间戳用。
"""
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .constants import DEFAULT_TIMEZONE

#: 允许识别的日期前缀长度：``2026-10-20`` / ``2026-10`` / ``2026``
_DATE_PATTERN = re.compile(r"^\s*(\d{4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?")


def get_tz(name: Optional[str] = None) -> ZoneInfo:
    """返回时区对象；名称非法时回落到 ``Asia/Shanghai``。

    回落到默认时区而不是 UTC，是因为本插件服务的是中文媒体定档口径，
    回落到 UTC 会让「今天」在凌晨时段错位一天。
    """
    candidate = (name or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def today(tz_name: Optional[str] = None) -> date:
    """返回指定时区下的「今天」。"""
    return datetime.now(get_tz(tz_name)).date()


def parse_date(value: object, tz_name: Optional[str] = None) -> Optional[date]:
    """把来源给出的各种日期表示解析为日期。

    支持：
    - ``date`` / ``datetime`` 实例（``datetime`` 按其自身时区转目标时区后取日期）
    - ``"2026-10-20"``、``"2026/10/20"``、``"2026.10.20"``
    - ``"2026-10"``（按当月 1 日）、``"2026"``（按当年 1 月 1 日）
    - 空串 / ``None`` / 无法识别 → ``None``

    .. note::
       不猜「只有年份时按年中」之类的语义；取 1 月 1 日是**下界**口径，
       保证不会把条目误判为「已经过了窗口」。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(get_tz(tz_name)).date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    match = _DATE_PATTERN.match(text)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    try:
        return date(year, month, day)
    except ValueError:
        # 例如 2026-02-30：非法日期直接判为无法识别，不抛异常打断整条流水线
        return None


def to_iso(value: object, tz_name: Optional[str] = None) -> Optional[str]:
    """把来源日期归一为 ``YYYY-MM-DD`` 字符串；无法识别返回 ``None``。"""
    parsed = parse_date(value, tz_name)
    return parsed.isoformat() if parsed else None


def window_end(
    future_days: int,
    *,
    tz_name: Optional[str] = None,
    now: Optional[date] = None,
) -> date:
    """返回发现窗口的结束日期（含当天）。

    ``future_days`` 非法（非正数）时按 1 天处理，避免出现空窗口。
    """
    base = now or today(tz_name)
    days = future_days if isinstance(future_days, int) and future_days > 0 else 1
    return base + timedelta(days=days)


def in_window(
    release: Optional[date],
    future_days: int,
    *,
    tz_name: Optional[str] = None,
    now: Optional[date] = None,
    allow_today: bool = True,
    past_days: int = 0,
) -> bool:
    """判断定档日期是否落在「今天-N ~ 今天+N 天」窗口内。

    - ``release`` 为 ``None`` → ``False``（无定档日期无法判断，宁缺毋滥）
    - 已过去的日期（早于今天）→ ``False``，除非给了 ``past_days``
    - ``allow_today=False`` 时，今天也算窗口外（用于「严格未来」口径）

    ``past_days`` 是「刚上映也算数」的宽限天数，**只给电影用**：数字版上线
    之后站点上才有资源，卡死「必须在未来」等于永远订不到刚上线的片子
    （真机：豆瓣榜单里《空枪》数字发行 2026-10-23，当天被「已过去」拒掉）。
    宽限期一过照样拒绝，所以榜单里的老片不会被误订。
    """
    if release is None:
        return False
    base = now or today(tz_name)
    grace = past_days if isinstance(past_days, int) and past_days > 0 else 0
    if release < base - timedelta(days=grace):
        return False
    if release == base and not allow_today:
        return False
    return release <= window_end(future_days, tz_name=tz_name, now=base)


def release_sort_ascending(sort_field: str) -> str:
    """返回 TMDB ``discover`` 的日期升序排序表达式。

    宿主 ``tmdb_discover`` 对电影拼 ``release_date.gte``、对剧集拼
    ``first_air_date.gte``，**都没有上界**（开发文档 §5.1）。因此必须靠
    「按日期升序」把窗口内最近的条目排到前面，再由本地窗口过滤截断。

    :param sort_field: ``"movie"`` 或 ``"tv"``
    """
    if str(sort_field).strip().casefold() in {"tv", "series", "show"}:
        return "first_air_date.asc"
    return "primary_release_date.asc"


def local_now_text(tz_name: Optional[str] = None) -> str:
    """返回 ``YYYY-MM-DD HH:MM:SS`` 形式的本地时间文本（落流水用）。"""
    return datetime.now(get_tz(tz_name)).strftime("%Y-%m-%d %H:%M:%S")


def utc_now_text() -> str:
    """返回 UTC ISO 时间文本（用于 ``discovered_at`` 之类与展示无关的字段）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "get_tz",
    "in_window",
    "local_now_text",
    "parse_date",
    "release_sort_ascending",
    "to_iso",
    "today",
    "utc_now_text",
    "window_end",
]
