"""媒体库画质探测（1.13.38 修复）。

历史坑：``_fetch`` 用 ``media_type == "电视剧"`` 判剧集，而宿主给的是 ``"tv"``，
导致剧集全被当电影搜；电影分支又只请求 ``Fields=Path`` 拿不到 ``MediaSources``，
于是所有条目都落成空结果缓存，洗版永远判「无基线」。
"""
import importlib
import sys
import types

import pytest


def _module():
    module = importlib.import_module("app.plugins.tgmediacenter.services.library_quality")
    return module


def _item(path: str, *, size: int = 0, height=None, codec="", audio_codec=""):
    streams = []
    if height is not None or codec:
        video = {"Type": "Video"}
        if height is not None:
            video["Height"] = height
        if codec:
            video["Codec"] = codec
        streams.append(video)
    if audio_codec:
        streams.append({"Type": "Audio", "Codec": audio_codec})
    source = {"Path": path, "MediaStreams": streams}
    if size:
        source["Size"] = size
    return {"Id": "1", "Type": "Movie", "Path": path, "MediaSources": [source]}


def test_profile_prefers_filename_resolution_over_stream_height():
    """2160p 的 .strm 在 Emby 里 Height 报 1608，不能被降级成 1080p。"""
    module = _module()
    item = _item(
        "/media/影视/电影/功夫女足 (2026)/功夫女足 (2026) - 2160p.H.265.10-bit.24fps.HQ.DTS 5.1.strm",
        size=18235191634,
        height=1608,
        codec="hevc",
    )
    profile = module.LibraryQualityService._profile_of(item)

    assert profile is not None
    assert profile["resolution"] == "2160p"
    assert profile["known"] is True
    assert profile["size_mb"] == pytest.approx(17390.4, abs=1.0)


def test_profile_falls_back_to_stream_height_when_filename_has_no_resolution():
    module = _module()
    item = _item("/media/影视/电影/无名/movie.mkv", height=2160, codec="hevc")
    profile = module.LibraryQualityService._profile_of(item)

    assert profile is not None
    assert profile["resolution"] == "2160p"
    assert profile["codec"] == "hevc"


def test_profile_without_sources_uses_item_path():
    module = _module()
    item = {"Id": "1", "Type": "Movie", "Path": "/media/x/Show - 1080p.WEB-DL.mkv"}
    profile = module.LibraryQualityService._profile_of(item)

    assert profile is not None
    assert profile["resolution"] == "1080p"


def test_profile_returns_none_when_nothing_usable():
    module = _module()
    assert module.LibraryQualityService._profile_of({}) is None


class _FakeRow:
    def __init__(self, payload: str):
        self.profiles = payload


def test_cached_rejects_legacy_payload_without_version(monkeypatch):
    """旧版缓存（无 v 字段）必须失效重探，否则空结果会卡 7 天。"""
    module = _module()
    service = module.LibraryQualityService(db=None, plugin_id="TgMediaCenter")

    legacy = '{"ts": %d, "empty": true, "episodes": {}}' % int(module.time.time())
    monkeypatch.setattr(service, "_load_row", lambda key: _FakeRow(legacy))
    assert service.cached("x|2026|movie") is None

    fresh = '{"ts": %d, "v": %d, "empty": false, "episodes": {"0": {"resolution": "2160p"}}}' % (
        int(module.time.time()),
        module._PROBE_VERSION,
    )
    monkeypatch.setattr(service, "_load_row", lambda key: _FakeRow(fresh))
    assert service.cached("x|2026|movie") == {"0": {"resolution": "2160p"}}


def test_fetch_treats_tv_as_series(monkeypatch):
    """宿主 media_type 是 "tv"，必须按剧集走 /Shows/{id}/Episodes。"""
    module = _module()
    service = module.LibraryQualityService(db=None, plugin_id="TgMediaCenter")
    calls = []

    monkeypatch.setattr(service, "_clients", lambda: [("emby", "http://emby", "key", "user")])

    def fake_get(base, path, params):
        calls.append((path, dict(params)))
        if path == "/Items":
            assert params["IncludeItemTypes"] == "Series"
            return [{"Id": "743828", "Type": "Series", "Name": "尚公主"}]
        if path == "/Shows/743828/Episodes":
            return [
                {"IndexNumber": 1, "Path": "/media/尚公主.S01E01.2160p.strm", "MediaSources": [{"Path": "/media/尚公主.S01E01.2160p.strm"}]},
            ]
        return None

    monkeypatch.setattr(service, "_get", fake_get)

    episodes, item_id, server = service._fetch("尚公主", "2026", "tv")

    assert item_id == "743828"
    assert server == "emby"
    assert episodes["1"]["resolution"] == "2160p"
    assert any(path == "/Shows/743828/Episodes" for path, _ in calls)


def test_fetch_movie_refetches_detail_for_media_sources(monkeypatch):
    """电影搜索接口不回 MediaSources 时要补一次按 Id 的明细查询。"""
    module = _module()
    service = module.LibraryQualityService(db=None, plugin_id="TgMediaCenter")

    monkeypatch.setattr(service, "_clients", lambda: [("emby", "http://emby", "key", "user")])

    def fake_get(base, path, params):
        if path == "/Items" and params.get("SearchTerm"):
            assert params["IncludeItemTypes"] == "Movie"
            return [{"Id": "701059", "Type": "Movie", "Name": "功夫女足", "Path": "/media/功夫女足 - 2160p.strm"}]
        if path == "/Items" and params.get("Ids") == "701059":
            return [
                _item("/media/功夫女足 (2026) - 2160p.H.265.strm", size=18235191634, height=1608, codec="hevc"),
            ]
        return None

    monkeypatch.setattr(service, "_get", fake_get)

    episodes, item_id, _server = service._fetch("功夫女足", "2026", "movie")

    assert item_id == "701059"
    assert episodes["0"]["resolution"] == "2160p"
    assert episodes["0"]["size_mb"] == pytest.approx(17390.4, abs=1.0)
