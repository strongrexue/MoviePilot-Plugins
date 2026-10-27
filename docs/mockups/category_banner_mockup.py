"""生成「分类横幅」封面效果图（mockup），同时充当布局参考实现。

这不是插件运行代码，只画图。运行：

    python docs/mockups/category_banner_mockup.py

产出（docs/mockups/）：
- category_banner_a_library.jpg        暖金 · 媒体库场景（Mode A · 左对齐）
- category_banner_b_library_cool.jpg   冷蓝 · 媒体库场景（Mode A · 左对齐）
- category_banner_c_posters.jpg        朱红 · 海报阵列（Mode A2 · 左对齐）
- category_banner_d_keyart_left.jpg    暖金 · 成品主视觉（Mode B · 左对齐，参考图原版式）
- category_banner_e_keyart_center.jpg  暖金 · 成品主视觉（Mode B · 标题块居中）

设计要点：**不按左右分区写死**。标题 / 英文名 / 标语 / 光带 / 标签 / 水印 / 边框
各自有独立的 x / y / 对齐方式 / 字号 / 字距，默认值拼出来才是参考图的版式；
想走居中、想挪标签、想换水印位置，都只是改参数。
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
OUT_DIR = Path(__file__).resolve().parent
FONT_DIR = OUT_DIR.parents[1] / "plugins.v3" / "embycovercenter" / "defaults" / "fonts"

FONT_TITLE = "优设标题黑.ttf"          # 笔画均匀的黑体，接近参考图标题
FONT_TEXT = "OPPOSans-M.ttf"           # 标签 / 英文标语
FONT_LIGHT = "OPPOSans-L.ttf"          # 英文副标题（细体 + 宽字距）
FONT_LATIN = "Bookman Old Style Bold.TTF"  # 海报片名条
FONT_BRUSH = "叶根友毛笔行书.ttf"       # 书法水印

# ---------------------------------------------------------------- 基础工具


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / name
    if path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def smooth(t: float) -> float:
    """smoothstep：两端导数为 0，渐变不会出现可见硬边。"""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, ratio: float):
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(round(x * (1 - ratio) + y * ratio)) for x, y in zip(a, b))


def vgradient(size, stops):
    """纵向渐变（stops: [(位置0-1, RGB)]）。"""
    width, height = size
    strip = Image.new("RGB", (1, height))
    draw = ImageDraw.Draw(strip)
    for y in range(height):
        t = y / max(1, height - 1)
        color = stops[-1][1]
        for index in range(len(stops) - 1):
            p0, c0 = stops[index]
            p1, c1 = stops[index + 1]
            if p0 <= t <= p1:
                color = mix(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        draw.point((0, y), fill=color)
    return strip.resize((width, height), Image.BILINEAR)


def radial_glow(size, center, radius, color, strength):
    """径向光晕：中心最亮、向外平滑衰减。"""
    if strength <= 0 or radius <= 0:
        return None
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = center
    steps = 40
    for index in range(steps, 0, -1):
        t = index / float(steps)
        draw.ellipse(
            (cx - radius * t, cy - radius * t, cx + radius * t, cy + radius * t),
            fill=int(strength * (1.0 - t) ** 2),
        )
    layer = Image.new("RGBA", size, tuple(color) + (0,))
    layer.putalpha(mask)
    return layer


def side_scrim(size, start_ratio, color, strength, ramp_ratio=0.30):
    """从 start_ratio 起向右压暗，ramp_ratio 宽度内吃满。

    参考图的暗场不是线性渐变——亮场保持到 55% 后迅速沉黑，
    再往右是「有肌理的黑」。线性渐变会把文字压在灰调上，读不清。
    """
    width, height = size
    start = int(width * start_ratio)
    ramp = max(1, int(width * ramp_ratio))
    alpha = Image.new("L", size, 0)
    draw = ImageDraw.Draw(alpha)
    for x in range(start, width):
        t = min(1.0, (x - start) / ramp)
        draw.line([(x, 0), (x, height)], fill=int(strength * smooth(t)))
    layer = Image.new("RGBA", size, tuple(color) + (0,))
    layer.putalpha(alpha)
    return layer


def vignette(size, strength, power=2.6):
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = width / 2.0, height / 2.0
    max_r = math.hypot(cx, cy)
    for index in range(48, 0, -1):
        t = index / 48.0
        draw.ellipse(
            (cx - max_r * t, cy - max_r * t, cx + max_r * t, cy + max_r * t),
            fill=int(strength * (t ** power)),
        )
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.putalpha(mask)
    return layer


def grain(image, amount):
    width, height = image.size
    ratio = max(0.0, min(1.0, amount / 100.0)) * 0.16
    if ratio <= 0:
        return image
    rng = random.Random((width << 20) ^ height ^ 0x9E3779B9)
    noise = Image.frombytes("L", (width, height), rng.randbytes(width * height))
    return Image.blend(image.convert("RGB"), Image.merge("RGB", (noise, noise, noise)), ratio).convert("RGBA")


def grade(image, tint, strength=0.14, lift=6):
    """统一调色：整体 wash 到同一色相，黑位带一点色，避免死黑。"""
    wash = Image.new("RGB", image.size, tint)
    out = Image.blend(image.convert("RGB"), wash, strength)
    if lift:
        out = Image.blend(out, Image.new("RGB", image.size, (255, 245, 230)), lift / 255.0)
    return out.convert("RGBA")


# ---------------------------------------------------------------- 文字工具


def tracked_width(text, text_font, tracking):
    return sum(text_font.getlength(char) for char in text) + tracking * max(0, len(text) - 1)


def fit_size(text, font_name, base_size, max_width, tracking_ratio):
    """按可用宽度自动缩字号：库名 2 个字和 8 个字都要排得下。"""
    size = max(8, int(base_size))
    for _ in range(24):
        candidate = font(font_name, size)
        if tracked_width(text, candidate, int(size * tracking_ratio)) <= max_width:
            break
        size = int(size * 0.94)
        if size <= 8:
            break
    return size


def align_x(anchor: float, width: float, align: str) -> float:
    """把「锚点」换算成绘制起点：left=锚点，center=锚点-半宽，right=锚点-全宽。"""
    if align == "center":
        return anchor - width / 2.0
    if align == "right":
        return anchor - width
    return anchor


def draw_tracked(draw, text, anchor_x, y, text_font, fill, tracking, align="left"):
    """逐字绘制（PIL 没有字距），按 align 相对 anchor_x 对齐。"""
    if not text:
        return
    start = align_x(anchor_x, tracked_width(text, text_font, tracking), align)
    x = start
    for char in text:
        draw.text((x, y), char, font=text_font, fill=fill)
        x += text_font.getlength(char) + tracking


def tracked_mask(size, text, text_font, tracking, anchor_x, y, align="left"):
    """同 draw_tracked，但输出 L 遮罩（给金属渐变标题用）。"""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    start = align_x(anchor_x, tracked_width(text, text_font, tracking), align)
    x = start
    for char in text:
        draw.text((x, y), char, font=text_font, fill=255)
        x += text_font.getlength(char) + tracking
    return mask


def metal_text(size, text, text_font, tracking, anchor_x, y, palette, align="left", sheen=0.5, glow=0.2):
    """金属渐变标题：纵向三段渐变 + 斜向高光带 + 柔光。"""
    width, height = size
    mask = tracked_mask(size, text, text_font, tracking, anchor_x, y, align)
    if mask.getbbox() is None:
        return None
    gradient = vgradient(size, palette["metal"]).convert("RGBA")
    gradient.putalpha(mask)
    if sheen > 0:
        band = Image.linear_gradient("L").rotate(-16, expand=True).resize(size, Image.BILINEAR)
        band = ImageChops.offset(band, -int(width * 0.18), 0)
        spec = ImageChops.multiply(mask, band.point(lambda v: int(v * sheen)))
        highlight = Image.new("RGBA", size, (255, 250, 236, 0))
        highlight.putalpha(spec)
        gradient = Image.alpha_composite(gradient, highlight)
    if glow > 0:
        bloom = mask.filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * glow))
        halo = Image.new("RGBA", size, tuple(palette["metal"][-1][1]) + (0,))
        halo.putalpha(bloom)
        gradient = Image.alpha_composite(halo, gradient)
    return gradient


# ---------------------------------------------------------------- 背景素材


def _ridge(draw, base_y, amp, tone, phase, steps=90):
    """平滑山脊：几组不同波长的正弦叠加，比随机折线更像实拍远景。"""
    points = [(-20, H)]
    for index in range(steps + 1):
        x = -20 + (W + 40) * index / steps
        y = (
            H * base_y
            + math.sin(x / 430.0 + phase) * amp
            + math.sin(x / 173.0 + phase * 1.7) * amp * 0.42
            + math.sin(x / 61.0 + phase * 2.3) * amp * 0.14
        )
        points.append((x, y))
    points.append((W + 20, H))
    draw.polygon(points, fill=tone + (255,))


def _haze(size, y_ratio, height_ratio, color, strength):
    """地平线雾带：把远近景分开，制造空气透视。"""
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    center = int(height * y_ratio)
    span = int(height * height_ratio)
    for y in range(max(0, center - span), min(height, center + span)):
        t = abs(y - center) / max(1, span)
        draw.line([(0, y), (width, y)], fill=int(strength * (1 - smooth(t))))
    layer = Image.new("RGBA", size, tuple(color) + (0,))
    layer.putalpha(mask)
    return layer


def _light_rays(size, center, color, count=7, strength=26):
    width, height = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    for index in range(count):
        angle = math.radians(-64 + index * 9)
        spread = math.radians(2.4 + (index % 3) * 1.6)
        length = height * 1.5
        far = (cx + math.sin(angle) * length, cy + math.cos(angle) * length)
        near = (cx + math.sin(angle) * height * 0.06, cy + math.cos(angle) * height * 0.06)
        left = (far[0] - math.sin(angle - spread) * length, far[1] - math.cos(angle - spread) * length)
        right = (far[0] - math.sin(angle + spread) * length, far[1] - math.cos(angle + spread) * length)
        draw.polygon([near, right, left], fill=color + (strength,))
    return layer.filter(ImageFilter.GaussianBlur(int(height * 0.012)))


def scene_layer(palette, seed=7):
    """Mode A：媒体库背景图（此处程序化模拟：天空 + 光源 + 多层山脊 + 雾）。"""
    layer = vgradient((W, H), palette["sky"]).convert("RGBA")
    sun_x, sun_y = int(W * palette.get("sun_x", 0.30)), int(H * palette.get("sun_y", 0.62))
    layer = Image.alpha_composite(layer, radial_glow((W, H), (sun_x, sun_y), W * 0.40, palette["sun"], 135))
    layer = Image.alpha_composite(layer, _light_rays((W, H), (sun_x, sun_y - int(H * 0.04)), palette["sun"]))
    sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    radius = int(H * 0.030)
    ImageDraw.Draw(sun).ellipse(
        (sun_x - radius, sun_y - radius, sun_x + radius, sun_y + radius), fill=palette["sun"] + (200,)
    )
    layer = Image.alpha_composite(layer, sun.filter(ImageFilter.GaussianBlur(int(H * 0.010))))

    for index, (base_y, tone, amp) in enumerate(palette["ridges"]):
        ridge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _ridge(ImageDraw.Draw(ridge_layer), base_y, amp, tone, phase=0.7 + index * 1.9)
        layer = Image.alpha_composite(layer, ridge_layer)
        if index < len(palette["ridges"]) - 1:
            layer = Image.alpha_composite(layer, _haze((W, H), base_y + 0.008, 0.05, palette["haze"], 110))

    ground = vgradient((W, H), [(0.0, palette["ground"]), (0.55, palette["ground"]), (1.0, (6, 4, 4))])
    gmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gmask).rectangle((0, int(H * 0.80), W, H), fill=255)
    ground.putalpha(gmask.filter(ImageFilter.GaussianBlur(52)).point(lambda v: int(v * 0.95)))
    return Image.alpha_composite(layer, ground)


def _person(draw, cx, base_y, height, color):
    """背光剪影：头 / 颈 / 肩 / 躯干 / 手臂 / 腿，只读轮廓不读细节。"""
    h = height
    head_r = h * 0.055
    head_cy = base_y - h * 0.905
    # 头（略窄的椭圆，别画成正圆，正圆很像棋子）
    draw.ellipse((cx - head_r * 0.86, head_cy - head_r, cx + head_r * 0.86, head_cy + head_r), fill=color)
    # 颈
    draw.rectangle((cx - h * 0.026, head_cy + head_r * 0.55, cx + h * 0.026, base_y - h * 0.815), fill=color)
    # 躯干 + 大衣：肩宽 → 收腰 → 下摆微张
    draw.polygon(
        [
            (cx - h * 0.112, base_y - h * 0.792),
            (cx - h * 0.088, base_y - h * 0.700),
            (cx - h * 0.072, base_y - h * 0.500),
            (cx - h * 0.098, base_y - h * 0.045),
            (cx + h * 0.098, base_y - h * 0.045),
            (cx + h * 0.072, base_y - h * 0.500),
            (cx + h * 0.088, base_y - h * 0.700),
            (cx + h * 0.112, base_y - h * 0.792),
            (cx, base_y - h * 0.812),
        ],
        fill=color,
    )
    # 手臂：贴身两条，往下略外张
    for side in (-1, 1):
        draw.polygon(
            [
                (cx + side * h * 0.100, base_y - h * 0.790),
                (cx + side * h * 0.128, base_y - h * 0.775),
                (cx + side * h * 0.108, base_y - h * 0.500),
                (cx + side * h * 0.080, base_y - h * 0.505),
            ],
            fill=color,
        )
    # 腿：大衣下摆以下露出的两条
    for side in (-1, 1):
        draw.rectangle(
            (cx + side * h * 0.016 - h * 0.022, base_y - h * 0.070,
             cx + side * h * 0.016 + h * 0.022, base_y),
            fill=color,
        )


def keyart_layer(palette):
    """Mode B：模拟「用户 / AI 提供的分类主视觉」，插件侧只做调色与压字。

    构图按参考图走：人物占左 6 成、背光剪影 + 轮廓光、远景压暗。
    """
    base = scene_layer(palette)
    base = base.filter(ImageFilter.GaussianBlur(2))

    figures = [(0.215, 1.020, 0.92), (0.335, 1.030, 0.68), (0.430, 1.020, 0.58)]
    sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sil_draw = ImageDraw.Draw(sil)
    for cx, base_y, scale in figures:
        _person(sil_draw, W * cx, H * base_y, H * scale, (6, 4, 4, 255))

    # 轮廓光：把剪影向左上偏移一层、模糊后垫在下面，只在左缘漏光
    rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    for cx, base_y, scale in figures:
        _person(rim_draw, W * cx - 9, H * base_y - 5, H * scale, palette["rim"] + (255,))
    rim = rim.filter(ImageFilter.GaussianBlur(int(H * 0.006)))
    rim.putalpha(rim.getchannel("A").point(lambda v: int(v * 0.55)))

    # 人物身后的体积光，把人物从背景里「剥离」出来
    back_glow = radial_glow((W, H), (int(W * 0.24), int(H * 0.55)), W * 0.30, palette["rim"], 60)

    layer = Image.alpha_composite(base, back_glow)
    layer = Image.alpha_composite(layer, rim)
    layer = Image.alpha_composite(layer, sil)

    # 脚下雾气 + 浮尘，遮掉剪影底部的硬边
    fog = vgradient((W, H), [(0.0, (0, 0, 0)), (1.0, palette["haze"])])
    fmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(fmask).rectangle((0, int(H * 0.84), W, H), fill=255)
    fog.putalpha(fmask.filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.55)))
    layer = Image.alpha_composite(layer, fog)

    rng = random.Random(5)
    dust = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dust_draw = ImageDraw.Draw(dust)
    for _ in range(120):
        x, y = rng.randint(0, W), rng.randint(int(H * 0.15), int(H * 0.9))
        r = rng.choice([1, 1, 2, 2, 3])
        alpha = rng.randint(30, 110)
        dust_draw.ellipse((x - r, y - r, x + r, y + r), fill=palette["rim"] + (alpha,))
    return Image.alpha_composite(layer, dust)


def poster_layer(palette, count=5):
    """Mode A2：一叠微旋转、互相遮挡的竖版海报，向右侧渐隐。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(vgradient((W, H), palette["sky"]), (0, 0))
    glow = radial_glow((W, H), (int(W * 0.26), int(H * 0.42)), W * 0.36, palette["sun"], 110)
    layer = Image.alpha_composite(layer, glow)

    card_h = int(H * 0.66)
    card_w = int(card_h * 2 / 3)
    rng = random.Random(11)
    accents = palette["accents"]
    for index in range(count):
        progress = index / max(1, count - 1)
        cx = int(W * (0.085 + progress * 0.350))
        cy = int(H * (0.475 + math.sin(progress * math.pi) * 0.010))
        accent = accents[index % len(accents)]

        art = vgradient(
            (card_w, card_h),
            [(0.0, mix(accent, (255, 250, 240), 0.30)), (0.45, accent), (1.0, mix(accent, (0, 0, 0), 0.72))],
        ).convert("RGBA")
        art_draw = ImageDraw.Draw(art)
        art_draw.polygon(
            [(0, card_h), (card_w * 0.58, card_h * 0.10), (card_w * 1.05, card_h * 0.26), (card_w * 0.52, card_h)],
            fill=mix(accent, (255, 245, 225), 0.55) + (150,),
        )
        _person(art_draw, card_w * 0.50, card_h * 0.96, card_h * 0.66, mix(accent, (0, 0, 0), 0.84) + (240,))
        art_draw.rectangle((0, card_h * 0.895, card_w, card_h), fill=(10, 8, 8, 235))
        art_draw.text(
            (card_w * 0.08, card_h * 0.912),
            f"TITLE {index + 1:02d}",
            font=font(FONT_LATIN, int(card_h * 0.030)),
            fill=mix(accent, (255, 255, 255), 0.65),
        )

        mask = Image.new("L", art.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=int(card_w * 0.05), fill=255)
        card = art.copy()
        card.putalpha(mask)

        shadow = Image.new("RGBA", (card_w + 160, card_h + 160), (0, 0, 0, 0))
        plate = Image.new("L", shadow.size, 0)
        ImageDraw.Draw(plate).rounded_rectangle(
            (80, 80, 80 + card_w, 80 + card_h), radius=int(card_w * 0.05), fill=200
        )
        shadow.putalpha(plate.filter(ImageFilter.GaussianBlur(28)))

        angle = rng.uniform(-3.0, 2.0)
        rotated = card.rotate(angle, resample=Image.BICUBIC, expand=True)
        rot_shadow = shadow.rotate(angle, resample=Image.BICUBIC, expand=True)
        layer.alpha_composite(rot_shadow, (cx - rotated.width // 2 - 60, cy - rotated.height // 2 - 52))
        layer.alpha_composite(rotated, (cx - rotated.width // 2, cy - rotated.height // 2))

    left_fade = side_scrim((W, H), 0.0, (0, 0, 0), 150)
    left_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(left_mask).rectangle((0, 0, int(W * 0.07), H), fill=255)
    left_fade.putalpha(left_mask.filter(ImageFilter.GaussianBlur(60)))
    layer = Image.alpha_composite(layer, left_fade)

    bottom = vgradient((W, H), [(0.0, (0, 0, 0)), (1.0, palette["ground"])])
    bmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(bmask).rectangle((0, int(H * 0.70), W, H), fill=255)
    bottom.putalpha(bmask.filter(ImageFilter.GaussianBlur(50)).point(lambda v: int(v * 0.9)))
    return Image.alpha_composite(layer, bottom)


# ---------------------------------------------------------------- 版式参数

# 每个元素独立定位：x / y 是画布比例，align 决定锚点含义。
# 默认值 = 参考图的版式；改任意一项就能挪动单个元素，互不影响。
DEFAULT_LAYOUT = {
    "scrim": {"enabled": True, "start": 0.44, "ramp": 0.17, "strength": 250},
    "title": {
        "x": 0.762, "y": 0.330, "size": 0.175,
        "tracking": 0.055, "align": "center", "max_width": 0.330,
    },
    "divider": {
        "width": 0.300, "gap": 0.050, "thickness": 0.0022,
        "flare_pos": 0.5, "flare_strength": 175, "align": "inherit",
        "color": "", "flare_color": "",
    },
    "subtitle": {
        "size_ratio": 0.225, "tracking": 0.46, "gap": 0.028,
        "max_width": 0.330, "align": "inherit",
    },
    "slogan_cn": {"size_ratio": 0.215, "gap": 0.030, "spacing": 0.85, "align": "inherit"},
    "slogan_en": {"size_ratio": 0.46, "tracking": 0.30, "gap": 0.026, "max_width": 0.330, "align": "inherit"},
    "tags": {"x": 0.042, "y": 0.918, "size": 0.0235, "tracking": 0.22, "align": "left"},
    "watermark": {
        "enabled": True, "text": "", "x": 0.985, "y": 0.500, "size": 0.520,
        "max_height": 0.840, "line_gap": 0.04, "opacity": 0.120, "rotate": -6,
    },
    "frame": {"radius": 0.040, "border_width": 0.0016, "glow": 1.0},
}


def _color(value, fallback):
    """颜色参数：空串 = 用配色方案里的默认值。"""
    text = str(value or "").strip()
    if not text:
        return tuple(fallback)
    try:
        return tuple(ImageColor.getrgb(text)[:3])
    except Exception:
        return tuple(fallback)


def merge_layout(**overrides):
    """浅合并布局参数（嵌套字典按层合并）。"""
    layout = deepcopy(DEFAULT_LAYOUT)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(layout.get(key), dict):
            layout[key].update(value)
        else:
            layout[key] = value
    return layout


# ---------------------------------------------------------------- 渲染


def render_banner(base: Image.Image, palette: dict, copy: dict, layout: dict) -> Image.Image:
    """把素材图 + 文案 + 版式参数合成分类横幅。

    自下而上：素材 → （可选）右侧压暗 → 溢光 → 调色 → 暗角/颗粒
    → 标题 / 光带 / 英文名 / 标语 → 标签 → 水印 → 圆角边框。
    """
    width, height = W, H
    frame = base.convert("RGBA").resize((width, height), Image.LANCZOS)

    if layout["scrim"]["enabled"]:
        frame = Image.alpha_composite(
            frame,
            side_scrim(
                (width, height),
                layout["scrim"]["start"], palette["scrim"],
                layout["scrim"]["strength"], layout["scrim"]["ramp"],
            ),
        )
        glow = radial_glow(
            (width, height),
            (int(width * layout["scrim"]["start"] * 0.92), int(height * 0.42)),
            width * 0.30, palette["glow"], 80,
        )
        if glow:
            frame = Image.alpha_composite(frame, glow)

    # 底部压暗：给标签条一个落脚点（不依赖左右分区，整幅底部都压）
    scrim = vgradient((width, height), [(0.0, (0, 0, 0)), (1.0, palette["scrim"])])
    smask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(smask).rectangle((0, int(height * 0.76), width, height), fill=255)
    scrim.putalpha(smask.filter(ImageFilter.GaussianBlur(72)).point(lambda v: int(v * 0.8)))
    frame = Image.alpha_composite(frame, scrim)

    frame = grade(frame, palette["grade"], palette["grade_strength"])
    frame = Image.alpha_composite(frame, vignette((width, height), 130))
    frame = grain(frame, 14)

    draw = ImageDraw.Draw(frame)

    # ---- 标题块：标题自身定位，后续元素跟随它的锚点与对齐方式
    title_spec = layout["title"]
    anchor = int(width * title_spec["x"])
    align = title_spec["align"]
    title_size = fit_size(
        copy["title"], FONT_TITLE, int(height * title_spec["size"]),
        int(width * title_spec["max_width"]), title_spec["tracking"],
    )
    title_font = font(FONT_TITLE, title_size)
    tracking = int(title_size * title_spec["tracking"])
    y = int(height * title_spec["y"])

    title_layer = metal_text(
        (width, height), copy["title"], title_font, tracking, anchor, y,
        palette, align=align, sheen=0.5, glow=0.20,
    )
    if title_layer is not None:
        shadow = title_layer.getchannel("A").filter(ImageFilter.GaussianBlur(int(height * 0.014)))
        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_layer.putalpha(shadow.point(lambda v: int(v * 0.5)))
        frame = Image.alpha_composite(frame, ImageChops.offset(shadow_layer, 0, int(height * 0.012)))
        frame = Image.alpha_composite(frame, title_layer)

    # ---- 光带：宽度/位置独立，高光点按 flare_pos 落在光带自身长度上
    divider = layout["divider"]
    line_align = align if divider["align"] == "inherit" else divider["align"]
    line_y = int(y + title_size * 0.92 + height * divider["gap"])
    line_w = int(width * divider["width"])
    line_x0 = int(align_x(anchor, line_w, line_align))
    line_thickness = max(1, int(height * divider["thickness"]))

    line_mask = Image.new("L", (width, height), 0)
    line_draw = ImageDraw.Draw(line_mask)
    for x in range(line_x0, line_x0 + line_w):
        t = (x - line_x0) / max(1, line_w - 1)
        alpha = int(150 * (1.0 - smooth(t)) + 26)
        line_draw.line([(x, line_y), (x, line_y + line_thickness)], fill=alpha)
    line_layer = Image.new("RGBA", (width, height), _color(divider.get("color"), palette["line"]) + (0,))
    line_layer.putalpha(line_mask)
    frame = Image.alpha_composite(frame, line_layer)

    flare_color = _color(divider.get("flare_color"), palette["flare"])
    flare_x = line_x0 + int(line_w * divider["flare_pos"])
    flare = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(flare).ellipse(
        (flare_x - int(width * 0.075), line_y - int(height * 0.010),
         flare_x + int(width * 0.075), line_y + int(height * 0.010)),
        fill=flare_color + (int(divider["flare_strength"]),),
    )
    frame = Image.alpha_composite(frame, flare.filter(ImageFilter.GaussianBlur(int(height * 0.008))))
    draw = ImageDraw.Draw(frame)
    draw.line(
        [(flare_x - int(width * 0.028), line_y), (flare_x + int(width * 0.028), line_y)],
        fill=(255, 252, 240, 225), width=max(2, line_thickness),
    )

    # ---- 英文名（全大写 + 宽字距）
    sub = layout["subtitle"]
    sub_align = align if sub["align"] == "inherit" else sub["align"]
    en_size = fit_size(
        copy["en"].upper(), FONT_LIGHT, int(title_size * sub["size_ratio"]),
        int(width * sub["max_width"]), sub["tracking"],
    )
    en_font = font(FONT_LIGHT, en_size)
    en_tracking = int(en_size * sub["tracking"])
    en_y = line_y + int(height * sub["gap"])
    draw_tracked(draw, copy["en"].upper(), anchor, en_y, en_font, palette["en"], en_tracking, sub_align)

    # ---- 中文标语（两段，大间距）
    cn = layout["slogan_cn"]
    cn_align = align if cn["align"] == "inherit" else cn["align"]
    cn_size = int(title_size * cn["size_ratio"])
    cn_font = font(FONT_TEXT, cn_size)
    gap = int(cn_size * cn["spacing"])
    parts = copy["slogan_cn"]
    block_w = sum(cn_font.getlength(part) for part in parts) + gap * max(0, len(parts) - 1)
    if block_w > width * sub["max_width"]:
        cn_size = max(14, int(cn_size * width * sub["max_width"] / block_w))
        cn_font = font(FONT_TEXT, cn_size)
        gap = int(cn_size * cn["spacing"])
        block_w = sum(cn_font.getlength(part) for part in parts) + gap * max(0, len(parts) - 1)
    cn_y = en_y + int(en_size * 1.45 + height * cn["gap"])
    x = align_x(anchor, block_w, cn_align)
    for index, part in enumerate(parts):
        draw.text((x, cn_y), part, font=cn_font, fill=palette["slogan_cn"])
        x += cn_font.getlength(part) + (gap if index < len(parts) - 1 else 0)

    # ---- 英文标语
    se = layout["slogan_en"]
    se_align = align if se["align"] == "inherit" else se["align"]
    se_size = fit_size(copy["slogan_en"], FONT_TEXT, int(cn_size * se["size_ratio"]), int(width * se["max_width"]), se["tracking"])
    se_font = font(FONT_TEXT, se_size)
    se_tracking = int(se_size * se["tracking"])
    se_y = cn_y + int(cn_size * 1.42 + height * se["gap"])
    draw_tracked(draw, copy["slogan_en"], anchor, se_y, se_font, palette["slogan_en"], se_tracking, se_align)

    # ---- 题材标签：独立定位，默认左下
    tags = layout["tags"]
    tag_size = int(height * tags["size"])
    tag_tracking = int(tag_size * tags["tracking"])
    tag_font = font(FONT_TEXT, tag_size)
    sep = "｜"
    total = sum(tracked_width(tag, tag_font, tag_tracking) for tag in copy["tags"])
    total += (
        tag_size * 0.55 + tag_font.getlength(sep) + tag_tracking + tag_size * 1.1
    ) * max(0, len(copy["tags"]) - 1)
    if total > width * 0.46:
        tag_size = max(11, int(tag_size * width * 0.46 / total))
        tag_tracking = int(tag_size * 0.22)
        tag_font = font(FONT_TEXT, tag_size)
        total = sum(tracked_width(tag, tag_font, tag_tracking) for tag in copy["tags"])
        total += (
            tag_size * 0.55 + tag_font.getlength(sep) + tag_tracking + tag_size * 1.1
        ) * max(0, len(copy["tags"]) - 1)
    tag_x = align_x(int(width * tags["x"]), total, tags["align"])
    tag_y = int(height * tags["y"])
    for index, tag in enumerate(copy["tags"]):
        draw_tracked(draw, tag, tag_x, tag_y, tag_font, palette["tag"], tag_tracking, "left")
        tag_x += tracked_width(tag, tag_font, tag_tracking)
        if index < len(copy["tags"]) - 1:
            draw_tracked(draw, sep, tag_x + tag_size * 0.55, tag_y, tag_font, palette["tag_sep"], tag_tracking, "left")
            tag_x += tag_font.getlength(sep) + tag_tracking + tag_size * 1.1

    # ---- 书法水印：默认整段标题竖排、右侧出血；字号随字数自动收缩，可整块关闭
    mark = layout["watermark"]
    if mark.get("enabled", True):
        mark_text = str(mark.get("text") or copy["title"]).strip()
        chars = [char for char in mark_text if not char.isspace()]
        if chars:
            base_size = int(height * mark["size"])
            available = height * mark["max_height"]
            step = available / max(1, len(chars))
            per = max(12, int(min(base_size, step * 0.92)))
            mark_font = font(FONT_BRUSH, per)
            line_gap = int(per * mark["line_gap"])
            col_w = max(mark_font.getlength(char) for char in chars)
            total_h = per * len(chars) + line_gap * (len(chars) - 1)
            canvas_w = int(col_w * 1.7)
            mark_img = Image.new(
                "RGBA", (canvas_w, int(total_h + per * 0.5)), (0, 0, 0, 0)
            )
            mark_draw = ImageDraw.Draw(mark_img)
            for index, char in enumerate(chars):
                char_w = mark_font.getlength(char)
                mark_draw.text(
                    ((canvas_w - char_w) / 2, index * (per + line_gap)),
                    char, font=mark_font, fill=palette["watermark"] + (255,),
                )
            mark_img = mark_img.rotate(mark["rotate"], resample=Image.BICUBIC, expand=True)
            mark_img.putalpha(mark_img.getchannel("A").point(lambda v: int(v * mark["opacity"])))
            frame.alpha_composite(
                mark_img,
                (int(width * mark["x"] - mark_img.width / 2), int(height * mark["y"] - mark_img.height / 2)),
            )

    # ---- 圆角 + 双层描边
    frame_spec = layout["frame"]
    radius = int(min(width, height) * frame_spec["radius"])
    card_mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(card_mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    frame.putalpha(card_mask)
    frame = Image.alpha_composite(Image.new("RGBA", (width, height), palette["outside"] + (255,)), frame)

    inset = max(2, int(height * 0.0035))
    border_w = max(1, int(height * frame_spec["border_width"]))
    edge = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        (inset, inset, width - 1 - inset, height - 1 - inset),
        radius=max(2, radius - inset),
        outline=palette["border"] + (170,), width=border_w,
    )
    frame = Image.alpha_composite(frame, edge)

    if frame_spec["glow"] > 0:
        glow_line = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(glow_line).rounded_rectangle(
            (inset, inset, width - 1 - inset, height - 1 - inset),
            radius=max(2, radius - inset),
            outline=palette["border"] + (110,), width=max(2, border_w * 2),
        )
        glow_line = glow_line.filter(ImageFilter.GaussianBlur(int(height * 0.006)))
        glow_line.putalpha(glow_line.getchannel("A").point(lambda v: int(v * frame_spec["glow"])))
        frame = Image.alpha_composite(frame, glow_line)

    return frame.convert("RGB")


# ---------------------------------------------------------------- 三套配色

WARM = {
    "sky": [(0.0, (10, 8, 9)), (0.38, (58, 28, 16)), (0.66, (168, 92, 38)), (0.82, (238, 166, 88)), (1.0, (120, 62, 26))],
    "sun": (255, 202, 132),
    "sun_x": 0.27,
    "sun_y": 0.66,
    "ridges": [
        (0.545, (126, 78, 48), 14),
        (0.615, (94, 54, 32), 20),
        (0.700, (56, 30, 20), 26),
        (0.860, (26, 14, 10), 30),
    ],
    "haze": (255, 196, 140),
    "ground": (18, 10, 8),
    "rim": (255, 208, 150),
    "accents": [(196, 104, 44), (128, 42, 26), (222, 148, 74), (86, 52, 40), (168, 66, 34)],
    "scrim": (7, 6, 6),
    "glow": (176, 116, 58),
    "grade": (118, 74, 36),
    "grade_strength": 0.14,
    "metal": [(0.0, (255, 248, 224)), (0.38, (240, 210, 154)), (0.60, (188, 138, 78)), (0.78, (226, 186, 128)), (1.0, (246, 220, 172))],
    "line": (196, 164, 112),
    "flare": (255, 232, 190),
    "en": (214, 196, 162),
    "slogan_cn": (236, 226, 208),
    "slogan_en": (158, 142, 118),
    "tag": (216, 204, 184),
    "tag_sep": (132, 118, 100),
    "watermark": (255, 232, 192),
    "border": (206, 172, 118),
    "outside": (5, 5, 6),
}

COOL = {
    "sky": [(0.0, (6, 10, 26)), (0.40, (18, 28, 74)), (0.66, (58, 74, 146)), (0.82, (132, 156, 212)), (1.0, (52, 66, 118))],
    "sun": (216, 232, 255),
    "sun_x": 0.20,
    "sun_y": 0.68,
    "ridges": [
        (0.545, (62, 82, 142), 16),
        (0.615, (40, 56, 108), 22),
        (0.700, (24, 34, 72), 28),
        (0.860, (12, 16, 38), 32),
    ],
    "haze": (178, 200, 246),
    "ground": (8, 12, 28),
    "rim": (212, 232, 255),
    "accents": [(58, 84, 168), (28, 44, 104), (116, 148, 214), (34, 60, 128), (78, 108, 188)],
    "scrim": (6, 8, 16),
    "glow": (96, 128, 200),
    "grade": (36, 54, 108),
    "grade_strength": 0.16,
    "metal": [(0.0, (250, 253, 255)), (0.38, (218, 232, 250)), (0.60, (146, 174, 220)), (0.80, (204, 224, 250)), (1.0, (238, 246, 255))],
    "line": (158, 188, 232),
    "flare": (232, 244, 255),
    "en": (198, 216, 242),
    "slogan_cn": (228, 238, 252),
    "slogan_en": (138, 158, 190),
    "tag": (204, 218, 238),
    "tag_sep": (116, 132, 160),
    "watermark": (222, 238, 255),
    "border": (144, 182, 232),
    "outside": (4, 6, 11),
}

CRIMSON = {
    "sky": [(0.0, (10, 5, 6)), (0.36, (62, 12, 10)), (0.64, (148, 32, 20)), (0.80, (216, 84, 38)), (1.0, (104, 24, 14))],
    "sun": (255, 158, 100),
    "sun_x": 0.24,
    "sun_y": 0.64,
    "ridges": [
        (0.545, (134, 44, 28), 14),
        (0.615, (96, 26, 18), 20),
        (0.700, (52, 12, 10), 26),
        (0.860, (22, 6, 6), 30),
    ],
    "haze": (255, 168, 112),
    "ground": (16, 6, 6),
    "rim": (255, 178, 128),
    "accents": [(178, 42, 30), (110, 22, 20), (222, 96, 52), (78, 26, 24), (150, 54, 34)],
    "scrim": (8, 5, 5),
    "glow": (178, 74, 40),
    "grade": (112, 34, 22),
    "grade_strength": 0.16,
    "metal": [(0.0, (255, 242, 222)), (0.38, (242, 198, 158)), (0.60, (188, 108, 74)), (0.80, (232, 176, 136)), (1.0, (250, 214, 180))],
    "line": (212, 156, 112),
    "flare": (255, 218, 176),
    "en": (226, 196, 168),
    "slogan_cn": (244, 230, 214),
    "slogan_en": (168, 140, 118),
    "tag": (228, 210, 192),
    "tag_sep": (142, 118, 100),
    "watermark": (255, 220, 188),
    "border": (216, 150, 108),
    "outside": (6, 4, 4),
}

COPY_WARM = {
    "title": "国产剧",
    "en": "CHINESE SERIES",
    "slogan_cn": ["好故事", "好人生"],
    "slogan_en": "GOOD STORIES, GOOD LIFE",
    "tags": ["爱情", "都市", "悬疑", "剧情", "家庭"],
}
COPY_COOL = {
    "title": "日番动画",
    "en": "JAPANESE ANIMATION",
    "slogan_cn": ["梦想·指引", "遇见未来"],
    "slogan_en": "DREAMS GUIDE US TO THE FUTURE",
    "tags": ["青春", "奇幻", "冒险", "成长", "治愈"],
}
COPY_CRIMSON = {
    "title": "华语电影",
    "en": "CHINESE FILMS",
    "slogan_cn": ["故事无界", "经典永恒"],
    "slogan_en": "STORIES WITHOUT BORDERS, CLASSICS FOREVER",
    "tags": ["动作", "武侠", "奇幻", "剧情", "历史"],
}


def main() -> None:
    # 参考图原版式（左对齐）——只作为可选预设保留
    left_aligned = merge_layout(
        title={"x": 0.575, "y": 0.335, "size": 0.190, "align": "left", "max_width": 0.365},
        divider={"width": 0.355, "gap": 0.052},
        subtitle={"tracking": 0.50, "max_width": 0.365},
    )

    # 长标题压力测试：标题 5 字，水印跟随整段标题、字号按字数自动收缩
    long_title = dict(COPY_WARM, title="国产连续剧", en="CHINESE DRAMA SERIES")

    jobs = [
        ("category_banner_a_library.jpg", WARM, COPY_WARM, scene_layer(WARM), DEFAULT_LAYOUT),
        ("category_banner_b_library_cool.jpg", COOL, COPY_COOL, scene_layer(COOL), DEFAULT_LAYOUT),
        ("category_banner_c_posters.jpg", CRIMSON, COPY_CRIMSON, poster_layer(CRIMSON), DEFAULT_LAYOUT),
        ("category_banner_d_keyart_left.jpg", WARM, COPY_WARM, keyart_layer(WARM), left_aligned),
        ("category_banner_e_keyart_center.jpg", WARM, COPY_WARM, keyart_layer(WARM), DEFAULT_LAYOUT),
        ("category_banner_f_long_title.jpg", WARM, long_title, keyart_layer(WARM), DEFAULT_LAYOUT),
    ]
    for filename, palette, copy, base, layout in jobs:
        image = render_banner(base, palette, copy, layout)
        image.resize((1280, 720), Image.LANCZOS).save(OUT_DIR / filename, quality=90, optimize=True)
        thumb = image.copy()
        thumb.thumbnail((640, 640), Image.LANCZOS)
        thumb.save(OUT_DIR / filename.replace(".jpg", "_thumb.jpg"), quality=86, optimize=True)
        print("written", OUT_DIR / filename)


if __name__ == "__main__":
    main()
