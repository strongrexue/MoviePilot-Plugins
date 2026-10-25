"""排除规则（黑名单）的回归测试。

盯住四件容易写错、写错了会静默伤到用户的事：

1. **内置预设绝不能默认生效** —— 装这个插件的人不该被别人的口味静默筛掉节目
   （用户 m03322 的原话：「那是不是其他人使用也会自动排除这些题材？」）；
2. **中文按包含、英文按整词** —— ``BL`` 不能拦掉 ``BLADE``，但 ``同性`` 必须
   拦住 ``同性恋``；
3. **第一层必须排在身份解析之前** —— 被拦的条目不该再花一次 TMDB 请求；
4. **被拦的条目不能被记成「订过」** —— 否则清空流水也救不回来（这条由插件的
   ``_recorded_keys`` 保证，这里锁住决策名不被误用）。
"""
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3" / PLUGIN_ID))

from core import constants as C  # noqa: E402
from core.blacklist import (  # noqa: E402
    BlacklistRules,
    check_item,
    check_keywords,
    check_parts,
    compile_line,
    item_genre_ids,
    match_words,
    rules_from_config,
)
from core.model import DiscoveredItem, ResolvedIdentity  # noqa: E402
from core.pipeline import filter_blacklist, filter_blacklist_keywords  # noqa: E402

TODAY = date.today()


def rules(**overrides) -> BlacklistRules:
    """按配置造一份规则（默认总开关打开、其余全空 —— 即「一条都不拦」）。"""
    config = {
        "blacklist_enabled": True,
        "blacklist_genre_movie": [],
        "blacklist_genre_tv": [],
        "blacklist_presets": [],
        "blacklist_words": "",
        "blacklist_match_title": True,
        "blacklist_match_tags": True,
        "blacklist_tmdb_keywords": False,
    }
    config.update(overrides)
    return rules_from_config(config)


def item(**overrides) -> DiscoveredItem:
    """构造一条待判定的条目。"""
    data = {
        "source": C.SOURCE_TMDB,
        "source_id": "1",
        "title": "某某片",
        "media_type": C.MEDIA_TYPE_MOVIE,
        "year": "2026",
        "release_date": (TODAY + timedelta(days=5)).isoformat(),
        "rating": 8.0,
    }
    data.update(overrides)
    return DiscoveredItem(**data)


# ----------------------------------------------------------------- 预设不默认生效

def test_disabled_switch_compiles_no_rules():
    """总开关关掉时，就算配置里写了词也一条都不生效。"""
    compiled = rules_from_config(
        {
            "blacklist_enabled": False,
            "blacklist_presets": ["lgbt"],
            "blacklist_words": "同性",
            "blacklist_genre_movie": [27],
        }
    )
    assert compiled.active is False
    assert check_item(compiled, item(title="同性恋日记")) == ""


def test_builtin_presets_are_opt_in():
    """内置预设只有勾选才生效 —— 这是「别人的口味不能默认套在你身上」的锁。"""
    without_presets = rules()
    assert without_presets.active is False
    assert check_item(without_presets, item(title="同性恋日记")) == ""

    with_presets = rules(blacklist_presets=["lgbt"])
    assert with_presets.active is True
    assert "同性" in check_item(with_presets, item(title="同性恋日记"))


def test_unknown_preset_key_is_ignored():
    """写错的预设 key 不能让插件整体报错（只当没勾）。"""
    compiled = rules(blacklist_presets=["no-such-preset"])
    assert compiled.active is False


def test_presets_and_custom_words_merge():
    """勾选预设 + 自定义词 = 取并集。"""
    compiled = rules(blacklist_presets=["lgbt"], blacklist_words="短剧")
    assert check_item(compiled, item(title="某某同性恋")) != ""
    assert check_item(compiled, item(title="某某短剧")) != ""


def test_empty_config_matches_nothing():
    """全空规则 = 零成本跳过（``active`` 为假，连循环都不进）。"""
    compiled = rules()
    assert compiled.active is False
    kept, blocked = filter_blacklist([item()], compiled)
    assert len(kept) == 1
    assert blocked == []


# ------------------------------------------------------------------- 题材词匹配

def test_chinese_word_matches_as_substring():
    """中文按包含：``同性`` 必须能拦住 ``同性恋``。"""
    compiled = rules(blacklist_words="同性")
    assert check_item(compiled, item(title="同性恋日记")) == "命中排除题材（标题）：同性"


def test_english_word_needs_word_boundary():
    """英文按整词：``BL`` 不能误伤 ``BLADE``。"""
    compiled = rules(blacklist_words="BL")
    assert check_item(compiled, item(title="BLADE RUNNER")) == ""
    assert "BL" in check_item(compiled, item(title="BL 漫画"))


def test_space_separated_words_are_and():
    """一行里空格分隔 = 全部命中才算（``韩国 同性`` 只拦韩国同性题材）。"""
    compiled = rules(blacklist_words="韩国 同性")
    hit = item(title="某片", raw={"genre": "2026 / 韩国 / 剧情 同性"})
    miss = item(title="某片", raw={"genre": "2026 / 日本 / 剧情 同性"})
    assert "韩国 同性" in check_item(compiled, hit)
    assert check_item(compiled, miss) == ""


def test_regex_prefix():
    """``regex:`` 行走正则。"""
    compiled = rules(blacklist_words=r"regex:^\[.+?\]")
    assert "regex:" in check_item(compiled, item(title="[搬运] 某某片"))


def test_case_prefix_is_case_sensitive():
    """``case:`` 行区分大小写。"""
    compiled = rules(blacklist_words="case:BL")
    assert check_item(compiled, item(title="bl 漫画")) == ""
    assert check_item(compiled, item(title="BL 漫画")) != ""


def test_comment_and_blank_lines_are_ignored():
    """空行与 ``#`` 注释不产生规则。"""
    compiled = rules(blacklist_words="# 这是注释\n\n同性")
    assert len(compiled.words) == 1


def test_broken_regex_falls_back_to_literal():
    """正则写错退化成字面量，不能让整轮发现抛异常。"""
    compiled = rules(blacklist_words="regex:[未闭合")
    assert compiled.active is True
    assert check_item(compiled, item(title="某片 [未闭合")) != ""


def test_compile_line_returns_none_for_blank():
    assert compile_line("   ") is None
    assert compile_line("#注释") is None


# --------------------------------------------------------------------- 排除类型

def test_genre_excludes_by_tmdb_id():
    """电影按 TMDB genre id 精确排除。"""
    compiled = rules(blacklist_genre_movie=[27])
    assert check_item(compiled, item(raw={"genre_ids": [27, 53]})) == "命中排除类型：恐怖(27)"


def test_genre_exclusion_is_per_media_type():
    """电影类型与剧集类型分开配置，互不影响。"""
    compiled = rules(blacklist_genre_movie=[27])
    tv = item(media_type=C.MEDIA_TYPE_TV, raw={"genre_ids": [27]})
    assert check_item(compiled, tv) == ""


def test_genre_reads_douban_category_text():
    """豆瓣源没有 genre id，只有 ``2026 / 韩国 / 恐怖 剧情`` 这种中文串。"""
    compiled = rules(blacklist_genre_movie=[27])
    assert "恐怖" in check_item(compiled, item(raw={"genre": "2026 / 韩国 / 恐怖 剧情"}))


def test_genre_reads_anilist_english_names():
    """AniList 给的是英文类型名，要能反查成 id。"""
    compiled = rules(blacklist_genre_tv=[35])
    anilist = item(media_type=C.MEDIA_TYPE_TV, raw={"genres": ["Comedy"]})
    assert check_item(compiled, anilist) != ""


def test_item_genre_ids_tolerates_junk():
    """脏数据（字符串 id、None、空串）不能让收集函数抛异常。"""
    ids = item_genre_ids(item(raw={"genre_ids": ["27", None, "", "abc", 35]}))
    assert ids == {27, 35}


def test_match_switches_can_be_turned_off():
    """关掉标题匹配后，片名里的题材词不再生效（题材串仍可命中）。"""
    compiled = rules(blacklist_words="同性", blacklist_match_title=False)
    assert check_item(compiled, item(title="同性恋日记")) == ""
    assert check_item(compiled, item(title="某片", raw={"genre": "剧情 同性"})) != ""


def test_match_tags_can_be_turned_off():
    compiled = rules(blacklist_words="同性", blacklist_match_tags=False)
    assert check_item(compiled, item(raw={"genre": "剧情 同性"})) == ""


def test_match_words_ignores_empty_texts():
    """没有可查文本时直接返回空串，不抛异常。"""
    assert match_words(rules(blacklist_words="同性"), [""]) == ""


# ----------------------------------------------------------------- 流水线接线

def test_filter_blacklist_splits_and_labels_decision():
    """被拦的条目产 ``skipped_blacklist`` 决策（进流水、不进「订过」）。"""
    compiled = rules(blacklist_words="同性")
    passed, blocked = filter_blacklist(
        [item(title="某片"), item(title="同性恋日记", source_id="2")], compiled
    )
    assert [entry.title for entry in passed] == ["某片"]
    assert len(blocked) == 1
    assert blocked[0].decision == C.DECISION_SKIPPED_BLACKLIST
    assert blocked[0].reason.startswith("命中排除题材")


def test_blacklist_decision_is_not_a_subscribe_record():
    """决策名必须与「已订阅 / 新增」区分开 —— 否则清空流水也解不了封。"""
    assert C.DECISION_SKIPPED_BLACKLIST not in {
        C.DECISION_ADDED,
        C.DECISION_SKIPPED_ALREADY_SUBSCRIBED,
        C.DECISION_SKIPPED_ALREADY_COMPLETED,
    }


def _lookup(words):
    """造一个假的 TMDB 关键词查询（``words`` 可以是异常对象）。"""

    async def call(media_type, media_id):
        if isinstance(words, Exception):
            raise words
        return words

    return call


def test_keyword_layer_blocks_matching_item():
    """第二层：TMDB 关键词命中即拦。"""
    compiled = rules(blacklist_tmdb_keywords=True, blacklist_words="gay")
    resolved = ResolvedIdentity(media_source="themoviedb", media_id="1")
    passed, blocked = asyncio.run(
        filter_blacklist_keywords(
            [item(title="无关片名", resolved=resolved)],
            compiled,
            _lookup(["gay", "romance"]),
        )
    )
    assert passed == []
    assert blocked[0].decision == C.DECISION_SKIPPED_BLACKLIST
    assert "gay" in blocked[0].reason


def test_keyword_layer_fails_open_on_network_error():
    """查不到关键词时放行：宁可漏拦一条，也不能错杀一批。"""
    compiled = rules(blacklist_tmdb_keywords=True, blacklist_words="gay")
    resolved = ResolvedIdentity(media_source="themoviedb", media_id="1")
    entries = [item(title="无关片名", resolved=resolved)]
    passed, blocked = asyncio.run(
        filter_blacklist_keywords(entries, compiled, _lookup(RuntimeError("超时")))
    )
    assert passed == entries
    assert blocked == []


def test_keyword_layer_skipped_when_disabled():
    """``blacklist_tmdb_keywords`` 默认关：连查询函数都不会被调用。"""
    compiled = rules(blacklist_words="gay")
    calls = []

    async def call(media_type, media_id):
        calls.append(media_id)
        return ["gay"]

    resolved = ResolvedIdentity(media_source="themoviedb", media_id="1")
    passed, blocked = asyncio.run(
        filter_blacklist_keywords([item(resolved=resolved)], compiled, call)
    )
    assert blocked == []
    assert calls == []


def test_check_keywords_reports_layer():
    """关键词层的命中原因要写明是哪一层，用户才知道该关哪个开关。"""
    compiled = rules(blacklist_words="gay")
    assert check_keywords(compiled, ["lgbt", "gay"]) == "命中排除题材（TMDB 关键词）：gay"
    assert check_keywords(compiled, []) == ""


# ------------------------------------------------------- 体检：check_parts（已有订阅）


def test_check_parts_matches_genre_by_id():
    """体检拿到的是宿主订阅行 + TMDB 详情，判定要与流水线同源同序。"""
    compiled = rules(blacklist_genre_tv=[10764])
    assert check_parts(compiled, name="某真人秀", genre_ids=[10764]) == "命中排除类型：真人秀(10764)"
    assert check_parts(compiled, name="某剧", genre_ids=[18]) == ""


def test_check_parts_respects_media_type_for_genres():
    """电影与剧集的类型表不同：同一个 id 在另一侧不该命中。"""
    compiled = rules(blacklist_genre_movie=[10764])
    assert check_parts(compiled, name="x", media_type="tv", genre_ids=[10764]) == ""
    assert check_parts(compiled, name="x", media_type="movie", genre_ids=[10764]) != ""


def test_check_parts_matches_title_and_keywords():
    compiled = rules(blacklist_words="同性")
    assert check_parts(compiled, name="以你的心诠释我的爱") == ""
    assert check_parts(compiled, name="同性恋研究") != ""
    compiled_kw = rules(blacklist_words="gay")
    assert check_parts(compiled_kw, name="某剧", keywords=["lgbt", "gay"]) == (
        "命中排除题材（TMDB 关键词）：gay"
    )


def test_check_parts_inactive_rules_never_match():
    """总开关关掉时体检必须一条都不命中（否则会让人以为规则在生效）。"""
    compiled = rules(blacklist_enabled=False, blacklist_genre_tv=[10764], blacklist_words="同性")
    assert check_parts(compiled, name="同性", genre_ids=[10764], keywords=["gay"]) == ""
