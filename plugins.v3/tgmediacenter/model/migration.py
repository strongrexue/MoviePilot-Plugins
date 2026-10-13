"""轻量表结构迁移。

随版本推进对**已建表**的存量库补列 / 改类型：模型定义已是最新，这里只负责把
老库追平。每次启动都会跑，全部幂等。

- ``ensure_bigint_columns``：``monitor_push_task`` 的 ``chat_id`` / ``message_id``
  升级为 BIGINT。1.4.1 及以前该表是 32 位 Integer，而 TG 频道 ID（约 ±1e12）
  超出 int32，Postgres 下推送入队直接 ``NumericValueOutOfRange``（1.4.1 真机踩坑）。
- ``ensure_hit_log_columns``：``monitor_hit_log`` 补 ``kind`` 列（1.5.0 起区分
  ``monitor`` / ``forward`` 两种流水来源）、``episode_end`` 列（1.6.3 起记录
  多集区间的结束集）。

任何失败只告警不阻断插件启动。
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.sdk.logging import logger

from .hit_log import TgHitLog
from .push_task import TgPushTask


def ensure_bigint_columns(db: Any) -> None:
    """把 push_task 的 chat_id/message_id 升级为 BIGINT（幂等，可重复调用）。"""
    if db is None:
        return
    table = TgPushTask.__table__
    try:
        from sqlalchemy import inspect as sa_inspect, text

        with db.session() as session:
            conn = session.connection()
            if conn.dialect.name == "sqlite":
                return
            insp = sa_inspect(conn)
            cols = {
                c["name"]: c
                for c in insp.get_columns(table.name, schema=table.schema or None)
            }
            qualified = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
            altered = []
            for column in ("chat_id", "message_id"):
                info = cols.get(column)
                if info is None:
                    continue
                if "BIGINT" in str(info.get("type", "")).upper():
                    continue
                session.execute(text(f"ALTER TABLE {qualified} ALTER COLUMN {column} TYPE BIGINT"))
                altered.append(column)
            if altered:
                session.commit()
                logger.info(f"[push_task 迁移] 已升级为 BIGINT：{', '.join(altered)}")
    except Exception as err:
        logger.warning(f"[push_task 迁移] 表结构检查/升级失败（不阻断启动）：{err}")


# monitor_hit_log 需要补列的存量库：列名 -> 建列 SQL 片段
_HIT_LOG_ADDED_COLUMNS: Dict[str, str] = {
    "kind": "VARCHAR(16) NOT NULL DEFAULT 'monitor'",
    # 1.6.3：多集区间（S01E05-E06）的结束集，媒体列拼完整名用
    "episode_end": "INTEGER NULL",
}


def ensure_hit_log_columns(db: Any) -> None:
    """给 ``monitor_hit_log`` 补 ``kind`` 列（1.5.0 起区分监控 / 转发流水，幂等）。"""
    _ensure_columns(db, TgHitLog, _HIT_LOG_ADDED_COLUMNS)


def _ensure_columns(db: Any, model: Any, specs: Dict[str, str]) -> None:
    """按 ``specs`` 给表补缺失的列（已存在则跳过；表未建则跳过）。"""
    if db is None or not specs:
        return
    table = model.__table__
    try:
        from sqlalchemy import inspect as sa_inspect, text

        with db.session() as session:
            conn = session.connection()
            insp = sa_inspect(conn)
            if not insp.has_table(table.name, schema=table.schema or None):
                return
            existing = {
                column["name"]
                for column in insp.get_columns(table.name, schema=table.schema or None)
            }
            qualified = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
            added: List[str] = []
            for column, ddl in specs.items():
                if column in existing:
                    continue
                session.execute(text(f"ALTER TABLE {qualified} ADD COLUMN {column} {ddl}"))
                added.append(column)
            if added:
                session.commit()
                logger.info(f"[{table.name} 迁移] 已补列：{', '.join(added)}")
    except Exception as err:
        logger.warning(f"[{table.name} 迁移] 表结构检查/补列失败（不阻断启动）：{err}")


def ensure_schema(db: Any) -> None:
    """统一入口：把存量库追平到当前模型（每次启动调用，幂等）。"""
    ensure_bigint_columns(db)
    ensure_hit_log_columns(db)
