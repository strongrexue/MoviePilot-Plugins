"""控制器契约：路由引用的处理函数必须真的存在。

真机事故（1.10.x）：删除 ``api_test_source`` 时用「从某个 def 删到下一个 def」的
粗剪法，把夹在中间的 ``api_poster`` / ``api_preview`` / ``api_mapping_cache`` /
``api_mapping_fix`` 一起删掉了 —— 路由表还指向它们，于是海报全部 500、
预览与映射缓存也一起挂掉。这个测试专门盯住这类「静默删空」。
"""
import re
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
ROOT = Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID

API = ROOT / "controller" / "api.py"
INIT = ROOT / "__init__.py"


def _read(path: Path) -> str:
    if not path.exists():
        pytest.skip("插件源码缺失")
    return path.read_text(encoding="utf-8")


def test_every_controller_reference_exists():
    """``api_controller.xxx`` 的每个 xxx 都必须在 api.py 里有定义。"""
    api_text = _read(API)
    init_text = _read(INIT)
    defined = set(re.findall(r"^(?:async )?def (\w+)\(", api_text, re.M))
    used = set(re.findall(r"api_controller\.(\w+)\(", init_text))
    missing = sorted(used - defined)
    assert not missing, f"插件引用了不存在的控制器函数：{missing}"


def test_every_route_has_implementation():
    """路由表里的 ``plugin.api_xxx`` 都必须在 api.py 里有对应函数。"""
    api_text = _read(API)
    defined = set(re.findall(r"^(?:async )?def (\w+)\(", api_text, re.M))
    routes = re.findall(r'\("(/[^"]*)",\s*plugin\.(\w+)', api_text)
    missing = [name for path, name in routes if name not in defined]
    assert not missing, f"路由表指向不存在的函数：{missing}"


def test_poster_route_still_present():
    """海报代理丢了会导致详情页、日历全部空白。"""
    api_text = _read(API)
    assert "async def api_poster" in api_text
    assert '("/poster"' in api_text


def test_calendar_route_present():
    api_text = _read(API)
    assert "async def api_calendar" in api_text
    assert '("/calendar"' in api_text
