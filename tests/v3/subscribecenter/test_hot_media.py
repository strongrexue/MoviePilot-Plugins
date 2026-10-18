"""热门媒体源：风格多选合并、评分与订阅人次筛选、去重。"""
import asyncio
import pathlib
import sys
from typing import Any, Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugins.v3"))


def _load():
    from subscribecenter.sources.hot_media import HotMediaSource

    return HotMediaSource


class FakeHelper:
    """按 (stype, genre_id) 返回预设行，并记录调用参数。"""

    def __init__(self, rows_by_key: Dict[Any, List[dict]]):
        self._rows = rows_by_key
        self.calls: List[dict] = []

    async def async_get_subscribe_statistic(self, **kwargs):
        self.calls.append(kwargs)
        key = (kwargs.get("stype"), kwargs.get("genre_id"))
        return list(self._rows.get(key, []))


def _row(name: str, count: int, rating: float = 8.0, media_id: int = 1) -> dict:
    return {
        "name": name,
        "count": count,
        "rating": rating,
        "media_source": "tmdb",
        "media_id": media_id,
        "year": "2025",
        "season": None,
    }


def test_genre_multi_merges_and_dedupes():
    source = _load()(FakeHelper({
        ("MOV", 28): [_row("A", 10, media_id=1), _row("B", 20, media_id=2)],
        ("MOV", 12): [_row("A", 10, media_id=1)],   # 与 28 重复
    }))
    config = {
        "hot_media_movie_enabled": True,
        "hot_media_tv_enabled": False,
        "hot_media_movie_limit": 20,
        "hot_media_movie_genres": [28, 12],
    }
    items = asyncio.run(source.fetch(config))
    assert [item.title for item in items] == ["A", "B"], "按媒体 id 去重"


def test_min_count_and_rating_filter():
    source = _load()(FakeHelper({
        ("TV", None): [
            _row("低分", 100, rating=5.0, media_id=1),
            _row("冷门", 3, rating=9.0, media_id=2),
            _row("合格", 50, rating=9.0, media_id=3),
        ],
    }))
    config = {
        "hot_media_movie_enabled": False,
        "hot_media_tv_enabled": True,
        "hot_media_tv_limit": 20,
        "hot_media_tv_min_count": 10,
        "hot_media_tv_min_rating": 7,
    }
    items = asyncio.run(source.fetch(config))
    assert [item.title for item in items] == ["合格"]


def test_empty_response_raises_with_hint():
    source = _load()(FakeHelper({}))
    config = {"hot_media_movie_enabled": True, "hot_media_tv_enabled": False}
    try:
        asyncio.run(source.fetch(config))
    except RuntimeError as err:
        assert "订阅数据共享" in str(err)
    else:  # pragma: no cover
        raise AssertionError("空数据应报错提示开启订阅数据共享")


def test_genre_list_accepts_comma_string():
    helper = FakeHelper({("MOV", 28): [_row("A", 10)]})
    source = _load()(helper)
    config = {
        "hot_media_movie_enabled": True,
        "hot_media_tv_enabled": False,
        "hot_media_movie_genres": "28",
    }
    items = asyncio.run(source.fetch(config))
    assert len(items) == 1
    assert helper.calls[0]["genre_id"] == 28
