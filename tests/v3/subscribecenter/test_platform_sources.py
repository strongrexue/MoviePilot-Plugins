"""平台首播源（腾讯视频 / B 站番剧）的单元测试。

两个源都依赖外部接口，测试只覆盖**纯函数部分**：
请求体是否还是合法的 JSON、卡片/时间表能否被正确翻译成
:class:`DiscoveredItem`、频道与窗口参数是否生效。
"""
import json

from app.plugins.subscribecenter.core.constants import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV
from app.plugins.subscribecenter.sources.bilibili import BilibiliSource
from app.plugins.subscribecenter.sources.qqvideo import (
    _PAYLOADS,
    CHANNELS,
    QqVideoSource,
    _cards,
    _strip_suffix,
    _to_item,
)


def _card(title="某剧", cid="mzc001", online="2026-10-29 12:00:00", wants="1234"):
    """造一张腾讯卡的 ``params`` 结构。"""
    params = {
        "title": title,
        "cid": cid,
        "online_time": online,
        "order_person_count": wants,
        "is_coming_soon": "1",
    }
    return {"params": params}


class TestQqVideo:
    def test_three_payloads_are_valid_json(self):
        assert set(_PAYLOADS) == {"tv", "movie", "variety"}
        for key, raw in _PAYLOADS.items():
            data = json.loads(raw)
            assert data["page_params"]["tab_type"] == "coming_soon", key
            assert data["flip_info"]["flip_params"]["source_key"], key

    def test_channels_cover_three_media_types(self):
        keys = [key for key, _label, _type in CHANNELS]
        assert keys == ["tv", "movie", "variety"]
        types = {media_type for _key, _label, media_type in CHANNELS}
        assert types == {MEDIA_TYPE_TV, MEDIA_TYPE_MOVIE}

    def test_card_with_date_becomes_dated_item(self):
        item = _to_item(_card(), MEDIA_TYPE_TV)
        assert item is not None
        assert item.release_date == "2026-10-29"
        assert item.year == "2026"
        assert item.date_unknown is False
        assert item.popularity == 1234.0
        assert item.source == "qq_video"
        assert item.media_type == MEDIA_TYPE_TV

    def test_card_without_date_is_marked_date_unknown(self):
        item = _to_item(_card(online=""), MEDIA_TYPE_MOVIE)
        assert item is not None
        assert item.release_date is None
        assert item.date_unknown is True

    def test_card_without_title_or_cid_is_dropped(self):
        assert _to_item({"params": {"cid": "x"}}, MEDIA_TYPE_TV) is None
        assert _to_item({"params": {"title": "某剧"}}, MEDIA_TYPE_TV) is None

    def test_cards_extracts_nested_list(self):
        data = {"data": {"card": {"children_list": {"list": {"cards": [{"a": 1}]}}}}}
        assert _cards(data) == [{"a": 1}]
        assert _cards({"data": {}}) == []
        assert _cards(None) == []

    def test_strip_suffix_removes_platform_noise(self):
        assert _strip_suffix("兰香如故·花胜秋宴") == "兰香如故"
        assert _strip_suffix("庆余年（会员版）") == "庆余年"
        assert _strip_suffix("狂飙") == "狂飙"

    def test_source_name(self):
        assert QqVideoSource().name == "qq_video"


class TestBilibili:
    @staticmethod
    def _day(pairs):
        """``[(season_id, title, ts)]`` -> 时间表的一天。"""
        return {
            "episodes": [
                {"season_id": sid, "title": title, "pub_ts": ts, "published": 0}
                for sid, title, ts in pairs
            ]
        }

    def test_keeps_earliest_episode_per_season(self):
        now = 1_800_000_000  # 远未来，避免「已播」过滤干扰
        days = [
            self._day([(1, "葬送的芙莉莲", now + 7200)]),
            self._day([(1, "葬送的芙莉莲", now + 3600)]),
        ]
        items = BilibiliSource._to_items(days, limit=10)
        assert len(items) == 1
        assert items[0].source_id == "1"
        assert items[0].source == "bilibili"
        assert items[0].media_type == MEDIA_TYPE_TV

    def test_skips_past_episodes(self):
        old = 1_600_000_000  # 2020 年
        days = [self._day([(2, "旧番", old)])]
        assert BilibiliSource._to_items(days, limit=10) == []

    def test_respects_limit_and_sorts_by_date(self):
        now = 1_800_000_000
        days = [
            self._day([(3, "丙", now + 86400 * 3)]),
            self._day([(1, "甲", now + 86400), (2, "乙", now + 86400 * 2)]),
        ]
        items = BilibiliSource._to_items(days, limit=2)
        assert len(items) == 2
        assert items[0].release_date <= items[1].release_date

    def test_source_name(self):
        assert BilibiliSource().name == "bilibili"
