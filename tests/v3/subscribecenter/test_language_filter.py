"""原始语言过滤与发现窗口的回归测试（0.3.0）。"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.sources.tmdb import TmdbSource, _language_filter  # noqa: E402

TODAY = date.today()


class FakeApi:
    """记录请求参数的 TMDB 替身。"""

    def __init__(self, movies=None, tvs=None):
        self._movies = movies or []
        self._tvs = tvs or []
        self.calls = []

    async def async_discover_movies(self, params):
        """记录并返回电影。"""
        self.calls.append(("movie", dict(params)))
        return list(self._movies)

    async def async_discover_tvs(self, params):
        """记录并返回剧集。"""
        self.calls.append(("tv", dict(params)))
        return list(self._tvs)


def movie(mid=1, rel=None):
    """构造一条电影结果。"""
    return {
        "id": mid,
        "title": "片",
        "release_date": rel or (TODAY + timedelta(days=2)).isoformat(),
        "vote_average": 0,
        "popularity": 20.0,
    }


BASE = {
    "tmdb_future_days": 3,
    "min_rating_tmdb": 6.0,
    "timezone": "Asia/Shanghai",
}


# --------------------------------------------------------------------- 语言解析

@pytest.mark.parametrize(
    "cfg,expected",
    [
        ({"filter_original_language": True, "tmdb_original_languages": "zh,ja,ko,en"}, "zh|ja|ko|en"),
        ({"filter_original_language": True, "tmdb_original_languages": "zh|ja"}, "zh|ja"),
        ({"filter_original_language": True, "tmdb_original_languages": ["zh", "en"]}, "zh|en"),
        ({"filter_original_language": False, "tmdb_original_languages": "zh"}, ""),
        ({"filter_original_language": True, "tmdb_original_languages": ""}, ""),
        ({"filter_original_language": True, "tmdb_original_languages": " zh , , ja "}, "zh|ja"),
        ({"filter_original_language": True, "tmdb_original_languages": "zh,!!,ja"}, "zh|ja"),
        ({"filter_original_language": True, "tmdb_original_languages": "zh,zh,ja"}, "zh|ja"),
        ({}, ""),
    ],
)
def test_language_filter_parsing(cfg, expected):
    """语言列表：去空白、去非法码、去重，用竖线并列；关闭时为空。"""
    assert _language_filter(cfg) == expected


# --------------------------------------------------------------------- 请求参数

@pytest.mark.asyncio
async def test_sends_original_language_when_enabled():
    """开启语言过滤时，请求必须带 ``with_original_language``。"""
    api = FakeApi(movies=[movie()])
    await TmdbSource(api, max_pages=1).fetch({
        **BASE, "filter_original_language": True,
        "tmdb_original_languages": "zh,ja,ko,en",
    })
    params = api.calls[0][1]
    assert params["with_original_language"] == "zh|ja|ko|en"


@pytest.mark.asyncio
async def test_omits_language_when_disabled():
    """关闭语言过滤时不得发送该参数（保持不限语言）。"""
    api = FakeApi(movies=[movie()])
    await TmdbSource(api, max_pages=1).fetch({
        **BASE, "filter_original_language": False,
        "tmdb_original_languages": "zh",
    })
    assert "with_original_language" not in api.calls[0][1]


@pytest.mark.asyncio
async def test_language_applies_to_both_media_types():
    """语言过滤对电影与剧集同时生效。"""
    api = FakeApi(movies=[movie()], tvs=[{
        "id": 9, "name": "剧", "first_air_date": (TODAY + timedelta(days=1)).isoformat(),
        "vote_average": 0, "popularity": 20.0,
    }])
    await TmdbSource(api, max_pages=1).fetch({
        **BASE, "filter_original_language": True,
        "tmdb_original_languages": "zh,ko",
    })
    kinds = {kind for kind, _ in api.calls}
    assert kinds == {"movie", "tv"}
    for _kind, params in api.calls:
        assert params["with_original_language"] == "zh|ko"


# --------------------------------------------------------------------- 窗口

def test_default_window_is_8_days():
    """默认窗口 3 天：PT 资源普遍上映后才有，提前订只是空转。

    3 天窗口 = 上映前 3 天进窗口，仍有 4 次运行机会吸收单次失败。
    """
    assert C.DEFAULT_FUTURE_DAYS == 3
    assert C.default_config()["tmdb_future_days"] == 3


@pytest.mark.asyncio
async def test_window_upper_bound_matches_config():
    """上界必须等于「今天 + 配置天数」。"""
    api = FakeApi(movies=[movie()])
    await TmdbSource(api, max_pages=1).fetch({**BASE, "tmdb_future_days": 3})
    params = api.calls[0][1]
    start = date.fromisoformat(params["primary_release_date.gte"])
    end = date.fromisoformat(params["primary_release_date.lte"])
    assert (end - start).days == 3


# --------------------------------------------------------------------- 配置一致性

def test_language_config_keys_declared_both_sides():
    """语言过滤的两个配置键必须两侧都有（整份覆盖语义）。"""
    cfg = C.default_config()
    assert cfg["filter_original_language"] is True
    assert cfg["tmdb_original_languages"] == C.DEFAULT_ORIGINAL_LANGUAGES

    frontend = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "configDefaults.js"
    )
    if frontend.exists():
        text = frontend.read_text(encoding="utf-8")
        assert "filter_original_language" in text
        assert "tmdb_original_languages" in text
