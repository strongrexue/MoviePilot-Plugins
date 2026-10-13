"""⑤ 历史消息缓存表。

把关注频道的消息永久保存在本地，供「订阅触发回搜」检索使用：
- 实时写入：新消息事件到达时，属于缓存频道的消息落库；
- 增量/范围同步：按频道位点 ``last_message_id`` 主动拉取，补齐断线窗口；
- 检索：按归一化标题精确命中，退回全文模糊兜底。

去重唯一键 ``plugin_id + chat_id + message_id`` 让实时写入与增量同步天然幂等
（重复拉到已入库的消息直接跳过，不产生副作用）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

Base = plugin_declarative_base()


class TgMessageCache(Base):
    """历史消息缓存。"""

    __tablename__ = "message_cache"
    __table_args__ = (
        UniqueConstraint("plugin_id", "chat_id", "message_id", name="uq_message_cache_dedupe"),
        Index("ix_message_cache_chat_date", "chat_id", "message_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 插件实例标识（分身隔离）
    plugin_id: Mapped[str] = mapped_column(String(64), index=True)
    # 消息定位
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    message_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    # 正文：净化后的全文（保留原文信息，供全文检索兜底）
    text: Mapped[str] = mapped_column(Text, default="")
    # 可推送链接（JSON 数组字符串）
    links_json: Mapped[str] = mapped_column(Text, default="[]")
    # 识别结果（与监控流水同一套 MetaVideo 口径）
    parsed_title: Mapped[str] = mapped_column(String(255), default="", index=True)
    # 归一化标题（小写去分隔符），检索主键
    title_norm: Mapped[str] = mapped_column(String(255), default="", index=True)
    year: Mapped[str] = mapped_column(String(16), default="")
    season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    episode: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    episode_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str] = mapped_column(String(16), default="")
    resolution: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="")
    # 入库时间（与消息时间区分：重放历史时 message_date 是旧的）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
