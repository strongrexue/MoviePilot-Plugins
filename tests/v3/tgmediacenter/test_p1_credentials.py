"""P1（TG 核心凭证）单元测试。

覆盖不依赖网络的纯逻辑：代理解析、敏感值掩码、对话归一，以及 API 路由合同。
需要网络的登录流程不做自动化测试，改由真实加载验证（见设计文档 P1 验收）。
"""
from app.plugins.tgmediacenter.controller import api as api_controller
from app.plugins.tgmediacenter.utils import (
    mask_secret,
    normalize_dialog,
    parse_proxy_for_telethon,
)


# --------------------------------------------------------------------- 代理解析


def test_parse_proxy_http():
    """http 代理应转换为 Telethon 的 http 结构。"""
    proxy = parse_proxy_for_telethon({"http": "http://127.0.0.1:7890",
                                      "https": "http://127.0.0.1:7890"})
    assert proxy == {"proxy_type": "http", "addr": "127.0.0.1", "port": 7890, "rdns": True}


def test_parse_proxy_socks5_with_auth():
    """socks5 代理应保留用户名密码。"""
    proxy = parse_proxy_for_telethon({"https": "socks5://user:pass@10.0.0.2:1080"})
    assert proxy is not None
    assert proxy["proxy_type"] == "socks5"
    assert proxy["addr"] == "10.0.0.2"
    assert proxy["port"] == 1080
    assert proxy["username"] == "user"
    assert proxy["password"] == "pass"


def test_parse_proxy_empty_and_invalid():
    """空配置与无法解析的配置都应返回 None（表示直连）。"""
    assert parse_proxy_for_telethon(None) is None
    assert parse_proxy_for_telethon({}) is None
    assert parse_proxy_for_telethon({"http": ""}) is None
    assert parse_proxy_for_telethon({"http": "ftp://1.2.3.4:21"}) is None


def test_parse_proxy_string_input():
    """支持直接传字符串。"""
    proxy = parse_proxy_for_telethon("socks5://1.2.3.4:1080")
    assert proxy is not None and proxy["proxy_type"] == "socks5"


# --------------------------------------------------------------------- 掩码


def test_mask_secret():
    """掩码只保留首尾片段，短值全部打码。"""
    assert mask_secret("") == ""
    assert mask_secret("abc") == "***"
    assert mask_secret("1BVtsOLkBuwgM7R1jIS0j") == "1BVt******IS0j"
    assert "******" in mask_secret("+8613800138000")


# --------------------------------------------------------------------- 对话归一


class _FakeEntity:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeDialog:
    def __init__(self, name, entity):
        self.name = name
        self.entity = entity
        self.id = getattr(entity, "id", 0)


def test_normalize_dialog_types():
    """频道 / 群组 / 用户应被正确归类。"""
    channel = normalize_dialog(_FakeDialog("某频道", _FakeEntity(id=100, broadcast=True, username="ch")))
    assert channel == {"id": 100, "name": "某频道", "type": "频道", "username": "ch"}

    group = normalize_dialog(_FakeDialog("某群", _FakeEntity(id=-100, megagroup=True)))
    assert group["type"] == "群组"

    user = normalize_dialog(_FakeDialog("张三", _FakeEntity(id=7, first_name="张", last_name="三")))
    assert user["type"] == "用户"
    assert user["id"] == 7


# --------------------------------------------------------------------- 路由合同


class _StubPlugin:
    """API 层只需要插件实例提供同名方法，用桩对象隔离宿主依赖。"""

    def api_status(self):
        ...

    def api_telegram_send_code(self, request):
        ...

    def api_telegram_sign_in(self, request):
        ...

    def api_telegram_logout(self):
        ...

    def api_telegram_dialogs(self):
        ...

    def api_telegram_refresh_dialogs(self):
        ...


def test_api_routes_contract():
    """所有路由都要声明 bear 认证与 response_model。"""
    routes = api_controller.get_api(_StubPlugin())
    paths = {route["path"] for route in routes}
    assert paths == {
        "/status",
        "/telegram/send_code",
        "/telegram/sign_in",
        "/telegram/logout",
        "/telegram/dialogs",
        "/telegram/refresh_dialogs",
    }
    for route in routes:
        assert route["auth"] == "bear"
        assert route["response_model"] is not None
        assert route["methods"]
        assert route["summary"]
