"""封面渲染引擎（PosterEngine）。

移植自 ChillPoster，按 V3 约束调整：

- 布局脚本**按需加载**（首次渲染时才 importlib 读取），不在模块导入期执行；
- 缓存挂在**实例**上，不放进进程级单例，避免虚拟分身之间互相污染；
- 字体从插件数据目录读取，缺失时回退到目录内任意字体或 PIL 默认字体。

布局模块契约：``render(engine, bg, config, assets, fonts, step=None) -> PIL.Image``
与 ``get_schema() -> {"fields": [...]}``（供前端按布局动态生成参数表单）。
"""
from __future__ import annotations

import base64
import importlib.util
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.sdk.logging import logger

from . import assets_meta

# 动态封面的输出尺寸（网页端可播放）与帧数上限。
ANIM_TARGET_WIDTH = 320
ANIM_MAX_FRAMES = 300
IMG_CACHE_MAX = 32

DEFAULT_ENGINE = "classic"

COMMON_SCHEMA_FIELDS: List[Dict[str, Any]] = [
    {"key": "title", "label": "主标题", "type": "text", "default": ""},
    {"key": "subtitle", "label": "副标题", "type": "text", "default": ""},
    {"key": "canvas_width", "label": "画布宽", "type": "number", "default": 1920},
    {"key": "canvas_height", "label": "画布高", "type": "number", "default": 1080},
    {"key": "blur_radius", "label": "背景模糊", "type": "number", "default": 4},
    {"key": "brightness", "label": "背景亮度", "type": "number", "default": 0.7, "step": 0.05},
    {"key": "font_title", "label": "标题字体", "type": "font", "default": ""},
    {"key": "font_subtitle", "label": "副标题字体", "type": "font", "default": ""},
    {"key": "title_size", "label": "标题字号", "type": "number", "default": 160},
    {"key": "subtitle_size", "label": "副标题字号", "type": "number", "default": 80},
    {"key": "output_width", "label": "输出宽（0=原始）", "type": "number", "default": 0},
    {"key": "output_height", "label": "输出高（0=原始）", "type": "number", "default": 0},
    {"key": "enable_animation", "label": "动态封面（APNG）", "type": "boolean", "default": False},
    {"key": "anim_frames", "label": "动画帧数", "type": "number", "default": 30},
    {"key": "anim_duration", "label": "帧间隔(ms)", "type": "number", "default": 100},
    {"key": "badge_style", "label": "角标样式", "type": "select", "default": "none",
     "options": [{"value": "none", "label": "无"}, {"value": "box", "label": "方框"},
                 {"value": "ribbon", "label": "角带"}]},
    {"key": "badge_size", "label": "角标字号", "type": "number", "default": 40},
    {"key": "badge_bg_color", "label": "角标底色", "type": "color", "default": "#0f172a"},
    {"key": "badge_text_color", "label": "角标字色", "type": "color", "default": "#ffffff"},
    {"key": "badge_font", "label": "角标字体", "type": "font", "default": ""},
]


class PosterEngine:
    """把一段渲染配置 + 素材合成为封面图片。"""

    def __init__(self, plugin) -> None:
        self.data_path = assets_meta.data_root(plugin)
        self.fonts_dir = assets_meta.fonts_dir(plugin)
        self.layouts_dir = assets_meta.layouts_dir(plugin)
        self._layouts: Optional[Dict[str, Any]] = None
        self._img_cache: Dict[str, Image.Image] = {}

    # -------------------------------------------------------------- 布局

    def _layout_files(self) -> Dict[str, Path]:
        """内置布局（插件包内）优先加载，用户布局（数据目录）可覆盖同名。"""
        files: Dict[str, Path] = {}
        builtin_dir = Path(__file__).parent / "layouts"
        if builtin_dir.exists():
            for item in sorted(builtin_dir.glob("*.py")):
                if item.name != "__init__.py":
                    files[item.stem] = item
        if self.layouts_dir.exists():
            for item in sorted(self.layouts_dir.glob("*.py")):
                if item.name != "__init__.py":
                    files[item.stem] = item
        return files

    @property
    def layout_modules(self) -> Dict[str, Any]:
        """按需加载布局模块（实例级缓存）。"""
        if self._layouts is None:
            modules: Dict[str, Any] = {}
            for name, path in self._layout_files().items():
                try:
                    spec = importlib.util.spec_from_file_location(f"embycovercenter_layout_{name}", path)
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "render"):
                        modules[name] = module
                    else:
                        logger.warning(f"[EmbyCoverCenter] 跳过布局 {name}：缺少 render()")
                except Exception as error:
                    logger.error(f"[EmbyCoverCenter] 加载布局失败 {name}: {error}")
            self._layouts = modules
        return self._layouts

    def layout_schemas(self) -> List[Dict[str, Any]]:
        """返回每个布局的参数字段（前端据此生成表单）。"""
        result: List[Dict[str, Any]] = []
        for name, module in self.layout_modules.items():
            schema = module.get_schema() if hasattr(module, "get_schema") else None
            fields = schema.get("fields") if isinstance(schema, dict) else None
            result.append({"name": name, "fields": fields if isinstance(fields, list) else []})
        return sorted(result, key=lambda item: item["name"])

    # -------------------------------------------------------------- 素材与字体

    def load_font(self, filename: Optional[str], size: int) -> ImageFont.FreeTypeFont:
        """按文件名加载字体；缺失时回退到目录内任意字体或 PIL 默认字体。"""
        size = max(1, int(size or 1))
        if filename:
            path = self.fonts_dir / str(filename)
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception as error:
                    logger.warning(f"[EmbyCoverCenter] 字体加载失败 {filename}: {error}")
        try:
            for item in sorted(self.fonts_dir.iterdir()):
                if item.is_file() and item.name.lower().endswith(assets_meta.FONT_EXTENSIONS):
                    return ImageFont.truetype(str(item), size)
        except Exception:
            pass
        return ImageFont.load_default()

    def download_img(self, url: Optional[str]) -> Optional[Image.Image]:
        """下载素材图片（带小型内存缓存）；失败返回 None。"""
        if not url:
            return None
        cached = self._img_cache.get(url)
        if cached is not None:
            return cached.copy()
        try:
            if str(url).startswith("data:image"):
                encoded = str(url).split(",", 1)[-1]
                img = Image.open(BytesIO(base64.b64decode(encoded, validate=False))).convert("RGBA")
            else:
                from app.sdk.network import RequestUtils

                res = RequestUtils(timeout=20).get_res(url=url)
                if res is None or res.status_code != 200:
                    return None
                img = Image.open(BytesIO(res.content)).convert("RGBA")
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 下载素材失败 {str(url)[:80]}: {error}")
            return None
        if len(self._img_cache) >= IMG_CACHE_MAX:
            self._img_cache.pop(next(iter(self._img_cache)), None)
        self._img_cache[url] = img.copy()
        return img

    @staticmethod
    def _rounded_mask(size: tuple, radius: int) -> Image.Image:
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=max(0, int(radius)), fill=255)
        return mask

    def paste_cover(self, canvas: Image.Image, url: Optional[str], box: tuple, radius: int = 0) -> None:
        """把素材按 cover 模式填满 box（保持比例，居中裁剪）后贴到画布。"""
        img = self.download_img(url)
        if img is None:
            return
        left, top, right, bottom = box
        target_w, target_h = max(1, right - left), max(1, bottom - top)
        src_w, src_h = img.size
        if src_w <= 0 or src_h <= 0:
            return
        scale = max(target_w / src_w, target_h / src_h)
        resized = img.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))), Image.LANCZOS)
        offset_x = max(0, (resized.size[0] - target_w) // 2)
        offset_y = max(0, (resized.size[1] - target_h) // 2)
        cropped = resized.crop((offset_x, offset_y, offset_x + target_w, offset_y + target_h))
        if radius > 0:
            canvas.paste(cropped, (left, top), self._rounded_mask(cropped.size, radius))
        else:
            canvas.paste(cropped, (left, top))

    # -------------------------------------------------------------- 绘制工具

    def draw_text_wrapper(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        fill: Any,
        line_spacing: int = 10,
        align: str = "left",
    ) -> int:
        """按最大宽度换行绘制文本，返回下一行的 y。"""
        if not text:
            return y
        lines: List[str] = []
        current = ""
        for char in str(text):
            candidate = current + char
            try:
                width = font.getlength(candidate)
            except Exception:
                width = font.getbbox(candidate)[2]
            if width <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)

        try:
            metrics = font.getmetrics()
            line_height = metrics[0] + metrics[1] + line_spacing
        except Exception:
            bbox = font.getbbox("Hg")
            line_height = (bbox[3] - bbox[1]) + line_spacing

        draw_y = y
        for line in lines:
            try:
                line_width = font.getlength(line)
            except Exception:
                line_width = font.getbbox(line)[2]
            draw_x = x
            if align == "center":
                draw_x = x - line_width / 2
            elif align == "right":
                draw_x = x - line_width
            draw.text((draw_x, draw_y), line, font=font, fill=fill)
            draw_y += line_height
        return draw_y

    def _draw_badge(self, img: Image.Image, config: Dict[str, Any], count: Any) -> Image.Image:
        """绘制数量角标（none / box / ribbon）。"""
        style = str(config.get("badge_style") or "none")
        if style == "none" or not count:
            return img
        text = str(count)
        scale = 4
        width, height = img.size
        overlay = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        base_size = 40 if style == "box" else 50
        user_size = int(config.get("badge_size") or base_size)
        font = None
        try:
            font = self.load_font(config.get("badge_font"), user_size * scale)
        except Exception:
            font = ImageFont.load_default()

        text_color = str(config.get("badge_text_color") or "#ffffff")
        bg_hex = str(config.get("badge_bg_color") or ("#b91c1c" if style == "ribbon" else "#0f172a"))
        try:
            r, g, b = ImageColor.getrgb(bg_hex)
            fill_color = (r, g, b, 255)
        except Exception:
            fill_color = (0, 0, 0, 255)

        if style == "ribbon":
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            ribbon_w = text_h + 40 * scale
            span = ribbon_w * 1.414
            gap = int(user_size * scale)
            points = [(gap, 0), (gap + span, 0), (0, gap + span), (0, gap)]
            draw.polygon(points, fill=fill_color)
            layer_size = int(max(text_w, span) * 2.5)
            layer = Image.new("RGBA", (layer_size, layer_size), (0, 0, 0, 0))
            center = layer_size / 2
            ImageDraw.Draw(layer).text(
                (center - text_w / 2 - bbox[0], center - text_h / 2 - bbox[1]),
                text, font=font, fill=text_color,
            )
            rotated = layer.rotate(45, resample=Image.BICUBIC)
            offset = int((gap + gap + span) / 2 - layer_size / 2)
            overlay.paste(rotated, (offset, offset), mask=rotated)
        else:
            margin = 30 * scale
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            box_w = text_w + int(user_size * 0.6 * scale) * 2
            box_h = text_h + int(user_size * 0.3 * scale) * 2
            box_w = max(box_w, box_h)
            rect = [(margin, margin), (margin + box_w, margin + box_h)]
            draw.rounded_rectangle(rect, radius=box_h / 2, fill=fill_color)
            draw.text(
                (margin + (box_w - text_w) / 2 - bbox[0], margin + (box_h - text_h) / 2 - bbox[1]),
                text, font=font, fill=text_color,
            )

        overlay = overlay.resize((width, height), resample=Image.LANCZOS)
        return Image.alpha_composite(img, overlay)

    # -------------------------------------------------------------- 渲染

    def _build_background(self, config: Dict[str, Any], assets: Dict[str, Any], size: tuple) -> Image.Image:
        canvas_w, canvas_h = size
        bg_url = assets.get("bg_url")
        bg = self.download_img(bg_url)
        if bg is None:
            bg = Image.new("RGBA", (canvas_w, canvas_h), (20, 30, 50, 255))
        if bg.size != (canvas_w, canvas_h):
            bg = bg.resize((canvas_w, canvas_h), Image.LANCZOS)
        blur = int(config.get("blur_radius") or 0)
        if blur > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(blur))
        try:
            bg = ImageEnhance.Brightness(bg).enhance(float(config.get("brightness") or 1))
        except Exception:
            pass
        return bg

    def _render_frame(
        self,
        config: Dict[str, Any],
        assets: Dict[str, Any],
        fonts: Dict[str, Any],
        step: Optional[float] = None,
    ) -> Image.Image:
        canvas_w = max(1, int(config.get("canvas_width") or 1920))
        canvas_h = max(1, int(config.get("canvas_height") or 1080))
        bg = self._build_background(config, assets, (canvas_w, canvas_h))
        layout = str(config.get("engine") or config.get("cover_layout") or DEFAULT_ENGINE)
        render = self.layout_modules.get(layout)
        if render is None:
            render = self.layout_modules.get(DEFAULT_ENGINE)
        if render is None:
            frame = bg
        else:
            try:
                frame = render.render(self, bg, config, assets, fonts, step=step)
            except TypeError:
                frame = render.render(self, bg, config, assets, fonts)
        return self._draw_badge(frame, config, assets.get("count"))

    def draw(self, config: Dict[str, Any], assets: Dict[str, Any]) -> str:
        """渲染封面并返回 base64（静态 JPEG 或动态 APNG）。"""
        config = dict(config or {})
        assets = dict(assets or {})
        fonts = {
            "main": self.load_font(config.get("font_title"), int(config.get("title_size") or 160)),
            "sub": self.load_font(config.get("font_subtitle"), int(config.get("subtitle_size") or 80)),
            "count": self.load_font(config.get("badge_font"), int(config.get("count_size") or 40)),
        }
        output = BytesIO()

        if config.get("enable_animation"):
            total_frames = max(2, min(int(config.get("anim_frames") or 30), ANIM_MAX_FRAMES))
            duration = max(20, int(config.get("anim_duration") or 100))
            target_h = max(1, int(ANIM_TARGET_WIDTH * 9 / 16))
            frames: List[Image.Image] = []
            for index in range(total_frames):
                step = index / float(total_frames - 1) if total_frames > 1 else 0.0
                frame = self._render_frame(config, assets, fonts, step=step)
                frame = frame.convert("RGBA").resize((ANIM_TARGET_WIDTH, target_h), Image.LANCZOS)
                frames.append(frame)
            frames[0].save(
                output, format="PNG", save_all=True, append_images=frames[1:],
                duration=duration, loop=0, optimize=False,
            )
        else:
            frame = self._render_frame(config, assets, fonts).convert("RGB")
            out_w = int(config.get("output_width") or 0)
            out_h = int(config.get("output_height") or 0)
            if out_w > 0 and out_h > 0 and frame.size != (out_w, out_h):
                frame = frame.resize((out_w, out_h), Image.LANCZOS)
            frame.save(output, format="JPEG", quality=90)

        self._img_cache.clear()
        return base64.b64encode(output.getvalue()).decode("utf-8")

    @staticmethod
    def base64_mime(payload: str) -> str:
        """按 base64 头猜测 MIME，供前端 dataURL 使用。"""
        head = payload[:8]
        if head.startswith("iVBOR"):
            return "image/png"
        if head.startswith("R0lGOD"):
            return "image/gif"
        return "image/jpeg"
