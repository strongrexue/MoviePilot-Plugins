"""极简：只保留背景与居中的大标题。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PIL import Image, ImageDraw


def get_schema() -> Dict[str, Any]:
    """布局专属参数。"""
    return {
        "fields": [
            {"key": "scrim_opacity", "label": "中央压暗浓度", "type": "number", "default": 120},
            {"key": "subtitle_gap", "label": "副标题间距", "type": "number", "default": 28},
            {"key": "text_color", "label": "文字颜色", "type": "color", "default": "#ffffff"},
        ]
    }


def render(engine, bg: Image.Image, config: Dict[str, Any], assets: Dict[str, Any],
           fonts: Dict[str, Any], step: Optional[float] = None) -> Image.Image:
    """渲染极简封面。"""
    canvas = bg.convert("RGBA").copy()
    width, height = canvas.size
    opacity = int(config.get("scrim_opacity") or 0)
    if opacity > 0:
        scrim = Image.new("RGBA", (width, height), (0, 0, 0, opacity))
        canvas = Image.alpha_composite(canvas, scrim)

    draw = ImageDraw.Draw(canvas, "RGBA")
    text_color = config.get("text_color") or "#ffffff"
    center_x = width / 2
    title = config.get("title") or ""
    subtitle = config.get("subtitle")

    # 居中：先用主字体量一次高度，保证标题垂直居中。
    main_font = fonts["main"]
    try:
        bbox = main_font.getbbox(title or " ")
    except Exception:
        bbox = (0, 0, 1, int(height * 0.1))
    line_height = max(1, bbox[3] - bbox[1])
    total = line_height + (int(config.get("subtitle_gap") or 28) + line_height // 2 if subtitle else 0)
    title_y = int((height - total) / 2)

    next_y = engine.draw_text_wrapper(
        draw, title, center_x, title_y, main_font, int(width * 0.86), text_color, align="center",
    )
    if subtitle:
        engine.draw_text_wrapper(
            draw, subtitle, center_x, next_y + int(config.get("subtitle_gap") or 28),
            fonts["sub"], int(width * 0.8), text_color, align="center",
        )
    return canvas
