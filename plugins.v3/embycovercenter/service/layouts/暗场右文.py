"""暗场右文：左侧「亮场」+ 右侧压暗文字带的电影海报版式。

**不需要用户自备母版图**：场景取自媒体库自己的背景图（没有背景图时回退首张海报），
左侧保持清晰、右侧渐变压暗成文字带；再用羽化 / 调色 / 暗角 / 颗粒把
不同来源的素材统一成同一种画面质感（对应「左亮右暗 + 右侧文字」的构图语法）。

关键设计：清晰区与失焦基底**取自同一张原图的同一取景**，两者逐像素对齐，
所以横向过渡的是「清晰度」而不是「画面内容」——观感像一张景深照片，
不会出现两块拼图错位的接缝。

分层顺序（自下而上）：
1. 基底：整张背景重度模糊 + 压暗，作为「失焦的远场」；
2. 清晰区：同一取景的清晰版本，从 hero_width_percent 起按 feather_right 淡出；
3. 暗场：从 darken_start_percent 开始向右渐变压暗到 tint_color；
4. 光晕：在清晰区右缘打一团主色光，让亮场「溢」进暗场，弱化接缝；
5. 暗角 + 颗粒：压住边角、统一噪点质感；
6. 文字：右侧竖排文字块（标题 / 装饰线 / 英文名）。
"""
from PIL import Image, ImageDraw, ImageOps, ImageEnhance, ImageColor, ImageFilter, ImageStat
import math
import random


# ---------------------------------------------------------------- 小工具

def _clamp(value, low, high, fallback):
    """把配置值（可能是字符串）夹到区间内；非法时用 fallback。"""
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
        return fallback


def _mix(color, other, ratio):
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(round(a * (1 - ratio) + b * ratio)) for a, b in zip(color, other))


def _smooth(t):
    """smoothstep：两端导数为 0，羽化不会出现可见的硬边。"""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _fade_mask(size, solid_until=0.0, fade_to=1.0, top=0.0, bottom=0.0):
    """清晰度衰减遮罩：``solid_until`` 之前全实，到 ``fade_to`` 平滑淡为 0。

    亮场与基底取自**同一取景**，只有清晰度沿横向衰减，接缝处画面内容完全对齐，
    观感是「一张照片的景深过渡」，而不是两块拼图。
    """
    width = max(1, int(size[0]))
    height = max(1, int(size[1]))
    solid_x = max(0, min(width, int(width * max(0.0, min(1.0, solid_until)))))
    fade_x = max(solid_x + 1, min(width, int(width * max(0.0, min(1.0, fade_to)))))

    columns = bytearray(b"\xff") * width
    span = float(fade_x - solid_x)
    for x in range(solid_x, fade_x):
        columns[x] = int(255 * (1.0 - _smooth((x - solid_x) / span)))
    for x in range(fade_x, width):
        columns[x] = 0

    rows = bytearray(b"\xff") * height
    top_h = min(height, int(height * max(0.0, min(1.0, top))))
    for y in range(top_h):
        rows[y] = int(255 * _smooth(y / float(top_h)))
    bottom_h = min(height, int(height * max(0.0, min(1.0, bottom))))
    for index in range(bottom_h):
        y = height - 1 - index
        rows[y] = min(rows[y], int(255 * _smooth(index / float(bottom_h))))

    # 行系数只有 256 种取值，缓存缩放后的整行，避免逐像素做除法。
    cache = {}
    data = bytearray(width * height)
    for y in range(height):
        factor = rows[y]
        if factor == 255:
            data[y * width:(y + 1) * width] = columns
            continue
        line = cache.get(factor)
        if line is None:
            line = bytes((value * factor) // 255 for value in columns)
            cache[factor] = line
        data[y * width:(y + 1) * width] = line
    return Image.frombytes("L", (width, height), bytes(data))


def _dominant_color(image, fallback=(24, 34, 52)):
    """取画面主色：兼顾占比、饱和度与亮度，避免选中大片灰黑背景。"""
    try:
        small = image.convert("RGB").resize((32, 32), Image.BILINEAR)
        quantized = small.quantize(colors=8, method=Image.MEDIANCUT)
        palette = quantized.getpalette() or []
        counts = quantized.getcolors() or []
        total = sum(count for count, _ in counts) or 1
        best, best_score = None, -1.0
        for count, index in counts:
            offset = index * 3
            if offset + 2 >= len(palette):
                continue
            red, green, blue = palette[offset:offset + 3]
            saturation = (max(red, green, blue) - min(red, green, blue)) / 255.0
            score = (count / float(total)) * (0.35 + saturation) * (0.4 + max(red, green, blue) / 255.0)
            if score > best_score:
                best, best_score = (red, green, blue), score
        return best or fallback
    except Exception:
        return fallback


def _radial_glow(size, center, radius, color, strength):
    """径向光晕（中心最亮、向外平滑衰减），用于亮场向暗场的溢光。"""
    if strength <= 0 or radius <= 0:
        return None
    width, height = int(size[0]), int(size[1])
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = center
    steps = 48
    for index in range(steps, 0, -1):
        t = index / float(steps)
        alpha = int(strength * (1.0 - t) ** 2)
        r = max(1.0, radius * t)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)
    layer = Image.new("RGBA", (width, height), tuple(color) + (0,))
    layer.putalpha(mask)
    return layer


def _side_gradient(size, start_x, color, strength):
    """从 start_x 向右渐变压暗（纯色 + 渐增 alpha）。"""
    width, height = int(size[0]), int(size[1])
    if strength <= 0:
        return None
    start_x = max(0, min(width, int(start_x)))
    span = max(1, width - start_x)
    alpha = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(alpha)
    for x in range(start_x, width):
        value = int(strength * _smooth((x - start_x) / float(span)))
        if value:
            draw.line([(x, 0), (x, height)], fill=value)
    layer = Image.new("RGBA", (width, height), tuple(color) + (0,))
    layer.putalpha(alpha)
    return layer


def _vignette(size, strength, power=2.4):
    """四角压暗。"""
    if strength <= 0:
        return None
    width, height = int(size[0]), int(size[1])
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = width / 2.0, height / 2.0
    max_r = math.hypot(cx, cy)
    steps = 64
    for index in range(steps, 0, -1):
        t = index / float(steps)
        alpha = int(strength * (t ** power))
        r = max_r * t
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layer.putalpha(mask)
    return layer


def _grain(image, amount):
    """叠一层高斯噪点，把不同来源的素材「统一到同一种颗粒感」。

    噪点按画布尺寸固定种子生成：同一份配置反复渲染的结果完全一致，
    否则动态封面逐帧都会换一套噪点，画面会「沙沙」地闪。
    """
    ratio = max(0.0, min(1.0, amount / 100.0)) * 0.18
    if ratio <= 0:
        return image
    width, height = image.size
    try:
        rng = random.Random((width << 20) ^ height ^ 0x9E3779B9)
        noise = Image.frombytes("L", (width, height), rng.randbytes(width * height))
    except Exception:
        return image
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    mixed = Image.blend(image.convert("RGB"), noise_rgb, ratio)
    return mixed.convert("RGBA")


# ---------------------------------------------------------------- schema

def get_schema():
    return [
        {
            "group": "资源与内容",
            "items": [
                {"key": "poster_count", "label": "兜底海报数量（无背景图时取首张当场景）", "type": "range",
                 "min": 0, "max": 12, "default": 2},
                {"key": "backdrop_count", "label": "获取背景数量", "type": "range", "min": 0, "max": 4, "default": 1},
                {"key": "auto_mirror", "label": "自动镜像成左亮右暗", "type": "boolean", "default": True},
                {"key": "title", "label": "主标题内容", "type": "text", "default": ""},
                {"key": "subtitle", "label": "副标题内容（英文名）", "type": "text", "default": ""},
            ],
        },
        {
            "group": "亮场（左侧场景）",
            "items": [
                {"key": "hero_width_percent", "label": "清晰区宽度 %（此点前完全清晰）", "type": "range",
                 "min": 10, "max": 95, "default": 62},
                {"key": "scene_brightness", "label": "清晰区亮度", "type": "range", "min": 0.2, "max": 1.4,
                 "step": 0.05, "default": 0.95},
                {"key": "scene_contrast", "label": "清晰区对比度", "type": "range", "min": 0.6, "max": 1.6,
                 "step": 0.05, "default": 1.06},
                {"key": "scene_saturation", "label": "清晰区饱和度", "type": "range", "min": 0.0, "max": 2.0,
                 "step": 0.05, "default": 1.08},
                {"key": "scene_blur", "label": "清晰区模糊（0=完全清晰）", "type": "range", "min": 0, "max": 60, "default": 0},
                {"key": "feather_right", "label": "向右淡出宽度 %", "type": "range", "min": 1, "max": 60, "default": 20},
                {"key": "feather_top", "label": "上缘羽化 %", "type": "range", "min": 0, "max": 40, "default": 6},
                {"key": "feather_bottom", "label": "下缘羽化 %", "type": "range", "min": 0, "max": 40, "default": 8},
            ],
        },
        {
            "group": "暗场与氛围",
            "items": [
                {"key": "base_blur", "label": "基底模糊", "type": "range", "min": 0, "max": 100, "default": 44},
                {"key": "base_brightness", "label": "基底亮度", "type": "range", "min": 0.05, "max": 1.0,
                 "step": 0.05, "default": 0.40},
                {"key": "tint_color", "label": "暗场主色", "type": "color", "default": "#070b12"},
                {"key": "darken_start_percent", "label": "压暗起点 %", "type": "range", "min": 20, "max": 90, "default": 44},
                {"key": "darken_strength", "label": "压暗强度", "type": "range", "min": 0, "max": 255, "default": 205},
                {"key": "glow_strength", "label": "溢光强度", "type": "range", "min": 0, "max": 255, "default": 70},
                {"key": "glow_radius_percent", "label": "溢光半径 %", "type": "range", "min": 10, "max": 100, "default": 46},
                {"key": "vignette_strength", "label": "暗角强度", "type": "range", "min": 0, "max": 255, "default": 110},
                {"key": "grain", "label": "颗粒强度", "type": "range", "min": 0, "max": 100, "default": 12},
            ],
        },
        {
            "group": "文字排版",
            "items": [
                {"key": "font_title", "label": "主标题字体", "type": "font", "default": "default.ttf"},
                {"key": "title_size", "label": "主标题字号", "type": "range", "min": 40, "max": 300, "default": 132},
                {"key": "title_color", "label": "主标题颜色", "type": "color", "default": "#FFFFFF"},
                {"key": "font_subtitle", "label": "副标题字体", "type": "font", "default": "default.ttf"},
                {"key": "subtitle_size", "label": "副标题字号", "type": "range", "min": 20, "max": 160, "default": 46},
                {"key": "subtitle_color", "label": "副标题颜色", "type": "color", "default": "#C9D2E0"},
                {"key": "text_align", "label": "文字对齐方式", "type": "select", "options": [
                    {"label": "左对齐", "value": "left"},
                    {"label": "居中对齐", "value": "center"},
                    {"label": "右对齐", "value": "right"},
                ], "default": "left"},
                {"key": "text_left_percent", "label": "文字左边界 %", "type": "range", "min": 0, "max": 95, "default": 64},
                {"key": "text_top_percent", "label": "文字顶部 %", "type": "range", "min": 0, "max": 95, "default": 38},
                {"key": "text_width_percent", "label": "文字最大宽度 %", "type": "range", "min": 10, "max": 60, "default": 30},
                {"key": "line_color", "label": "装饰线颜色", "type": "color", "default": "#7F8FA6"},
                {"key": "line_width", "label": "装饰线粗细", "type": "range", "min": 0, "max": 20, "default": 3},
                {"key": "line_length_percent", "label": "装饰线长度 %（占文字宽）", "type": "range",
                 "min": 5, "max": 100, "default": 30},
                {"key": "gap_1", "label": "标题与装饰线间距", "type": "range", "min": 0, "max": 200, "default": 26},
                {"key": "gap_2", "label": "装饰线与副标间距", "type": "range", "min": 0, "max": 200, "default": 26},
            ],
        },
    ]


# ---------------------------------------------------------------- 渲染

def _pick_source(ctx, assets, config=None):
    """选场景素材：优先媒体库背景图，没有就用首张海报。

    基底与清晰区**共用这一张原图**，是「同一取景、只有清晰度不同」的前提。
    ``auto_mirror`` 打开时，若画面右侧比左侧亮，就水平镜像——
    参考版式的构图语法是「左亮右暗」，暗调素材不翻转会把文字压在亮场上。
    """
    url = str(assets.get("bg_url") or "").strip()
    if not url:
        posters = [item for item in (assets.get("posters") or []) if item]
        url = posters[0] if posters else ""
    if not url:
        return None
    image = ctx.download_img(url)
    if image is None:
        return None
    if _auto_mirror_enabled(config) and _is_right_brighter(image):
        image = ImageOps.mirror(image)
    return image


def _auto_mirror_enabled(config) -> bool:
    if not config:
        return True
    value = config.get("auto_mirror")
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(value) if value is not None else True


def _is_right_brighter(image, margin=0.04):
    """画面右侧是否明显比左侧亮（用于决定要不要镜像成「左亮右暗」）。"""
    try:
        gray = image.convert("L")
        width, height = gray.size
        third = max(1, width // 3)
        left = ImageStat.Stat(gray.crop((0, 0, third, height))).mean[0]
        right = ImageStat.Stat(gray.crop((width - third, 0, width, height))).mean[0]
        return right > left * (1.0 + margin)
    except Exception:
        return False


def _build_base(source, config, width, height):
    """基底：同一取景重度模糊 + 压暗，作为失焦的远场。"""
    tint = _rgb(config.get("tint_color"), (7, 11, 18))
    if source is None:
        return Image.new("RGBA", (width, height), tint + (255,))
    base = ImageOps.fit(source.convert("RGBA"), (width, height), method=Image.LANCZOS)
    blur = int(_clamp(config.get("base_blur"), 0, 100, 44))
    if blur > 0:
        base = base.filter(ImageFilter.GaussianBlur(blur))
    base = ImageEnhance.Brightness(base).enhance(_clamp(config.get("base_brightness"), 0.05, 1.0, 0.40))
    wash = Image.new("RGBA", (width, height), tint + (255,))
    return Image.blend(base.convert("RGB"), wash.convert("RGB"), 0.35).convert("RGBA")


def _build_scene(source, config, width, height):
    """亮场：与基底**同一取景**的清晰版本，横向按比例淡出；素材缺失时返回 None。

    关键点：这里和 ``_build_base`` 用同一个 ``ImageOps.fit`` 取景，
    因此两张图逐像素对齐，羽化后只是「清晰度」在过渡，画面内容不会错位。
    """
    if source is None:
        return None
    scene = ImageOps.fit(source.convert("RGBA"), (width, height), method=Image.LANCZOS)
    scene = ImageEnhance.Brightness(scene).enhance(_clamp(config.get("scene_brightness"), 0.2, 1.4, 0.95))
    scene = ImageEnhance.Contrast(scene).enhance(_clamp(config.get("scene_contrast"), 0.6, 1.6, 1.06))
    scene = ImageEnhance.Color(scene).enhance(_clamp(config.get("scene_saturation"), 0.0, 2.0, 1.08))
    blur = int(_clamp(config.get("scene_blur"), 0, 60, 0))
    if blur > 0:
        scene = scene.filter(ImageFilter.GaussianBlur(blur))
    solid_until = _clamp(config.get("hero_width_percent"), 10, 95, 62) / 100.0
    fade_span = _clamp(config.get("feather_right"), 1, 60, 20) / 100.0
    mask = _fade_mask(
        (width, height),
        solid_until=solid_until,
        fade_to=min(1.0, solid_until + fade_span),
        top=_clamp(config.get("feather_top"), 0, 40, 6) / 100.0,
        bottom=_clamp(config.get("feather_bottom"), 0, 40, 8) / 100.0,
    )
    return scene, mask


def _draw_text(ctx, frame, config, fonts, width, height):
    title = str(config.get("title") or "").strip()
    subtitle = str(config.get("subtitle") or "").strip()
    if not title and not subtitle:
        return
    draw = ImageDraw.Draw(frame)
    font_title = fonts.get("font_title") or fonts.get("main")
    font_sub = fonts.get("font_subtitle") or fonts.get("sub") or font_title

    align = str(config.get("text_align") or "left")
    left = int(width * _clamp(config.get("text_left_percent"), 0, 95, 64) / 100.0)
    max_width = max(1, int(width * _clamp(config.get("text_width_percent"), 10, 60, 30) / 100.0))
    if align == "center":
        anchor_x = left + max_width // 2
    elif align == "right":
        anchor_x = left + max_width
    else:
        anchor_x = left
    y = int(height * _clamp(config.get("text_top_percent"), 0, 95, 38) / 100.0)

    if title:
        y = ctx.draw_text_wrapper(
            draw, title, anchor_x, y, font_title, max_width,
            config.get("title_color", "#FFFFFF"), line_spacing=8, align=align,
        )

    # 装饰线：标题与英文名之间的一根细横线，给文字块一个视觉支点。
    line_width = int(_clamp(config.get("line_width"), 0, 20, 3))
    line_length = int(max_width * _clamp(config.get("line_length_percent"), 5, 100, 30) / 100.0)
    if line_width > 0 and line_length > 0:
        y += int(_clamp(config.get("gap_1"), 0, 200, 26))
        if align == "center":
            x0 = anchor_x - line_length // 2
        elif align == "right":
            x0 = anchor_x - line_length
        else:
            x0 = anchor_x
        draw.rectangle([(x0, y), (x0 + line_length, y + line_width)], fill=config.get("line_color", "#7F8FA6"))
        y += int(_clamp(config.get("gap_2"), 0, 200, 26))

    if subtitle:
        ctx.draw_text_wrapper(
            draw, subtitle, anchor_x, y, font_sub, max_width,
            config.get("subtitle_color", "#C9D2E0"), line_spacing=6, align=align,
        )


def render(ctx, bg, config, assets, fonts):
    width, height = bg.size
    source = _pick_source(ctx, assets, config)
    frame = _build_base(source, config, width, height)

    scene = _build_scene(source, config, width, height)
    if scene is not None:
        image, mask = scene
        frame.paste(image, (0, 0), mask)

    # 暗场：从起点向右渐变压暗到主色。
    overlay = _side_gradient(
        (width, height),
        int(width * _clamp(config.get("darken_start_percent"), 20, 90, 44) / 100.0),
        _rgb(config.get("tint_color"), (7, 11, 18)),
        _clamp(config.get("darken_strength"), 0, 255, 205),
    )
    if overlay is not None:
        frame = Image.alpha_composite(frame, overlay)

    # 溢光：在清晰区右缘打一团主色光，弱化清晰区与暗场的接缝。
    glow_strength = _clamp(config.get("glow_strength"), 0, 255, 70)
    if glow_strength > 0:
        hero_edge = _clamp(config.get("hero_width_percent"), 10, 95, 62) / 100.0
        glow = _radial_glow(
            (width, height),
            (int(width * hero_edge * 0.94), int(height * 0.44)),
            width * _clamp(config.get("glow_radius_percent"), 10, 100, 46) / 100.0,
            _mix(_dominant_color(bg), (255, 255, 255), 0.35),
            glow_strength,
        )
        if glow is not None:
            frame = Image.alpha_composite(frame, glow)

    vignette = _vignette((width, height), _clamp(config.get("vignette_strength"), 0, 255, 110))
    if vignette is not None:
        frame = Image.alpha_composite(frame, vignette)

    frame = _grain(frame, _clamp(config.get("grain"), 0, 100, 12))
    _draw_text(ctx, frame, config, fonts, width, height)
    return frame
