"""P9 前向闸门 A：TG 推送前判断「PT 路是否已经在管」。

背景与完整规格见 ``.workbuddy/P9_判定链规格.md``。核心判定链（在「仅缺失」
确认媒体库缺失**之后**执行，顺序不可换——``media_exists`` 是最硬的终点真相）：

    A0 总开关（默认关 = 完全维持现状）
    A1 媒体库已有？——上游「仅缺失」刚查过，这里只承接结论，不重复查询
    A2 订阅桥 → 查下载历史（近 T）
         · 查询不可用 → 放行（fail-open）+ WARNING，绝不静默拦截
         · 无记录 → A4' 成熟期：未满 T 等待（skipped_pt_waiting），满了放行
         · 有记录 → A3 活跃性细化
    A3 有记录 → 用 download_hash 查下载器活种
         · 有活跃种 → skipped_pt_active
         · 无活跃种（死种/已清）→ 立即放行补推，不等 T
         · 下载器不可用 → 放行（fail-open）+ WARNING
         · 未启用细化 / 记录无 hash → 保守视为在管（skipped_pt_active）

纪律（规格 §8/§9，硬性）：
- **一律 fail-open 且留痕**：sdk 是宿主能力，MP 升级可能失配；fail-closed 会让
  推送静默失效，比重复获取严重得多。借鉴 1.7.9「None 静默放行」的教训，所有
  「取不到值」的分支都显式写日志。
- **禁止全量拉取**：下载历史按身份过滤查询（定向、代价与历史总量无关），
  种子按 hash 查询；结果做短 TTL 内存缓存（历史 60s / 种子 30s / 结论 60s），
  同一批消息逐集不重复打宿主。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.sdk.logging import logger

from ..model.p9_gate import TgP9Gate
from .matcher import MediaMatcher, _normalize_title

# 缓存 TTL（秒）：结论与下载历史 60s，种子 30s（规格 §9）
_RESULT_TTL_SECONDS = 60
_HISTORY_TTL_SECONDS = 60
_TORRENT_TTL_SECONDS = 30
# 下载历史单次查询页大小与翻页上限（身份过滤后不会多；上限只防异常宿主）
_HISTORY_PAGE_SIZE = 50
_HISTORY_MAX_PAGES = 4
# 锚点表惰性清理：超过该天数未见的键在读路径顺手删除（规格 §7）
_GATE_KEY_STALE_DAYS = 90

# 决策常量（与 model/hit_log.py / 前端 decision.js 三处逐字同步）
DECISION_SKIPPED_PT_ACTIVE = "skipped_pt_active"
DECISION_SKIPPED_PT_WAITING = "skipped_pt_waiting"

# ---------------------------------------------------------------------------
# 依赖探测（与 matcher 同款模式：无宿主环境降级，不抛异常）
try:  # 宿主只读查询：下载历史
    from app.sdk.queries import list_download_history

    HISTORY_QUERIES_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境
    list_download_history = None  # type: ignore[assignment]
    HISTORY_QUERIES_AVAILABLE = False

try:  # 下载器助手
    from app.sdk.services import DownloaderHelper

    DOWNLOADER_AVAILABLE = True
except Exception:  # pragma: no cover
    DownloaderHelper = None  # type: ignore[assignment]
    DOWNLOADER_AVAILABLE = False

_WARNED_MISSING: set = set()


def _warn_once(message: str) -> None:
    """同类警告只打一次（插件常驻进程，刷屏会淹没真正有用的日志）。"""
    if message in _WARNED_MISSING:
        return
    _WARNED_MISSING.add(message)
    logger.warning(message)


@dataclass
class GateResult:
    """闸门结论：``pass``=放行继续后续流程，``skip``=拦截并记决策。"""

    action: str                      # "pass" | "skip"
    reason: str                      # 人类可读说明（进流水 detail）
    decision: Optional[str] = None   # skip 时的决策常量；pass 时为 None
    degraded: bool = False           # True = 宿主能力缺失/查询失败而 fail-open

    @property
    def passed(self) -> bool:
        return self.action == "pass"


@dataclass(frozen=True)
class _Identity:
    """判定链的身份对象（季粒度；TG 侧没有 tmdbid，见规格 §2.1）。"""

    title: str
    year: str
    media_type: str
    season: Optional[int] = None

    @classmethod
    def from_meta(cls, meta: Optional[dict]) -> "_Identity":
        meta = meta or {}
        season = meta.get("season")
        try:
            season = int(season) if season is not None else None
        except (TypeError, ValueError):
            season = None
        return cls(
            title=str(meta.get("title") or ""),
            year=str(meta.get("year") or ""),
            media_type=str(meta.get("media_type") or ""),
            season=season,
        )

    @property
    def key(self) -> str:
        """季粒度锚点键：归一片名|年份|类型|季（缺失季用空串占位）。"""
        return "|".join([
            _normalize_title(self.title), self.year, self.media_type,
            str(self.season if self.season is not None else ""),
        ])


class _TtlCache:
    """极简 TTL 缓存（线程安全；超容量整体清空，与 matcher 同款兜底）。"""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = max(1.0, float(ttl_seconds))
        self._lock = threading.Lock()
        self._data: Dict[Any, Tuple[float, Any]] = {}

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            at, value = entry
            if time.monotonic() - at > self._ttl:
                self._data.pop(key, None)
                return None
            return value

    def put(self, key: Any, value: Any) -> None:
        with self._lock:
            if len(self._data) > 256:
                self._data.clear()
            self._data[key] = (time.monotonic(), value)


class GateStore:
    """``tgmc_p9_gate`` 表的读写（首次缺失锚点）。

    写入时机（规格 §7）：仅在「仅缺失」判定为缺失时登记/刷新；媒体库确认
    已有后清除。任何数据库异常都只降级为"没有锚点"（闸门按"无记录即放行"
    处理），不阻断流水线。
    """

    def __init__(self, plugin_id: str, db_getter: Callable[[], Any]) -> None:
        self._plugin_id = str(plugin_id or "")
        self._db_getter = db_getter

    def first_missing_at(self, key: str) -> Optional[datetime]:
        """取首次缺失时间；无记录返回 None（调用方负责先 touch）。"""
        row = self._get(key)
        return row.first_missing_at if row is not None else None

    def touch(self, key: str) -> None:
        """登记缺失：已有锚点只刷新 last_seen_at，没有则新建（幂等）。"""
        try:
            db = self._db_getter()
            if db is None:
                return
            now = datetime.now()
            with db.session() as session:
                row = session.get(TgP9Gate, (self._plugin_id, key))
                if row is None:
                    session.add(TgP9Gate(
                        plugin_id=self._plugin_id, key=key,
                        first_missing_at=now, last_seen_at=now,
                    ))
                else:
                    row.last_seen_at = now
                session.commit()
        except Exception as err:
            logger.debug(f"[P9] 缺失锚点登记失败（按无锚点处理）：{err}")

    def clear(self, key: str) -> None:
        """媒体库确认已有后清除锚点（已入库，不再需要计时）。"""
        try:
            db = self._db_getter()
            if db is None:
                return
            with db.session() as session:
                row = session.get(TgP9Gate, (self._plugin_id, key))
                if row is not None:
                    session.delete(row)
                    session.commit()
        except Exception as err:
            logger.debug(f"[P9] 缺失锚点清除失败（忽略）：{err}")

    def _get(self, key: str) -> Optional[TgP9Gate]:
        try:
            db = self._db_getter()
            if db is None:
                return None
            with db.session() as session:
                row = session.get(TgP9Gate, (self._plugin_id, key))
                if row is None:
                    return None
                # 90 天未见的键顺手清掉（表体积可控，惰性即可，规格 §7）
                if row.last_seen_at is not None:
                    stale = (datetime.now() - row.last_seen_at).days
                    if stale > _GATE_KEY_STALE_DAYS:
                        session.delete(row)
                        session.commit()
                        return None
                first = row.first_missing_at
        except Exception as err:
            logger.debug(f"[P9] 缺失锚点读取失败（按无锚点处理）：{err}")
            return None
        return _AnchorRow(first_missing_at=first)


class _AnchorRow:
    """脱离会话后的最小锚点载体（避免持有 ORM 对象跨会话使用）。"""

    __slots__ = ("first_missing_at",)

    def __init__(self, first_missing_at: Optional[datetime]) -> None:
        self.first_missing_at = first_missing_at


class ForwardGate:
    """闸门 A 判定器（线程安全；结论带 60s 缓存）。"""

    def __init__(
        self,
        *,
        matcher: MediaMatcher,
        store: GateStore,
        config_getter: Callable[[], dict],
    ) -> None:
        self._matcher = matcher
        self._store = store
        self._config_getter = config_getter
        self._result_cache = _TtlCache(_RESULT_TTL_SECONDS)
        self._history_cache = _TtlCache(_HISTORY_TTL_SECONDS)
        self._torrent_cache = _TtlCache(_TORRENT_TTL_SECONDS)

    # ------------------------------------------------------------------ 入口

    def check(self, meta: Optional[dict], missing: bool) -> Optional[GateResult]:
        """流水线入口：维护缺失锚点并跑判定链。

        :param missing: 上游「仅缺失」的判定结论（True=确认缺失，False=不缺）。
            ``True`` → 登记/刷新锚点（成熟期 T 的起点，规格 §7）；
            ``False`` → 清除锚点（已入库，不再计时）。
        :returns: 闸门未启用时返回 ``None``（调用方维持现状）；否则 GateResult。
        """
        cfg = self._config_getter() or {}
        if not cfg.get("p9_forward_gate_enabled"):
            return None
        ident = _Identity.from_meta(meta)
        if not ident.title:
            return None
        if missing:
            self._store.touch(ident.key)
        else:
            self._store.clear(ident.key)
        return self.evaluate(meta)

    def clear_anchor(self, meta: Optional[dict]) -> None:
        """媒体库确认已有后清除锚点（闸门未启用时也清，保持表干净）。"""
        ident = _Identity.from_meta(meta)
        if ident.title:
            self._store.clear(ident.key)

    def evaluate(self, meta: Optional[dict]) -> GateResult:
        """对一条已识别的媒体跑完整判定链（A0 → A2 → A3/A4'）。"""
        cfg = self._config_getter() or {}
        if not cfg.get("p9_forward_gate_enabled"):
            return GateResult("pass", "闸门未启用")
        if not HISTORY_QUERIES_AVAILABLE:
            _warn_once("[P9] 宿主缺少 app.sdk.queries.list_download_history，"
                       "前向闸门不生效（按现状放行）")
            return GateResult("pass", "下载历史查询不可用，按现状放行", degraded=True)

        ident = _Identity.from_meta(meta)
        if not ident.title:
            return GateResult("pass", "无有效标题，闸门不参与判定")

        cached = self._result_cache.get(ident.key)
        if cached is not None:
            return cached

        result = self._evaluate(ident, cfg)
        self._result_cache.put(ident.key, result)
        return result

    # ------------------------------------------------------------------ 判定链

    def _evaluate(self, ident: _Identity, cfg: dict) -> GateResult:
        # A2. 订阅桥 → 查下载历史
        within_hours = self._hours(cfg.get("p9_maturity_hours"))
        records = self._query_history(ident, within_hours)
        if records is None:
            # 查询失败：fail-open（详情已由 _fetch_history 留痕）
            return GateResult("pass", "下载历史查询失败，按现状放行", degraded=True)

        if not records:
            # A4'. 无记录 = PT 还没拿到资源 → 成熟期内等待，超期放行
            first = self._store.first_missing_at(ident.key)
            if first is None:
                # 没锚点（库迁移失败 / 该路径没 touch 过）按"刚发现"处理：
                # 本轮放行、下一轮起正常计时——绝不能因缺锚点就永久放行或拦截
                return GateResult("pass", "无下载记录且无缺失锚点，放行", degraded=True)
            age_hours = (datetime.now() - first).total_seconds() / 3600.0
            if age_hours < within_hours:
                return GateResult(
                    "skip",
                    f"PT 未取到资源，成熟期内（{age_hours:.1f}h / {within_hours:g}h）暂不补",
                    decision=DECISION_SKIPPED_PT_WAITING,
                )
            return GateResult(
                "pass", f"PT 超成熟期（{age_hours:.1f}h > {within_hours:g}h）未取到，TG 补"
            )

        # A3. 有记录 → 判「在途」还是「死种」
        hashes = sorted({
            str(r.get("download_hash") or "").strip()
            for r in records if str(r.get("download_hash") or "").strip()
        })
        if not cfg.get("p9_check_downloader"):
            return GateResult(
                "skip", f"PT 有下载记录（{len(records)} 条，未启用活跃性细化）",
                decision=DECISION_SKIPPED_PT_ACTIVE,
            )
        if not hashes:
            # 记录全无 hash（异常数据）→ 保守视为在管，绝不放行造成重复
            return GateResult(
                "skip", f"PT 有下载记录（{len(records)} 条，记录无 hash，保守跳过）",
                decision=DECISION_SKIPPED_PT_ACTIVE,
            )

        torrents = self._query_torrents(hashes)
        if torrents is None:
            # 下载器查询失败：fail-open（详情已由 _query_torrents 留痕）
            return GateResult("pass", "下载器查询不可用，按现状放行", degraded=True)
        active = [t for t in torrents if _torrent_active(t)]
        if active:
            best = max((_torrent_progress(t) for t in active), default=0.0)
            return GateResult(
                "skip",
                f"PT 在途（{len(active)} 个活跃种，最高进度 {best:.0f}%）",
                decision=DECISION_SKIPPED_PT_ACTIVE,
            )
        # 有记录 + 无活跃种 = 下载失败/已被清（死种）→ 立即补，不等 T（规格 §12 决策 4）
        return GateResult(
            "pass",
            f"有下载记录但下载器已无活跃种（{len(hashes)} 个 hash，死种/已清），TG 补"
        )

    # ------------------------------------------------------------------ 下载历史（A2）

    def _query_history(
        self, ident: _Identity, within_hours: float
    ) -> "Optional[List[Dict[str, Any]]]":
        """按身份查下载历史，返回**窗口内**的记录；``None`` = 查询失败。

        先走订阅桥借 ``(media_source, media_id)`` 精确查；未命中订阅退回
        ``title`` 过滤（注意：过滤器 title 是精确匹配，资源名与 TMDB 名有差异
        时会漏查——漏查的代价是"多推一条"，与 fail-open 同向，可接受）。
        时间窗口（近 T）过滤器不支持，取回后在本地按 ``date`` 筛。
        """
        source, media_id = self._matcher.subscription_identity(
            title=ident.title, year=ident.year, season=ident.season
        )
        if source and media_id:
            fingerprint: Tuple = ("id", source, media_id, ident.season)
            filters: Dict[str, Any] = {"media_source": source, "media_id": media_id}
        else:
            fingerprint = ("title", _normalize_title(ident.title), ident.season)
            filters = {"title": ident.title}

        records = self._history_cache.get(fingerprint)
        if records is None:
            records = self._fetch_history(filters)
            self._history_cache.put(fingerprint, records)
        if records is None:
            return None
        return [
            r for r in records
            if _within_window(r.get("date"), within_hours) and _season_matches(r, ident)
        ]

    @staticmethod
    def _fetch_history(filters: Dict[str, Any]) -> "Optional[List[Dict[str, Any]]]":
        """真正调用宿主查询；异常返回 None（fail-open 信号，由调用方放行）。"""
        try:
            collected: List[Dict[str, Any]] = []
            for page_num in range(1, _HISTORY_MAX_PAGES + 1):
                try:
                    page = list_download_history(
                        filters, {"page": page_num, "count": _HISTORY_PAGE_SIZE}
                    )
                except TypeError:
                    # 测试桩或老签名不支持分页参数
                    page = list_download_history(filters)
                items = list(getattr(page, "items", None) or [])
                collected.extend(_snapshot_to_dict(item) for item in items)
                if len(items) < _HISTORY_PAGE_SIZE:
                    break
            return collected
        except Exception as err:
            # 只打一次 WARNING：宿主接口失配是常态级风险，刷屏没有意义
            _warn_once(f"[P9] 下载历史查询失败（闸门对这类身份放行）：{err}")
            return None

    # ------------------------------------------------------------------ 下载器（A3）

    def _query_torrents(self, hashes: List[str]) -> "Optional[List[Any]]":
        """按 hash 查种子；``None`` = 查询失败（fail-open 信号）。"""
        cache_key = tuple(hashes)
        cached = self._torrent_cache.get(cache_key)
        if cached is not None:
            return cached
        torrents: Optional[List[Any]]
        try:
            if not DOWNLOADER_AVAILABLE:
                _warn_once("[P9] 宿主缺少 DownloaderHelper，活跃性细化不可用（放行）")
                torrents = None
            else:
                helper = DownloaderHelper()
                found: List[Any] = []
                queried = False
                failed = False
                for service in (helper.get_services() or {}).values():
                    # list_torrents 在**模块**实例上（与媒体服务器同款分层）；
                    # 个别版本可能直接挂在 service 实例上，逐个探测
                    for candidate in (getattr(service, "module", None),
                                      getattr(service, "instance", None)):
                        func = getattr(candidate, "list_torrents", None)
                        if not callable(func):
                            continue
                        try:
                            try:
                                found.extend(func(hashs=list(cache_key)) or [])
                            except TypeError:
                                found.extend(func(list(cache_key)) or [])
                            queried = True
                        except TypeError:
                            continue  # 签名不匹配，试下一个挂载点
                        except Exception as err:
                            # 有下载器但查询失败：**不能**当成"无活跃种"（会把死种
                            # 判定放大成误放行），整体按查询失败 fail-open
                            _warn_once(f"[P9] 下载器查询失败（活跃性细化不可用，放行）：{err}")
                            failed = True
                            break
                    if failed:
                        break
                if failed:
                    torrents = None
                elif not queried:
                    # 一个能调的实例都没有：等价于下载器不可用，fail-open
                    _warn_once("[P9] 未枚举到可调用的下载器实例（活跃性细化不可用，放行）")
                    torrents = None
                else:
                    torrents = found
        except Exception as err:
            _warn_once(f"[P9] 下载器查询失败（活跃性细化不可用，放行）：{err}")
            torrents = None
        self._torrent_cache.put(cache_key, torrents)
        return torrents

    # ------------------------------------------------------------------ 小工具

    @staticmethod
    def _hours(value: Any) -> float:
        try:
            hours = float(value)
        except (TypeError, ValueError):
            return 2.0
        return hours if hours > 0 else 0.0


# ---------------------------------------------------------------------------
# 模块级小工具（无状态）


def _snapshot_to_dict(item: Any) -> Dict[str, Any]:
    """把宿主快照压成判定所需的最小字典（避免持有多余引用）。"""
    return {
        "title": getattr(item, "title", None),
        "year": getattr(item, "year", None),
        "seasons": getattr(item, "seasons", None),
        "episodes": getattr(item, "episodes", None),
        "download_hash": getattr(item, "download_hash", None),
        "date": getattr(item, "date", None),
    }


def _within_window(date_value: Any, within_hours: float) -> bool:
    """记录时间是否在近 T 小时内；时间缺失/解析失败按"在窗口内"处理。

    往保守方向错：宁可视为在管（少推）也不因解析失败放行造成重复下载。
    """
    if not date_value:
        return True
    text = str(date_value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text[:19].strip(), fmt)
            break
        except ValueError:
            continue
    else:
        return True
    age_hours = (datetime.now() - parsed).total_seconds() / 3600.0
    return age_hours <= max(within_hours, 0.0) + 0.01


def _season_matches(record: Dict[str, Any], ident: _Identity) -> bool:
    """记录的季是否与身份一致（电影 / 未识别季的身份不按季筛）。

    宿主把 ``meta.season`` 原样写进 seasons 列（int 或 "S01" 形态都有可能），
    这里宽松解析；解析失败按"季不可知 = 匹配"处理（保守方向，同上）。
    """
    if ident.season is None:
        return True
    raw = record.get("seasons")
    if raw in (None, ""):
        return True
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if not digits:
        return True
    try:
        return int(digits) == int(ident.season)
    except (TypeError, ValueError):
        return True


def _torrent_active(torrent: Any) -> bool:
    """种子是否"在途"：状态为下载/暂停，或进度未到 100%。

    拿不到任何信息时按"在途"处理——这里错放行 = 重复下载，错拦截 = 少推一条
    且下一轮成熟期后还会补，保守方向与历史查询一致。
    """
    state = getattr(torrent, "state", None)
    text = str(getattr(state, "value", state) or "").upper()
    if "DOWNLOADING" in text or "PAUSED" in text:
        return True
    progress = getattr(torrent, "progress", None)
    if progress is None:
        return not text  # 状态与进度都拿不到：按在途处理
    try:
        return float(progress) < 100
    except (TypeError, ValueError):
        return True


def _torrent_progress(torrent: Any) -> float:
    try:
        return float(getattr(torrent, "progress", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
