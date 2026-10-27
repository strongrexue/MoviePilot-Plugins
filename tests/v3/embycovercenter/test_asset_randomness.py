"""素材抽取的随机性回归：用户反馈「随机抽取每次都一样，都是同一张」。

两个叠加原因：
1. `controller/api.py` 的 `_fetch_assets` 对 random 模式也走 120s 短缓存，
   cache_key 不含随机因子 → 连点预览返回同一批素材。
2. `emby_assets.fetch_assets` 在素材不足抽样数量时直接 `pool[:n]`，
   小库（只有一两张背景图）等于固定取前几张。
"""
import random

import pytest

from app.plugins.embycovercenter.controller import api as api_controller
from app.plugins.embycovercenter.controller import schemas as api_schemas
from app.plugins.embycovercenter.service import emby_assets
from app.plugins.embycovercenter.service.emby_gateway import ServerRef


class _Ref:
    name = "Emby"


def _patch_items(monkeypatch, posters, backdrops):
    """伪造 Items 查询：按 ImageTypes 返回不同素材池，并记录调用次数。"""

    calls = []

    def fake_get_json(ref, path, params=None):
        if path == "Library/MediaFolders":
            return {"Items": [{"Id": "lib1", "CollectionType": "movies"}]}
        if path == "Users/uid/Views":
            return {"Items": [{"Id": "lib1", "Name": "华语电影"}]}
        if path.endswith("/Items"):
            calls.append(dict(params or {}))
            if params and params.get("ImageTypes") == "Backdrop":
                items = [{"Id": f"b{i}", "BackdropImageTags": ["tag"]} for i in range(backdrops)]
            elif params and params.get("ImageTypes") == "Primary":
                items = [{"Id": f"p{i}", "ImageTags": {"Primary": "tag"}} for i in range(posters)]
            else:
                items = []
            return {"Items": items, "TotalRecordCount": len(items)}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(emby_assets, "admin_user_id", lambda ref: "uid")
    # 素材 URL 由宿主 UrlUtils 生成，测试里换成可直接比较的字符串
    monkeypatch.setattr(
        emby_assets.emby_gateway,
        "real_url",
        lambda ref, path, query=None: f"http://emby/{path}?{sorted((query or {}).items())}",
    )
    return calls


def test_random_mode_shuffles_even_when_pool_is_small(monkeypatch):
    """素材比要的还少时也要打散顺序，不能永远取前几张。"""
    _patch_items(monkeypatch, posters=2, backdrops=2)
    ref = ServerRef(name="Emby", type="emby", instance=object())
    seen = set()
    for _ in range(40):
        assets = emby_assets.fetch_assets(ref, "lib1", mode="random", poster_count=2, backdrop_count=1)
        seen.add(assets["bg_url"])
        # 两张海报都要有机会被选中，且数量不多不少、不重复
        assert len(assets["posters"]) == 2
        assert len(set(assets["posters"])) == 2
    assert len(seen) > 1, "素材不足抽样数量时仍固定取第一张，随机没生效"


def test_random_mode_samples_large_pool(monkeypatch):
    """素材充足时用 random.sample，抽取结果应有变化且不重复。"""
    _patch_items(monkeypatch, posters=20, backdrops=8)
    ref = ServerRef(name="Emby", type="emby", instance=object())
    backgrounds = set()
    for _ in range(30):
        assets = emby_assets.fetch_assets(ref, "lib1", mode="random", poster_count=3, backdrop_count=2)
        assert len(assets["posters"]) == 3
        assert len(set(assets["posters"])) == 3, "抽样结果出现重复"
        assert len(assets["backdrops"]) == 2
        backgrounds.add(assets["bg_url"])
    assert len(backgrounds) > 1, "背景图每次都一样，随机没生效"


def test_latest_mode_is_stable(monkeypatch):
    """latest 模式仍按顺序取前几张（确定性），不随机。"""
    _patch_items(monkeypatch, posters=6, backdrops=3)
    ref = ServerRef(name="Emby", type="emby", instance=object())
    first = emby_assets.fetch_assets(ref, "lib1", mode="latest", poster_count=2, backdrop_count=1)
    second = emby_assets.fetch_assets(ref, "lib1", mode="latest", poster_count=2, backdrop_count=1)
    assert first["backdrops"] == second["backdrops"]
    assert first["posters"] == second["posters"]


@pytest.fixture(autouse=True)
def _clear_cache():
    api_controller._ASSETS_CACHE.clear()
    yield
    api_controller._ASSETS_CACHE.clear()


def _request(mode="random"):
    return api_schemas.CoverPreviewRequest(
        server="Emby",
        library_id="lib1",
        layout="分类横幅",
        config={},
        mode=mode,
        poster_count=2,
        backdrop_count=1,
    )


def test_random_mode_bypasses_assets_cache(monkeypatch):
    """random 模式不能命中素材缓存：命中就等于把上一次的素材原样还回去。"""
    _patch_items(monkeypatch, posters=20, backdrops=8)
    monkeypatch.setattr(api_controller.emby_gateway, "resolve", lambda server="": _Ref())

    seen = set()
    for _ in range(12):
        assets = api_controller._fetch_assets(_request("random"), _Ref(), {})
        seen.add(assets["bg_url"])
    assert len(seen) > 1, "random 模式命中了缓存，随机抽取仍是同一张"
    assert api_controller._ASSETS_CACHE == {}, "random 模式不该写入素材缓存"


def test_latest_mode_still_cached(monkeypatch):
    """latest 模式保留短缓存：同一库连续预览不必重复查询 Emby。"""
    calls = _patch_items(monkeypatch, posters=6, backdrops=3)
    monkeypatch.setattr(api_controller.emby_gateway, "resolve", lambda server="": _Ref())

    api_controller._fetch_assets(_request("latest"), _Ref(), {})
    first_round = len(calls)
    api_controller._fetch_assets(_request("latest"), _Ref(), {})
    assert len(calls) == first_round, "latest 模式应命中缓存，不该再查 Emby"
    assert api_controller._ASSETS_CACHE, "latest 模式应写入缓存"
