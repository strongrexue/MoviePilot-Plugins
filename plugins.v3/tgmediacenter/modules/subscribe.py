"""③ 订阅服务编排：拉取 → 过滤 → 全局去重 → 建宿主订阅 → 结果汇总。

职责：
- 读取配置里勾选的订阅源（``subscribe_sources``），按通道分发拉取；
- 过滤（评分下限 / 媒体类型）；
- 全局去重（``model.subscribe_seen`` 表）；
- 建宿主订阅（``app.chain.subscribe.SubscribeChain.add``）；
- 汇总结果并写插件数据缓存（供前端「最近抓取结果」展示）。

通知：**不主动发**——建订阅后宿主自带订阅成功通知。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, List, Optional

from app.sdk.logging import logger

from ..core import subscribe_sources as sources_lib
from ..services import douban_source, mp_source

# 最近抓取结果缓存键（插件数据）
_STATE_KEY = "subscribe_state"
# 单次同步调用的总时间预算（秒）：必须小于同步接口的网关超时
_SYNC_DEADLINE_SECONDS = 50
# 单次同步调用处理的条目上限（其余返回 remaining，由前端提示再次点击）
_SYNC_MAX_ITEMS = 60


class SubscribeModule:
    """订阅服务编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin

    # ------------------------------------------------------------------ 配置

    @property
    def _config(self) -> dict:
        return getattr(self._plugin, "config", {}) or {}

    def _cfg(self, key: str, default: Any = None) -> Any:
        value = self._config.get(key)
        return default if value is None else value

    def enabled(self) -> bool:
        return bool(self._cfg("subscribe_enabled"))

    def _rsshub_base(self) -> str:
        return str(self._cfg("subscribe_rsshub_base", "https://rsshub.app") or "").strip().rstrip("/") or "https://rsshub.app"

    def _sources(self) -> List[dict]:
        """读取配置里勾选的订阅源列表（每条含 key/channel/enabled/min_rating/media_type）。"""
        value = self._cfg("subscribe_sources", [])
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _enabled_sources(self, channel: Optional[str] = None) -> List[dict]:
        result = []
        for item in self._sources():
            if not item.get("enabled"):
                continue
            if channel and item.get("channel") != channel:
                continue
            result.append(item)
        return result

    # ------------------------------------------------------------------ 状态缓存

    def _state(self) -> dict:
        data = self._plugin.get_data(_STATE_KEY) or {}
        return data if isinstance(data, dict) else {}

    def _save_state(self, **patch: Any) -> dict:
        merged = self._state()
        merged.update(patch)
        merged["at"] = datetime.now().isoformat(timespec="seconds")
        self._plugin.save_data(_STATE_KEY, merged)
        return merged

    def status(self) -> dict:
        """返回订阅服务状态（不联网，只用配置与缓存）。"""
        state = self._state()
        sources = self._sources()
        return {
            "enabled": self.enabled(),
            "rsshub_base": self._rsshub_base(),
            "sources": sources,
            "mp_count": sum(1 for s in sources if s.get("channel") == "mp" and s.get("enabled")),
            "douban_count": sum(1 for s in sources if s.get("channel") == "douban" and s.get("enabled")),
            "last_sync": str(state.get("at") or ""),
            "last_result": state.get("last_result") if isinstance(state.get("last_result"), dict) else {},
        }

    # ------------------------------------------------------------------ 数据库

    def _db(self):
        return self._plugin.get_database()

    def _is_seen(self, unique_key: str) -> bool:
        """查全局去重表是否已处理过该唯一键。"""
        from sqlalchemy import select

        from ..model.subscribe_seen import SubscribeSeen

        try:
            # 注意：PluginDatabaseHandle.session 是**方法**（def session(self)），
            # 必须调用后把返回的 Session 当上下文管理器（SQLAlchemy 2.0 退出时自动 close）
            with self._db().session() as session:
                row = session.execute(
                    select(SubscribeSeen.id).where(SubscribeSeen.unique_key == unique_key)
                ).first()
                return row is not None
        except Exception as err:  # pragma: no cover - 表未建等异常按未处理
            logger.warning(f"查询订阅去重表失败：{err}")
            return False

    def _mark_seen(
        self,
        *,
        channel: str,
        source_key: str,
        unique_key: str,
        title: str,
        media_source: str,
        media_id: str,
        status: str,
    ) -> None:
        """写入去重表。"""
        from ..model.subscribe_seen import SubscribeSeen

        plugin_id = self._plugin.__class__.__name__
        try:
            with self._db().session() as session:
                session.add(SubscribeSeen(
                    plugin_id=plugin_id,
                    channel=channel,
                    source_key=source_key,
                    unique_key=unique_key,
                    title=str(title or "")[:250],
                    media_source=str(media_source or "")[:30],
                    media_id=str(media_id or "")[:60],
                    status=str(status or "created")[:16],
                ))
                session.commit()
        except Exception as err:  # pragma: no cover
            logger.warning(f"写订阅去重表失败：{err}")

    # ------------------------------------------------------------------ 建订阅

    def _subscribe(self, item: dict) -> tuple[bool, str, str, str]:
        """建宿主订阅，返回 ``(成功, 说明, media_source, media_id)``。

        用**同步版 ``add()``** 直接调用——宿主同步插件（如豆瓣榜单订阅）的标准用法；
        ``async_add`` 是给宿主异步 API 层用的，放到我们自己起的事件循环里会和
        宿主的 DB 会话/运行时状态打架。
        """
        from app.chain.subscribe import SubscribeChain
        from app.schemas.types import MediaSource, MediaType

        title = str(item.get("title") or "").strip()
        year = str(item.get("year") or "").strip()
        if not title:
            return False, "缺少标题", "", ""

        # 媒体类型归一
        media_type_name = str(item.get("media_type") or "")
        mtype = None
        if media_type_name in ("电影", "movie", "Movie"):
            mtype = MediaType.MOVIE
        elif media_type_name in ("电视剧", "tv", "TV", "animation", "动画"):
            mtype = MediaType.TV

        # 媒体来源与 ID
        media_source = None
        media_id = ""
        if item.get("tmdb_id"):
            media_source = MediaSource.TMDB
            media_id = str(item["tmdb_id"])
        elif item.get("douban_id"):
            media_source = MediaSource.Douban
            media_id = str(item["douban_id"])
        elif item.get("bangumi_id"):
            media_source = MediaSource.Bangumi
            media_id = str(item["bangumi_id"])

        try:
            subscribe_id, message = SubscribeChain().add(
                title=title,
                year=year,
                mtype=mtype,
                media_source=media_source,
                media_id=media_id,
                exist_ok=True,
                message=True,
                username="订阅服务",
            )
        except Exception as err:  # pragma: no cover
            return False, f"建订阅异常：{err}", str(media_source) if media_source else "", media_id

        source_value = str(media_source) if media_source else ""
        if subscribe_id:
            return True, "已创建订阅", source_value, media_id
        # 无 subscribe_id 但有说明（如"已存在"）
        return False, str(message or "订阅失败"), source_value, media_id

    # ------------------------------------------------------------------ 过滤

    def _pass_filter(self, item: dict, source_cfg: dict) -> tuple[bool, str]:
        """过滤：评分下限 + 媒体类型。返回 ``(通过, 跳过原因)``。"""
        min_rating = _to_float(source_cfg.get("min_rating"))
        if min_rating > 0:
            rating = _to_float(item.get("vote_average"))
            if rating <= 0:
                return False, "无评分"
            if rating < min_rating:
                return False, f"评分 {rating} 低于 {min_rating}"
        want_type = str(source_cfg.get("media_type") or "all")
        if want_type not in ("", "all"):
            got = str(item.get("media_type") or "")
            if not _type_match(want_type, got):
                return False, f"类型 {got} 不匹配"
        return True, ""

    # ------------------------------------------------------------------ 同步

    def sync(self, channel: Optional[str] = None, dry_run: bool = False) -> dict:
        """同步订阅源：拉取、过滤、去重、建订阅。

        :param channel: 仅同步指定通道（mp / douban），None 表示全部
        :param dry_run: 只拉取解析，不建订阅（用于测试）
        """
        sources = self._enabled_sources(channel)
        result: dict[str, Any] = {
            "total_sources": len(sources),
            "hit": 0,        # 命中（拉取到的条目数）
            "created": 0,    # 新建订阅
            "skipped": 0,    # 跳过（已存在/过滤/已处理）
            "failed": 0,     # 失败
            "remaining": 0,  # 超预算未处理
            "results": [],   # 逐条结果（截断）
            "message": "",
        }

        if not sources:
            result["message"] = "未启用任何订阅源"
            return result

        deadline = time.monotonic() + _SYNC_DEADLINE_SECONDS
        processed = 0
        proxy = self._resolve_proxy()

        for source_cfg in sources:
            source_key = str(source_cfg.get("key") or "")
            source_def = sources_lib.lookup(source_key)
            if source_def is None:
                logger.warning(f"未知订阅源 key：{source_key}")
                continue
            if time.monotonic() > deadline or processed >= _SYNC_MAX_ITEMS:
                break

            # 拉取
            try:
                if source_def.channel == "mp":
                    items = mp_source.fetch_mp_source(source_key, page=1, count=30)
                else:
                    items = douban_source.fetch_douban_source(source_def, self._rsshub_base(), proxy=proxy)
            except Exception as err:  # pragma: no cover
                logger.warning(f"拉取订阅源 {source_key} 失败：{err}")
                result["failed"] += 1
                continue

            for item in items:
                if time.monotonic() > deadline or processed >= _SYNC_MAX_ITEMS:
                    break
                result["hit"] += 1
                processed += 1

                title = str(item.get("title") or "")
                ok, skip_reason = self._pass_filter(item, source_cfg)
                if not ok:
                    result["skipped"] += 1
                    _append_result(result, title, False, skip_reason)
                    continue

                unique_key = _unique_key(item)
                if self._is_seen(unique_key):
                    result["skipped"] += 1
                    _append_result(result, title, False, "已处理过")
                    continue

                if dry_run:
                    result["skipped"] += 1
                    _append_result(result, title, True, "解析成功（仅测试）")
                    continue

                ok_sub, msg, media_source, media_id = self._subscribe(item)
                if ok_sub:
                    result["created"] += 1
                    self._mark_seen(
                        channel=source_def.channel, source_key=source_key,
                        unique_key=unique_key, title=title,
                        media_source=media_source, media_id=media_id, status="created",
                    )
                else:
                    # "已存在" 也记去重，避免重复尝试
                    result["skipped"] += 1
                    self._mark_seen(
                        channel=source_def.channel, source_key=source_key,
                        unique_key=unique_key, title=title,
                        media_source=media_source, media_id=media_id, status="skipped",
                    )
                _append_result(result, title, ok_sub, msg)

        result["remaining"] = 0
        result["message"] = (
            f"同步完成：命中 {result['hit']}，新建 {result['created']}，"
            f"跳过 {result['skipped']}，失败 {result['failed']}"
        )
        if processed >= _SYNC_MAX_ITEMS:
            result["message"] += "（已达单次上限，可再次点击继续）"

        # 写状态缓存（前端「最近抓取结果」）
        self._save_state(last_result={
            "hit": result["hit"],
            "created": result["created"],
            "skipped": result["skipped"],
            "failed": result["failed"],
            "results": result["results"][:50],
        })
        return result

    def _resolve_proxy(self) -> Optional[bool]:
        """豆瓣 RSS 是否走代理（沿用宿主设置）。"""
        try:
            from app.sdk.config import settings
        except Exception:  # pragma: no cover
            return False
        try:
            proxies = getattr(settings, "PROXY", None)
        except Exception:  # pragma: no cover
            return False
        return bool(proxies)


# ------------------------------------------------------------------ 辅助

def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _type_match(want: str, got: str) -> bool:
    """媒体类型匹配（宽容：电影 vs 剧集/动画）。"""
    want_l = str(want).lower()
    got_l = str(got).lower()
    if want_l == "movie":
        return got_l in ("movie", "电影", "movie")
    if want_l in ("tv", "animation"):
        return got_l in ("tv", "电视剧", "animation", "动画", "剧集")
    return True


def _unique_key(item: dict) -> str:
    from ..model.subscribe_seen import SubscribeSeen

    return SubscribeSeen.build_unique_key(
        douban_id=item.get("douban_id") or None,
        tmdb_id=item.get("tmdb_id") or None,
        bangumi_id=item.get("bangumi_id") or None,
        title=str(item.get("title") or ""),
        year=str(item.get("year") or ""),
        media_type=str(item.get("media_type") or ""),
    )


def _append_result(result: dict, title: str, ok: bool, message: str) -> None:
    if len(result["results"]) < 50:
        result["results"].append({"title": str(title or "")[:120], "ok": ok, "message": str(message or "")})
