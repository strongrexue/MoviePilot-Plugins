"""生成「分类横幅」的 6 套预设 JSON 与 640×360 缩略图。

只用布局模块本身 + 一组程序化底图（复用 mockup 的场景/海报/主视觉生成器），
不依赖 MoviePilot 宿主，所以可以在仓库里直接跑：

    python docs/mockups/gen_category_banner_presets.py

产物：
- plugins.v3/embycovercenter/defaults/templates/分类横幅-*.json
- plugins.v3/embycovercenter/defaults/templates/分类横幅-*.jpg
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "plugins.v3" / "embycovercenter"
LAYOUT_PATH = PLUGIN_DIR / "service" / "layouts" / "分类横幅.py"
TEMPLATE_DIR = PLUGIN_DIR / "defaults" / "templates"
FONT_DIR = PLUGIN_DIR / "defaults" / "fonts"

LAYOUT_NAME = "分类横幅"

CJK_FALLBACKS = [
    "优设标题黑.ttf",
    "OPPOSans-M.ttf",
    "OPPOSans-L.ttf",
    "叶根友毛笔行书.ttf",
]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


layout = _load_module("category_banner_layout", LAYOUT_PATH)
mockup = _load_module("category_banner_mockup", Path(__file__).with_name("category_banner_mockup.py"))


class _FakeEngine:
    """布局只用到 load_font / download_img / data_path / fonts_dir。"""

    def __init__(self) -> None:
        self.data_path = str(TEMPLATE_DIR.parent)  # 缩略图不需要本地 keyart
        self.fonts_dir = FONT_DIR

    def load_font(self, name, size):
        candidates = [name] if name else []
        candidates.extend(CJK_FALLBACKS)
        for candidate in candidates:
            path = FONT_DIR / str(candidate)
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), max(1, int(size)))
                except Exception:
                    continue
        return ImageFont.load_default()

    def download_img(self, url):
        # 缩略图用程序化底图，不下载任何网络素材（bg_source 自然回退到 bg）。
        return None


def _defaults() -> dict:
    """从 schema 取默认值，保证预设与字段永远对齐。"""
    return {
        item["key"]: item.get("default")
        for group in layout.get_schema()
        for item in group["items"]
    }


WARM = {
    "scrim_color": "#0A0705",
    "grade_color": "#7A4A24",
    "grade_strength": 14,
    "title_gradient_top": "#FFF6DC",
    "title_gradient_bottom": "#C79A55",
    "divider_color": "#C4A470",
    "divider_flare_color": "#FFE8BE",
    "subtitle_color": "#D9C9AE",
    "slogan_color": "#EFE3CD",
    "tags_color": "#D8C8AE",
    "watermark_color": "#FFDCBC",
    "frame_border_color": "#D8966C",
    "frame_outside_color": "#060404",
    "glow_color": "#FFD9A8",
}

COOL = {
    "scrim_color": "#04080F",
    "grade_color": "#1E3A5F",
    "grade_strength": 16,
    "title_gradient_top": "#F2F8FF",
    "title_gradient_bottom": "#8FB6DE",
    "divider_color": "#8FA8C8",
    "divider_flare_color": "#E8F4FF",
    "subtitle_color": "#C8D6E8",
    "slogan_color": "#E4EEFA",
    "tags_color": "#CBD8E6",
    "watermark_color": "#DDEBFF",
    "frame_border_color": "#9DB6D8",
    "frame_outside_color": "#04070C",
    "glow_color": "#BFE0FF",
}

CRIMSON = {
    "scrim_color": "#0C0504",
    "grade_color": "#5A1A18",
    "grade_strength": 18,
    "title_gradient_top": "#FFF0E0",
    "title_gradient_bottom": "#D89A6A",
    "divider_color": "#C98A6A",
    "divider_flare_color": "#FFE0C0",
    "subtitle_color": "#E0C8B8",
    "slogan_color": "#F0DCC8",
    "tags_color": "#E0C8B8",
    "watermark_color": "#FFD8C0",
    "frame_border_color": "#C08060",
    "frame_outside_color": "#070303",
    "glow_color": "#FFB080",
}

# (文件名, 显示名, 覆盖项, 缩略图底图, 缩略图题材, 缩略图文案)
PRESETS = [
    (
        "分类横幅-暖金",
        "分类横幅 · 暖金",
        {**WARM, "bg_source": "keyart"},
        lambda: mockup.keyart_layer(mockup.WARM),
        ["爱情", "都市", "悬疑", "剧情", "家庭"],
        ("国产剧", "CHINESE SERIES"),
    ),
    (
        "分类横幅-冷蓝",
        "分类横幅 · 冷蓝",
        {**COOL, "bg_source": "keyart"},
        lambda: mockup.keyart_layer(mockup.COOL),
        ["青春", "奇幻", "冒险", "成长", "治愈"],
        ("日番动画", "JAPANESE ANIMATION"),
    ),
    (
        "分类横幅-朱红",
        "分类横幅 · 朱红",
        {**CRIMSON, "bg_source": "keyart"},
        lambda: mockup.keyart_layer(mockup.CRIMSON),
        ["动作", "武侠", "犯罪", "惊悚", "剧情"],
        ("华语电影", "CHINESE FILMS"),
    ),
    (
        "分类横幅-左对齐",
        "分类横幅 · 左对齐（参考图原版式）",
        {
            **WARM,
            "bg_source": "keyart",
            "title_x": 57.5,
            "title_y": 33.5,
            "title_size": 190,
            "title_align": "left",
            "title_max_width": 36.5,
            "divider_width": 35.5,
            "subtitle_tracking": 0.50,
            "subtitle_max_width": 36.5,
            "slogan_max_width": 36.5,
        },
        lambda: mockup.keyart_layer(mockup.WARM),
        ["爱情", "都市", "悬疑", "剧情", "家庭"],
        ("国产剧", "CHINESE SERIES"),
    ),
    (
        "分类横幅-海报阵列",
        "分类横幅 · 海报阵列",
        {
            **CRIMSON,
            "bg_source": "posters",
            "poster_count": 12,
            "watermark_opacity": 10,
        },
        lambda: mockup.poster_layer(mockup.CRIMSON),
        ["华语", "电影", "经典", "高分", "收藏"],
        ("华语电影", "CHINESE FILMS"),
    ),
    (
        "分类横幅-无压暗全幅",
        "分类横幅 · 无压暗全幅",
        {
            **WARM,
            "bg_source": "library",
            "scrim_enabled": False,
            "frame_radius": 0,
            "grade_color": "#4A4038",
            "grade_strength": 8,
            "glow_strength": 0,
            "vignette_strength": 90,
        },
        lambda: mockup.scene_layer(mockup.WARM),
        ["纪录片", "自然", "人文", "历史", "科学"],
        ("纪录片", "DOCUMENTARIES"),
    ),
]


def build_config(overrides: dict) -> dict:
    config = _defaults()
    config.update(overrides)
    config["engine"] = LAYOUT_NAME
    config.setdefault("poster_count", 6)
    config.setdefault("backdrop_count", 2)
    config["badge_style"] = "none"
    return config


def main() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    engine = _FakeEngine()
    for filename, display, overrides, background, genres, copy in PRESETS:
        config = build_config(overrides)
        payload = {"name": display, "layout": LAYOUT_NAME, "config": config}
        (TEMPLATE_DIR / f"{filename}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8"
        )

        # 底图按 1920×1080 生成，再缩到 640×360 交给布局（尺寸参数按画布高缩放）。
        base = background().convert("RGBA").resize((640, 360), Image.LANCZOS)
        assets = {"genres": genres, "posters": [], "count": 0}
        # 缩略图用示例库名（真实自动封面会把标题替换成媒体库名），预设里 title 仍留空。
        preview = dict(config, title=copy[0], subtitle=copy[1])
        image = layout.render(engine, base, preview, assets, {})
        image.convert("RGB").save(TEMPLATE_DIR / f"{filename}.jpg", quality=88, optimize=True)
        print("written", filename)


if __name__ == "__main__":
    main()
