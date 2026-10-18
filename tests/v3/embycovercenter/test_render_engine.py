"""render_engine 修复回归：字体中文回退 / 角标对比度 / 背景海报兜底 / 内置模板修复。"""
import json
import shutil
from pathlib import Path

from app.plugins.embycovercenter.service import assets_meta
from app.plugins.embycovercenter.service.render_engine import PosterEngine

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


def test_load_font_prefers_cjk_on_missing(tmp_path):
    """引用不存在的字体时，回退应优先中文字体而不是按文件名排序拿到英文字体。"""
    engine = _make_engine(tmp_path, fonts=("Bodoni MT Black.TTF", "优设标题黑.ttf"))
    font = engine.load_font("不存在的字体.ttf", 40)
    assert str(font.path).endswith("优设标题黑.ttf")


def test_load_font_missing_cjk_falls_back_to_any(tmp_path):
    """目录里只有英文字体时回退到目录内任意字体（不崩）。"""
    engine = _make_engine(tmp_path, fonts=("Bodoni MT Black.TTF",))
    font = engine.load_font("缺失.ttf", 40)
    assert font is not None


def test_badge_white_on_white_gets_contrast(tmp_path):
    """白底白字（模板历史错误配置）应自动改为深色字，数字可见。"""
    engine = _make_engine(tmp_path, fonts=("优设标题黑.ttf",))
    img = engine._draw_badge(
        __import__("PIL.Image", fromlist=["Image"]).new("RGBA", (300, 160), (255, 255, 255, 255)),
        {"badge_style": "box", "badge_bg_color": "#ffffff", "badge_text_color": "#ffffff", "badge_size": 40},
        "386",
    )
    # 角标区域内应出现深色像素（#0f172a 的字；box 从 (30,30) 起约占到 (150,150)）
    dark = sum(
        1
        for x in range(20, 160)
        for y in range(20, 150)
        if sum(img.getpixel((x, y))[:3]) < 240
    )
    assert dark > 30


def test_badge_normal_colors_untouched(tmp_path):
    """正常深底白字不应被改写。"""
    engine = _make_engine(tmp_path, fonts=("优设标题黑.ttf",))
    img = engine._draw_badge(
        __import__("PIL.Image", fromlist=["Image"]).new("RGBA", (300, 160), (255, 255, 255, 255)),
        {"badge_style": "box", "badge_bg_color": "#0f172a", "badge_text_color": "#ffffff", "badge_size": 40},
        "386",
    )
    # 深色底应该仍占多数（角标底色存在）
    dark = sum(
        1
        for x in range(0, 120)
        for y in range(0, 60)
        if sum(img.getpixel((x, y))[:3]) < 240
    )
    assert dark > 300


def test_background_falls_back_to_first_poster(tmp_path, monkeypatch):
    """无 backdrop 时用首张海报兜底做背景（不再是纯色底）。"""
    from PIL import Image

    engine = _make_engine(tmp_path)
    red_poster = Image.new("RGB", (200, 300), (200, 30, 30))
    monkeypatch.setattr(engine, "download_img", lambda url: red_poster.copy() if url else None)
    bg = engine._build_background({"blur_radius": 0}, {"posters": ["http://p1"]}, (192, 108))
    # 背景应来自海报（红色）而不是默认纯色底 (20,30,50)
    pixel = bg.convert("RGB").getpixel((5, 5))
    assert pixel == (200, 30, 30)
    assert bg.mode == "RGBA"  # 布局普遍用 alpha_composite，必须 RGBA


def test_background_bright_poster_replaces_dark_backdrop(tmp_path, monkeypatch):
    """backdrop 近黑（暗色主题图）时应换更亮的海报做背景。"""
    from PIL import Image

    engine = _make_engine(tmp_path)
    dark_backdrop = Image.new("RGB", (1920, 1080), (5, 5, 5))
    bright_poster = Image.new("RGB", (200, 300), (220, 180, 60))

    def fake_download(url):
        if url == "http://bg":
            return dark_backdrop.copy()
        if url == "http://p1":
            return bright_poster.copy()
        return None

    monkeypatch.setattr(engine, "download_img", fake_download)
    bg = engine._build_background(
        {"blur_radius": 0}, {"bg_url": "http://bg", "posters": ["http://p1"]}, (192, 108)
    )
    assert bg.convert("RGB").getpixel((5, 5)) == (220, 180, 60)


def test_real_layout_composite_does_not_break(tmp_path, monkeypatch):
    """回归：背景海报兜底后走真实布局渲染，alpha_composite 不再报 wrong mode。"""
    from PIL import Image

    engine = _make_engine(tmp_path, fonts=("优设标题黑.ttf",))
    poster = Image.new("RGB", (200, 300), (120, 160, 90))
    monkeypatch.setattr(engine, "download_img", lambda url: poster.copy() if url else None)
    config = {
        "engine": "经典平铺",
        "title": "儿童",
        "subtitle": "Kids",
        "canvas_width": 480,
        "canvas_height": 270,
        "poster_count": 3,
        "backdrop_count": 0,
    }
    assets = {"posters": ["http://p1", "http://p2", "http://p3"], "count": 386}
    encoded = engine.draw(config, assets)  # 不抛 "image has wrong mode" 即通过
    assert encoded


def test_fix_known_template_bugs(tmp_path):
    """历史错误模板字段自动修正；用户自定义值不动。"""
    plugin = _FakePlugin(tmp_path)
    templates = assets_meta.templates_dir(plugin)
    templates.mkdir(parents=True, exist_ok=True)
    # 旧错误值 → 修正
    stale = {
        "name": "旋转默认",
        "config": {"badge_bg_color": "#ffffff", "badge_text_color": "#ffffff", "title": "x"},
    }
    (templates / "旋转默认.json").write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
    # 用户自定义 → 不动
    custom = {
        "name": "动态平铺",
        "config": {"font_title": "我的字体.ttf"},
    }
    (templates / "动态平铺.json").write_text(json.dumps(custom, ensure_ascii=False), encoding="utf-8")

    fixed = assets_meta.fix_known_template_bugs(plugin)
    assert fixed == 1
    patched = json.loads((templates / "旋转默认.json").read_text(encoding="utf-8"))
    assert patched["config"]["badge_text_color"] == "#0f172a"
    assert patched["config"]["title"] == "x"  # 其余字段不丢
    untouched = json.loads((templates / "动态平铺.json").read_text(encoding="utf-8"))
    assert untouched["config"]["font_title"] == "我的字体.ttf"


def test_rename_legacy_template_names(tmp_path):
    """内置模板的旧显示名（xxx默认 / xxx预设）就地改成布局本名；用户改过名的不动。"""
    plugin = _FakePlugin(tmp_path)
    templates = assets_meta.templates_dir(plugin)
    templates.mkdir(parents=True, exist_ok=True)
    legacy = {"name": "扇形展开默认", "layout": "扇形展开", "config": {"title": "x"}}
    (templates / "扇形展开默认.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    custom = {"name": "我的旋转", "layout": "旋转", "config": {}}
    (templates / "旋转默认.json").write_text(json.dumps(custom, ensure_ascii=False), encoding="utf-8")

    assert assets_meta.rename_legacy_template_names(plugin) == 1
    renamed = json.loads((templates / "扇形展开默认.json").read_text(encoding="utf-8"))
    assert renamed["name"] == "扇形展开"
    assert renamed["config"]["title"] == "x"  # 其余字段不丢
    untouched = json.loads((templates / "旋转默认.json").read_text(encoding="utf-8"))
    assert untouched["name"] == "我的旋转"  # 用户自定义名字保留
    # 幂等：再跑一次没有可改的
    assert assets_meta.rename_legacy_template_names(plugin) == 0


def test_default_template_display_names_have_no_suffix(tmp_path):
    """随包分发的预设显示名不带「默认 / 预设」后缀，且与布局同名。"""
    plugin = _FakePlugin(tmp_path)
    assets_meta.seed_default_templates(plugin)
    templates = assets_meta.list_templates(plugin)
    names = {item["name"] for item in templates}
    assert {
        "扇形展开",
        "斜线分割",
        "旋转",
        "旋转堆叠",
        "海报墙",
        "经典堆叠",
        "经典平铺",
        "聚焦",
        "荣耀视界",
        "极简",
        "动态平铺",
    } <= names
    assert not [name for name in names if name.endswith(("默认", "预设"))]
    # 文件名保持原样：auto_cover_template 存的是它，老配置不能失效
    filenames = {item["filename"] for item in templates}
    assert "旋转默认.json" in filenames and "旋转堆叠预设.json" in filenames
    # 迁移表里的文件名必须都还在包里（只改显示名、不改文件名的约定）
    shipped = {path.name for path in (PACKAGE / "defaults" / "templates").glob("*.json")}
    assert set(assets_meta.TEMPLATE_NAME_RENAMES) <= shipped


def test_anim_fast_path_matches_frame_by_frame_render(tmp_path, monkeypatch):
    """render_anim 快速通道应与逐帧 render() 视觉一致（动画帧间只有海报水平偏移变化）。"""
    from PIL import Image, ImageChops

    engine = _make_engine(tmp_path, fonts=("优设标题黑.ttf",))
    colors = [(120, 160, 90), (90, 120, 200), (200, 90, 90)]

    def fake_download(url):
        if not url:
            return None
        idx = int(url.rsplit("p", 1)[-1]) % len(colors)
        return Image.new("RGB", (200, 300), colors[idx])

    monkeypatch.setattr(engine, "download_img", fake_download)
    config = {
        "engine": "经典平铺(动态)",
        "title": "电影",
        "subtitle": "Movies",
        "canvas_width": 480,
        "canvas_height": 270,
        "poster_count": 5,
        "backdrop_count": 0,
        "enable_animation": True,
        "anim_frames": 12,
        "anim_duration": 33,
        "badge_style": "none",
    }
    assets = {"posters": [f"http://p{i}" for i in range(5)], "count": 0}
    fonts = {"main": engine.load_font(None, 30), "sub": engine.load_font(None, 20), "count": engine.load_font(None, 16)}

    fast = []
    render = engine.layout_modules["经典平铺(动态)"]
    render.render_anim(engine, config, assets, fonts, sink=fast.append)

    slow = []
    for index in range(12):
        step = index / float(11)
        slow.append(engine._render_frame(config, assets, fonts, step=step))

    assert len(fast) == len(slow) == 12
    for a, b in zip(fast, slow):
        bbox = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox()
        assert bbox is None  # 逐帧像素完全一致
