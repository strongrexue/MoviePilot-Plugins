"""「分类横幅」布局回归：可发现性 / 主视觉取值 / 标签三级来源 / 确定性 / 极端参数 / 内置预设。"""
import base64
import io
import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

from app.plugins.embycovercenter.service import assets_meta
from app.plugins.embycovercenter.service.render_engine import PosterEngine

PACKAGE = Path(assets_meta.__file__).resolve().parent.parent
LAYOUT = "分类横幅"
PRESETS = (
    "分类横幅-暖金",
    "分类横幅-冷蓝",
    "分类横幅-朱红",
    "分类横幅-左对齐",
    "分类横幅-海报阵列",
    "分类横幅-无压暗全幅",
)

# 文件名 → 界面显示名（文件名是唯一标识，显示名可以带说明）
DISPLAY_NAMES = {
    "分类横幅-暖金": "分类横幅 · 暖金",
    "分类横幅-冷蓝": "分类横幅 · 冷蓝",
    "分类横幅-朱红": "分类横幅 · 朱红",
    "分类横幅-左对齐": "分类横幅 · 左对齐（参考图原版式）",
    "分类横幅-海报阵列": "分类横幅 · 海报阵列",
    "分类横幅-无压暗全幅": "分类横幅 · 无压暗全幅",
}


class _FakePlugin:
    def __init__(self, data_path):
        self._data_path = Path(data_path)

    def get_data_path(self):
        return self._data_path


def _make_engine(tmp_path):
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    for name in ("优设标题黑.ttf", "OPPOSans-M.ttf", "OPPOSans-L.ttf"):
        src = PACKAGE / "defaults" / "fonts" / name
        if src.exists():
            shutil.copy(src, assets_meta.fonts_dir(plugin) / name)
    return PosterEngine(plugin)


def _gradient(size, left, right):
    """横向线性渐变图，模拟「一侧亮、一侧暗」的媒体库背景图。"""
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


def _render(engine, config, assets):
    layout = engine.layout_modules[LAYOUT]
    size = (config.get("canvas_width", 640), config.get("canvas_height", 360))
    bg = engine._build_background(config, assets, size)
    return layout.render(engine, bg, config, assets)


def test_layout_is_discoverable_and_has_schema(tmp_path):
    """布局被引擎自动发现（无需改前端），schema 覆盖用户要求的每个可调分区。"""
    engine = _make_engine(tmp_path)
    assert LAYOUT in engine.layout_modules
    module = engine.layout_modules[LAYOUT]
    assert callable(module.render)

    schema = module.get_schema()
    groups = {group["group"] for group in schema}
    # 用户明确要求「标题/副标题/字距/光带/圆角框/水印/标签各自可单独分区修改」
    for expected in ("背景与底图", "主标题", "英文名", "标语", "灯带（标题下的光带）",
                     "题材标签", "书法水印", "圆角边框"):
        assert expected in groups, f"缺少分组：{expected}"

    keys = {item["key"] for group in schema for item in group["items"]}
    for key in (
        "bg_source", "keyart_file", "keyart_per_library", "keyart_focus_x",
        "title_x", "title_y", "title_tracking", "title_align",
        "divider_color", "divider_flare_pos", "divider_flare_color",
        "tags_source", "tags_x", "tags_y", "tags_per_library",
        "watermark_enabled", "watermark_x", "watermark_rotate",
        "frame_radius", "frame_border_color",
    ):
        assert key in keys, f"schema 缺少字段：{key}"

    listed = {item["name"]: item for item in engine.layout_schemas()}
    assert LAYOUT in listed and listed[LAYOUT]["groups"]
    engine.close()


def test_keyart_field_is_a_file_picker_field(tmp_path):
    """主视觉文件名必须是 file 类型（前端据此渲染上传控件，而不是纯文本框）。"""
    engine = _make_engine(tmp_path)
    schema = engine.layout_modules[LAYOUT].get_schema()
    item = next(
        entry for group in schema for entry in group["items"] if entry["key"] == "keyart_file"
    )
    assert item["type"] == "file"
    engine.close()


def test_uploaded_keyart_is_used_as_scene(tmp_path, monkeypatch):
    """上传到 data/keyart/ 的图应被 keyart_file 按裸文件名取到，并决定画面内容。"""
    engine = _make_engine(tmp_path)
    plugin = _FakePlugin(tmp_path)
    # 一张纯红主视觉：如果它真被用上，画面左半必然明显偏红。
    art = Image.new("RGB", (1280, 720), (200, 30, 30))
    buffer = io.BytesIO()
    art.save(buffer, format="PNG")
    assets_meta.save_keyart(plugin, "keyart-red.png", buffer.getvalue())
    assert "keyart-red.png" in assets_meta.list_keyart(plugin)

    config = {
        "engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
        "bg_source": "keyart", "keyart_file": "keyart-red.png",
        "title": "国产剧", "subtitle": "Chinese Drama", "badge_style": "none",
        "scrim_enabled": False, "grade_strength": 0, "grain": 0,
        "vignette_strength": 0, "watermark_enabled": False,
    }
    frame = _render(engine, config, {"posters": [], "count": 0}).convert("RGB")
    left = ImageStat.Stat(frame.crop((0, 0, 320, 360))).mean
    assert left[0] > left[1] * 1.5 and left[0] > left[2] * 1.5, f"主视觉没生效：{left}"
    engine.close()


def test_missing_keyart_falls_back_to_library_background(tmp_path, monkeypatch):
    """主视觉文件不存在时回退到媒体库背景图，而不是报错或全黑。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((640, 360), (210, 180, 120), (24, 28, 40))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
        "bg_source": "keyart", "keyart_file": "not-there.png",
        "title": "日番", "subtitle": "Anime", "badge_style": "none",
        "scrim_enabled": False, "grade_strength": 0, "grain": 0,
        "vignette_strength": 0, "watermark_enabled": False,
    }
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    frame = _render(engine, config, assets)
    assert frame.size == (640, 360)
    left, right = _half_luma(frame)
    assert left > right * 1.5, f"应回退到背景图（左亮右暗）：左 {left:.1f} / 右 {right:.1f}"
    engine.close()


def test_path_traversal_file_name_is_rejected(tmp_path):
    """keyart_file 来自配置，必须拒绝路径穿越，只认裸文件名。"""
    module = _make_engine(tmp_path).layout_modules[LAYOUT]
    for bad in ("../secret.png", "a/b.png", "a\\b.png", "C:/x.png", ".hidden.png", "a|b.png"):
        assert module._safe_file_name(bad) == "", f"未拒绝危险文件名：{bad}"
    assert module._safe_file_name("keyart-red.png") == "keyart-red.png"


def test_tags_source_priority(tmp_path):
    """标签三级来源：manual / library / auto 的优先级必须按配置生效。"""
    module = _make_engine(tmp_path).layout_modules[LAYOUT]
    assets = {"library_id": "lib-1", "genres": ["剧情", "悬疑"]}
    base = {
        "tags_text": "手填甲｜手填乙",
        "tags_per_library": json.dumps({"lib-1": ["库标签A"]}, ensure_ascii=False),
        "tags_separator": "｜",
    }
    assert module._tags_for(dict(base, tags_source="manual"), assets) == ["手填甲", "手填乙"]
    assert module._tags_for(dict(base, tags_source="library"), assets) == ["库标签A"]
    assert module._tags_for(dict(base, tags_source="auto"), assets) == ["剧情", "悬疑"]
    # 高优先级来源为空时逐级回退，最终为空列表而不是崩
    empty = {"tags_per_library": "{}", "tags_separator": "｜"}
    assert module._tags_for(dict(empty, tags_source="manual"), {}) == []


def test_render_is_deterministic(tmp_path, monkeypatch):
    """同配置重复渲染逐像素一致（噪点固定种子，否则动态封面会闪）。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((480, 270), (200, 170, 110), (24, 28, 40))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": LAYOUT, "canvas_width": 480, "canvas_height": 270,
        "bg_source": "library", "title": "欧美剧", "subtitle": "Western Drama",
        "grain": 30, "badge_style": "none",
    }
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    first = _render(engine, config, assets).convert("RGB")
    second = _render(engine, config, assets).convert("RGB")
    assert ImageChops.difference(first, second).getbbox() is None
    engine.close()


def test_extreme_and_string_config_values(tmp_path, monkeypatch):
    """参数全 0 / 全满 / 字符串垃圾（前端 range 可能传字符串）都不能崩。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((320, 180), (180, 150, 90), (30, 34, 46))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0}
    base = {
        "engine": LAYOUT, "canvas_width": 320, "canvas_height": 180,
        "bg_source": "library", "title": "极端", "subtitle": "Extreme", "badge_style": "none",
    }
    schema_keys = [
        item["key"] for group in engine.layout_modules[LAYOUT].get_schema()
        for item in group["items"]
    ]

    zeros = dict(base, **{key: 0 for key in schema_keys})
    zeros.update({"tags_source": "manual", "title_align": "left", "divider_align": "left"})
    assert _render(engine, zeros, assets).size == (320, 180)

    maxed = dict(base, **{key: 255 for key in schema_keys})
    maxed.update({"bg_source": "posters", "title_align": "center", "divider_align": "center"})
    assert _render(engine, maxed, assets).size == (320, 180)

    garbage = dict(base, **{key: "abc" for key in schema_keys})
    garbage.update({"bg_source": "library", "keyart_per_library": "not-json"})
    assert _render(engine, garbage, assets).size == (320, 180)
    engine.close()


def test_missing_assets_does_not_crash(tmp_path, monkeypatch):
    """没有任何素材时返回纯色底 + 文字，不抛异常。"""
    engine = _make_engine(tmp_path)
    monkeypatch.setattr(engine, "download_img", lambda url: None)
    config = {
        "engine": LAYOUT, "canvas_width": 320, "canvas_height": 180,
        "bg_source": "posters", "title": "无素材", "subtitle": "Fallback", "badge_style": "none",
    }
    frame = _render(engine, config, {"posters": [], "count": 0})
    assert frame.size == (320, 180) and frame.mode == "RGBA"
    engine.close()


def test_long_title_shrinks_instead_of_overflowing(tmp_path, monkeypatch):
    """库名越长字号自动越小，标题亮区不能超出画布右边界。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((640, 360), (210, 180, 120), (24, 28, 40))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    assets = {"bg_url": "http://bg", "posters": [], "count": 0}
    base = {
        "engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
        "bg_source": "library", "badge_style": "none", "watermark_enabled": False,
    }
    widths = []
    for title in ("剧", "国产剧", "国产连续剧集", "国产连续剧集超长名称测试"):
        frame = _render(engine, dict(base, title=title, subtitle=""), assets).convert("L")
        # 标题是整幅最亮的部分；取亮区包围盒看右边界
        bbox = frame.point(lambda v: 255 if v > 200 else 0).getbbox()
        assert bbox is not None, f"标题没画出来：{title}"
        widths.append(bbox[2])
    assert all(width <= 640 for width in widths), f"标题越界：{widths}"
    engine.close()


def test_shipped_presets_match_schema(tmp_path):
    """6 套随包预设都能加载、布局名一致、schema 字段齐全、缩略图 640×360。"""
    engine = _make_engine(tmp_path)
    schema_keys = {
        item["key"]
        for group in engine.layout_modules[LAYOUT].get_schema()
        for item in group["items"]
    }
    for stem in PRESETS:
        template = PACKAGE / "defaults" / "templates" / f"{stem}.json"
        assert template.exists(), f"缺少预设：{stem}"
        payload = json.loads(template.read_text(encoding="utf-8"))
        assert payload["name"] == DISPLAY_NAMES[stem]
        assert payload["layout"] == LAYOUT
        # 预设里不能缺布局自己的参数（缺了配置页会显示为空）
        assert not (schema_keys - set(payload["config"])), f"{stem} 缺字段"
        preview = PACKAGE / "defaults" / "templates" / f"{stem}.jpg"
        assert preview.exists(), f"缺少缩略图：{stem}"
        with Image.open(preview) as image:
            assert image.size == (640, 360)
    engine.close()


def test_all_presets_render(tmp_path, monkeypatch):
    """每套预设都要真能渲染出图（不只是字段对得上）。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((640, 360), (210, 180, 120), (24, 28, 40))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    assets = {"bg_url": "http://bg", "posters": ["http://p1"], "count": 0,
              "library_id": "lib-1", "library_name": "国产剧", "library_en": "Chinese Drama",
              "genres": ["剧情"]}
    for stem in PRESETS:
        payload = json.loads(
            (PACKAGE / "defaults" / "templates" / f"{stem}.json").read_text(encoding="utf-8")
        )
        config = dict(payload["config"])
        config.update({"engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
                       "badge_style": "none"})
        frame = _render(engine, config, assets)
        assert frame.size == (640, 360), f"{stem} 渲染尺寸不对"
    engine.close()
