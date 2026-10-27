"""1.6.25 回归：遮罩四方向 / 画布自动跟随 / JPEG 画质 / 底图锐化。"""
import base64
import io
import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

from app.plugins.embycovercenter.service import assets_meta
from app.plugins.embycovercenter.service.render_engine import (
    CANVAS_PRESETS,
    MAX_CANVAS_SIDE,
    PosterEngine,
)

PACKAGE = Path(assets_meta.__file__).resolve().parent.parent


class _FakePlugin:
    def __init__(self, data_path):
        self._data_path = Path(data_path)

    def get_data_path(self):
        return self._data_path


def _make_engine(tmp_path, fonts=()):
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    for name in fonts:
        src = PACKAGE / "defaults" / "fonts" / name
        if src.exists():
            shutil.copy(src, assets_meta.fonts_dir(plugin) / name)
    return PosterEngine(plugin)


def _side_means(mask):
    width, height = mask.size
    left = ImageStat.Stat(mask.crop((0, 0, width // 2, height))).mean[0]
    right = ImageStat.Stat(mask.crop((width // 2, 0, width, height))).mean[0]
    return left, right


def _band_means(mask):
    width, height = mask.size
    top = ImageStat.Stat(mask.crop((0, 0, width, height // 2))).mean[0]
    bottom = ImageStat.Stat(mask.crop((0, height // 2, width, height))).mean[0]
    return top, bottom


def test_smart_mask_horizontal_directions(tmp_path):
    """horizontal = 左黑右亮；horizontal_reverse = 右黑左亮（遮罩不透明度即“黑”的浓度）。"""
    engine = _make_engine(tmp_path)
    forward = engine.create_smart_mask(200, 100, 255, 100, "horizontal")
    reverse = engine.create_smart_mask(200, 100, 255, 100, "horizontal_reverse")

    left, right = _side_means(forward)
    assert left > right * 2.5, f"horizontal 不是左黑右亮：左 {left:.1f} / 右 {right:.1f}"
    assert forward.getpixel((0, 50)) == 255, "horizontal 左侧应完全不透明"
    assert forward.getpixel((199, 50)) <= 2, "horizontal 右侧应完全透明"

    left, right = _side_means(reverse)
    assert right > left * 2.5, f"horizontal_reverse 不是右黑左亮：左 {left:.1f} / 右 {right:.1f}"
    assert reverse.getpixel((0, 50)) <= 2, "horizontal_reverse 左侧应完全透明"
    assert reverse.getpixel((199, 50)) >= 250, "horizontal_reverse 右侧应完全不透明"

    # 两者是镜像关系（同一渐变方向翻转，允许 1-2 级量化误差）
    mirrored = reverse.transpose(Image.FLIP_LEFT_RIGHT)
    assert max(ImageChops.difference(forward, mirrored).getdata()) <= 3
    engine.close()


def test_smart_mask_vertical_directions(tmp_path):
    """vertical = 下黑上亮（历史行为）；vertical_reverse = 上黑下亮。"""
    engine = _make_engine(tmp_path)
    legacy = engine.create_smart_mask(100, 200, 255, 100, "vertical")
    reverse = engine.create_smart_mask(100, 200, 255, 100, "vertical_reverse")

    top, bottom = _band_means(legacy)
    assert bottom > top * 2.5, f"vertical 不是下黑上亮：上 {top:.1f} / 下 {bottom:.1f}"
    assert legacy.getpixel((50, 0)) == 0, "vertical 顶部应完全透明"
    assert legacy.getpixel((50, 199)) >= 250, "vertical 底部应完全不透明"

    top, bottom = _band_means(reverse)
    assert top > bottom * 2.5, f"vertical_reverse 不是上黑下亮：上 {top:.1f} / 下 {bottom:.1f}"
    assert reverse.getpixel((50, 0)) == 255, "vertical_reverse 顶部应完全不透明"
    assert reverse.getpixel((50, 199)) <= 2, "vertical_reverse 底部应完全透明"

    mirrored = reverse.transpose(Image.FLIP_TOP_BOTTOM)
    assert max(ImageChops.difference(legacy, mirrored).getdata()) <= 3
    engine.close()


def test_smart_mask_aliases_and_degenerate_coverage(tmp_path):
    """别名（right/top/bottom）与 coverage=0 都不能崩，且方向语义一致。"""
    engine = _make_engine(tmp_path)
    base = engine.create_smart_mask(100, 100, 200, 100, "horizontal_reverse")
    assert ImageChops.difference(base, engine.create_smart_mask(100, 100, 200, 100, "right")).getbbox() is None
    assert ImageChops.difference(
        engine.create_smart_mask(100, 100, 200, 100, "vertical_reverse"),
        engine.create_smart_mask(100, 100, 200, 100, "top"),
    ).getbbox() is None
    # coverage=0 时整块遮罩为空（不能退化成全黑盖住画面）
    empty = engine.create_smart_mask(100, 100, 255, 0, "horizontal")
    assert ImageStat.Stat(empty).mean[0] == 0
    # 未知方向退回水平默认，不抛异常
    assert engine.create_smart_mask(100, 100, 255, 100, "不认识").size == (100, 100)
    engine.close()


def test_resolve_canvas_follows_preset_and_keyart(tmp_path):
    """canvas_preset：预设取固定尺寸、custom 取宽高、auto 跟随主视觉原图。"""
    engine = _make_engine(tmp_path)
    assert engine.resolve_canvas({"canvas_preset": "1080p"}) == (1920, 1080)
    assert engine.resolve_canvas({"canvas_preset": "1440p"}) == (2560, 1440)
    assert engine.resolve_canvas({"canvas_preset": "2160p"}) == (3840, 2160)
    assert engine.resolve_canvas({"canvas_preset": "custom", "canvas_width": 1234, "canvas_height": 678}) == (1234, 678)
    # 没有主视觉时 auto 退回 canvas_width/height（默认 1920×1080）
    assert engine.resolve_canvas({"canvas_preset": "auto"}) == (1920, 1080)

    # 上传 3840×2160 的主视觉后，auto 应直接按原图出画布（这正是用户抱怨的「被压成 1080p」）
    art = Image.new("RGB", (3840, 2160), (30, 40, 60))
    buffer = io.BytesIO()
    art.save(buffer, format="PNG")
    assets_meta.save_keyart(_FakePlugin(tmp_path), "big.png", buffer.getvalue())
    assert engine.resolve_canvas({"canvas_preset": "auto", "keyart_file": "big.png"}) == (3840, 2160)
    engine.close()


def test_resolve_canvas_clamps_and_forces_even(tmp_path):
    """超大尺寸被 MAX_CANVAS_SIDE 截断，奇数边取偶（JPEG 奇数边会多黑边）。"""
    engine = _make_engine(tmp_path)
    width, height = engine.resolve_canvas({"canvas_preset": "custom", "canvas_width": 99999, "canvas_height": 9999})
    assert width == MAX_CANVAS_SIDE
    assert height % 2 == 0 and height <= MAX_CANVAS_SIDE
    assert engine.resolve_canvas({"canvas_preset": "custom", "canvas_width": 1921, "canvas_height": 1081}) == (1920, 1080)
    # 非法值退回默认，不抛异常
    assert engine.resolve_canvas({"canvas_preset": "custom", "canvas_width": 0, "canvas_height": "abc"}) == (1920, 1080)
    engine.close()


def test_draw_honours_output_quality(tmp_path, monkeypatch):
    """output_quality 越高文件越大；老配置没有该键时按 95 走（不再固定 90）。"""
    engine = _make_engine(tmp_path)
    # 高细节噪点图：画质差异在体积上可测
    scene = Image.effect_noise((480, 270), 60).convert("RGB")
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": "经典平铺",
        "title": "画质",
        "canvas_preset": "custom",
        "canvas_width": 480,
        "canvas_height": 270,
        "badge_style": "none",
    }
    assets = {"bg_url": "http://bg", "posters": [], "count": 0}
    low = len(base64.b64decode(engine.draw(dict(config, output_quality=70), assets)))
    high = len(base64.b64decode(engine.draw(dict(config, output_quality=100), assets)))
    default = len(base64.b64decode(engine.draw(dict(config), assets)))
    assert high > low, f"画质参数没生效：q70={low} / q100={high}"
    assert default > low * 1.2, f"默认画质应接近 95：default={default} / q70={low}"
    engine.close()


def test_draw_keeps_2k_canvas_instead_of_downscaling(tmp_path, monkeypatch):
    """选 2160p 时输出必须是 3840×2160，不能被悄悄缩回 1920×1080。"""
    engine = _make_engine(tmp_path)
    scene = Image.new("RGB", (1920, 1080), (40, 60, 90))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": "经典平铺",
        "title": "2K",
        "canvas_preset": "2160p",
        "badge_style": "none",
    }
    assets = {"bg_url": "http://bg", "posters": [], "count": 0}
    data = base64.b64decode(engine.draw(config, assets))
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == (3840, 2160), f"2K 画布被压缩：{image.size}"
    engine.close()


def test_category_banner_does_not_sharpen_background(tmp_path, monkeypatch):
    """用户要求去掉底图智能锐化：底图应原样进出，不再有 _unsharp。"""
    engine = _make_engine(tmp_path)
    module = engine.layout_modules["分类横幅"]
    assert not hasattr(module, "_unsharp"), "底图智能锐化应已移除"
    assert "sharpen_amount" not in {
        item["key"] for group in module.get_schema() for item in group["items"]
    }
    engine.close()


def test_shipped_preset_uses_library_background_without_scrim(tmp_path):
    """随包预设走媒体库背景图，默认不压暗、不调色（底图什么样就什么样）。"""
    payload = json.loads(
        (PACKAGE / "defaults" / "templates" / "分类横幅.json").read_text(encoding="utf-8")
    )
    config = payload["config"]
    assert config["bg_source"] == "library"
    for removed in ("scrim_enabled", "scrim_color", "scrim_start", "scrim_ramp", "scrim_strength"):
        assert removed not in config, f"预设仍带已删除字段：{removed}"
    for removed in ("grade_color", "grade_strength", "glow_color", "glow_strength",
                    "vignette_strength", "grain"):
        assert removed not in config, f"预设仍带已下线的调色字段：{removed}"
    # 预设默认「保持原图」：遮罩关、底部不压、亮度/对比度/饱和度都是 1.0
    assert config["mask_enabled"] is False
    assert config["bottom_scrim_strength"] == 0
    assert config["scene_brightness"] == 1.0
    assert config["scene_contrast"] == 1.0
    assert config["scene_saturation"] == 1.0
    assert config["mask_direction"] == "horizontal_reverse"
    assert config["canvas_preset"] == "auto"
    assert config["output_quality"] == 95
    assert CANVAS_PRESETS["2160p"] == (3840, 2160)
