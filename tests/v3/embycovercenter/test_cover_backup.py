"""cover_backup：原版封面备份 / 列表 / 恢复 / 版本裁剪。"""
import base64
import sys
from pathlib import Path

import pytest

from app.plugins.embycovercenter.service import cover_backup
from app.plugins.embycovercenter.service.emby_gateway import GatewayError


class _FakePlugin:
    """cover_backup 只依赖 _config / get_data_path。"""

    def __init__(self, config=None, data_path=None):
        self._config = dict(config or {})
        self._data_path = Path(data_path or ".")

    @property
    def config(self):
        return self._config

    def get_data_path(self):
        return self._data_path


@pytest.fixture()
def _png_bytes():
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_backup_library_saves_and_lists(tmp_path, monkeypatch, _png_bytes):
    plugin = _FakePlugin(data_path=tmp_path)
    target = {"server": "Emby", "ref": object(), "library_id": "lib1", "name": "电影"}
    monkeypatch.setattr(cover_backup.emby_gateway, "get_raw", lambda ref, path, query=None: _png_bytes)

    saved = cover_backup.backup_library(plugin, target, {})
    assert saved is not None and saved.exists()

    backups = cover_backup.list_backups(plugin)
    assert len(backups) == 1
    item = backups[0]
    assert item["server"] == "Emby" and item["library_id"] == "lib1" and item["library_name"] == "电影"
    assert len(item["versions"]) == 1
    assert item["versions"][0]["size"] == len(_png_bytes)


def test_backup_library_skips_when_no_cover(tmp_path, monkeypatch):
    plugin = _FakePlugin(data_path=tmp_path)
    target = {"server": "Emby", "ref": object(), "library_id": "lib1", "name": "电影"}
    monkeypatch.setattr(cover_backup.emby_gateway, "get_raw", lambda ref, path, query=None: None)
    assert cover_backup.backup_library(plugin, target, {}) is None
    assert cover_backup.list_backups(plugin) == []


def test_backup_library_disabled_by_config(tmp_path, monkeypatch, _png_bytes):
    plugin = _FakePlugin({"auto_backup_enabled": False}, data_path=tmp_path)
    target = {"server": "Emby", "ref": object(), "library_id": "lib1", "name": "电影"}
    monkeypatch.setattr(cover_backup.emby_gateway, "get_raw", lambda ref, path, query=None: _png_bytes)
    assert cover_backup.backup_library(plugin, target, plugin.config) is None


def test_backup_library_failure_does_not_raise(tmp_path, monkeypatch):
    """备份失败（网络等）绝不阻断封面上传主流程，只返回 None。"""
    plugin = _FakePlugin(data_path=tmp_path)
    target = {"server": "Emby", "ref": object(), "library_id": "lib1", "name": "电影"}

    def _boom(ref, path, query=None):
        raise GatewayError("HTTP 502")

    monkeypatch.setattr(cover_backup.emby_gateway, "get_raw", _boom)
    assert cover_backup.backup_library(plugin, target, {}) is None


def test_backup_prunes_to_keep_limit(tmp_path, _png_bytes):
    """超过 BACKUP_KEEP 版时按时间戳淘汰最旧版本。"""
    plugin = _FakePlugin(data_path=tmp_path)
    stamps = ["20260101-000001", "20260101-000002", "20260101-000003", "20260101-000004"]
    directory = cover_backup._library_dir(plugin, "Emby", "lib1")
    directory.mkdir(parents=True, exist_ok=True)
    for stamp in stamps:
        (directory / f"{stamp}.jpg").write_bytes(_png_bytes)

    cover_backup._prune_versions(directory)
    names = sorted(path.stem for path in directory.glob("*.jpg"))
    assert names == stamps[-cover_backup.BACKUP_KEEP:]


def test_restore_uses_latest_or_given_version(tmp_path, monkeypatch, _png_bytes):
    plugin = _FakePlugin(data_path=tmp_path)
    directory = cover_backup._library_dir(plugin, "Emby", "lib1")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "20260101-000001.jpg").write_bytes(_png_bytes)
    (directory / "20260101-000002.jpg").write_bytes(_png_bytes)

    uploaded = []
    monkeypatch.setattr(cover_backup.emby_gateway, "resolve", lambda server: object())
    monkeypatch.setattr(
        cover_backup.emby_gateway,
        "post_raw",
        lambda ref, path, data, content_type, query=None: uploaded.append((path, data, content_type)),
    )

    cover_backup.restore_library(plugin, "Emby", "lib1", "")
    assert uploaded[0][0] == "Items/lib1/Images/Primary"
    assert base64.b64decode(uploaded[0][1]) == _png_bytes  # base64 原样可解

    cover_backup.restore_library(plugin, "Emby", "lib1", "20260101-000001")
    assert uploaded[1][0] == "Items/lib1/Images/Primary"


def test_restore_missing_backup_raises_value_error(tmp_path):
    plugin = _FakePlugin(data_path=tmp_path)
    with pytest.raises(ValueError):
        cover_backup.restore_library(plugin, "Emby", "lib404", "")


def test_backup_thumb_returns_data_uri(tmp_path, _png_bytes):
    """缩略图：真实 JPEG 备份 → data URI；缺文件 → None。"""
    from io import BytesIO

    from PIL import Image

    plugin = _FakePlugin(data_path=tmp_path)
    # 生成一张 64x32 的真 JPEG 备份（PNG 字节无法被 PIL 按 JPEG 解码校验）
    directory = cover_backup._library_dir(plugin, "Emby", "lib1")
    directory.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    Image.new("RGB", (64, 32), color=(200, 100, 50)).save(buffer, format="JPEG")
    (directory / "20260101-000001.jpg").write_bytes(buffer.getvalue())

    uri = cover_backup.backup_thumb(plugin, "Emby", "lib1", "20260101-000001")
    assert uri and uri.startswith("data:image/jpeg;base64,")

    # 不带 timestamp → 取最新一版；不存在的库 → None
    assert cover_backup.backup_thumb(plugin, "Emby", "lib1", "").startswith("data:image/jpeg")
    assert cover_backup.backup_thumb(plugin, "Emby", "lib404", "") is None
