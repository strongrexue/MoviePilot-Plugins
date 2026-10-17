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
    """多条同名候选仍然拒绝（歧义不猜）。"""
    candidates = [
        {"tmdb_id": 1, "title": "牧神记", "year": "2024", "media_type": "tv"},
        {"tmdb_id": 2, "title": "牧神记", "year": "2019", "media_type": "tv"},
    ]
    assert match_candidate_year(candidates, tv("牧神记"), strict_year=False) is None


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
