"""轻量表结构迁移。

只做一件事：把 ``monitor_push_task`` 的 ``chat_id`` / ``message_id`` 升级为
BIGINT。1.4.1 及以前该表是 32 位 Integer，而 TG 频道 ID（约 ±1e12）超出
int32，Postgres 下推送入队直接 ``NumericValueOutOfRange``（1.4.1 真机踩坑）。
模型已改为 BigInteger；这里给**已建表**的存量库补 ``ALTER COLUMN``。

- SQLite 类型宽松，跳过（也无 ALTER COLUMN 语法）；
- 已是 BIGINT 时跳过，避免无谓的表重写；
- 任何失败只告警不阻断插件启动。
"""
from __future__ import annotations

from typing import Any

from app.sdk.logging import logger

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
