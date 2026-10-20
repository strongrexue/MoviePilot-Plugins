"""按播出日自动启停：纯判定逻辑的回归锁。

真机场景：两百条订阅 + 默认 ``spider`` 订阅模式（约 32 轮/天），宿主每一轮都把
**全部** ``R``/``P`` 订阅拉进匹配循环 —— 当天根本没有新集的条目纯属空转。
``core/autotoggle.py`` 就是用来判断「这条订阅今天还需不需要参与搜索」的纯函数层。

这份测试盯住三件写错了会直接伤到用户的事：

1. **暂停只能写 ``S``**。宿主 ``get_states_for_search("R")`` 返回 ``"R,P"``，
   写 ``P`` 等于没暂停 —— 这是网上流传最广的错解，也是本项目踩过的坑；
2. **绝不往 ``Subscribe.note`` 写标记**。它是宿主的「已下载集号」清单，
   ``completion.py`` / ``priority.py`` 靠它算进度，写脏了会显示成集数错乱；
3. **只恢复自己暂停的**。用户手动暂停的订阅一旦被自动恢复，等于插件替用户
   做了决定，而且第二天还会再打一次架。

用例里的行一律用 dict 构造（``decide`` 同时接受 ORM 对象与 dict），
这样单测不依赖宿主 ORM。
"""
import asyncio
import sys
import types
from datetime import date
from pathlib import Path
from types import SimpleNamespace

PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins.v3"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from subscribecenter.core import autotoggle  # noqa: E402

TODAY = date(2026, 10, 20)


def _row(**overrides):
    """构造一条订阅行（默认是一条正在播出的剧集，什么都没下到）。

    ``type`` 用真实宿主值 ``"电视剧"``（``MediaType.TV``）：它是普通字符串列，
    存的是 ``MediaType`` 的**值**，不是 ``"tv"`` —— 1.13.0 就是在这里翻的车，
    默认值必须跟生产一致，否则整份用例都测不到那个 bug。
    """
    row = {
        "id": 7,
        "name": "测试剧集",
        "type": "电视剧",
        "media_source": "themoviedb",
        "media_id": "1234",
        "season": 1,
        "state": "R",
        "start_episode": 1,
        "total_episode": 12,
        "lack_episode": 12,
        "note": [],
        "episode_priority": None,
        "episode_group": "",
    }
    row.update(overrides)
    return row


def _eps(*pairs):
    """播出索引：``("2026-10-20", 3)`` 形式。"""
    return list(pairs)


# --------------------------------------------------------------------- 基本判定


def test_pending_within_window_keeps_running():
    """昨天那集没入库、还在保留窗口内 → 保持 R（继续搜种）。"""
    result = autotoggle.decide(
        _row(), _eps(("2026-10-19", 1)), TODAY, keep_days=3
    )
    assert result.target == autotoggle.STATE_RUN
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_PENDING
    assert result.pending == (1,)
    assert result.last_air == "2026-10-19"


def test_pending_overdue_pauses():
    """缺集已经超出窗口、后面也没有要播的 → 暂停（别一直挂着空转）。"""
    result = autotoggle.decide(_row(), _eps(("2026-10-01", 1)), TODAY, keep_days=3)
    assert result.target == autotoggle.STATE_PAUSED
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_MISSING_OVERDUE


def test_pending_overdue_but_upcoming_keeps_running():
    """缺集虽然过期，但明天就出新集 → 保持 R，别刚恢复又暂停。"""
    result = autotoggle.decide(
        _row(),
        _eps(("2026-10-01", 1), ("2026-10-21", 2)),
        TODAY,
        keep_days=3,
        lookahead_days=1,
    )
    assert result.action == autotoggle.ACTION_KEEP
    assert result.target == autotoggle.STATE_RUN
    assert result.reason == autotoggle.REASON_UPCOMING


def test_all_aired_downloaded_pauses():
    """已播的全入库、后面没有新集 → 暂停。"""
    result = autotoggle.decide(
        _row(note=[1, 2]), _eps(("2026-10-18", 1), ("2026-10-19", 2)), TODAY
    )
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_ALL_DONE
    assert result.aired == 2
    assert result.downloaded == 2


def test_premiere_not_aired_pauses():
    """首集还没播（新番预定）→ 暂停，等播出那天再开。"""
    result = autotoggle.decide(_row(state="R"), _eps(("2026-11-01", 1)), TODAY)
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_PREMIERE
    assert result.next_air == "2026-11-01"


def test_lookahead_counts_upcoming():
    """``lookahead_days`` 内的待播集算「该搜」。"""
    result = autotoggle.decide(
        _row(), _eps(("2026-11-01", 1)), TODAY, lookahead_days=15
    )
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_UPCOMING


def test_lookahead_zero_only_today():
    """``lookahead_days=0``（默认）时，明天的集不算 —— 只在播出当天开。"""
    result = autotoggle.decide(
        _row(), _eps(("2026-10-21", 1)), TODAY, lookahead_days=0
    )
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_PREMIERE


def test_episodes_before_start_episode_are_ignored():
    """``start_episode=5`` 的订阅不能因为前 4 集没下就被判成「一直缺集」。"""
    result = autotoggle.decide(
        _row(start_episode=5, note=[]),
        _eps(("2026-10-01", 1), ("2026-10-08", 2), ("2026-10-15", 3)),
        TODAY,
    )
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_ALL_DONE
    assert result.pending == ()


# --------------------------------------------------------------------- 已入库集号


def test_best_version_uses_episode_priority():
    """洗版订阅不用 ``note``，靠 ``episode_priority == 100`` 记进度。"""
    result = autotoggle.decide(
        _row(best_version=1, note=[], episode_priority={"1": 100, "2": 40}),
        _eps(("2026-10-19", 1), ("2026-10-20", 2)),
        TODAY,
    )
    assert result.downloaded == 1
    assert result.pending == (2,)
    assert result.action == autotoggle.ACTION_KEEP


def test_best_version_ignores_note_and_keeps_searching():
    """洗版订阅「刚下完 1080」不等于「不用再搜」（真机反馈的那个坑）。

    ``note`` 里 12 集都在 —— 换成普通订阅就是「已播剧集全部入库」该暂停；
    但洗版订阅还要等更好的版本（``episode_priority`` 没到 100），必须继续 R。
    """
    row = _row(
        best_version=1,
        note=list(range(1, 13)),
        episode_priority={str(ep): 60 for ep in range(1, 13)},
        lack_episode=0,
    )
    eps = [("2026-10-%02d" % day, day) for day in range(8, 20)]
    result = autotoggle.decide(row, eps, TODAY, keep_days=3, best_keep_days=90)
    assert result.target == autotoggle.STATE_RUN
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_BEST_PENDING
    assert result.downloaded == 0
    assert len(result.pending) == 12
    assert "洗到顶" in result.detail


def test_best_version_pauses_after_wash_window():
    """洗版窗口也过了（90 天没等到更好版本）→ 先暂停，别永远搜。"""
    row = _row(best_version=1, note=[1], episode_priority={"1": 60})
    result = autotoggle.decide(
        row, _eps(("2026-06-01", 1)), TODAY, keep_days=3, best_keep_days=90
    )
    assert result.target == autotoggle.STATE_PAUSED
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_BEST_OVERDUE


def test_best_version_completed_when_priority_reaches_100():
    """``episode_priority`` 全到 100 = 洗到头 → 按「已播剧集全部入库」暂停。"""
    row = _row(best_version=1, note=[1, 2], episode_priority={"1": 100, "2": 100})
    result = autotoggle.decide(
        row, _eps(("2026-10-18", 1), ("2026-10-19", 2)), TODAY, best_keep_days=90
    )
    assert result.downloaded == 2
    assert result.target == autotoggle.STATE_PAUSED
    assert result.reason == autotoggle.REASON_ALL_DONE


def test_best_version_current_priority_seed():
    """还没建 ``episode_priority`` 映射时，宿主的 ``current_priority`` 是种子值。"""
    low = _row(best_version=1, current_priority=60, total_episode=2)
    assert autotoggle.episode_numbers(low) == set()
    high = _row(best_version=1, current_priority=100, total_episode=2)
    assert autotoggle.episode_numbers(high) == {1, 2}


def test_normal_subscription_still_trusts_note():
    """回归锁：普通订阅照旧按 ``note`` 判定，别被洗版逻辑带偏。"""
    row = _row(note=[1, 2], episode_priority={"1": 60, "2": 60})
    assert autotoggle.episode_numbers(row) == {1, 2}


def test_empty_note_with_lack_zero_means_all_downloaded():
    """``note`` 被清空但 ``lack_episode <= 0``：视为整季下全（真机「已完成」就是这样）。"""
    result = autotoggle.decide(
        _row(note=[], total_episode=2, lack_episode=0),
        _eps(("2026-10-19", 1), ("2026-10-20", 2)),
        TODAY,
    )
    assert result.downloaded == 2
    assert result.reason == autotoggle.REASON_ALL_DONE


def test_note_is_never_mutated():
    """判定是只读的：``note`` 是宿主的数据列，绝不能留痕。"""
    row = _row(note=[1], episode_priority={"1": 100})
    snapshot = (list(row["note"]), dict(row["episode_priority"]), dict(row))
    autotoggle.decide(row, _eps(("2026-10-20", 2)), TODAY)
    assert list(row["note"]) == snapshot[0]
    assert dict(row["episode_priority"]) == snapshot[1]
    assert row == snapshot[2]


# --------------------------------------------------------------------- 该跳过的


def _movie_row(**overrides):
    """一条电影订阅：``season=0``、没有集数信息。

    宿主给电影用的是 ``total_episode=1``/``note=[]``，而且洗版订阅入库后状态
    仍是 ``R``（``completion.py`` 要等 ``priority=100`` 的资源），所以电影
    判定**不能**看「已入库」。
    """
    row = _row(
        type="电影",
        season=0,
        media_id="603",
        total_episode=1,
        lack_episode=1,
        note=[],
    )
    row.update(overrides)
    return row


def test_movie_waits_before_release():
    """还没到数字发行日 → 暂停等出种。"""
    result = autotoggle.decide(
        _movie_row(), [], TODAY, releases=[("2026-11-01", 4)]
    )
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_MOVIE_WAIT
    assert result.basis == "2026-11-01"
    assert result.basis_kind == "digital"


def test_movie_runs_inside_window():
    """数字发行日 = 今天 → 该搜。"""
    result = autotoggle.decide(
        _movie_row(), [], TODAY, keep_days=3, releases=[("2026-10-20", 4)]
    )
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_MOVIE_WINDOW


def test_movie_overdue_pauses():
    """发行日已过、保留窗口也过了，还没下到 → 暂停。"""
    result = autotoggle.decide(
        _movie_row(), [], TODAY, keep_days=3, releases=[("2026-10-01", 4)]
    )
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_MOVIE_OVERDUE


def test_movie_owned_paused_is_resumed_on_release_day():
    """本插件暂停的电影，到发行日要恢复。"""
    result = autotoggle.decide(
        _movie_row(id=603, state="S"),
        [],
        TODAY,
        keep_days=3,
        releases=[("2026-10-20", 4)],
        owned={603: {"state": "S"}},
    )
    assert result.action == autotoggle.ACTION_RESUME
    assert result.target == autotoggle.STATE_RUN


def test_best_version_movie_waits_for_physical():
    """洗版订阅看实体发行：数字版早就出了，但 BD 还没出时不能停。"""
    releases = [("2026-09-01", 4), ("2026-10-18", 5)]
    normal = autotoggle.decide(_movie_row(best_version=0), [], TODAY, keep_days=3,
                               releases=releases)
    best = autotoggle.decide(_movie_row(best_version=1), [], TODAY, keep_days=3,
                             best_keep_days=90, releases=releases)

    # 普通订阅：数字发行 9/1，窗口 3 天，早过了 → 暂停
    assert normal.reason == autotoggle.REASON_MOVIE_OVERDUE
    assert normal.basis == "2026-09-01"
    # 洗版订阅：基准换成实体发行 10/18，保留 90 天 → 继续搜
    assert best.action == autotoggle.ACTION_KEEP
    assert best.reason == autotoggle.REASON_MOVIE_WINDOW
    assert best.basis == "2026-10-18"
    assert best.basis_kind == "physical"


def test_movie_without_release_dates_is_skipped():
    """取不到发行日期时一动不动 —— 宁可多搜，不可误暂停。"""
    result = autotoggle.decide(_movie_row(), [], TODAY, releases=[])
    assert result.action == autotoggle.ACTION_SKIP
    assert result.reason == autotoggle.REASON_NO_RELEASE


def test_movie_can_be_switched_off():
    """关掉「连电影一起管」后，电影回到「不归本功能管」。"""
    result = autotoggle.decide(
        _movie_row(), [], TODAY, releases=[("2026-11-01", 4)], movie_enabled=False
    )
    assert result.action == autotoggle.ACTION_SKIP
    assert result.reason == autotoggle.REASON_MOVIE


def test_release_records_flattens_tmdb_payload():
    """宿主 ``async_get_info`` 返回的是原始 TMDB 结构（``release_dates.results``）。"""
    info = {
        "release_dates": {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"release_date": "2026-03-05T00:00:00.000Z", "type": 4},
                        {"release_date": "2026-04-02T00:00:00.000Z", "type": 5},
                    ],
                },
                {
                    "iso_3166_1": "CN",
                    "release_dates": [
                        {"release_date": "2026-01-10T00:00:00.000Z", "type": 4}
                    ],
                },
            ]
        }
    }
    records = autotoggle.release_records(info)
    assert ("2026-01-10", 4) in records
    assert ("2026-03-05", 4) in records
    # 同类型取最早的地区日期：越早的那天起就可能已经有种
    assert autotoggle.movie_basis(records) == ("2026-01-10", "digital")
    assert autotoggle.movie_basis(records, best_version=True) == ("2026-04-02", "physical")


def test_release_records_falls_back_to_top_level_date():
    """没有 ``release_dates`` 时退回顶层 ``release_date``（记作「上映」）。"""
    records = autotoggle.release_records({"release_date": "2025-06-01"})
    assert records == [("2025-06-01", 0)]
    assert autotoggle.movie_basis(records) == ("2025-06-01", "general")
    # 完全没日期 → 空，调用方据此跳过
    assert autotoggle.release_records({}) == []
    assert autotoggle.movie_basis([]) == ("", "")


def test_plan_feeds_movie_releases():
    """``plan`` 要按 ``media_id`` 把发行记录交给电影的判定。"""
    data = autotoggle.plan(
        [_movie_row()],
        {},
        TODAY,
        release_index={"603": [("2026-11-01", 4)]},
    )
    item = data["items"][0]
    assert item["reason"] == autotoggle.REASON_MOVIE_WAIT
    assert item["basis"] == "2026-11-01"
    assert data["paused"] == 1


def test_music_is_skipped():
    """音乐订阅既没有季也没有播出日，同样放过。"""
    result = autotoggle.decide(
        _row(type="音乐", season=0, media_id="111"), _eps(("2026-10-01", 1)), TODAY
    )
    assert result.reason == autotoggle.REASON_MOVIE


def test_media_kind_accepts_host_values():
    """``type`` 的三种真实形态都要认成剧集。

    宿主的列是字符串（``"电视剧"``）；万一是枚举成员、或者上游塞了 ``"tv"``，
    也不能因为形态不同就把用户的订阅全判成「非剧集」——1.13.0 的翻车点。
    """

    class _MediaTypeTV:
        """模拟 ``MediaType.TV`` 枚举成员：``name`` 与 ``value`` 都要能认。"""

        name = "TV"
        value = "电视剧"

        def __str__(self):
            return "MediaType.TV"

    assert autotoggle.media_kind(_row(type="电视剧")) == "tv"
    assert autotoggle.media_kind(_row(type="tv")) == "tv"
    assert autotoggle.media_kind(_row(type="TV")) == "tv"
    assert autotoggle.media_kind(_row(type=_MediaTypeTV())) == "tv"
    assert autotoggle.media_kind(_row(type="电影")) == "movie"
    assert autotoggle.media_kind(_row(type="movie")) == "movie"
    assert autotoggle.media_kind(_row(type="音乐")) == "music"
    # 拿不准的一律「未知」，不要猜成电影
    assert autotoggle.media_kind(_row(type=None)) == ""
    assert autotoggle.media_kind(_row(type="")) == ""
    assert autotoggle.media_kind(_row(type="系列")) == ""


def test_unknown_type_still_judged():
    """``type`` 缺失/陌生时照常判定，不能一律跳过（否则等于功能失效）。"""
    result = autotoggle.decide(_row(type=None), _eps(("2026-10-20", 3)), TODAY)
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_PENDING


def test_pending_state_is_skipped():
    """``P`` 仍会被宿主搜索，改它只会破坏宿主语义。"""
    result = autotoggle.decide(_row(state="P"), _eps(("2026-10-20", 1)), TODAY)
    assert result.action == autotoggle.ACTION_SKIP
    assert result.reason == autotoggle.REASON_PENDING_STATE
    assert result.target == "P", "跳过的条目不应产生目标状态"


def test_user_paused_is_never_resumed():
    """不是本插件暂停的 ``S`` → 用户手动暂停，永不恢复。"""
    result = autotoggle.decide(
        _row(state="S", id=9), _eps(("2026-10-20", 1)), TODAY, owned={}
    )
    assert result.action == autotoggle.ACTION_SKIP
    assert result.reason == autotoggle.REASON_USER_PAUSED


def test_manual_change_drops_ownership():
    """我们暂停过、但状态被改成 R → 让位给用户，本轮不动。"""
    result = autotoggle.decide(
        _row(state="R", id=9),
        _eps(("2026-10-20", 1)),
        TODAY,
        owned={"9": {"state": "S"}},
    )
    assert result.action == autotoggle.ACTION_SKIP
    assert result.reason == autotoggle.REASON_MANUAL
    assert result.owned is True


def test_owned_paused_is_resumed_on_air_day():
    """自己暂停的订阅到播出日要恢复 —— 这是整个功能的主路径。"""
    result = autotoggle.decide(
        _row(state="S", id=9),
        _eps(("2026-10-20", 4)),
        TODAY,
        owned={"9": {"state": "S"}},
    )
    assert result.action == autotoggle.ACTION_RESUME
    assert result.target == autotoggle.STATE_RUN
    assert result.owned is True


def test_no_schedule_is_skipped():
    """拿不到播出表时**不动**：宁可多搜一次，也不要把订阅误暂停。"""
    for episodes in (None, [], [("", 1)], [("待定", 2)]):
        result = autotoggle.decide(_row(), episodes, TODAY)
        assert result.action == autotoggle.ACTION_SKIP
        assert result.reason == autotoggle.REASON_NO_SCHEDULE


# --------------------------------------------------------------------- plan 汇总


def test_plan_uses_calendar_index_keys():
    """索引键与日历一致：``(media_id, season)``；没有季号时回落 ``(media_id, 0)``。"""
    rows = [_row(id=1, season=2, media_id="555"), _row(id=2, season=0, media_id="666")]
    index = {
        ("555", 2): _eps(("2026-10-20", 1)),
        ("666", 0): _eps(("2026-10-20", 1)),
    }
    data = autotoggle.plan(rows, index, TODAY)
    assert [item["action"] for item in data["items"]] == [
        autotoggle.ACTION_KEEP,
        autotoggle.ACTION_KEEP,
    ]
    assert data["today"] == "2026-10-20"


def test_plan_counts_and_reasons():
    """plan 的计数口径：paused / resumed / kept / skipped / planned。"""
    rows = [
        _row(id=1, state="R", note=[1]),  # 全下完 → 暂停
        _row(id=2, state="S", owned=None),  # 用户暂停 → 跳过
        _row(id=3, state="S"),  # 自己暂停 + 今天播 → 恢复
    ]
    index = {("1234", 1): _eps(("2026-10-19", 1))}
    data = autotoggle.plan(rows, index, TODAY, owned={"3": {"state": "S"}})
    assert data["paused"] == 1
    assert data["resumed"] == 1
    assert data["skipped"] == 1
    assert data["planned"] == 2
    assert data["reasons"][autotoggle.REASON_ALL_DONE] == 1
    assert data["reasons"][autotoggle.REASON_USER_PAUSED] == 1


def test_plan_puts_changes_first():
    """界面先看会动的：恢复 → 暂停 → 不动 → 跳过。"""
    rows = [
        _row(id=1, state="R", type="movie", season=0),  # skip
        _row(id=2, state="R", note=[1, 2]),  # pause
        _row(id=3, state="S"),  # resume
        _row(id=4, state="R", note=[]),  # keep
    ]
    index = {
        ("1234", 1): _eps(("2026-10-19", 1), ("2026-10-20", 2)),
    }
    data = autotoggle.plan(rows, index, TODAY, owned={"3": {"state": "S"}})
    assert [item["action"] for item in data["items"]] == [
        autotoggle.ACTION_RESUME,
        autotoggle.ACTION_PAUSE,
        autotoggle.ACTION_KEEP,
        autotoggle.ACTION_SKIP,
    ]


def test_plan_truncates_but_keeps_resumes():
    """单次上限截断时优先保留「恢复」：少暂停只是多搜一次，漏恢复会整天不搜。"""
    rows = [
        _row(id=1, state="S"),  # resume
        _row(id=2, state="R", note=[1, 2]),  # pause
        _row(id=3, state="R", name="b", note=[1, 2]),  # pause
    ]
    index = {("1234", 1): _eps(("2026-10-19", 1))}
    data = autotoggle.plan(rows, index, TODAY, owned={"1": {"state": "S"}}, max_changes=1)
    assert data["truncated"] is True
    assert data["planned"] == 1
    assert [item["id"] for item in data["changes"]] == [1]
    assert data["resumed"] == 1
    assert data["paused"] == 0


# --------------------------------------------------------------------- 接管表


def test_next_owned_tracks_pause_resume_and_manual():
    """接管表只记「自己暂停的」，并随执行结果增删。"""
    rows = [
        _row(id=1, state="R", note=[1, 2]),  # → 暂停，记入
        _row(id=2, state="S"),  # → 恢复，移出
        _row(id=3, state="R"),  # 手动改回 → 放弃接管，移出
    ]
    index = {("1234", 1): _eps(("2026-10-19", 1), ("2026-10-20", 2))}
    owned = {"2": {"state": "S"}, "3": {"state": "S"}, "99": {"state": "S"}}
    data = autotoggle.plan(rows, index, TODAY, owned=owned)
    new_owned = autotoggle.next_owned(owned, data, today_text="2026-10-20")

    assert set(new_owned) == {"1"}, f"接管表应只剩新暂停的 1，实际 {sorted(new_owned)}"
    assert new_owned["1"]["state"] == autotoggle.STATE_PAUSED
    assert new_owned["1"]["since"] == "2026-10-20"


def test_next_owned_respects_applied_ids():
    """写失败的条目不能进接管表 —— 否则下次会去「恢复」一个从没暂停过的订阅。"""
    rows = [_row(id=1, state="R", note=[1])]
    index = {("1234", 1): _eps(("2026-10-19", 1))}
    data = autotoggle.plan(rows, index, TODAY)

    assert autotoggle.next_owned({}, data, today_text="2026-10-20", applied_ids=[]) == {}
    kept = autotoggle.next_owned({}, data, today_text="2026-10-20", applied_ids=[1])
    assert set(kept) == {"1"}


# --------------------------------------------------------------------- 契约


def test_every_reason_has_a_label():
    """每个原因码都要有中文说明，前端只做兜底展示。"""
    missing = [
        name
        for name in dir(autotoggle)
        if name.startswith("REASON_") and name != "REASON_LABELS"
        and isinstance(getattr(autotoggle, name), str)
        and getattr(autotoggle, name) not in autotoggle.REASON_LABELS
    ]
    assert not missing, f"这些原因码没有中文说明：{missing}"


def test_paused_state_is_s_not_p():
    """守住语义：暂停是 ``S``；``P`` 是「待定」，宿主照样搜，本插件不碰。"""
    assert autotoggle.STATE_PAUSED == "S"
    assert autotoggle.STATE_PENDING == "P"
    pending_row = autotoggle.decide(_row(state="P"), _eps(("2026-10-20", 1)), TODAY)
    assert pending_row.action == autotoggle.ACTION_SKIP
    assert pending_row.target == "P"


def test_decide_is_pure_without_host():
    """纯函数：源码里不能出现宿主模块的 import（离线加载插件时不能炸）。"""
    source = Path(autotoggle.__file__).read_text(encoding="utf-8")
    offending = [
        line
        for line in source.splitlines()
        if line.strip().startswith(("import app", "from app"))
    ]
    assert not offending, f"纯逻辑模块不应 import 宿主：{offending}"


# --------------------------------------------------------------------- 插件接线


def _plan_stub(items, changes=None):
    """造一份 plan 输出，喂给 ``auto_toggle_run``。"""
    return {
        "today": "2026-10-20",
        "items": items,
        "changes": changes if changes is not None else [],
        "paused": 0,
        "resumed": 0,
        "kept": 0,
        "skipped": 0,
        "planned": len(changes or []),
        "reasons": {},
        "truncated": False,
    }


def test_config_is_clamped(plugin_cls):
    """配置越界要在读的时候收敛：笔误不该变成难查的行为异常。"""
    plugin = plugin_cls()
    plugin.init_plugin(
        {
            "enabled": True,
            "auto_toggle_enabled": True,
            "auto_toggle_cron": "不是 cron",
            "auto_toggle_lookahead_days": -5,
            "auto_toggle_keep_days": 3650,
            "auto_toggle_max_changes": 99999,
            "auto_toggle_notify": True,
        }
    )
    cfg = plugin._auto_toggle_config()
    assert cfg["enabled"] is True
    assert cfg["cron"] == "5 0 * * *", "非法 cron 回落到默认"
    assert cfg["lookahead_days"] == 0, "负数收敛到 0"
    assert cfg["keep_days"] == 90, "上限 90 天"
    assert cfg["max_changes"] == 2000, "上限 2000 条"
    assert cfg["notify"] is True


def test_service_registers_autotoggle_job(plugin_cls):
    """打开开关才注册定时任务；关着的时候服务列表不能凭空多一项。"""
    off = plugin_cls()
    off.init_plugin({"enabled": True, "auto_toggle_enabled": False})
    assert "subscribecenter_autotoggle" not in [item["id"] for item in off.get_service()]

    on = plugin_cls()
    on.init_plugin({"enabled": True, "auto_toggle_enabled": True})
    jobs = {item["id"]: item for item in on.get_service()}
    assert "subscribecenter_autotoggle" in jobs
    job = jobs["subscribecenter_autotoggle"]
    assert job["func"] == on.auto_toggle_scheduled
    assert job["trigger"] is not None


def test_routes_declared(plugin_cls):
    """两个路由都要有响应模型（否则宿主按模型校验时前端只拿到「未知错误」）。"""
    plugin = plugin_cls()
    plugin.init_plugin({"enabled": True})
    table = {item["path"]: item for item in plugin.get_api()}
    assert table["/auto_toggle"]["methods"] == ["GET"]
    assert table["/auto_toggle/apply"]["methods"] == ["POST"]
    for path in ("/auto_toggle", "/auto_toggle/apply"):
        assert table[path]["response_model"] is not None, path


def test_run_records_ownership(plugin):
    """跑完要落盘接管表：只记自己暂停的，写失败的、被手动改的都清掉。"""
    plugin._auto_toggle_state = lambda: {
        "owned": {"2": {"state": "S"}, "3": {"state": "S"}, "77": {"state": "S"}}
    }

    async def fake_plan():
        return _plan_stub(
            [
                {"id": 1, "name": "A", "action": "pause", "reason": "all_done", "target": "S"},
                {"id": 2, "name": "B", "action": "resume", "reason": "upcoming", "target": "R"},
                {"id": 3, "name": "C", "action": "skip", "reason": "manual_changed", "target": "R"},
            ],
            changes=[
                {"id": 1, "name": "A", "action": "pause", "target": "S"},
                {"id": 2, "name": "B", "action": "resume", "target": "R"},
            ],
        )

    async def fake_apply(changes):
        return [1, 2], []

    plugin.auto_toggle_plan = fake_plan
    plugin._apply_auto_toggle = fake_apply
    result = asyncio.run(plugin.auto_toggle_run(reason="cron"))

    assert result["paused"] == 1
    assert result["resumed"] == 1
    assert result["applied"] == 2
    assert result["owned"] == 1, "只剩新暂停的那条"
    saved = plugin.get_data("auto_toggle")
    assert set(saved["owned"]) == {"1"}
    assert saved["owned"]["1"]["state"] == "S"
    assert saved["last_run"]["reason"] == "cron"


def test_run_only_counts_applied(plugin):
    """写失败的条目不能计入暂停/恢复，也不能进接管表。"""
    plugin._auto_toggle_state = lambda: {}

    async def fake_plan():
        return _plan_stub(
            [
                {"id": 1, "name": "A", "action": "pause", "reason": "all_done", "target": "S"},
                {"id": 2, "name": "B", "action": "pause", "reason": "all_done", "target": "S"},
            ],
            changes=[
                {"id": 1, "name": "A", "action": "pause", "target": "S"},
                {"id": 2, "name": "B", "action": "pause", "target": "S"},
            ],
        )

    async def fake_apply(changes):
        return [1], [{"id": 2, "error": "boom"}]

    plugin.auto_toggle_plan = fake_plan
    plugin._apply_auto_toggle = fake_apply
    result = asyncio.run(plugin.auto_toggle_run())

    assert result["paused"] == 1
    assert result["failed"][0]["id"] == 2
    assert set(plugin.get_data("auto_toggle")["owned"]) == {"1"}


def test_scheduled_does_nothing_when_disabled(plugin):
    """定时入口在开关关闭时必须原地返回，不能碰订阅表。"""
    calls = []
    plugin._bridge = SimpleNamespace(run=lambda *a, **k: calls.append(1))
    plugin.auto_toggle_scheduled()
    assert not calls


# --------------------------------------------------------------------- 写状态

CHANGES = [
    {"id": 1, "name": "A", "action": "pause", "target": "S"},
    {"id": 2, "name": "B", "action": "resume", "target": "R"},
]


def _stub(monkeypatch, name, **attrs):
    """往 ``sys.modules`` 里插一个假宿主模块。

    父包也一起造（``__path__ = []``），否则 ``from app.x.y import z`` 会先
    去 import 父包而失败。
    """
    parts = name.split(".")
    for index in range(1, len(parts)):
        parent = ".".join(parts[:index])
        if parent not in sys.modules:
            pkg = types.ModuleType(parent)
            pkg.__path__ = []
            monkeypatch.setitem(sys.modules, parent, pkg)
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def _write_host(monkeypatch, *, fail_on=None, none_on=None, commit_error=False):
    """装一套假的 ``subscription_mutation_scope``，返回记录下来的写调用。"""
    calls = []

    class SubscriptionActor:
        def __init__(self, name="", is_superuser=False):
            self.name = name
            self.is_superuser = is_superuser

    class Service:
        async def update_status(self, sid, state, actor):
            calls.append((sid, state, actor))
            if sid == fail_on:
                raise RuntimeError("boom")
            if sid == none_on:
                return None
            return "mutation"

    class Scope:
        async def __aenter__(self):
            return Service()

        async def __aexit__(self, *exc):
            if commit_error:
                raise RuntimeError("commit failed")
            return False

    _stub(
        monkeypatch,
        "app.application.subscription.mutation",
        SubscriptionActor=SubscriptionActor,
    )
    _stub(
        monkeypatch,
        "app.startup.composition.subscription",
        subscription_mutation_scope=lambda: Scope(),
    )
    return calls


def test_apply_goes_through_mutation_scope(plugin, monkeypatch):
    """主路径：一条一个事务，用超级用户身份写，宿主才会绕过归属校验。"""
    calls = _write_host(monkeypatch)
    applied, failed = asyncio.run(plugin._apply_auto_toggle(list(CHANGES)))

    assert applied == [1, 2]
    assert failed == []
    assert [(sid, target) for sid, target, _ in calls] == [(1, "S"), (2, "R")]
    assert all(actor.is_superuser for _, _, actor in calls), "插件代表系统写入"
    assert calls[0][2].name == "SubscribeCenter"


def test_apply_counts_missing_subscribe_as_failure(plugin, monkeypatch):
    """宿主返回 None = 订阅不存在/无权限，必须计入失败，不能记成成功。"""
    _write_host(monkeypatch, none_on=2)
    applied, failed = asyncio.run(plugin._apply_auto_toggle(list(CHANGES)))

    assert applied == [1]
    assert [item["id"] for item in failed] == [2]
    assert "未找到" in failed[0]["error"]


def test_apply_isolates_single_failure(plugin, monkeypatch):
    """一条抛异常不能拖垮整批 —— 否则一条坏数据就永远改不动订阅。"""
    _write_host(monkeypatch, fail_on=1)
    applied, failed = asyncio.run(plugin._apply_auto_toggle(list(CHANGES)))

    assert applied == [2]
    assert [item["id"] for item in failed] == [1]


def test_apply_rolls_back_whole_batch_on_commit_error(plugin, monkeypatch):
    """提交失败等于一条都没落地：必须返回空 applied，接管表才不会记错。"""
    _write_host(monkeypatch, commit_error=True)
    applied, failed = asyncio.run(plugin._apply_auto_toggle(list(CHANGES)))

    assert applied == [], "事务回滚了就不能报成功"
    assert {item["id"] for item in failed} == {1, 2}
    assert all("提交失败" in item["error"] for item in failed)


def test_apply_falls_back_to_direct_write(plugin, monkeypatch):
    """老宿主没有 ``subscription_mutation_scope`` 时降级直写，并自行 commit。"""
    # None 在 sys.modules 里 = 导入立刻失败，正好模拟「宿主没这个模块」
    monkeypatch.setitem(sys.modules, "app.application.subscription.mutation", None)
    monkeypatch.setitem(sys.modules, "app.startup.composition.subscription", None)

    calls = []
    commits = []

    class Session:
        async def commit(self):
            commits.append(1)

    class Scope:
        async def __aenter__(self):
            return Session()

        async def __aexit__(self, *exc):
            return False

    class SubscribeOper:
        def __init__(self, session):
            self.session = session

        async def async_stage_update(self, sid, payload):
            calls.append((sid, payload.get("state")))
            return object()

    _stub(monkeypatch, "app.db", async_session_scope=lambda: Scope())
    _stub(monkeypatch, "app.db.oper.subscribe", SubscribeOper=SubscribeOper)

    applied, failed = asyncio.run(plugin._apply_auto_toggle(list(CHANGES)))

    assert applied == [1, 2]
    assert failed == []
    assert calls == [(1, "S"), (2, "R")]
    assert len(commits) == 2, "宿主 async_session_scope 退出不 commit，必须自己提交"


def test_apply_refuses_to_write_p(plugin, monkeypatch):
    """``P`` 不是暂停（宿主仍会搜索），写它等于骗自己，直接拒绝。"""
    calls = _write_host(monkeypatch)
    applied, failed = asyncio.run(
        plugin._apply_auto_toggle(
            [{"id": 3, "name": "C", "action": "pause", "target": "P"}]
        )
    )

    assert applied == []
    assert [item["id"] for item in failed] == [3]
    assert "非法" in failed[0]["error"]
    assert calls == [], "非法目标状态不该碰宿主"
