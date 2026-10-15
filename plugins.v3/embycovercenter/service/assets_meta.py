"""封面资源管理：字体、模板与数据目录。

运行期资源统一放在插件数据目录（``get_data_path()``），**不写回插件源码目录**
（更新时源码目录可能被替换）。所有对外暴露的文件名都做白名单校验，拒绝路径穿越。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

FONT_EXTENSIONS = (".ttf", ".otf", ".ttc")
TEMPLATE_EXTENSION = ".json"
PREVIEW_EXTENSION = ".jpg"
# 预览图最大边（等比缩放后保存）。
PREVIEW_MAX_SIDE = 640
# 随插件分发的默认资源目录（首次初始化时只补缺失，不覆盖用户文件）。
PACKAGE_DEFAULTS_DIR = Path(__file__).resolve().parent.parent / "defaults"


def data_root(plugin) -> Path:
    """插件数据目录（不存在时由基类创建）。"""
    return plugin.get_data_path()


def fonts_dir(plugin) -> Path:
    return data_root(plugin) / "fonts"


def templates_dir(plugin) -> Path:
    return data_root(plugin) / "templates"


def layouts_dir(plugin) -> Path:
    return data_root(plugin) / "layouts"


def ensure_dirs(plugin) -> None:
    """确保资源子目录存在（init_plugin 调用）。"""
    for path in (fonts_dir(plugin), templates_dir(plugin), layouts_dir(plugin)):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as error:  # pragma: no cover - 磁盘异常
            logger.error(f"[EmbyCoverCenter] 创建资源目录失败 {path}: {error}")


def seed_default_templates(plugin) -> int:
    """把随插件分发的默认模板（含预览缩略图）拷进数据目录（只补缺失，不覆盖用户文件）。"""
    source = PACKAGE_DEFAULTS_DIR / "templates"
    if not source.exists():
        return 0
    ensure_dirs(plugin)
    target = templates_dir(plugin)
    copied = 0
    for item in sorted(source.iterdir()):
        if not item.is_file() or item.suffix.lower() not in (TEMPLATE_EXTENSION, PREVIEW_EXTENSION):
            continue
        destination = target / item.name
        if destination.exists():
            continue
        try:
            destination.write_bytes(item.read_bytes())
            copied += 1
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 拷贝默认模板失败 {item.name}: {error}")
    copied += fix_known_template_bugs(plugin)
    return copied


# 内置模板的历史错误字段（仅当用户端文件仍是旧错误值时才修正，不动用户自定义内容）：
# - 旋转默认：角标白底白字，数字不可见；
# - 动态平铺：引用了不存在的字体文件名（内置字体无 "(商用需授权)" 后缀）。
TEMPLATE_FIELD_FIXES = {
    "旋转默认.json": (
        {"badge_bg_color": "#ffffff", "badge_text_color": "#ffffff"},
        {"badge_text_color": "#0f172a"},
    ),
    "动态平铺.json": (
        {"font_title": "字魂白鸽天行体(商用需授权).ttf"},
        {"font_title": "字魂白鸽天行体.ttf"},
    ),
}


def fix_known_template_bugs(plugin) -> int:
    """修正用户数据目录里内置模板的历史错误字段；返回修复文件数。"""
    import json

    target = templates_dir(plugin)
    fixed = 0
    for name, (old_values, new_values) in TEMPLATE_FIELD_FIXES.items():
        path = target / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            config = data.get("config")
            if not isinstance(config, dict):
                continue
            if not all(str(config.get(key)) == value for key, value in old_values.items()):
                continue  # 用户已自定义，跳过
            config.update(new_values)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            fixed += 1
            logger.info(f"[EmbyCoverCenter] 已修正内置模板历史问题：{name}")
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 修正模板失败 {name}: {error}")
    return fixed


def seed_default_fonts(plugin) -> int:
    """把随插件分发的默认字体包（ChillPoster 同款）拷进数据目录（只补缺失，不覆盖用户字体）。"""
    source = PACKAGE_DEFAULTS_DIR / "fonts"
    if not source.exists():
        return 0
    ensure_dirs(plugin)
    target = fonts_dir(plugin)
    copied = 0
    for item in sorted(source.iterdir()):
        if not item.is_file() or item.suffix.lower() not in FONT_EXTENSIONS:
            continue
        destination = target / item.name
        if destination.exists():
            continue
        try:
            destination.write_bytes(item.read_bytes())
            copied += 1
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 拷贝默认字体失败 {item.name}: {error}")
    return copied


def _safe_name(raw: Any, extensions: tuple) -> str:
    """校验文件名：只允许裸文件名且扩展名在白名单内。"""
    name = str(raw or "").strip()
    if not name:
        raise ValueError("文件名不能为空")
    if any(token in name for token in ("..", "/", "\\")) or name.startswith("."):
        raise ValueError(f"非法文件名：{name}")
    if extensions and not name.lower().endswith(extensions):
        raise ValueError(f"不支持的文件类型：{name}")
    return name


# --------------------------------------------------------------------------- 字体


def list_fonts(plugin) -> List[str]:
    """返回数据目录内可用的字体文件名。"""
    directory = fonts_dir(plugin)
    if not directory.exists():
        return []
    return sorted(
        item.name for item in directory.iterdir()
        if item.is_file() and item.name.lower().endswith(FONT_EXTENSIONS)
    )


def font_path(plugin, name: Any) -> Path:
    """返回字体的绝对路径（调用方需先完成文件名校验）。"""
    safe = _safe_name(name, FONT_EXTENSIONS)
    path = fonts_dir(plugin) / safe
    if not path.exists():
        raise ValueError(f"字体不存在：{safe}")
    return path


def save_font(plugin, name: Any, content: bytes) -> str:
    """保存上传的字体（base64 已在调用方解码）。"""
    if not content:
        raise ValueError("字体内容为空")
    safe = _safe_name(name, FONT_EXTENSIONS)
    ensure_dirs(plugin)
    (fonts_dir(plugin) / safe).write_bytes(content)
    return safe


def save_font_base64(plugin, name: Any, payload: str) -> str:
    """保存 base64 上传的字体。"""
    encoded = str(payload or "").split(",", 1)[-1]
    try:
        content = base64.b64decode(encoded, validate=False)
    except Exception as error:
        raise ValueError("字体 base64 解码失败") from error
    return save_font(plugin, name, content)


def delete_font(plugin, name: Any) -> bool:
    """删除字体文件。"""
    safe = _safe_name(name, FONT_EXTENSIONS)
    path = fonts_dir(plugin) / safe
    if not path.exists():
        return False
    path.unlink()
    return True


# --------------------------------------------------------------------------- 模板


def default_template_preview(name: Any) -> Optional[Path]:
    """插件包内随分发的默认模板缩略图（数据目录缺失时的兜底来源）。"""
    safe = _safe_name(name, (PREVIEW_EXTENSION,))
    path = PACKAGE_DEFAULTS_DIR / "templates" / safe
    return path if path.exists() else None


def list_templates(plugin) -> List[Dict[str, Any]]:
    """返回模板预设列表（含布局、参数与预览图标记）。"""
    directory = templates_dir(plugin)
    if not directory.exists():
        return []
    result: List[Dict[str, Any]] = []
    for item in sorted(directory.glob(f"*{TEMPLATE_EXTENSION}")):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 跳过损坏模板 {item.name}: {error}")
            continue
        preview = item.with_suffix(PREVIEW_EXTENSION)
        has_preview = preview.exists() or default_template_preview(preview.name) is not None
        result.append(
            {
                "filename": item.name,
                "name": str(data.get("name") or item.stem),
                "layout": str(data.get("layout") or "classic"),
                "config": data.get("config") if isinstance(data.get("config"), dict) else {},
                "has_preview": has_preview,
            }
        )
    return result


def read_template(plugin, filename: Any) -> Dict[str, Any]:
    """读取模板预设内容。"""
    safe = _safe_name(filename, (TEMPLATE_EXTENSION,))
    path = templates_dir(plugin) / safe
    if not path.exists():
        raise ValueError(f"模板不存在：{safe}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"模板内容不合法：{safe}")
    return data


def template_preview_path(plugin, filename: Any) -> Optional[Path]:
    """返回模板缩略图路径：优先数据目录，缺失时回退到插件包内的默认缩略图。"""
    safe = _safe_name(filename, (TEMPLATE_EXTENSION,))
    preview_name = str(Path(safe).with_suffix(PREVIEW_EXTENSION).name)
    local = templates_dir(plugin) / preview_name
    if local.exists():
        return local
    return default_template_preview(preview_name)


def save_template(
    plugin,
    filename: Any,
    *,
    layout: str,
    config: Dict[str, Any],
    name: str = "",
    preview_data_url: Optional[str] = None,
) -> Dict[str, Any]:
    """保存模板预设，并在提供预览图时落盘一张缩略图。"""
    safe = _safe_name(filename, (TEMPLATE_EXTENSION,))
    ensure_dirs(plugin)
    data = {
        "name": str(name or Path(safe).stem),
        "layout": str(layout or "classic"),
        "config": config if isinstance(config, dict) else {},
    }
    (templates_dir(plugin) / safe).write_text(
        json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    if preview_data_url:
        _save_preview(plugin, safe, preview_data_url)
    return {"filename": safe, **data}


def _save_preview(plugin, filename: str, preview_data_url: str) -> None:
    """把前端生成的 dataURL 存成模板缩略图；失败不影响模板保存。"""
    try:
        from io import BytesIO

        from PIL import Image

        encoded = str(preview_data_url).split(",", 1)[-1]
        raw = base64.b64decode(encoded, validate=False)
        with Image.open(BytesIO(raw)) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE))
            img.save((templates_dir(plugin) / filename).with_suffix(PREVIEW_EXTENSION), format="JPEG", quality=80)
    except Exception as error:
        logger.warning(f"[EmbyCoverCenter] 保存模板预览失败 {filename}: {error}")


def delete_template(plugin, filename: Any) -> bool:
    """删除模板与其预览图。"""
    safe = _safe_name(filename, (TEMPLATE_EXTENSION,))
    path = templates_dir(plugin) / safe
    existed = path.exists()
    if existed:
        path.unlink()
    preview = path.with_suffix(PREVIEW_EXTENSION)
    if preview.exists():
        preview.unlink()
    return existed


def save_template_base64(plugin, filename: Any, payload: str) -> str:
    """保存 base64 上传的模板 JSON。"""
    safe = _safe_name(filename, (TEMPLATE_EXTENSION,))
    encoded = str(payload or "").split(",", 1)[-1]
    try:
        raw = base64.b64decode(encoded, validate=False)
        data = json.loads(raw.decode("utf-8"))
    except Exception as error:
        raise ValueError("模板文件解析失败（需为 JSON）") from error
    if not isinstance(data, dict):
        raise ValueError("模板文件内容不合法")
    ensure_dirs(plugin)
    payload_data = {
        "name": str(data.get("name") or Path(safe).stem),
        "layout": str(data.get("layout") or "classic"),
        "config": data.get("config") if isinstance(data.get("config"), dict) else {},
    }
    (templates_dir(plugin) / safe).write_text(
        json.dumps(payload_data, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return safe
