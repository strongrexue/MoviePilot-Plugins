"""极影视（zspace）接入的回归测试。

覆盖四道关里的读侧三关 + 写侧失败提示：
- 类型白名单与 ``emby/`` 前缀（list_servers / _relative_path / _placeholder_url）；
- 无静态 apikey 时从运行时 ``instance._apikey`` 回落（resolve，且每次现取）；
- ``Users`` 端点 404 时从 ``instance.user`` 回落取用户 ID（admin_user_id / list_libraries）；
- 封面写入失败给出带 HTTP 状态码的可操作提示，其余类型文案不变。

参考实现：wio-ki/mediacovergenerator v1.8.2（按 Emby 兼容接口盲写，作者无真机实测）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.plugins.embycovercenter.service import emby_assets, emby_gateway
from app.plugins.embycovercenter.service.emby_gateway import ServerRef


# ---------------------------------------------------------------------------
# 通用桩
# ---------------------------------------------------------------------------
class _Instance:
    """宿主极影视/Emby 模块实例的最小桩。"""

    def __init__(self, inactive=False, user=None, apikey=None, post_response=None):
        self._inactive = inactive
        self.user = user
        self._apikey = apikey
        self._post_response = post_response
        self.post_calls = []

    def is_inactive(self):
        return self._inactive

    def post_data(self, url=None, data=None, headers=None):
        self.post_calls.append({"url": url, "data": data, "headers": headers})
        return self._post_response


class _Service:
    def __init__(self, type_name, instance=None):
        self.type = type_name
        self.instance = instance or _Instance()


class _Conf:
    def __init__(self, config):
        self.config = config


class _FakeHelper:
    def __init__(self, services, configs=None):
        self._services = services
        self._configs = configs or {}

    def get_services(self):
        return self._services

    def get_configs(self):
        return self._configs


class _Res:
    def __init__(self, status_code):
        self.status_code = status_code


def _ref(type_name="zspace", instance=None):
    return ServerRef(
        name="极影视",
        type=type_name,
        instance=instance or _Instance(user="uid-zs", apikey="tok-1"),
        host="http://nas:1234/",
        apikey="tok-1",
    )


# ---------------------------------------------------------------------------
# 1) 类型白名单
# ---------------------------------------------------------------------------
def test_list_servers_includes_zspace(monkeypatch):
    """极影视出现在可选服务器列表里，未被 SUPPORTED_TYPES 挡掉。"""
    services = {
        "115emby": _Service("emby"),
        "homejelly": _Service("jellyfin"),
        "极影视": _Service("zspace"),
        "飞牛": _Service("trimemedia"),
    }
    monkeypatch.setattr(emby_gateway, "_helper", lambda: _FakeHelper(services))

    servers = emby_gateway.list_servers()

    assert [s["name"] for s in servers] == ["115emby", "homejelly", "极影视"]
    assert {s["name"]: s["type"] for s in servers} == {
        "115emby": "emby",
        "homejelly": "jellyfin",
        "极影视": "zspace",
    }


# ---------------------------------------------------------------------------
# 2) emby/ 前缀与占位符 URL
# ---------------------------------------------------------------------------
def test_relative_path_emby_and_zspace_share_prefix():
    """极影视与 Emby 同带 emby/ 前缀，Jellyfin 走根路径。"""
    assert emby_gateway._relative_path("emby", "Users/x/Views") == "emby/Users/x/Views"
    assert emby_gateway._relative_path("zspace", "Users/x/Views") == "emby/Users/x/Views"
    assert emby_gateway._relative_path("jellyfin", "Users/x/Views") == "Users/x/Views"
    # 传入带前导斜杠也能归一化
    assert emby_gateway._relative_path("zspace", "/Items") == "emby/Items"


def test_placeholder_url_zspace_uses_host_apikey_placeholders():
    """透传 URL 一律用占位符，让宿主把 [APIKEY] 换成 AccessToken。"""
    url = emby_gateway._placeholder_url(_ref(), "Items/lib1/Images/Primary")
    assert url == "[HOST]emby/Items/lib1/Images/Primary?api_key=[APIKEY]"
    # 带 query 时追加参数
    url2 = emby_gateway._placeholder_url(_ref(), "Items/lib1", {"maxHeight": 600})
    assert url2 == "[HOST]emby/Items/lib1?api_key=[APIKEY]&maxHeight=600"


# ---------------------------------------------------------------------------
# 3) resolve：无静态 apikey 时从 instance._apikey 回落
# ---------------------------------------------------------------------------
def test_resolve_zspace_falls_back_to_runtime_apikey(monkeypatch):
    """极影视配置没有 apikey，real_url()/delete() 用的密钥取自运行时 AccessToken。"""
    inst = _Instance(user="uid-zs", apikey="access-token-aaa")
    services = {"极影视": _Service("zspace", inst)}
    configs = {"极影视": _Conf({"host": "http://nas:1234/"})}  # 刻意不带 apikey
    monkeypatch.setattr(emby_gateway, "_helper", lambda: _FakeHelper(services, configs))

    ref = emby_gateway.resolve("极影视")

    assert ref.type == "zspace"
    assert ref.apikey == "access-token-aaa"
    assert ref.host == "http://nas:1234/"


def test_resolve_zspace_re_reads_apikey_each_time(monkeypatch):
    """重连换 token 后旧值不能残留：每次 resolve() 都现取实例上的 _apikey。"""
    inst = _Instance(user="uid-zs", apikey="token-old")
    services = {"极影视": _Service("zspace", inst)}
    configs = {"极影视": _Conf({"host": "http://nas:1234/"})}
    monkeypatch.setattr(emby_gateway, "_helper", lambda: _FakeHelper(services, configs))

    assert emby_gateway.resolve("极影视").apikey == "token-old"
    inst._apikey = "token-new"  # 模拟宿主 reconnect() 刷新 AccessToken
    assert emby_gateway.resolve("极影视").apikey == "token-new"


def test_resolve_prefers_static_apikey_when_present(monkeypatch):
    """Emby 这类带静态 apikey 的服务器仍优先用配置值，不被回落覆盖。"""
    inst = _Instance(user="uid", apikey="runtime-token")
    services = {"115emby": _Service("emby", inst)}
    configs = {"115emby": _Conf({"host": "http://emby:8096", "apikey": "static-key"})}
    monkeypatch.setattr(emby_gateway, "_helper", lambda: _FakeHelper(services, configs))

    assert emby_gateway.resolve("115emby").apikey == "static-key"


# ---------------------------------------------------------------------------
# 4) admin_user_id / list_libraries：Users 404 回落
# ---------------------------------------------------------------------------
def test_admin_user_id_zspace_uses_instance_user_without_hitting_users(monkeypatch):
    """极影视直接回落 instance.user，不去撞必然 404 的 Users 全量列表。"""
    emby_assets._ADMIN_USER_CACHE.clear()
    inst = _Instance(user="zspace-user-id", apikey="tok")
    ref = _ref(instance=inst)

    def boom(ref_arg, path, query=None):
        raise AssertionError(f"极影视不应请求 {path}")

    monkeypatch.setattr(emby_gateway, "get_json", boom)

    assert emby_assets.admin_user_id(ref) == "zspace-user-id"
    # 命中缓存后仍返回同一个 ID
    assert emby_assets.admin_user_id(ref) == "zspace-user-id"
    emby_assets._ADMIN_USER_CACHE.clear()


def test_admin_user_id_zspace_without_user_returns_none():
    """实例还没登录（user 为空）时明确失败，不让 list_libraries 打空用户 ID。"""
    emby_assets._ADMIN_USER_CACHE.clear()
    ref = _ref(instance=_Instance(user=None, apikey="tok"))

    assert emby_assets.admin_user_id(ref) is None
    emby_assets._ADMIN_USER_CACHE.clear()


def test_list_libraries_zspace_tolerates_404_and_uses_views(monkeypatch):
    """VirtualFolders/Users 均 404 时，媒体库仍能从 Users/{uid}/Views 列出。"""
    emby_assets._ADMIN_USER_CACHE.clear()
    calls = []

    def fake_get_json(ref, path, query=None):
        calls.append(path)
        if path == "Library/VirtualFolders":
            raise emby_gateway.GatewayError("HTTP 404")  # 极影视没实现
        if path == "Users/uid-zs/Views":
            return {
                "Items": [
                    {"Id": "lib-movie", "Name": "电影", "CollectionType": "movies"},
                    {"Id": "lib-tv", "Name": "剧集", "CollectionType": "tvshows"},
                ]
            }
        raise AssertionError(f"未预期的端点：{path}")

    monkeypatch.setattr(emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(
        emby_gateway,
        "real_url",
        lambda ref, path, query=None: f"http://nas/emby/{path}?api_key={ref.apikey}",
    )

    ref = _ref(instance=_Instance(user="uid-zs", apikey="tok"))
    libs = emby_assets.list_libraries(ref)

    assert [lib["id"] for lib in libs] == ["lib-movie", "lib-tv"]
    assert libs[0]["name"] == "电影"
    assert libs[0]["cover_url"].startswith("http://nas/emby/Items/lib-movie/Images/Primary")
    assert "Library/VirtualFolders" in calls
    assert "Users" not in calls  # 关键：没有去撞 Users 全量列表
    assert "Users/uid-zs/Views" in calls
    emby_assets._ADMIN_USER_CACHE.clear()


# ---------------------------------------------------------------------------
# 5) post_raw：写封面失败的可操作提示
# ---------------------------------------------------------------------------
def test_post_raw_zspace_failure_has_actionable_hint():
    """极影视写封面失败时，报错带状态码 + 手动设置指引 + 反馈请求。"""
    inst = _Instance(user="uid", apikey="tok", post_response=_Res(404))
    ref = _ref(instance=inst)

    with pytest.raises(emby_gateway.GatewayError) as excinfo:
        emby_gateway.post_raw(
            ref,
            "Items/lib1/Images/Primary",
            data="base64string",
            content_type="image/jpeg",
        )

    message = str(excinfo.value)
    assert "HTTP 404" in message
    assert "极影视" in message
    assert "生成预览" in message
    assert "手动" in message
    assert "反馈" in message
    # 透传仍走占位符，不拼真实 URL
    assert inst.post_calls[0]["url"] == (
        "[HOST]emby/Items/lib1/Images/Primary?api_key=[APIKEY]"
    )


def test_post_raw_zspace_failure_hint_only_for_cover_upload():
    """非封面写入的 POST 失败不加极影视专属提示，避免误报。"""
    inst = _Instance(user="uid", apikey="tok", post_response=_Res(500))
    ref = _ref(instance=inst)

    with pytest.raises(emby_gateway.GatewayError) as excinfo:
        emby_gateway.post_raw(ref, "Items/lib1/Refresh", data={}, content_type="application/json")

    assert "极影视" not in str(excinfo.value)
    assert "HTTP 500" in str(excinfo.value)


@pytest.mark.parametrize("type_name", ["emby", "jellyfin"])
def test_post_raw_other_types_keep_original_message(type_name):
    """Emby / Jellyfin 的失败文案保持原样，不受极影视分支影响。"""
    inst = _Instance(user="uid", apikey="tok", post_response=_Res(400))
    ref = _ref(type_name=type_name, instance=inst)

    with pytest.raises(emby_gateway.GatewayError) as excinfo:
        emby_gateway.post_raw(
            ref,
            "Items/lib1/Images/Primary",
            data="base64string",
            content_type="image/jpeg",
        )

    message = str(excinfo.value)
    assert "HTTP 400" in message
    assert "极影视" not in message
    assert "手动" not in message


@pytest.mark.parametrize("status", [200, 204])
def test_post_raw_zspace_success_does_not_raise(status):
    """200/204 视为写入成功，不抛错（真机若支持写入即可正常应用）。"""
    inst = _Instance(user="uid", apikey="tok", post_response=_Res(status))
    ref = _ref(instance=inst)

    emby_gateway.post_raw(
        ref,
        "Items/lib1/Images/Primary",
        data="base64string",
        content_type="image/jpeg",
    )  # 不抛异常
    assert len(inst.post_calls) == 1
