"""emby_gateway.list_servers 的服务器类型过滤测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.plugins.embycovercenter.service import emby_gateway


class _Instance:
    def __init__(self, inactive=False):
        self._inactive = inactive

    def is_inactive(self):
        return self._inactive


class _Service:
    def __init__(self, type_name, inactive=False):
        self.type = type_name
        self.instance = _Instance(inactive)


class _FakeHelper:
    def __init__(self, services):
        self._services = services

    def get_services(self):
        return self._services


def test_list_servers_filters_unsupported_types(monkeypatch):
    """飞牛影视（trimemedia）等未适配类型不出现在服务器列表里。"""
    services = {
        "115emby": _Service("emby"),
        "homejelly": _Service("jellyfin"),
        "飞牛": _Service("trimemedia"),
        "plex": _Service("plex"),
    }
    monkeypatch.setattr(emby_gateway, "_helper", lambda: _FakeHelper(services))

    names = [s["name"] for s in emby_gateway.list_servers()]

    assert names == ["115emby", "homejelly"]


def test_list_servers_reports_active_state(monkeypatch):
    """保留的 emby/jellyfin 条目仍按实例状态给出 active。"""
    services = {
        "115emby": _Service("emby", inactive=True),
        "homejelly": _Service("jellyfin"),
    }
    monkeypatch.setattr(emby_gateway, "_helper", lambda: _FakeHelper(services))

    servers = emby_gateway.list_servers()

    assert {s["name"]: s["active"] for s in servers} == {"115emby": False, "homejelly": True}
