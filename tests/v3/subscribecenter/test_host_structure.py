"""宿主适配层的**结构哨兵**：关键方法必须存在（0.8.5）。

为什么需要这个文件：0.8.4 修 bug 时用「从 `search()` 到 `_search_without_year()`
切片替换」的方式改代码，把夹在中间的 `resolve_target_season` 及其辅助方法
**整段删掉了**。

后果在真机上表现为：「黑帮领地本该订第 2 季，却订了第 1 季」。因为
`IdentityResolver` 找不到该方法时 fail-open 成「可订 + 默认季」，宿主便按
第 1 季订阅 —— 而第 1 季早就播完、库里也有，等于白订。

当时的单元测试全绿，因为测试用的是**假的** TmdbResolver（直接实现了
`resolve_target_season`），根本没覆盖真实适配层。这个文件补上这一层：
只做结构断言，不访问网络。
"""
import inspect
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core.host import (  # noqa: E402
    HostSubscribeBackend,
    HostTmdbResolver,
)

# --------------------------------------------------------------------- 解析层

@pytest.mark.parametrize(
    "name",
    [
        # 身份解析
        "search",
        "search_raw",
        "convert_to_tmdb",
        # 季号裁决（0.8.4 被误删的那一组）
        "resolve_target_season",
        "_season_has_upcoming",
        "_find_season_group",
        "_tmdb_get",
        # 原始搜索兜底
        "_search_without_year",
    ],
)
def test_resolver_exposes_required_methods(name):
    """这些方法缺一个都会让真机行为静默退化，必须有。"""
    assert hasattr(HostTmdbResolver, name), (
        f"HostTmdbResolver 缺少 {name} —— "
        "IdentityResolver 会 fail-open 成「默认季」，导致订错季"
    )


def test_resolve_target_season_returns_three_tuple():
    """返回值必须是 ``(可订, 季号, episode_group)`` 三元组。"""
    signature = inspect.signature(HostTmdbResolver.resolve_target_season)
    params = list(signature.parameters)

    assert "season_hint" in params
    assert "prefer_episode_group" in params

    source = inspect.getsource(HostTmdbResolver.resolve_target_season)
    # 三个返回点都应返回三元组
    assert source.count("return (") >= 3
    assert "return (True, None, None)" in source, "fail-open 分支不见了"
    assert "return (False, None, None)" in source, "不可订分支不见了"


def test_resolve_target_season_is_coroutine():
    """必须是协程（调用方 await 它）。"""
    assert inspect.iscoroutinefunction(HostTmdbResolver.resolve_target_season)


# --------------------------------------------------------------------- 写入层

@pytest.mark.parametrize("name", ["add", "subscription_exists", "history_exists"])
def test_backend_exposes_required_methods(name):
    """写入层三件套：写入、活跃订阅查询、历史查询。"""
    assert hasattr(HostSubscribeBackend, name)


def test_backend_add_accepts_episode_group():
    """``add`` 必须接受 episode_group（被压成单季的番剧靠它精确订阅）。"""
    signature = inspect.signature(HostSubscribeBackend.add)
    assert "episode_group" in signature.parameters


def test_backend_exists_accepts_season():
    """去重必须能按季过滤（同一部剧的不同季是不同订阅）。"""
    for method in ("subscription_exists", "history_exists"):
        signature = inspect.signature(getattr(HostSubscribeBackend, method))
        assert "season" in signature.parameters, f"{method} 缺少 season 参数"


# --------------------------------------------------------------------- 模块级

def test_module_level_helpers_present():
    """模块级小工具也要在（切片替换时最容易被连带删掉）。"""
    from subscribecenter.core import host

    for name in ("media_source_enum", "media_type_enum", "_build_metainfo"):
        assert hasattr(host, name), f"host 模块缺少 {name}"
