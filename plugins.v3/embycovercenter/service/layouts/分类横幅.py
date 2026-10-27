"""分类横幅：一套「按元素独立定位」的媒体库封面版式。

参考图（六张分类横幅）的视觉语法是：**左画面 / 右文字 / 金属标题 / 光带 / 书法水印**。
这里不把「左右分区」写死成结构，而是把每个元素都做成独立图层：

- 标题给一个锚点（``title_x`` / ``title_y`` / ``title_align``），
  副标题 / 中文标语 / 英文标语默认 ``inherit`` 跟随标题的锚点与对齐；
- 光带、题材标签、书法水印、圆角边框各有自己的坐标；
- 压暗不再内建，改由「特效与装饰」的通用渐变遮罩（``mask_*``）提供，
  四个方向可选，颜色可调，和「极简」布局共用同一套语义。

默认值拼出来是参考图的居中版式；改任意一项只动那个元素，互不影响。

底图两种来源（``bg_source``）：
- ``library``：引擎给的媒体库背景图；
- ``keyart``：用户/AI 准备的成品主视觉（本地上传 / URL / 按库配置），
  都不会画人物——那是美术资产，插件只负责版式与压字。

``auto_mirror``（文案「素材镜像」）对两种来源都生效：**开启即水平翻转、关闭就用原图**，
不判断画面哪边更亮，默认关闭。

**不做统一调色**：底图什么样就什么样，「底图调整」三个开关（亮度 / 对比度 /
饱和度，默认 1.0 = 原样）显式开启才生效；「特效与装饰」里的渐变遮罩默认开启
（浓度 180 / 范围 66%），底部遮罩默认关闭。

分层顺序（自下而上）：
底图（+ 可选亮度/对比度/饱和度）→ 渐变遮罩（可选）→ 底部遮罩
→ 书法水印 → 标题（金属渐变）→ 光带 → 副标题 → 中文标语
→ 英文标语 → 题材标签 → 圆角边框。
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from PIL import (
    Image,
    ImageChops,
    ImageColor,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)

# 尺寸类参数（字号 / 圆角 / 线宽）都按 1080 高的画布校准，渲染时按实际高度等比缩放。
REFERENCE_HEIGHT = 1080


# ---------------------------------------------------------------- 基础工具


def _clamp(value, low, high, fallback):
    """把配置值夹到区间内；非法值（字符串 / None / NaN）用 fallback。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(fallback)
    if number != number:  # NaN
        number = float(fallback)
    return max(low, min(high, number))


def _rgb(value, fallback=(0, 0, 0)):
    try:
        return tuple(ImageColor.getrgb(str(value))[:3])
    except Exception:
        return tuple(fallback)


def _mix(color, other, ratio):
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(round(a * (1 - ratio) + b * ratio)) for a, b in zip(color, other))


def _vgradient(size, stops):
    """纵向渐变（stops: [(位置 0-1, RGB)]），先画 1px 竖条再拉伸。"""
    width, height = int(size[0]), int(size[1])
    strip = Image.new("RGB", (1, max(1, height)))
    draw = ImageDraw.Draw(strip)
    for y in range(max(1, height)):
        t = y / max(1, height - 1)
        color = stops[-1][1]
        for index in range(len(stops) - 1):
            p0, c0 = stops[index]
            p1, c1 = stops[index + 1]
            if p0 <= t <= p1:
                color = _mix(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        draw.point((0, y), fill=color)
    return strip.resize((max(1, width), max(1, height)), Image.BILINEAR)


def _glow_line(size, center, length, thickness, color, flare_color, strength):
    """标题下的灯带：横向「亮核 + 宽光晕」双高斯，纵向单高斯。

    参考图（哆啦A梦）的灯带不是「一条实线 + 一个高光点」的拼接，也不是单高斯：
    实测剖面是**中间一段很窄的近白亮核，外面裹一层宽得多的柔光**，
    单高斯无论怎么调都只能「要么太尖、要么太长」。所以这里用双高斯叠加：

        横向 >90% 半宽 ≈ 0.044 × 灯带长度（窄核）
        横向 >50% 半宽 ≈ 0.120 × 灯带长度
        横向 >25% 半宽 ≈ 0.213 × 灯带长度
        横向 >10% 半宽 ≈ 0.369 × 灯带长度（宽光晕）

    参数由 `.sim/embycovercenter/fit_glow.py` 对这四档实测值做最小二乘拟合得到。

    返回的图层是**预乘过的光**（RGB 已按强度缩放、alpha 铺满），调用方要用
    ``ImageChops.screen`` 叠上去——灯带是「发光」，压在亮底图上也该亮得起来。
    """
    width, height = int(size[0]), int(size[1])
    if strength <= 0 or length <= 1:
        return None
    span = float(length)
    sigma_core = max(0.6, span * 0.078)
    sigma_halo = max(sigma_core * 1.6, span * 0.228)
    weight_core = 0.64
    sigma_y = max(0.9, float(thickness) * 1.35)
    cx, cy = float(center[0]), float(center[1])
    x0 = max(0, int(cx - sigma_halo * 3.0))
    x1 = min(width, int(cx + sigma_halo * 3.0) + 1)
    y0 = max(0, int(cy - sigma_y * 3.5))
    y1 = min(height, int(cy + sigma_y * 3.5) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 255))
    pixels = layer.load()
    two_core = 2.0 * sigma_core * sigma_core
    two_halo = 2.0 * sigma_halo * sigma_halo
    two_sy = 2.0 * sigma_y * sigma_y
    for y in range(y0, y1):
        gy = math.exp(-((y - cy) ** 2) / two_sy)
        if gy <= 0.004:
            continue
        for x in range(x0, x1):
            dx2 = (x - cx) ** 2
            gx = weight_core * math.exp(-dx2 / two_core) + (1.0 - weight_core) * math.exp(-dx2 / two_halo)
            factor = strength * gx * gy / 255.0
            if factor <= 0.002:
                continue
            tint = _mix(color, flare_color, min(1.0, gx ** 1.2))
            pixels[x - x0, y - y0] = (
                int(tint[0] * factor), int(tint[1] * factor), int(tint[2] * factor), 255,
            )
    return x0, y0, layer


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=max(0, int(radius)), fill=255
    )
    return mask


# ---------------------------------------------------------------- 文字工具


def _tracked_width(text, text_font, tracking):
    if not text:
        return 0.0
    try:
        return sum(text_font.getlength(char) for char in text) + tracking * max(0, len(text) - 1)
    except Exception:
        return float(text_font.getbbox(text)[2])


def _align_x(anchor, width, align):
    """锚点换算成绘制起点：left=锚点，center=锚点-半宽，right=锚点-全宽。"""
    if align == "center":
        return anchor - width / 2.0
    if align == "right":
        return anchor - width
    return anchor


def _draw_tracked(draw, text, anchor_x, y, text_font, fill, tracking, align="left"):
    """逐字绘制（PIL 没有字距），按 align 相对 anchor_x 对齐。"""
    if not text:
        return
    x = _align_x(anchor_x, _tracked_width(text, text_font, tracking), align)
    for char in text:
        draw.text((x, y), char, font=text_font, fill=fill)
        x += text_font.getlength(char) + tracking


def _text_size(text_font):
    """字体行高（ascent + descent）；取不到时退回 bbox。"""
    try:
        ascent, descent = text_font.getmetrics()
        return ascent + descent
    except Exception:
        bbox = text_font.getbbox("Hg")
        return max(1, bbox[3] - bbox[1])


class _FontBook:
    """按 (字体文件名, 字号) 缓存字体对象；字号会随自动缩放变化，重复加载很贵。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self._cache = {}

    def get(self, name, size):
        size = max(1, int(size))
        key = (str(name or ""), size)
        font = self._cache.get(key)
        if font is None:
            font = self._ctx.load_font(name or None, size)
            self._cache[key] = font
        return font

    def fit(self, name, text, base_size, max_width, tracking_ratio, minimum=8):
        """按可用宽度自动缩字号：库名 2 个字和 8 个字都要排得下。"""
        size = max(int(minimum), int(base_size))
        if not text or max_width <= 0:
            return size
        for _ in range(28):
            font = self.get(name, size)
            if _tracked_width(text, font, int(size * tracking_ratio)) <= max_width:
                break
            size = int(size * 0.94)
            if size <= minimum:
                return int(minimum)
        return size


def _metal_text(
    size,
    text,
    text_font,
    tracking,
    anchor_x,
    y,
    align,
    top_color,
    bottom_color,
    sheen=0.45,
    glow=0.18,
):
    """金属渐变标题：纵向三段渐变 + 斜向高光带 + 柔光。

    只在文字包围盒上作画（不是整张画布），1920×1080 下比全幅图层省一个数量级。
    返回 ``(layer, (x, y))``，由调用方 ``alpha_composite`` 到画布。
    """
    width, height = int(size[0]), int(size[1])
    block_w = _tracked_width(text, text_font, tracking)
    pad = max(6, int(_text_size(text_font) * 0.45))
    box_w = max(1, int(block_w) + pad * 2)
    box_h = max(1, int(_text_size(text_font)) + pad * 2)

    mask = Image.new("L", (box_w, box_h), 0)
    draw = ImageDraw.Draw(mask)
    start = _align_x(anchor_x, block_w, align)
    x = pad + (start - math.floor(start))
    for char in text:
        draw.text((x, pad), char, font=text_font, fill=255)
        x += text_font.getlength(char) + tracking
    if mask.getbbox() is None:
        return None

    bright = _mix(top_color, (255, 252, 244), 0.42)
    stops = [
        (0.0, bright),
        (0.42, tuple(top_color)),
        (0.66, _mix(top_color, bottom_color, 0.55)),
        (1.0, tuple(bottom_color)),
    ]
    gradient = _vgradient((box_w, box_h), stops).convert("RGBA")
    gradient.putalpha(mask)

    if sheen > 0:
        band = Image.linear_gradient("L").rotate(-16, expand=True).resize((box_w, box_h), Image.BILINEAR)
        band = ImageChops.offset(band, -int(box_w * 0.18), 0)
        spec = ImageChops.multiply(mask, band.point(lambda v: int(v * sheen)))
        highlight = Image.new("RGBA", (box_w, box_h), (255, 250, 236, 0))
        highlight.putalpha(spec)
        gradient = Image.alpha_composite(gradient, highlight)

    if glow > 0:
        blur = max(2, int(_text_size(text_font) * 0.12))
        bloom = mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * glow))
        halo = Image.new("RGBA", (box_w, box_h), tuple(stops[2][1]) + (0,))
        halo.putalpha(bloom)
        gradient = Image.alpha_composite(halo, gradient)

    return gradient, (int(start) - pad, int(y) - pad)


# ---------------------------------------------------------------- 配置读取


def _value(config, key, default=None):
    """取原始配置值：只有「没配」才用默认；空串保留，用户才能把标语 / 标签清空。"""
    if not isinstance(config, dict):
        return default
    value = config.get(key)
    return default if value is None else value


def _flag(config, key, default=True):
    value = _value(config, key, None)
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)


def _choice(config, key, options, default):
    value = str(_value(config, key, default) or default).strip()
    return value if value in options else default


def _number(config, key, default):
    return _clamp(_value(config, key, default), -1e9, 1e9, default)


def _json_map(raw):
    """解析「按库配置」的 JSON；任何异常都当空映射，绝不让渲染崩掉。"""
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------- schema

DEFAULT_FONT_TITLE = "优设标题黑.ttf"
DEFAULT_FONT_TEXT = "OPPOSans-M.ttf"
DEFAULT_FONT_LIGHT = "OPPOSans-L.ttf"
DEFAULT_FONT_BRUSH = "叶根友毛笔行书.ttf"

_ALIGN_OPTIONS = ["left", "center", "right"]
_INHERIT_ALIGN_OPTIONS = ["inherit", "left", "center", "right"]


def get_schema():
    """配置页参数：分组顺序就是界面顺序，默认值即参考图版式。"""
    return [
        {
            "group": "背景与底图",
            "items": [
                {"key": "bg_source", "label": "底图来源", "type": "select", "default": "keyart",
                 "options": [
                     {"label": "成品主视觉（上传 / URL / 按库）", "value": "keyart"},
                     {"label": "媒体库背景图", "value": "library"},
                 ]},
                {"key": "keyart_file", "label": "主视觉文件（上传后从 keyart/ 选）", "type": "file", "default": ""},
                {"key": "keyart_url", "label": "主视觉 URL（图床 / 直链）", "type": "text", "default": ""},
                {"key": "keyart_per_library", "label": "按库指定主视觉（JSON：库ID → 文件名或 URL）", "type": "text",
                 "default": "{}"},
                {"key": "keyart_focus_x", "label": "主视觉裁剪焦点 X %（防裁到脸）", "type": "range",
                 "min": 0, "max": 100, "step": 1, "default": 50},
                {"key": "keyart_focus_y", "label": "主视觉裁剪焦点 Y %", "type": "range",
                 "min": 0, "max": 100, "step": 1, "default": 50},
                {"key": "auto_mirror", "label": "素材镜像（开启即水平翻转，关闭用原图）", "type": "boolean",
                 "default": False},
            ],
        },
        {
            "group": "底图调整（默认 1.0 = 保持原样）",
            "items": [
                {"key": "scene_brightness", "label": "亮度", "type": "range",
                 "min": 0.5, "max": 1.6, "step": 0.01, "default": 1.0},
                {"key": "scene_contrast", "label": "对比度", "type": "range",
                 "min": 0.5, "max": 1.6, "step": 0.01, "default": 1.0},
                {"key": "scene_saturation", "label": "饱和度", "type": "range",
                 "min": 0.0, "max": 2.0, "step": 0.01, "default": 1.0},
            ],
        },
        {
            "group": "特效与装饰",
            "items": [
                {"key": "mask_enabled", "label": "显示渐变遮罩", "type": "boolean", "default": True},
                {"key": "mask_color", "label": "遮罩颜色", "type": "color", "default": "#000000"},
                {"key": "mask_opacity", "label": "遮罩浓度", "type": "range", "min": 0, "max": 255, "step": 1,
                 "default": 180},
                {"key": "mask_coverage", "label": "遮罩覆盖范围 %", "type": "range", "min": 10, "max": 100, "step": 1,
                 "default": 66},
                {"key": "mask_direction", "label": "遮罩方向", "type": "select", "default": "horizontal_reverse",
                 "options": [
                     {"label": "水平渐变 (左黑右亮)", "value": "horizontal"},
                     {"label": "水平渐变 (右黑左亮)", "value": "horizontal_reverse"},
                     {"label": "垂直渐变 (下黑上亮)", "value": "vertical"},
                     {"label": "垂直渐变 (上黑下亮)", "value": "vertical_reverse"},
                 ]},
                {"key": "bottom_scrim_color", "label": "底部遮罩颜色", "type": "color", "default": "#0A0705"},
                {"key": "bottom_scrim_strength", "label": "底部遮罩浓度（0=不压，保持原图）", "type": "range",
                 "min": 0, "max": 255, "step": 1, "default": 0},
            ],
        },
        {
            "group": "主标题",
            "items": [
                {"key": "title_enabled", "label": "显示主标题", "type": "boolean", "default": True},
                {"key": "title", "label": "主标题（空 = 媒体库名）", "type": "text", "default": ""},
                {"key": "font_title", "label": "主标题字体", "type": "font", "default": DEFAULT_FONT_TITLE},
                {"key": "title_size", "label": "字号（1080 高基准，超宽自动缩）", "type": "range",
                 "min": 40, "max": 320, "step": 1, "default": 189},
                {"key": "title_tracking", "label": "字距 em", "type": "range", "min": 0, "max": 0.2, "step": 0.005, "default": 0.055},
                {"key": "title_x", "label": "锚点 X %", "type": "range", "min": 0, "max": 100, "step": 0.1, "default": 76.2},
                {"key": "title_y", "label": "顶边 Y %", "type": "range", "min": 0, "max": 100, "step": 0.1, "default": 33},
                {"key": "title_align", "label": "对齐方式（锚点含义）", "type": "select", "default": "center",
                 "options": [{"label": "左对齐", "value": "left"}, {"label": "居中", "value": "center"},
                             {"label": "右对齐", "value": "right"}]},
                {"key": "title_max_width", "label": "最大宽度 %（超过缩字号）", "type": "range",
                 "min": 10, "max": 100, "step": 1, "default": 33},
                {"key": "title_gradient_top", "label": "金属字顶部颜色", "type": "color", "default": "#FFF6DC"},
                {"key": "title_gradient_bottom", "label": "金属字底部颜色", "type": "color", "default": "#C79A55"},
            ],
        },
        {
            "group": "副标题",
            "items": [
                {"key": "subtitle_enabled", "label": "显示副标题", "type": "boolean", "default": True},
                {"key": "subtitle", "label": "副标题（空 = 内置词典 / 库名）", "type": "text", "default": ""},
                {"key": "font_subtitle", "label": "副标题字体", "type": "font", "default": DEFAULT_FONT_LIGHT},
                {"key": "subtitle_size_ratio", "label": "字号（相对主标题）", "type": "range",
                 "min": 0.05, "max": 0.6, "step": 0.005, "default": 0.225},
                {"key": "subtitle_tracking", "label": "字距 em", "type": "range", "min": 0, "max": 0.8, "step": 0.01, "default": 0.46},
                {"key": "subtitle_gap", "label": "与光带距离 % 画布高", "type": "range", "min": 0, "max": 10, "step": 0.1, "default": 2.8},
                {"key": "subtitle_align", "label": "对齐方式", "type": "select", "default": "inherit",
                 "options": [{"label": "跟随标题", "value": "inherit"}, {"label": "左对齐", "value": "left"},
                             {"label": "居中", "value": "center"}, {"label": "右对齐", "value": "right"}]},
                {"key": "subtitle_max_width", "label": "最大宽度 %", "type": "range", "min": 10, "max": 100, "step": 1, "default": 33},
                {"key": "subtitle_color", "label": "颜色", "type": "color", "default": "#D9C9AE"},
            ],
        },
        {
            "group": "标语",
            "items": [
                {"key": "slogan_enabled", "label": "显示标语", "type": "boolean", "default": True},
                {"key": "slogan_cn", "label": "中文标语（空格分段）", "type": "text", "default": "好故事 好人生"},
                {"key": "slogan_en", "label": "英文标语（全大写渲染）", "type": "text", "default": "GOOD STORIES, GOOD LIFE"},
                {"key": "font_slogan", "label": "标语的字体", "type": "font", "default": DEFAULT_FONT_TEXT},
                {"key": "slogan_size_ratio", "label": "中文标语字号（相对主标题）", "type": "range",
                 "min": 0.05, "max": 0.6, "step": 0.005, "default": 0.215},
                {"key": "slogan_spacing", "label": "中文两段之间的间距 em（0=贴紧）", "type": "range",
                 "min": 0, "max": 3, "step": 0.05, "default": 0.85},
                {"key": "slogan_gap", "label": "与副标题距离 % 画布高", "type": "range", "min": 0, "max": 10, "step": 0.1, "default": 3.0},
                {"key": "slogan_en_size_ratio", "label": "英文标语字号（相对中文标语）", "type": "range",
                 "min": 0.1, "max": 1.2, "step": 0.01, "default": 0.46},
                {"key": "slogan_en_tracking", "label": "英文标语字距 em", "type": "range",
                 "min": 0, "max": 1, "step": 0.01, "default": 0.30},
                {"key": "slogan_align", "label": "对齐方式", "type": "select", "default": "inherit",
                 "options": [{"label": "跟随标题", "value": "inherit"}, {"label": "左对齐", "value": "left"},
                             {"label": "居中", "value": "center"}, {"label": "右对齐", "value": "right"}]},
                {"key": "slogan_max_width", "label": "最大宽度 %", "type": "range", "min": 10, "max": 100, "step": 1, "default": 33},
                {"key": "slogan_color", "label": "颜色", "type": "color", "default": "#EFE3CD"},
            ],
        },
        {
            "group": "灯带（标题下的光带）",
            "items": [
                {"key": "divider_enabled", "label": "显示光带", "type": "boolean", "default": True},
                {"key": "divider_width", "label": "长度 % 画布宽", "type": "range", "min": 5, "max": 100, "step": 1, "default": 30},
                {"key": "divider_thickness", "label": "灯带高度（1080 高基准）", "type": "range", "min": 1, "max": 12, "step": 0.1, "default": 2.4},
                {"key": "divider_gap", "label": "与标题下沿距离 % 画布高", "type": "range", "min": 0, "max": 15, "step": 0.1, "default": 5.0},
                {"key": "divider_color", "label": "灯带颜色", "type": "color", "default": "#C4A470"},
                {"key": "divider_flare_color", "label": "中心亮色", "type": "color", "default": "#FFFAF0"},
                {"key": "divider_flare_pos", "label": "高光点位置 %（50=正中）", "type": "range", "min": 0, "max": 100, "step": 1, "default": 50},
                {"key": "divider_flare_strength", "label": "中心亮度", "type": "range", "min": 0, "max": 255, "step": 1, "default": 245},
                {"key": "divider_align", "label": "对齐方式", "type": "select", "default": "inherit",
                 "options": [{"label": "跟随标题", "value": "inherit"}, {"label": "左对齐", "value": "left"},
                             {"label": "居中", "value": "center"}, {"label": "右对齐", "value": "right"}]},
            ],
        },
        {
            "group": "题材标签",
            "items": [
                {"key": "tags_enabled", "label": "显示题材标签", "type": "boolean", "default": True},
                {"key": "tags_source", "label": "取值优先级", "type": "select", "default": "manual",
                 "options": [
                     {"label": "手填优先", "value": "manual"},
                     {"label": "按库预设优先", "value": "library"},
                     {"label": "接口题材优先（Emby Genres）", "value": "auto"},
                 ]},
                {"key": "tags_text", "label": "手填标签（用分隔符隔开）", "type": "text", "default": ""},
                {"key": "tags_per_library", "label": "按库预设（JSON：库ID → 爱情｜都市｜…）", "type": "text", "default": "{}"},
                {"key": "tags_separator", "label": "分隔符", "type": "text", "default": "｜"},
                {"key": "font_tags", "label": "标签字体", "type": "font", "default": DEFAULT_FONT_TEXT},
                {"key": "tags_size", "label": "字号（1080 高基准）", "type": "range", "min": 8, "max": 60, "step": 1, "default": 25},
                {"key": "tags_tracking", "label": "字距 em", "type": "range", "min": 0, "max": 1, "step": 0.01, "default": 0.22},
                {"key": "tags_x", "label": "锚点 X %", "type": "range", "min": 0, "max": 100, "step": 0.1, "default": 4.2},
                {"key": "tags_y", "label": "锚点 Y %", "type": "range", "min": 0, "max": 100, "step": 0.1, "default": 91.8},
                {"key": "tags_align", "label": "对齐方式（默认左下）", "type": "select", "default": "left",
                 "options": [{"label": "左对齐", "value": "left"}, {"label": "居中", "value": "center"},
                             {"label": "右对齐", "value": "right"}]},
                {"key": "tags_max_width", "label": "最大宽度 %（超过缩字号）", "type": "range",
                 "min": 10, "max": 100, "step": 1, "default": 46},
                {"key": "tags_color", "label": "颜色", "type": "color", "default": "#D8C8AE"},
            ],
        },
        {
            "group": "书法水印",
            "items": [
                {"key": "watermark_enabled", "label": "显示水印", "type": "boolean", "default": True},
                {"key": "watermark_text", "label": "水印文字（空 = 整段标题）", "type": "text", "default": ""},
                {"key": "font_watermark", "label": "水印字体（缺失时自动跳过）", "type": "font", "default": DEFAULT_FONT_BRUSH},
                {"key": "watermark_size", "label": "单字字号上限（1080 高基准）", "type": "range",
                 "min": 0, "max": 900, "step": 1, "default": 520},
                {"key": "watermark_max_height", "label": "竖排总高上限 %（按字数自动缩）", "type": "range",
                 "min": 20, "max": 100, "step": 1, "default": 84},
                {"key": "watermark_x", "label": "锚点 X %（>100 = 右侧出血）", "type": "range",
                 "min": 0, "max": 130, "step": 0.1, "default": 85},
                {"key": "watermark_y", "label": "锚点 Y %", "type": "range", "min": 0, "max": 100, "step": 0.1, "default": 50},
                {"key": "watermark_line_gap", "label": "字间空隙（相对字号）", "type": "range",
                 "min": 0, "max": 1, "step": 0.01, "default": 0.04},
                {"key": "watermark_opacity", "label": "透明度 %", "type": "range", "min": 0, "max": 40, "step": 1, "default": 3},
                {"key": "watermark_rotate", "label": "旋转角度", "type": "range", "min": -30, "max": 30, "step": 1, "default": -6},
                {"key": "watermark_color", "label": "颜色", "type": "color", "default": "#FFDCBC"},
            ],
        },
        {
            "group": "圆角边框",
            "items": [
                {"key": "frame_radius", "label": "圆角半径（1080 高基准，0=直角）", "type": "range",
                 "min": 0, "max": 160, "step": 1, "default": 80},
                {"key": "frame_border_width", "label": "边框粗细（1080 高基准）", "type": "range",
                 "min": 0, "max": 16, "step": 0.1, "default": 8},
                {"key": "frame_border_color", "label": "边框颜色", "type": "color", "default": "#D8966C"},
                {"key": "frame_border_opacity", "label": "边框不透明度 %", "type": "range", "min": 0, "max": 100, "step": 1, "default": 66},
                {"key": "frame_glow", "label": "边框柔光 %", "type": "range", "min": 0, "max": 100, "step": 1, "default": 100},
                {"key": "frame_outside_color", "label": "圆角外底色", "type": "color", "default": "#060404"},
            ],
        },
    ]


# ---------------------------------------------------------------- 背景


def _safe_file_name(raw):
    """只接受裸文件名，拒绝路径穿越（keyart 来自配置，不能直接拼路径）。"""
    name = str(raw or "").strip()
    if not name or any(token in name for token in ("..", "/", "\\", ":", "|")) or name.startswith("."):
        return ""
    return name


def _load_reference(ctx, reference):
    """按「URL / dataURL / 数据目录里的裸文件名」加载一张主视觉。"""
    reference = str(reference or "").strip()
    if not reference:
        return None
    lowered = reference.lower()
    if lowered.startswith(("http://", "https://", "data:image")):
        return ctx.download_img(reference)
    name = _safe_file_name(reference)
    if not name:
        return None
    raw_root = str(getattr(ctx, "data_path", "") or "").strip()
    if not raw_root:
        return None
    data_path = Path(raw_root)
    for folder in (data_path / "keyart", data_path):
        candidate = folder / name
        if candidate.is_file():
            try:
                with Image.open(candidate) as image:
                    return image.convert("RGBA")
            except Exception:
                return None
    return None


def _focus_fit(image, size, focus_x, focus_y):
    """cover 裁剪到画布比例，再按焦点平移（避免把人物/标题裁掉）。"""
    width, height = int(size[0]), int(size[1])
    source = image.convert("RGBA")
    src_w, src_h = source.size
    if src_w <= 0 or src_h <= 0:
        return None
    scale = max(width / float(src_w), height / float(src_h))
    resized = source.resize((max(1, int(src_w * scale + 0.5)), max(1, int(src_h * scale + 0.5))), Image.LANCZOS)
    span_x = max(0, resized.size[0] - width)
    span_y = max(0, resized.size[1] - height)
    left = int(round(span_x * max(0.0, min(1.0, focus_x))))
    top = int(round(span_y * max(0.0, min(1.0, focus_y))))
    return resized.crop((left, top, left + width, top + height))


def _keyart(ctx, config, assets, size):
    """Mode B：按库配置 → URL → 上传文件名的顺序取主视觉。"""
    library_id = str(assets.get("library_id") or config.get("library_id") or "")
    mapping = _json_map(_value(config, "keyart_per_library", {}))
    candidates = []
    if library_id and mapping.get(library_id):
        candidates.append(mapping.get(library_id))
    candidates.append(_value(config, "keyart_url", ""))
    candidates.append(_value(config, "keyart_file", ""))
    for reference in candidates:
        image = _load_reference(ctx, reference)
        if image is not None:
            return _focus_fit(
                image,
                size,
                _clamp(_value(config, "keyart_focus_x", 50), 0, 100, 50) / 100.0,
                _clamp(_value(config, "keyart_focus_y", 50), 0, 100, 50) / 100.0,
            )
    return None


def _build_scene(ctx, bg, config, assets):
    """底图：返回 RGBA 画布；素材缺失时退回引擎给的背景图。不做任何锐化/调色。"""
    width, height = bg.size
    size = (width, height)
    source = _choice(config, "bg_source", ("keyart", "library"), "keyart")

    scene = None
    if source == "keyart":
        scene = _keyart(ctx, config, assets, size)
    if scene is None:
        scene = ImageOps.fit(bg.convert("RGBA"), size, method=Image.LANCZOS)
    # 素材镜像：两种底图来源都适用（主视觉 / 媒体库背景图）。
    # 语义是「开启就镜像、关闭就用原图」，不判断画面哪边更亮 —— 用户要的是可控的翻转开关，
    # 而不是让插件猜。默认关闭。
    if _flag(config, "auto_mirror", False):
        scene = ImageOps.mirror(scene)

    # 底图调整：默认全部 1.0，等于「底图什么样就什么样」；只有用户显式调了才生效。
    brightness = _clamp(_value(config, "scene_brightness", 1.0), 0.5, 1.6, 1.0)
    contrast = _clamp(_value(config, "scene_contrast", 1.0), 0.5, 1.6, 1.0)
    saturation = _clamp(_value(config, "scene_saturation", 1.0), 0.0, 2.0, 1.0)
    if abs(brightness - 1.0) > 1e-3:
        scene = ImageEnhance.Brightness(scene).enhance(brightness)
    if abs(contrast - 1.0) > 1e-3:
        scene = ImageEnhance.Contrast(scene).enhance(contrast)
    if abs(saturation - 1.0) > 1e-3:
        scene = ImageEnhance.Color(scene).enhance(saturation)
    return scene


# ---------------------------------------------------------------- 标签


def _split_tags(text, separator):
    separator = str(separator or "｜")
    pattern = r"[\s|｜]+" if separator in ("｜", "|") else re.escape(separator)
    return [token.strip() for token in re.split(pattern, str(text or "")) if token.strip()]


def _tags_for(config, assets):
    """标签三级取值：手填 / 按库预设 / 接口题材，按 tags_source 决定谁优先。"""
    library_id = str(assets.get("library_id") or config.get("library_id") or "")
    separator = _value(config, "tags_separator", "｜")
    manual = _split_tags(_value(config, "tags_text", ""), separator)

    mapping = _json_map(_value(config, "tags_per_library", {}))
    preset = mapping.get(library_id) if library_id else None
    if isinstance(preset, (list, tuple)):
        per_library = [str(item).strip() for item in preset if str(item).strip()]
    else:
        per_library = _split_tags(preset, separator)

    genres = assets.get("genres")
    auto = []
    if isinstance(genres, (list, tuple)):
        auto = [str(item).strip() for item in genres if str(item).strip()]
    elif genres:
        auto = _split_tags(genres, separator)

    order = {
        "manual": (manual, per_library, auto),
        "library": (per_library, manual, auto),
        "auto": (auto, per_library, manual),
    }.get(_choice(config, "tags_source", ("manual", "library", "auto"), "manual"), (manual, per_library, auto))
    for candidate in order:
        if candidate:
            return candidate
    return []


# ---------------------------------------------------------------- 渲染


def render(ctx, bg, config, assets, fonts=None, step=None):
    """把素材 + 配置合成分类横幅；``step`` 只为兼容动态封面签名，本布局不做动画。"""
    config = config if isinstance(config, dict) else {}
    assets = assets if isinstance(assets, dict) else {}
    width, height = bg.size
    scale = height / float(REFERENCE_HEIGHT)

    def px(value, minimum=1):
        return max(minimum, int(round(float(value) * scale)))

    book = _FontBook(ctx)
    frame = _build_scene(ctx, bg, config, assets)
    title = str(_value(config, "title", "") or assets.get("library_name") or "").strip()

    # ---- 渐变遮罩（特效与装饰）：与「极简」同一套参数，方向可正可反，颜色可选
    if _flag(config, "mask_enabled", True):
        mask = ctx.create_smart_mask(
            width,
            height,
            _clamp(_value(config, "mask_opacity", 180), 0, 255, 180),
            _clamp(_value(config, "mask_coverage", 66), 10, 100, 66),
            _choice(
                config,
                "mask_direction",
                ("horizontal", "horizontal_reverse", "vertical", "vertical_reverse"),
                "horizontal_reverse",
            ),
        )
        mask_color = _rgb(_value(config, "mask_color", "#000000"), (0, 0, 0))
        shade = Image.new("RGBA", (width, height), mask_color + (255,))
        shade.putalpha(mask)
        frame = Image.alpha_composite(frame, shade)

    # ---- 底部遮罩：给左下角的题材标签一个落脚点（整幅压，不依赖左右分区）
    # 默认 0 = 完全不压，底图什么样就什么样；用户想要压暗再往上调。
    bottom_strength = _clamp(_value(config, "bottom_scrim_strength", 0), 0, 255, 0)
    if bottom_strength > 0:
        bottom = _vgradient((width, height), [(0.0, (0, 0, 0)), (1.0, _rgb(_value(config, "bottom_scrim_color", "#0A0705"), (10, 7, 5)))])
        bmask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(bmask).rectangle((0, int(height * 0.76), width, height), fill=255)
        bottom.putalpha(
            bmask.filter(ImageFilter.GaussianBlur(max(4, int(height * 0.066)))).point(
                lambda v: int(v * bottom_strength / 255.0)
            )
        )
        frame = Image.alpha_composite(frame, bottom)

    # ---- 书法水印：整段标题竖排，字号按字数自动收缩，可整块关闭。
    # 默认锚点 85%，会落在标题右侧的可见区里，所以先画它、再画文字，
    # 让它当背景纹理而不是压在标题上（否则字叠字像重影）。
    if _flag(config, "watermark_enabled", True):
        mark_text = str(_value(config, "watermark_text", "") or title).strip()
        chars = [char for char in mark_text if not char.isspace()]
        mark_font_name = _value(config, "font_watermark", DEFAULT_FONT_BRUSH)
        # 字体缺失就整块跳过，别把中文画成一排方框（tofu）。
        raw_fonts_dir = str(getattr(ctx, "fonts_dir", "") or "").strip()
        font_available = True
        if mark_font_name:
            font_available = bool(raw_fonts_dir) and (Path(raw_fonts_dir) / str(mark_font_name)).is_file()
        if chars and font_available:
            base_mark = px(_clamp(_value(config, "watermark_size", 520), 0, 900, 520))
            available = height * _clamp(_value(config, "watermark_max_height", 84), 20, 100, 84) / 100.0
            per = max(8, int(min(base_mark, available / len(chars) * 0.92)))
            mark_font = book.get(mark_font_name, per)
            line_gap = int(per * _clamp(_value(config, "watermark_line_gap", 0.04), 0, 1, 0.04))
            col_w = max(mark_font.getlength(char) for char in chars)
            total_h = per * len(chars) + line_gap * (len(chars) - 1)
            mark_img = Image.new("RGBA", (max(1, int(col_w * 1.7)), max(1, int(total_h + per * 0.5))), (0, 0, 0, 0))
            mark_draw = ImageDraw.Draw(mark_img)
            mark_color = _rgb(_value(config, "watermark_color", "#FFDCBC"), (255, 220, 188)) + (255,)
            for index, char in enumerate(chars):
                char_w = mark_font.getlength(char)
                mark_draw.text(
                    ((mark_img.width - char_w) / 2, index * (per + line_gap)),
                    char, font=mark_font, fill=mark_color,
                )
            mark_img = mark_img.rotate(
                _clamp(_value(config, "watermark_rotate", -6), -30, 30, -6), resample=Image.BICUBIC, expand=True
            )
            opacity = _clamp(_value(config, "watermark_opacity", 3), 0, 40, 3) / 100.0
            mark_img.putalpha(mark_img.getchannel("A").point(lambda v: int(v * opacity)))
            frame.alpha_composite(
                mark_img,
                (
                    int(width * _clamp(_value(config, "watermark_x", 85), 0, 130, 85) / 100.0 - mark_img.width / 2),
                    int(height * _clamp(_value(config, "watermark_y", 50), 0, 100, 50) / 100.0 - mark_img.height / 2),
                ),
            )

    # ---- 标题：决定整块文字的锚点与对齐，其余元素默认 inherit
    title_align = _choice(config, "title_align", tuple(_ALIGN_OPTIONS), "center")
    anchor = width * _clamp(_value(config, "title_x", 76.2), 0, 100, 76.2) / 100.0
    title_top = height * _clamp(_value(config, "title_y", 33), 0, 100, 33) / 100.0
    title_tracking_ratio = _clamp(_value(config, "title_tracking", 0.055), 0, 0.2, 0.055)
    title_font_name = _value(config, "font_title", DEFAULT_FONT_TITLE)
    base_size = px(_clamp(_value(config, "title_size", 189), 40, 320, 189))
    max_width = width * _clamp(_value(config, "title_max_width", 33), 10, 100, 33) / 100.0
    title_size = book.fit(title_font_name, title, base_size, max_width, title_tracking_ratio)
    title_tracking = int(title_size * title_tracking_ratio)
    title_font = book.get(title_font_name, title_size)

    if title and _flag(config, "title_enabled", True):
        metal = _metal_text(
            (width, height), title, title_font, title_tracking, anchor, title_top, title_align,
            _rgb(_value(config, "title_gradient_top", "#FFF6DC"), (255, 246, 220)),
            _rgb(_value(config, "title_gradient_bottom", "#C79A55"), (199, 154, 85)),
        )
        if metal is not None:
            layer, (layer_x, layer_y) = metal
            shadow = layer.getchannel("A").filter(
                ImageFilter.GaussianBlur(max(2, int(height * 0.014)))
            ).point(lambda v: int(v * 0.5))
            shadow_layer = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            shadow_layer.putalpha(shadow)
            frame.alpha_composite(shadow_layer, (layer_x, layer_y + int(height * 0.012)))
            frame.alpha_composite(layer, (layer_x, layer_y))

    # ---- 光带：高光点按 flare_pos 落在光带自身长度上
    divider_align = _choice(config, "divider_align", tuple(_INHERIT_ALIGN_OPTIONS), "inherit")
    if divider_align == "inherit":
        divider_align = title_align
    line_y = int(title_top + title_size * 0.92 + height * _clamp(_value(config, "divider_gap", 5.0), 0, 15, 5.0) / 100.0)
    line_w = int(width * _clamp(_value(config, "divider_width", 30), 5, 100, 30) / 100.0)
    line_x0 = int(_align_x(anchor, line_w, divider_align))
    line_thickness = px(_clamp(_value(config, "divider_thickness", 2.4), 1, 12, 2.4))
    if _flag(config, "divider_enabled", True) and line_w > 0:
        flare_ratio = _clamp(_value(config, "divider_flare_pos", 50), 0, 100, 50) / 100.0
        glow = _glow_line(
            (width, height),
            (line_x0 + line_w * flare_ratio, line_y),
            line_w,
            line_thickness,
            _rgb(_value(config, "divider_color", "#C4A470"), (196, 164, 112)),
            _rgb(_value(config, "divider_flare_color", "#FFFAF0"), (255, 250, 240)),
            _clamp(_value(config, "divider_flare_strength", 245), 0, 255, 245),
        )
        if glow is not None:
            # 光带要「发光」而不是「贴一张白纸」：用 screen 叠，压到亮底图上也亮得起来。
            # （alpha 叠加时，白光照在本来就白的地方等于没画。）
            glow_x, glow_y, layer = glow
            box = (glow_x, glow_y, glow_x + layer.width, glow_y + layer.height)
            frame.paste(ImageChops.screen(frame.crop(box), layer), box)

    # ---- 副标题（全大写 + 宽字距）
    subtitle = str(_value(config, "subtitle", "") or assets.get("library_en") or "").strip().upper()
    subtitle_align = _choice(config, "subtitle_align", tuple(_INHERIT_ALIGN_OPTIONS), "inherit")
    if subtitle_align == "inherit":
        subtitle_align = title_align
    subtitle_tracking_ratio = _clamp(_value(config, "subtitle_tracking", 0.46), 0, 0.8, 0.46)
    subtitle_base = int(title_size * _clamp(_value(config, "subtitle_size_ratio", 0.225), 0.05, 0.6, 0.225))
    subtitle_max = width * _clamp(_value(config, "subtitle_max_width", 33), 10, 100, 33) / 100.0
    subtitle_size = book.fit(
        _value(config, "font_subtitle", DEFAULT_FONT_LIGHT), subtitle, subtitle_base, subtitle_max, subtitle_tracking_ratio
    )
    subtitle_font = book.get(_value(config, "font_subtitle", DEFAULT_FONT_LIGHT), subtitle_size)
    subtitle_tracking = int(subtitle_size * subtitle_tracking_ratio)
    subtitle_y = line_y + int(height * _clamp(_value(config, "subtitle_gap", 2.8), 0, 10, 2.8) / 100.0)
    if subtitle and _flag(config, "subtitle_enabled", True):
        _draw_tracked(
            ImageDraw.Draw(frame), subtitle, anchor, subtitle_y, subtitle_font,
            _rgb(_value(config, "subtitle_color", "#D9C9AE"), (217, 201, 174)) + (255,),
            subtitle_tracking, subtitle_align,
        )

    # ---- 中文标语：空格分段，段间距可调（默认 0.85em，不再是大裂口）
    slogan_align = _choice(config, "slogan_align", tuple(_INHERIT_ALIGN_OPTIONS), "inherit")
    if slogan_align == "inherit":
        slogan_align = title_align
    slogan_font_name = _value(config, "font_slogan", DEFAULT_FONT_TEXT)
    slogan_color = _rgb(_value(config, "slogan_color", "#EFE3CD"), (239, 227, 205)) + (255,)
    slogan_parts = [part for part in re.split(r"[\s｜|]+", str(_value(config, "slogan_cn", "") or "")) if part]
    slogan_size = int(title_size * _clamp(_value(config, "slogan_size_ratio", 0.215), 0.05, 0.6, 0.215))
    slogan_font = book.get(slogan_font_name, slogan_size)
    slogan_spacing = _clamp(_value(config, "slogan_spacing", 0.85), 0, 3, 0.85)
    slogan_max = width * _clamp(_value(config, "slogan_max_width", 33), 10, 100, 33) / 100.0
    slogan_gap = int(slogan_size * slogan_spacing)
    slogan_block = sum(slogan_font.getlength(part) for part in slogan_parts) + slogan_gap * max(0, len(slogan_parts) - 1)
    if slogan_parts and slogan_block > slogan_max:
        slogan_size = max(8, int(slogan_size * slogan_max / slogan_block))
        slogan_font = book.get(slogan_font_name, slogan_size)
        slogan_gap = int(slogan_size * slogan_spacing)
        slogan_block = sum(slogan_font.getlength(part) for part in slogan_parts) + slogan_gap * max(0, len(slogan_parts) - 1)
    slogan_y = subtitle_y + int(subtitle_size * 1.45 + height * _clamp(_value(config, "slogan_gap", 3.0), 0, 10, 3.0) / 100.0)
    slogan_enabled = _flag(config, "slogan_enabled", True)
    if slogan_parts and slogan_enabled:
        draw = ImageDraw.Draw(frame)
        x = _align_x(anchor, slogan_block, slogan_align)
        for index, part in enumerate(slogan_parts):
            draw.text((x, slogan_y), part, font=slogan_font, fill=slogan_color)
            x += slogan_font.getlength(part) + (slogan_gap if index < len(slogan_parts) - 1 else 0)

    # ---- 英文标语
    slogan_en = str(_value(config, "slogan_en", "") or "").strip().upper()
    if slogan_en and slogan_enabled:
        en_ratio = _clamp(_value(config, "slogan_en_size_ratio", 0.46), 0.1, 1.2, 0.46)
        en_tracking_ratio = _clamp(_value(config, "slogan_en_tracking", 0.30), 0, 1, 0.30)
        en_base = int(max(8, slogan_size) * en_ratio)
        en_size = book.fit(slogan_font_name, slogan_en, en_base, slogan_max, en_tracking_ratio)
        en_font = book.get(slogan_font_name, en_size)
        en_y = slogan_y + int(max(8, slogan_size) * 1.42 + height * 0.026)
        # 英文标语比中文标语退一档：混进压暗色，而不是用半透明（直接画在 RGBA 上会丢 alpha）。
        en_color = _mix(slogan_color[:3], (10, 7, 5), 0.18)
        _draw_tracked(
            ImageDraw.Draw(frame), slogan_en, anchor, en_y, en_font, en_color,
            int(en_size * en_tracking_ratio), slogan_align,
        )

    # ---- 题材标签：默认左下；手填 > 按库预设 > 接口题材
    tags = _tags_for(config, assets) if _flag(config, "tags_enabled", True) else []
    if tags:
        tag_size = px(_clamp(_value(config, "tags_size", 25), 8, 60, 25))
        tag_tracking_ratio = _clamp(_value(config, "tags_tracking", 0.22), 0, 1, 0.22)
        tag_font_name = _value(config, "font_tags", DEFAULT_FONT_TEXT)
        tag_font = book.get(tag_font_name, tag_size)
        separator = str(_value(config, "tags_separator", "｜") or "｜")[:2]
        tag_tracking = int(tag_size * tag_tracking_ratio)
        tag_max = width * _clamp(_value(config, "tags_max_width", 46), 10, 100, 46) / 100.0

        def _block_width(size, font, tracking):
            width_sum = sum(_tracked_width(tag, font, tracking) for tag in tags)
            sep_w = _tracked_width(separator, font, tracking) + size * 1.65
            return width_sum + sep_w * max(0, len(tags) - 1)

        total = _block_width(tag_size, tag_font, tag_tracking)
        if total > tag_max:
            tag_size = max(8, int(tag_size * tag_max / max(1.0, total)))
            tag_font = book.get(tag_font_name, tag_size)
            tag_tracking = int(tag_size * tag_tracking_ratio)
            total = _block_width(tag_size, tag_font, tag_tracking)

        tag_align = _choice(config, "tags_align", tuple(_ALIGN_OPTIONS), "left")
        tag_x = _align_x(
            width * _clamp(_value(config, "tags_x", 4.2), 0, 100, 4.2) / 100.0, total, tag_align
        )
        tag_y = int(height * _clamp(_value(config, "tags_y", 91.8), 0, 100, 91.8) / 100.0)
        tag_color = _rgb(_value(config, "tags_color", "#D8C8AE"), (216, 200, 174))
        separator_color = _mix(tag_color, (10, 7, 5), 0.28)
        draw = ImageDraw.Draw(frame)
        for index, tag in enumerate(tags):
            _draw_tracked(draw, tag, tag_x, tag_y, tag_font, tag_color, tag_tracking, "left")
            tag_x += _tracked_width(tag, tag_font, tag_tracking)
            if index < len(tags) - 1:
                _draw_tracked(draw, separator, tag_x + tag_size * 0.75, tag_y, tag_font, separator_color, tag_tracking, "left")
                tag_x += _tracked_width(separator, tag_font, tag_tracking) + tag_size * 1.65

    # ---- 圆角 + 双层描边（最后画，保证边框压在文字上沿）
    radius = px(_clamp(_value(config, "frame_radius", 80), 0, 160, 80), minimum=0)
    if radius > 0:
        frame.putalpha(_rounded_mask((width, height), radius))
        outside = _rgb(_value(config, "frame_outside_color", "#060404"), (6, 4, 4))
        frame = Image.alpha_composite(Image.new("RGBA", (width, height), outside + (255,)), frame)

    border_w = px(_clamp(_value(config, "frame_border_width", 8), 0, 16, 8), minimum=0)
    border_opacity = _clamp(_value(config, "frame_border_opacity", 66), 0, 100, 66) / 100.0
    if border_w > 0 and border_opacity > 0:
        inset = max(2, int(height * 0.0035))
        border_color = _rgb(_value(config, "frame_border_color", "#D8966C"), (216, 150, 108))
        edge = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(edge).rounded_rectangle(
            (inset, inset, width - 1 - inset, height - 1 - inset),
            radius=max(0, radius - inset), outline=border_color + (int(255 * border_opacity),), width=border_w,
        )
        frame = Image.alpha_composite(frame, edge)

        glow_ratio = _clamp(_value(config, "frame_glow", 100), 0, 100, 100) / 100.0
        if glow_ratio > 0:
            glow_line = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            ImageDraw.Draw(glow_line).rounded_rectangle(
                (inset, inset, width - 1 - inset, height - 1 - inset),
                radius=max(0, radius - inset), outline=border_color + (110,), width=max(2, border_w * 2),
            )
            glow_line = glow_line.filter(ImageFilter.GaussianBlur(max(1, int(height * 0.006))))
            glow_line.putalpha(glow_line.getchannel("A").point(lambda v: int(v * glow_ratio)))
            frame = Image.alpha_composite(frame, glow_line)

    return frame
