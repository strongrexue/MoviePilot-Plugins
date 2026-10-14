"""P9 前向闸门的「首次发现缺失」锚点表。

闸门 A 的成熟期（T）需要一个「这部作品从什么时候开始缺」的时间锚点。插件
自记（规格 §12 决策 3）：只在「仅缺失」判定为媒体库缺失时登记 / 刷新，
媒体库确认已有后清除该键。键为**季粒度**（归一片名|年份|类型|季）——
MP 的下载与订阅都以季为单位，"PT 拿到没有"是季级事实（规格 §12 决策 2）。

表体积 = 用户关注的作品数量级，可忽略；读取方（闸门）会对 90 天未见的
键做惰性清理。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

Base = plugin_declarative_base()


class TgP9Gate(Base):
    """前向闸门的缺失计时锚点（季粒度）。"""

    __tablename__ = "p9_gate"

    # 复合主键：(插件实例, 身份键)，与其它表的 plugin_id 隔离口径一致
    plugin_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 键 = 归一片名|年份|媒体类型|季（缺失季用空串占位），与判定链口径一致
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    # 首次发现媒体库缺失的时间（成熟期 T 的锚点）
    first_missing_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 最近一次确认缺失的时间（诊断用）
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 最近一次闸门结论（决策常量或 pass_*），诊断用
    last_verdict: Mapped[str] = mapped_column(String(64), default="")
