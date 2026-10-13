"""④ TG 资源监控 / ⑥ 通用转发：命中与推送流水表。

每一条被监控或转发规则处理过的消息都会落一行（含被跳过的），用于：
- 前端「命中流水」展示与复盘；
- 同一条消息不重复处理（唯一键 plugin_id + rule_id + chat_id + message_id）。

规则本身存在配置里（``monitor_rules`` / ``forward_rules``，随配置表单整份保存），
本表只记流水。``kind`` 区分来源（``monitor`` / ``forward``）：两套规则的 id 各自
独立生成，前端流水与统计按 kind 分栏展示。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

Base = plugin_declarative_base()

# 决策取值（与前端展示一一对应）
# 说明：同规则同消息的重复事件不记流水（去重唯一键与首条冲突），只计统计，
# 因此不存在 skipped_duplicate 决策。
DECISION_HIT = "hit"                      # 命中且判定应推送（已入推送队列）
DECISION_SKIPPED_NOT_MISSING = "skipped_not_missing"    # 识别成功但媒体库/订阅显示不缺
DECISION_SKIPPED_NOT_SUBSCRIBED = "skipped_not_subscribed"  # 仅缺失开启且未订阅（方案 A 门禁）
DECISION_SKIPPED_UNRECOGNIZED = "skipped_unrecognized"  # 标题无法识别
DECISION_SKIPPED_KEYWORD = "skipped_keyword"            # 自定义关键词未命中
DECISION_SKIPPED_NO_LINK = "skipped_no_link"            # 没有可推送的链接
DECISION_SKIPPED_UNKNOWN = "skipped_unknown"            # 无法判断缺失（无媒体服务器/订阅）
DECISION_SKIPPED_EXTENSION = "skipped_extension"        # ⑥ 转发：文件扩展名未命中
DECISION_FAILED = "failed"                # 处理过程出错

# 流水来源（两套规则共用一张表，靠 kind 分栏）
KIND_MONITOR = "monitor"
KIND_FORWARD = "forward"
KINDS = (KIND_MONITOR, KIND_FORWARD)

DECISIONS = (
    DECISION_HIT,
    DECISION_SKIPPED_NOT_MISSING,
    DECISION_SKIPPED_NOT_SUBSCRIBED,
    DECISION_SKIPPED_UNRECOGNIZED,
    DECISION_SKIPPED_KEYWORD,
    DECISION_SKIPPED_NO_LINK,
    DECISION_SKIPPED_UNKNOWN,
    DECISION_SKIPPED_EXTENSION,
    DECISION_FAILED,
)


class TgHitLog(Base):
    """监控命中流水。"""

    __tablename__ = "monitor_hit_log"
    __table_args__ = (
        UniqueConstraint("plugin_id", "rule_id", "chat_id", "message_id",
                         name="uq_monitor_hit_dedupe"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 插件实例标识（分身隔离）
    plugin_id: Mapped[str] = mapped_column(String(64), index=True)
    # 流水来源：monitor（④ 资源监控）/ forward（⑥ 通用转发）
    kind: Mapped[str] = mapped_column(String(16), default=KIND_MONITOR, index=True)
    # 规则身份（配置里的规则在保存时归一分配 id，保证跨版本稳定）
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    rule_name: Mapped[str] = mapped_column(String(128), default="")
    # 消息定位
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    # 识别结果
    title: Mapped[str] = mapped_column(String(255), default="")
    year: Mapped[str] = mapped_column(String(16), default="")
    season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    episode: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str] = mapped_column(String(16), default="")
    # 决策与去向
    decision: Mapped[str] = mapped_column(String(32), index=True)
    destination: Mapped[str] = mapped_column(String(32), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    # 人类可读的原因/结果说明
    detail: Mapped[str] = mapped_column(String(512), default="")
    # 处理时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
