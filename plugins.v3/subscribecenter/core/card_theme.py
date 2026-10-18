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


def _rules(selector: str, color: str) -> list:
    """方案 3（安全版）：加粗描边 + 左侧强调条 + 卡片底色。

    .. important::
       这里**不用** ``::after`` 覆盖层 —— 覆盖层会盖在卡片内容之上，
       一旦被宿主自身的伪元素规则干扰，就可能出现「整张卡看不见」的错觉。
       只用 box-shadow 画描边 + 背景色，绝不遮挡任何内容。
    """
    return [
        f"{selector}{{",
        f"  box-shadow:inset 0 0 0 3px {color}, inset 7px 0 0 0 {color} !important;",
        f"  background-color:{_rgba(color, 0.12)} !important;",
        "}",
    ]


def build_block(colors: Dict[str, str]) -> str:
    """生成标记块（含首尾标记行）。

    方案 3：整卡描边 + 左侧强调条 + 底色，最醒目；
    洗版仍由宿主自带的左上角徽章表达（不额外配色，避免和状态色打架）。
    """
    lines = [
        BLOCK_BEGIN,
        "/* 方案 3：3px 描边 + 左侧 7px 强调条 + 卡片底色（不覆盖内容） */",
    ]
    lines += _rules(".subscribe-card", colors["subscribing"])
    lines += _rules(".subscribe-card.subscribe-card-pending-tint", colors["pending"])
    lines += _rules(".subscribe-card.subscribe-card-paused", colors["paused"])
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


def merge_css(existing: Optional[str], colors: Dict[str, str]) -> str:
    """把标记块合并进用户已有的自定义 CSS。"""
    base = strip_block(existing).rstrip()
    block = build_block(colors).rstrip()
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
    "DEFAULT_COLORS",
    "build_block",
    "merge_css",
    "normalize_colors",
    "split",
    "strip_block",
]
