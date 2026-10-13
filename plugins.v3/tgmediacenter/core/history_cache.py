"""⑤ 历史消息缓存：写入、同步、检索与统计。

职责边界
--------
- 本文件只碰「缓存」本身：落库、按位点增量拉取、时间范围回溯、检索、统计；
- 订阅触发回搜（拿订阅标题去缓存里找资源并入推送队列）在
  ``modules/cache.py``，因为那一步需要缺失判断与推送编排；
- 拉取走 Telegram 运行时（``core/runtime.py``），每批一次协程调用，
  批次之间在同步线程里 sleep，既能让出控制权，也天然避开 FloodWait。

位点
----
每频道 ``last_message_id`` 存在插件数据（``save_data``）里，数据量很小：
- 实时写入时同步推进位点（避免增量同步把已入库的再拉一遍）；
- 增量同步从位点之后开始，中断后再点「更新缓存」即从断点继续。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core import links as link_utils
from ..model.message_cache import TgMessageCache
from ..services import recognizer as recognizer_service
from ..services.matcher import _normalize_title

# 位点在插件数据里的键
CURSOR_KEY = "cache_cursor"
# 同步模式
MODE_ALL = "all"          # 所有消息
MODE_RELATIVE = "relative"  # 相对时间（最近 N 天）
MODE_ABSOLUTE = "absolute"  # 绝对时间范围
SYNC_MODES = (MODE_ALL, MODE_RELATIVE, MODE_ABSOLUTE)

# 单批拉取条数：过大会在一次请求里塞太多（易触发 FloodWait），过小则轮次太多
DEFAULT_BATCH = 200
# 批次之间的让出间隔（秒）
_BATCH_SLEEP = 0.8
# 单批拉取的协程超时（秒）
_FETCH_TIMEOUT = 90
# 同步线程内连续失败的最大轮次（防死循环）
_MAX_FETCH_FAILURES = 3


def to_naive_utc(value: Any) -> Optional[datetime]:
    """把任意时间归一为 UTC 无时区 datetime（库内统一口径）。"""
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def now_utc() -> datetime:
    """当前 UTC 无时区时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_title(value: Any) -> str:
    """标题归一化（与缺失判断同一套规则，保证检索与订阅匹配口径一致）。"""
    return _normalize_title(value)


class HistoryCacheService:
    """消息缓存的读写与同步。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._state: Dict[str, Any] = {
            "running": False,
            "chat_id": 0,
            "mode": "",
            "processed": 0,
            "inserted": 0,
            "started_at": "",
            "finished_at": "",
            "last_error": "",
        }

    # ------------------------------------------------------------------ 基础

    def _plugin_id(self) -> str:
        return getattr(self._plugin, "__class__").__name__ or "TgMediaCenter"

    def _db(self):
        return getattr(self._plugin, "get_database", lambda: None)()

    def _get_data(self, key: str, default: Any = None) -> Any:
        try:
            value = self._plugin.get_data(key)
            return default if value is None else value
        except Exception:  # pragma: no cover - 宿主接口缺失
            return default

    def _save_data(self, key: str, value: Any) -> None:
        try:
            self._plugin.save_data(key, value)
        except Exception as err:  # pragma: no cover
            logger.debug(f"写入插件数据失败（{key}）：{err}")

    # ------------------------------------------------------------------ 位点

    def cursors(self) -> Dict[int, int]:
        """读取全部频道位点（chat_id → last_message_id）。"""
        raw = self._get_data(CURSOR_KEY, {}) or {}
        result: Dict[int, int] = {}
        if not isinstance(raw, dict):
            return result
        for key, value in raw.items():
            try:
                result[int(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return result

    def cursor_of(self, chat_id: int) -> int:
        return int(self.cursors().get(int(chat_id), 0) or 0)

    def set_cursor(self, chat_id: int, message_id: int) -> None:
        """推进位点（只前进，不后退，避免并发写入把位点拉回去）。"""
        cursors = self.cursors()
        chat = int(chat_id)
        current = int(cursors.get(chat, 0) or 0)
        if int(message_id) <= current:
            return
        cursors[chat] = int(message_id)
        self._save_data(CURSOR_KEY, {str(key): value for key, value in cursors.items()})

    def drop_cursors(self, chat_ids: List[int]) -> None:
        cursors = self.cursors()
        for chat_id in chat_ids:
            cursors.pop(int(chat_id), None)
        self._save_data(CURSOR_KEY, {str(key): value for key, value in cursors.items()})

    # ------------------------------------------------------------------ 写入

    def record(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        message_date: Any = None,
        cleaned: Optional[str] = None,
        meta: Optional[dict] = None,
        links: Optional[List[str]] = None,
    ) -> bool:
        """写入一条缓存（幂等：重复消息直接跳过）。

        :param cleaned: 已净化的正文；缺省时内部净化。
        :param meta: 已识别的元信息；缺省时内部识别（历史同步走这条）。
        :param links: 已提取的链接；缺省时内部解析。
        """
        db = self._db()
        if db is None:
            return False
        body = str(text or "")
        if not body.strip():
            return False
        if cleaned is None:
            cleaned = recognizer_service.purify_text(body)
        if meta is None:
            meta = recognizer_service.recognize(body)
        if links is None:
            parsed = link_utils.parse_push_text(body)
            links = [item.raw or item.url for item in parsed.items if item.supported]
        # 净化后为空说明整条都是广告行：仍缓存原文，避免检索时找不到
        stored_text = cleaned or body
        inserted = self._insert_rows([self._row(
            chat_id=int(chat_id),
            message_id=int(message_id),
            message_date=to_naive_utc(message_date) or now_utc(),
            text=stored_text,
            links=links,
            meta=meta,
        )])
        if inserted:
            self.set_cursor(chat_id, message_id)
        return bool(inserted)

    def _row(self, *, chat_id: int, message_id: int, message_date: Optional[datetime],
             text: str, links: List[str], meta: Optional[dict]) -> TgMessageCache:
        title = str((meta or {}).get("title") or "")[:255]
        return TgMessageCache(
            plugin_id=self._plugin_id(),
            chat_id=int(chat_id),
            message_id=int(message_id),
            message_date=message_date,
            text=str(text or "")[:20000],
            links_json=json.dumps(list(links or []), ensure_ascii=False)[:4000],
            parsed_title=title,
            title_norm=normalize_title(title)[:255],
            year=str((meta or {}).get("year") or "")[:16],
            season=(meta or {}).get("season"),
            episode=(meta or {}).get("episode"),
            episode_end=(meta or {}).get("episode_end"),
            media_type=str((meta or {}).get("media_type") or "")[:16],
            resolution=str((meta or {}).get("resource_pix") or (meta or {}).get("resource_type") or "")[:32],
            source=str((meta or {}).get("resource_type") or "")[:32],
        )

    def _insert_rows(self, rows: List[TgMessageCache]) -> int:
        """批量插入（先剔除已存在的 message_id，保证幂等且不刷错误日志）。"""
        if not rows:
            return 0
        db = self._db()
        if db is None:
            return 0
        plugin_id = self._plugin_id()
        try:
            from sqlalchemy import select

            chat_id = int(rows[0].chat_id)
            ids = [int(row.message_id) for row in rows]
            with db.session() as session:
                existing = set()
                for chunk in _chunks(ids, 500):
                    found = session.execute(
                        select(TgMessageCache.message_id).where(
                            TgMessageCache.plugin_id == plugin_id,
                            TgMessageCache.chat_id == chat_id,
                            TgMessageCache.message_id.in_(chunk),
                        )
                    ).scalars().all()
                    existing.update(int(item) for item in found)
                fresh = [row for row in rows if int(row.message_id) not in existing]
                if not fresh:
                    return 0
                session.add_all(fresh)
                session.commit()
                return len(fresh)
        except Exception as err:
            logger.warning(f"写入消息缓存失败（chat={rows[0].chat_id if rows else ''}）：{err}")
            return 0

    # ------------------------------------------------------------------ 同步

    def is_syncing(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def progress(self) -> dict:
        with self._lock:
            return dict(self._state)

    def start_sync(self, chat_ids: List[int], *, mode: str = MODE_ALL, days: int = 30,
                   start: Any = None, end: Any = None, runtime: Any = None,
                   batch: int = DEFAULT_BATCH) -> dict:
        """在后台线程启动同步（同一时间只允许一个同步任务）。"""
        targets = [int(chat_id) for chat_id in (chat_ids or [])]
        if not targets:
            return {"started": False, "message": "未选择要缓存的频道"}
        if self.is_syncing():
            return {"started": False, "message": "已有缓存同步任务在进行中"}
        if runtime is None or getattr(runtime, "client", None) is None:
            return {"started": False, "message": "TG 未连接，无法拉取历史消息（请先到「TG 凭证」页连接）"}
        self._cancel.clear()
        with self._lock:
            self._state.update({
                "running": True,
                "chat_id": 0,
                "mode": str(mode or MODE_ALL),
                "processed": 0,
                "inserted": 0,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": "",
                "last_error": "",
            })
        self._thread = threading.Thread(
            target=self._run_sync,
            args=(targets, str(mode or MODE_ALL), int(days or 30), start, end, runtime, int(batch or DEFAULT_BATCH)),
            name="tgmc.cache.sync",
            daemon=True,
        )
        self._thread.start()
        return {"started": True, "message": f"已开始同步 {len(targets)} 个频道"}

    def request_cancel(self) -> None:
        self._cancel.set()

    def _run_sync(self, targets: List[int], mode: str, days: int, start: Any, end: Any,
                  runtime: Any, batch: int) -> None:
        """同步线程主体：逐频道按位点拉取。"""
        since, until = self._time_window(mode, days, start, end)
        try:
            for chat_id in targets:
                if self._cancel.is_set():
                    break
                with self._lock:
                    self._state["chat_id"] = int(chat_id)
                try:
                    self._sync_one(runtime, chat_id, since=since, until=until, batch=batch)
                except Exception as err:  # 单频道失败不影响其余频道
                    with self._lock:
                        self._state["last_error"] = f"频道 {chat_id} 同步失败：{err}"
                    logger.warning(f"[{self._plugin_id()}] 缓存同步失败（chat={chat_id}）：{err}")
        finally:
            with self._lock:
                self._state["running"] = False
                self._state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            logger.info(
                f"[{self._plugin_id()}] 缓存同步结束：新增 {self.progress().get('inserted', 0)} 条"
                f"（扫描 {self.progress().get('processed', 0)} 条）"
            )

    @staticmethod
    def _time_window(mode: str, days: int, start: Any, end: Any) -> "tuple[Optional[datetime], Optional[datetime]]":
        """把同步模式翻译成 [since, until] 时间窗口。"""
        if mode == MODE_RELATIVE:
            return now_utc() - timedelta(days=max(1, int(days or 30))), None
        if mode == MODE_ABSOLUTE:
            return _parse_date(start), _parse_date(end, end_of_day=True)
        return None, None

    def _sync_one(self, runtime: Any, chat_id: int, *, since: Optional[datetime],
                  until: Optional[datetime], batch: int) -> None:
        """按位点循环拉取单个频道，直到没有更多消息或越过时间窗口。"""
        cursor = self.cursor_of(chat_id)
        failures = 0
        while not self._cancel.is_set():
            try:
                payload = runtime.call(
                    self._fetch_batch(runtime.client, chat_id, cursor, batch),
                    timeout=_FETCH_TIMEOUT,
                )
            except Exception as err:
                failures += 1
                wait = _flood_wait_seconds(err)
                if wait:
                    logger.info(f"[{self._plugin_id()}] TG 限流，等待 {wait} 秒后继续缓存同步")
                    time.sleep(min(wait + 1, 300))
                    continue
                if failures >= _MAX_FETCH_FAILURES:
                    raise
                logger.warning(f"[{self._plugin_id()}] 拉取历史消息失败（第 {failures} 次）：{err}")
                time.sleep(2)
                continue

            failures = 0
            fetched = payload.get("messages") or []
            if not fetched:
                break
            rows: List[TgMessageCache] = []
            max_id = cursor
            stop = False
            for item in fetched:
                message_id = int(item.get("id") or 0)
                if message_id <= max_id:
                    continue
                max_id = message_id
                if not str(item.get("text") or "").strip():
                    # 与 _fetch_batch 的取舍一致：无正文的消息没有可检索信息。
                    # 位点已推进，不会死循环。
                    continue
                date = to_naive_utc(item.get("date"))
                if until is not None and date is not None and date > until:
                    # 反向遍历（旧→新）：一旦越过上界，后面只会更新，直接收工
                    stop = True
                    break
                if since is not None and date is not None and date < since:
                    # 早于下界：跳过但位点仍推进（避免下次重复扫描）
                    continue
                rows.append(self._row(
                    chat_id=chat_id,
                    message_id=message_id,
                    message_date=date or now_utc(),
                    text=str(item.get("text") or ""),
                    links=item.get("links") or [],
                    meta=item.get("meta"),
                ))
            inserted = self._insert_rows(rows)
            with self._lock:
                self._state["processed"] += len(fetched)
                self._state["inserted"] += int(inserted)
            if max_id > cursor:
                cursor = max_id
                self.set_cursor(chat_id, cursor)
            if stop or len(fetched) < batch:
                break
            time.sleep(_BATCH_SLEEP)

    async def _fetch_batch(self, client: Any, chat_id: int, cursor: int, batch: int) -> dict:
        """拉取一批消息（在 TG 事件循环内执行）。

        纯文本消息才进缓存：无正文的纯媒体消息没有任何可检索信息
        （与监控流水线"纯媒体跳过"的取舍一致）。
        """
        entity = await client.get_entity(int(chat_id))
        messages: List[dict] = []
        async for message in client.iter_messages(
            entity,
            limit=int(batch),
            min_id=int(cursor or 0),
            reverse=True,
        ):
            messages.append(message)
        payload: List[dict] = []
        for message in messages:
            text = str(getattr(message, "message", "") or "")
            if not text.strip():
                continue
            meta = recognizer_service.recognize(text)
            parsed = link_utils.parse_push_text(text)
            payload.append({
                "id": int(getattr(message, "id", 0) or 0),
                "date": getattr(message, "date", None),
                "text": text,
                "meta": meta,
                "links": [item.raw or item.url for item in parsed.items if item.supported],
            })
        return {"messages": payload}

    # ------------------------------------------------------------------ 检索

    def search(self, title: str, *, year: str = "", limit: int = 50,
               chat_ids: Optional[List[int]] = None) -> List[dict]:
        """按标题检索缓存消息：先归一标题命中，再退回全文模糊。

        返回 ``[{"chat_id", "message_id", "title", "year", "season", "episode",
        "text", "links", "message_date"}]``，按消息 ID 倒序（新的在前）。
        """
        keyword = str(title or "").strip()
        if not keyword:
            return []
        norm = normalize_title(keyword)
        db = self._db()
        if db is None:
            return []
        try:
            from sqlalchemy import or_, select

            filters = [TgMessageCache.plugin_id == self._plugin_id()]
            if chat_ids:
                filters.append(TgMessageCache.chat_id.in_([int(item) for item in chat_ids]))
            rows: List[Any] = []
            if norm:
                exact = [TgMessageCache.title_norm == norm]
                if year:
                    exact.append(TgMessageCache.year == str(year))
                with db.session() as session:
                    rows = list(session.execute(
                        select(TgMessageCache)
                        .where(*filters, *exact)
                        .order_by(TgMessageCache.message_id.desc())
                        .limit(int(limit))
                    ).scalars().all())
            if not rows:
                # 全文兜底：标题识别失败的脏消息也能被搜到
                with db.session() as session:
                    rows = list(session.execute(
                        select(TgMessageCache)
                        .where(*filters, or_(
                            TgMessageCache.text.like(f"%{keyword}%"),
                            TgMessageCache.parsed_title.like(f"%{keyword}%"),
                        ))
                        .order_by(TgMessageCache.message_id.desc())
                        .limit(int(limit))
                    ).scalars().all())
            return [self._search_view(row) for row in rows]
        except Exception as err:
            logger.warning(f"检索消息缓存失败：{err}")
            return []

    def search_by_title(self, title: str, *, year: str = "", limit: int = 200,
                        chat_ids: Optional[List[int]] = None) -> List[dict]:
        """订阅回搜专用：归一标题包含匹配（"玉簟秋" 命中 "玉簟秋 S01E03" 这类）。"""
        keyword = str(title or "").strip()
        if not keyword:
            return []
        norm = normalize_title(keyword)
        db = self._db()
        if db is None:
            return []
        try:
            from sqlalchemy import select

            filters = [TgMessageCache.plugin_id == self._plugin_id()]
            if chat_ids:
                filters.append(TgMessageCache.chat_id.in_([int(item) for item in chat_ids]))
            with db.session() as session:
                rows = list(session.execute(
                    select(TgMessageCache)
                    .where(*filters, TgMessageCache.title_norm.like(f"%{norm}%"))
                    .order_by(TgMessageCache.message_id.desc())
                    .limit(int(limit))
                ).scalars().all())
            return [self._search_view(row) for row in rows]
        except Exception as err:
            logger.warning(f"按标题检索消息缓存失败：{err}")
            return []

    @staticmethod
    def _search_view(row: Any) -> dict:
        date = getattr(row, "message_date", None)
        return {
            "chat_id": int(getattr(row, "chat_id", 0) or 0),
            "message_id": int(getattr(row, "message_id", 0) or 0),
            "title": str(getattr(row, "parsed_title", "") or ""),
            "year": str(getattr(row, "year", "") or ""),
            "season": getattr(row, "season", None),
            "episode": getattr(row, "episode", None),
            "episode_end": getattr(row, "episode_end", None),
            "media_type": str(getattr(row, "media_type", "") or ""),
            "text": str(getattr(row, "text", "") or ""),
            "links": _loads_list(getattr(row, "links_json", "") or "[]"),
            "message_date": date.isoformat(timespec="seconds") if date else "",
        }

    # ------------------------------------------------------------------ 维护

    def stats(self, chat_ids: List[int]) -> List[dict]:
        """每个频道的缓存条数与最新消息时间（附带同步位点）。"""
        db = self._db()
        targets = [int(chat_id) for chat_id in (chat_ids or [])]
        cursors = self.cursors()
        if db is None:
            return [self._empty_stat(chat_id, cursors) for chat_id in targets]
        try:
            from sqlalchemy import func, select

            filters = [TgMessageCache.plugin_id == self._plugin_id()]
            if targets:
                filters.append(TgMessageCache.chat_id.in_(targets))
            with db.session() as session:
                rows = session.execute(
                    select(
                        TgMessageCache.chat_id,
                        func.count(TgMessageCache.id),
                        func.max(TgMessageCache.message_date),
                        func.max(TgMessageCache.message_id),
                    )
                    .where(*filters)
                    .group_by(TgMessageCache.chat_id)
                ).all()
            found = {
                int(row[0]): {
                    "chat_id": int(row[0]),
                    "count": int(row[1] or 0),
                    "latest_date": row[2].isoformat(timespec="seconds") if row[2] else "",
                    "latest_message_id": int(row[3] or 0),
                    "cursor": int(cursors.get(int(row[0]), 0) or 0),
                }
                for row in rows
            }
            for chat_id in targets:
                found.setdefault(chat_id, self._empty_stat(chat_id, cursors))
            return [found[chat_id] for chat_id in targets]
        except Exception as err:
            logger.warning(f"统计消息缓存失败：{err}")
            return [self._empty_stat(chat_id, cursors) for chat_id in targets]

    def total_count(self) -> int:
        """缓存总条数（状态卡展示）。"""
        db = self._db()
        if db is None:
            return 0
        try:
            from sqlalchemy import func, select

            with db.session() as session:
                return int(session.execute(
                    select(func.count()).select_from(TgMessageCache)
                    .where(TgMessageCache.plugin_id == self._plugin_id())
                ).scalar() or 0)
        except Exception as err:  # pragma: no cover
            logger.debug(f"统计缓存总条数失败：{err}")
            return 0

    @staticmethod
    def _empty_stat(chat_id: int, cursors: Dict[int, int]) -> dict:
        return {
            "chat_id": int(chat_id),
            "count": 0,
            "latest_date": "",
            "latest_message_id": 0,
            "cursor": int(cursors.get(int(chat_id), 0) or 0),
        }

    def clear(self, chat_ids: List[int]) -> int:
        """清空指定频道的缓存（连同位点），返回删除条数。"""
        db = self._db()
        targets = [int(chat_id) for chat_id in (chat_ids or [])]
        if db is None or not targets:
            return 0
        try:
            from sqlalchemy import delete

            with db.session() as session:
                result = session.execute(
                    delete(TgMessageCache).where(
                        TgMessageCache.plugin_id == self._plugin_id(),
                        TgMessageCache.chat_id.in_(targets),
                    )
                )
                session.commit()
                deleted = int(result.rowcount or 0)
            self.drop_cursors(targets)
            return deleted
        except Exception as err:
            logger.warning(f"清空消息缓存失败：{err}")
            return 0


def _chunks(items: List[int], size: int) -> "List[List[int]]":
    """把列表切成固定大小的块（SQL IN 查询用，避免参数过长）。"""
    return [items[index:index + size] for index in range(0, len(items), size)]


def _loads_list(raw: str) -> List[str]:
    try:
        value = json.loads(raw or "[]")
    except Exception:  # pragma: no cover
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _parse_date(value: Any, *, end_of_day: bool = False) -> Optional[datetime]:
    """解析前端传入的日期（``YYYY-MM-DD`` 或 ISO 时间串）。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if end_of_day and len(text) <= 10:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return to_naive_utc(parsed)


def _flood_wait_seconds(err: BaseException) -> int:
    """Telethon FloodWaitError 的等待秒数（按名字判断，避免具名导入）。"""
    if err.__class__.__name__ != "FloodWaitError":
        return 0
    try:
        return int(getattr(err, "seconds", 0) or 0)
    except Exception:  # pragma: no cover
        return 0
