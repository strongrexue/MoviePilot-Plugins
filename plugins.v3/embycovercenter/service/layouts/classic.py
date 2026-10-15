"""经典平铺：右上标题 + 底部海报横排（动态模式下海报缓慢横移）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PIL import Image, ImageDraw


def get_schema() -> Dict[str, Any]:
    """布局专属参数。"""
    return {
        "fields": [
            {"key": "title_margin", "label": "左右边距", "type": "number", "default": 90},
            {"key": "subtitle_gap", "label": "副标题间距", "type": "number", "default": 24},
            {"key": "poster_gap", "label": "海报间距", "type": "number", "default": 24},
            {"key": "poster_radius", "label": "海报圆角", "type": "number", "default": 16},
            {"key": "poster_height_ratio", "label": "海报区高度占比", "type": "number", "default": 0.42, "step": 0.02},
            {"key": "overlay_opacity", "label": "底部遮罩浓度", "type": "number", "default": 200},
            {"key": "text_color", "label": "文字颜色", "type": "color", "default": "#ffffff"},
        ]
    }


def _draw_bottom_overlay(canvas: Image.Image, start: int, opacity: int) -> Image.Image:
    width, height = canvas.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    span = max(1, height - start)
    for y in range(start, height):
        alpha = int(opacity * ((y - start) / span))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(canvas.convert("RGBA"), overlay)


def render(engine, bg: Image.Image, config: Dict[str, Any], assets: Dict[str, Any],
           fonts: Dict[str, Any], step: Optional[float] = None) -> Image.Image:
    """渲染经典平铺封面。"""
    canvas = bg.convert("RGBA").copy()
    width, height = canvas.size
    margin = int(config.get("title_margin") or 90)
    text_color = config.get("text_color") or "#ffffff"
    draw = ImageDraw.Draw(canvas, "RGBA")

    title_y = int(height * 0.16)
    title_y = engine.draw_text_wrapper(
        draw, config.get("title") or "", margin, title_y, fonts["main"],
        width - margin * 2, text_color, align="left",
    )
    subtitle = config.get("subtitle")
    if subtitle:
        gap = int(config.get("subtitle_gap") or 24)
        engine.draw_text_wrapper(
            draw, subtitle, margin, title_y + gap, fonts["sub"],
            width - margin * 2, text_color, align="left",
        )

    posters = list(assets.get("posters") or [])
    if not posters:
        return canvas

    ratio = float(config.get("poster_height_ratio") or 0.42)
    area_height = int(height * ratio)
    area_top = height - area_height - int(height * 0.06)
    start_overlay = area_top - int(height * 0.12)
    canvas = _draw_bottom_overlay(canvas, max(0, start_overlay), int(config.get("overlay_opacity") or 200))

    gap = int(config.get("poster_gap") or 24)
    radius = int(config.get("poster_radius") or 16)
    count = len(posters)
    cell_width = int((width - margin * 2 - gap * (count - 1)) / count)
    poster_width = int(cell_width * 0.74)
    poster_height = int(poster_width * 1.5)
    if poster_height > area_height:
        poster_height = area_height
        poster_width = int(poster_height / 1.5)

    shift = int(step * cell_width * 0.6) if step else 0
    x = margin - shift
    top = area_top + (area_height - poster_height) // 2
    for url in posters:
        engine.paste_cover(canvas, url, (x, top, x + poster_width, top + poster_height), radius=radius)
        x += cell_width + gap
    return canvas
