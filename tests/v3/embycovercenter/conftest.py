"""测试路径适配：把 ``plugins.v3/embycovercenter`` 别名为 ``app.plugins.embycovercenter``。

宿主包结构（``app`` / ``app.plugins`` 与宿主叶子模块的最小桩）由上层
``tests/v3/conftest.py`` 统一准备，本文件只负责把本插件目录注册成
``app.plugins.embycovercenter``——手工塞 ``sys.modules`` 不会执行 ``__init__.py``，
必须用 spec 执行一次，否则拿不到 ``EmbyCoverCenter``。
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "plugins.v3" / "embycovercenter"

_MODULE_NAME = "app.plugins.embycovercenter"

if _MODULE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        _MODULE_NAME,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
