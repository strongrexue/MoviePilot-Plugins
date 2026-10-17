"""待确认（L4）修复：搜索词变体 + 跨路线去重（0.8.4）。

真机数据：一次运行 249 条 / 新增 66 / 跳过 183 / **待确认 38**，全部是
douban_rss 的 L4（TMDB 搜不到）。逐条实测后发现三类可修：

1. **标题带年份**：豆瓣综艺把年份写进标题（妻子的浪漫旅行2026、歌手2026、
   披荆斩棘2026、我家那闺女2026），而 TMDB 里不带年份。实测再去掉年份后
   4 条全部命中。

2. **宿主识别给出错误结果后没有第二次机会**：宿主把「豫见她们 第2季」
   识别成了别的剧，旧实现据此直接返回单条候选，我们的匹配规则拒掉之后就
   退化成待确认。现在识别结果只是**候选之一**，始终补一次原始搜索；
   身份层还会用「去尾部年份」等变体再试。

3. **跨路线重复**：`/douban/tv/coming` 带 subject id，`/douban/list/*` 的
   link 是空的只能用标题造 id —— 同一部剧出现在两类路线里 source_id 不同，
   被当成两条（伊甸园之东、流人 第六季、爱上草莓的季节 各两次）。
"""
import sys
from datetime import date
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.identity import (  # noqa: E402
    IdentityResolver,
    search_variants,
    strip_trailing_year,
)
from subscribecenter.core.model import DiscoveredItem  # noqa: E402
from subscribecenter.core.pipeline import dedupe_within_source  # noqa: E402

TODAY = date.today()


# --------------------------------------------------------------------- 去年份

@pytest.mark.parametrize(
    "raw,expected",
    [
        # 真机待确认的综艺，去掉年份后 TMDB 可命中
        ("妻子的浪漫旅行2026", "妻子的浪漫旅行"),
        ("我家那闺女2026", "我家那闺女"),
        ("披荆斩棘2026", "披荆斩棘"),
        ("歌手2026", "歌手"),
        # 带分隔符
        ("披荆斩棘 2026", "披荆斩棘"),
        # 片名里像年份的数字不能被削（2099 超出合理范围）
        ("银翼杀手2099", "银翼杀手2099"),
        # 老片名
        ("1917", "1917"),
        # 没有年份
        ("Dreamland", "Dreamland"),
        ("流人 第六季", "流人 第六季"),
    ],
)
def test_strip_trailing_year(raw, expected):
    """只削「合理的年份」，不能把片名里的数字当成年份。"""
    assert strip_trailing_year(raw) == expected


def test_search_variants_order():
    """搜索词依次为：去季号 -> 再去尾部年份。"""
    assert search_variants("牧神记5") == ["牧神记"]
    assert search_variants("妻子的浪漫旅行2026") == ["妻子的浪漫旅行2026", "妻子的浪漫旅行"]
    assert search_variants("流人 第六季") == ["流人"]
    assert search_variants("Dreamland") == ["Dreamland"]


# --------------------------------------------------------------------- 变体重试

class VariantTmdb:
    """主搜索空手而归、变体搜索能命中的 TMDB 替身。"""

    def __init__(self, variant_hit=True):
        self.variant_hit = variant_hit
        self.raw_calls = []

    async def search(self, title, year, media_type, *, limit=5):
        return ()

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        return None

    async def search_raw(self, term, media_type):
        self.raw_calls.append(term)
        if self.variant_hit and term == "妻子的浪漫旅行":
            return (
                {
                    "tmdb_id": 97199,
                    "title": "妻子的浪漫旅行",
                    "year": "2018",
                    "media_type": media_type,
                },
            )
        return ()

    async def resolve_target_season(self, tmdb_id, media_type, season_hint=None, **kwargs):
        return (True, 1, None)


def show(**overrides):
    """构造一条剧集条目。"""
    data = {
        "source": C.SOURCE_DOUBAN_RSS,
        "source_id": "title:妻子的浪漫旅行2026",
        "title": "妻子的浪漫旅行2026",
        "media_type": C.MEDIA_TYPE_TV,
        "year": "2026",
        "release_date": None,
        "date_unknown": True,
        "native_ids": {},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


@pytest.mark.asyncio
async def test_resolver_retries_with_variants():
    """主搜索无候选时，用「去年份」的变体重试并命中。"""
    tmdb = VariantTmdb()
    item = await IdentityResolver(tmdb).resolve(show())

    assert item.resolved is not None, "变体重试没有生效"
    assert item.resolved.media_id == "97199"
    assert "variant:" in item.resolved.reason
    assert "妻子的浪漫旅行" in tmdb.raw_calls


@pytest.mark.asyncio
async def test_variant_retry_stops_at_first_hit():
    """命中即停，不做多余请求。

    顺序：先用**条目标题本身**做原始搜索（绕过宿主那层名称过滤），
    再用「去年份」的变体。
    """
    tmdb = VariantTmdb()
    await IdentityResolver(tmdb).resolve(show())
    assert tmdb.raw_calls == ["妻子的浪漫旅行2026", "妻子的浪漫旅行"]


@pytest.mark.asyncio
async def test_no_variant_method_is_tolerated():
    """宿主没实现 search_raw 时不能崩（向后兼容）。"""

    class NoRaw(VariantTmdb):
        search_raw = None

    item = await IdentityResolver(NoRaw()).resolve(show())
    assert item.resolved is None


# --------------------------------------------------------------------- 跨路线去重

def make(source_id, title, native_ids=None, year="2026", media_type=None):
    """构造条目。"""
    return DiscoveredItem(
        source=C.SOURCE_DOUBAN_RSS,
        source_id=source_id,
        title=title,
        media_type=media_type or C.MEDIA_TYPE_TV,
        year=year,
        release_date=None,
        date_unknown=True,
        native_ids=native_ids or {},
    )


def test_same_title_across_routes_is_merged():
    """同一部剧出现在「带 id 的路线」和「不带 id 的路线」里要合并成一条。

    真机：伊甸园之东、流人 第六季、爱上草莓的季节 各出现两次。
    """
    with_id = make("34607563", "伊甸园之东", {"douban": "34607563"})
    without_id = make("title:伊甸园之东", "伊甸园之东")
    result = dedupe_within_source([without_id, with_id])

    assert len(result) == 1
    # 保留带原生 id 的那条（省一次标题搜索）
    assert result[0].native_ids == {"douban": "34607563"}


def test_both_with_different_ids_are_kept():
    """两条都带原生 id 且不同 -> 是不同的作品（同名），都要保留。"""
    first = make("111", "同名剧", {"douban": "111"})
    second = make("222", "同名剧", {"douban": "222"})
    assert len(dedupe_within_source([first, second])) == 2


def test_different_year_is_not_merged():
    """同名但年份不同 -> 不合并。"""
    first = make("a", "某剧", year="2025")
    second = make("b", "某剧", year="2026")
    assert len(dedupe_within_source([first, second])) == 2


def test_different_media_type_is_not_merged():
    """同名但一个是电影一个是剧集 -> 不合并。"""
    first = make("a", "某作", media_type=C.MEDIA_TYPE_TV)
    second = make("b", "某作", media_type=C.MEDIA_TYPE_MOVIE)
    assert len(dedupe_within_source([first, second])) == 2


def test_same_source_id_still_deduped():
    """原有的 source_id 去重行为不变。"""
    first = make("x", "第一条")
    second = make("x", "第二条")
    result = dedupe_within_source([first, second])
    assert len(result) == 1
    assert result[0].title == "第一条"


# --------------------------------------------------------------------- 原因文案

@pytest.mark.asyncio
async def test_pending_reason_lists_tried_terms():
    """「待确认」要写明尝试过哪些搜索词 —— 只写「无确定性身份」没有信息量。"""
    from subscribecenter.core.writer import SubscriptionWriter

    class NoopBackend:
        async def subscription_exists(self, media_source, media_id, season=None):
            return False

        async def history_exists(self, media_source, media_id, season=None):
            return False

        async def add(self, *args, **kwargs):
            raise AssertionError("不该写入")

    item = show(
        title="流人 第六季",
        raw={"search_variants": ["流人"]},
    )
    writer = SubscriptionWriter(NoopBackend(), daily_limit=0)
    report = await writer.write([item], dry_run=False)

    reason = report.outcomes[0].reason
    assert report.outcomes[0].decision == C.DECISION_PENDING_REVIEW
    assert "流人" in reason, "原因里没写尝试过的搜索词"
    assert "手动订阅" in reason, "原因里没给出下一步"


@pytest.mark.asyncio
async def test_pending_reason_without_variants_still_readable():
    """没有变体信息时也要给出可读原因。"""
    from subscribecenter.core.writer import SubscriptionWriter

    class NoopBackend:
        async def subscription_exists(self, media_source, media_id, season=None):
            return False

        async def history_exists(self, media_source, media_id, season=None):
            return False

        async def add(self, *args, **kwargs):
            raise AssertionError("不该写入")

    writer = SubscriptionWriter(NoopBackend(), daily_limit=0)
    report = await writer.write([show(raw={})], dry_run=False)
    assert "手动订阅" in report.outcomes[0].reason
