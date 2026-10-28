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
    """音乐库角标只数专辑；计数端点与素材查询一致（Users/{uid}/Items）。"""
    calls = []

    def fake_get_json(ref, path, params=None):
        if path == "Library/MediaFolders":
            return {"Items": [{"Id": "m1", "CollectionType": "music"}]}
        if path.endswith("/Items"):
            calls.append(dict(params or {}))
            return {"TotalRecordCount": 11}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(emby_assets, "admin_user_id", lambda ref: "uid")
    assert emby_assets.library_count(_Ref(), "m1") == 11
    assert calls and calls[0]["IncludeItemTypes"] == "MusicAlbum"


def test_fetch_assets_music_uses_album_posters(monkeypatch):
    """音乐库整链路：素材（背景/海报）查询带 MusicAlbum,MusicArtist；计数查询只数 MusicAlbum。"""
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
    asset_queries = [p for p in captured if p.get("ImageTypes")]
    count_queries = [p for p in captured if not p.get("ImageTypes")]
    assert asset_queries, "应发起素材查询"
    assert all(p["IncludeItemTypes"] == "MusicAlbum,MusicArtist" for p in asset_queries)
    assert count_queries and all(p["IncludeItemTypes"] == "MusicAlbum" for p in count_queries)
    assert assets["posters"] == [] and assets["count"] == 0


def test_library_name_reads_views_and_caches(monkeypatch):
    """库名取自 Users/{uid}/Views；同一库连续查询只打一次接口（预览会反复要库名）。"""
    emby_assets._LIBRARY_NAME_CACHE.clear()
    calls = []

    def fake_get_json(ref, path, params=None):
        calls.append(path)
        if path == "Users/uid/Views":
            return {"Items": [{"Id": "lib1", "Name": "国产剧"}]}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(emby_assets, "admin_user_id", lambda ref: "uid")
    assert emby_assets.library_name(_Ref(), "lib1") == "国产剧"
    assert emby_assets.library_name(_Ref(), "lib1") == "国产剧"
    assert calls.count("Users/uid/Views") == 1, "第二次应命中缓存"
    # 查不到的库返回空串（调用方回退到 ID），且不该污染缓存
    assert emby_assets.library_name(_Ref(), "ghost") == ""
    assert emby_assets.library_name(_Ref(), "") == ""
    emby_assets._LIBRARY_NAME_CACHE.clear()


def test_library_genres_ranks_by_frequency(monkeypatch):
    """题材按出现次数降序、最多 6 个；只统计主体类型（音乐库不混入艺术家）。"""
    captured = []

    def fake_get_json(ref, path, params=None):
        if path == "Library/MediaFolders":
            return {"Items": [{"Id": "lib1", "CollectionType": "movies"}]}
        if path.endswith("/Items"):
            captured.append(dict(params or {}))
            return {"Items": [
                {"Genres": ["剧情", "悬疑"]},
                {"Genres": ["剧情", "动作"]},
                {"Genres": ["剧情", "悬疑", "犯罪"]},
            ]}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(emby_assets, "admin_user_id", lambda ref: "uid")
    genres = emby_assets.library_genres(_Ref(), "lib1")
    assert genres[:2] == ["剧情", "悬疑"], f"排序不对：{genres}"
    assert "动作" in genres and "犯罪" in genres
    assert len(genres) <= emby_assets.MAX_GENRES
    assert captured and captured[0]["Fields"] == "Genres"
    assert captured[0]["IncludeItemTypes"] == "Movie"


def test_library_genres_returns_empty_on_error(monkeypatch):
    """题材接口失败时返回空列表，由布局回退到手填标签。"""

    def boom(ref, path, params=None):
        raise emby_assets.emby_gateway.GatewayError("timeout")

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", boom)
    assert emby_assets.library_genres(_Ref(), "lib1") == []
    assert emby_assets.library_genres(_Ref(), "") == []


def test_fetch_assets_exposes_library_metadata(monkeypatch):
    """fetch_assets 必须带回 library_id / library_name / library_en / genres。

    布局「分类横幅」直接读这四个键当标题、英文名、按库主视觉与自动标签，
    缺了它们就只能靠用户手填。
    """
    emby_assets._LIBRARY_NAME_CACHE.clear()

    def fake_get_json(ref, path, params=None):
        if path == "Library/MediaFolders":
            return {"Items": [{"Id": "lib1", "CollectionType": "movies"}]}
        if path == "Users/uid/Views":
            return {"Items": [{"Id": "lib1", "Name": "华语电影"}]}
        if path.endswith("/Items"):
            if params and params.get("Fields") == "Genres":
                return {"Items": [{"Genres": ["剧情"]}]}
            return {"Items": [], "TotalRecordCount": 0}
        return {}

    monkeypatch.setattr(emby_assets.emby_gateway, "get_json", fake_get_json)
    monkeypatch.setattr(emby_assets, "admin_user_id", lambda ref: "uid")
    ref = ServerRef(name="Emby", type="emby", instance=object())
    assets = emby_assets.fetch_assets(ref, "lib1", mode="random", poster_count=1, backdrop_count=1)
    assert assets["library_id"] == "lib1"
    assert assets["library_name"] == "华语电影"
    assert assets["library_en"] == "CHINESE FILMS"
    assert assets["genres"] == ["剧情"]
    emby_assets._LIBRARY_NAME_CACHE.clear()
