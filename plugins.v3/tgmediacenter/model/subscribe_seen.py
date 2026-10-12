"""③ 订阅服务的全局去重表。

跨源、跨 Tab、跨抓取周期只处理一次：同一部片，无论先被 MP 榜单还是豆瓣榜单
命中，后到的都跳过。唯一键 ``unique_key`` 优先取宿主媒体 ID（豆瓣 ID / tmdbid /
bangumiid），无 ID 时退化为 ``title+year+media_type`` 的规范化哈希。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

Base = plugin_declarative_base()


class SubscribeSeen(Base):
    """订阅服务去重记录。"""

    __tablename__ = "subscribe_seen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 插件实例标识（虚拟分身隔离）
    plugin_id: Mapped[str] = mapped_column(String(64), index=True)
    # 数据源通道：mp / douban
    channel: Mapped[str] = mapped_column(String(16))
    # 订阅源 key（见 core/subscribe_sources.py）
    source_key: Mapped[str] = mapped_column(String(64))
    # 全局唯一键（见模块说明）
    unique_key: Mapped[str] = mapped_column(String(255), unique=True)
    # 标题（仅展示用）
    title: Mapped[str] = mapped_column(String(255), default="")
    # 宿主媒体身份（建订阅后回填，供追溯）
    media_source: Mapped[str] = mapped_column(String(32), default="")
    media_id: Mapped[str] = mapped_column(String(64), default="")
    # 处理结果：created / skipped / failed
    status: Mapped[str] = mapped_column(String(16), default="created")
    # 首次见到时间
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @staticmethod
    def build_unique_key(
        *,
        douban_id: Optional[str] = None,
        tmdb_id: Optional[str] = None,
        bangumi_id: Optional[str] = None,
        title: str = "",
        year: str = "",
        media_type: str = "",
    ) -> str:
        """生成全局唯一键（供写入与查询共用，保证口径一致）。"""
        if douban_id:
            return f"douban:{douban_id}"
        if tmdb_id:
            return f"tmdb:{tmdb_id}"
        if bangumi_id:
            return f"bangumi:{bangumi_id}"
        # 无宿主 ID 时退化为标题+年份+类型的规范化哈希
        import hashlib

        normalized = f"{title}|{year}|{media_type}".strip().casefold()
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
        return f"title:{digest}"
