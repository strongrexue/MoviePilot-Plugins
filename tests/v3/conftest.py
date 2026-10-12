"""测试路径适配：把 ``plugins.v3/tgmediacenter`` 别名为 ``app.plugins.tgmediacenter``。

两种运行方式都支持：

- 有 MoviePilot 宿主 venv（推荐）：``../MoviePilot/.venv/python -m pytest tests/v3``
  ——宿主模块真实可用，本文件不做任何替换；
- 无宿主环境：对插件用到的少量宿主模块打**最小桩**（仅保证可导入；
  涉及网络/调度的行为仍由真机验证，桩会让测试在误用时直接报错）。
"""
import importlib.util
import logging
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins.v3" / "tgmediacenter"


def _make_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _ensure_package(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = _make_module(name)
    if not hasattr(module, "__path__"):
        module.__path__ = []
    return module


def _try_import(name: str) -> bool:
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
    _make_module("app.sdk")
    _ensure_package("app.sdk")
    _make_module("app.sdk.logging", logger=logging.getLogger("tgmediacenter.test"))

if not _try_import("app.sdk.plugin"):
    _make_module("app.sdk.plugin", _PluginBase=type("_PluginBase", (), {}))

if not _try_import("app.adapters.network.http"):
    _make_module("app.adapters")
    _ensure_package("app.adapters")
    _ensure_package("app.adapters.network")

    class _StubAsyncRequestUtils:  # pragma: no cover - 误用即失败
        def __init__(self, *args, **kwargs):
            raise RuntimeError("测试环境无宿主 HTTP 客户端；网络行为需真机验证")

    _make_module("app.adapters.network.http", AsyncRequestUtils=_StubAsyncRequestUtils)

if not _try_import("app.sdk.config"):
    _make_module("app.sdk.config", settings=type("S", (), {"PROXY": None})())

if not _try_import("app.schemas"):
    from typing import Generic, TypeVar

    from pydantic import BaseModel

    _T = TypeVar("_T")

    class _StubResponse(BaseModel, Generic[_T]):
        """宿主 ``schemas.Response`` 的最小替身（仅支撑路由模型下标）。"""

        success: bool = True
        message: str = ""
        data: _T = None

    _make_module("app.schemas", Response=_StubResponse)

# 3) 插件包别名：真正执行 __init__.py（手工塞 sys.modules 不会执行它，
#    导致 from app.plugins.tgmediacenter import TgMediaCenter 拿不到名字）
if not _try_import("app.plugins.tgmediacenter"):
    spec = importlib.util.spec_from_file_location(
        "app.plugins.tgmediacenter",
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["app.plugins.tgmediacenter"] = module
    spec.loader.exec_module(module)
