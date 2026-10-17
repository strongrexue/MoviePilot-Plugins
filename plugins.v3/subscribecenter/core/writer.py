"""订阅写入 —— 全插件**唯一**的写入点。

开发文档 §7.3 的纪律全部落在本模块：

1. 用 ``SubscribeChain().async_add()``（不是 ``add()``，也不是 REST）；
2. 身份走 ``media_source`` + ``media_id`` 成对字段，**没有** ``tmdbid`` 形参；
3. ``title`` / ``year`` 位置必填，且 ``year`` 是**字符串**；
4. ``add()`` 按身份幂等 —— 靠返回的 ``message`` 区分「新增」与「已存在」；
5. 写入前**实时**复查宿主订阅，而不是依赖运行开始时的快照；
6. **必须同时查 ``SubscribeHistory``** —— 宿主 ``async_add()`` 不做这个检查，
   而订阅完成后记录会移入 history（开发文档 §7.6）。

本模块不直接导入宿主：``SubscribeChain`` 等能力经 :class:`SubscribeBackend`
注入，因此可离线单测。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence

from .constants import (
    DECISION_ADDED,
    DECISION_PENDING_REVIEW,
    DECISION_SKIPPED_ALREADY_COMPLETED,
    DECISION_SKIPPED_ALREADY_SUBSCRIBED,
    DECISION_SKIPPED_DAILY_LIMIT,
    DECISION_SKIPPED_DRY_RUN,
    DECISION_SKIPPED_FINISHED,
    DECISION_SKIPPED_NOT_FUTURE,
    DECISION_SKIPPED_OUT_OF_WINDOW,
    DECISION_SKIPPED_SPECIAL,
    WRITABLE_CONFIDENCE,
)
from .identity import HOST_SOURCE_TMDB
from .model import DiscoveredItem
from .window import parse_date, today

#: 写入前的自我校验：定档日期距今天**最多**允许多少天。
#: 这是对上游窗口过滤的冗余兜底 —— 宁可拒写，也不要把「几十年前的老片」
#: 或「日期算错的条目」写进订阅（真机出现过 2003 年的《戴帽子的猫》被列为新增）。
SELF_CHECK_MAX_FUTURE_DAYS = 365

#: 宿主 ``async_add`` 的返回文案（用于区分新增 / 已存在）
MESSAGE_ADDED = "新增订阅成功"
MESSAGE_EXISTS = "订阅已存在"


class SubscribeBackend(Protocol):
    """宿主订阅能力（由适配器实现）。"""

    async def add(
        self,
        title: str,
        year: str,
        media_source: str,
        media_id: str,
        media_type: str,
        season: Optional[int] = None,
        *,
        message: bool = ...,
        exist_ok: bool = ...,
    ) -> tuple:
        """调用 ``SubscribeChain().async_add()``，返回 ``(subscribe_id, message)``。"""
        ...

    async def subscription_exists(self, media_source: str, media_id: str) -> bool:
        """宿主是否已有该身份的**活跃**订阅（``Subscribe`` 表，任意状态）。"""
        ...

    async def history_exists(self, media_source: str, media_id: str) -> bool:
        """宿主是否已有该身份的**已完成**订阅历史（``SubscribeHistory`` 表）。"""
        ...


@dataclass
class WriteOutcome:
    """单条条目的写入结果。"""

    item: DiscoveredItem
    decision: str
    success: bool = False
    subscribe_id: Optional[int] = None
    message: str = ""
    reason: str = ""

    @property
    def added(self) -> bool:
        """是否真的新增了订阅（幂等命中不算新增）。"""
        return self.decision == DECISION_ADDED and self.success

    def to_dict(self) -> Dict[str, Any]:
        """序列化用于落流水 / 回传前端。"""
        data = self.item.to_log_dict()
        data.update(
            {
                "decision": self.decision,
                "success": self.success,
                "subscribe_id": self.subscribe_id,
                "message": self.message,
                "reason": self.reason,
            }
        )
        return data


@dataclass
class WriteReport:
    """一次写入批次的汇总。"""

    outcomes: List[WriteOutcome] = field(default_factory=list)
    limit_hit: bool = False
    dry_run: bool = False

    @property
    def added(self) -> List[WriteOutcome]:
        """真正新增的条目。"""
        return [o for o in self.outcomes if o.added]

    @property
    def added_count(self) -> int:
        """新增条数。"""
        return len(self.added)

    @property
    def skipped(self) -> List[WriteOutcome]:
        """被跳过的条目（含待确认）。"""
        return [o for o in self.outcomes if o.decision != DECISION_ADDED]

    @property
    def pending_review(self) -> List[WriteOutcome]:
        """进待确认列表的条目（L4）。"""
        return [o for o in self.outcomes if o.decision == DECISION_PENDING_REVIEW]

    def to_summary(self) -> Dict[str, Any]:
        """汇总字典（通知与状态接口共用）。"""
        return {
            "total": len(self.outcomes),
            "added": self.added_count,
            "skipped": len(self.skipped),
            "pending_review": len(self.pending_review),
            "limit_hit": self.limit_hit,
            "dry_run": self.dry_run,
        }


class SubscriptionWriter:
    """把发现条目写成宿主订阅。

    :param backend: 宿主订阅能力
    :param daily_limit: 每日写入上限（<=0 表示不限制）
    """

    def __init__(self, backend: SubscribeBackend, *, daily_limit: int = 30) -> None:
        self._backend = backend
        self._daily_limit = daily_limit

    # ------------------------------------------------------------------ 主入口

    async def write(
        self,
        items: Sequence[DiscoveredItem],
        *,
        dry_run: bool,
        already_written_today: int = 0,
        tz_name: Optional[str] = None,
    ) -> WriteReport:
        """逐条写入订阅。

        **串行**执行（开发文档 §7.3：写入串行或小批量，避免给宿主压力）。

        :param dry_run: 只判定不写入
        :param already_written_today: 今日已写入计数（决定上限剩余额度）
        """
        report = WriteReport(dry_run=dry_run)
        budget = self._remaining_budget(already_written_today)
        current_day = today(tz_name)

        for item in items:
            # 额度必须在**写入之前**检查：否则超限批次仍会真的调用宿主 add()
            if budget <= 0:
                report.outcomes.append(
                    WriteOutcome(
                        item=item,
                        decision=DECISION_SKIPPED_DAILY_LIMIT,
                        success=False,
                        reason=f"今日写入已达上限 {self._daily_limit} 条",
                    )
                )
                report.limit_hit = True
                continue
            outcome = await self._write_one(item, dry_run=dry_run, today_value=current_day)
            if outcome.decision == DECISION_ADDED:
                budget -= 1
            report.outcomes.append(outcome)

        return report

    # ------------------------------------------------------------------ 单条

    async def _write_one(
        self,
        item: DiscoveredItem,
        *,
        dry_run: bool,
        today_value: Any,
    ) -> WriteOutcome:
        """判定单条条目并（在允许时）写入。"""
        # ---- 特别篇 / OVA / 番外：设计上不处理
        #
        # 这类内容在 TMDB 通常没有独立条目，标题匹配必然失败。若走通用分支会
        # 显示「无确定性身份（L4）」，看起来像插件有 bug（真机踩过 3 条）。
        # 明确标注为「特别篇不处理」，让日志说实话；需要的话可手动订阅。
        if getattr(item, "special", False):
            return WriteOutcome(
                item=item,
                decision=DECISION_SKIPPED_SPECIAL,
                reason="特别篇 / OVA / 番外等衍生内容，本插件不处理（需要可手动订阅）",
            )

        # ---- 匹配到的剧集已全部播完：订了也搜不到未播资源
        #
        # 真机事故：Bangumi《ゲルぴよ 第2期》开播 2026-10-21，但 TMDB 只有第 1 季
        # （2026-01~03 全播完）。不传季号时宿主按第 1 季订阅，等于订了一部老番。
        if getattr(item, "finished", False):
            return WriteOutcome(
                item=item,
                decision=DECISION_SKIPPED_FINISHED,
                reason="匹配到的 TMDB 剧集已无未播出内容（可能匹配到了旧季），跳过",
            )

        # ---- 身份可写性（L4 永不写入）
        confidence = item.confidence
        if not item.resolved or confidence not in WRITABLE_CONFIDENCE:
            return WriteOutcome(
                item=item,
                decision=DECISION_PENDING_REVIEW,
                reason=f"无确定性身份（{confidence}），仅记录待人工确认",
            )
        identity = item.resolved

        # ---- 兜底：定档日期必须落在合理窗口内
        #
        # 上游流水线已经做过窗口过滤，这里再验一次是**故意的冗余**：
        # 真机出现过「戴帽子的猫」被列为新增、而该片 TMDB 上是 2003 年作品的情况。
        # 不管前面哪一步（源返回、归一、去重）出了错，这道闸门都能挡住
        # 「订进几十年前老片」这种最伤信任的错误。
        release = parse_date(item.release_date)
        if release is not None:
            if release < today_value:
                return WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_NOT_FUTURE,
                    reason=f"定档日期 {release.isoformat()} 已过去",
                )
            if (release - today_value).days > SELF_CHECK_MAX_FUTURE_DAYS:
                return WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_OUT_OF_WINDOW,
                    reason=(
                        f"定档日期 {release.isoformat()} 距今天超过 "
                        f"{SELF_CHECK_MAX_FUTURE_DAYS} 天，超出合理窗口"
                    ),
                )

        # ---- 写入前实时复查（两层：活跃订阅 + 已完成历史）
        try:
            if await self._backend.subscription_exists(identity.media_source, identity.media_id):
                return WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_ALREADY_SUBSCRIBED,
                    reason="宿主已有该订阅",
                )
            if await self._backend.history_exists(identity.media_source, identity.media_id):
                return WriteOutcome(
                    item=item,
                    decision=DECISION_SKIPPED_ALREADY_COMPLETED,
                    reason="宿主已完成过该订阅（订阅历史中存在）",
                )
        except Exception as err:  # noqa: BLE001 - 复查失败按 fail-open 交给 add() 幂等兜底
            return await self._do_write(item, dry_run=dry_run, precheck_error=str(err))

        return await self._do_write(item, dry_run=dry_run, precheck_error="")

    async def _do_write(
        self,
        item: DiscoveredItem,
        *,
        dry_run: bool,
        precheck_error: str,
    ) -> WriteOutcome:
        """执行 dry-run 判定或真实写入。"""
        identity = item.resolved
        assert identity is not None  # _write_one 已保证

        if dry_run:
            return WriteOutcome(
                item=item,
                decision=DECISION_SKIPPED_DRY_RUN,
                reason="dry-run 模式，未写入",
            )

        title = item.title or item.original_title or ""
        if not title:
            return WriteOutcome(
                item=item,
                decision=DECISION_PENDING_REVIEW,
                reason="标题为空，无法写入",
            )

        try:
            sid, message = await self._backend.add(
                title=title,
                year=str(item.year or ""),
                media_source=identity.media_source,
                media_id=identity.media_id,
                media_type=item.media_type,
                season=item.season,
                message=False,  # 逐条静默，由插件在末尾发汇总通知
                exist_ok=False,
            )
        except Exception as err:  # noqa: BLE001 - 单条失败不影响后续条目
            return WriteOutcome(
                item=item,
                decision=DECISION_PENDING_REVIEW,
                reason=f"写入异常：{err}",
            )

        text = str(message or "")
        # add() 幂等：命中既有订阅时返回既有 ID + 「订阅已存在」，不算新增
        if text == MESSAGE_EXISTS:
            return WriteOutcome(
                item=item,
                decision=DECISION_SKIPPED_ALREADY_SUBSCRIBED,
                success=True,
                subscribe_id=sid,
                message=text,
                reason="宿主判定订阅已存在（幂等命中）",
            )
        if not sid:
            return WriteOutcome(
                item=item,
                decision=DECISION_PENDING_REVIEW,
                message=text,
                reason=f"写入未成功：{text or '宿主未返回订阅 ID'}",
            )
        return WriteOutcome(
            item=item,
            decision=DECISION_ADDED,
            success=True,
            subscribe_id=sid,
            message=text or MESSAGE_ADDED,
            reason=precheck_error and f"复查失败但写入成功（{precheck_error}）" or "",
        )

    # ------------------------------------------------------------------ 额度

    def _remaining_budget(self, already_written_today: int) -> int:
        """返回今日剩余可写入条数；``daily_limit<=0`` 表示不限制（返回极大值）。"""
        if self._daily_limit <= 0:
            return 10 ** 6
        try:
            used = max(0, int(already_written_today))
        except (TypeError, ValueError):
            used = 0
        return max(0, self._daily_limit - used)


__all__ = [
    "MESSAGE_ADDED",
    "MESSAGE_EXISTS",
    "HOST_SOURCE_TMDB",
    "SubscribeBackend",
    "SubscriptionWriter",
    "WriteOutcome",
    "WriteReport",
]
