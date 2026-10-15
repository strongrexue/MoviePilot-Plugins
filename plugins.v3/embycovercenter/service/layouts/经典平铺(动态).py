from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import math

# =============================================================================
# 辅助函数：圆角处理
# =============================================================================
def add_rounded_corners(im, radius):
    if radius <= 0: return im
    circle = Image.new('L', (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
    alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
    alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
    alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))
    
    if im.mode != 'RGBA': im = im.convert('RGBA')
    im.putalpha(alpha)
    return im

# =============================================================================
# 定义布局参数 (已统一顺序)
# =============================================================================
def get_schema():
    return [
        # --- 1. 核心资源与内容 ---
        {
            "group": "资源与内容",
            "items": [
                {"key": "poster_count", "label": "获取海报数量", "type": "range", "min": 3, "max": 20, "default": 8},
                {"key": "backdrop_count", "label": "获取背景数量", "type": "range", "min": 0, "max": 1, "default": 1},
                {"key": "title", "label": "主标题内容", "type": "text", "default": ""},
                {"key": "subtitle", "label": "副标题内容", "type": "text", "default": ""},
            ]
        },
        # --- 2. 动画设置 (特有) ---
        {
            "group": "动画设置",
            "items": [
                {"key": "enable_animation", "label": "开启无限循环", "type": "boolean", "default": True},
                {"key": "anim_direction", "label": "方向 (1:左往右, -1:右往左)", "type": "select", "options": [
                    {"value": 1, "label": "从左往右 >>>"},
                    {"value": -1, "label": "<<< 从右往左"}
                ], "default": 1},
                {"key": "anim_frames", "label": "动画帧数 (总长)", "type": "range", "min": 20, "max": 300, "default": 90},
                {"key": "anim_duration", "label": "帧间隔 (ms)", "type": "range", "min": 20, "max": 200, "default": 33},
            ]
        },
        # --- 3. 布局与背景 ---
        {
            "group": "布局与背景",
            "items": [
                {"key": "poster_scale", "label": "海报缩放 (建议0.5-0.6)", "type": "range", "min": 0.3, "max": 1.5, "step": 0.05, "default": 0.55},
                {"key": "layout_start_x", "label": "整体起始X坐标", "type": "range", "min": -200, "max": 500, "default": 0},
                {"key": "poster_y_percent", "label": "海报垂直位置 %", "type": "range", "min": 0, "max": 100, "default": 45},
                {"key": "poster_spacing", "label": "海报间距 (px)", "type": "range", "min": 0, "max": 100, "default": 20},
                {"key": "blur_radius", "label": "背景模糊程度", "type": "range", "min": 0, "max": 50, "default": 4},
            ]
        },
        # --- 4. 特效与装饰 ---
        {
            "group": "特效与装饰",
            "items": [
                {"key": "poster_corner_radius", "label": "海报圆角半径", "type": "range", "min": 0, "max": 50, "default": 12},
                {"key": "poster_brightness", "label": "海报亮度 (1.0原图)", "type": "range", "min": 0.1, "max": 1.5, "step": 0.1, "default": 1.0},
                {"key": "poster_shadow_opacity", "label": "海报阴影浓度", "type": "range", "min": 0, "max": 255, "default": 140},
                {"key": "mask_opacity", "label": "黑色遮罩浓度", "type": "range", "min": 0, "max": 255, "default": 200},
            ]
        },
        # --- 5. 字体与排版 (最全设置) ---
        {
            "group": "字体与排版",
            "items": [
                # 主标题
                {"key": "font_title", "label": "主标题字体", "type": "font", "default": "default.ttf"},
                {"key": "title_size", "label": "主标题字号", "type": "range", "min": 30, "max": 200, "default": 80},
                {"key": "title_color", "label": "主标题颜色", "type": "color", "default": "#FFFFFF"},
                
                # 副标题
                {"key": "font_subtitle", "label": "副标题字体", "type": "font", "default": "default.ttf"},
                {"key": "subtitle_size", "label": "副标题字号", "type": "range", "min": 20, "max": 150, "default": 40},
                {"key": "subtitle_color", "label": "副标题颜色", "type": "color", "default": "#DDDDDD"},
                
                # 排版
                {"key": "text_left_percent", "label": "文字左边距 %", "type": "range", "min": 0, "max": 100, "default": 5},
                {"key": "text_top_percent", "label": "文字上边距 %", "type": "range", "min": 0, "max": 100, "default": 75},
                {"key": "text_gap", "label": "标题与副标间距", "type": "range", "min": 0, "max": 100, "default": 20},
            ]
        }
    ]

# =============================================================================
# 素材准备 / 绘制辅助（render 与 render_anim 共用，保证两条路径视觉一致）
# =============================================================================
def _prepare_posters(ctx, config, assets, width, height):
    """一次性下载并处理全部海报（缩放/亮度/圆角）与阴影。

    返回 (items, shadow, geom)；items = [(海报在队列里的基准x, 处理好的图)]。
    动画帧间只有水平偏移变化，海报本体与阴影都不随帧变，只需处理一次。
    """
    poster_urls = list(assets.get('posters') or [])
    count = int(config.get('poster_count', 8))
    if not poster_urls:
        return None
    while len(poster_urls) < count:
        poster_urls.extend(poster_urls)
    poster_urls = poster_urls[:count]

    scale = float(config.get('poster_scale', 0.55))
    base_h, base_w = 550, 366
    target_h, target_w = int(base_h * scale), int(base_w * scale)
    spacing = int(config.get('poster_spacing', 20))
    radius = int(config.get('poster_corner_radius', 12))
    unit_width = target_w + spacing
    total_loop_width = count * unit_width
    layout_start_x = int(config.get('layout_start_x', 0))
    pos_y = int(height * (float(config.get('poster_y_percent', 45)) / 100)) - (target_h // 2)
    p_bright = float(config.get('poster_brightness', 1.0))
    p_shadow = int(config.get('poster_shadow_opacity', 140))

    shadow_margin = 10
    shadow = Image.new("RGBA", (target_w + shadow_margin*2, target_h + shadow_margin*2), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(shadow_margin, shadow_margin), (target_w+shadow_margin, target_h+shadow_margin)],
        radius=radius, fill=(0, 0, 0, p_shadow)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))

    items = []
    for i, url in enumerate(poster_urls):
        p_img = ctx.download_img(url)
        if not p_img:
            continue
        p_img = p_img.resize((target_w, target_h), Image.LANCZOS)
        if p_bright != 1.0:
            p_img = ImageEnhance.Brightness(p_img).enhance(p_bright)
        items.append((i * unit_width, add_rounded_corners(p_img, radius)))

    geom = {
        'width': width,
        'target_w': target_w,
        'total_loop_width': total_loop_width,
        'layout_start_x': layout_start_x,
        'pos_y': pos_y,
        'shadow_margin': shadow_margin,
    }
    return items, shadow, geom


def _paint_posters(bg, items, shadow, geom, anim_offset):
    """把海报按当前偏移画到画布（原地修改 bg），画布外的一律跳过。"""
    target_w = geom['target_w']
    loop = geom['total_loop_width']
    for base_x, p_img in items:
        current_x_relative = (base_x + anim_offset) % loop
        for extra in (0, -loop, loop):
            draw_x = geom['layout_start_x'] + current_x_relative + extra
            # 只绘制在画布范围内（稍微放宽一点边界）
            if draw_x > -target_w - 50 and draw_x < geom['width'] + 50:
                bg.paste(shadow, (int(draw_x) - geom['shadow_margin'] + 5, geom['pos_y'] - geom['shadow_margin'] + 5), mask=shadow)
                bg.paste(p_img, (int(draw_x), geom['pos_y']), mask=p_img)


def _draw_titles(ctx, config, fonts, draw, width, height):
    """主副标题（与静态路径同参数，画在海报之上）。"""
    f_title = fonts.get('font_title') or fonts.get('main')
    f_sub = fonts.get('font_subtitle') or fonts.get('sub') or f_title

    c_title = config.get('title_color', '#FFFFFF')
    c_sub = config.get('subtitle_color', '#DDDDDD')

    cx = int(width * (float(config.get('text_left_percent', 5)) / 100))
    cy = int(height * (float(config.get('text_top_percent', 75)) / 100))
    mw = int(width * 0.9)
    gap = int(config.get('text_gap', 20))

    title = config.get('title', '')
    if title:
        cy = ctx.draw_text_wrapper(draw, title, cx, cy, f_title, mw, c_title)
        cy += gap

    sub = config.get('subtitle', '')
    if sub:
        ctx.draw_text_wrapper(draw, sub, cx, cy, f_sub, mw, c_sub)


def _paint_backdrop(ctx, bg, config, width, height):
    """背景模糊（保持与静态路径一致的双重模糊视觉）+ 水平遮罩。"""
    blur_radius = int(config.get('blur_radius', 4))
    if blur_radius > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(blur_radius))
    mask_opacity = int(config.get('mask_opacity', 200))
    if mask_opacity > 0:
        mask = ctx.create_smart_mask(width, height, mask_opacity, 100, 'horizontal')
        black_layer = Image.new('RGBA', (width, height), (0,0,0,255))
        black_layer.putalpha(mask)
        bg = Image.alpha_composite(bg, black_layer)
    return bg


# =============================================================================
# 渲染入口函数
# =============================================================================
def render(ctx, bg, config, assets, fonts, step=0.0):
    width, height = bg.size
    bg = _paint_backdrop(ctx, bg, config, width, height)

    prepared = _prepare_posters(ctx, config, assets, width, height)
    if prepared:
        items, shadow, geom = prepared
        anim_offset = 0
        if config.get('enable_animation', True):
            direction = int(config.get('anim_direction', 1))
            anim_offset = step * geom['total_loop_width'] * direction
        _paint_posters(bg, items, shadow, geom, anim_offset)

    draw = ImageDraw.Draw(bg)
    _draw_titles(ctx, config, fonts, draw, width, height)

    return bg


def render_anim(ctx, config, assets, fonts, sink):
    """动画快速通道：素材与基底只处理一次，逐帧只做位移合成 + 文字绘制。

    帧间唯一变化是海报的水平偏移，因此与逐帧调用 render() 视觉完全一致，
    但省掉每帧的背景重建/模糊/海报下载缩放圆角，渲染耗时降一个数量级。
    每生成一帧调用 sink(frame)，全尺寸帧不驻留内存。
    """
    total_frames = max(2, min(int(config.get('anim_frames') or 30), 300))
    width = max(1, int(config.get('canvas_width') or 1920))
    height = max(1, int(config.get('canvas_height') or 1080))

    # 基底背景：与引擎 _render_frame 相同的构建逻辑（兜底/亮度/首次模糊）。
    bg = ctx.build_background_for_layout(config, assets, (width, height))
    bg = _paint_backdrop(ctx, bg, config, width, height)

    prepared = _prepare_posters(ctx, config, assets, width, height)
    items, shadow, geom = prepared if prepared else ([], None, {})
    direction = int(config.get('anim_direction', 1))

    for index in range(total_frames):
        step = index / float(total_frames - 1) if total_frames > 1 else 0.0
        frame = bg.copy()
        if prepared:
            anim_offset = step * geom['total_loop_width'] * direction
            _paint_posters(frame, items, shadow, geom, anim_offset)
        draw = ImageDraw.Draw(frame)
        _draw_titles(ctx, config, fonts, draw, width, height)
        sink(frame)