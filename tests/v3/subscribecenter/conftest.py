"""SubscribeCenter 测试路径适配。

把 ``plugins.v3/subscribecenter`` 别名为 ``app.plugins.subscribecenter``，
与 ``tests/v3/conftest.py`` 的做法一致（官方要求：插件测试必须用
``app.plugins.<plugin_id>`` 路径导入，否则同一插件会以两个模块名加载）。

有 MoviePilot 宿主 venv 时（推荐）：宿主模块真实可用，本文件不做替换；
无宿主环境时：只对插件用到的少量宿主模块打最小桩，保证纯逻辑可离线单测。
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "plugins.v3" / "subscribecenter"
PLUGIN_MODULE = "app.plugins.subscribecenter"


def _make_module(name: str, **attrs):
    """注册一个最小桩模块。"""
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _ensure_package(name: str) -> types.ModuleType:
    """确保包路径存在且带 ``__path__``。"""
    module = sys.modules.get(name)
    if module is None:
        module = _make_module(name)
    if not hasattr(module, "__path__"):
        module.__path__ = []
    return module


def _try_import(name: str) -> bool:
    """尝试导入；缺失返回 ``False``。"""
    try:
        __import__(name)
        return True
    except ModuleNotFoundError:
        return False


# 1) app 包结构（有宿主时直接用真实包）
try:
    import app  # noqa: F401
except ModuleNotFoundError:
    _ensure_package("app")
_ensure_package("app.plugins")

# 2) 宿主叶子模块的最小桩（仅在宿主缺失时生效；必须在加载插件 __init__ 前就位）
if not _try_import("app.sdk.logging"):
    _ensure_package("app.sdk")
    import logging

    _make_module("app.sdk.logging", logger=logging.getLogger("subscribecenter.test"))

if not _try_import("app.sdk.plugin"):
    class _StubPluginBase:
        """宿主插件基类最小桩：实例级数据存取，语义与宿主一致。"""

        def get_data(self, key=None, default=None):
            store = self.__dict__.setdefault("_stub_plugin_data", {})
            value = store.get(key, default)
            return default if value is None and key not in store else value

        def save_data(self, key, value) -> None:
            self.__dict__.setdefault("_stub_plugin_data", {})[key] = value

        def del_data(self, key=None) -> None:
            self.__dict__.setdefault("_stub_plugin_data", {}).pop(key, None)

    _make_module("app.sdk.plugin", _PluginBase=_StubPluginBase)

if not _try_import("app.schemas"):
    from typing import Generic, TypeVar

    from pydantic import BaseModel

    _T = TypeVar("_T")

    class _StubResponse(BaseModel, Generic[_T]):
        """宿主 ``schemas.Response`` 的最小替身。"""

        success: bool = True
        message: str = ""
        data: _T = None

    _make_module("app.schemas", Response=_StubResponse)

if not _try_import("app.sdk.queries"):
    class _StubQueryPage:
        """宿主分页结果最小替身。"""

        def __init__(self, total: int = 0):
            self.total = total
            self.items: list = []

    _make_module("app.sdk.queries")

# 3) 插件包别名：真正执行 __init__.py
if not _try_import(PLUGIN_MODULE):
    spec = importlib.util.spec_from_file_location(
        PLUGIN_MODULE,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[PLUGIN_MODULE] = module
    spec.loader.exec_module(module)


@pytest.fixture()
def plugin_cls(monkeypatch):
    """返回插件主类，并把宿主基类的 ``__init__`` 换成不碰 ORM 的轻量版本。

    真实 ``_PluginBase.__init__`` 会构造 ``PluginDataOper`` / ``PluginInstanceOper`` 等
    宿主 ORM 访问对象，单测里既不需要也会连数据库。这里替换 ``__init__`` 后，
    插件自身的 ``get_data`` / ``save_data`` 用内存字典，语义与宿主一致（按实例隔离）。

    这样做的代价是**不覆盖宿主 ORM 交互** —— 那部分由真机验证承担；
    本 fixture 只为「元数据 / 路由 / 配置 / 状态接口」这类纯逻辑提供可运行的实例。
    """
    import app.sdk.plugin as host_plugin

    base = host_plugin._PluginBase

    def _light_init(self) -> None:
        self.__dict__["_stub_plugin_data"] = {}

    def _get_data(self, key=None, default=None):
        store = self.__dict__.setdefault("_stub_plugin_data", {})
        value = store.get(key, default)
        return default if value is None and key not in store else value

    def _save_data(self, key, value, plugin_id=None) -> None:
        self.__dict__.setdefault("_stub_plugin_data", {})[key] = value

    monkeypatch.setattr(base, "__init__", _light_init)
    monkeypatch.setattr(base, "get_data", _get_data, raising=False)
    monkeypatch.setattr(base, "save_data", _save_data, raising=False)
    monkeypatch.setattr(base, "post_message", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(base, "update_config", lambda *a, **k: True, raising=False)

    return sys.modules[PLUGIN_MODULE].SubscribeCenter


@pytest.fixture()
def plugin(plugin_cls):
    """返回一个已 ``init_plugin`` 的插件实例（默认配置）。"""
    instance = plugin_cls()
    instance.init_plugin({})
    return instance
