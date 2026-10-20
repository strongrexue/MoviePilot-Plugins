"""按播出日自动启停订阅（纯逻辑，无宿主依赖）。

背景：宿主的「订阅刷新」按 ``cron`` 把**全部** ``R``/``P`` 订阅拉进匹配循环
（默认 spider 模式下约 32 次/天）。订阅数到两百条时，绝大多数条目当天并没有
新集，完全属于空转。本模块只回答一个问题：

    这条订阅**今天**有没有必要参与搜索？

判定依据是 TMDB 每季的 ``episodes[].air_date`` 与订阅自己的
``note``（宿主写进去的「已下载集号」清单）：

- 有已播未入库的集，且在 ``keep_days`` 窗口内 → 需要搜索（``R``）
- 有 ``lookahead_days`` 天内将要播出的集 → 需要搜索（``R``）
- 其余情况（已下全 / 首集还没播 / 缺集超过窗口）→ 不必搜索（``S``）

宿主状态语义（MoviePilot v3.1.6 已逐行核验，**与常见误传相反**）：

===========  ==========================================================
``R``        订阅中 —— 参与定时刷新与匹配
``P``        待定 —— **仍然会被搜索**（``get_states_for_search("R")``
             返回 ``"R,P"``），只是不允许「完成」
``S``        暂停 —— 被订阅刷新排除；手动补搜时仍可搜到
===========  ==========================================================

.. important::
   所以「暂停」只能写 ``S``，写 ``P`` 等于没暂停。另外**绝不能**把标记写进
   ``Subscribe.note`` —— 那是宿主自己的「已下载集号」清单，
   ``completion.py`` / ``priority.py`` 都靠它算进度，改写它会让集数统计错乱。
   本插件的接管标记存在自己的插件数据里（见 ``__init__.py``）。

.. note::
   本模块是**纯函数**：输入订阅行 + 播出索引 + 今天，输出计划，
   不碰数据库、不碰宿主、不打日志。所有副作用（写状态、落盘标记）由调用方做。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .calendar import MOVIE_KEY
from .window import parse_date

# --------------------------------------------------------------------- 状态常量

#: 宿主订阅状态：订阅中（参与搜索）
STATE_RUN = "R"
#: 宿主订阅状态：待定（**仍参与搜索**，本插件不碰）
STATE_PENDING = "P"
#: 宿主订阅状态：暂停（被订阅刷新排除）
STATE_PAUSED = "S"

#: 参与自动启停决策的订阅状态。
#:
#: 排除 ``N``（新建、还没有播出信息）与完成态（已移入订阅历史表）。
#: ``P`` 也取出来：不是要动它，而是要在预览里显示「这条宿主仍在搜索，本插件不碰」，
#: 否则用户会以为插件漏了它。
WRITABLE_STATES = (STATE_RUN, STATE_PENDING, STATE_PAUSED)

# --------------------------------------------------------------------- 动作

ACTION_PAUSE = "pause"
ACTION_RESUME = "resume"
ACTION_KEEP = "keep"
ACTION_SKIP = "skip"

#: 真正会写库的动作
WRITE_ACTIONS = (ACTION_PAUSE, ACTION_RESUME)

# --------------------------------------------------------------------- 原因码

#: 有已播未入库的集，且在窗口内
REASON_PENDING = "pending"
#: 有 lookahead 天内将要播出的集
REASON_UPCOMING = "upcoming"
#: 已播的集全部入库，且没有待播集
REASON_ALL_DONE = "all_done"
#: 缺集已超过 keep 窗口（PT 迟迟没有资源）
REASON_MISSING_OVERDUE = "missing_overdue"
#: 首集还没播出
REASON_PREMIERE = "premiere"
#: 拿不到播出表（TMDB 失败 / 该季无 air_date）
REASON_NO_SCHEDULE = "no_schedule"
#: 非剧集（电影 / 音乐），不归本模块管
REASON_MOVIE = "movie"
#: 没有可用的媒体 ID（非 TMDB 来源），查不到播出表
REASON_NO_ID = "no_media_id"
#: 状态是「待定」，尊重宿主语义不碰
REASON_PENDING_STATE = "pending_state"
#: 状态是「暂停」但不是本插件暂停的 → 视为用户手动暂停，永不自动恢复
REASON_USER_PAUSED = "user_paused"
#: 本插件暂停过，但状态已被改成别的 → 视为用户手动干预，放弃接管
REASON_MANUAL = "manual_changed"
#: 电影没有播出日，只在「全部恢复」时出现
REASON_RELEASE = "release"

#: 原因码 → 中文短说明（前端兜底展示用）
REASON_LABELS: Dict[str, str] = {
    REASON_PENDING: "今天有已播未入库的集",
    REASON_UPCOMING: "临近播出",
    REASON_ALL_DONE: "已播剧集全部入库",
    REASON_MISSING_OVERDUE: "缺集超过保留窗口",
    REASON_PREMIERE: "首集尚未播出",
    REASON_NO_SCHEDULE: "取不到播出表",
    REASON_MOVIE: "非剧集",
    REASON_NO_ID: "没有 TMDB ID",
    REASON_PENDING_STATE: "状态为待定，不干预",
    REASON_USER_PAUSED: "用户手动暂停，不接管",
    REASON_MANUAL: "状态被手动改动，放弃接管",
    REASON_RELEASE: "手动全部恢复",
}


# --------------------------------------------------------------------- 数据模型

def _get(obj: Any, name: str, default: Any = None) -> Any:
    """兼容 dict 与 ORM 对象地取字段（与插件里的 ``_field`` 同口径）。"""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _text(value: Any) -> str:
    """转成去空白的字符串；``None`` → 空串。"""
    return str(value if value is not None else "").strip()


def _int(value: Any, default: int = 0) -> int:
    """宽松转整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


#: 宿主 ``MediaType`` 的取值（``app/schemas/types.py``）—— 是**中文**，不是 ``tv``
_TV_TYPES = frozenset({"电视剧", "剧集", "连续剧"})
_MOVIE_TYPES = frozenset({"电影"})
_MUSIC_TYPES = frozenset({"音乐"})


def media_kind(row: Any) -> str:
    """把订阅的 ``type`` 归一成 ``"tv"`` / ``"movie"`` / ``"music"`` / ``""``。

    .. important::
       宿主 ``Subscribe.type`` 是普通字符串列，存的是 ``MediaType`` 的**值**，
       而 ``MediaType.TV = "电视剧"``（不是 ``"tv"``）。1.13.0 直接拿 ``"tv"``
       比较，结果两百条订阅全被判成「非剧集」，预览里一条都不动 ——
       这就是那次翻车的根因。

    拿不准的一律返回 ``""``（未知）：未知不等于电影，交给后面的
    「有没有播出表」去判断，别靠猜把用户的订阅排除掉。
    """
    raw = _get(row, "type")
    value = getattr(raw, "value", raw)  # 万一上游塞的是枚举成员
    text = _text(value)
    name = _text(getattr(raw, "name", "")).upper()
    lowered = text.lower()
    if name == "TV" or lowered == "tv" or text in _TV_TYPES:
        return "tv"
    if name == "MOVIE" or lowered in {"movie", "film"} or text in _MOVIE_TYPES:
        return "movie"
    if name == "MUSIC" or lowered == "music" or text in _MUSIC_TYPES:
        return "music"
    return ""


def _episode_pair(item: Any) -> Optional[Tuple[str, int]]:
    """把一条「播出索引」条目归一为 ``(YYYY-MM-DD, 集号)``。

    索引的标准形态是 ``(air_date, episode_number)`` 元组；这里同时接受
    dict（``{"air_date": ..., "episode_number": ...}``）与对象，
    方便单测直接塞 TMDB 原始结构。
    """
    if isinstance(item, (tuple, list)):
        if len(item) < 2:
            return None
        air, number = item[0], item[1]
    else:
        air = _get(item, "air_date")
        number = _get(item, "episode_number")
    day = parse_date(air)
    if day is None:
        return None
    return day.isoformat(), _int(number)


def episode_numbers(row: Any) -> set:
    """返回该订阅**已入库**的集号集合。

    三个来源按可靠性排序：

    1. ``note`` —— 宿主自己写的「已下载集号」清单，最准；
    2. ``episode_priority`` —— 洗版订阅不用 ``note``，靠「优先级 100 = 完成」
       的映射记录进度（见 ``policy.py`` 的 ``_get_best_version_completed_episodes``）；
    3. 兜底 —— ``note`` 为空但 ``lack_episode <= 0`` 且 ``total_episode > 0``：
       视为整季已下全（真机上「已完成」的订阅 note 会被清空）。

    .. warning::
       只读不写。任何情况下都不要往 ``note`` 里写本插件的标记。
    """
    note = _get(row, "note")
    if isinstance(note, (list, tuple, set)):
        numbers = {_int(item, -1) for item in note}
        numbers.discard(-1)
        if numbers:
            return numbers

    priority = _get(row, "episode_priority")
    if isinstance(priority, Mapping) and priority:
        done = {
            _int(key, -1)
            for key, value in priority.items()
            if _int(value) >= 100
        }
        done.discard(-1)
        if done:
            return done

    total = _int(_get(row, "total_episode"))
    lack = _int(_get(row, "lack_episode"))
    if total > 0 and lack <= 0:
        return set(range(1, total + 1))
    return set()


@dataclass(frozen=True)
class Decision:
    """一条订阅的处置结论。"""

    subscribe_id: int
    name: str
    season: int
    #: 决策前的订阅状态
    state: str
    #: 决策后应当是的状态（``R`` / ``S``）；跳过时与 ``state`` 相同
    target: str
    action: str
    reason: str
    #: 中文说明（给界面看，不参与逻辑）
    detail: str
    #: 已播未入库的集号
    pending: Tuple[int, ...] = ()
    #: 下一集播出日
    next_air: str = ""
    #: 已播的最新一集播出日
    last_air: str = ""
    #: 已播集数 / 已入库集数（用于界面）
    aired: int = 0
    downloaded: int = 0
    #: 该订阅当前是否由本插件暂停（接管中）
    owned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转成可直接 JSON 化的字典。"""
        return {
            "id": self.subscribe_id,
            "name": self.name,
            "season": self.season,
            "state": self.state,
            "target": self.target,
            "action": self.action,
            "reason": self.reason,
            "reason_label": REASON_LABELS.get(self.reason, self.reason),
            "detail": self.detail,
            "pending": list(self.pending),
            "next_air": self.next_air,
            "last_air": self.last_air,
            "aired": self.aired,
            "downloaded": self.downloaded,
            "owned": self.owned,
        }


def _decision(
    row: Any,
    *,
    state: str,
    target: str,
    action: str,
    reason: str,
    detail: str,
    owned: bool = False,
    pending: Sequence[int] = (),
    next_air: str = "",
    last_air: str = "",
    aired: int = 0,
    downloaded: int = 0,
) -> Decision:
    """构造一条结论（统一走这里，避免字段漏填）。"""
    return Decision(
        subscribe_id=_int(_get(row, "id")),
        name=_text(_get(row, "name")),
        season=_int(_get(row, "season")),
        state=state,
        target=target,
        action=action,
        reason=reason,
        detail=detail,
        pending=tuple(pending),
        next_air=next_air,
        last_air=last_air,
        aired=aired,
        downloaded=downloaded,
        owned=owned,
    )


def _describe(reason: str, **values: Any) -> str:
    """生成一句中文说明（界面展示用）。"""
    if reason == REASON_PENDING:
        return "第 {ep} 集 {air} 未入库（已播 {days} 天）".format(**values)
    if reason == REASON_UPCOMING:
        return "第 {ep} 集 {air} 播出".format(**values)
    if reason == REASON_ALL_DONE:
        return "已播 {aired} 集全部入库".format(**values)
    if reason == REASON_MISSING_OVERDUE:
        return "第 {ep} 集 {air} 未入库（超 {keep} 天窗口）".format(**values)
    if reason == REASON_PREMIERE:
        return "首集 {air} 才播出".format(**values)
    if reason == REASON_NO_SCHEDULE:
        return "取不到该季的播出表（TMDB 无返回），本轮不动"
    if reason == REASON_MOVIE:
        return "非剧集订阅（电影/音乐），不按播出日调度"
    if reason == REASON_NO_ID:
        return "没有可用的 TMDB ID，查不到播出表"
    if reason == REASON_PENDING_STATE:
        return "状态为「待定」，宿主仍会搜索它，本插件不干预"
    if reason == REASON_USER_PAUSED:
        return "当前是暂停且非本插件所暂停 → 视为用户手动暂停，不恢复"
    if reason == REASON_MANUAL:
        return "本插件暂停过，但状态已被改成 {state} → 放弃接管".format(**values)
    return REASON_LABELS.get(reason, reason)


def decide(
    row: Any,
    episodes: Optional[Iterable[Any]],
    today: date,
    *,
    lookahead_days: int = 0,
    keep_days: int = 3,
    owned: Optional[Mapping[Any, Any]] = None,
) -> Decision:
    """对**一条**订阅给出结论。

    :param row: 订阅行（ORM 对象或 dict）
    :param episodes: 该订阅所属季的播出索引：``[(air_date, episode_number), ...]``
    :param today: 插件时区下的「今天」
    :param lookahead_days: 提前几天开启（0 = 只在播出当天开启）
    :param keep_days: 已播未入库的集最多保留几天继续搜索
    :param owned: 本插件的接管表 ``{订阅 ID: {"state": 我们写入的状态, ...}}``；
        ``None`` 表示空表（预览时也传真实表，判定才一致）
    """
    owned = owned or {}
    subscribe_id = _int(_get(row, "id"))
    state = _text(_get(row, "state")).upper()
    own = owned.get(subscribe_id) or owned.get(str(subscribe_id)) or None
    is_owned = bool(own)

    def skip(reason: str, detail: str = "") -> Decision:
        return _decision(
            row,
            state=state,
            target=state,
            action=ACTION_SKIP,
            reason=reason,
            detail=detail or _describe(reason, state=state),
            owned=is_owned,
        )

    # ---- 1. 只看剧集；电影没有播出日，音乐更没有
    if media_kind(row) in ("movie", "music"):
        return skip(REASON_MOVIE)

    media_id = _text(_get(row, "media_id"))
    if not media_id.isdigit():
        return skip(REASON_NO_ID)

    # ---- 2. 状态与接管权
    if state == STATE_PENDING:
        # P 仍会被宿主搜索，改成 R 或 S 都会改变宿主语义之外的东西，不碰
        return skip(REASON_PENDING_STATE)
    if state not in (STATE_RUN, STATE_PAUSED):
        return skip(REASON_NO_SCHEDULE, f"未识别的订阅状态 {state!r}，本轮不动")
    if is_owned and state != _text(own.get("state") or STATE_PAUSED).upper():
        # 我们暂停过，但现在是别的状态 → 用户手动改回来了，放弃接管。
        # 不能「按规矩再暂停一次」：那会跟用户的手动操作来回打架。
        return skip(REASON_MANUAL)
    if state == STATE_PAUSED and not is_owned:
        return skip(REASON_USER_PAUSED)

    # ---- 3. 播出表
    air = [pair for pair in (_episode_pair(item) for item in (episodes or [])) if pair]
    if not air:
        return skip(REASON_NO_SCHEDULE)

    air.sort(key=lambda pair: (pair[0], pair[1]))
    today_text = today.isoformat()
    downloaded = episode_numbers(row)
    start_episode = _int(_get(row, "start_episode"), 1)

    aired = [(day, number) for day, number in air if day <= today_text]
    # 只看 start_episode 之后的集：订阅「从第 N 集开始」是用户的选择，
    # 把前面的集算成缺集会让它永远被判为「需要搜索」。
    pending = [
        (day, number)
        for day, number in aired
        if number >= start_episode and number not in downloaded
    ]
    horizon = today + timedelta(days=max(0, lookahead_days))
    upcoming = [
        (day, number)
        for day, number in air
        if today_text < day <= horizon.isoformat()
    ]
    next_air = next((day for day, _ in air if day > today_text), "")
    last_air = aired[-1][0] if aired else ""
    common = {
        "pending": [number for _, number in pending],
        "next_air": next_air,
        "last_air": last_air,
        "aired": len(aired),
        "downloaded": len(downloaded),
    }

    # ---- 4. 决策
    if pending:
        day, number = pending[-1]
        gap = (today - (parse_date(day) or today)).days
        if gap <= max(0, keep_days):
            target, reason = STATE_RUN, REASON_PENDING
            detail = _describe(REASON_PENDING, ep=number, air=day, days=gap)
        elif upcoming:
            day2, number2 = upcoming[0]
            target, reason = STATE_RUN, REASON_UPCOMING
            detail = _describe(REASON_UPCOMING, ep=number2, air=day2)
        else:
            target, reason = STATE_PAUSED, REASON_MISSING_OVERDUE
            detail = _describe(
                REASON_MISSING_OVERDUE, ep=number, air=day, keep=max(0, keep_days)
            )
    elif upcoming:
        day, number = upcoming[0]
        target, reason = STATE_RUN, REASON_UPCOMING
        detail = _describe(REASON_UPCOMING, ep=number, air=day)
    elif not aired:
        day, number = air[0]
        target, reason = STATE_PAUSED, REASON_PREMIERE
        detail = _describe(REASON_PREMIERE, air=day)
    else:
        target, reason = STATE_PAUSED, REASON_ALL_DONE
        detail = _describe(REASON_ALL_DONE, aired=len(aired))

    action = ACTION_KEEP
    if target == STATE_RUN and state != STATE_RUN:
        action = ACTION_RESUME
    elif target == STATE_PAUSED and state != STATE_PAUSED:
        action = ACTION_PAUSE

    return _decision(
        row,
        state=state,
        target=target,
        action=action,
        reason=reason,
        detail=detail,
        owned=is_owned,
        **common,
    )


#: 界面排序权重：先看会变动的，再看跳过的
_ACTION_RANK = {ACTION_RESUME: 0, ACTION_PAUSE: 1, ACTION_KEEP: 2, ACTION_SKIP: 3}


def plan(
    rows: Iterable[Any],
    episode_index: Mapping[Any, Any],
    today: date,
    *,
    lookahead_days: int = 0,
    keep_days: int = 3,
    owned: Optional[Mapping[Any, Any]] = None,
    max_changes: int = 0,
) -> Dict[str, Any]:
    """对全部订阅做一次决策，返回「计划」。

    索引键与插件日历一致：``(media_id, season)``，没有季号时是
    ``(media_id, "movie")``（见 ``core/calendar.py`` 的 ``MOVIE_KEY``）。

    :param max_changes: 单次改动上限（0 = 不限）。超出时**先保恢复、后保暂停**
        —— 少暂停几条只是多搜一次，漏恢复会让该搜的订阅一整天不搜。
    :return: ``{"today", "items", "changes", "paused", "resumed", "kept",
        "skipped", "reasons", "truncated"}``
    """
    decisions: List[Decision] = []
    for row in rows:
        media_id = _text(_get(row, "media_id"))
        season = _int(_get(row, "season"))
        #: 剧集组订阅在索引里登记的是 (media_id, season)，电影登记的是
        #: (media_id, MOVIE_KEY)；这里两种键都试一遍，取不到才算「无播出表」。
        episodes = episode_index.get((media_id, season if season > 0 else MOVIE_KEY))
        if episodes is None:
            episodes = episode_index.get((media_id, season))
        decisions.append(
            decide(
                row,
                episodes,
                today,
                lookahead_days=lookahead_days,
                keep_days=keep_days,
                owned=owned,
            )
        )

    decisions.sort(key=lambda item: (_ACTION_RANK.get(item.action, 9), item.name))

    changes = [item for item in decisions if item.action in WRITE_ACTIONS]
    truncated = False
    if max_changes and len(changes) > max_changes:
        # 恢复优先：pauses 排在后面被截掉
        changes.sort(key=lambda item: (item.action != ACTION_RESUME, item.name))
        changes = changes[:max_changes]
        truncated = True

    reasons: Dict[str, int] = {}
    for item in decisions:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1

    keep_ids = {item.subscribe_id for item in changes}
    return {
        "today": today.isoformat(),
        "items": [item.to_dict() for item in decisions],
        # changes 只保留真正会写库的，且与截断后的集合一致
        "changes": [item.to_dict() for item in changes if item.subscribe_id in keep_ids],
        "paused": len([item for item in changes if item.action == ACTION_PAUSE]),
        "resumed": len([item for item in changes if item.action == ACTION_RESUME]),
        "kept": len([item for item in decisions if item.action == ACTION_KEEP]),
        "skipped": len([item for item in decisions if item.action == ACTION_SKIP]),
        "planned": len(changes),
        "reasons": reasons,
        "truncated": truncated,
    }


def next_owned(
    owned: Optional[Mapping[Any, Any]],
    plan_data: Mapping[str, Any],
    *,
    today_text: str,
    applied_ids: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """算出执行后的接管表。

    规则：

    - 本次暂停成功的 → 记入接管表（``state=S``）
    - 本次恢复成功的 → 移出接管表（不再是我们暂停的）
    - 状态被手动改动（``manual_changed``）→ 移出接管表（放弃接管）
    - 已经不在订阅表里的 ID → 移出（订阅被删了）

    :param applied_ids: 真正写成功的订阅 ID；``None`` 表示「计划里的全部」
    """
    result: Dict[str, Any] = {
        str(key): dict(value)
        for key, value in (owned or {}).items()
        if isinstance(value, Mapping)
    }
    applied = None if applied_ids is None else {int(item) for item in applied_ids}
    present = {int(item["id"]) for item in plan_data.get("items") or [] if item.get("id")}

    for key in list(result):
        if _int(key, -1) not in present:
            result.pop(key, None)

    for item in plan_data.get("items") or []:
        sid = _int(item.get("id"))
        action = item.get("action")
        if action == ACTION_SKIP and item.get("reason") == REASON_MANUAL:
            result.pop(str(sid), None)
            continue
        if applied is not None and sid not in applied:
            continue
        if action == ACTION_PAUSE:
            result[str(sid)] = {
                "state": STATE_PAUSED,
                "reason": item.get("reason"),
                "since": today_text,
                "name": item.get("name"),
            }
        elif action == ACTION_RESUME:
            result.pop(str(sid), None)
    return result


__all__ = [
    "ACTION_KEEP",
    "ACTION_PAUSE",
    "ACTION_RESUME",
    "ACTION_SKIP",
    "Decision",
    "REASON_ALL_DONE",
    "REASON_LABELS",
    "REASON_MANUAL",
    "REASON_MISSING_OVERDUE",
    "REASON_MOVIE",
    "REASON_NO_ID",
    "REASON_NO_SCHEDULE",
    "REASON_PENDING",
    "REASON_PENDING_STATE",
    "REASON_PREMIERE",
    "REASON_RELEASE",
    "REASON_UPCOMING",
    "REASON_USER_PAUSED",
    "STATE_PAUSED",
    "STATE_PENDING",
    "STATE_RUN",
    "WRITABLE_STATES",
    "WRITE_ACTIONS",
    "decide",
    "episode_numbers",
    "media_kind",
    "next_owned",
    "plan",
]
