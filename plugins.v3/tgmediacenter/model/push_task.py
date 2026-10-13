"""④ TG 资源监控：推送任务队列表。

决策为 ``hit`` 的消息入队，由推送 worker 按 destination 分派执行：
- ``pan115``：分享链接转存 / 磁力 eD2k 离线（复用 115 模块）；
- ``tg_forward``：把原消息转发到目标会话（受全局冷却约束）；
- ``none``：仅记录（调试用）。

失败重试带指数退避；重试次数用尽标记 failed 并保留错误信息。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

Base = plugin_declarative_base()

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

STATUSES = (STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED)

# 推送 worker 单轮处理的任务数上限（同步接口外的后台线程，仍要克制）
_WORKER_BATCH = 10
# 失败重试上限
MAX_RETRIES = 3


class TgPushTask(Base):
    """监控推送任务。"""

    __tablename__ = "monitor_push_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(64), index=True)
    # 关联规则与消息（与 hit_log 同键，便于追溯）
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    # 注意必须 BigInteger：TG 频道 ID 约 ±1e12，32 位 Integer 会
    # NumericValueOutOfRange 入队失败（1.4.1 真机踩坑，与 hit_log 同口径）
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    # 推送目标与负载
    destination: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[str] = mapped_column(String(64), default="")
    # JSON：{"links": [...], "text": "...", "title": "..."}
    payload: Mapped[str] = mapped_column(Text, default="{}")
    # 状态机
    status: Mapped[str] = mapped_column(String(16), default=STATUS_PENDING, index=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(512), default="")
    # JSON：执行结果摘要
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @staticmethod
    def worker_batch() -> int:
        """worker 单轮最多处理的任务数。"""
        return _WORKER_BATCH

    @staticmethod
    def max_retries() -> int:
        """失败重试上限。"""
        return MAX_RETRIES
