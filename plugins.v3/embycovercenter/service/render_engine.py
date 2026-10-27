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
import hashlib
import importlib.util
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.sdk.logging import logger

from . import assets_meta

# 动态封面的输出尺寸（网页端可播放）与帧数上限。
ANIM_TARGET_WIDTH = 320
ANIM_MAX_FRAMES = 300
IMG_CACHE_MAX = 128
# 磁盘缓存上限（文件数）：素材 URL 带 Emby 图片 tag（图片变更即换 URL，天然内容寻址），
# 自动封面每轮反复抽样同一批海报，磁盘缓存命中后无需重新下载。
IMG_DISK_CACHE_MAX = 800

# 默认布局（与内置布局模块名一致）。
DEFAULT_ENGINE = "经典平铺"

# 引擎通用参数（各布局 schema 之外的部分：画布/输出/动态/角标）。
COMMON_SCHEMA_FIELDS: List[Dict[str, Any]] = [
    {"key": "canvas_preset", "label": "画布尺寸", "type": "select", "default": "auto",
     "options": [
         {"label": "跟随主视觉原图（无主视觉时 1920×1080）", "value": "auto"},
         {"label": "1920×1080（全高清）", "value": "1080p"},
         {"label": "2560×1440（2K）", "value": "1440p"},
         {"label": "3840×2160（4K）", "value": "2160p"},
         {"label": "自定义（用下面的宽高）", "value": "custom"},
     ]},
    {"key": "canvas_width", "label": "画布宽（预设=自定义时生效）", "type": "number", "default": 1920},
    {"key": "canvas_height", "label": "画布高（预设=自定义时生效）", "type": "number", "default": 1080},
    {"key": "output_width", "label": "输出宽（0=原始）", "type": "number", "default": 0},
    {"key": "output_height", "label": "输出高（0=原始）", "type": "number", "default": 0},
    {"key": "output_quality", "label": "JPEG 画质（95 以上不降采样）", "type": "number", "default": 95},
    {"key": "enable_animation", "label": "动态封面（APNG）", "type": "boolean", "default": False},
    {"key": "anim_frames", "label": "动画帧数", "type": "number", "default": 30},
    {"key": "anim_duration", "label": "帧间隔(ms)", "type": "number", "default": 100},
    {"key": "badge_style", "label": "角标样式", "type": "select", "default": "none",
     "options": [{"label": "无", "value": "none"}, {"label": "方框", "value": "box"},
                 {"label": "角带", "value": "ribbon"}]},
    {"key": "badge_size", "label": "角标字号", "type": "number", "default": 40},
    {"key": "badge_bg_color", "label": "角标底色", "type": "color", "default": "#0f172a"},
    {"key": "badge_text_color", "label": "角标字色", "type": "color", "default": "#ffffff"},
    {"key": "badge_font", "label": "角标字体", "type": "font", "default": ""},
]

# 画布预设 → (宽, 高)；``auto`` / ``custom`` 走单独分支。
CANVAS_PRESETS: Dict[str, tuple] = {
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "2160p": (3840, 2160),
}
# 单边上限：再大就是几百 MB 的 PIL 位图，预览必然超时。
MAX_CANVAS_SIDE = 4096

COMMON_GROUP_NAME = "引擎通用（画布 / 输出 / 动态 / 角标）"

# 字体缺失时的回退优先序：只放内置且包含中文字形的字体，
# 避免回退到英文书法字体导致中文画成方框（tofu）。
PREFERRED_FALLBACK_FONTS = [
    "优设标题黑.ttf",
    "字魂白鸽天行体.ttf",
    "方正行楷_GBK.ttf",
    "HYZhuanShuF.ttf",
    "剑豪体.ttf",
    "叶根友毛笔行书.ttf",
    "字小魂扶摇手书.ttf",
    "字小魂京都和风体.ttf",
    "仓耳舒圆体W02.ttf",
    "杨任东竹石体.ttf",
    "汉仪雪峰体简.ttf",
    "熊兔流星体.ttf",
    "OPPOSans-H.ttf",
    "OPPOSans-M.ttf",
]


class PosterEngine:
    """把一段渲染配置 + 素材合成为封面图片。"""

    def __init__(self, plugin) -> None:
        self.data_path = assets_meta.data_root(plugin)
        self.fonts_dir = assets_meta.fonts_dir(plugin)
        self.layouts_dir = assets_meta.layouts_dir(plugin)
        self._layouts: Optional[Dict[str, Any]] = None
        self._img_cache: Dict[str, Image.Image] = {}
        self._imgcache_dir = Path(self.data_path) / "imgcache"
        self._http = None  # 惰性创建的会话（连接复用，逐张新建 TCP/TLS 太浪费）
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=8)

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
        """返回每个布局的展示名与分组参数字段（前端据此生成表单）。

        兼容两种 schema 写法：布局直接返回**分组列表**（ChillPoster 风格，
        ``[{"group": ..., "items": [...]}]``），或返回 ``{"fields": [...]}`` 时
        自动包裹成单个分组。
        """
        result: List[Dict[str, Any]] = []
        for name, module in self.layout_modules.items():
            schema = module.get_schema() if hasattr(module, "get_schema") else None
            groups: List[Dict[str, Any]] = []
            if isinstance(schema, list):
                groups = [item for item in schema if isinstance(item, dict)]
            elif isinstance(schema, dict):
                if isinstance(schema.get("groups"), list):
                    groups = [item for item in schema["groups"] if isinstance(item, dict)]
                elif isinstance(schema.get("fields"), list):
                    groups = [{"group": "参数", "items": schema["fields"]}]
            result.append({"name": name, "label": name, "groups": groups})
        return sorted(result, key=lambda item: item["name"])

    # -------------------------------------------------------------- 素材与字体

    def load_font(self, filename: Optional[str], size: int) -> ImageFont.FreeTypeFont:
        """按文件名加载字体；缺失时优先回退到内置中文字体，避免中文渲染成方框。"""
        size = max(1, int(size or 1))
        if filename:
            path = self.fonts_dir / str(filename)
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception as error:
                    logger.warning(f"[EmbyCoverCenter] 字体加载失败 {filename}: {error}")
        # 回退顺序：已知中文字体优先（英文字体无 CJK 字形会把中文画成方框），
        # 再退目录内任意字体，最后 PIL 默认字体。
        for name in PREFERRED_FALLBACK_FONTS:
            candidate = self.fonts_dir / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except Exception:
                    continue
        try:
            for item in sorted(self.fonts_dir.iterdir()):
                if item.is_file() and item.name.lower().endswith(assets_meta.FONT_EXTENSIONS):
                    return ImageFont.truetype(str(item), size)
        except Exception:
            pass
        return ImageFont.load_default()

    def _http_get(self, url: str):
        """经引擎级会话下载（连接复用）；会话创建失败则退回临时实例。"""
        if self._http is None:
            from app.sdk.network import RequestUtils

            self._http = RequestUtils(timeout=12)
        return self._http.get_res(url=url)

    def _disk_cache_path(self, url: str) -> Path:
        return self._imgcache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".img")

    def _disk_get(self, url: str) -> Optional[Image.Image]:
        """读磁盘缓存；任何异常都视为未命中（缓存绝不阻塞渲染）。"""
        try:
            path = self._disk_cache_path(url)
            if path.exists():
                with path.open("rb") as handle:
                    return Image.open(handle).convert("RGBA")
        except Exception:
            return None
        return None

    def _disk_put(self, url: str, data: bytes) -> None:
        """写磁盘缓存（临时文件 + 原子替换），超上限时按 mtime 淘汰最旧文件。"""
        try:
            self._imgcache_dir.mkdir(parents=True, exist_ok=True)
            path = self._disk_cache_path(url)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, path)
            files = [item for item in self._imgcache_dir.glob("*.img")]
            if len(files) > IMG_DISK_CACHE_MAX:
                for stale in sorted(files, key=lambda item: item.stat().st_mtime)[: len(files) - IMG_DISK_CACHE_MAX]:
                    try:
                        stale.unlink()
                    except OSError:
                        pass
        except Exception as error:  # pragma: no cover - 缓存写失败不影响渲染
            logger.debug(f"[EmbyCoverCenter] 素材磁盘缓存写入失败：{error}")

    def download_img(self, url: Optional[str]) -> Optional[Image.Image]:
        """下载素材图片（内存 + 磁盘两级缓存，线程安全）；失败返回 None。"""
        if not url:
            return None
        with self._lock:
            cached = self._img_cache.get(url)
        if cached is not None:
            return cached.copy()
        if not str(url).startswith("data:image"):
            img = self._disk_get(url)
            if img is not None:
                with self._lock:
                    self._img_cache[url] = img.copy()
                return img
        try:
            if str(url).startswith("data:image"):
                encoded = str(url).split(",", 1)[-1]
                img = Image.open(BytesIO(base64.b64decode(encoded, validate=False))).convert("RGBA")
            else:
                # 单张素材超时压到 12s：素材都很小，超时说明该地址不可达，
                # 让它尽早失败，别把整个预览拖到前端 20s 超时。
                res = self._http_get(url)
                if res is None or res.status_code != 200:
                    return None
                self._disk_put(url, res.content)
                img = Image.open(BytesIO(res.content)).convert("RGBA")
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 下载素材失败 {str(url)[:80]}: {error}")
            return None
        with self._lock:
            if len(self._img_cache) >= IMG_CACHE_MAX:
                self._img_cache.pop(next(iter(self._img_cache)), None)
            self._img_cache[url] = img.copy()
        return img

    def prefetch(self, urls: Optional[List[str]]) -> None:
        """并行预热素材图片缓存。

        封面预览的主要耗时是**串行下载素材**（海报墙预设一次要 40 张），
        串行太慢会撞上反向代理读超时（表现为 502），这里改成并行。
        """
        targets = [url for url in dict.fromkeys(urls or []) if url and url not in self._img_cache]
        if not targets:
            return
        try:
            list(self._executor.map(self.download_img, targets))
        except Exception as error:  # pragma: no cover - 预热失败不影响渲染
            logger.warning(f"[EmbyCoverCenter] 素材预取失败: {error}")

    def close(self) -> None:
        """释放线程池与图片缓存（stop_service 调用）。"""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        self._img_cache.clear()

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

    def create_smart_mask(
        self,
        width: int,
        height: int,
        opacity: int,
        coverage_percent: int,
        direction: str = "horizontal",
    ) -> Image.Image:
        """生成渐变遮罩，供布局叠加压暗层。

        ``direction`` 四个取值（“黑”= 遮罩最浓、“亮”= 完全透明）：

        - ``horizontal``：左黑右亮（默认，文字压在左边时用）
        - ``horizontal_reverse``：右黑左亮
        - ``vertical``：下黑上亮（历史行为，保持输出不变）
        - ``vertical_reverse``：上黑下亮

        兼容别名：``right``/``left`` 归到水平，``top``/``bottom`` 归到垂直。
        """
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        key = str(direction or "horizontal").strip().lower()
        coverage = max(0.0, min(100.0, float(coverage_percent or 0))) / 100.0

        def _curve(value: float) -> float:
            """smoothstep：两端导数为 0，渐变起止处不会留下一条可见的直边。"""
            value = max(0.0, min(1.0, value))
            return value * value * (3.0 - 2.0 * value)

        if key in ("vertical", "vertical_reverse", "top", "bottom"):
            # 垂直：coverage 是渐变占画布高度的比例。
            span = int(height * coverage)
            if span <= 0:
                return mask
            # vertical / bottom：下黑上亮（y=height 最浓，y<=height-span 全透明）
            # vertical_reverse / top：上黑下亮
            from_top = key in ("vertical_reverse", "top")
            for y in range(height):
                if from_top:
                    ratio = (height - y) / span if y >= height - span else 1.0
                else:
                    ratio = (y - (height - span)) / span if y >= height - span else 0.0
                alpha = int(opacity * _curve(ratio))
                draw.line([(0, y), (width, y)], fill=alpha)
        else:
            span = int(width * coverage)
            if span <= 0:
                return mask
            # horizontal：左浓右淡；horizontal_reverse：右浓左淡。
            # 两个方向必须是严格的镜像关系：``coverage`` 表示「渐变占了多宽的边」，
            # 因此 reverse 的渐变带贴在右边缘，左侧 (1-coverage) 的部分完全透明。
            reverse = key in ("horizontal_reverse", "right", "right_to_left")
            for x in range(width):
                offset = (width - 1 - x) if reverse else x
                ratio = offset / span if offset <= span else 1.0
                draw.line([(x, 0), (x, height)], fill=int(opacity * (1.0 - _curve(ratio))))
        return mask

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
        # 防御：字色与底色过近（如模板误配成白底白字）时数字会不可见，
        # 按底色亮度自动改用深/浅字色。
        try:
            tr, tg, tb = ImageColor.getrgb(text_color)
            lum_bg = (0.299 * fill_color[0] + 0.587 * fill_color[1] + 0.114 * fill_color[2]) / 255
            lum_tx = (0.299 * tr + 0.587 * tg + 0.114 * tb) / 255
            if abs(lum_bg - lum_tx) < 0.35:
                text_color = "#0f172a" if lum_bg > 0.5 else "#ffffff"
        except Exception:
            pass

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

    @staticmethod
    def _mean_luma(img: Image.Image) -> float:
        """缩略图平均亮度（0-255），用于检测近黑背景。"""
        small = img.convert("L").resize((32, 18))
        pixels = list(small.getdata())
        return sum(pixels) / max(1, len(pixels))

    def _keyart_size_hint(self, config: Dict[str, Any]) -> Optional[tuple]:
        """尽量取到用户主视觉的原图尺寸（``canvas_preset=auto`` 用）。

        这里只做**只读探测**：取不到（没配、文件不在、下载失败）就返回 None，
        由调用方退回 1920×1080，绝不影响正常渲染。
        """
        reference = str(config.get("keyart_url") or "").strip()
        image = None
        if reference:
            image = self.download_img(reference)
        if image is None:
            name = str(config.get("keyart_file") or "").strip()
            if name and not any(token in name for token in ("..", "/", "\\", ":", "|")) and not name.startswith("."):
                candidate = Path(self.data_path) / "keyart" / name
                if candidate.is_file():
                    try:
                        with Image.open(candidate) as probe:
                            return probe.size
                    except Exception:
                        return None
        return image.size if image is not None else None

    @staticmethod
    def _positive_int(value: Any, fallback: int) -> int:
        """宽容地把配置值转成正整数（前端可能传 ``""`` / ``"abc"`` / ``None``）。"""
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            return fallback
        return number if number > 0 else fallback

    def resolve_canvas(self, config: Dict[str, Any]) -> tuple:
        """按 ``canvas_preset`` 决定画布尺寸：自动跟随主视觉 / 预设 / 自定义。"""
        preset = str(config.get("canvas_preset") or "auto").strip().lower()
        size = None
        if preset in CANVAS_PRESETS:
            size = CANVAS_PRESETS[preset]
        elif preset == "custom":
            size = (
                self._positive_int(config.get("canvas_width"), 1920),
                self._positive_int(config.get("canvas_height"), 1080),
            )
        else:
            size = self._keyart_size_hint(config)
            if size is None:
                size = (
                    self._positive_int(config.get("canvas_width"), 1920),
                    self._positive_int(config.get("canvas_height"), 1080),
                )
        width = max(1, min(MAX_CANVAS_SIDE, self._positive_int(size[0], 1920)))
        height = max(1, min(MAX_CANVAS_SIDE, self._positive_int(size[1], 1080)))
        # 编码器对奇数边长不友好（JPEG 会多一行黑边），统一取偶。
        return (width - width % 2, height - height % 2)

    def _build_background(self, config: Dict[str, Any], assets: Dict[str, Any], size: tuple) -> Image.Image:
        canvas_w, canvas_h = size
        posters = [url for url in (assets.get("posters") or []) if url]
        bg = self.download_img(assets.get("bg_url"))
        if bg is None and posters:
            # 媒体库没有 backdrop（或下载失败）时用首张海报兜底，
            # 避免整张封面只剩纯色底。
            bg = self.download_img(posters[0])
        if bg is None:
            bg = Image.new("RGBA", (canvas_w, canvas_h), (20, 30, 50, 255))
        else:
            if bg.size != (canvas_w, canvas_h):
                bg = ImageOps.fit(bg, (canvas_w, canvas_h), method=Image.LANCZOS)
            # 背景过暗（暗色主题图/近黑图）时尝试换更亮的海报。
            if self._mean_luma(bg) < 26 and posters:
                alt = self.download_img(posters[0])
                if alt is not None:
                    alt = ImageOps.fit(alt, (canvas_w, canvas_h), method=Image.LANCZOS)
                    if self._mean_luma(alt) > self._mean_luma(bg):
                        bg = alt
        # 布局普遍使用 Image.alpha_composite，背景必须统一 RGBA。
        if bg.mode != "RGBA":
            bg = bg.convert("RGBA")
        blur = int(config.get("blur_radius") or 0)
        if blur > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(blur))
        try:
            bg = ImageEnhance.Brightness(bg).enhance(float(config.get("brightness") or 1))
        except Exception:
            pass
        return bg

    def build_background_for_layout(self, config, assets, size):
        """供布局的 render_anim 构建与 _render_frame 完全一致的基底背景。"""
        return self._build_background(config, assets, size)

    def _render_frame(
        self,
        config: Dict[str, Any],
        assets: Dict[str, Any],
        fonts: Dict[str, Any],
        step: Optional[float] = None,
    ) -> Image.Image:
        canvas_w, canvas_h = self.resolve_canvas(config)
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
        title_font = self.load_font(config.get("font_title"), int(config.get("title_size") or 160))
        subtitle_font = self.load_font(config.get("font_subtitle"), int(config.get("subtitle_size") or 80))
        badge_font = self.load_font(config.get("badge_font"), int(config.get("count_size") or 40))
        fonts: Dict[str, Any] = {"main": title_font, "sub": subtitle_font, "count": badge_font}
        # 兼容按**字体文件名**取字体（部分布局用 fonts.get("剑豪体.ttf") 之类的写法）。
        for key, font in (
            (config.get("font_title"), title_font),
            (config.get("font_subtitle"), subtitle_font),
            (config.get("badge_font"), badge_font),
            (config.get("font_count"), badge_font),
        ):
            if key:
                fonts.setdefault(str(key), font)
        output = BytesIO()

        # 并行预取本轮要用的素材，避免串行下载拖到网关读超时。
        t0 = time.perf_counter()
        self.prefetch(
            [assets.get("bg_url")]
            + list(assets.get("backdrops") or [])
            + list(assets.get("posters") or [])
        )
        t_prefetch = time.perf_counter()

        if config.get("enable_animation"):
            total_frames = max(2, min(int(config.get("anim_frames") or 30), ANIM_MAX_FRAMES))
            duration = max(20, int(config.get("anim_duration") or 100))
            target_h = max(1, int(ANIM_TARGET_WIDTH * 9 / 16))
            frames: List[Image.Image] = []
            layout = str(config.get("engine") or config.get("cover_layout") or DEFAULT_ENGINE)
            render = self.layout_modules.get(layout) or self.layout_modules.get(DEFAULT_ENGINE)
            if render is not None and hasattr(render, "render_anim"):
                # 布局自带动画快速通道：素材与基底只处理一次，逐帧只做位移合成。
                # sink 先画角标再缩到输出尺寸，全尺寸帧不驻留内存。
                def _sink(raw_frame: Image.Image) -> None:
                    frame = self._draw_badge(raw_frame, config, assets.get("count"))
                    frames.append(frame.convert("RGBA").resize((ANIM_TARGET_WIDTH, target_h), Image.LANCZOS))

                render.render_anim(self, config, assets, fonts, _sink)
            if not frames:
                # 兼容未实现 render_anim 的布局：逐帧全量渲染（慢，仅兜底）。
                for index in range(total_frames):
                    step = index / float(total_frames - 1) if total_frames > 1 else 0.0
                    frame = self._render_frame(config, assets, fonts, step=step)
                    frame = frame.convert("RGBA").resize((ANIM_TARGET_WIDTH, target_h), Image.LANCZOS)
                    frames.append(frame)
            frames[0].save(
                output, format="PNG", save_all=True, append_images=frames[1:],
                duration=duration, loop=0, optimize=False,
            )
            mode = f"动画×{len(frames)}帧"
        else:
            frame = self._render_frame(config, assets, fonts).convert("RGB")
            out_w = int(config.get("output_width") or 0)
            out_h = int(config.get("output_height") or 0)
            if out_w > 0 and out_h > 0 and frame.size != (out_w, out_h):
                frame = frame.resize((out_w, out_h), Image.LANCZOS)
            # 画质：默认 95 且关闭色度抽样，2K/4K 输出不会被再压一道；
            # 只有用户显式调低才降质（老配置里没有这个键，按 95 走）。
            try:
                quality = int(config.get("output_quality") or 95)
            except (TypeError, ValueError):
                quality = 95
            quality = max(60, min(100, quality))
            frame.save(
                output,
                format="JPEG",
                quality=quality,
                subsampling=0 if quality >= 90 else 2,
                optimize=False,
            )
            mode = "静态"

        # 这里**不清空**图片缓存：素材元数据有 120s 短缓存，同一批 URL 在缓存期内
        # 多次预览可命中，避免「改一个参数就重新下载几十张海报」把预览拖过 20s 超时。
        # 缓存由 IMG_CACHE_MAX 做 LRU 上限、由 close() 在插件停止时释放。
        logger.info(
            "[EmbyCoverCenter] 渲染完成：%s，素材预取 %.1fs，渲染+编码 %.1fs",
            mode,
            t_prefetch - t0,
            time.perf_counter() - t_prefetch,
        )
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
