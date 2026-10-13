"""推送任务入队（监控流水线与缓存回搜共用）。

两条链路都会产出推送任务：监控决策命中、缓存回搜命中。任务表结构一致，
因此把「组 payload + 落库」这段抽成公共函数，避免两处漂移。

负载结构：``{"links": [...], "text": "...", "title": "..."}``（destination
实现只依赖这三项）。
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from app.sdk.logging import logger

from ..model.push_task import STATUS_PENDING, TgPushTask


def enqueue_push(
    db: Any,
    plugin_id: str,
    *,
    rule_id: str,
    chat_id: int,
    message_id: int,
    destination: str,
    target_id: str = "",
    links: Optional[List[str]] = None,
    text: str = "",
    title: str = "",
) -> Optional[int]:
    """写入一条待推送任务，返回任务 ID；失败返回 None。"""
    if db is None:
        return None
    payload = {
        "links": list(links or []),
        "text": str(text or "")[:4000],
        "title": str(title or "")[:250],
    }
    try:
        with db.session() as session:
            task = TgPushTask(
                plugin_id=str(plugin_id or "")[:64],
                rule_id=str(rule_id or "")[:64],
                chat_id=int(chat_id or 0),
                message_id=int(message_id or 0),
                destination=str(destination or "smart")[:32],
                target_id=str(target_id or "")[:64],
                payload=json.dumps(payload, ensure_ascii=False),
                status=STATUS_PENDING,
            )
            session.add(task)
            session.commit()
            return int(task.id)
    except Exception as err:
        logger.warning(f"推送任务入队失败：{err}")
        return None
