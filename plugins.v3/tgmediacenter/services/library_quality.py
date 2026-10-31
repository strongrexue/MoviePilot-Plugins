"""媒体库画质探测（1.13.35）。

宿主的 ``MediaServerItem`` 不带画质字段，Emby 客户端的 ``get_items`` 也不请求
``MediaSources``，所以这里直接按「已同步的条目 id」向媒体服务器要单条/整剧明细——
只读、不扫盘、不转码；``MediaSources`` 是媒体服务器自己库里的元数据。

成本控制：结果落库缓存（默认 7 天）、只在基线缺失时查询、单请求超时、串行、
失败记否定缓存，绝不在消息主链路上阻塞。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger

from ..model.library_quality import TgLibraryQuality
from . import quality as quality_service

try:  # pragma: no cover - 宿主依赖，测试环境用桩
    from app.sdk.services import MediaServerHelper
    from app.sdk.network import RequestUtils

    MEDIASERVER_AVAILABLE = True
except Exception:  # pragma: no cover
    MediaServerHelper = None  # type: ignore[assignment]
    RequestUtils = None  # type: ignore[assignment]
    MEDIASERVER_AVAILABLE = False

TTL_DAYS = 7
RETRY_FAILED_DAYS = 7
TIMEOUT = 5
_MAX_ROWS = 4000
_VIDEO_CODEC_MAP = {
    "av1": "av1",
    "hevc": "hevc",
    "h265": "hevc",
    "h264": "h264",
    "avc": "h264",
    "vp9": "vp9",
}
_AUDIO_CODEC_MAP = {
    "truehd": "truehd",
    "eac3": "eac3",
    "ac3": "ac3",
    "dts": "dts",
    "flac": "flac",
    "aac": "aac",
    "opus": "opus",
}


def media_key(title: str, year: Any, media_type: str) -> str:
    return "|".join([str(title or "").strip(), str(year or "").strip(), str(media_type or "").strip()])


class LibraryQualityService:
    """按标题取媒体库画质（带库内缓存）。"""

    def __init__(self, db: Any, plugin_id: str) -> None:
        self._db = db
        self._plugin_id = str(plugin_id or "")
        self._lock = threading.Lock()
        self._last_call = 0.0

    # ------------------------------------------------------------------ 读取
    def cached(self, key: str) -> Optional[Dict[str, Any]]:
        """读缓存；未过期返回 profiles，过期/没有返回 None。"""
        row = self._load_row(key)
        if row is None:
            return None
        try:
            payload = json.loads(row.profiles or "{}")
        except Exception:
            return None
        ts = payload.get("ts")
        ttl = RETRY_FAILED_DAYS if payload.get("empty") else TTL_DAYS
        if ts and (datetime.now() - datetime.fromtimestamp(float(ts))) < timedelta(days=ttl):
            return payload.get("episodes") or {}
        return None

    def profiles_for(self, title: str, year: Any, media_type: str) -> Dict[str, Any]:
        """取某部影视的逐集画质；拿不到返回空 dict（调用方按「无基线」处理）。"""
        key = media_key(title, year, media_type)
        cached = self.cached(key)
        if cached is not None:
            return cached
        try:
            episodes, item_id, server = self._fetch(title, year, media_type)
        except Exception as err:  # pragma: no cover - 探测失败不影响主链
            logger.debug(f"媒体库画质探测失败（{title}）：{err}")
            self._store(key, "", "", {}, empty=True)
            return {}
        self._store(key, item_id, server, episodes, empty=not bool(episodes))
        return episodes

    # ------------------------------------------------------------------ 探测
    def _clients(self) -> List[Tuple[str, str, str, str]]:
        if not MEDIASERVER_AVAILABLE:
            return []
        clients: List[Tuple[str, str, str, str]] = []
        try:
            helper = MediaServerHelper()
            for service in helper.iterate_module_instances():
                inst = getattr(service, "instance", None)
                if inst is None:
                    continue
                host = str(getattr(inst, "_host", "") or "").rstrip("/")
                api_key = str(getattr(inst, "_apikey", "") or "")
                user = str(getattr(inst, "user", "") or getattr(inst, "_user", "") or "")
                if host and api_key:
                    clients.append((str(getattr(service, "name", "") or ""), host, api_key, user))
        except Exception as err:  # pragma: no cover
            logger.debug(f"读取媒体服务器实例失败：{err}")
        return clients

    def _fetch(self, title: str, year: Any, media_type: str) -> Tuple[Dict[str, Any], str, str]:
        episodes: Dict[str, Any] = {}
        for name, host, api_key, _user in self._clients():
            base = host if host.rstrip("/").endswith(("emby", "jellyfin")) else host
            item_type = "Series" if str(media_type or "") == "电视剧" else "Movie"
            params = {
                "api_key": api_key,
                "Recursive": "true",
                "IncludeItemTypes": item_type,
                "SearchTerm": str(title or ""),
                "Fields": "Path",
                "Limit": 5,
            }
            if str(year or "").strip():
                params["Years"] = str(year).strip()
            items = self._get(base, "/Items", params)
            if not items:
                continue
            entry = next((it for it in items if str(it.get("Type") or "") == item_type), items[0])
            item_id = str(entry.get("Id") or "")
            if not item_id:
                continue
            if item_type == "Series":
                rows = self._get(base, f"/Shows/{item_id}/Episodes", {
                    "api_key": api_key,
                    "Fields": "MediaSources,Path",
                    "Limit": 500,
                }) or []
                for row in rows:
                    number = row.get("IndexNumber")
                    profile = self._profile_of(row)
                    if profile and number is not None:
                        episodes[str(number)] = profile
            else:
                profile = self._profile_of(entry)
                if profile:
                    episodes["0"] = profile
            if episodes:
                return episodes, item_id, name
        return {}, "", ""

    def _get(self, base: str, path: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        if RequestUtils is None:  # pragma: no cover
            return None
        with self._lock:
            gap = time.time() - self._last_call
            if gap < 0.3:
                time.sleep(0.3 - gap)
            self._last_call = time.time()
        try:
            res = RequestUtils(timeout=TIMEOUT).get_res(f"{base}{path}", params)
        except Exception as err:  # pragma: no cover
            logger.debug(f"媒体服务器请求失败（{path}）：{err}")
            return None
        if res is None or getattr(res, "status_code", 0) != 200:
            return None
        try:
            payload = res.json() or {}
        except Exception:  # pragma: no cover
            return None
        items = payload.get("Items")
        return items if isinstance(items, list) else None

    @staticmethod
    def _profile_of(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sources = item.get("MediaSources") or []
        if not sources:
            return None
        source = sources[0] or {}
        path = str(source.get("Path") or item.get("Path") or "")
        # 文件名通常带分辨率/片源，直接复用质量解析器
        profile = quality_service.parse_quality(path)
        streams = source.get("MediaStreams") or []
        video = next((s for s in streams if str(s.get("Type") or "") == "Video"), None)
        audio = next((s for s in streams if str(s.get("Type") or "") == "Audio"), None)
        if video:
            height = video.get("Height")
            try:
                height_int = int(height)
            except (TypeError, ValueError):
                height_int = 0
            if height_int >= 2000:
                profile["resolution"] = "2160p"
            elif height_int >= 1000:
                profile["resolution"] = "1080p"
            elif height_int >= 700:
                profile["resolution"] = "720p"
            codec = _VIDEO_CODEC_MAP.get(str(video.get("Codec") or "").lower())
            if codec:
                profile["codec"] = codec
            effect = str(video.get("VideoRangeType") or video.get("VideoRange") or "").upper()
            if "DOLBY" in effect or "DOVI" in effect or effect == "DV":
                profile["effect"] = "dv"
            elif "HDR10+" in effect:
                profile["effect"] = "hdr10p"
            elif "HDR10" in effect:
                profile["effect"] = "hdr10"
            elif "HDR" in effect:
                profile["effect"] = "hdr"
        if audio:
            codec = _AUDIO_CODEC_MAP.get(str(audio.get("Codec") or "").lower())
            if codec:
                profile["audio"] = codec
        try:
            size = int(source.get("Size") or 0)
        except (TypeError, ValueError):
            size = 0
        if size:
            profile["size_mb"] = round(size / 1024 / 1024, 1)
        profile["known"] = bool(profile.get("resolution"))
        return profile

    # ------------------------------------------------------------------ 存储
    def _load_row(self, key: str) -> Optional[TgLibraryQuality]:
        if self._db is None:
            return None
        try:
            with self._db.session() as session:
                return (
                    session.query(TgLibraryQuality)
                    .filter(TgLibraryQuality.plugin_id == self._plugin_id)
                    .filter(TgLibraryQuality.media_key == key)
                    .first()
                )
        except Exception as err:  # pragma: no cover
            logger.debug(f"读取媒体库画质缓存失败：{err}")
            return None

    def _store(self, key: str, item_id: str, server: str, episodes: Dict[str, Any], *, empty: bool) -> None:
        if self._db is None:
            return
        payload = json.dumps(
            {"ts": time.time(), "empty": bool(empty), "episodes": episodes},
            ensure_ascii=False,
        )
        try:
            with self._db.session() as session:
                row = (
                    session.query(TgLibraryQuality)
                    .filter(TgLibraryQuality.plugin_id == self._plugin_id)
                    .filter(TgLibraryQuality.media_key == key)
                    .first()
                )
                if row is None:
                    row = TgLibraryQuality(plugin_id=self._plugin_id, media_key=key)
                    session.add(row)
                row.server = str(server or "")[:64]
                row.item_id = str(item_id or "")[:64]
                row.profiles = payload
                row.updated_at = datetime.now()
                session.commit()
                self._prune(session)
        except Exception as err:  # pragma: no cover
            logger.debug(f"写入媒体库画质缓存失败：{err}")

    def _prune(self, session: Any) -> None:
        try:
            count = (
                session.query(TgLibraryQuality)
                .filter(TgLibraryQuality.plugin_id == self._plugin_id)
                .count()
            )
            if count <= _MAX_ROWS:
                return
            olds = (
                session.query(TgLibraryQuality)
                .filter(TgLibraryQuality.plugin_id == self._plugin_id)
                .order_by(TgLibraryQuality.updated_at.asc())
                .limit(count - _MAX_ROWS)
                .all()
            )
            for row in olds:
                session.delete(row)
            session.commit()
        except Exception:  # pragma: no cover
            pass
