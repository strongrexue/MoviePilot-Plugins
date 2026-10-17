"""日期窗口与时区归一的回归测试（开发文档 §6.5）。"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core import window as W  # noqa: E402

# --------------------------------------------------------------------- 解析

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-10-20", date(2026, 10, 20)),
        ("2026/10/20", date(2026, 10, 20)),
        ("2026.10.20", date(2026, 10, 20)),
        ("2026-10", date(2026, 10, 1)),      # 只有年月 → 取当月 1 日（下界口径）
        ("2026", date(2026, 1, 1)),          # 只有年 → 取 1 月 1 日
        ("  2026-10-20  ", date(2026, 10, 20)),
        (date(2026, 10, 20), date(2026, 10, 20)),
        (datetime(2026, 10, 20, 12, 0), date(2026, 10, 20)),
    ],
)
def test_parse_date_supported_forms(raw, expected):
    """各种来源日期表示都能解析。"""
    assert W.parse_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "not-a-date", "abc", "--", "2026-13-45"])
def test_parse_date_rejects_bad_input(raw):
    """非法/空输入返回 ``None`` 而不是抛异常（不打断流水线）。"""
    assert W.parse_date(raw) is None


def test_parse_date_normalizes_aware_datetime_to_target_tz():
    """带时区的 datetime 需先转目标时区再取日期。

    UTC 2026-10-20 23:30 在 Asia/Shanghai（UTC+8）已是 10-21。
    """
    aware = datetime(2026, 10, 20, 23, 30, tzinfo=ZoneInfo("UTC"))
    assert W.parse_date(aware, "Asia/Shanghai") == date(2026, 10, 21)
    assert W.parse_date(aware, "UTC") == date(2026, 10, 20)


def test_to_iso_shape():
    """输出统一为 ``YYYY-MM-DD``。"""
    assert W.to_iso("2026-10-20T00:00:00") == "2026-10-20"
    assert W.to_iso(None) is None


# --------------------------------------------------------------------- 时区

def test_get_tz_falls_back_to_default_on_bad_name():
    """非法时区名回落到默认时区，不抛异常。"""
    assert W.get_tz("Not/AZone") == ZoneInfo("Asia/Shanghai")
    assert W.get_tz("") == ZoneInfo("Asia/Shanghai")
    assert W.get_tz(None) == ZoneInfo("Asia/Shanghai")


def test_get_tz_accepts_valid_name():
    """合法时区名直接使用。"""
    assert W.get_tz("UTC") == ZoneInfo("UTC")


# --------------------------------------------------------------------- 窗口

def test_in_window_inclusive_bounds():
    """窗口是闭区间：今天与「今天+N 天」都算在窗口内。"""
    base = date(2026, 10, 20)
    assert W.in_window(base, 30, now=base)
    assert W.in_window(base + timedelta(days=30), 30, now=base)
    assert not W.in_window(base + timedelta(days=31), 30, now=base)


def test_in_window_rejects_past_and_missing():
    """过去日期与无日期都必须被拒（宁缺毋滥）。"""
    base = date(2026, 10, 20)
    assert not W.in_window(base - timedelta(days=1), 30, now=base)
    assert not W.in_window(None, 30, now=base)


def test_in_window_allow_today_false_excludes_today():
    """严格未来口径下，今天也算窗口外。"""
    base = date(2026, 10, 20)
    assert not W.in_window(base, 30, now=base, allow_today=False)
    assert W.in_window(base + timedelta(days=1), 30, now=base, allow_today=False)


def test_window_end_handles_bad_future_days():
    """``future_days`` 非法时按 1 天处理，避免出现空窗口。"""
    base = date(2026, 10, 20)
    assert W.window_end(0, now=base) == base + timedelta(days=1)
    assert W.window_end(-5, now=base) == base + timedelta(days=1)
    assert W.window_end("x", now=base) == base + timedelta(days=1)


# --------------------------------------------------------------------- 排序表达式

@pytest.mark.parametrize(
    "media_type,expected",
    [
        ("movie", "primary_release_date.asc"),
        ("tv", "first_air_date.asc"),
        ("TV", "first_air_date.asc"),
        ("series", "first_air_date.asc"),
    ],
)
def test_release_sort_ascending(media_type, expected):
    """TMDB 窗口没有上界，必须靠日期升序 + 本地过滤。"""
    assert W.release_sort_ascending(media_type) == expected


def test_local_now_text_shape():
    """本地时间文本形如 ``YYYY-MM-DD HH:MM:SS``。"""
    text = W.local_now_text("Asia/Shanghai")
    assert len(text) == 19 and text[4] == "-" and text[10] == " "


def test_utc_now_text_shape():
    """UTC 时间文本以 Z 结尾。"""
    assert W.utc_now_text().endswith("Z")
