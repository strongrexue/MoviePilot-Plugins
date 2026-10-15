"""封面备份 / 恢复：自动封面覆盖上传前，先把媒体库当前原版封面存到数据目录。

目录布局：``<数据目录>/backups/<服务器名>/<库ID>/<时间戳>.jpg``，同目录
``meta.json`` 记录库名等展示信息；每库只保留最近 ``BACKUP_KEEP`` 版（按时间戳
文件名排序淘汰），避免长期膨胀。备份失败只记日志，绝不阻断封面上传主流程。
"""
from __future__ import annotations

import base64
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from . import assets_meta, emby_gateway
from .emby_gateway import GatewayError

# 每个媒体库保留的备份版本数（含最新一版）。
BACKUP_KEEP = 3
# 备份目录名（位于插件数据目录下）。
BACKUP_DIRNAME = "backups"


def backups_root(plugin) -> Path:
    return Path(assets_meta.data_root(plugin)) / BACKUP_DIRNAME


def _library_dir(plugin, server: str, library_id: str) -> Path:
    safe_server = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in str(server or "默认"))
    safe_library = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in str(library_id or "unknown"))
    return backups_root(plugin) / safe_server / safe_library


def _meta_path(directory: Path) -> Path:
    return directory / "meta.json"


def backup_library(plugin, target: Dict[str, Any], config: Dict[str, Any]) -> Optional[Path]:
    """上传前备份媒体库当前 Primary 封面。

    - ``auto_backup_enabled`` 关闭时直接跳过；
    - 媒体库当前没有封面（HTTP 404）视为无备份需求，静默返回；
    - 任何失败只记日志返回 None，不阻断封面上传。

    :returns: 备份文件路径（未备份时为 None）。
    """
    if not config.get("auto_backup_enabled", True):
        return None
    ref = target.get("ref")
    server = str(target.get("server") or "")
    library_id = str(target.get("library_id") or "")
    library_name = str(target.get("name") or library_id)
    if ref is None or not library_id:
        return None
    try:
        data = emby_gateway.get_raw(ref, f"Items/{library_id}/Images/Primary")
        if not data:
            return None
        directory = _library_dir(plugin, server, library_id)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        image_path = directory / f"{stamp}.jpg"
        image_path.write_bytes(data)
        _write_meta(directory, library_name)
        _prune_versions(directory)
        logger.info(f"[EmbyCoverCenter] 已备份原版封面：{server} / {library_name} → {image_path.name}")
        return image_path
    except (GatewayError, OSError) as error:  # 备份失败绝不阻断封面更新
        logger.warning(f"[EmbyCoverCenter] 备份原版封面失败 {server} / {library_name}：{error}")
        return None
    except Exception as error:  # pragma: no cover - 其余异常同样不阻断
        logger.warning(f"[EmbyCoverCenter] 备份原版封面异常 {server} / {library_name}：{error}")
        return None


def _write_meta(directory: Path, library_name: str) -> None:
    """写/补 meta.json（只补缺失字段，不覆盖已有展示信息）。"""
    meta_path = _meta_path(directory)
    meta: Dict[str, Any] = {}
    try:
        if meta_path.exists():
            import json

            meta = dict(json.loads(meta_path.read_text(encoding="utf-8")) or {})
    except Exception:
        meta = {}
    if library_name and not meta.get("library_name"):
        meta["library_name"] = library_name
    try:
        import json

        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _prune_versions(directory: Path) -> None:
    """按文件名（时间戳）只保留最近 BACKUP_KEEP 版。"""
    versions = sorted(directory.glob("*.jpg"))
    for stale in versions[:-BACKUP_KEEP] if len(versions) > BACKUP_KEEP else []:
        try:
            stale.unlink()
        except OSError:
            pass


def list_backups(plugin) -> List[Dict[str, Any]]:
    """返回全部备份：``[{server, library_id, library_name, versions: [...]}]``。"""
    root = backups_root(plugin)
    result: List[Dict[str, Any]] = []
    if not root.exists():
        return result
    import json

    for library_dir in sorted(root.iterdir()):
        if not library_dir.is_dir():
            continue
        for version_dir in sorted(library_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            versions: List[Dict[str, Any]] = []
            for image in sorted(version_dir.glob("*.jpg"), reverse=True):
                versions.append(
                    {
                        "timestamp": image.stem,
                        "size": image.stat().st_size,
                        "filename": image.name,
                    }
                )
            if not versions:
                continue
            library_name = ""
            try:
                meta = json.loads(_meta_path(version_dir).read_text(encoding="utf-8"))
                library_name = str((meta or {}).get("library_name") or "")
            except Exception:
                library_name = ""
            result.append(
                {
                    "server": library_dir.name,
                    "library_id": version_dir.name,
                    "library_name": library_name or version_dir.name,
                    "versions": versions,
                }
            )
    return result


def restore_library(plugin, server: str, library_id: str, timestamp: str = "") -> None:
    """把备份封面写回媒体库 Primary；timestamp 为空用最新一版。

    :raises ValueError: 备份不存在。
    :raises GatewayError: 上传失败。
    """
    from .render_engine import PosterEngine

    directory = _library_dir(plugin, server, library_id)
    image_path: Optional[Path] = None
    if timestamp:
        candidate = directory / f"{timestamp}.jpg"
        image_path = candidate if candidate.exists() else None
    else:
        versions = sorted(directory.glob("*.jpg"), reverse=True)
        image_path = versions[0] if versions else None
    if image_path is None:
        raise ValueError("备份不存在或已被清理")
    ref = emby_gateway.resolve(server)
    data = image_path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    emby_gateway.post_raw(
        ref,
        f"Items/{library_id}/Images/Primary",
        data=encoded,
        content_type="image/jpeg",
    )
    logger.info(f"[EmbyCoverCenter] 已从备份恢复封面：{server} / {library_id} ← {image_path.name}")


def delete_backups(plugin, server: str = "", library_id: str = "") -> int:
    """删除备份（指定库删该库，否则删整台服务器；均未指定清空全部）。"""
    root = backups_root(plugin)
    if not root.exists():
        return 0
    if server and library_id:
        target = _library_dir(plugin, server, library_id)
    elif server:
        target = root / _safe_component(server)
    else:
        target = root
    if not target.exists():
        return 0
    count = sum(1 for _ in target.rglob("*.jpg"))
    shutil.rmtree(target, ignore_errors=True)
    return count


def _safe_component(text: str) -> str:
    return "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in str(text or ""))
