"""emby_assets 素材查询的类型适配测试：音乐库取专辑、影视库照旧、未知库兜底。"""

from app.plugins.embycovercenter.service import emby_assets
from app.plugins.embycovercenter.service.emby_gateway import ServerRef


class _Ref:
    name = "Emby"


def _patch_media_folders(monkeypatch, folders):
    monkeypatch.setattr(
        emby_assets.emby_gateway,
        "get_json",
        lambda ref, path, params=None: {"Items": folders} if path == "Library/MediaFolders" else {},
    )


def test_include_types_music_library(monkeypatch):
    """音乐库拉 MusicAlbum + MusicArtist（只刮了艺术家的库用艺术家图兜底）。"""
    _patch_media_folders(
        monkeypatch,
        [{"Id": "lib1", "CollectionType": "music"}, {"Id": "lib2", "CollectionType": "movies"}],
    )
    assert emby_assets._include_types(_Ref(), "lib1") == "MusicAlbum,MusicArtist"


def test_include_types_movie_and_tv(monkeypatch):
    """电影/剧集库行为不变。"""
    _patch_media_folders(
        monkeypatch,
        [{"Id": "lib1", "CollectionType": "movies"}, {"Id": "lib2", "CollectionType": "tvshows"}],
    )
    assert emby_assets._include_types(_Ref(), "lib1") == "Movie"
    assert emby_assets._include_types(_Ref(), "lib2") == "Series"


def test_include_types_unknown_fallback(monkeypatch):
    """混合库 / 未知类型 / 类型查询失败时全类型兜底。"""
    _patch_media_folders(monkeypatch, [{"Id": "lib1", "CollectionType": "mixed"}])
    assert emby_assets._include_types(_Ref(), "lib1") == "Movie,Series,MusicAlbum"
    assert emby_assets._include_types(_Ref(), "ghost") == "Movie,Series,MusicAlbum"


def test_include_types_gateway_error_fallback(monkeypatch):
    """MediaFolders 接口失败时兜底为全类型，不拖垮素材拉取。"""

    def boom(ref, path, params=None):
        raise emby_assets.emby_gateway.GatewayError("timeout")

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", boom)
    assert emby_assets._include_types(_Ref(), "lib1") == "Movie,Series,MusicAlbum"


def test_library_count_music_counts_albums_only(monkeypatch):
    """音乐库角标只数专辑：素材查询含艺术家兜底，计数不含（避免显示翻倍）。"""
    calls = []

    def fake_get_json(ref, path, params=None):
        if path == "Library/MediaFolders":
            return {"Items": [{"Id": "m1", "CollectionType": "music"}]}
        if path == "Items":
            calls.append(dict(params or {}))
            return {"TotalRecordCount": 11}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    assert emby_assets.library_count(_Ref(), "m1") == 11
    assert calls and calls[0]["IncludeItemTypes"] == "MusicAlbum"


def test_fetch_assets_music_uses_album_posters(monkeypatch):
    """音乐库整链路：fetch_assets 的海报查询应带 MusicAlbum,MusicArtist 类型。"""
    captured = []

    def fake_get_json(ref, path, params=None):
        if path == "Library/MediaFolders":
            return {"Items": [{"Id": "m1", "CollectionType": "music"}]}
        if path.endswith("/Items"):
            captured.append(dict(params or {}))
            return {"Items": [], "TotalRecordCount": 0}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(emby_assets, "admin_user_id", lambda ref: "uid")
    ref = ServerRef(name="Emby", type="emby", instance=object())
    assets = emby_assets.fetch_assets(ref, "m1", mode="latest", poster_count=6, backdrop_count=1)
    assert captured, "应发起 Items 查询"
    assert all(p["IncludeItemTypes"] == "MusicAlbum,MusicArtist" for p in captured)
    assert assets["posters"] == [] and assets["count"] == 0
