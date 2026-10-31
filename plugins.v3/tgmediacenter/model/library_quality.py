"""媒体库画质缓存表（1.13.35）。

一部影视一行：把从媒体服务器拿到的「逐集画质 profile」整体存成 JSON，
避免每集一行、也避免重复向媒体服务器发请求。TTL 到期后按需重取。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

Base = plugin_declarative_base()


class TgLibraryQuality(Base):
    """媒体库画质（按标题 + 年份 + 类型一行）。"""

    __tablename__ = "library_quality"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(64), index=True)
    # 媒体服务器名称（多实例时用于区分）
    server: Mapped[str] = mapped_column(String(64), default="")
    # 媒体服务器条目 id
    item_id: Mapped[str] = mapped_column(String(64), default="")
    # 归一化键：标题|年份|类型
    media_key: Mapped[str] = mapped_column(String(255), index=True)
    # JSON：{"episodes": {"1": {...}, "2": {...}}}，电影用 "0"
    profiles: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
