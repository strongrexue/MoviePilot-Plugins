"""订阅卡片配色：CSS 合并必须保留用户自己的自定义 CSS。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugins.v3"))

from subscribecenter.core import card_theme as t  # noqa: E402


def test_normalize_colors_falls_back_on_invalid():
    colors = t.normalize_colors({"subscribing": "红色", "pending": "#00ff00", "paused": ""})
    assert colors["subscribing"] == t.DEFAULT_COLORS["subscribing"]
    assert colors["pending"] == "#00FF00"
    assert colors["paused"] == t.DEFAULT_COLORS["paused"]


def test_merge_keeps_user_css():
    user = "body{color:red}"
    merged = t.merge_css(user, t.normalize_colors({}))
    assert merged.startswith("body{color:red}")
    assert t.BLOCK_BEGIN in merged and t.BLOCK_END in merged


def test_merge_is_idempotent():
    colors = t.normalize_colors({"subscribing": "#FFC107"})
    once = t.merge_css("", colors)
    twice = t.merge_css(once, colors)
    assert twice.count(t.BLOCK_BEGIN) == 1, "重复保存不能叠加多个块"


def test_strip_removes_only_our_block():
    user = "body{color:red}"
    merged = t.merge_css(user, t.normalize_colors({}))
    stripped = t.strip_block(merged).rstrip()
    assert stripped == user
    assert t.BLOCK_BEGIN not in stripped


def test_paused_and_pending_selectors_present():
    css = t.build_block(t.normalize_colors({}))
    assert ".subscribe-card.subscribe-card-pending-tint" in css
    assert ".subscribe-card.subscribe-card-paused" in css
    assert "box-shadow:inset 0 0 0 3px" in css, "方案3：3px 描边"
    assert "inset 7px 0 0 0" in css, "左侧强调条"
    assert "::after" not in css, "不要覆盖层（会挡住内容）"
