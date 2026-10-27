"""封面资源管理：字体、模板与数据目录。

运行期资源统一放在插件数据目录（``get_data_path()``），**不写回插件源码目录**
（更新时源码目录可能被替换）。所有对外暴露的文件名都做白名单校验，拒绝路径穿越。
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

FONT_EXTENSIONS = (".ttf", ".otf", ".ttc")
TEMPLATE_EXTENSION = ".json"
PREVIEW_EXTENSION = ".jpg"
# 主视觉（keyart）只收常见位图：布局用 Pillow 打开，矢量 / 动图一律不认。
KEYART_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
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


def keyart_dir(plugin) -> Path:
    """主视觉（keyart）目录：布局 ``分类横幅`` 按裸文件名从这里取图。"""
    return data_root(plugin) / "keyart"


def ensure_dirs(plugin) -> None:
    """确保资源子目录存在（init_plugin 调用）。"""
    for path in (fonts_dir(plugin), templates_dir(plugin), layouts_dir(plugin), keyart_dir(plugin)):
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
    retire_legacy_templates(plugin)
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
    copied += rename_legacy_template_names(plugin)
    upgrade_shipped_templates(plugin)
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


# 内置模板显示名的历史命名（「xxx默认」「xxx预设」）统一去掉后缀，写进界面的就是布局本名。
# 只改用户数据目录里的 *显示名*，文件名保持不动 —— 文件名是模板的唯一标识，
# 已被 ``auto_cover_template`` 等配置引用，改名会让老用户的选择失效。
TEMPLATE_NAME_RENAMES = {
    "扇形展开默认.json": ("扇形展开默认", "扇形展开"),
    "斜线分割默认.json": ("斜线分割默认", "斜线分割"),
    "旋转默认.json": ("旋转默认", "旋转"),
    "旋转堆叠预设.json": ("旋转堆叠预设", "旋转堆叠"),
    "海报墙默认.json": ("海报墙默认", "海报墙"),
    "经典堆叠默认.json": ("经典堆叠默认", "经典堆叠"),
    "经典平铺默认.json": ("经典平铺默认", "经典平铺"),
    "聚焦默认.json": ("聚焦默认", "聚焦"),
    "荣耀视界默认.json": ("荣耀视界默认", "荣耀视界"),
}


def rename_legacy_template_names(plugin) -> int:
    """把内置模板的旧显示名改成布局本名；返回改动文件数。

    只修正 ``name`` 仍等于旧默认值的文件（即用户没改过名），
    用户自行重命名过的模板原样保留。老用户的模板文件在首次初始化时已拷进数据目录、
    之后不会被覆盖，所以这条迁移必须留在每次初始化都跑的路径里。
    """
    target = templates_dir(plugin)
    renamed = 0
    for filename, (old_name, new_name) in TEMPLATE_NAME_RENAMES.items():
        path = target / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or str(data.get("name") or "") != old_name:
                continue  # 用户已自定义名字，跳过
            data["name"] = new_name
            path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            renamed += 1
            logger.info(f"[EmbyCoverCenter] 已更新内置模板名：{old_name} → {new_name}")
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 更新模板名失败 {filename}: {error}")
    return renamed


def _template_digest(data: Dict[str, Any]) -> str:
    """模板内容指纹：名字 + 布局 + 配置（不含预览图与键顺序）。"""
    payload = json.dumps(
        {"name": data.get("name"), "layout": data.get("layout"), "config": data.get("config")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# 1.6.23 一次性铺开的 6 套「分类横幅」预设，1.6.24 收成单套；老用户数据目录里
# 已经拷过这些文件，只靠「补缺失」清不掉，所以按内容指纹精确回收。
# 1.6.26 起「暗场右文」预设也下线（布局模块保留，用户自建模板仍可用它）。
RETIRED_TEMPLATES = {
    "分类横幅-暖金.json": "49ad552d4d9372e6ce8af67b1b0506d8a7cc6fcdd365cac288db9885901431d9",
    "分类横幅-冷蓝.json": "7e1c97d3ccd29d3aada0f142b8eecd4abda32430e422d417daaae74cd705e460",
    "分类横幅-朱红.json": "9979c46144f92440644084f6095cce9021436fa28b00bbb0e52dc67360ffb4a6",
    "分类横幅-左对齐.json": "5db7a383365f3c6cea8b83e3c7a2d6e138326624326e1f0c08f24c0722c20c5c",
    "分类横幅-海报阵列.json": "1bc3e53879e8ca44be9be95c652208f8ee6ebbc10d53cc9d16201f1dd98b4607",
    "分类横幅-无压暗全幅.json": "7c5c746cc87cbe9f1ea149a50513b3aa745a8855e1f41160b5db4abdede61107",
    "暗场右文.json": "aef05ccba607e529845cfafeef4335ebc5cc931027782848787e29dc53be3e97",
}


def retire_legacy_templates(plugin) -> int:
    """回收已下线的内置预设（连同缩略图）；返回删除的模板数。

    只在内容指纹仍等于发行时那一版时才删：用户改过配置或改过名就原样保留，
    不碰自定义模板。
    """
    target = templates_dir(plugin)
    removed = 0
    for filename, digest in RETIRED_TEMPLATES.items():
        path = target / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or _template_digest(data) != digest:
                continue  # 用户已自定义，跳过
            path.unlink()
            preview = path.with_suffix(PREVIEW_EXTENSION)
            if preview.exists():
                preview.unlink()
            removed += 1
            logger.info(f"[EmbyCoverCenter] 已移除过时的内置预设：{filename}")
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 移除内置预设失败 {filename}: {error}")
    return removed


# 内置预设「原地升级」：数据目录里的文件只在首次初始化时拷一次，之后只补缺失，
# 所以插件升级时老用户拿到的还是旧配置、旧缩略图（界面上就是「缩略图没变」）。
# 这里登记历代发行版的模板内容指纹：指纹仍命中说明用户没改过，整体换成新版
# （json + 缩略图一起换）；改过配置的保持原样，不碰用户数据。
SHIPPED_TEMPLATE_HISTORY = {
    "分类横幅.json": {
        "a2a8f578e7e6a4dc5437c833dd447c3f47251f17303a928a371896e10e6c298e",  # 1.6.24
        "325ccc52e84786261c94ee9b07072f38ceb8beaad84088abce65b470e584a95c",  # 1.6.25
        "2cb529284350541a43c72c48ce8ec9990d171af8cbddf79c48f610296cb7863a",  # 1.6.26
        "ef7a582c506e384cbac56ea3645e04d0aa9e207f2e37b68a2f52b0c17116852c",  # 1.6.27
        "e03a6ec0ecf7e075e0dfadad45e9b8d7b45cc1220d14c0c4007d813af9d52fc6",  # 1.6.27 发布版
    },
}


def upgrade_shipped_templates(plugin) -> int:
    """把未被用户改动过的内置预设升级到本版随包版本（含缩略图）；返回升级数量。

    两种情况会触发升级：``json`` 指纹命中历史发行版，或 ``json`` 已是最新版
    但缩略图与随包版本字节不一致（老装机「缩略图没变」就是后者）。缩略图字节
    相同则不写盘，避免无谓 IO。
    """
    source = PACKAGE_DEFAULTS_DIR / "templates"
    if not source.exists():
        return 0
    target = templates_dir(plugin)
    upgraded = 0
    for filename, history in SHIPPED_TEMPLATE_HISTORY.items():
        packaged = source / filename
        path = target / filename
        if not packaged.exists() or not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            digest = _template_digest(data)
            packaged_data = json.loads(packaged.read_text(encoding="utf-8"))
            packaged_digest = _template_digest(packaged_data) if isinstance(packaged_data, dict) else ""
            if digest != packaged_digest and digest not in history:
                continue  # 用户已自定义，跳过
            changed = False
            if digest != packaged_digest:
                path.write_bytes(packaged.read_bytes())
                changed = True
            preview_name = path.with_suffix(PREVIEW_EXTENSION).name
            packaged_preview = source / preview_name
            if packaged_preview.exists():
                local_preview = target / preview_name
                if not local_preview.exists() or local_preview.read_bytes() != packaged_preview.read_bytes():
                    local_preview.write_bytes(packaged_preview.read_bytes())
                    changed = True
            if not changed:
                continue
            upgraded += 1
            logger.info(f"[EmbyCoverCenter] 已更新内置预设：{filename}")
        except Exception as error:
            logger.warning(f"[EmbyCoverCenter] 更新内置预设失败 {filename}: {error}")
    return upgraded


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


# --------------------------------------------------------------------------- 主视觉


def list_keyart(plugin) -> List[str]:
    """返回数据目录内已上传的主视觉文件名（按名称排序）。"""
    directory = keyart_dir(plugin)
    if not directory.exists():
        return []
    return sorted(
        item.name for item in directory.iterdir()
        if item.is_file() and item.name.lower().endswith(KEYART_EXTENSIONS)
    )


def keyart_path(plugin, name: Any) -> Path:
    """返回主视觉的绝对路径（调用方需先完成文件名校验）。"""
    safe = _safe_name(name, KEYART_EXTENSIONS)
    path = keyart_dir(plugin) / safe
    if not path.exists():
        raise ValueError(f"主视觉不存在：{safe}")
    return path


def save_keyart(plugin, name: Any, content: bytes) -> str:
    """保存上传的主视觉（base64 已在调用方解码）。"""
    if not content:
        raise ValueError("主视觉内容为空")
    safe = _safe_name(name, KEYART_EXTENSIONS)
    ensure_dirs(plugin)
    (keyart_dir(plugin) / safe).write_bytes(content)
    return safe


def save_keyart_base64(plugin, name: Any, payload: str) -> str:
    """保存 base64 上传的主视觉；顺便校验确实是可解析的位图。"""
    encoded = str(payload or "").split(",", 1)[-1]
    try:
        content = base64.b64decode(encoded, validate=False)
    except Exception as error:
        raise ValueError("主视觉 base64 解码失败") from error
    if not content:
        raise ValueError("主视觉内容为空")
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(content)) as probe:
            probe.verify()
    except Exception as error:
        raise ValueError("主视觉不是有效的图片文件") from error
    return save_keyart(plugin, name, content)


def delete_keyart(plugin, name: Any) -> bool:
    """删除主视觉文件。"""
    safe = _safe_name(name, KEYART_EXTENSIONS)
    path = keyart_dir(plugin) / safe
    if not path.exists():
        return False
    path.unlink()
    return True
