"""身份分级解析 L1–L4 的回归测试。

**本文件最重要的断言是「L4 永不写入」** —— 那是整个插件防止误写的核心闸门
（开发文档 §6.2）。
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core import constants as C  # noqa: E402
from core.cache import MappingCacheStore  # noqa: E402
from core.identity import (  # noqa: E402
    IdentityResolver,
    match_candidate_year,
    normalize_title,
    resolve_from_native_ids,
    review_candidates,
    title_similarity,
)
from core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402

# --------------------------------------------------------------------- 假件

class FakeTmdb:
    """可编程的 TMDB 解析替身。"""

    def __init__(self, candidates=None, converted=None, raise_on_search=False):
        self.candidates = list(candidates or [])
        self.converted = dict(converted or {})
        self.raise_on_search = raise_on_search
        self.search_calls = 0

    async def search(self, title, year, media_type, *, limit=5):
        """返回预设候选。"""
        self.search_calls += 1
        if self.raise_on_search:
            raise RuntimeError("TMDB 不可用")
        return self.candidates

    async def convert_to_tmdb(self, media_source, media_id, media_type):
        """按 ``f"{source}:{id}"`` 查预设换算表。"""
        return self.converted.get(f"{media_source}:{media_id}")


class MemoryStore:
    """内存缓存存储替身。"""

    def __init__(self):
        self.payload = None

    def load(self):
        """读取载荷。"""
        return self.payload

    def save(self, payload):
        """写入载荷。"""
        self.payload = payload


def make_item(**overrides):
    """构造一条默认 TMDB 条目，便于按需覆盖字段。"""
    data = {
        "source": C.SOURCE_TMDB,
        "source_id": "1",
        "title": "沙丘",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": "2026",
        "release_date": "2026-11-01",
        "native_ids": {},
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# --------------------------------------------------------------------- 标题归一

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("沙丘", "沙丘"),
        ("  沙丘  ", "沙丘"),
        ("ＤＵＮＥ", "dune"),          # 全角 → 半角 + 小写
        ("Dune：Part Two", "dune part two"),
        ("沙丘（2026）", "沙丘"),
        ("某剧 第二季", "某剧"),
        ("Show S02", "show"),
        ("Show Season 3", "show"),
    ],
)
def test_normalize_title(raw, expected):
    """标题标准化：全角折叠、去装饰、压空白、统一小写。"""
    assert normalize_title(raw) == expected


def test_title_similarity_boundaries():
    """相似度边界：完全相同为 1，完全不同为低分。"""
    assert title_similarity("沙丘", "沙丘") == 1.0
    assert title_similarity("", "沙丘") == 0.0
    assert title_similarity("沙丘", "完全不相干的名字") < 0.5


# --------------------------------------------------------------------- L1

def test_l1_from_tmdb_native_id():
    """L1：源自带 tmdb ID → 直接确认，无需搜索。"""
    item = make_item(native_ids={"tmdb": "693134"})
    identity = resolve_from_native_ids(item)
    assert identity is not None
    assert identity.media_source == "themoviedb"
    assert identity.media_id == "693134"
    assert identity.confidence == C.CONFIDENCE_L1
    assert identity.writable


def test_l1_rejects_zero_and_blank_native_id():
    """``"0"`` 与空白不是有效身份（与宿主 resolve_media_identity 同口径）。"""
    assert resolve_from_native_ids(make_item(native_ids={"tmdb": "0"})) is None
    assert resolve_from_native_ids(make_item(native_ids={"tmdb": "  "})) is None
    assert resolve_from_native_ids(make_item()) is None


def test_identity_rejects_empty_pair():
    """身份成对约束：任一为空即非法。"""
    with pytest.raises(ValueError):
        ResolvedIdentity(media_source="themoviedb", media_id="")
    with pytest.raises(ValueError):
        ResolvedIdentity(media_source="", media_id="123")
    with pytest.raises(ValueError):
        ResolvedIdentity(media_source="themoviedb", media_id="0")


# --------------------------------------------------------------------- L3

def test_l3_exact_title_and_year_match():
    """L3：标题精确 + 年份一致 → 唯一确认。"""
    candidates = [
        {"tmdb_id": 111, "title": "沙丘", "year": "2026", "media_type": "movie"},
        {"tmdb_id": 222, "title": "沙丘", "year": "1984", "media_type": "movie"},
    ]
    hit = match_candidate_year(candidates, make_item(title="沙丘", year="2026"))
    assert hit is not None
    candidate, reason = hit
    assert candidate["tmdb_id"] == 111
    assert "year_match" in reason


def test_l3_rejects_wrong_year_even_if_title_identical():
    """年份不符必须拒绝 —— 同名不同年是典型的误写来源。"""
    candidates = [{"tmdb_id": 222, "title": "沙丘", "year": "1984", "media_type": "movie"}]
    assert match_candidate_year(candidates, make_item(title="沙丘", year="2026")) is None


def test_l3_rejects_candidate_without_year():
    """候选缺年份 → 无法校验 → 不确认（宁缺毋滥）。"""
    candidates = [{"tmdb_id": 222, "title": "沙丘", "year": None, "media_type": "movie"}]
    assert match_candidate_year(candidates, make_item(title="沙丘", year="2026")) is None


def test_l3_rejects_ambiguous_multiple_matches():
    """多条候选同时满足 → 歧义不猜。"""
    candidates = [
        {"tmdb_id": 111, "title": "沙丘", "year": "2026", "media_type": "movie"},
        {"tmdb_id": 333, "title": "沙丘", "year": "2026", "media_type": "movie"},
    ]
    assert match_candidate_year(candidates, make_item(title="沙丘", year="2026")) is None


def test_l3_rejects_media_type_mismatch():
    """媒体类型不一致的候选不参与匹配。"""
    candidates = [{"tmdb_id": 111, "title": "沙丘", "year": "2026", "media_type": "tv"}]
    assert match_candidate_year(candidates, make_item(title="沙丘", year="2026")) is None


def test_l3_accepts_season_normalized_title():
    """季号/副标题装饰被归一剥离后按精确匹配命中。

    ``沙丘 第二部`` 归一为 ``沙丘``，因此命中原因仍是 ``title_exact``；
    这比「包含匹配」更严格，是期望行为。
    """
    candidates = [
        {"tmdb_id": 111, "title": "沙丘 第二部", "year": "2026", "media_type": "movie"}
    ]
    hit = match_candidate_year(candidates, make_item(title="沙丘", year="2026"))
    assert hit is not None
    assert "year_match" in hit[1]


def test_l3_accepts_contained_title():
    """真正的包含关系（副标题是片名的超集）按 contained 命中。"""
    candidates = [
        {"tmdb_id": 111, "title": "沙丘外传前传", "year": "2026", "media_type": "movie"}
    ]
    hit = match_candidate_year(candidates, make_item(title="沙丘外传", year="2026"))
    assert hit is not None
    assert "contained" in hit[1]


# --------------------------------------------------------------------- L4

def test_l4_never_writable():
    """L4 级别身份不可写入 —— 这是防误写的核心闸门。"""
    identity = ResolvedIdentity(
        media_source="themoviedb", media_id="999", confidence=C.CONFIDENCE_L4
    )
    assert not identity.writable
    assert C.CONFIDENCE_L4 not in C.WRITABLE_CONFIDENCE


def test_writable_levels_are_l1_l2_l3_only():
    """允许写入的级别只有 L1/L2/L3。"""
    assert C.WRITABLE_CONFIDENCE == {
        C.CONFIDENCE_L1,
        C.CONFIDENCE_L2,
        C.CONFIDENCE_L3,
    }


def test_review_candidates_returns_best_score_over_threshold():
    """L4 只会产生相似度分数，供待确认列表排序。"""
    candidates = [{"tmdb_id": 111, "title": "沙丘 2026", "media_type": "movie"}]
    score = review_candidates(candidates, make_item(title="沙丘2026"), threshold=0.5)
    assert score is not None and score >= 0.9
    assert review_candidates(candidates, make_item(title="毫不相干的剧"), threshold=0.9) is None


# --------------------------------------------------------------------- 编排

@pytest.mark.asyncio
async def test_resolver_prefers_l1_over_search():
    """有原生 tmdb ID 时不得触发搜索（省调用、避免误匹配）。"""
    tmdb = FakeTmdb(candidates=[{"tmdb_id": 999, "title": "沙丘", "year": "2026"}])
    resolver = IdentityResolver(tmdb)
    item = await resolver.resolve(make_item(native_ids={"tmdb": "693134"}))
    assert item.resolved is not None
    assert item.resolved.media_id == "693134"
    assert item.resolved.confidence == C.CONFIDENCE_L1
    assert tmdb.search_calls == 0


@pytest.mark.asyncio
async def test_resolver_converts_bangumi_to_tmdb():
    """Bangumi 原生 ID 经宿主换算 → L1 确定性身份。"""
    tmdb = FakeTmdb(converted={"bangumi:4567": {"tmdb_id": "693134", "year": "2013"}})
    resolver = IdentityResolver(tmdb)
    item = await resolver.resolve(
        make_item(source=C.SOURCE_BANGUMI, source_id="4567", title="进击的巨人",
                  year="2013", native_ids={"bangumi": "4567"})
    )
    assert item.resolved is not None
    assert item.resolved.media_id == "693134"
    assert item.resolved.confidence == C.CONFIDENCE_L2
    assert item.resolved.reason.startswith("convert:bangumi")


@pytest.mark.asyncio
async def test_conversion_carries_season_for_sequels():
    """续作必须带上季号，否则宿主会按第 1 季订阅（订错季）。"""

    class _SeasonTmdb(FakeTmdb):
        async def convert_to_tmdb(self, media_source, media_id, media_type):
            return {"tmdb_id": "999", "year": "2026", "season": 2}

    resolver = IdentityResolver(_SeasonTmdb())
    item = await resolver.resolve(
        make_item(source=C.SOURCE_BANGUMI, source_id="513878", title="边缘行者 2",
                  year="2026", native_ids={"bangumi": "513878"})
    )
    assert item.resolved is not None
    assert item.resolved.media_id == "999"
    assert item.season == 2, "季号没有从换算结果带回条目"


@pytest.mark.asyncio
async def test_conversion_rejected_on_year_mismatch():
    """换算返回的年份与条目不符时**不确认** —— 宿主的换算是标题匹配，
    必须二次校验，否则会把 A 番写成 B 番。"""

    class _WrongYearTmdb(FakeTmdb):
        async def convert_to_tmdb(self, media_source, media_id, media_type):
            return {"tmdb_id": "888", "year": "1999"}

    resolver = IdentityResolver(_WrongYearTmdb())
    item = await resolver.resolve(
        make_item(source=C.SOURCE_BANGUMI, source_id="777", title="某番",
                  year="2026", native_ids={"bangumi": "777"})
    )
    assert item.resolved is None
    assert not item.writable


@pytest.mark.asyncio
async def test_resolver_falls_back_to_l4_when_year_mismatch():
    """L3 校验不过 → 落到 L4 待确认，**不确认身份**。"""
    tmdb = FakeTmdb(candidates=[{"tmdb_id": 222, "title": "沙丘", "year": "1984", "media_type": "movie"}])
    resolver = IdentityResolver(tmdb)
    item = await resolver.resolve(make_item(title="沙丘", year="2026", native_ids={}))
    assert item.resolved is None
    assert item.review_score is not None
    assert not item.writable


@pytest.mark.asyncio
async def test_resolver_search_failure_is_swallowed():
    """搜索抛异常等同「无候选」，不得向上冒泡打断整条流水线。"""
    tmdb = FakeTmdb(raise_on_search=True)
    resolver = IdentityResolver(tmdb)
    item = await resolver.resolve(make_item(native_ids={}))
    assert item.resolved is None
    assert not item.writable


@pytest.mark.asyncio
async def test_resolver_uses_cache_on_second_run():
    """L2：已确认映射在第二次运行直接复用，不再搜索。"""
    store = MemoryStore()
    cache = MappingCacheStore(store)
    tmdb = FakeTmdb(candidates=[{"tmdb_id": 111, "title": "沙丘", "year": "2026", "media_type": "movie"}])

    resolver = IdentityResolver(tmdb, cache)
    first = await resolver.resolve(make_item(source_id="77", title="沙丘", year="2026", native_ids={}))
    assert first.resolved is not None and first.resolved.confidence == C.CONFIDENCE_L3

    # 新建解析器（模拟下次运行）+ 同一个持久化缓存
    resolver2 = IdentityResolver(tmdb, MappingCacheStore(store))
    second = await resolver2.resolve(make_item(source_id="77", title="沙丘", year="2026", native_ids={}))
    assert second.resolved is not None
    assert second.resolved.confidence == C.CONFIDENCE_L2
    assert tmdb.search_calls == 1


@pytest.mark.asyncio
async def test_l4_result_is_not_cached():
    """L4 结果绝不能进缓存，否则会污染后续运行。"""
    store = MemoryStore()
    cache = MappingCacheStore(store)
    tmdb = FakeTmdb(candidates=[{"tmdb_id": 222, "title": "沙丘", "year": "1984", "media_type": "movie"}])
    resolver = IdentityResolver(tmdb, cache)
    await resolver.resolve(make_item(source_id="88", title="沙丘", year="2026", native_ids={}))
    assert cache.size == 0
