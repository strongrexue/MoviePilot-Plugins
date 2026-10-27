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
PRESETS = ("分类横幅",)

# 文件名 → 界面显示名（文件名是唯一标识，显示名可以带说明）
DISPLAY_NAMES = {
    "分类横幅": "分类横幅",
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
    for expected in ("背景与底图", "底图调整（默认 1.0 = 保持原样）", "特效与装饰", "主标题", "副标题", "标语",
                     "灯带（标题下的光带）", "题材标签", "书法水印", "圆角边框"):
        assert expected in groups, f"缺少分组：{expected}"
    # 用户要求「去掉调色与质感组件，底图什么样就什么样」
    assert "调色与质感" not in groups, "调色与质感分组应已移除"
    # 「英文名」已按用户要求改名为「副标题」
    assert "英文名" not in groups, "「英文名」分组应已改名为「副标题」"

    keys = {item["key"] for group in schema for item in group["items"]}
    for key in (
        "bg_source", "keyart_file", "keyart_per_library", "keyart_focus_x",
        "mask_enabled", "mask_color", "mask_direction", "mask_coverage", "bottom_scrim_strength",
        "scene_brightness", "scene_contrast", "scene_saturation",
        "title_enabled", "title_x", "title_y", "title_tracking", "title_align",
        "subtitle_enabled", "slogan_enabled", "tags_enabled",
        "divider_color", "divider_flare_pos", "divider_flare_color",
        "tags_source", "tags_x", "tags_y", "tags_per_library",
        "watermark_enabled", "watermark_x", "watermark_rotate",
        "frame_radius", "frame_border_color",
    ):
        assert key in keys, f"schema 缺少字段：{key}"
    # 用户要求「去掉底图智能锐化」
    assert "sharpen_amount" not in keys, "底图智能锐化应已移除"

    # 右侧压暗层已整组移除，海报阵列底图也已移除（改由「特效与装饰」提供遮罩）
    for removed in ("scrim_enabled", "scrim_color", "scrim_start", "scrim_ramp", "scrim_strength"):
        assert removed not in keys, f"已删除的字段仍在 schema：{removed}"
    # 「调色与质感」整组下线：统一色相 / 溢光 / 暗角 / 颗粒都不再参与渲染
    for removed in ("grade_color", "grade_strength", "glow_color", "glow_strength",
                    "vignette_strength", "grain"):
        assert removed not in keys, f"调色与质感字段仍在 schema：{removed}"
    # auto_mirror 语义属于底图，移到「背景与底图」分组
    bg_group = next(group for group in schema if group["group"] == "背景与底图")
    assert "auto_mirror" in {item["key"] for item in bg_group["items"]}
    bg = next(item for group in schema for item in group["items"] if item["key"] == "bg_source")
    assert [option["value"] for option in bg["options"]] == ["keyart", "library"]

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
        "mask_enabled": False, "watermark_enabled": False,
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
        "mask_enabled": False, "watermark_enabled": False,
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
    """同配置重复渲染逐像素一致（遮罩 / 锐化都必须是确定性的）。"""
    engine = _make_engine(tmp_path)
    scene = _gradient((480, 270), (200, 170, 110), (24, 28, 40))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    config = {
        "engine": LAYOUT, "canvas_width": 480, "canvas_height": 270,
        "bg_source": "library", "title": "欧美剧", "subtitle": "Western Drama",
        "mask_enabled": True, "badge_style": "none",
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
    maxed.update({"bg_source": "library", "title_align": "center", "divider_align": "center"})
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
        "bg_source": "library", "title": "无素材", "subtitle": "Fallback", "badge_style": "none",
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
    """随包预设都能加载、布局名一致、schema 字段齐全、缩略图 640×360。"""
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


def _plain_config(**overrides):
    """只留灯带、其它元素全关的最小配置，便于单独测灯带形状。"""
    config = {
        "engine": LAYOUT, "canvas_width": 640, "canvas_height": 360,
        "bg_source": "library", "title": "", "subtitle": "",
        "slogan_cn": "", "slogan_en": "", "tags_text": "",
        "watermark_enabled": False, "mask_enabled": False,
        "frame_radius": 0, "frame_border_width": 0, "badge_style": "none",
        "divider_enabled": True, "divider_width": 40, "divider_thickness": 3,
        "divider_flare_pos": 50, "divider_flare_strength": 245,
        "divider_color": "#FFFFFF", "divider_flare_color": "#FFFFFF",
    }
    config.update(overrides)
    return config


def test_divider_is_a_continuous_glow(tmp_path, monkeypatch):
    """灯带必须是一条连续的高斯光带：单峰、没有平台段、两端淡进背景。

    旧实现是「一条接近等亮的横杠 + 中间一坨椭圆高光」，横杠左右两端还各自
    带硬边，看起来像贴上去的；参考图（哆啦A梦那张）是一条中心发白、
    向外连续衰减的光带。
    """
    engine = _make_engine(tmp_path)
    scene = Image.new("RGB", (640, 360), (20, 22, 28))
    monkeypatch.setattr(engine, "download_img", lambda url: scene.copy() if url else None)
    frame = _render(engine, _plain_config(), {"bg_url": "http://bg", "posters": [], "count": 0})
    gray = frame.convert("L")
    width, height = gray.size

    row = max(range(height // 2, height), key=lambda y: sum(gray.getpixel((x, y)) for x in range(width)))
    profile = [gray.getpixel((x, row)) for x in range(width)]
    background = profile[0]
    peak = max(profile)
    peak_at = profile.index(peak)
    assert peak - background > 80, "灯带没画出来"

    span = [x for x in range(width) if profile[x] > background + 0.02 * (peak - background)]
    left, right = span[0], span[-1]
    # 不能有台阶：相邻两列的最大跳变必须远小于整体高度（硬边/贴上去的横杠会超标）
    steps = [abs(profile[x] - profile[x - 1]) for x in range(left + 1, right + 1)]
    assert max(steps) <= 0.22 * (peak - background), "灯带有硬边（相邻列亮度突跳）"

    for ratio in (0.35, 0.45):
        for x in (peak_at - int((right - left) * ratio), peak_at + int((right - left) * ratio)):
            if left <= x <= right:
                assert profile[x] < background + 0.3 * (peak - background), "灯带两端没有淡出"

    # 从中心向外单调衰减（允许 1 级量化抖动），左端不再「左高右低」的斜坡
    for x in range(peak_at + 1, right + 1):
        assert profile[x] <= profile[x - 1] + 1, "灯带右侧不是单调衰减"
    for x in range(peak_at - 1, left - 1, -1):
        assert profile[x] <= profile[x + 1] + 1, "灯带左侧不是单调衰减"

    # 纵向也应是柔和衰减，而不是一条 1px 硬线
    column = [gray.getpixel((peak_at, y)) for y in range(max(0, row - 4), min(height, row + 5))]
    assert abs(column[0] - column[-1]) <= 3, "灯带纵向不对称"
    assert column[0] < peak - 40 and column[-1] < peak - 40, "灯带纵向没有过渡（硬线）"
    engine.close()


def test_schema_defaults_for_divider_and_watermark(tmp_path):
    """水印锚点默认 85%、灯带中心亮度默认 245、遮罩默认开启（浓度 180 / 范围 66%）、底图不做任何调整。"""
    engine = _make_engine(tmp_path)
    schema = engine.layout_modules[LAYOUT].get_schema()
    defaults = {item["key"]: item.get("default") for group in schema for item in group["items"]}
    assert defaults["watermark_x"] == 85
    assert defaults["watermark_opacity"] == 3
    assert defaults["divider_flare_strength"] == 245
    assert defaults["mask_enabled"] is True
    assert defaults["mask_color"] == "#000000"
    assert defaults["mask_opacity"] == 180
    assert defaults["mask_coverage"] == 66
    assert defaults["mask_direction"] == "horizontal_reverse"
    # 「底图什么样就什么样」：亮度/对比度/饱和度默认 1.0，底部遮罩默认 0
    assert defaults["scene_brightness"] == 1.0
    assert defaults["scene_contrast"] == 1.0
    assert defaults["scene_saturation"] == 1.0
    assert defaults["bottom_scrim_strength"] == 0
    # 四个文字区块各自带独立开关，默认全开
    for key in ("title_enabled", "subtitle_enabled", "slogan_enabled", "tags_enabled"):
        assert defaults[key] is True, f"{key} 默认应为开"
    engine.close()


def test_retire_legacy_templates_only_when_unmodified(tmp_path, monkeypatch):
    """1.6.23 铺开的 6 套预设按内容指纹回收；用户改过配置或改过名的原样保留。"""
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    target = assets_meta.templates_dir(plugin)
    shipped = {"name": "分类横幅 · 暖金", "layout": LAYOUT, "config": {"title_size": 189}}
    path = target / "分类横幅-暖金.json"
    path.write_text(json.dumps(shipped, ensure_ascii=False), encoding="utf-8")
    (target / "分类横幅-暖金.jpg").write_bytes(b"preview")

    monkeypatch.setattr(
        assets_meta,
        "RETIRED_TEMPLATES",
        {
            "分类横幅-暖金.json": assets_meta._template_digest(shipped),
            "分类横幅-不存在.json": "0" * 64,
        },
    )
    assert assets_meta.retire_legacy_templates(plugin) == 1
    assert not path.exists()
    assert not (target / "分类横幅-暖金.jpg").exists()

    edited = {"name": "我的分类横幅", "layout": LAYOUT, "config": {"title_size": 200}}
    path.write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        assets_meta, "RETIRED_TEMPLATES", {"分类横幅-暖金.json": assets_meta._template_digest(shipped)}
    )
    assert assets_meta.retire_legacy_templates(plugin) == 0
    assert path.exists()


def test_seeded_install_has_single_category_banner_preset(tmp_path):
    """新装/升级后数据目录里只剩一套「分类横幅」预设。"""
    plugin = _FakePlugin(tmp_path)
    assets_meta.seed_default_templates(plugin)
    entries = assets_meta.list_templates(plugin)
    assert "分类横幅" in [entry["name"] for entry in entries]
    assert not [entry for entry in entries if entry["name"].startswith("分类横幅-")]


def test_upgrade_shipped_templates_replaces_legacy_copy(tmp_path):
    """内置预设原地升级：老指纹被覆盖成随包版本，缩略图同步换新，重复调用幂等。"""
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    target = assets_meta.templates_dir(plugin)
    packaged = json.loads(
        (assets_meta.PACKAGE_DEFAULTS_DIR / "templates" / "分类横幅.json").read_text(encoding="utf-8")
    )
    packaged_digest = assets_meta._template_digest(packaged)
    legacy = {"name": packaged["name"], "layout": LAYOUT, "config": {"title_size": 111}}
    legacy_digest = assets_meta._template_digest(legacy)
    assert legacy_digest != packaged_digest

    path = target / "分类横幅.json"
    preview = target / "分类横幅.jpg"
    path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    preview.write_bytes(b"old-preview")

    monkeypatch_target = assets_meta.SHIPPED_TEMPLATE_HISTORY
    assets_meta.SHIPPED_TEMPLATE_HISTORY = {"分类横幅.json": {legacy_digest}}
    try:
        assert assets_meta.upgrade_shipped_templates(plugin) == 1
    finally:
        assets_meta.SHIPPED_TEMPLATE_HISTORY = monkeypatch_target

    assert assets_meta._template_digest(json.loads(path.read_text(encoding="utf-8"))) == packaged_digest
    assert preview.read_bytes() == (
        assets_meta.PACKAGE_DEFAULTS_DIR / "templates" / "分类横幅.jpg"
    ).read_bytes()
    # 幂等：已经是随包版本时不再改动
    assets_meta.SHIPPED_TEMPLATE_HISTORY = {"分类横幅.json": {legacy_digest}}
    try:
        assert assets_meta.upgrade_shipped_templates(plugin) == 0
    finally:
        assets_meta.SHIPPED_TEMPLATE_HISTORY = monkeypatch_target


def test_upgrade_shipped_templates_keeps_user_edits(tmp_path):
    """用户改过配置的预设不能被覆盖。"""
    plugin = _FakePlugin(tmp_path)
    assets_meta.ensure_dirs(plugin)
    target = assets_meta.templates_dir(plugin)
    packaged = json.loads(
        (assets_meta.PACKAGE_DEFAULTS_DIR / "templates" / "分类横幅.json").read_text(encoding="utf-8")
    )
    legacy = {"name": packaged["name"], "layout": LAYOUT, "config": {"title_size": 111}}
    edited = {"name": "我的分类横幅", "layout": LAYOUT, "config": {"title_size": 300}}
    path = target / "分类横幅.json"
    path.write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()

    original = assets_meta.SHIPPED_TEMPLATE_HISTORY
    assets_meta.SHIPPED_TEMPLATE_HISTORY = {"分类横幅.json": {assets_meta._template_digest(legacy)}}
    try:
        assert assets_meta.upgrade_shipped_templates(plugin) == 0
    finally:
        assets_meta.SHIPPED_TEMPLATE_HISTORY = original
    assert path.read_bytes() == before


def test_shipped_preset_history_matches_packaged_file(tmp_path):
    """登记的历史指纹必须都和随包版本不同，否则这条记录毫无意义。"""
    packaged = json.loads(
        (assets_meta.PACKAGE_DEFAULTS_DIR / "templates" / "分类横幅.json").read_text(encoding="utf-8")
    )
    packaged_digest = assets_meta._template_digest(packaged)
    history = assets_meta.SHIPPED_TEMPLATE_HISTORY["分类横幅.json"]
    assert history, "应登记至少一个历史版本指纹"
    assert packaged_digest not in history
