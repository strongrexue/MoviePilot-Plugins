"""AniList 数据源的回归测试（1.0.0）。

锁住四条真机验证过的行为：

1. **双通道**：新番按 ``startDate``、连载中按 ``nextAiringEpisode`` 落窗口。
   国漫（长篇连载）只有第二条通道抓得到 —— 《遮天》2023 年开播、208 集，
   用「开播日 + 窗口」永远对不上。
2. **国漫标题**：``countryOfOrigin=CN`` 的 ``title.native`` 就是中文原名，
   直接用作首选标题；日番用 ``native``（日文），罗马音留作原名。
3. **国漫开关**：关掉后 CN 条目必须被排除。
4. **失败必须抛**：查询失败静默返回空会被当成「今天没新番」。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.sources import anilist as al  # noqa: E402


class FakeClient:
    """按查询类型返回预置数据的假客户端。"""

    def __init__(self, season_pages=None, ongoing_pages=None, donghua_pages=None, fail=False):
        self.season_pages = season_pages or []
        self.ongoing_pages = ongoing_pages or []
        self.donghua_pages = donghua_pages or []
        self.fail = fail
        self.calls = 0
        self.donghua_calls = 0

    async def post(self, url, json=None):  # noqa: ANN001
        self.calls += 1
        if self.fail:
            raise RuntimeError("网络不可达")
        query = (json or {}).get("query", "")
        page = int((json or {}).get("variables", {}).get("page") or 1)
        if 'countryOfOrigin: "CN"' in query:
            self.donghua_calls += 1
            rows = self.donghua_pages
        elif "status: RELEASING" in query:
            rows = self.ongoing_pages
        else:
            rows = self.season_pages
        data = rows[page - 1] if page - 1 < len(rows) else []

        class Response:
            @staticmethod
            def json():
                return {"data": {"Page": {"media": data}}}

        return Response()


def media(index, *, native, start=None, country="JP", next_days=None, **extra):
    """构造一条 AniList media。"""
    payload = {
        "id": 1000 + index,
        "idMal": 2000 + index,
        "countryOfOrigin": country,
        "isAdult": False,
        "format": "TV",
        "status": "RELEASING",
        "episodes": 12,
        "popularity": 5000,
        "averageScore": 80,
        "season": "FALL",
        "seasonYear": 2026,
        "title": {"native": native, "romaji": f"Romaji {index}", "english": None},
        "startDate": None,
        "nextAiringEpisode": None,
    }
    if start is not None:
        payload["startDate"] = {"year": start.year, "month": start.month, "day": start.day}
    if next_days is not None:
        moment = next_days
        payload["nextAiringEpisode"] = {
            "episode": 5,
            "airingAt": int(moment.replace(tzinfo=None).timestamp()),
        }
    payload.update(extra)
    return payload


def as_utc(day):
    """把日期变成正午（UTC 秒精度足够）。"""
    from datetime import datetime, timezone

    return datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)


def run(coro):
    """同步跑协程。"""
    import asyncio

    return asyncio.run(coro)


# --------------------------------------------------------------------- 通道与标题

def test_season_channel_uses_start_date():
    """新番通道：开播日在窗口内 → 收；窗口外 → 丢。"""
    today = date.today()
    client = FakeClient(
        season_pages=[
            [
                media(1, native="新番A", start=today + timedelta(days=1)),
                media(2, native="太远的新番", start=today + timedelta(days=30)),
                media(3, native="已经开播", start=today - timedelta(days=20)),
            ]
        ]
    )
    items = run(al.AniListSource(client).fetch({"anilist_future_days": 3}))
    titles = {item.title for item in items}
    assert "新番A" in titles
    assert "太远的新番" not in titles
    assert "已经开播" not in titles


def test_ongoing_channel_uses_next_airing():
    """连载通道：按「下一集播出时间」落窗口 —— 国漫的唯一入口。"""
    today = date.today()
    client = FakeClient(
        season_pages=[[]],
        ongoing_pages=[
            [
                media(11, native="遮天", country="CN",
                      start=today - timedelta(days=900),
                      next_days=as_utc(today + timedelta(days=2))),
                media(12, native="下周才更", country="CN",
                      start=today - timedelta(days=900),
                      next_days=as_utc(today + timedelta(days=20))),
            ]
        ],
    )
    items = run(al.AniListSource(client).fetch({"anilist_future_days": 3}))
    assert [item.title for item in items] == ["遮天"], "连载中的国漫必须靠下一集时间进窗口"
    assert items[0].raw["channel"] == "ongoing"
    assert items[0].year == str(today.year - 2), "年份应取开播年，而不是下一集那年"


def test_donghua_native_title_is_chinese():
    """国漫首选中文原名；日番用日文原名、罗马音作 original_title。"""
    today = date.today()
    client = FakeClient(
        season_pages=[
            [
                media(21, native="凡人修仙传 第四季", country="CN",
                      start=today + timedelta(days=1)),
                media(22, native="ジョジョの奇妙な冒険", country="JP",
                      start=today + timedelta(days=1)),
            ]
        ]
    )
    items = run(al.AniListSource(client).fetch({"anilist_future_days": 3}))
    by_title = {item.title: item for item in items}
    assert "凡人修仙传 第四季" in by_title
    assert by_title["凡人修仙传 第四季"].original_title.startswith("Romaji")
    assert "ジョジョの奇妙な冒険" in by_title


def test_donghua_switch_excludes_cn():
    """关掉「包含国漫」后 CN 条目必须被排除。"""
    today = date.today()
    client = FakeClient(
        season_pages=[
            [
                media(31, native="某国漫", country="CN", start=today + timedelta(days=1)),
                media(32, native="某日番", country="JP", start=today + timedelta(days=1)),
            ]
        ]
    )
    items = run(
        al.AniListSource(client).fetch(
            {"anilist_future_days": 3, "anilist_include_donghua": False}
        )
    )
    assert [item.title for item in items] == ["某日番"]


def test_source_id_and_native_ids():
    """原生 ID 必须带上 anilist 与 mal，供身份缓存与排查使用。"""
    today = date.today()
    client = FakeClient(season_pages=[[media(41, native="某番", start=today + timedelta(days=1))]])
    items = run(al.AniListSource(client).fetch({"anilist_future_days": 3}))
    assert items[0].source == C.SOURCE_ANILIST
    assert items[0].source_id == "1041"
    assert items[0].native_ids == {"anilist": "1041", "mal": "2041"}


def test_query_failure_raises():
    """查询失败必须抛 —— 静默返回空会被当成「今天没新番」。"""
    with pytest.raises(RuntimeError):
        run(al.AniListSource(FakeClient(fail=True)).fetch({"anilist_future_days": 3}))


def test_movie_format_maps_to_movie():
    """MOVIE 格式映射成电影，其余按剧集处理。"""
    today = date.today()
    client = FakeClient(
        season_pages=[
            [
                media(51, native="某剧场版", start=today + timedelta(days=1), format="MOVIE"),
                media(52, native="某番", start=today + timedelta(days=1), format="TV"),
            ]
        ]
    )
    items = run(al.AniListSource(client).fetch({"anilist_future_days": 3}))
    types = {item.title: item.media_type for item in items}
    assert types["某剧场版"] == C.MEDIA_TYPE_MOVIE
    assert types["某番"] == C.MEDIA_TYPE_TV


# --------------------------------------------------------------------- 赛季计算

def test_season_math():
    """季度边界：1-3 冬、4-6 春、7-9 夏、10-12 秋。"""
    assert al.season_of(date(2026, 1, 15)) == ("WINTER", 2026)
    assert al.season_of(date(2026, 4, 1)) == ("SPRING", 2026)
    assert al.season_of(date(2026, 7, 31)) == ("SUMMER", 2026)
    assert al.season_of(date(2026, 10, 17)) == ("FALL", 2026)
    assert al.next_season("FALL", 2026) == ("WINTER", 2027)
    assert al.next_season("WINTER", 2026) == ("SPRING", 2026)

def test_donghua_without_schedule_is_date_unknown():
    """国漫没有 nextAiringEpisode 时不能丢弃 —— 标记 date_unknown 交给 TMDB。

    真机：AniList 不跟踪 遮天 / 吞噬星空 的播出表（nextAiringEpisode=None）。
    如果退回去用 2023 年的开播日，会被窗口直接丢掉，等于永远发现不了。
    """
    today = date.today()
    client = FakeClient(
        season_pages=[[]],
        ongoing_pages=[[]],
        donghua_pages=[
            [
                media(61, native="遮天", country="CN",
                      start=today - timedelta(days=900)),
                media(62, native="有播出表的国漫", country="CN",
                      start=today - timedelta(days=900),
                      next_days=as_utc(today + timedelta(days=1))),
            ]
        ],
    )
    items = run(al.AniListSource(client).fetch({"anilist_future_days": 3}))
    by_title = {item.title: item for item in items}
    assert "遮天" in by_title, "没有播出表的国漫必须靠 date_unknown 放行"
    assert by_title["遮天"].date_unknown is True
    assert by_title["遮天"].release_date is None
    assert "有播出表的国漫" in by_title
    assert by_title["有播出表的国漫"].date_unknown is False


def test_donghua_channel_skipped_when_switch_off():
    """关掉国漫开关后，不应再发国漫专用查询。"""
    client = FakeClient(season_pages=[[]], ongoing_pages=[[]], donghua_pages=[[media(71, native="某国漫", country="CN")]])
    items = run(
        al.AniListSource(client).fetch(
            {"anilist_future_days": 3, "anilist_include_donghua": False}
        )
    )
    assert items == []
    assert client.donghua_calls == 0

# --------------------------------------------------------------------- 海报

@pytest.mark.asyncio
async def test_poster_is_attached_from_host_index():
    """解析成功后要把海报路径回填到条目（流水页显示封面）。

    两条来源：候选候选里的 poster_path，以及宿主 resolve_target_season
    拉 TMDB 详情时顺带记下的路径（零额外请求）。
    """
    from subscribecenter.core.identity import IdentityResolver

    class Resolver:
        def __init__(self):
            self._posters = {"693134": "/dune2.jpg"}

        async def search(self, title, year, media_type, *, limit=5):
            return [
                {
                    "tmdb_id": "693134",
                    "title": title,
                    "year": year or "2026",
                    "media_type": media_type,
                    "poster_path": "/dune2.jpg",
                }
            ]

        async def resolve_target_season(self, tmdb_id, media_type, season_hint=None, tz_name=None, **kw):
            return (True, 1, None)

    from subscribecenter.core.model import DiscoveredItem

    entity = DiscoveredItem(
        source=C.SOURCE_TMDB,
        source_id="1",
        title="沙丘2",
        media_type=C.MEDIA_TYPE_MOVIE,
        year="2026",
        release_date="2026-11-01",
    )
    resolver = IdentityResolver(Resolver())
    await resolver.resolve(entity)
    assert entity.resolved is not None
    assert entity.raw.get("poster") == "/dune2.jpg"


# ------------------------------------------------ 国漫续作豁免（1.2.3 真机）

def test_donghua_is_exempt_from_continuation_year_floor():
    """国漫续作不加年份下限。

    真机：完美世界 第七季 / 妖神记 第十季 / 万界独尊 第三季 / 逆天邪神 第2季
    全部是 L4 待确认 —— 国漫在 TMDB 是「单条目 + 首播年很早（2018~2021）」，
    而 AniList 条目年份是该季年份（2026），续作年份闸门把候选全拒了。
    国漫的正确性交给季号裁决 + 「TMDB 还有没有未播集」，不需要年份下限。
    """
    from subscribecenter.core.identity import _continuation_floor
    from subscribecenter.core.model import DiscoveredItem

    donghua = DiscoveredItem(
        source=C.SOURCE_ANILIST, source_id="1", title="完美世界 第七季",
        media_type="tv", year="2026", release_date="2026-10-20",
        raw={"country": "CN"},
    )
    jp = DiscoveredItem(
        source=C.SOURCE_ANILIST, source_id="2", title="某番 第2期",
        media_type="tv", year="2026", release_date="2026-10-20",
        raw={"country": "JP"},
    )
    assert _continuation_floor(donghua) is None, "国漫不应有年份下限"
    assert _continuation_floor(jp) == 2026, "日番续作仍要年份下限"
