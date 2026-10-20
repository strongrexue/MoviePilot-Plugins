"""P1（TG 核心凭证）单元测试。

覆盖不依赖网络的纯逻辑：代理解析、敏感值掩码、对话归一、验证码投递渠道与重发
冷却，以及 API 路由合同。需要网络的登录流程不做自动化测试，改由真实加载验证。
"""
from datetime import datetime, timedelta

import pytest

from app.plugins.tgmediacenter.controller import api as api_controller
from app.plugins.tgmediacenter.core import telegram as tg
from app.plugins.tgmediacenter.core.runtime import TelegramRuntime
from app.plugins.tgmediacenter.modules.credentials import CredentialsModule
from app.plugins.tgmediacenter.utils import (
    describe_delivery,
    mask_secret,
    normalize_dialog,
    parse_proxy_for_telethon,
    remaining_seconds,
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
    """频道 / 群组 / 用户 / 机器人应被正确归类。"""
    channel = normalize_dialog(_FakeDialog("某频道", _FakeEntity(id=100, broadcast=True, username="ch")))
    assert channel == {"id": 100, "name": "某频道", "type": "频道", "username": "ch"}

    group = normalize_dialog(_FakeDialog("某群", _FakeEntity(id=-100, megagroup=True)))
    assert group["type"] == "群组"

    user = normalize_dialog(_FakeDialog("张三", _FakeEntity(id=7, first_name="张", last_name="三")))
    assert user["type"] == "用户"
    assert user["id"] == 7

    bot = normalize_dialog(_FakeDialog("某机器人", _FakeEntity(id=42, first_name="Bot", bot=True, username="somebot")))
    assert bot["type"] == "机器人"


# --------------------------------------------------------------------- 路由合同


class _StubPlugin:
    """API 层只需要插件实例提供同名方法，用桩对象隔离宿主依赖。"""

    def api_status(self):
        ...

    def api_overview(self):
        ...

    def api_telegram_send_code(self, request):
        ...

    def api_telegram_sign_in(self, request):
        ...

    def api_telegram_logout(self):
        ...

    def api_telegram_dialogs(self):
        ...

    def api_telegram_connect(self):
        ...

    def api_telegram_refresh_dialogs(self):
        ...

    def api_pan115_status(self):
        ...

    def api_pan115_check(self):
        ...

    def api_pan115_logout(self):
        ...

    def api_pan115_verify_dir(self, request):
        ...

    def api_pan115_push(self, request):
        ...

    def api_pan115_qr_start(self, request):
        ...

    def api_pan115_qr_poll(self):
        ...

    def api_pan115_qr_cancel(self):
        ...

    def api_pan115_cookie_reveal(self):
        ...

    # P4 资源监控
    def api_monitor_rules(self):
        ...

    def api_monitor_rules_save(self, request):
        ...

    def api_monitor_hits(self, page: int = 1, page_size: int = 20, decision: str = "",
                         keyword: str = ""):
        ...

    def api_monitor_hits_clear(self, request):
        ...

    def api_monitor_status(self):
        ...

    def api_monitor_test(self, request):
        ...

    # P5 历史消息缓存
    def api_cache_settings(self):
        ...

    def api_cache_settings_save(self, request):
        ...

    def api_cache_status(self):
        ...

    def api_cache_sync(self, request):
        ...

    def api_cache_cancel(self):
        ...

    def api_cache_clear(self, request):
        ...

    def api_cache_search(self, request):
        ...

    def api_cache_check_subscriptions(self):
        ...

    # 存量补扫（1.12.0）
    def api_cache_backfill_status(self):
        ...

    def api_cache_backfill_start(self, request):
        ...

    def api_cache_backfill_cancel(self):
        ...

    # P6 通用转发
    def api_forward_rules(self):
        ...

    def api_forward_rules_save(self, request):
        ...

    def api_forward_status(self):
        ...

    def api_forward_hits(self, page: int = 1, page_size: int = 20, decision: str = "",
                         keyword: str = ""):
        ...

    def api_forward_hits_clear(self, request):
        ...

    def api_forward_test(self, request):
        ...

    # P9 重复获取治理
    def api_p9_guard(self):
        ...


def test_api_routes_contract():
    """所有路由都要声明 bear 认证与 response_model。"""
    routes = api_controller.get_api(_StubPlugin())
    paths = {route["path"] for route in routes}
    assert paths == {
        "/status",
        # P7 详情页 / 仪表盘聚合视图
        "/overview",
        "/telegram/send_code",
        "/telegram/sign_in",
        "/telegram/logout",
        "/telegram/dialogs",
        "/telegram/connect",
        "/telegram/refresh_dialogs",
        "/pan115/status",
        "/pan115/check",
        "/pan115/logout",
        "/pan115/verify_dir",
        "/pan115/push",
        "/pan115/qr_start",
        "/pan115/qr_poll",
        "/pan115/qr_cancel",
        "/pan115/cookie_reveal",
        # P4 资源监控（rules 同时注册 GET 与 PUT）
        "/monitor/rules",
        "/monitor/hits",
        "/monitor/hits/clear",
        "/monitor/status",
        "/monitor/test",
        # P5 历史消息缓存（settings 同时注册 GET 与 PUT）
        "/cache/settings",
        "/cache/status",
        "/cache/sync",
        "/cache/cancel",
        "/cache/clear",
        "/cache/search",
        "/cache/check_subscriptions",
        # 存量补扫（1.12.0）
        "/cache/backfill/status",
        "/cache/backfill/start",
        "/cache/backfill/cancel",
        # P6 通用转发（rules 同时注册 GET 与 PUT）
        "/forward/rules",
        "/forward/status",
        "/forward/hits",
        "/forward/hits/clear",
        "/forward/test",
        # P9 重复获取治理（P9-1：能力探针 + 反向开关重贴）
        "/p9/guard",
    }
    for route in routes:
        assert route["auth"] == "bear"
        assert route["response_model"] is not None
        assert route["methods"]
        assert route["summary"]


# --------------------------------------------------------------------- 运行时


def test_telethon_available_is_boolean():
    """依赖可用性必须以布尔值暴露。

    回归保护：早期实现用 @property，在类上访问会拿到 property 对象，
    被塞进响应模型后导致 /status 校验失败。
    """
    value = TelegramRuntime.telethon_available()
    assert isinstance(value, bool)


def test_runtime_requires_credentials(tmp_path):
    """缺少凭证时不应启动运行时，也不应抛异常。"""
    runtime = TelegramRuntime(api_id=None, api_hash="", session_string="")
    assert runtime.credentials_ready is False
    assert runtime.start() is False
    assert runtime.is_running() is False
    runtime.stop()


def test_runtime_api_id_normalization():
    """api_id 需要归一为整数，非法值视为缺失。"""
    assert TelegramRuntime(api_id="12345", api_hash="x").credentials_ready is True
    assert TelegramRuntime(api_id="  678 ", api_hash="x")._api_id == 678
    assert TelegramRuntime(api_id="abc", api_hash="x").credentials_ready is False
    assert TelegramRuntime(api_id="", api_hash="x").credentials_ready is False


def test_runtime_proxy_support_probe_is_bool():
    """代理依赖探测也必须是静态方法，返回布尔值。"""
    assert isinstance(TelegramRuntime.proxy_support_available(), bool)


def test_proxy_ignored_hint_names_missing_dependency(monkeypatch):
    """缺少 python-socks 时，提示必须点名依赖与代理地址，而不是笼统说"检查网络"。

    回归保护：Telethon 把代理当软依赖，缺 python-socks 时只打一行 UserWarning
    就直连；机房直连不通时用户只会看到"45 秒连接失败"，误以为是代理配错了。
    """
    from app.plugins.tgmediacenter.core import runtime as runtime_module

    monkeypatch.setattr(runtime_module, "PROXY_SUPPORT_AVAILABLE", False)
    runtime = TelegramRuntime(
        api_id=1,
        api_hash="x",
        proxy={"proxy_type": "http", "addr": "192.168.1.9", "port": 7890, "rdns": True},
    )
    hint = runtime.proxy_ignored_hint()
    assert "python-socks" in hint
    assert "192.168.1.9:7890" in hint


def test_proxy_ignored_hint_silent_without_proxy_or_with_support(monkeypatch):
    """没有配代理、或环境支持代理时不应骚扰用户。"""
    from app.plugins.tgmediacenter.core import runtime as runtime_module

    proxy = {"proxy_type": "http", "addr": "1.2.3.4", "port": 7890, "rdns": True}
    monkeypatch.setattr(runtime_module, "PROXY_SUPPORT_AVAILABLE", False)
    assert TelegramRuntime(api_id=1, api_hash="x").proxy_ignored_hint() == ""
    monkeypatch.setattr(runtime_module, "PROXY_SUPPORT_AVAILABLE", True)
    assert TelegramRuntime(api_id=1, api_hash="x", proxy=proxy).proxy_ignored_hint() == ""


def test_ensure_runtime_surfaces_proxy_hint(monkeypatch):
    """连接失败且代理被忽略时，异常文案要带上依赖提示。"""
    module = CredentialsModule(_StubCredPlugin(config={"tg_api_id": 1, "tg_api_hash": "x"}))

    # 测试环境（宿主 venv）没装 telethon，这里只验证分支逻辑，把依赖探针打桩。
    monkeypatch.setattr(TelegramRuntime, "telethon_available", staticmethod(lambda: True))
    monkeypatch.setattr(TelegramRuntime, "start", lambda self, connect_timeout=30: False)
    monkeypatch.setattr(
        TelegramRuntime,
        "proxy_ignored_hint",
        lambda self: "已配置代理 1.2.3.4:7890，但当前环境缺少 python-socks",
    )
    with pytest.raises(tg.TelegramOperationError) as err:
        module.ensure_runtime(connect_timeout=3)
    assert "python-socks" in str(err.value)


def test_ensure_runtime_keeps_generic_message_without_proxy_hint(monkeypatch):
    """没有代理依赖线索时保持原来的通用提示。"""
    module = CredentialsModule(_StubCredPlugin(config={"tg_api_id": 1, "tg_api_hash": "x"}))

    monkeypatch.setattr(TelegramRuntime, "telethon_available", staticmethod(lambda: True))
    monkeypatch.setattr(TelegramRuntime, "start", lambda self, connect_timeout=30: False)
    monkeypatch.setattr(TelegramRuntime, "proxy_ignored_hint", lambda self: "")
    with pytest.raises(tg.TelegramOperationError) as err:
        module.ensure_runtime(connect_timeout=3)
    assert "请检查服务器网络与代理设置" in str(err.value)


def test_runtime_start_warns_when_proxy_dependency_missing(monkeypatch, caplog):
    """start() 在连接前先告警，避免用户只看得到 45 秒超时。"""
    from app.plugins.tgmediacenter.core import runtime as runtime_module

    monkeypatch.setattr(runtime_module, "PROXY_SUPPORT_AVAILABLE", False)
    monkeypatch.setattr(runtime_module, "TELETHON_AVAILABLE", True)
    runtime = TelegramRuntime(
        api_id=1,
        api_hash="x",
        proxy={"proxy_type": "http", "addr": "1.2.3.4", "port": 7890, "rdns": True},
    )
    monkeypatch.setattr(TelegramRuntime, "call", lambda self, coro, timeout=None: (_ for _ in ()).throw(RuntimeError("boom")))
    caplog.set_level("WARNING")
    assert runtime.start(connect_timeout=1) is False
    assert any("python-socks" in (record.getMessage() or "") for record in caplog.records)


# --------------------------------------------------- API ID 填错（真实故障复现）


def test_parse_api_id_accepts_numbers_only():
    """api_id 必须能归一成整数；把口令粘进来这种是真实发生过的故障。"""
    assert TelegramRuntime.parse_api_id("12345678") == 12345678
    assert TelegramRuntime.parse_api_id(12345678) == 12345678
    assert TelegramRuntime.parse_api_id(" 678 ") == 678
    assert TelegramRuntime.parse_api_id("Ldb456090") is None
    assert TelegramRuntime.parse_api_id("") is None
    assert TelegramRuntime.parse_api_id(None) is None


def test_api_id_issue_names_the_problem_and_masks_value():
    """凭证"填了但不是数字"要能单独识别出来，且不能把原值打进提示里。"""
    module = CredentialsModule(
        _StubCredPlugin(config={"tg_api_id": "Ldb456090", "tg_api_hash": "x"})
    )
    issue = module.api_id_issue()
    assert "纯数字" in issue
    assert "Ldb456090" not in issue

    ok = CredentialsModule(_StubCredPlugin(config={"tg_api_id": "12345678", "tg_api_hash": "x"}))
    assert ok.api_id_issue() == ""

    empty = CredentialsModule(_StubCredPlugin(config={"tg_api_id": "", "tg_api_hash": "x"}))
    assert empty.api_id_issue() == ""


def test_ensure_runtime_rejects_non_numeric_api_id():
    """错误必须在建运行时之前暴露，而不是被报成"45 秒连接失败"。"""
    module = CredentialsModule(
        _StubCredPlugin(config={"tg_api_id": "Ldb456090", "tg_api_hash": "x"})
    )
    with pytest.raises(tg.TelegramOperationError) as err:
        module.ensure_runtime(connect_timeout=3)
    message = str(err.value)
    assert "纯数字" in message
    assert "45 秒" not in message
    assert "代理" not in message


def test_status_exposes_api_id_issue():
    """状态接口要带出该问题，前端才能提前提示而不是等连接超时。"""
    module = CredentialsModule(
        _StubCredPlugin(config={"tg_api_id": "Ldb456090", "tg_api_hash": "x"})
    )
    assert "纯数字" in module.status()["api_id_issue"]

    ok = CredentialsModule(_StubCredPlugin(config={"tg_api_id": "12345678", "tg_api_hash": "x"}))
    assert ok.status()["api_id_issue"] == ""


def test_runtime_start_records_reason_when_credentials_unusable(monkeypatch):
    """start() 早退时要把原因留给调用方，日志里也不能只说"未配置"。"""
    from app.plugins.tgmediacenter.core import runtime as runtime_module

    # 宿主 venv 无 telethon，否则原因会被"依赖未安装"抢先命中
    monkeypatch.setattr(runtime_module, "TELETHON_AVAILABLE", True)
    runtime = TelegramRuntime(api_id="Ldb456090", api_hash="x")
    assert runtime.start(connect_timeout=1) is False
    assert "API ID" in runtime.last_start_error



# --------------------------------------------------------------------- 投递渠道


class SentCodeTypeApp:
    """桩类：类名需与 Telethon 的 SentCodeType* 保持一致。"""


class SentCodeTypeSms:
    """桩类：短信投递。"""


class _FakeSent:
    def __init__(self, sent_type):
        self.type = sent_type


def test_delivery_channel_mapping():
    """验证码投递渠道应按 SentCode.type 的类名识别。"""
    assert tg.delivery_channel(_FakeSent(SentCodeTypeApp())) == "app"
    assert tg.delivery_channel(_FakeSent(SentCodeTypeSms())) == "sms"
    assert tg.delivery_channel(_FakeSent(None)) == "unknown"
    assert tg.delivery_channel(object()) == "unknown"


def test_describe_delivery_is_actionable():
    """渠道说明要能指导用户去哪找验证码。"""
    assert "Telegram 应用" in describe_delivery("app")
    assert "短信" in describe_delivery("sms")
    assert describe_delivery("") == describe_delivery("unknown")
    assert describe_delivery("不存在的渠道") == describe_delivery("unknown")


def test_remaining_seconds():
    """重发倒计时应按发码时间与 Telegram 给出的间隔计算。"""
    now = datetime(2026, 10, 12, 22, 0, 0)
    past = (now - timedelta(seconds=20)).isoformat(timespec="seconds")
    assert remaining_seconds(past, 60, now=now) == 40
    assert remaining_seconds(past, 10, now=now) == 0
    assert remaining_seconds("", 60, now=now) == 0
    assert remaining_seconds(past, 0, now=now) == 0
    assert remaining_seconds(past, "abc", now=now) == 0
    assert remaining_seconds("不是时间", 60, now=now) == 0


# --------------------------------------------------------------------- 发码冷却


class _StubCredPlugin:
    """凭证模块只依赖插件的配置与数据读写，用桩对象隔离宿主。"""

    def __init__(self, config=None, data=None):
        self._config = dict(config or {})
        self._data = dict(data or {})

    @property
    def config(self):
        return self._config

    def get_state(self):
        return False

    def get_data(self, key=None):
        return self._data.get(key)

    def save_data(self, key, value):
        self._data[key] = value

    def del_data(self, key):
        self._data.pop(key, None)

    def save_config(self, **patch):
        self._config.update(patch)

    def drop_config(self, *keys):
        for key in keys:
            self._config.pop(key, None)


def _pending(**overrides):
    """构造一份待验证登录上下文。"""
    payload = {
        "phone": "+8613800138000",
        "phone_code_hash": "hash",
        "at": datetime.now().isoformat(timespec="seconds"),
        "delivery": "app",
        "timeout": 60,
    }
    payload.update(overrides)
    return payload


def test_send_code_blocked_within_cooldown():
    """冷却期内重复发码应被本地拦截并给出可操作提示。

    回归保护：Telegram 对同号码发码有最小间隔，间隔内再请求会得到
    SEND_CODE_UNAVAILABLE，早期实现把一长串英文报错直接抛给用户。
    """
    module = CredentialsModule(_StubCredPlugin(data={"pending_login": _pending()}))
    with pytest.raises(tg.TelegramOperationError) as excinfo:
        module.send_code("+8613800138000")
    assert "秒后可重新发送" in str(excinfo.value)


def test_send_code_allows_other_phone_within_cooldown():
    """换号不受上一号码冷却限制：应走到运行时检查而非被冷却拦截。"""
    module = CredentialsModule(_StubCredPlugin(data={"pending_login": _pending()}))
    with pytest.raises(tg.TelegramOperationError) as excinfo:
        module.send_code("+8613900139000")
    assert "API ID" in str(excinfo.value)


def test_cooldown_expires():
    """冷却结束后不应再拦截。"""
    expired = _pending(at=(datetime.now() - timedelta(seconds=180)).isoformat(timespec="seconds"))
    module = CredentialsModule(_StubCredPlugin(data={"pending_login": expired}))
    assert module.resend_in() == 0
    with pytest.raises(tg.TelegramOperationError) as excinfo:
        module.send_code("+8613800138000")
    assert "API ID" in str(excinfo.value)


# --------------------------------------------------------------------- 待登录上下文


def test_pending_login_masks_phone():
    """待登录上下文对外只暴露掩码手机号。"""
    module = CredentialsModule(_StubCredPlugin(data={"pending_login": _pending()}))
    view = module.pending_login()
    assert view is not None
    assert view["phone_masked"] == mask_secret("+8613800138000")
    assert "+8613800138000" not in view["phone_masked"]
    assert view["delivery"] == "app"
    assert "Telegram 应用" in view["delivery_text"]
    assert view["resend_in"] > 0


def test_pending_login_absent_without_hash():
    """没有 phone_code_hash 时不应对外声称存在待登录上下文。"""
    module = CredentialsModule(_StubCredPlugin(data={"pending_login": _pending(phone_code_hash="")}))
    assert module.pending_login() is None


# --------------------------------------------------------------------- 会话存储


def test_session_stored_in_plugin_data():
    """会话以插件数据为准，同时兼容旧版本存在配置里的值。"""
    data_module = CredentialsModule(_StubCredPlugin(data={"tg_session_string": "from-data"}))
    assert data_module.session_string() == "from-data"

    legacy_module = CredentialsModule(_StubCredPlugin(config={"tg_session_string": "from-config"}))
    assert legacy_module.session_string() == "from-config"

    assert CredentialsModule(_StubCredPlugin()).session_string() == ""


def test_migrate_session_from_config():
    """旧版本存在配置里的会话应迁到数据，并从配置中移除。

    回归保护：宿主「保存配置」是整份覆盖，而前端表单不含会话串，
    会话留在配置里就会在用户点一次保存后被清空（表现为"已登录"变"未登录"）。
    """
    plugin = _StubCredPlugin(config={"tg_api_id": "1", "tg_session_string": "legacy"})
    CredentialsModule(plugin).migrate_session_from_config()
    assert plugin.get_data("tg_session_string") == "legacy"
    assert "tg_session_string" not in plugin.config


def test_migrate_does_not_override_existing_data():
    """数据里已有会话时不被旧配置覆盖，但配置里的旧字段仍要清掉。"""
    plugin = _StubCredPlugin(
        config={"tg_session_string": "legacy"},
        data={"tg_session_string": "fresh"},
    )
    CredentialsModule(plugin).migrate_session_from_config()
    assert plugin.get_data("tg_session_string") == "fresh"
    assert "tg_session_string" not in plugin.config


def test_status_reports_session_from_data():
    """/status 的会话徽章应反映插件数据里的会话。"""
    module = CredentialsModule(_StubCredPlugin(data={"tg_session_string": "s"}))
    assert module.status()["session_present"] is True
    module = CredentialsModule(_StubCredPlugin())
    assert module.status()["session_present"] is False


# --------------------------------------------------------------------- 断线自愈


def test_is_disconnected_error():
    """连接断开类错误要能被识别（供"重连后重试"决策）。"""
    assert tg.is_disconnected_error(ConnectionError("Cannot send requests while disconnected"))
    assert tg.is_disconnected_error(RuntimeError("Cannot send requests while disconnected"))
    assert not tg.is_disconnected_error(RuntimeError("PHONE_CODE_INVALID"))
    assert not tg.is_disconnected_error(ValueError("手机号不能为空"))


async def _dummy_coro():
    return "ignored"


class _FakeRuntime:
    """桩运行时：首次调用抛断线错误，重连后成功。"""

    def __init__(self, fail_times: int = 1, reconnect_ok: bool = True):
        self.calls = 0
        self.reconnects = 0
        self._fail_times = fail_times
        self._reconnect_ok = reconnect_ok

    def call(self, coro, timeout=30):
        if hasattr(coro, "close"):
            coro.close()
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ConnectionError("Cannot send requests while disconnected")
        return "ok"

    def ensure_connected(self, timeout=12):
        self.reconnects += 1
        return self._reconnect_ok


def test_call_tg_retries_after_disconnect():
    """连接断开后应重连并重试一次。

    回归保护：真机出现过 "发送验证码失败：Cannot send requests while disconnected"
    —— 运行时线程活着但网络层已断开，此时直接发请求必然失败。
    """
    runtime = _FakeRuntime()
    module = CredentialsModule(_StubCredPlugin())
    assert module._call_tg(runtime, _dummy_coro, timeout=5) == "ok"
    assert runtime.calls == 2
    assert runtime.reconnects == 1


def test_call_tg_gives_up_when_reconnect_fails():
    """重连失败时不再重试，把断线错误抛给上层翻译。"""
    runtime = _FakeRuntime(fail_times=2, reconnect_ok=False)
    module = CredentialsModule(_StubCredPlugin())
    with pytest.raises(ConnectionError):
        module._call_tg(runtime, _dummy_coro, timeout=5)
    assert runtime.calls == 1


def test_call_tg_does_not_retry_other_errors():
    """非断线错误应原样抛出，不做重试。"""
    class _Runtime:
        calls = 0

        def call(self, coro, timeout=30):
            if hasattr(coro, "close"):
                coro.close()
            _Runtime.calls += 1
            raise tg.TelegramOperationError("验证码错误")

    module = CredentialsModule(_StubCredPlugin())
    with pytest.raises(tg.TelegramOperationError):
        module._call_tg(_Runtime(), _dummy_coro, timeout=5)
    assert _Runtime.calls == 1


# --------------------------------------------------------------------- 响应模型


def test_send_code_response_model():
    """/telegram/send_code 需返回投递渠道与可重发倒计时。"""
    from app.plugins.tgmediacenter.controller import schemas as api_schemas

    assert api_schemas.API_RESPONSE_MODELS["/telegram/send_code"] is api_schemas.TgSendCodeData
    data = api_schemas.TgSendCodeData.model_validate({
        "phone_masked": "+861******8000",
        "delivery": "app",
        "delivery_text": "已发送到你的 Telegram 应用",
        "resend_in": 60,
        "message": "验证码已发送到你的 Telegram 应用",
    })
    assert data.delivery == "app"
    assert data.resend_in == 60


def test_status_model_accepts_pending_login():
    """/status 需容纳待登录上下文，且允许为空。"""
    from app.plugins.tgmediacenter.controller import schemas as api_schemas

    data = api_schemas.TgStatusData.model_validate({
        "pending_login": {"phone_masked": "+86******8000", "delivery": "sms", "resend_in": 12},
    })
    assert data.pending_login is not None
    assert data.pending_login.delivery == "sms"
    assert api_schemas.TgStatusData.model_validate({"pending_login": None}).pending_login is None
