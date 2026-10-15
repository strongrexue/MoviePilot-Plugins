"""海报墙：等宽网格铺满海报，底部压一条标题条。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PIL import Image, ImageDraw


def get_schema() -> Dict[str, Any]:
    """布局专属参数。"""
    return {
        "fields": [
            {"key": "columns", "label": "列数", "type": "number", "default": 3},
            {"key": "poster_gap", "label": "海报间距", "type": "number", "default": 20},
            {"key": "poster_radius", "label": "海报圆角", "type": "number", "default": 14},
            {"key": "wall_margin", "label": "四周边距", "type": "number", "default": 60},
            {"key": "title_bar_opacity", "label": "标题条浓度", "type": "number", "default": 190},
            {"key": "text_color", "label": "文字颜色", "type": "color", "default": "#ffffff"},
        ]
    }


def render(engine, bg: Image.Image, config: Dict[str, Any], assets: Dict[str, Any],
           fonts: Dict[str, Any], step: Optional[float] = None) -> Image.Image:
    """渲染海报墙封面。"""
    canvas = bg.convert("RGBA").copy()
    width, height = canvas.size
    margin = int(config.get("wall_margin") or 60)
    gap = int(config.get("poster_gap") or 20)
    radius = int(config.get("poster_radius") or 14)
    columns = max(1, int(config.get("columns") or 3))

    posters = list(assets.get("posters") or [])
    bar_height = int(height * 0.22)
    area_height = height - bar_height - margin
    cell_width = int((width - margin * 2 - gap * (columns - 1)) / columns)
    cell_height = int(area_height * 0.5) if len(posters) > columns else area_height

    offset = 0
    if step and len(posters) > columns:
        offset = int(step * (cell_width + gap))

    index = 0
    for row in range(max(1, (len(posters) + columns - 1) // columns)):
        for column in range(columns):
            if index >= len(posters):
                break
            left = margin + column * (cell_width + gap)
            top = margin + row * (cell_height + gap)
            band = (left - offset, top, left + cell_width - offset, top + cell_height)
            engine.paste_cover(canvas, posters[index], band, radius=radius)
            index += 1

    bar_top = height - bar_height
    bar = Image.new("RGBA", (width, bar_height), (0, 0, 0, int(config.get("title_bar_opacity") or 190)))
    canvas.paste(bar, (0, bar_top), bar)

    draw = ImageDraw.Draw(canvas, "RGBA")
    text_color = config.get("text_color") or "#ffffff"
    title_y = bar_top + int(bar_height * 0.22)
    title_y = engine.draw_text_wrapper(
        draw, config.get("title") or "", margin, title_y, fonts["main"],
        width - margin * 2, text_color, align="left",
    )
    if config.get("subtitle"):
        engine.draw_text_wrapper(
            draw, config["subtitle"], margin, title_y + int(bar_height * 0.08), fonts["sub"],
            width - margin * 2, text_color, align="left",
        )
    return canvas
