"""订阅卡片配色：把状态颜色写进宿主的自定义 CSS。

宿主会在启动时把 ``UserCustomCSS`` 注入成 ``<style>``（前端
``default-*.js`` 里 ``document.head.appendChild``），所以插件只要把
生成的样式写进这个设置，MoviePilot 的订阅卡片就会跟着变色。

.. important::
   宿主这个设置是**用户自己的**，可能已经写了别的内容 —— 必须用标记块
   包裹我们这段，写入时只替换标记块内部，标记外一个字都不动。
"""
import re
from typing import Any, Dict, Optional, Tuple

#: 标记块：只替换这两行之间的内容，避免覆盖用户自己的自定义 CSS
BLOCK_BEGIN = "/* SUBSCRIBECENTER:CARD-THEME:BEGIN —— 由胖虎订阅中心生成，请勿手改 */"
BLOCK_END = "/* SUBSCRIBECENTER:CARD-THEME:END */"

#: 状态色默认值（订阅中 / 待定 / 暂停）
DEFAULT_COLORS: Dict[str, str] = {
    "subscribing": "#FFC107",
    "pending": "#F97316",
    "paused": "#9CA3AF",
}

#: 洗版外框颜色（可选的额外标记，默认不开启）
BEST_VERSION_COLOR = "#A855F7"

#: 合法的 #RRGGBB
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_colors(value: Any) -> Dict[str, str]:
    """把外部传入的颜色归一化；非法值回退到默认（不抛错）。"""
    colors = dict(DEFAULT_COLORS)
    if isinstance(value, dict):
        for key in DEFAULT_COLORS:
            candidate = str(value.get(key) or "").strip()
            if _HEX.match(candidate):
                colors[key] = candidate.upper()
    return colors


def _rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB -> rgba(r,g,b,a)，用于整卡浅染色。"""
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha:.2f})"


def _rules(selector: str, color: str, color_alpha: float = 0.12) -> list:
    """方案 3：整卡浅染色 + 2px 描边 + 左侧 5px 强调条。"""
    return [
        f"{selector}{{",
        f"  box-shadow:inset 0 0 0 2px {color}, inset 5px 0 0 0 {color} !important;",
        f"  background-color:{_rgba(color, 0.10)} !important;",
        "}",
        f"{selector}::after{{",
        '  content:"";',
        "  position:absolute;",
        "  inset:0;",
        "  border-radius:inherit;",
        "  pointer-events:none;",
        "  z-index:3;",
        f"  background:{_rgba(color, color_alpha)} !important;",
        "}",
    ]


def build_block(colors: Dict[str, str], best_version_outline: bool = False) -> str:
    """生成标记块（含首尾标记行）。

    方案 3：整卡按状态浅染色 + 2px 描边，最醒目；洗版仍用宿主自带的
    左上角徽章表达（可选再加紫色外框）。
    """
    lines = [
        BLOCK_BEGIN,
        "/* 方案 3：整卡浅染色 + 2px 描边；洗版用宿主自带左上角徽章 */",
        ".subscribe-card{",
        "  position:relative !important;",
        "}",
    ]
    lines += _rules(".subscribe-card", colors["subscribing"])
    lines += _rules(".subscribe-card.subscribe-card-pending-tint", colors["pending"], 0.14)
    lines += _rules(".subscribe-card.subscribe-card-paused", colors["paused"], 0.10)
    if best_version_outline:
        lines += [
            ".subscribe-card:has(.best-version-badge){",
            f"  outline:2px solid {BEST_VERSION_COLOR} !important;",
            "  outline-offset:-2px;",
            "}",
        ]
    lines.append(BLOCK_END)
    return chr(10).join(lines) + chr(10)


def strip_block(css: Optional[str]) -> str:
    """删除我们写入的标记块（保留其它内容）。"""
    text = css or ""
    start = text.find(BLOCK_BEGIN)
    if start < 0:
        return text
    end = text.find(BLOCK_END, start)
    if end < 0:
        # 只有开头没有结尾（被人手改坏了）—— 把标记行删掉即可
        return text.replace(BLOCK_BEGIN, "")
    end += len(BLOCK_END)
    # 顺带吃掉块尾的一个换行，避免留下空行
    if text[end:end + 1] == chr(10):
        end += 1
    return text[:start] + text[end:]


def merge_css(existing: Optional[str], colors: Dict[str, str], best_version_outline: bool) -> str:
    """把标记块合并进用户已有的自定义 CSS。"""
    base = strip_block(existing).rstrip()
    block = build_block(colors, best_version_outline).rstrip()
    if not base:
        return block + chr(10)
    return base + chr(10) + chr(10) + block + chr(10)


def split(existing: Optional[str]) -> Tuple[str, str]:
    """返回（用户自己的部分，我们的标记块）——给接口回读用。"""
    text = existing or ""
    start = text.find(BLOCK_BEGIN)
    if start < 0:
        return text, ""
    end = text.find(BLOCK_END, start)
    if end < 0:
        return text, ""
    return text[:start] + text[end + len(BLOCK_END):], text[start:end + len(BLOCK_END)]


__all__ = [
    "BLOCK_BEGIN",
    "BLOCK_END",
    "BEST_VERSION_COLOR",
    "DEFAULT_COLORS",
    "build_block",
    "merge_css",
    "normalize_colors",
    "split",
    "strip_block",
]
