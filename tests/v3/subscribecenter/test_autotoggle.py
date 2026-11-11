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
import time
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
    eps = [("2026-10-%02d" % (7 + ep), ep) for ep in range(1, 13)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.target == autotoggle.STATE_RUN
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_BEST_PENDING
    assert result.downloaded == 0
    assert len(result.pending) == 12
    assert "洗到顶" in result.detail


def test_best_version_marks_complete_after_wash_window():
    """洗版窗口也过了（90 天没等到更好版本）→ **标记洗版完成**，不暂停。

    暂停会让它永远卡在 ``S``：宿主的完成判定只在搜索态跑，停在暂停上等于
    「既不洗也不收尾」，用户还得手动清。写 100 才是宿主认的「洗版结束」。
    """
    row = _row(best_version=1, note=[1], episode_priority={"1": 60}, total_episode=1)
    result = autotoggle.decide(
        row, _eps(("2026-06-01", 1)), TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.action == autotoggle.ACTION_MARK_COMPLETE
    assert result.reason == autotoggle.REASON_BEST_OVERDUE
    # 必须是 R：停在 S 上宿主不会进完成判定，写 100 也等于没生效
    assert result.target == autotoggle.STATE_RUN
    assert result.best_full is False
    # 分集洗版要给出「还没到 100、需要补写」的集号
    assert result.target_episodes == (1,)


def test_best_version_marks_complete_full_season():
    """全集洗版超期只写 ``current_priority``，不需要逐集集号。"""
    row = _row(
        best_version=1, best_version_full=1,
        note=[1], episode_priority={"1": 60}, total_episode=1,
    )
    result = autotoggle.decide(
        row, _eps(("2026-06-01", 1)), TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.action == autotoggle.ACTION_MARK_COMPLETE
    assert result.best_full is True
    assert result.target_episodes == ()


def test_best_version_wash_window_starts_from_finale():
    """洗版窗口从**季终**（最后一集播出日）起算，不是最后一集没洗到顶的那天。

    第 1 集拖了 80 天没洗到顶、第 12 集昨天刚播完 —— 按旧算法（锚点取
    ``pending[-1]``，这里恰好也是第 1 集）会判超期；按季终起算只过了 1 天，
    仍在 90 天窗口内，必须保持 R，给它留够洗版期。
    """
    row = _row(
        best_version=1,
        note=list(range(1, 13)),
        episode_priority={"1": 60},
        lack_episode=0,
    )
    eps = [("2026-08-01", 1)] + [("2026-10-%02d" % (1 + ep), ep) for ep in range(2, 13)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_BEST_PENDING


def test_best_version_wash_window_after_finale_overdue():
    """季终已过 91 天仍没洗到顶 → 标记完成。"""
    row = _row(
        best_version=1,
        note=list(range(1, 13)),
        episode_priority={"1": 60},
        lack_episode=0,
    )
    eps = [("2026-06-01", ep) for ep in range(1, 13)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.action == autotoggle.ACTION_MARK_COMPLETE
    assert result.reason == autotoggle.REASON_BEST_OVERDUE


def test_best_version_during_airing_always_keeps_searching():
    """洗版订阅在播出期**一律保持 R**，不再按「入库即暂停」判。

    1.18.3 试过「每集最近 N 天保持搜索」，结果日更剧天天命中、几乎不暂停；
    1.18.4 改成整季都保持搜索：宿主在播出期只下首个可用版本，1080 先出、
    2160 常隔几十分钟才出，一暂停就再也抓不到。收工路径只有季终后那一条。
    """
    row = _row(
        best_version=1,
        note=list(range(1, 13)),
        episode_priority={str(ep): 60 for ep in range(1, 13)},
    )
    eps = [("2026-10-%02d" % (7 + ep), ep) for ep in range(1, 13)]
    eps.append(("2026-10-21", 13))

    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.target == autotoggle.STATE_RUN
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_BEST_AIRING
    assert "2026-10-21" in result.detail

    always = autotoggle.decide(
        row,
        eps,
        TODAY,
        keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
        best_mode=autotoggle.BEST_MODE_ALWAYS,
    )
    assert always.target == autotoggle.STATE_RUN
    assert always.reason == autotoggle.REASON_BEST_PENDING


# ------------------------------------------------------------------ 季终前开洗版
# 宿主 ``app/chain/subscribe/completion.py:163`` 分两条路：没开洗版 → 已播全入库
# 就写历史并**删除订阅**；开了洗版 → 走优先级判定，没洗到 100 就不删。所以普通
# 订阅必须在最后一集**播出之前**补上 ``best_version``，等于给结局上保险。


def test_best_preopen_sets_best_version_before_finale():
    """最后一集明天就播、配置 1 天 → 本轮给它开洗版。"""
    row = _row(note=list(range(1, 11)), lack_episode=1, best_version=0)
    eps = [("2026-10-%02d" % (9 + ep), ep) for ep in range(1, 11)]
    eps.append(("2026-10-21", 11))
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3, best_preopen_days=1,
        best_preopen_enabled=True,
    )
    assert result.action == autotoggle.ACTION_SET_BEST
    assert result.reason == autotoggle.REASON_BEST_PREOPEN
    # 状态不动：只写 best_version 字段，不暂停也不恢复
    assert result.target == row["state"]
    assert result.days_to_finale == 1
    assert "2026-10-21" in result.detail


def test_best_preopen_off_by_default():
    """开关没开就一行都不动（1.18.5 起关闭靠开关，不再用天数 0 表示关闭）。"""
    row = _row(note=list(range(1, 11)), lack_episode=1)
    eps = [("2026-10-%02d" % (9 + ep), ep) for ep in range(1, 11)]
    eps.append(("2026-10-21", 11))
    result = autotoggle.decide(row, eps, TODAY, keep_days=3)
    assert result.action != autotoggle.ACTION_SET_BEST


def test_best_preopen_zero_days_means_finale_today():
    """天数为 0 = 季终当天才转洗版（不是关闭）。"""
    row = _row(note=list(range(1, 11)), lack_episode=1)
    eps = [("2026-10-%02d" % (10 + ep), ep) for ep in range(1, 11)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3, best_preopen_days=0,
        best_preopen_enabled=True,
    )
    assert result.action == autotoggle.ACTION_SET_BEST
    assert result.days_to_finale == 0


def test_best_preopen_skips_existing_best_version():
    """已经是洗版订阅的不再重复开。"""
    row = _row(
        note=list(range(1, 11)),
        lack_episode=1,
        best_version=1,
        episode_priority={str(ep): 60 for ep in range(1, 11)},
    )
    eps = [("2026-10-%02d" % (9 + ep), ep) for ep in range(1, 11)]
    eps.append(("2026-10-21", 11))
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3, best_preopen_days=1,
        best_preopen_enabled=True,
    )
    assert result.action != autotoggle.ACTION_SET_BEST


def test_best_preopen_ignores_show_already_finished():
    """季终已经过了的老剧不开洗版，否则会把几百条存量订阅全改成洗版。"""
    row = _row(note=[], lack_episode=12)
    eps = [("2026-06-%02d" % ep, ep) for ep in range(1, 13)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3, best_preopen_days=1,
        best_preopen_enabled=True,
    )
    assert result.action != autotoggle.ACTION_SET_BEST


def test_best_preopen_respects_window():
    """最后一集还在 3 天后 → 1 天窗口还没到，不动。"""
    row = _row(note=list(range(1, 11)), lack_episode=1)
    eps = [("2026-10-%02d" % (9 + ep), ep) for ep in range(1, 11)]
    eps.append(("2026-10-23", 11))
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3, best_preopen_days=1,
        best_preopen_enabled=True,
    )
    assert result.action != autotoggle.ACTION_SET_BEST
    assert result.days_to_finale == 3


# ------------------------------------------------------------------ 季终判定的三重兜底
# 季终一误判，洗版窗口就提前开始计时 → 到期标记完成 → 宿主归档删订阅。
# 三种情况必须捞回来：①最后一集被删了 air_date ②集数没追满 ③季中休更。


def test_finale_not_reached_when_undated_episode_left():
    """有集号在最后已播集之后、只是没有播出日（延期）→ 不算季终。"""
    row = _row(best_version=1, note=list(range(1, 11)),
               episode_priority={str(ep): 60 for ep in range(1, 11)})
    eps = [("2026-09-%02d" % ep, ep) for ep in range(1, 11)]
    result = autotoggle.decide(
        row, eps, TODAY, best_keep_days_tv=7,
        season={"total": 12, "extra": [11, 12]},
    )
    assert result.finale is False
    # 不算季终 → 仍走播出期口径，保持搜索
    assert result.target == autotoggle.STATE_RUN
    assert result.reason == autotoggle.REASON_BEST_AIRING


def test_finale_not_reached_when_episode_count_incomplete():
    """TMDB 说这一季 40 集、播出表只到 25 → 不算季终。"""
    row = _row(note=[1])
    eps = [("2026-09-%02d" % (ep % 28 + 1), ep) for ep in range(1, 26)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3, season={"total": 40},
    )
    assert result.finale is False


def test_finale_not_reached_for_mid_season_break():
    """最后一集带 ``mid_season`` 标记 = 季中休更，不能当季终。"""
    row = _row(note=[1])
    eps = [("2026-10-%02d" % ep, ep) for ep in range(1, 10)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3,
        season={"total": 9, "mid_season": True},
    )
    assert result.finale is False


def test_finale_confirmed_by_tmdb_status():
    """TMDB 标了 ``Ended`` → 就算集数没追满也算季终。"""
    row = _row(best_version=1, note=list(range(1, 11)),
               episode_priority={str(ep): 60 for ep in range(1, 11)})
    eps = [("2026-06-%02d" % ep, ep) for ep in range(1, 11)]
    result = autotoggle.decide(
        row, eps, TODAY, best_keep_days_tv=7,
        season={"total": 20, "status": "Ended"},
    )
    assert result.finale is True


def test_finale_canceled_show_also_counts():
    """``Canceled`` 同样处理：不会再有新集了。"""
    row = _row(best_version=1, note=[1], episode_priority={"1": 60})
    eps = [("2026-06-01", 1)]
    result = autotoggle.decide(
        row, eps, TODAY, best_keep_days_tv=7,
        season={"total": 8, "status": "Canceled"},
    )
    assert result.finale is True
    # 季终已过 7 天以上 → 标记洗版完成，不暂停
    assert result.action == autotoggle.ACTION_MARK_COMPLETE


def test_best_version_after_finale_enters_wash_window():
    """季终后（索引里没有未来集）才进洗版窗口：还没洗到顶 → 保持 R。"""
    row = _row(
        best_version=1,
        note=list(range(1, 13)),
        episode_priority={str(ep): 60 for ep in range(1, 13)},
    )
    eps = [("2026-10-%02d" % (7 + ep), ep) for ep in range(1, 13)]
    result = autotoggle.decide(
        row, eps, TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.target == autotoggle.STATE_RUN
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_BEST_PENDING


def test_plan_passes_best_mode():
    """``plan()`` 要把洗版模式透传给 ``decide()``（曾漏传导致配置无效）。"""
    row = _row(
        best_version=1,
        note=list(range(1, 13)),
        episode_priority={str(ep): 60 for ep in range(1, 13)},
    )
    eps = [("2026-10-%02d" % (7 + ep), ep) for ep in range(1, 13)]
    eps.append(("2026-10-21", 13))
    index = {("1234", 1): eps}

    default = autotoggle.plan(
        [row], index, TODAY, keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    # 默认 after_finale：播出期按「整季保持搜索」判，不写库
    assert default["changes"] == []
    assert default["items"][0]["reason"] == autotoggle.REASON_BEST_AIRING

    always = autotoggle.plan(
        [row],
        index,
        TODAY,
        keep_days=3,
        best_keep_days_tv=90, best_keep_days_movie=90,
        best_mode=autotoggle.BEST_MODE_ALWAYS,
    )
    # always：播出期也直接按洗版窗口算，同样保持搜索但原因不同
    assert always["changes"] == []
    assert always["items"][0]["reason"] == autotoggle.REASON_BEST_PENDING


def test_best_version_completed_when_priority_reaches_100():
    """``episode_priority`` 全到 100 = 洗到头 → 仍保持 R，只换原因。"""
    row = _row(best_version=1, note=[1, 2], episode_priority={"1": 100, "2": 100})
    result = autotoggle.decide(
        row, _eps(("2026-10-18", 1), ("2026-10-19", 2)), TODAY,
        best_keep_days_tv=90, best_keep_days_movie=90,
    )
    assert result.downloaded == 2
    # 洗版洗完也不写 S：宿主只处理搜索态的订阅，停在 S 上等于永远卡住
    assert result.target == autotoggle.STATE_RUN
    assert result.action == autotoggle.ACTION_KEEP
    assert result.reason == autotoggle.REASON_BEST_DONE


def test_best_version_current_priority_seed():
    """还没建 ``episode_priority`` 映射时，宿主的 ``current_priority`` 是种子值。"""
    low = _row(best_version=1, current_priority=60, total_episode=2)
    assert autotoggle.best_version_done(low) == set()
    high = _row(best_version=1, current_priority=100, total_episode=2)
    assert autotoggle.best_version_done(high) == {1, 2}


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


def test_movie_overdue_completes():
    """发行日已过、保留窗口也过了，还没下到 → 写完成历史后收工。

    普通电影写 ``current_priority=100`` 宿主不认（那只对洗版订阅有效），
    留着只会一直 R 白搜，所以直接走「完成 + 删除」。
    """
    result = autotoggle.decide(
        _movie_row(), [], TODAY, keep_days=3, releases=[("2026-10-01", 4)]
    )
    assert result.action == autotoggle.ACTION_COMPLETE
    assert result.reason == autotoggle.REASON_MOVIE_OVERDUE
    assert result.target == autotoggle.STATE_RUN


def test_best_version_movie_overdue_marks_complete():
    """洗版电影超窗口只标记洗版完成，不删 —— 洗版问的是「洗到顶没有」。"""
    result = autotoggle.decide(
        _movie_row(best_version=1),
        [],
        TODAY,
        keep_days=3,
        best_keep_days_movie=90,
        releases=[("2026-06-01", 5)],
    )
    assert result.action == autotoggle.ACTION_MARK_COMPLETE
    assert result.reason == autotoggle.REASON_MOVIE_OVERDUE
    assert result.target == autotoggle.STATE_RUN


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
                             best_keep_days_movie=90, releases=releases)

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


def test_movie_basis_ex_estimates_digital_from_theatrical():
    """只有影院日期时，往后推一个偏移当估算发行日，并标记「估算」。

    真机案例：《神探之痕迹》TMDB 只有影院上映 2026-10-01，数字版还没公布。
    院线在映期间站点上根本没有可下版本，拿上映日开窗等于白搜，窗口一过还会
    判「已过期」，等真出 WEB-DL 时反而不搜了。
    """
    records = [("2026-10-01", 3)]
    day, kind, estimated, raw = autotoggle.movie_basis_ex(
        records, theatrical_offset_days=90
    )
    assert (day, kind, estimated, raw) == ("2026-12-30", "estimated", True, "2026-10-01")
    # 不估算时保持旧行为（直接用上映日）
    assert autotoggle.movie_basis_ex(records) == (
        "2026-10-01",
        "theatrical",
        False,
        "2026-10-01",
    )
    # 简版接口不做估算：日历 / 发现流程要的是真实发行日
    assert autotoggle.movie_basis(records) == ("2026-10-01", "theatrical")


def test_movie_basis_ex_prefers_real_digital_over_estimate():
    """TMDB 补上真实数字发行日期后，锚点必须切回真实日期。"""
    records = [("2026-10-01", 3), ("2026-12-05", 4)]
    day, kind, estimated, raw = autotoggle.movie_basis_ex(
        records, theatrical_offset_days=90
    )
    assert (day, kind, estimated, raw) == ("2026-12-05", "digital", False, "2026-12-05")
    # 洗版看实体发行，也不该被影院估算顶掉
    records = [("2026-10-01", 3), ("2027-01-05", 5)]
    assert autotoggle.movie_basis_ex(
        records, best_version=True, theatrical_offset_days=90
    ) == ("2027-01-05", "physical", False, "2027-01-05")


def test_movie_theatrical_estimate_pauses_until_estimated_date():
    """影院在映 + 估算偏移 → 估算日之前保持暂停，而不是判「已过期」。"""
    result = autotoggle.decide(
        _movie_row(),
        [],
        TODAY,
        releases=[("2026-10-01", 3)],
        keep_days=30,
        movie_theatrical_offset_days=90,
    )
    assert result.action == autotoggle.ACTION_PAUSE
    assert result.reason == autotoggle.REASON_MOVIE_WAIT
    assert result.basis == "2026-12-30"
    assert result.basis_kind == "estimated"
    assert result.assumed is True
    assert "影院上映 2026-10-01 + 90 天估算" in result.detail


def test_movie_theatrical_offset_zero_keeps_old_behaviour():
    """偏移设 0 = 不估算，行为与 1.17.4 之前完全一致。"""
    result = autotoggle.decide(
        _movie_row(),
        [],
        TODAY,
        releases=[("2026-10-01", 3)],
        keep_days=30,
        movie_theatrical_offset_days=0,
    )
    assert result.reason == autotoggle.REASON_MOVIE_WINDOW
    assert result.basis == "2026-10-01"
    assert result.basis_kind == "theatrical"
    assert result.assumed is False
    assert "估算" not in result.detail


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
    data = autotoggle.plan(rows, index, TODAY, owned={"1": {"state": "S"}})
    assert data["truncated"] is False
    assert data["planned"] == 3
    assert {item["id"] for item in data["changes"]} == {1, 2, 3}
    assert data["resumed"] == 1
    assert data["paused"] == 2


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
            "auto_toggle_best_version_keep_days_tv": 99999,
            "auto_toggle_best_version_keep_days_movie": 99999,
            "auto_toggle_notify": True,
        }
    )
    cfg = plugin._auto_toggle_config()
    assert cfg["enabled"] is True
    assert cfg["cron"] == "5 0 * * *", "非法 cron 回落到默认"
    assert cfg["lookahead_days"] == 0, "负数收敛到 0"
    assert cfg["keep_days"] == 90, "上限 90 天"
    assert cfg["best_keep_days_tv"] == 365, "上限 365 天"
    assert cfg["best_keep_days_movie"] == 365, "上限 365 天"
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


def _follow_ready(plugin_cls, **overrides):
    """构造一个「自动启停 + 跟随刷新」都打开的插件实例。"""
    plugin = plugin_cls()
    config = {
        "enabled": True,
        "auto_toggle_enabled": True,
        "auto_toggle_follow_refresh": True,
    }
    config.update(overrides)
    plugin.init_plugin(config)
    return plugin


class _FollowBridge:
    """记录「有没有真的被叫去跑一轮」。"""

    def __init__(self):
        self.calls = 0

    def run(self, func, timeout=None):
        self.calls += 1
        return {"ok": True}


def test_follow_refresh_registers_service_only_when_enabled(plugin_cls):
    """跟随刷新的心跳只在开关打开时注册；关着不能凭空多一个每分钟任务。"""
    off = _follow_ready(plugin_cls, auto_toggle_follow_refresh=False)
    assert "subscribecenter_autotoggle_follow" not in [
        item["id"] for item in off.get_service()
    ]

    on = _follow_ready(plugin_cls)
    jobs = {item["id"]: item for item in on.get_service()}
    assert "subscribecenter_autotoggle_follow" in jobs
    job = jobs["subscribecenter_autotoggle_follow"]
    assert job["func"] == on.auto_toggle_follow_tick
    assert job["trigger"] is not None


def test_follow_tick_records_then_runs_next_minute(plugin_cls):
    """两段式：先记下「刷新完成了」，下一次心跳才真正跑（给宿主留落库时间）。"""
    plugin = _follow_ready(plugin_cls)
    plugin._refresh_progress = lambda: ("2026-11-01 10:00:00", False)
    bridge = _FollowBridge()
    plugin._bridge = bridge

    plugin.auto_toggle_follow_tick()
    assert bridge.calls == 0, "第一次只记下完成时间，不马上跑"
    seen = plugin._auto_toggle_state()["refresh_follow"]
    assert seen["finished_at"] == "2026-11-01 10:00:00"

    state = plugin._auto_toggle_state()
    state["refresh_follow"]["seen_at"] -= 120
    plugin._save_auto_toggle_state(state)
    plugin.auto_toggle_follow_tick()
    assert bridge.calls == 1, "过了静置时间，这一跳应该真的跑"
    assert plugin._auto_toggle_state()["refresh_follow"].get("ran_at")


def test_follow_tick_waits_for_settle_seconds(plugin_cls):
    """刚看到完成就立刻跑 = 可能读到没落库的旧账，必须等。"""
    plugin = _follow_ready(plugin_cls)
    plugin._refresh_progress = lambda: ("2026-11-01 10:00:00", False)
    bridge = _FollowBridge()
    plugin._bridge = bridge

    plugin.auto_toggle_follow_tick()
    plugin.auto_toggle_follow_tick()
    assert bridge.calls == 0


def test_follow_tick_debounces_within_thirty_minutes(plugin_cls):
    """spider 模式一天刷 32 次，30 分钟内跑过就不再跟着跑。"""
    plugin = _follow_ready(plugin_cls)
    plugin._refresh_progress = lambda: ("2026-11-01 10:00:00", False)
    bridge = _FollowBridge()
    plugin._bridge = bridge
    plugin._save_auto_toggle_state(
        {
            "refresh_follow": {
                "finished_at": "2026-11-01 10:00:00",
                "seen_at": time.time() - 300,
                "ran_at": time.time() - 60,
            }
        }
    )

    plugin.auto_toggle_follow_tick()
    assert bridge.calls == 0


def test_follow_tick_ignores_missing_or_running_refresh(plugin_cls):
    """拿不到完成时间、或刷新正在跑，都不能触发。"""
    plugin = _follow_ready(plugin_cls)
    bridge = _FollowBridge()
    plugin._bridge = bridge

    plugin._refresh_progress = lambda: (None, False)
    plugin.auto_toggle_follow_tick()
    assert "refresh_follow" not in plugin._auto_toggle_state()

    plugin._refresh_progress = lambda: ("2026-11-01 10:00:00", True)
    plugin.auto_toggle_follow_tick()
    assert "refresh_follow" not in plugin._auto_toggle_state()
    assert bridge.calls == 0


def test_follow_tick_does_nothing_when_switch_off(plugin_cls):
    """开关关着时连进度都不该去读（每分钟一次也不白花）。"""
    plugin = _follow_ready(plugin_cls, auto_toggle_follow_refresh=False)
    reads = []
    plugin._refresh_progress = lambda: reads.append(1) or ("2026-11-01 10:00:00", False)
    bridge = _FollowBridge()
    plugin._bridge = bridge

    plugin.auto_toggle_follow_tick()
    assert reads == []
    assert bridge.calls == 0


def test_follow_tick_skips_when_previous_round_running(plugin_cls):
    """上一轮还在跑就别叠一轮。"""
    plugin = _follow_ready(plugin_cls)
    plugin._refresh_progress = lambda: ("2026-11-01 10:00:00", False)
    plugin._auto_toggle_running = lambda: {"running": True}
    bridge = _FollowBridge()
    plugin._bridge = bridge
    plugin._save_auto_toggle_state(
        {
            "refresh_follow": {
                "finished_at": "2026-11-01 10:00:00",
                "seen_at": time.time() - 300,
            }
        }
    )

    plugin.auto_toggle_follow_tick()
    assert bridge.calls == 0


def test_refresh_progress_reads_only_subscribe_refresh(plugin_cls, monkeypatch):
    """只认订阅刷新：其它任务（比如文件整理）跑完了不能触发我们。"""
    plugin = _follow_ready(plugin_cls)

    class _FakeScheduler:
        def list(self):
            return [
                SimpleNamespace(id="subscribe_refresh"),
                SimpleNamespace(id="subscribe_refresh|8:30"),
                SimpleNamespace(id="transfer"),
            ]

        def get_progress(self, job_id):
            return {
                "subscribe_refresh": SimpleNamespace(
                    status="success", finished_at="2026-11-01 10:00:00"
                ),
                "subscribe_refresh|8:30": SimpleNamespace(
                    status="success", finished_at="2026-11-01 12:30:00"
                ),
                "transfer": SimpleNamespace(
                    status="success", finished_at="2026-11-01 23:59:00"
                ),
            }.get(job_id)

    fake_module = types.ModuleType("app.application.scheduling")
    fake_module.get_scheduler = lambda: _FakeScheduler()
    monkeypatch.setitem(sys.modules, "app.application.scheduling", fake_module)

    finished, running = plugin._refresh_progress()
    assert finished == "2026-11-01 12:30:00", "取订阅刷新里最新的那个完成时间"
    assert running is False


def test_refresh_progress_marks_running(plugin_cls, monkeypatch):
    """刷新正在跑的时候不能当成「已经跑完」。"""
    plugin = _follow_ready(plugin_cls)

    class _FakeScheduler:
        def list(self):
            return []

        def get_progress(self, job_id):
            return SimpleNamespace(status="running", finished_at="2026-11-01 09:00:00")

    fake_module = types.ModuleType("app.application.scheduling")
    fake_module.get_scheduler = lambda: _FakeScheduler()
    monkeypatch.setitem(sys.modules, "app.application.scheduling", fake_module)

    _finished, running = plugin._refresh_progress()
    assert running is True


def test_routes_declared(plugin_cls):
    """两个路由都要有响应模型（否则宿主按模型校验时前端只拿到「未知错误」）。"""
    plugin = plugin_cls()
    plugin.init_plugin({"enabled": True})
    table = {item["path"]: item for item in plugin.get_api()}
    assert table["/auto_toggle"]["methods"] == ["GET"]
    assert table["/auto_toggle/apply"]["methods"] == ["POST"]
    for path in ("/auto_toggle", "/auto_toggle/apply"):
        assert table[path]["response_model"] is not None, path


def test_calendar_flags_follow_plan(plugin):
    """日历上的「今天会不会被搜」必须跟预览是同一份判定。

    被判「跳过」的（P 态、电影开关关掉…）没有 target，只能按宿主当前状态算：
    `R`/`P` 仍会被刷新搜到，`S` 不会。标错这个，日历就会替插件说谎。
    """
    plugin._auto_toggle_config = lambda: {"enabled": True}

    async def fake_plan(**_kwargs):
        return _plan_stub(
            [
                {"id": 1, "target": "R", "state": "R", "reason": "pending", "reason_label": "缺集"},
                {"id": 2, "target": "S", "state": "R", "reason": "all_done", "reason_label": "已播剧集全部入库"},
                {"id": 3, "target": "P", "state": "P", "reason": "pending_state", "reason_label": "P 态"},
                {"id": 4, "target": "S", "state": "S", "reason": "user_paused", "reason_label": "手动暂停"},
            ]
        )

    plugin.auto_toggle_plan = fake_plan
    flags = asyncio.run(plugin._auto_toggle_flags())

    assert flags[1] == {"searched": True, "note": ""}
    assert flags[2]["searched"] is False
    assert flags[2]["note"] == "已播剧集全部入库"
    assert flags[3]["searched"] is True, "P 态仍会被刷新搜到"
    assert flags[4]["searched"] is False, "S 态不会被搜"


def test_calendar_flags_absent_or_swallowed(plugin):
    """没开自动启停、或判定自己炸了，都不能让日历崩，也不能瞎标。"""
    plugin._auto_toggle_config = lambda: {"enabled": False}
    assert asyncio.run(plugin._auto_toggle_flags()) is None

    plugin._auto_toggle_config = lambda: {"enabled": True}

    async def boom(**_kwargs):
        raise RuntimeError("tmdb down")

    plugin.auto_toggle_plan = boom
    assert asyncio.run(plugin._auto_toggle_flags()) is None


def test_run_records_ownership(plugin):
    """跑完要落盘接管表：只记自己暂停的，写失败的、被手动改的都清掉。"""
    plugin._auto_toggle_state = lambda: {
        "owned": {"2": {"state": "S"}, "3": {"state": "S"}, "77": {"state": "S"}}
    }

    async def fake_plan(**_kwargs):
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

    async def fake_plan(**_kwargs):
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
    """装一套假的 ``subscription_mutation_scope``，返回记录下来的写调用。

    记录的是 ``(sid, payload, actor)``：1.18.2 起插件不再只写状态，
    「标记洗版完成」要往同一个接口写 ``current_priority``/``episode_priority``，
    所以替身必须实现 ``update()`` 而不是 ``update_status()``。
    """
    calls = []

    class SubscriptionActor:
        def __init__(self, name="", is_superuser=False):
            self.name = name
            self.is_superuser = is_superuser

    class Service:
        async def get_accessible(self, sid, actor):
            return None

        async def update(self, sid, payload, actor):
            calls.append((sid, dict(payload), actor))
            if sid == fail_on:
                raise RuntimeError("boom")
            if sid == none_on:
                return None
            return "mutation"

        async def update_status(self, sid, state, actor):
            return await self.update(sid, {"state": state}, actor)

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
    assert [(sid, payload) for sid, payload, _ in calls] == [
        (1, {"state": "S"}),
        (2, {"state": "R"}),
    ]
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


# --------------------------------------------------- 缺集来源：订阅记录 / 媒体库核对


def test_has_download_record_reads_note_and_priority():
    """「订阅有没有入库记录」只看 ``note`` 与 ``episode_priority`` 两个宿主列。"""
    assert autotoggle.has_download_record(_row(note=[1, 2])) is True
    assert autotoggle.has_download_record(_row(note=[])) is False
    assert autotoggle.has_download_record(_row(note=None)) is False
    assert autotoggle.has_download_record(_row(note=[0, None, "x"])) is False
    assert (
        autotoggle.has_download_record(
            _row(note=[], best_version=1, episode_priority={"1": 80})
        )
        is True
    )


def test_library_present_removes_false_missing():
    """库里有第 1 集 → 不再算缺 → 已播全部入库 → 暂停。

    这就是用户那条 180 集国漫的场景：集不是经订阅下的，``note`` 是空的。
    """
    result = autotoggle.decide(
        _row(note=[]),
        _eps(("2026-10-19", 1)),
        TODAY,
        keep_days=3,
        library_present={1},
        library_check=True,
    )
    assert result.reason == autotoggle.REASON_ALL_DONE
    assert result.library_confirmed == 1
    assert result.assumed is False


def test_library_present_keeps_really_missing():
    """库里确实没有第 2 集 → 仍然算缺。并集只会减少误报，不会漏报。"""
    result = autotoggle.decide(
        _row(note=[]),
        _eps(("2026-10-19", 1), ("2026-10-20", 2)),
        TODAY,
        keep_days=3,
        library_present={1},
        library_check=True,
    )
    assert result.reason == autotoggle.REASON_PENDING
    assert list(result.pending) == [2]


def test_library_present_ignored_for_best_version():
    """洗版问的是「洗到顶没有」，媒体库里有 1080 不等于洗完，所以不参与。"""
    row = _row(note=[1], best_version=1, episode_priority={"1": 80})
    result = autotoggle.decide(
        row,
        _eps(("2026-10-19", 1)),
        TODAY,
        best_keep_days_tv=90,
        best_keep_days_movie=90,
        best_mode=autotoggle.BEST_MODE_ALWAYS,
        library_present={1},
        library_check=True,
    )
    assert result.library_confirmed == 0
    assert result.reason == autotoggle.REASON_BEST_PENDING


def test_plan_passes_library_index_by_subscribe_id():
    """``library_index`` 的键是**订阅 ID**，不是 media_id。"""
    rows = [_row(id=11, note=[]), _row(id=12, note=[])]
    index = {("1234", 1): _eps(("2026-10-19", 1))}
    data = autotoggle.plan(
        rows, index, TODAY, keep_days=3, library_index={11: {1}}, library_check=True
    )
    by_id = {item["id"]: item for item in data["items"]}

    assert by_id[11]["action"] == autotoggle.ACTION_PAUSE
    assert by_id[11]["library_confirmed"] == 1
    assert by_id[11]["assumed"] is False
    assert by_id[12]["action"] == autotoggle.ACTION_KEEP
    assert by_id[12]["assumed"] is True


# ---------------------------------------------- 从流水手动补订阅（「加入订阅」按钮）


def _hist_record(**overrides):
    """一条「已加入」流水（宿主 ``_history_item`` 的形态）。"""
    record = {
        "decision": "added",
        "success": True,
        "source": "tmdb",
        "source_id": "603",
        "title": "手动补订阅测试",
        "media_type": "tv",
        "year": "2024",
        "season": 2,
        "media_source": "themoviedb",
        "media_id": "603",
        "confidence": "L1",
        "episode_group": "g:abc",
        "run_at": "2026-10-20 10:00:00",
    }
    record.update(overrides)
    return record


def _host_module(plugin):
    """插件**自己**加载出来的 ``core.host`` 模块。

    不能写成 ``import subscribecenter.core.host``：插件是按官方要求在
    ``app.plugins.subscribecenter`` 路径下加载的，那是**另一个**模块对象，
    patch 前者对插件无效（真机不报错、测试假绿）。
    """
    import importlib

    return importlib.import_module(type(plugin).__module__ + ".core.host")


class _HostBackend:
    """假的 ``HostSubscribeBackend``：记录问了什么、写了什么。"""
    def __init__(self, *, exists=False, subscribe_id=42):
        self.exists = exists
        self.subscribe_id = subscribe_id
        self.asked = []
        self.added = []

    async def subscription_exists(self, media_source, media_id, season=None):
        self.asked.append((media_source, media_id, season))
        return self.exists

    async def add(self, title, year, media_source, media_id, media_type, season=None, **kwargs):
        self.added.append(
            {
                "title": title,
                "year": year,
                "media_source": media_source,
                "media_id": media_id,
                "media_type": media_type,
                "season": season,
                "episode_group": kwargs.get("episode_group"),
            }
        )
        return self.subscribe_id, "已添加"


def test_history_subscribe_refuses_record_without_identity(plugin):
    """L4 待确认的记录没有确定性身份，不能凭空订一条。"""
    record = _hist_record(media_source="", media_id="", confidence="L4", decision="pending_review")
    plugin._history = lambda: [record]
    result = asyncio.run(plugin.subscribe_from_history(key="tmdb:手动补订阅测试:2024"))
    assert result.action == "skipped"
    assert "身份" in result.message


def test_history_subscribe_adds_and_writes_history(plugin, monkeypatch):
    """正常补订阅：走宿主 add、把 ``episode_group`` 原样带上、补一条流水。"""
    host_module = _host_module(plugin)

    backend = _HostBackend()
    monkeypatch.setattr(host_module, "HostSubscribeBackend", lambda: backend)
    record = _hist_record()
    written = []
    plugin._history = lambda: [record]
    plugin._append_history = lambda outcomes, *, run_at: written.extend(
        outcome.to_dict() for outcome in outcomes
    )
    plugin._subscription_state = lambda *a, **k: asyncio.sleep(0, result="")

    result = asyncio.run(plugin.subscribe_from_history(key="themoviedb:603"))

    assert result.action == "added"
    assert result.subscribe_id == 42
    assert backend.asked == [("themoviedb", "603", 2)]
    assert backend.added[0]["season"] == 2
    assert backend.added[0]["episode_group"] == "g:abc", "番剧必须靠它订回正确季"
    assert written and written[0]["decision"] == "added"
    assert written[0]["episode_group"] == "g:abc", "流水也要带上，否则下次再补还是错的"


def test_history_subscribe_does_not_touch_existing_subscribe(plugin, monkeypatch):
    """订阅还在 → 只回报状态，绝不改状态（用户可能就是想让它暂停着）。"""
    host_module = _host_module(plugin)

    backend = _HostBackend(exists=True)
    monkeypatch.setattr(host_module, "HostSubscribeBackend", lambda: backend)
    plugin._history = lambda: [_hist_record(state="S")]

    async def fake_state(*args, **kwargs):
        return "S"

    plugin._subscription_state = fake_state

    result = asyncio.run(plugin.subscribe_from_history(key="themoviedb:603"))

    assert result.action == "subscribed"
    assert result.state == "S"
    assert "已暂停" in result.message
    assert backend.added == [], "已存在就不该再写一条"


# ------------------------------------------------- 媒体库探针：预算 / 候选筛选


def _lib_row(**overrides):
    """探针用的订阅行（ORM 形态，插件里全是 ``getattr`` 取字段）。"""
    row = SimpleNamespace(
        id=1,
        name="探针剧",
        type="电视剧",
        media_source="themoviedb",
        media_id="900",
        season=1,
        state="R",
        start_episode=1,
        total_episode=12,
        lack_episode=12,
        note=[],
        episode_priority=None,
        best_version=0,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _now_text(plugin):
    """当前时区的 ISO 时间文本（构造「新鲜的」探针缓存用）。"""
    from subscribecenter.core.window import local_now_text

    return local_now_text(plugin._tz())


# ------------------------------------------------------------------ 后台执行
# 真机事故：预览里同步跑探针，200 条串行要好几分钟，请求被网关 502 掐断。
# 现在预览永远 probe=False，真正的核对只在后台线程里做。


def test_apply_starts_background_thread(plugin):
    """「立即执行」只挂线程就返回，绝不在请求里同步跑完。"""
    calls = []
    plugin._bridge = SimpleNamespace(busy=False, run=lambda *a, **k: None)
    plugin._auto_toggle_background = lambda: calls.append(1)
    plugin._auto_toggle_state = lambda: {}

    result = asyncio.run(plugin.auto_toggle_apply())
    for _ in range(50):
        if calls:
            break
        time.sleep(0.02)

    assert result["started"] is True
    assert result["running"] is True
    assert calls == [1], "后台线程必须真的跑起来"


def test_apply_refuses_while_running(plugin):
    """上一轮还在跑（牌子未过期）→ 直接拒绝，不排队。"""
    plugin._auto_toggle_state = lambda: {
        "last_run": {"running": True, "started_ts": time.time(), "started_at": "2026-10-21 09:00:00"}
    }
    plugin._bridge = SimpleNamespace(busy=False, run=lambda *a, **k: None)

    try:
        asyncio.run(plugin.auto_toggle_apply())
    except RuntimeError as err:
        assert "还在后台跑" in str(err)
    else:  # pragma: no cover - 没抛异常就是错
        raise AssertionError("应该拒绝重复执行")


def test_stale_running_flag_expires(plugin):
    """进程被杀留下的「正在跑」牌子，半小时后要自动作废。"""
    plugin._auto_toggle_state = lambda: {
        "last_run": {"running": True, "started_ts": time.time() - 3600}
    }
    assert plugin._auto_toggle_running()["running"] is False


def test_apply_refuses_when_discovery_busy(plugin):
    """发现流水在跑时不能同时改订阅表。"""
    plugin._auto_toggle_state = lambda: {}
    plugin._bridge = SimpleNamespace(busy=True, run=lambda *a, **k: None)

    try:
        asyncio.run(plugin.auto_toggle_apply())
    except RuntimeError as err:
        assert "发现任务" in str(err)
    else:  # pragma: no cover
        raise AssertionError("发现任务在跑时应该拒绝")


# ------------------------------------------- 1.17.4 下载记录 + 缓存保质期

def test_missing_from_no_exists_ignores_key_name():
    """宿主返回的键名它自己拼，我们不猜 —— 遍历取值（1.17.4 真机 70 条全空的原因）。"""
    from types import SimpleNamespace

    parse = autotoggle.missing_from_no_exists

    # 键是 tmdb:900 也好、themoviedb:900 也好、随便什么，都能取到
    for key in ("tmdb:900", "themoviedb:900", "900", "随便"):
        payload = {key: {1: SimpleNamespace(episodes=[4, 5])}}
        assert parse(payload, 1) == {4, 5}

    # 季号是字符串也要认
    assert parse({"x": {"1": SimpleNamespace(episodes=[7])}}, 1) == {7}
    # 这一季什么都不缺
    assert parse({"x": {1: SimpleNamespace(episodes=[])}}, 1) == set()
    # 结构不认识 / 空返回 = 问不出结论
    assert parse({}, 1) is None
    assert parse(None, 1) is None
    assert parse({"x": {2: SimpleNamespace(episodes=[1])}}, 1) is None
    assert parse({"x": "不是字典"}, 1) is None


def test_download_record_never_counts_as_imported():
    """朱色假面场景：第 4 集刚下完没导入，note 里有 4，但库里只有 1~3。

    以前把 note + 下载记录并进「已入库」→ 判成「已播 4 集全部入库」直接暂停。
    """
    row = _row(note=[4])
    result = autotoggle.decide(
        row,
        _eps(("2026-10-17", 1), ("2026-10-18", 2), ("2026-10-19", 3), ("2026-10-20", 4)),
        TODAY,
        keep_days=30,
        library_present={1, 2, 3},
        library_check=True,
    )

    assert result.reason == autotoggle.REASON_PENDING
    assert list(result.pending) == [4]
    assert result.action == autotoggle.ACTION_KEEP
    assert result.library_confirmed == 3


def test_all_done_needs_library_confirmation():
    """四集都在库里了才算「全部入库」。"""
    row = _row(note=[4])
    result = autotoggle.decide(
        row,
        _eps(("2026-10-17", 1), ("2026-10-18", 2), ("2026-10-19", 3), ("2026-10-20", 4)),
        TODAY,
        keep_days=30,
        library_present={1, 2, 3, 4},
        library_check=True,
    )

    assert result.reason == autotoggle.REASON_ALL_DONE
    assert result.action == autotoggle.ACTION_PAUSE


def test_library_unknown_does_nothing():
    """还没核对到 → 什么都不动：既不暂停也不恢复。"""
    running = autotoggle.decide(
        _row(state="R"),
        _eps(("2026-10-01", 1)),
        TODAY,
        keep_days=3,
        library_present=None,
        library_check=True,
    )
    assert running.reason == autotoggle.REASON_LIBRARY_UNKNOWN
    assert running.action == autotoggle.ACTION_KEEP
    assert running.target == autotoggle.STATE_RUN

    paused = autotoggle.decide(
        _row(state="S"),
        _eps(("2026-10-01", 1)),
        TODAY,
        keep_days=3,
        owned={7: {"state": "S"}},
        library_present=None,
        library_check=True,
    )
    assert paused.action == autotoggle.ACTION_KEEP
    assert paused.target == autotoggle.STATE_PAUSED


# --------------------------------------------------------------------- 集数缺口（订阅中但缺几集）


def test_in_window_gaps_basic():
    """已播但没入库、还在窗口内的集 → 返回 (播出日, 集号, 还剩几天)。"""
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=5),
        _eps(("2026-10-19", 1), ("2026-10-18", 2), ("2026-10-25", 3)),
        TODAY,
        keep_days=3,
        confirmed=set(),  # 实探：库一集都没有 → 这些都是缺口
    )
    # TODAY=2026-10-20，keep_days=3 → 只收 10-17..10-20 已播且未入库的
    # 10-19 缺: gap=1 → days_left=3-1=2；10-18 缺: gap=2 → days_left=1
    # 10-25 是未来集，不算缺口
    assert gaps == [
        ("2026-10-18", 2, 1),
        ("2026-10-19", 1, 2),
    ]


def test_in_window_gaps_excludes_downloaded():
    """实探已入库的集不算缺口，未入库的仍算。"""
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=5, note=[1]),
        _eps(("2026-10-19", 1), ("2026-10-18", 2)),
        TODAY,
        keep_days=3,
        confirmed={1},  # 实探确认第 1 集在库 → 不报缺；第 2 集缺
    )
    assert gaps == [("2026-10-18", 2, 1)]


def test_in_window_gaps_no_probe_evidence_reports_nothing():
    """没有实探证据（confirmed=None）→ 一律不报缺（宁可漏报不误报）。"""
    # note=[1] 即使标记了下过第 1 集，没实探证据也不该用它兜底报缺口
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=5, note=[1]),
        _eps(("2026-10-19", 1), ("2026-10-18", 2)),
        TODAY,
        keep_days=3,
    )
    assert gaps == []


def test_in_window_gaps_confirmed_only():
    """传了 confirmed（实探）就只认实探，note 不再算入库 → 都显示为缺口。"""
    row = _row(total_episode=5, note=[1])
    # 实探只确认了一个空集（set()）：第 1 集即使有 note 也应重新算缺口
    gaps = autotoggle.in_window_gaps(
        row,
        _eps(("2026-10-19", 1), ("2026-10-18", 2)),
        TODAY,
        keep_days=3,
        confirmed=set(),
    )
    assert gaps == [
        ("2026-10-18", 2, 1),
        ("2026-10-19", 1, 2),
    ]


def test_in_window_gaps_future_air_date_not_counted():
    """播出日在今天之后的，不是缺口（还没到播出时间）。"""
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=5),
        _eps(("2026-10-21", 1)),
        TODAY,
        keep_days=3,
    )
    assert gaps == []


def test_in_window_gaps_today_listed_when_old_gap_exists():
    """有旧缺口时，今天（TODAY）播的集也一并列出（直观）。"""
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=5),
        _eps(("2026-10-19", 1), ("2026-10-20", 2)),  # 昨天缺 1 + 今天播 2
        TODAY,
        keep_days=3,
        confirmed=set(),
    )
    # 旧缺口 10-19/1（days_left=3-1=2）→ 今天 10-20/2 也一并列出（days_left=3-0=3）
    assert gaps == [
        ("2026-10-19", 1, 2),
        ("2026-10-20", 2, 3),
    ]


def test_in_window_gaps_today_only_without_old_gap_not_listed():
    """只有今天第一次播、没有旧缺口 → 整部不列（今天才播，还没到补搜）。"""
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=5),
        _eps(("2026-10-20", 1)),  # 只有今天这一集
        TODAY,
        keep_days=3,
        confirmed=set(),
    )
    assert gaps == []


def test_in_window_gaps_before_start_episode_ignored():
    """早于 start_episode 的不算缺口（不存在要补它）。"""
    gaps = autotoggle.in_window_gaps(
        _row(total_episode=12, start_episode=3),
        _eps(("2026-10-19", 2), ("2026-10-18", 3)),
        TODAY,
        keep_days=3,
        start_episode=3,
        confirmed=set(),  # 实探：库一集都没有 → 缺口按缺席逐个算
    )
    assert gaps == [("2026-10-18", 3, 1)]


def test_library_present_from_lack_prefix():
    """缺 4 集 → 前 8 集视为已入库（宿主顺序追更的假设）。"""
    row = _lib_row(total_episode=12, lack_episode=4, start_episode=1)
    assert autotoggle.library_present_from_lack(row) == {1, 2, 3, 4, 5, 6, 7, 8}


def test_library_present_from_lack_respects_start_episode():
    """从第 5 集开始追：目标范围 5..12 共 8 集，缺 4 集 → 5,6,7,8。"""
    row = _lib_row(total_episode=12, lack_episode=4, start_episode=5)
    assert autotoggle.library_present_from_lack(row) == {5, 6, 7, 8}


def test_library_present_from_lack_missing_total_returns_none():
    assert autotoggle.library_present_from_lack(_lib_row(total_episode=0)) is None


def test_library_present_from_lack_missing_lack_returns_none():
    assert autotoggle.library_present_from_lack(_lib_row(lack_episode=None)) is None


def test_library_present_from_lack_full_lack_means_empty():
    """新建订阅宿主会直接把缺集置成总集数 —— 此时当作一集都没有。"""
    row = _lib_row(total_episode=12, lack_episode=12)
    assert autotoggle.library_present_from_lack(row) == set()


def test_library_present_from_lack_never_overshoots_total():
    row = _lib_row(total_episode=12, lack_episode=99)
    assert autotoggle.library_present_from_lack(row) == set()


def test_library_index_reads_host_lack_episode(plugin):
    """索引来自 lack_episode：电影与拿不到数字的不进索引。"""
    rows = [
        _lib_row(id=1, lack_episode=10),
        _lib_row(id=2, lack_episode=12),
        _lib_row(id=3, type="电影"),
        _lib_row(id=4, lack_episode=None),
    ]
    index, stats = asyncio.run(plugin._library_present_index(rows))
    assert index == {1: {1, 2}, 2: set()}
    assert stats["mode"] == "mp"
    assert stats["known"] == 2
    assert stats["unknown"] == 1, "电影不算；缺集数未知的算待核对"


def test_library_index_includes_best_version(plugin):
    """洗版订阅**必须**进索引（1.18.3 修的真机 bug）。

    早期这里把 ``best_version=1`` 的订阅排除掉，理由是「洗版问的是洗到顶没有」。
    可 ``decide`` 在播出期还要判「这一集入库了没有」；不在索引里就永远拿不到
    ``library_present`` → 一律 ``library_unknown`` 保持不动 → 自动启停对全部
    洗版订阅失效。真机：尚公主第 25 集下完入库，判定仍是「保持不动」。
    """
    rows = [_lib_row(id=1, best_version=1)]
    index, stats = asyncio.run(plugin._library_present_index(rows))
    assert index == {1: set()}, "缺 12 集 → 一集都没入库，但必须出现在索引里"
    assert stats["known"] == 1
    assert stats["unknown"] == 0


def test_library_index_best_version_uses_host_lack_episode(plugin):
    """洗版订阅的入库判断同样读宿主 ``lack_episode``（它按「有没有下到任一版本」算）。"""
    rows = [_lib_row(id=5, best_version=1, lack_episode=8)]
    index, _ = asyncio.run(plugin._library_present_index(rows))
    # total=12, lack=8 → 前 4 集已在库
    assert index == {5: {1, 2, 3, 4}}


def _capture_messages(plugin):
    """把 ``post_message`` 换成记录器，返回收到的消息列表。"""
    sent = []

    def fake_post_message(**kwargs):
        sent.append(kwargs)

    plugin.post_message = fake_post_message
    return sent


def test_notify_auto_toggle_sends_one_card_per_change(plugin):
    """一部一条卡片：标题带剧名+季+原因，带海报，链接到订阅页。"""
    sent = _capture_messages(plugin)
    plugin._notify_auto_toggle(
        {
            "changed": [
                {
                    "id": 38,
                    "name": "朱色假面",
                    "season": 1,
                    "action": "pause",
                    "reason_label": "已播剧集全部入库",
                    "detail": "已播 4 集全部入库",
                    "poster": "https://image.tmdb.org/t/p/w500/a.jpg",
                    "kind": "tv",
                },
                {
                    "id": 198,
                    "name": "神探之痕迹",
                    "season": 0,
                    "action": "resume",
                    "reason_label": "缺集在窗口内",
                    "detail": "下一集 2026-11-07",
                    "poster": "",
                    "kind": "movie",
                },
            ],
            "failed": [],
        }
    )
    assert len(sent) == 2, "两条改动就发两条，不再合成一条"
    first, second = sent
    assert first["title"] == "朱色假面 S1 已播剧集全部入库"
    assert "处理：已暂停订阅" in first["text"]
    assert "说明：已播 4 集全部入库" in first["text"]
    assert first["image"] == "https://image.tmdb.org/t/p/w500/a.jpg"
    assert first["link"] == "#/subscribe/tv?tab=mysub"
    assert second["title"] == "神探之痕迹 缺集在窗口内", "电影没有季号"
    assert "处理：已恢复订阅" in second["text"]
    assert second["image"] is None, "没有海报就别传空串"
    assert second["link"] == "#/subscribe/movie?tab=mysub"


def test_notify_auto_toggle_reports_failures_separately(plugin):
    """失败单独发一条，别混在卡片里让人以为改成功了。"""
    sent = _capture_messages(plugin)
    plugin._notify_auto_toggle(
        {
            "changed": [],
            "failed": [
                {"id": 7, "name": "某剧", "error": "宿主未找到该订阅（可能已被删除）"},
            ],
        }
    )
    assert len(sent) == 1
    assert "有失败" in sent[0]["title"]
    assert "某剧" in sent[0]["text"]
    assert "宿主未找到该订阅" in sent[0]["text"]


def test_notify_auto_toggle_silent_without_changes(plugin):
    """没改动、没失败就一条都不发。"""
    sent = _capture_messages(plugin)
    plugin._notify_auto_toggle({"changed": [], "failed": []})
    assert sent == []


# --------------------------------------------------------------------- 集数修正
#
# 背景：宿主 ``compute_lack_episode`` 对洗版订阅只看 ``note`` ∪
# ``episode_priority``（订阅自己下过的集），媒体库里早就存在的老集不记账，
# 页面就显示「明明有 25 集只写 2 集」。1.18.6 的修正流程 = 每轮自动启停
# 末尾挑几条洗版剧集订阅实探媒体库，把「库有 ∧ 已播 ∧ 在目标范围 ∧
# note 没有」的集号交给宿主 ``backfill_existing_episodes`` 补记。
# 下面锁住纯函数层与接线层的行为（探库/写库两个方法在单测里替换掉）。


def _bf_row(**overrides):
    """默认是一条「总 60 集、账上只记了 26/27」的洗版剧集订阅（对标真机 id=116）。"""
    row = {
        "id": 116,
        "name": "伟大的长征",
        "best_version": 1,
        "best_version_full": 0,
        "total_episode": 60,
        "start_episode": 1,
        "lack_episode": 34,
        "note": [26, 27],
        "last_update": "2026-11-01 10:00:00",
    }
    row.update(overrides)
    return _row(**row)


def test_backfill_candidates_picks_best_tv_only():
    """候选只收「剧集 + 洗版 + 总集数已知」，普通订阅与非剧集一律不收。"""
    rows = [
        _bf_row(id=1),
        _bf_row(id=2, best_version=0),
        _bf_row(id=3, type="电影"),
        _bf_row(id=4, total_episode=0),
    ]
    picked = autotoggle.backfill_candidates(
        rows, today_text="2026-11-06", cooldown_at={}
    )
    assert [item["id"] for item in picked] == [1]
    assert picked[0]["media_id"] == "1234"


def test_backfill_candidates_cooldown_and_ordering():
    """7 天内探过的跳过；没探过的里 last_update 最旧优先；limit 截断。"""
    rows = [
        _bf_row(id=1, last_update="2026-11-05 08:00:00"),
        _bf_row(id=2, last_update="2026-10-01 08:00:00"),
        _bf_row(id=3, last_update="2026-11-03 08:00:00"),
    ]
    cooldown = {"3": "2026-11-02"}  # 距 11-06 才 4 天 → 冷却内
    picked = autotoggle.backfill_candidates(
        rows, today_text="2026-11-06", cooldown_at=cooldown, limit=5
    )
    assert [item["id"] for item in picked] == [2, 1], "旧账优先"

    limited = autotoggle.backfill_candidates(
        rows, today_text="2026-11-06", cooldown_at={}, limit=1
    )
    assert [item["id"] for item in limited] == [2]


def test_backfill_episodes_four_layer_intersection():
    """库有 ∧ 已播 ∧ 目标范围 ∧ note 没有 —— 四层交集，一层都不多写。"""
    row = _bf_row()
    air = [(f"2026-10-{n:02d}", n) for n in range(1, 28)]
    air.append(("2026-12-05", 28))  # 还没播的一集
    # 库里有 1..27 + 61（界外）；今天 2026-11-06：28 未播、61 越界
    episodes = autotoggle.backfill_episodes(
        row, air, today_text="2026-11-06", present=list(range(1, 28)) + [61]
    )
    assert episodes == list(range(1, 26)), "26/27 已在 note；28 未播不补；61 越界不补"


def test_backfill_episodes_refuses_without_signal():
    """探不到（None）、库里空的、播出表缺失、非洗版目标 —— 一律返回空不写账。"""
    row = _bf_row()
    air = [("2026-10-01", 1), ("2026-10-08", 2)]
    assert autotoggle.backfill_episodes(row, air, today_text="2026-11-06", present=None) == []
    assert autotoggle.backfill_episodes(row, air, today_text="2026-11-06", present=[]) == []
    assert autotoggle.backfill_episodes(row, None, today_text="2026-11-06", present=[1]) == []
    assert autotoggle.backfill_episodes(
        _bf_row(total_episode=0), air, today_text="2026-11-06", present=[1]
    ) == []


def test_backfill_wiring_cooldown_and_counts(plugin, monkeypatch):
    """接线：探完无论结果都记探测日；补账成功才计数；探库失败也记日防天天重探。"""
    mod = sys.modules["app.plugins.subscribecenter"]
    monkeypatch.setattr(
        mod,
        "logger",
        types.SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None),
        raising=False,
    )

    probe_calls = []
    applied = {}

    async def fake_rows():
        return [SimpleNamespace(**_bf_row(id=116)), SimpleNamespace(**_bf_row(id=117, last_update="2026-11-02 00:00:00"))]

    async def fake_probe(row):
        probe_calls.append(int(row.id))
        if int(row.id) == 117:
            raise RuntimeError("媒体服务器没接")
        return list(range(1, 28))

    async def fake_apply(sid, episodes):
        applied[sid] = list(episodes)
        return True

    plugin._auto_toggle_rows = fake_rows
    plugin._backfill_probe_library = fake_probe
    plugin._backfill_apply_note = fake_apply
    plugin.__dict__["_season_cache"] = {
        ("1234", 1): (0.0, [("2026-10-01", n) for n in range(1, 28)], {"total": 60})
    }

    state = {}
    cfg = {"backfill_notes": True}
    backfilled, failed = asyncio.run(
        plugin._backfill_note_episodes(cfg, state, {"today": "2026-11-06"})
    )
    assert backfilled == 1
    assert failed == 1, "117 探库抛异常 → 计失败"
    assert applied == {116: list(range(1, 26))}, "26/27 已在 note，补的是 1..25"
    assert set(state["backfill_at"]) == {"116", "117"}, "探失败的也记日，防天天重探"

    #: 第二轮：都在 7 天冷却内 → 一条都不探
    probe_calls.clear()
    backfilled2, failed2 = asyncio.run(
        plugin._backfill_note_episodes(cfg, state, {"today": "2026-11-09"})
    )
    assert (backfilled2, failed2) == (0, 0)
    assert probe_calls == []


def test_backfill_disabled_switch_skips_everything(plugin):
    """配置关着 → 一个查询都不发。"""
    called = []

    async def fake_rows():
        called.append(1)
        return []

    plugin._auto_toggle_rows = fake_rows
    out = asyncio.run(
        plugin._backfill_note_episodes({"backfill_notes": False}, {}, {"today": "2026-11-06"})
    )
    assert out == (0, 0)
    assert not called


def test_run_inner_surfaces_backfill_counts(plugin, monkeypatch):
    """整轮跑完：backfilled/backfill_failed 进 last_run 与 result，但绝不进通知。"""
    plugin._auto_toggle_state = lambda: {}

    async def fake_plan(**_kwargs):
        return _plan_stub([{"id": 1, "name": "A", "state": "R", "target": "R", "action": "skip", "reason": "pending"}])

    async def fake_apply(changes):
        return [], []

    async def fake_backfill(cfg, state, planned):
        return 3, 1

    plugin.auto_toggle_plan = fake_plan
    plugin._apply_auto_toggle = fake_apply
    plugin._backfill_note_episodes = fake_backfill
    sent = _capture_messages(plugin)
    result = asyncio.run(plugin.auto_toggle_run(reason="cron"))

    assert result["backfilled"] == 3
    assert result["backfill_failed"] == 1
    assert result["last_run"]["backfilled"] == 3
    saved = plugin.get_data("auto_toggle")
    assert saved["last_run"]["backfill_failed"] == 1
    assert sent == [], "集数修正保持静默，不发通知"

