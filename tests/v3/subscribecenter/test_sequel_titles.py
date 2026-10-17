"""续作标题归一与「剧集不校验年份」的回归测试（0.6.3）。

真机暴露的问题：Bangumi 的续作条目永远匹配不上 TMDB。

    Bangumi 条目            年份      TMDB 剧集              首播年
    牧神记5                 2026      《牧神记》              2024-10-27
    赛博朋克：边缘行者 2      2026      Cyberpunk: Edgerunners  2022-09-13

宿主的 Bangumi→TMDB 换算按「标题 + 年份」匹配，而续作年份与剧集首播年
**必然不同**，所以必然失败；我原来的兜底搜索也带年份，同样失败。

修法两条：基础剧名（去尾部季号）搜索 + 剧集不校验年份（但要求标题精确）。
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.core.identity import (  # noqa: E402
    match_candidate_year,
    strip_season_suffix,
)
from subscribecenter.core.model import DiscoveredItem  # noqa: E402


def tv(title, year="2026"):
    """构造一条剧集条目。"""
    return DiscoveredItem(
        source=C.SOURCE_BANGUMI,
        source_id="1",
        title=title,
        media_type=C.MEDIA_TYPE_TV,
        year=year,
        release_date=f"{year}-10-20",
        native_ids={"bangumi": "1"},
    )


def movie(title, year="2026"):
    """构造一条电影条目。"""
    return DiscoveredItem(
        source=C.SOURCE_DOUBAN_RSS,
        source_id="1",
        title=title,
        media_type=C.MEDIA_TYPE_MOVIE,
        year=year,
        release_date=f"{year}-10-20",
        native_ids={"douban": "1"},
    )


# --------------------------------------------------------------------- 基础剧名

@pytest.mark.parametrize(
    "raw,expected",
    [
        # 中文尾部数字（Bangumi 常见）
        ("牧神记5", "牧神记"),
        # 有分隔符 + 数字
        ("赛博朋克：边缘行者 2", "赛博朋克：边缘行者"),
        # 「第N期」形式
        ("ゲルぴよ 第2期", "ゲルぴよ"),
        # 本来就没有季号
        ("牧神记", "牧神记"),
        ("Dreamland", "Dreamland"),
        # 纯数字片名：绝不能削（1917 不是「第 17 季」）
        ("1917", "1917"),
        ("12 12 12", "12 12 12"),
        # 只有季号没有片名：不削
        ("第5季", "第5季"),
        # 数字前一个字符是字母且无分隔符：保守不动
        ("ShowS02", "ShowS02"),
    ],
)
def test_strip_season_suffix(raw, expected):
    """尾部季号剥离必须保守：只削明显是季号的情况。"""
    assert strip_season_suffix(raw) == expected


def test_strip_season_suffix_handles_chinese_numerals():
    """中文数字季号必须能剥（真机：豆瓣「信号 第二季」「镀金时代 第四季」）。

    原实现只做 `int()`，遇到「二」抛 ValueError 后放弃剥离，
    导致基础名没取到、TMDB 搜不到 -> 误判成待确认。
    """
    from subscribecenter.core.identity import extract_season_hint

    assert strip_season_suffix("信号 第二季") == "信号"
    assert strip_season_suffix("镀金时代 第四季") == "镀金时代"
    assert strip_season_suffix("某番 第十二季") == "某番"
    assert extract_season_hint("信号 第二季") == 2
    assert extract_season_hint("镀金时代 第四季") == 4
    assert extract_season_hint("某番 第十二季") == 12


# --------------------------------------------------------------------- 剧集放宽

def test_tv_accepts_year_mismatch_when_title_exact():
    """剧集：标题精确相等即可，**不要求年份相同**。

    牧神记5（2026）→ TMDB《牧神记》(2024) 是正确映射。
    """
    candidates = [
        {"tmdb_id": 236534, "title": "牧神记", "year": "2024", "media_type": "tv"},
    ]
    hit = match_candidate_year(candidates, tv("牧神记"), strict_year=False)
    assert hit is not None
    assert hit[0]["tmdb_id"] == 236534


def test_tv_rejects_contained_title_without_year():
    """剧集放宽年份，但**不接受「包含」匹配** —— 否则同名前传会被错配。"""
    candidates = [
        {"tmdb_id": 1, "title": "牧神记外传", "year": "2024", "media_type": "tv"},
    ]
    assert match_candidate_year(candidates, tv("牧神记"), strict_year=False) is None


def test_tv_still_rejects_ambiguity():
    """多条同名候选、且没有一条年份接近 -> 仍然拒绝（歧义不猜）。"""
    candidates = [
        {"tmdb_id": 1, "title": "牧神记", "year": "2015", "media_type": "tv"},
        {"tmdb_id": 2, "title": "牧神记", "year": "2010", "media_type": "tv"},
    ]
    assert match_candidate_year(candidates, tv("牧神记"), strict_year=False) is None


def test_tv_ambiguity_resolved_by_year_proximity():
    """多条同名但有**恰好一条**年份在 ±2 内 -> 用它消歧。

    真机：搜「半熟恋人」返回两条同名（2021 / 2012）。
    """
    candidates = [
        {"tmdb_id": 1, "title": "半熟恋人", "year": "2012", "media_type": "tv"},
        {"tmdb_id": 2, "title": "半熟恋人", "year": "2026", "media_type": "tv"},
    ]
    hit = match_candidate_year(candidates, tv("半熟恋人", "2026"), strict_year=False)
    assert hit is not None
    assert hit[0]["tmdb_id"] == 2


def test_movie_keeps_strict_year():
    """电影仍然严格要求年份相等 —— 同名片不同年是最常见的误写来源。"""
    candidates = [
        {"tmdb_id": 999, "title": "沙丘", "year": "1984", "media_type": "movie"},
    ]
    assert match_candidate_year(candidates, movie("沙丘", "2026"), strict_year=True) is None
    # 年份一致则通过
    candidates_ok = [
        {"tmdb_id": 111, "title": "沙丘", "year": "2026", "media_type": "movie"},
    ]
    assert match_candidate_year(candidates_ok, movie("沙丘", "2026"), strict_year=True) is not None


def test_tv_accepts_host_base_title():
    """**宿主识别返回基础名时必须接受**。

    真机日志：
      themoviedb - 赛博朋克：边缘行者 TMDB识别结果：电视剧 赛博朋克：边缘行者 (2022) 105248
      recognition.py - 赛博朋克：边缘行者 2 识别到媒体信息：电视剧 赛博朋克：边缘行者 (2022)

    宿主把条目名「赛博朋克：边缘行者 2」识别成了基础名《赛博朋克：边缘行者》，
    两者相差「 2」。若只认「精确相等」就会把宿主已经成功识别的结果拒掉
    （0.6.3 正是这样踩的）。
    """
    candidates = [
        {"tmdb_id": 105248, "title": "赛博朋克：边缘行者", "year": "2022",
         "media_type": "tv"},
    ]
    hit = match_candidate_year(
        candidates, tv("赛博朋克：边缘行者 2"), strict_year=False
    )
    assert hit is not None
    assert hit[0]["tmdb_id"] == 105248


def test_tv_accepts_base_title_for_mu_shen_ji():
    """牧神记5（2026）→ TMDB《牧神记》(2024) 同样是基础名相等。"""
    candidates = [
        {"tmdb_id": 236534, "title": "牧神记", "year": "2024", "media_type": "tv"},
    ]
    hit = match_candidate_year(candidates, tv("牧神记5"), strict_year=False)
    assert hit is not None
    assert hit[0]["tmdb_id"] == 236534


def test_tv_rejects_contained_but_not_base_equal():
    """「包含」但「基础名不相等」仍然拒绝（防同名前传错配）。"""
    candidates = [
        {"tmdb_id": 1, "title": "牧神记外传", "year": "2024", "media_type": "tv"},
    ]
    assert match_candidate_year(candidates, tv("牧神记"), strict_year=False) is None


def test_strict_year_defaults_to_true():
    """默认必须是严格模式（调用方忘记传参时不能放松）。"""
    candidates = [
        {"tmdb_id": 1, "title": "牧神记", "year": "2024", "media_type": "tv"},
    ]
    assert match_candidate_year(candidates, tv("牧神记")) is None


# ------------------------------------------------------- 续作识别（1.0.4 真机事故）

def test_english_season_suffix_is_parsed():
    """英文/日式季号必须能解析：AniList 的日番标题大量使用这些写法。

    真机：``Black Clover 2nd Season`` 原来 hint=None，季号提示缺失后
    宿主的季号裁决只能取「该条目最大的在播季」，一旦条目认错就稳定订 S01。
    """
    from subscribecenter.core.identity import extract_season_hint, strip_season_suffix

    assert extract_season_hint("Black Clover 2nd Season") == 2
    assert extract_season_hint("Jobless Reincarnation Season 3") == 3
    assert extract_season_hint("Overlord Part 2") == 2
    assert extract_season_hint("呪術廻戦 第2クール") == 2
    assert extract_season_hint("某番 第3部") == 3
    assert strip_season_suffix("Black Clover 2nd Season") == "Black Clover"
    assert strip_season_suffix("呪術廻戦 第2クール") == "呪術廻戦"


def test_non_sequel_titles_are_not_flagged():
    """普通片名不能被误判成续作（否则会被年份闸门误杀）。"""
    from subscribecenter.core.identity import is_continuation_title

    for title in ("沙丘", "1917", "斗罗大陆2绝世唐门", "BLEACH 千年血戦篇-禍進譚-", "Dune"):
        assert is_continuation_title(title) is False, title


def test_sequel_titles_are_flagged():
    """带季号（>=2）的标题要识别为续作。"""
    from subscribecenter.core.identity import is_continuation_title

    for title in ("野生のラスボスが現れた！ 第2期", "Black Clover 2nd Season", "凡人修仙传 第四季"):
        assert is_continuation_title(title) is True, title


def test_season_one_suffix_is_not_continuation():
    """「第1季」不算续作 —— 下限只对 >=2 生效，避免误杀翻拍/同名新作。"""
    from subscribecenter.core.identity import is_continuation_title

    assert is_continuation_title("某某 第1季") is False


def test_continuation_rejects_older_candidate():
    """续作条目必须拒绝「更旧年份」的候选。

    真机事故：AniList「野生のラスボスが現れた！ 第2期」(2026) 搜日文命中 0，
    退化成中文基础名后 TMDB 只返回 2025 那部（上一季）。TV 不做年份硬校验，
    于是认成 2025 条目 —— 订阅结果是 S01，而不是最新季。
    """
    from subscribecenter.core.identity import match_candidate_year
    from subscribecenter.core.model import DiscoveredItem

    entity = DiscoveredItem(
        source="anilist", source_id="1",
        title="某番 第2期", media_type="tv", year="2026",
        release_date="2026-10-20",
    )
    older = [{"tmdb_id": "111", "title": "某番", "year": "2025", "media_type": "tv"}]
    assert match_candidate_year(older, entity, strict_year=False, min_year=2026) is None

    same_year = [{"tmdb_id": "222", "title": "某番", "year": "2026", "media_type": "tv"}]
    hit = match_candidate_year(same_year, entity, strict_year=False, min_year=2026)
    assert hit is not None and hit[0]["tmdb_id"] == "222"


def test_continuation_floor_only_applies_to_sequels():
    """下限只对续作生效；普通作品返回 None（不限制）。"""
    from subscribecenter.core.identity import _continuation_floor
    from subscribecenter.core.model import DiscoveredItem

    sequel = DiscoveredItem(
        source="anilist", source_id="1", title="某番 第2期",
        media_type="tv", year="2026", release_date="2026-10-20",
    )
    plain = DiscoveredItem(
        source="tmdb", source_id="2", title="沙丘",
        media_type="movie", year="2026", release_date="2026-11-01",
    )
    assert _continuation_floor(sequel) == 2026
    assert _continuation_floor(plain) is None


# ------------------------------------------------ 分季版降权（1.2.4 真机）

def test_split_entry_is_deprioritized():
    """同名多候选时，优先选不带「分季版」的重复条目。

    真机（一念永恒）：TMDB 同时有主条目 107371（1 季 200 集 + Seasons 分组）
    与「分季版」331477（S1~S4）。两者标题都能匹配、年份都是 2020，
    季号裁决挑了「真有第 4 季」的分季版 → 订到 S04/30 集。
    """
    from subscribecenter.core.identity import match_candidate_year
    from subscribecenter.core.model import DiscoveredItem

    entity = DiscoveredItem(
        source="anilist", source_id="1", title="一念永恒 第四季",
        media_type="tv", year="2020", release_date="2020-08-12",
    )
    candidates = [
        {"tmdb_id": "331477", "title": "一念永恒 (分季版)", "year": "2020", "media_type": "tv"},
        {"tmdb_id": "107371", "title": "一念永恒", "year": "2020", "media_type": "tv"},
    ]
    hit = match_candidate_year(candidates, entity, strict_year=False)
    assert hit is not None
    assert hit[0]["tmdb_id"] == "107371", "应优先主条目而不是分季版"


def test_split_marker_only_inside_brackets():
    """只认括号里的限定词，别误伤「剧场版」这类正常标题。"""
    from subscribecenter.core.identity import _is_split_entry

    assert _is_split_entry("一念永恒 (分季版)") is True
    assert _is_split_entry("某番（合集）") is True
    assert _is_split_entry("某番", "Split") is False
    assert _is_split_entry("剧场版 某番") is False


# ------------------------------------- 国漫同名多条目（1.2.5 真机）

def _donghua(title, year):
    from subscribecenter.core.model import DiscoveredItem

    return DiscoveredItem(
        source="anilist", source_id="1", title=title, media_type="tv",
        year=year, release_date=f"{year}-10-01", raw={"country": "CN"},
    )


def test_donghua_prefers_latest_year_on_same_title():
    """同名多条目时国漫取年份最大的那个。

    真机：完美世界 第七季 -> TMDB 有「完美世界 2021」与「完美世界 2000」；
    旧逻辑判歧义（年份都不在 ±1）且续作跳过兜底 -> 直接待确认。
    """
    from subscribecenter.core.identity import match_candidate_year

    entity = _donghua("完美世界 第七季", "2026")
    candidates = [
        {"tmdb_id": "7120", "title": "完美世界", "year": "2000", "media_type": "tv"},
        {"tmdb_id": "124003", "title": "完美世界", "year": "2021", "media_type": "tv"},
    ]
    hit = match_candidate_year(candidates, entity, strict_year=False, prefer_latest_year=True)
    assert hit is not None
    assert hit[0]["tmdb_id"] == "124003", "应取年份更大的主条目"


def test_donghua_same_year_prefers_smaller_tmdb_id():
    """同年同名时取 tmdb_id 最小的（主条目最早创建，分季版/合集是后补的）。

    真机：一念永恒 107371（主条目 1 季 200 集）vs 331477（分季版 S1~S4），
    标题与年份都一样，只能靠 id 顺序判断。
    """
    from subscribecenter.core.identity import match_candidate_year

    entity = _donghua("一念永恒 第四季", "2020")
    candidates = [
        {"tmdb_id": "331477", "title": "一念永恒", "year": "2020", "media_type": "tv"},
        {"tmdb_id": "107371", "title": "一念永恒", "year": "2020", "media_type": "tv"},
    ]
    hit = match_candidate_year(candidates, entity, strict_year=False, prefer_latest_year=True)
    assert hit is not None
    assert hit[0]["tmdb_id"] == "107371", "应取主条目而不是分季版"


def test_japanese_sequel_does_not_prefer_latest():
    """日番续作不启用「年份最大」——它们在 TMDB 是独立条目，取最大会选错。"""
    from subscribecenter.core.identity import _prefers_latest_year
    from subscribecenter.core.model import DiscoveredItem

    jp = DiscoveredItem(
        source="anilist", source_id="2", title="某番 第2期", media_type="tv",
        year="2026", release_date="2026-10-01", raw={"country": "JP"},
    )
    assert _prefers_latest_year(jp) is False
