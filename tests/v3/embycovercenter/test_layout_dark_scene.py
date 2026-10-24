"""「暗场右文」布局回归：构图方向 / 接缝对齐 / 确定性 / 极端参数 / 内置预设。"""
import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat

from app.plugins.embycovercenter.service import assets_meta
from app.plugins.embycovercenter.service.render_engine import PosterEngine

PACKAGE = Path(assets_meta.__file__).resolve().parent.parent
LAYOUT = "暗场右文"


class _FakePlugin:
    def __init__(self, data_path):
        self._data_path = Path(data_path)

    def get_data_path(self):
        return self._data_path


def _make_engine(tmp_path, fonts=("优设标题黑.ttf", "OPPOSans-M.ttf")):
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    for name in fonts:
        src = PACKAGE / "defaults" / "fonts" / name
        if src.exists():
            shutil.copy(src, assets_meta.fonts_dir(plugin) / name)
    return PosterEngine(plugin)


def _load_layout(tmp_path):
    """取到布局模块本身（测试内部函数时不必走引擎）。"""
    return _make_engine(tmp_path).layout_modules[LAYOUT]


def _gradient(size, left, right):
    """横向线性渐变图，用来模拟「一侧亮、一侧暗」的媒体库背景图。"""
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for x in range(width):
        ratio = x / max(1, width - 1)
        color = tuple(int(left[i] + (right[i] - left[i]) * ratio) for i in range(3))
        draw.line([(x, 0), (x, height)], fill=color)
    return image


def _half_luma(image):
    gray = image.convert("L")
    width, height = gray.size
    left = ImageStat.Stat(gray.crop((0, 0, width // 2, height))).mean[0]
    right = ImageStat.Stat(gray.crop((width // 2, 0, width, height))).mean[0]
    return left, right


def _render(engine, config, assets, fonts=None):
    layout = engine.layout_modules[LAYOUT]
    size = (config.get("canvas_width", 640), config.get("canvas_height", 360))
    fonts = fonts or {
        "main": engine.load_font("优设标题黑.ttf", 44),
        "sub": engine.load_font("OPPOSans-M.ttf", 16),
        "count": engine.load_font(None, 14),
    }
    bg = engine._build_background(config, assets, size)
    return layout.render(engine, bg, config, assets, fonts)


def test_layout_is_discoverable_and_has_schema(tmp_path):
    """新布局应被引擎自动发现（无需改前端），且导出 render 与 get_schema。"""
    engine = _make_engine(tmp_path)
    assert LAYOUT in engine.layout_modules
    module = engine.layout_modules[LAYOUT]
    assert callable(module.render)
    schema = module.get_schema()
    assert isinstance(schema, list) and schema
    keys = {item["key"] for group in schema for item in group["items"]}
    # 几个关键可调项必须在（用户在配置页里能看到）
    assert {"hero_width_percent", "text_left_percent", "tint_color", "auto_mirror"} <= keys
    # layout_schemas() 也应把它列进去
    listed = {item["name"]: item for item in engine.layout_schemas()}
    assert LAYOUT in listed and listed[LAYOUT]["groups"]
    engine.close()


def test_composition_is_left_bright_right_dark(tmp_path, monkeypatch):
    """渲染结果必须是「左亮右暗」，文字才有落点。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((640, 360), (230, 200, 120), (20, 24, 34))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
        "title": "华语剧集", "subtitle": "Chinese Drama", "badge_style": "none",
    }
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    frame = _render(engine, config, assets)
    left, right = _half_luma(frame)
    assert left > right * 1.8, f"左 {left:.1f} / 右 {right:.1f} 不满足左亮右暗"
    engine.close()


def test_scene_and_base_share_the_same_framing(tmp_path):
    """清晰区与基底必须用**整画布**取景。

    历史 bug：清晰区按 ``hero_width`` 单独 ``ImageOps.fit`` 到 (hero_w, height)，
    基底按 (width, height) fit。素材宽高比与画布一致时两者恰好相同，看不出问题；
    换成 4:3 海报这类不同比例素材，裁剪位置就错开，接缝处画面内容对不上。
    """
    module = _load_layout(tmp_path)
    # 4:3 素材放到 16:9 画布：只有「都按整画布取景」时才不会错位。
    source = _gradient((400, 300), (240, 210, 130), (18, 22, 32))
    width, height = 640, 360
    plain = dict(canvas_width=width, canvas_height=height)

    scene, _ = module._build_scene(
        source,
        dict(plain, scene_brightness=1.0, scene_contrast=1.0, scene_saturation=1.0, scene_blur=0),
        width,
        height,
    )
    expected = ImageOps.fit(source.convert("RGBA"), (width, height), method=Image.LANCZOS)
    assert ImageChops.difference(scene.convert("RGB"), expected.convert("RGB")).getbbox() is None

    base = module._build_base(
        source, dict(plain, base_blur=0, base_brightness=1.0, tint_color="#070b12"), width, height
    )
    tint = Image.new("RGB", (width, height), (7, 11, 18))
    expected_base = Image.blend(expected.convert("RGB"), tint, 0.35)
    assert ImageChops.difference(base.convert("RGB"), expected_base).getbbox() is None


def test_render_is_deterministic(tmp_path, monkeypatch):
    """同配置重复渲染必须逐像素一致（噪点用固定种子，否则动态封面会闪）。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((480, 270), (200, 170, 110), (24, 28, 40))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": LAYOUT, "canvas_width": 480, "canvas_height": 270,
        "title": "日番", "subtitle": "Anime", "grain": 30, "badge_style": "none",
    }
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    first = _render(engine, config, assets).convert("RGB")
    second = _render(engine, config, assets).convert("RGB")
    assert ImageChops.difference(first, second).getbbox() is None
    engine.close()


def test_auto_mirror_flips_right_bright_source(tmp_path, monkeypatch):
    """素材本身左暗右亮时自动镜像，保证文字区落在暗侧。"""
    engine = _make_engine(tmp_path)
    # 左暗右亮：不做镜像的话文字会压在亮场上
    scene = _gradient((640, 360), (20, 24, 34), (230, 200, 120))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
        "auto_mirror": True, "title": "", "subtitle": "", "badge_style": "none",
    }
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    frame = _render(engine, config, assets)
    left, right = _half_luma(frame)
    assert left > right * 1.8, f"镜像后仍不是左亮右暗：左 {left:.1f} / 右 {right:.1f}"

    # 关掉开关就保持原方向（右亮）
    config["auto_mirror"] = False
    frame = _render(engine, config, assets)
    left, right = _half_luma(frame)
    assert right > left, f"关闭 auto_mirror 后方向应保持原样：左 {left:.1f} / 右 {right:.1f}"
    engine.close()


def test_missing_assets_does_not_crash(tmp_path, monkeypatch):
    """没有任何素材时返回纯色底 + 文字，不抛异常。"""
    engine = _make_engine(tmp_path)
    monkeypatch.setattr(engine, "download_img", lambda url: None)
    config = {
        "engine": LAYOUT, "canvas_width": 320, "canvas_height": 180,
        "title": "无素材", "subtitle": "Fallback", "badge_style": "none",
    }
    frame = _render(engine, config, {"posters": [], "count": 0})
    assert frame.size == (320, 180) and frame.mode == "RGBA"
    engine.close()


def test_extreme_and_string_config_values(tmp_path, monkeypatch):
    """参数全 0 / 全满 / 字符串（前端 range 可能传字符串）都不能崩。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((320, 180), (180, 150, 90), (30, 34, 46))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    base = {"engine": LAYOUT, "canvas_width": 320, "canvas_height": 180,
            "title": "极端", "subtitle": "Extreme", "badge_style": "none"}

    zeros = dict(base, hero_width_percent=0, feather_right=0, scene_blur=0, base_blur=0,
                 base_brightness=0, darken_strength=0, glow_strength=0,
                 vignette_strength=0, grain=0, title_size=1, subtitle_size=1)
    assert _render(engine, zeros, assets).size == (320, 180)

    maxed = dict(base, hero_width_percent=100, feather_right=100, scene_blur=60,
                 base_blur=100, base_brightness=1, darken_strength=255,
                 glow_strength=255, vignette_strength=255, grain=100,
                 title_size=300, subtitle_size=160)
    assert _render(engine, maxed, assets).size == (320, 180)

    strings = dict(base, hero_width_percent="abc", feather_right="", base_blur="x",
                   tint_color="not-a-color", title_color=None, text_align="weird",
                   text_left_percent="abc")
    assert _render(engine, strings, assets).size == (320, 180)
    engine.close()


def test_empty_title_draws_no_text(tmp_path, monkeypatch):
    """标题与副标题都为空时不应画任何文字像素。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((320, 180), (180, 150, 90), (30, 34, 46))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    base = {"engine": LAYOUT, "canvas_width": 320, "canvas_height": 180, "badge_style": "none"}
    blank = _render(engine, dict(base, title="", subtitle=""), assets).convert("RGB")
    titled = _render(engine, dict(base, title="电影", subtitle="Movies"), assets).convert("RGB")
    assert ImageChops.difference(blank, titled).getbbox() is not None  # 有字时应不同
    engine.close()


def test_shipped_preset_matches_schema(tmp_path):
    """随包预设「暗场右文」存在、能加载、字段与 schema 对得上、缩略图尺寸正确。"""
    template = PACKAGE / "defaults" / "templates" / f"{LAYOUT}.json"
    assert template.exists()
    payload = json.loads(template.read_text(encoding="utf-8"))
    assert payload["name"] == LAYOUT
    assert payload["layout"] == LAYOUT

    engine = _make_engine(tmp_path)
    schema_keys = {
        item["key"]
        for group in engine.layout_modules[LAYOUT].get_schema()
        for item in group["items"]
    }
    # 预设里不能缺布局自己的参数（缺了配置页会显示为空）
    assert not (schema_keys - set(payload["config"]))
    engine.close()

    preview = PACKAGE / "defaults" / "templates" / f"{LAYOUT}.jpg"
    assert preview.exists()
    with Image.open(preview) as image:
        assert image.size == (640, 360)
