"""已转存链接台账：记录所有 115 转存成功的链接身份，供私聊交互判重（1.7.5）。

背景：115 的分享转存接口在"同一分享已保存过"时照样返回成功（再存一份），
不像 ed2k / 磁力离线那样会报「任务已存在」——真机实测同一分享链接两天各转一次，
115 里落了两份。本台账在本地补一道判重：所有 115 转存成功（监控规则 / 缓存回搜 /
私聊交互）都记入，私聊转存前先查，命中就不再调 115。

存储纪律：后端自管状态，存 ``save_data``，禁止放配置（保存配置 = 整份覆盖）。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlsplit

from app.sdk.logging import logger

# save_data 键（带版本号，结构变更时换键重起步）
_LEDGER_KEY = "pan115_transfer_ledger_v1"
# 容量与时效：只服务"最近转过没有"的判重，太大只会拖慢每次读写
_LEDGER_MAX_ENTRIES = 1000
_LEDGER_TTL_DAYS = 90


def link_identity(kind: str, url: str = "", code: str = "") -> str:
    """把一条链接归一成判重身份。

    - 115 分享：按分享码（同一分享带不带提取码、走不走镜像域名都是同一条）；
    - 磁力：按 btih 哈希（dn=/追踪器差异不影响身份）；
    - eD2k：按完整链接（含文件名/大小/哈希，小写归一）；
    - 其他：按原文。
    """
    kind = str(kind or "").strip().lower()
    url = str(url or "").strip()
    if kind == "share" or (not kind and code):
        return f"share:{str(code or '').strip().lower()}"
    if kind == "magnet":
        btih = _magnet_btih(url)
        if btih:
            return f"magnet:{btih.lower()}"
        return f"raw:{url.lower()}"
    if kind == "ed2k":
        return f"ed2k:{url.lower()}"
    return f"raw:{url.lower()}"


def _magnet_btih(url: str) -> str:
    """从磁力链里取 btih 哈希（不含 urn: 前缀）。"""
    try:
        parts = urlsplit(url)
        for key in ("xt",):
            for value in parse_qs(parts.query or "").get(key) or []:
                text = str(value or "").strip().lower()
                if text.startswith("urn:btih:"):
                    return text[len("urn:btih:"):]
    except ValueError:
        pass
    return ""


def ed2k_file_name(url: str) -> str:
    """从 eD2k 链接取文件名（结构：ed2k://|file|<名>|<大小>|<哈希>|/）。"""
    text = str(url or "").strip()
    segments = text.split("|")
    if text.lower().startswith("ed2k://") and len(segments) >= 3:
        name = segments[2].strip()
        return name
    return ""


def magnet_file_name(url: str) -> str:
    """从磁力链取显示名：优先 ``dn=`` 参数，退回 btih 前 12 位。"""
    try:
        parts = urlsplit(url)
        for value in parse_qs(parts.query or "").get("dn") or []:
            name = value.strip()
            if name:
                return name
    except ValueError:
        pass
    btih = _magnet_btih(url)
    return f"btih:{btih[:12]}" if btih else ""


def _truncate(label: str, limit: int = 60) -> str:
    """展示名截断（与通知口径一致，避免超长文件名撑爆回执）。"""
    text = str(label or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def record(plugin: Any, entries: Iterable[dict]) -> int:
    """记录转存成功的链接。entry: ``{kind, url, code, label}``；返回新增条数。"""
    if plugin is None:
        return 0
    now = time.time()
    with _lock():
        ledger = _load(plugin)
        added = 0
        for entry in entries or []:
            try:
                key = link_identity(
                    entry.get("kind"), entry.get("url"), entry.get("code")
                )
            except Exception:  # pragma: no cover - 归一失败不拖累主流程
                continue
            if not key or key in ledger:
                continue
            ledger[key] = {
                "label": _truncate(entry.get("label")),
                "at": datetime.now().isoformat(timespec="seconds"),
                "ts": now,
            }
            added += 1
        if not added:
            return 0
        _save(plugin, _prune(ledger))
        return added


def lookup(plugin: Any, identities: List[str]) -> Dict[str, dict]:
    """查台账：返回命中的 ``{identity: {label, at}}``。"""
    if plugin is None or not identities:
        return {}
    with _lock():
        ledger = _load(plugin)
        return {key: ledger[key] for key in identities if key in ledger}


def _load(plugin: Any) -> Dict[str, dict]:
    try:
        data = plugin.get_data(_LEDGER_KEY)
    except Exception:  # pragma: no cover - save_data 异常按空台账处理
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _save(plugin: Any, ledger: Dict[str, dict]) -> None:
    try:
        plugin.save_data(_LEDGER_KEY, ledger)
    except Exception as err:  # pragma: no cover - 写入失败只影响下次判重
        logger.warning(f"[transfer_ledger] 台账写入失败（忽略）：{err}")


def _prune(ledger: Dict[str, dict]) -> Dict[str, dict]:
    """容量与时效裁剪：先按 90 天时效丢过期，再按时间保留最新 N 条。"""
    cutoff = time.time() - _LEDGER_TTL_DAYS * 86400
    kept = {key: value for key, value in ledger.items()
            if float(value.get("ts") or 0) >= cutoff}
    if len(kept) > _LEDGER_MAX_ENTRIES:
        ordered = sorted(kept.items(), key=lambda kv: float(kv[1].get("ts") or 0), reverse=True)
        kept = dict(ordered[: _LEDGER_MAX_ENTRIES])
    return kept


_LOCK = threading.Lock()


def _lock() -> threading.Lock:
    return _LOCK


def stale_days(days: int = _LEDGER_TTL_DAYS) -> timedelta:
    """暴露时效（测试 / 展示用）。"""
    return timedelta(days=days)
