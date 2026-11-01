"""手动回搜（1.13.38）：手机上说一句「胖虎 片名」就能查库挑版本。

为什么做成聊天交互而不是网页：这个功能本来就是给**手机上**用的——看到一部片子
想补，掏出手机说一句就行，不需要打开 MP 网页。所以：

1. 触发：``胖虎 凡人修仙传``（前缀「胖虎」是固定触发语，避免和正常聊天混淆）；
2. 后台按片名检索消息缓存 → 按「季-集」分组，每组只留画质最优的那条；
3. 每条再对一遍洗版基线（已推送 / 下载历史 / 媒体库），标出「可升级 / 持平 / 无基线」；
4. 回一条**可点选的**消息：Telegram 渲染成 inline keyboard，微信等不支持按钮的
   渠道自动降级成「回复编号」，翻页用 ``p`` / ``n``；
5. 用户选中哪条，就只把那一条的链接入推送队列（走和监控完全相同的转存链路）。

设计边界：
- 只读缓存，不主动去 TG 拉历史；缓存里没有就直说没有；
- 不改任何既有规则，也不写命中流水（这是用户主动操作，不是规则判定）；
- 请求状态存插件数据，24 小时过期、最多留 5 条，避免长期占用。
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger

from ..services import quality as quality_service
from ..services import wash_gate

# 触发语：必须以它开头，后面跟片名
TRIGGER = "胖虎"

# 插件命令动作名（宿主 get_command() → PluginAction 事件里的 action）
ACTION_COMMAND = "manual_search"

# 请求状态（插件数据 KV）
_STATE_KEY = "manual_search_state"
_MAX_REQUESTS = 5
_TTL_SECONDS = 24 * 3600

# 一页列多少条（与宿主交互通知同款：TG 一屏 8 条够看）
_PAGE_SIZE = 8

# 纯文本渠道（微信等没有按钮）一页列 6 条：8 条实测会被客户端吞掉最后 3 行
# （用户 m24675 真机验证），6 条安全
_PAGE_SIZE_PLAIN = 6

# 每页按钮一行放几个数字（TG 上限 4）
_BUTTONS_PER_ROW = 4

# 取海报最多等几秒（超时先发纯文本，后台线程自己跑完丢弃）
_POSTER_TIMEOUT = 8.0

# 状态标记
MARK_UPGRADE = "↑ 可升级"
MARK_FLAT = "= 持平"
MARK_LOWER = "↓ 更低"
MARK_UNKNOWN = "? 无基线"

# ``/胖虎`` 命令里表示「选第几条 / 翻页 / 取消」的参数（不是片名）
_COMMAND_RE = re.compile(r"^(?:[0-9]{1,2}|n|p|上一页|下一页|取消|x)$", re.IGNORECASE)

# 触发语前后允许带的标点：宿主用 ``app/domain/title.py:_SENTENCE_PUNCTUATION_PATTERN``
# 判断「像不像片名」，句子里带这些标点就**不会**被当成媒体搜索吃掉，才会落到插件。
_LEAD_PUNCT = "？?！!。.，,；;、 \t"
_TAIL_PUNCT = " \t:：,，、-—？?！!。"


def match_trigger(text: str) -> Optional[str]:
    """从一条用户文本里取出触发语后面的片名；不是本模块的触发语就返回 None。

    兼容三种写法（前两种能绕开宿主的媒体搜索拦截）::

        ？胖虎 凡人修仙传
        胖虎 凡人修仙传？
        /胖虎 凡人修仙传      ← 命令入口，走 CommandExcute，不经过标题判定

    :returns: 片名（可能是空串，表示只说了触发语）；不是触发语则 None
    """
    if not text:
        return None
    stripped = text.strip()
    candidate = stripped.lstrip(_LEAD_PUNCT)
    if not candidate.startswith(TRIGGER):
        return None
    return candidate[len(TRIGGER):].strip(_TAIL_PUNCT)


def _payload(event: Any) -> Dict[str, Any]:
    """把宿主事件对象归一成字典（不同宿主版本字段名不一）。"""
    if isinstance(event, dict):
        return event
    for attr in ("event_data", "data", "payload"):
        value = getattr(event, attr, None)
        if isinstance(value, dict):
            return value
    return {}


def _text_of(payload: Dict[str, Any]) -> str:
    for key in ("text", "input_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _user_of(payload: Dict[str, Any]) -> str:
    value = payload.get("userid")
    return str(value) if value not in (None, "") else ""


def _channel_of(payload: Dict[str, Any]) -> str:
    """事件来源渠道（``NotificationChannel`` 的取值，如 ``Telegram`` / ``微信``）。

    宿主事件里带的是 ``NotificationChannel`` 枚举；这里统一成字符串便于落盘，
    发送时再还原成枚举——不设渠道的消息会广播给所有管理员渠道（串台）。
    """
    value = payload.get("channel")
    if value in (None, ""):
        return ""
    return str(getattr(value, "value", value) or "")


def _channel_value(name: str) -> Any:
    """把渠道名还原成宿主 ``NotificationChannel``；宿主没这个枚举就返回 None。"""
    text = str(name or "").strip()
    if not text:
        return None
    try:
        from app.schemas.types import NotificationChannel

        return NotificationChannel(text)
    except Exception:  # pragma: no cover - 老宿主/测试桩没有该枚举
        return None


def _is_plain_channel(name: str) -> bool:
    """这个渠道的正文认不认 Markdown（不认就只能发纯文本）。

    企业微信应用消息走 ``msgtype: text``，``[标题](地址)`` 会原样显示方括号，
    所以微信系一律按纯文本排版；其余渠道（Telegram 等）用 Markdown 链接。
    """
    text = str(name or "").strip()
    return bool(text) and "微信" in text


def _short_id() -> str:
    return uuid.uuid4().hex[:6]


def _page_size(channel: str) -> int:
    """这个渠道一页列几条：纯文本渠道 6 条，其余（有按钮）8 条。"""
    return _PAGE_SIZE_PLAIN if _is_plain_channel(channel) else _PAGE_SIZE


def _human_size(size_mb: Optional[float]) -> str:
    """体积显示：>=1024MB 用 GB，保留一位小数。"""
    if not size_mb:
        return ""
    try:
        value = float(size_mb)
    except (TypeError, ValueError):
        return ""
    if value >= 1024:
        return f"{value / 1024:.1f}GB"
    return f"{value:.0f}MB"


class ManualSearchModule:
    """「胖虎 片名」→ 候选列表 → 点选推送。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ 配置

    def enabled(self) -> bool:
        config = getattr(self._plugin, "config", None) or {}
        if not isinstance(config, dict):
            return True
        value = config.get("manual_search_enabled", True)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in ("", "0", "false", "no", "off")

    # ------------------------------------------------------------------ 状态

    def _state(self) -> Dict[str, Any]:
        try:
            stored = self._plugin.get_data(_STATE_KEY) or {}
        except Exception:  # pragma: no cover - 读不到按空处理
            return {}
        items = stored.get("items") if isinstance(stored, dict) else None
        return dict(items) if isinstance(items, dict) else {}

    def _save_state(self, items: Dict[str, Any]) -> None:
        now = time.time()
        kept = {
            key: value for key, value in (items or {}).items()
            if isinstance(value, dict) and now - float(value.get("created_at") or 0) < _TTL_SECONDS
        }
        if len(kept) > _MAX_REQUESTS:
            ordered = sorted(kept.items(), key=lambda kv: float(kv[1].get("created_at") or 0))
            kept = dict(ordered[-_MAX_REQUESTS:])
        try:
            self._plugin.save_data(_STATE_KEY, {"items": kept, "version": 1})
        except Exception as err:  # pragma: no cover
            logger.warning(f"[{self._plugin_id()}] 保存手动回搜状态失败：{err}")

    def _get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        request = self._state().get(str(request_id or ""))
        return request if isinstance(request, dict) else None

    def _drop_request(self, request_id: str) -> None:
        items = self._state()
        items.pop(str(request_id or ""), None)
        self._save_state(items)

    def _latest_request(self, userid: str,
                        channel: str = "") -> Optional[Tuple[str, Dict[str, Any]]]:
        """找该用户最近一条仍在有效期内的请求（命令回「/胖虎 1」用）。

        为什么要带 ``channel``：宿主给命令事件填的 ``user`` 和给 ``UserMessage``
        填的 ``userid`` 未必是同一种标识（一个可能是昵称、一个是数字 ID），只按
        用户匹配会出现「明明刚搜过却说没有正在进行的回搜」。所以按「同用户 >
        同渠道 > 最近」打分，只要命中共中一个维度就认。
        """
        items = self._state()
        now = time.time()
        alive = [
            (key, value) for key, value in items.items()
            if isinstance(value, dict)
            and now - float(value.get("created_at") or 0) < _TTL_SECONDS
        ]
        if not alive:
            return None

        def _score(pair: Tuple[str, Dict[str, Any]]) -> Tuple[int, int, float]:
            value = pair[1]
            same_user = bool(userid) and str(value.get("userid") or "") == userid
            same_channel = bool(channel) and str(value.get("channel") or "") == channel
            return (1 if same_user else 0, 1 if same_channel else 0,
                    float(value.get("created_at") or 0))

        alive.sort(key=_score, reverse=True)
        best = alive[0]
        if _score(best)[:2] == (0, 0):
            # 既不是这个用户、也不是这个渠道：不认，免得替别人操作
            return None
        return best

    def _plugin_id(self) -> str:
        return self._plugin.__class__.__name__

    # ------------------------------------------------------------------ 文本入口

    def handle_text(self, event: Any) -> bool:
        """处理一条用户文本；返回 True 表示已被本模块消费（不再交给链接转存）。"""
        if not self.enabled():
            return False
        payload = _payload(event)
        text = _text_of(payload)
        if not text:
            return False
        channel = _channel_of(payload)

        if text.startswith(TRIGGER) or match_trigger(text) is not None:
            title = match_trigger(text) or ""
            if not title:
                self._post(
                    title=f"{TRIGGER} 手动回搜",
                    text=f"用法：？胖虎 片名 或 /胖虎 片名（例如：？胖虎 凡人修仙传）",
                    channel=channel,
                )
                return True
            if _COMMAND_RE.match(title):
                # 「？胖虎 3」这种：参数是命令（选条目/翻页/取消），不是片名
                if self._handle_reply(title, _user_of(payload), channel):
                    return True
                self._no_request(channel)
                return True
            threading.Thread(
                target=self._run_search,
                args=(title, _user_of(payload), channel),
                name="tgmc-manual-search",
                daemon=True,
            ).start()
            return True

        # 裸数字 / p / n 一律不接：宿主 ``app/chain/interaction.py:289`` 的
        # ``isdigit()`` 与 ``:331``/``:361`` 的 p/n 分支会先把它们吃掉并回
        # 「输入无效」，插件根本收不到。选条目、翻页只走 ``/胖虎`` 命令入口
        # （用户 m24248：要专属路径，不跟宿主抢）。
        return False

    # ------------------------------------------------------------------ 命令入口

    def handle_command(self, event: Any) -> bool:
        """``/胖虎 片名`` 命令入口（宿主插件命令 → ``PluginAction`` 事件）。

        为什么还要单独做命令入口：宿主在派发 ``UserMessage`` 给插件**之前**，会先用
        ``_MediaInteractionChain.handle_text_interaction`` 判断「这句话像不像片名」
        （``app/chain/music_interaction/music.py:resolve_media_action`` →
        ``app/domain/title.py:is_media_title_like``），像就当成媒体搜索吃掉，搜不到
        直接回「XXX 没有找到对应的媒体信息！」——纯文本「胖虎 凡人修仙传」因此根本
        到不了插件。以 ``/`` 开头走的是 ``EventType.CommandExcute`` 分支
        （``app/chain/message.py:523``），不会被拦。
        """
        if not self.enabled():
            return False
        payload = _payload(event)
        if str(payload.get("action") or "") != ACTION_COMMAND:
            return False
        channel = _channel_of(payload)
        title = str(payload.get("arg_str") or "").strip().strip(" \t:：,，、-—")
        userid = str(payload.get("user") or payload.get("userid") or "")
        if not title:
            self._post(
                title=f"{TRIGGER} 手动回搜",
                text="用法：/胖虎 片名（例如：/胖虎 凡人修仙传）",
                channel=channel,
            )
            return True
        if _COMMAND_RE.match(title):
            # /胖虎 1（推送第 1 条）、/胖虎 n（下一页）、/胖虎 取消
            if self._handle_reply(title, userid, channel):
                return True
            self._no_request(channel)
            return True
        threading.Thread(
            target=self._run_search,
            args=(title, userid, channel),
            name="tgmc-manual-search",
            daemon=True,
        ).start()
        return True

    def _no_request(self, channel: str = "") -> None:
        """命令参数没有对应的回搜请求（过期/已取消/从没搜过）。"""
        self._post(
            title=f"{TRIGGER} 手动回搜",
            text=f"没有正在进行的回搜。先发 /胖虎 片名 搜一次，再用 /胖虎 1 推送。",
            channel=channel,
        )

    def _handle_reply(self, text: str, userid: str, channel: str = "") -> bool:
        """``/胖虎 1`` / ``/胖虎 n`` / ``/胖虎 取消``：对最近一次回搜做操作。

        为什么必须挂在 ``/胖虎`` 命令上：裸数字和 ``n`` / ``p`` 会被宿主
        ``app/chain/interaction.py:289`` / ``:331`` / ``:361`` 先吃掉并回「输入
        无效」，插件收不到（用户 m24248：要专属路径，不跟宿主抢）。
        """
        found = self._latest_request(userid, channel)
        if not found:
            return False
        request_id, request = found
        lowered = text.lower()
        if lowered in ("取消", "x"):
            self._drop_request(request_id)
            self._post(
                title="已取消",
                text="这次手动回搜已取消。",
                channel=channel or str(request.get("channel") or ""),
            )
            return True
        if lowered in ("p", "上一页"):
            self._turn_page(request_id, -1)
            return True
        if lowered in ("n", "下一页"):
            self._turn_page(request_id, 1)
            return True
        try:
            index = int(text) - 1
        except ValueError:
            return False
        return self._push_items(request_id, [index], channel=channel)

    # ------------------------------------------------------------------ 检索

    def _run_search(self, title: str, userid: str, channel: str = "") -> None:
        try:
            request_id = self._search_and_send(title, userid, channel)
            if request_id:
                logger.info(f"[{self._plugin_id()}] 手动回搜「{title}」→ 请求 {request_id}")
        except Exception as err:  # pragma: no cover - 后台线程不能抛
            logger.warning(f"[{self._plugin_id()}] 手动回搜失败：{err}")
            self._post(
                title=f"{TRIGGER} 手动回搜",
                text=f"检索「{title}」时出错：{err}",
                channel=channel,
            )

    def _search_and_send(self, title: str, userid: str, channel: str = "") -> Optional[str]:
        cache = getattr(self._plugin, "_cache", None)
        if cache is None:
            self._post(
                title=f"{TRIGGER} 手动回搜",
                text="消息缓存模块未就绪，请稍后再试",
                channel=channel,
            )
            return None
        rows = cache.search_by_title(title, limit=200)
        if not rows:
            self._post(
                title=f"【{title}】没有找到",
                text=f"消息缓存里没有「{title}」。\n"
                     f"（缓存只包含已监听频道的历史消息；刚发的消息要等下一轮同步）",
                channel=channel,
            )
            return None

        rules = cache.wash_rules()
        items = self._build_items(rows, rules, cache)
        if not items:
            self._post(
                title=f"【{title}】没有可用候选",
                text="找到的消息里既没有带链接的资源，也认不出分辨率/体积，没法列出来。",
                channel=channel,
            )
            return None

        request_id = _short_id()
        state = self._state()
        year = ""
        for item in items:
            if str(item.get("year") or ""):
                year = str(item.get("year"))
                break
        state[request_id] = {
            "title": title,
            "year": year,
            "items": items,
            "page": 0,
            "created_at": time.time(),
            "userid": userid,
            "channel": channel,
            # 一页几条随渠道定：TG 有按钮 8 条，微信纯文本 6 条（用户 m24154）
            "page_size": _page_size(channel),
            "message_id": 0,
            "chat_id": 0,
            # 海报只查一次，翻页复用（取不到就是空串，退回纯文本）
            "poster": self._poster(title),
        }
        self._save_state(state)
        self._send_page(request_id, state[request_id], edit=False)
        return request_id

    def _build_items(self, rows: List[dict], rules: Dict[str, Any], cache: Any) -> List[dict]:
        """把缓存里命中的**每一条**资源都列出来，逐条对基线只做标注。

        1.13.38 起不再按洗版规则筛（用户 m23312：手动回搜独立于订阅/监控，
        要「全部接入、直接推给用户」）——旧实现有两层过滤会把大量候选整条
        吃掉：① ``filter_profile`` 白名单+体积闸（画质没写进白名单、标题里
        没写分辨率的直接被丢）；② 同集只留画质最优的一条（同集其它版本不
        显示）。现在只丢两类：没有链接的、以及连分辨率/体积都解析不出的
        （既没法比较也没法描述）。

        基线比较保留，但只用于打标记 ``↑/= /↓/?``，不再决定「显不显示」。
        排序：按洗版规则的画质排，同分再按体积大→小。

        1.13.38 起（用户 m24027）标记不再展示给用户——「值不值得升级」由用户
        自己看画质和体积判断，这里只负责把候选排好序。
        """
        items: List[dict] = []
        baseline_cache: Dict[Tuple, Dict[str, dict]] = {}
        # 1.13.38：列表每行带上来源频道名（展示用，取不到就留空）
        names: Dict[int, str] = {}
        getter = getattr(cache, "dialog_names", None)
        if callable(getter):
            try:
                names = getter() or {}
            except Exception:  # pragma: no cover - 取不到来源不影响列条目
                names = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "")
            links = [str(item) for item in (row.get("links") or []) if item]
            if not links:
                continue
            profile = quality_service.parse_quality(text)
            if not profile.get("resolution") and profile.get("size_mb") is None:
                # 连分辨率、体积都认不出：没法比较、也没法给用户描述，直接不列
                continue
            title = str(row.get("title") or "")
            year = str(row.get("year") or "")
            season = row.get("season")
            episode = row.get("episode")
            media_type = str(row.get("media_type") or "")
            keys = quality_service.episode_keys(
                title, year, media_type, season, episode, row.get("episode_end"),
            )
            bucket = (media_type, season)
            if bucket not in baseline_cache:
                try:
                    baseline_cache[bucket] = cache.wash_baselines(
                        title, year, media_type, season,
                    ) or {}
                except Exception:  # pragma: no cover - 基线取不到按无基线
                    baseline_cache[bucket] = {}
            profiles = self._episode_profiles(profile, keys)
            verdict = wash_gate.judge(
                profile, rules, baseline_cache[bucket],
                keys=keys, profiles=profiles,
            )
            state = verdict.get("state")
            detail_state = ""
            detail_reason = ""
            for detail in verdict.get("details") or []:
                if str(detail.get("key") or "") in keys:
                    detail_state = str(detail.get("state") or "")
                    detail_reason = str(detail.get("reason") or "")
                    break
            if state == wash_gate.STATE_PUSH:
                # 「无基线 / 画质解析不出」并不等于更优，单独标出来
                if detail_state == quality_service.STATE_UNKNOWN or detail_reason.startswith("首次推送"):
                    mark = MARK_UNKNOWN
                else:
                    mark = MARK_UPGRADE
            elif state == wash_gate.STATE_LOWER:
                mark = MARK_LOWER
            elif state == wash_gate.STATE_FLAT:
                mark = MARK_FLAT
            else:  # pragma: no cover - judge 其余状态按无基线处理
                mark = MARK_UNKNOWN
            items.append({
                "profile": profile,
                "links": links,
                "text": text,
                "chat_id": int(row.get("chat_id") or 0),
                "source": str(names.get(int(row.get("chat_id") or 0)) or ""),
                "message_id": int(row.get("message_id") or 0),
                "title": title,
                "year": year,
                "season": season,
                "episode": episode,
                "episode_end": row.get("episode_end"),
                "media_type": media_type,
                "key": keys[0] if keys else "",
                "keys": keys,
                "profiles": profiles,
                "mark": mark,
                "reason": str(verdict.get("reason") or ""),
            })

        def _order(item: dict) -> Tuple:
            quality_key = quality_service.sort_key(item.get("profile") or {}, rules)
            size_mb = item.get("profile", {}).get("size_mb")
            return (
                quality_key,
                -(float(size_mb) if size_mb else 0.0),
                int(item.get("season") or 0),
                int(item.get("episode") or 0),
                int(item.get("message_id") or 0),
            )

        items.sort(key=_order)
        return items

    # ------------------------------------------------------------------ 渲染 / 发送

    def _label(self, item: dict) -> str:
        season = item.get("season")
        episode = item.get("episode")
        if not episode:
            return "整包"
        prefix = f"S{int(season):02d}" if season else ""
        end = item.get("episode_end")
        if end and int(end) > int(episode):
            return f"{prefix}E{int(episode):02d}-E{int(end):02d}"
        return f"{prefix}E{int(episode):02d}"

    def _line(self, index: int, item: dict, *, pushed: bool = False,
              markdown: bool = True) -> str:
        """一条候选占两行（用户 m24638 要求整齐）：第一行来源，第二行集数/画质/体积。

        ```
        1. 🌐 115网盘影视热更频道
        S01E07 · 🌟 2160p · 💾 1.6GB
        ```

        集数做成 115 分享链接（Markdown 链接，Telegram 侧由 telegramify 转
        MarkdownV2）。只有 ``http(s)`` 链接才做超链接——ed2k / 磁力链接里带
        ``|`` 会截断语法，Telegram 会把整条链接当纯文本糊出来（用户 m24060）。

        ``markdown=False`` 时不加链接——企业微信图文消息的 description 原样显示
        ``[标题](地址)``，只能给纯标签（用户 m24248 前的实测结论）。

        没有来源频道时（对话已不在缓存里）退化成两行里的第一行直接放集数。
        """
        profile = item.get("profile") or {}
        label = self._label(item)
        url = str((item.get("links") or [""])[0] or "").strip()
        if url and markdown and url.lower().startswith(("http://", "https://")):
            label = f"[{label}]({url})"
        quality = str(profile.get("resolution") or "").strip()
        size = _human_size(profile.get("size_mb"))
        source = str(item.get("source") or "").strip()

        specs = [label]
        if quality:
            specs.append(f"🌟 {quality}")
        if size:
            specs.append(f"💾 {size}")
        if pushed:
            specs.append("✓ 已推送")
        detail = " · ".join(specs)

        if not source:
            return f"{index}. {detail}"
        return f"{index}. 🌐 {source}\n{detail}"

    def _poster(self, title: str, *, timeout: float = _POSTER_TIMEOUT) -> str:
        """取片名海报（每轮回搜只查一次，取不到就退回纯文本）。

        走宿主的 ``MediaChain``（TMDB/豆瓣），属于**外部网络**调用，可能很慢，
        所以放在短命线程里并只等 ``timeout`` 秒：超时就先发纯文本列表，后台线程
        自己跑完丢弃。海报只是锦上添花，绝不能拖住用户等列表。
        """
        keyword = str(title or "").strip()
        if not keyword:
            return ""
        found: Dict[str, str] = {}

        def _work() -> None:
            try:
                from app.chain.media import MediaChain

                _meta, medias = MediaChain().search(keyword)
            except Exception as err:  # pragma: no cover - 宿主不可用/未配置数据源
                logger.debug(f"[{self._plugin_id()}] 取海报失败：{err}")
                return
            for media in medias or []:
                try:
                    image = media.get_message_image()
                except Exception:  # pragma: no cover - 单个媒体取图失败不影响其它
                    continue
                if image:
                    found["url"] = str(image)
                    return

        worker = threading.Thread(target=_work, daemon=True)
        worker.start()
        worker.join(timeout)
        return found.get("url", "")

    def _header(self, request: dict) -> str:
        """列表标题：``玉簟秋 (2026)``（用户 m24546：标题第一行留片名+年份就够）。"""
        name = str(request.get("title") or "")
        year = str(request.get("year") or "")
        return name + (f" ({year})" if year else "")

    def _send_page(self, request_id: str, request: dict, *, edit: bool) -> bool:
        items = request.get("items") or []
        total = len(items)
        pushed_indexes = {int(index) for index in (request.get("pushed") or [])}
        channel = str(request.get("channel") or "")
        page_size = int(request.get("page_size") or _page_size(channel))
        page_count = max(1, (total + page_size - 1) // page_size)
        page = int(request.get("page") or 0)
        page = min(max(0, page), page_count - 1)
        request["page"] = page
        start = page * page_size
        chunk = items[start:start + page_size]

        # 企业微信的应用消息是 msgtype=text，不认 Markdown，只能给纯标签
        plain = _is_plain_channel(channel)
        lines = [self._line(start + offset + 1, item,
                            pushed=(start + offset) in pushed_indexes, markdown=not plain)
                 for offset, item in enumerate(chunk)]
        meta_parts = [f"共 {total} 条"]
        if page_count > 1:
            meta_parts.append(f"第 {page + 1}/{page_count} 页")
        meta = " · ".join(meta_parts)
        nav: List[str] = []
        if page < page_count - 1:
            nav.append("/胖虎 n 下一页")
        if page > 0:
            nav.append("/胖虎 p 上一页")
        if plain:
            # 微信没有按钮、也不能编辑消息：操作提示只能写清楚命令怎么写
            footer = " · ".join(["回复 /胖虎 1 推送第 1 条"] + nav + ["/胖虎 取消"])
        else:
            # TG 下方就是数字键盘和翻页按钮，正文不再写任何操作提示（用户 m24703）
            footer = ""
        body = "\n".join(lines + ([footer] if footer else []))
        poster = str(request.get("poster") or "") or None

        if plain:
            # 微信也是一条图文消息：海报在上，标题、条数页码、列表、操作提示依次在下。
            # 1.13.38 曾拆成「卡片 + 纯文本列表」两条，带图那条描述只有一行，
            # 客户端就渲染成小卡片、缩略图跑到下方（用户 m24613 截图对比旧版）。
            return self._post(
                title=self._header(request), text=f"{meta}\n{body}",
                channel=channel, image=poster,
            )

        buttons = self._buttons(request_id, page, page_count, chunk, start)
        ref = None
        if edit and request.get("message_id") and request.get("chat_id"):
            ref = (int(request["message_id"]), int(request["chat_id"]))
        return self._post(
            title=self._header(request), text=f"{meta}\n{body}",
            buttons=buttons, edit_ref=ref, channel=channel, image=poster,
        )

    def _callback(self, content: str) -> str:
        """宿主回调格式：``[PLUGIN]{插件ID}|{内容}``，缺前缀会被判定为格式错误。"""
        return f"[PLUGIN]{self._plugin_id()}|{content}"

    def _buttons(self, request_id: str, page: int, page_count: int,
                 chunk: List[dict], start: int) -> List[List[dict]]:
        rows: List[List[dict]] = []
        row: List[dict] = []
        for offset, _item in enumerate(chunk):
            index = start + offset
            row.append({
                "text": str(index + 1),
                "callback_data": self._callback(f"s:{request_id}:{index}"),
            })
            if len(row) >= _BUTTONS_PER_ROW:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        if page_count > 1:
            nav: List[dict] = []
            if page > 0:
                nav.append({"text": "⬅️ 上一页", "callback_data": self._callback(f"p:{request_id}:prev")})
            if page < page_count - 1:
                nav.append({"text": "下一页 ➡️", "callback_data": self._callback(f"p:{request_id}:next")})
            if nav:
                rows.append(nav)
        return rows

    def _post(self, *, title: str, text: str, buttons: Optional[List[List[dict]]] = None,
              edit_ref: Optional[Tuple[int, int]] = None, channel: str = "",
              image: Optional[str] = None) -> bool:
        """发消息：优先走 chain + Message（不注入插件页链接），失败退回 post_message。

        ``channel`` 必须带上事件来源渠道：宿主 ``NotificationModule.check_message`` 只放行
        ``message.channel`` 为空或等于自身渠道的消息，留空就会广播给所有管理员渠道（串台）。

        ``image`` 给了就走图文（Telegram 转 send_photo、微信转 news 图文卡），
        没有就纯文本。
        """
        kwargs: Dict[str, Any] = {"title": title, "text": text}
        target_channel = _channel_value(channel)
        if target_channel is not None:
            kwargs["channel"] = target_channel
        if image:
            kwargs["image"] = image
        if buttons:
            kwargs["buttons"] = buttons
        if edit_ref:
            kwargs["original_message_id"] = edit_ref[0]
            kwargs["original_chat_id"] = edit_ref[1]
            kwargs["save_history"] = False

        chain = getattr(self._plugin, "chain", None)
        if chain is not None:
            try:
                from app.schemas.message import Message

                chain.post_message(Message(**kwargs))
                return True
            except Exception as err:  # pragma: no cover - 宿主 Message 构造失败则降级
                logger.debug(f"[{self._plugin_id()}] chain 发消息失败，改用 post_message：{err}")

        func = getattr(self._plugin, "post_message", None)
        if not callable(func):
            return False
        try:
            func(**kwargs)
            return True
        except TypeError:
            # 老宿主不认 buttons / original_message_id 等扩展参数
            try:
                func(title=title, text=text)
                return True
            except Exception as err:  # pragma: no cover
                logger.debug(f"[{self._plugin_id()}] 发消息失败：{err}")
                return False
        except Exception as err:  # pragma: no cover
            logger.debug(f"[{self._plugin_id()}] 发消息失败：{err}")
            return False

    # ------------------------------------------------------------------ 翻页 / 推送

    def _turn_page(self, request_id: str, delta: int) -> bool:
        with self._lock:
            request = self._get_request(request_id)
            if not request:
                return False
            items = request.get("items") or []
            page_size = int(request.get("page_size") or _page_size(
                str(request.get("channel") or "")))
            page_count = max(1, (len(items) + page_size - 1) // page_size)
            page = int(request.get("page") or 0) + int(delta)
            request["page"] = min(max(0, page), page_count - 1)
            state = self._state()
            state[request_id] = request
            self._save_state(state)
        self._send_page(request_id, request, edit=True)
        return True

    def handle_action(self, event: Any) -> None:
        """宿主 MessageAction 回调（按钮点击）。"""
        if not self.enabled():
            return
        payload = _payload(event)
        plugin_id = str(payload.get("plugin_id") or "")
        if plugin_id and plugin_id != self._plugin_id():
            return
        content = _text_of(payload)
        if not content:
            return
        parts = content.split(":")
        action = parts[0]
        if action == "p" and len(parts) >= 3:
            self._turn_page(parts[1], -1 if parts[2] == "prev" else 1)
        elif action == "s" and len(parts) >= 3:
            try:
                index = int(parts[2])
            except ValueError:
                return
            self._push_items(parts[1], [index], channel=_channel_of(payload))
        elif action == "a" and len(parts) >= 2:
            request = self._get_request(parts[1])
            if not request:
                self._post(
                    title="这次回搜已结束",
                    text="这条手动回搜已结束（可能已取消或超过 24 小时），请重新发一次「胖虎 片名」。",
                    channel=_channel_of(payload),
                )
                return
            pushed = {int(index) for index in (request.get("pushed") or [])}
            indexes = [index for index, item in enumerate(request.get("items") or [])
                       if item.get("mark") == MARK_UPGRADE and index not in pushed]
            if not indexes:
                self._post(
                    title="没有待推送的升级项",
                    text="可升级的条目都已经加入推送队列了。",
                    channel=str(request.get("channel") or "") or _channel_of(payload),
                )
                return
            self._push_items(parts[1], indexes, channel=_channel_of(payload))
        elif action == "x" and len(parts) >= 2:
            request = self._get_request(parts[1]) or {}
            self._drop_request(parts[1])
            self._post(
                title="已取消",
                text="这次手动回搜已取消。",
                channel=str(request.get("channel") or "") or _channel_of(payload),
            )

    def _pipeline(self):
        """取监控流水线：优先走监控模块的懒启动入口（流水线挂在 monitor 上）。"""
        monitor = getattr(self._plugin, "_monitor", None)
        ensure = getattr(monitor, "_ensure_pipeline", None)
        if callable(ensure):
            try:
                pipeline = ensure()
            except Exception as err:  # pragma: no cover - 宿主异常时退回插件属性
                logger.warning(f"[{self._plugin_id()}] 取推送流水线失败：{err}")
                pipeline = None
            if pipeline is not None:
                starter = getattr(monitor, "ensure_started", None)
                if callable(starter):
                    try:
                        starter()
                    except Exception:  # pragma: no cover - 启动失败不影响入队
                        pass
                return pipeline
        return getattr(self._plugin, "_pipeline", None)

    def _push_items(self, request_id: str, indexes: List[int], *, channel: str = "") -> bool:
        with self._lock:
            request = self._get_request(request_id)
            if not request:
                self._post(
                    title="这次回搜已结束",
                    text="这条手动回搜已结束（可能已取消或超过 24 小时），请重新发一次「胖虎 片名」。",
                    channel=channel,
                )
                return False
            items = request.get("items") or []
            already = {int(index) for index in (request.get("pushed") or [])}
            picked_indexes = []
            for index in indexes or []:
                value = int(index)
                if 0 <= value < len(items) and value not in already:
                    picked_indexes.append(value)
            if not picked_indexes:
                if already & {int(index) for index in (indexes or [])}:
                    self._post(
                        title="已推送过",
                        text="选中的条目之前已经加入推送队列了。",
                        channel=channel or str(request.get("channel") or ""),
                    )
                return False
            picked = [items[index] for index in picked_indexes]
            reply_channel = channel or str(request.get("channel") or "")

        pipeline = self._pipeline()
        if pipeline is None:
            self._post(
                title="推送不可用", text="推送流水线未就绪，请稍后再试。", channel=reply_channel,
            )
            return False

        ok_count = 0
        done_indexes: List[int] = []
        for index, item in zip(picked_indexes, picked):
            try:
                extra = self._wash_extra(item) or {}
                # 1.13.38：把发起渠道带进任务负载，回执据此只发回该渠道
                # （否则 TG 里点的推送，转存完成通知会广播到微信）
                if reply_channel:
                    extra["origin_channel"] = reply_channel
                task_id = pipeline._enqueue_push(
                    rule={"id": "manual_search", "target_id": ""},
                    chat_id=int(item.get("chat_id") or 0),
                    message_id=int(item.get("message_id") or 0),
                    text=str(item.get("text") or ""),
                    links=[str(link) for link in (item.get("links") or [])],
                    destination="pan115",
                    title=str(item.get("title") or ""),
                    extra=extra,
                )
                if task_id:
                    ok_count += 1
                    done_indexes.append(index)
            except Exception as err:  # pragma: no cover - 单条失败不影响其它
                logger.warning(f"[{self._plugin_id()}] 手动回搜入队失败：{err}")

        if done_indexes:
            self._mark_pushed(request_id, done_indexes)

        if ok_count:
            self._post(
                title=self._receipt_title(picked[0]),
                text=self._receipt_text(picked),
                channel=reply_channel,
                image=str(request.get("poster") or "") or None,
            )
        else:
            label = "、".join(self._label(item) for item in picked[:5])
            self._post(
                title="入队失败",
                text=f"{label} 没有成功入队，请查看插件日志。",
                channel=reply_channel,
            )
        return ok_count > 0

    def _receipt_title(self, item: dict) -> str:
        """推送回执标题，照宿主「📥 开始下载」那张卡：``📥 开始推送\\n玉簟秋 (2026)``。"""
        name = str(item.get("title") or "")
        year = str(item.get("year") or "")
        return "📥 开始推送\n" + name + (f" ({year})" if year else "")

    def _receipt_text(self, picked: List[dict]) -> str:
        """回执正文：emoji 字段行（时间 / 来源 / 集数 / 画质 / 体积 / 链接）。"""
        first = picked[0] if picked else {}
        profile = first.get("profile") or {}
        lines = [f"🕒 时间：{time.strftime('%Y-%m-%d %H:%M')}"]
        source = str(first.get("source") or "").strip()
        if source:
            lines.append(f"🌐 来源：{source}")
        labels = "、".join(self._label(item) for item in picked[:5])
        if labels:
            lines.append(f"🎬 集数：{labels}")
        quality = str(profile.get("resolution") or "").strip()
        if quality:
            lines.append(f"🌟 质量：{quality}")
        size = _human_size(profile.get("size_mb"))
        if size:
            lines.append(f"💾 大小：{size}")
        link = str((first.get("links") or [""])[0] or "").strip()
        if link:
            lines.append(f"🔗 链接：{link}")
        lines.append("转存完成后会另发通知；列表仍可继续点选。")
        return "\n".join(lines)

    def _mark_pushed(self, request_id: str, indexes: List[int]) -> None:
        """把已入队的条目记到请求里：列表不失效，可继续翻页/点其它集。"""
        with self._lock:
            items = self._state()
            request = items.get(str(request_id or ""))
            if not isinstance(request, dict):
                return
            pushed = [int(index) for index in (request.get("pushed") or [])]
            for index in indexes:
                if int(index) not in pushed:
                    pushed.append(int(index))
            request["pushed"] = pushed
            items[str(request_id)] = request
            self._save_state(items)

    @staticmethod
    def _episode_profiles(profile: dict, keys: List[str]) -> Optional[Dict[str, dict]]:
        """整包资源按集数摊体积：逐集比较时体积才可比（否则整包体积天然更大）。"""
        if not keys or len(keys) <= 1:
            return None
        size_mb = profile.get("size_mb")
        if not size_mb:
            return None
        per = round(float(size_mb) / len(keys), 2)
        return {key: dict(profile, size_mb=per) for key in keys}

    @staticmethod
    def _wash_extra(item: dict) -> Optional[Dict[str, Any]]:
        """带上洗版上下文：整包资源要按集拆键，推送后逐集记基线。"""
        keys = [str(key) for key in (item.get("keys") or []) if key]
        if not keys:
            key = str(item.get("key") or "")
            if not key:
                return None
            keys = [key]
        wash: Dict[str, Any] = {
            "keys": keys,
            "profile": item.get("profile") or {},
        }
        profiles = item.get("profiles")
        if profiles:
            wash["profiles"] = profiles
        episodes: List[int] = []
        for key in keys:
            parts = key.split("|")
            if len(parts) >= 5 and parts[3]:
                try:
                    episodes.append(int(parts[3]))
                except ValueError:  # pragma: no cover - 键里不是数字就跳过
                    continue
        if episodes:
            wash["episodes"] = episodes
        return {"wash": wash}
