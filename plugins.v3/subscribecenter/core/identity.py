"""身份分级解析（L1–L4）—— 全案质量的核心。

开发文档 §6 的定义：

===========  ==========================================  ==========
级别          手段                                          是否允许写入
===========  ==========================================  ==========
L1 直通       源自带确定性 ID（tmdb/imdb/tvdb/bangumi…）      ✅
L2 缓存       source+source_id / 标题+年份+类型 的已确认映射   ✅
L3 精确搜索    标题+年份+类型 → 搜索候选，**年份硬校验**         ✅
L4 模糊评分    ``difflib`` 相似度                              ❌ 永不写入
===========  ==========================================  ==========

本模块**不导入宿主**：所有宿主能力（TMDB 搜索、跨源换算）都通过下面两个
``Protocol`` 注入。这样 L1–L4 的全部分支都能离线单测（开发文档 §14.1）。
"""
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from .constants import (
    CONFIDENCE_L1,
    CONFIDENCE_L2,
    CONFIDENCE_L3,
    CONFIDENCE_L4,
    MEDIA_TYPE_MOVIE,
    SOURCE_BANGUMI,
    SOURCE_DOUBAN_RSS,
    SOURCE_SIMKL,
)
from .model import DiscoveredItem, ResolvedIdentity
from .window import parse_date

#: 宿主 ``MediaSource`` 的规范值（字符串形式，避免本模块依赖宿主枚举）
HOST_SOURCE_TMDB = "themoviedb"

#: 能直接给出 TMDB 身份的辅助 ID 优先级（高 → 低）
TMDB_LIKE_PRIORITY: Tuple[str, ...] = ("tmdb", "themoviedb", "imdb", "tvdb")

#: 不能直接给出 TMDB、但可经跨源换算的身份（来源 → 辅助 ID 键）
CONVERTIBLE_SOURCES: Dict[str, Tuple[str, ...]] = {
    SOURCE_BANGUMI: ("bangumi",),
    SOURCE_DOUBAN_RSS: ("douban",),
    SOURCE_SIMKL: ("simkl",),
}

#: 通用相似度阈值（仅用于 L4 待确认列表排序，不作为写入闸门）
DEFAULT_REVIEW_THRESHOLD = 0.60


# --------------------------------------------------------------------- 注入契约

class TmdbSearchCandidate(Protocol):
    """TMDB 搜索候选的最小结构。"""

    tmdb_id: int
    title: str
    original_title: Optional[str]
    year: Optional[str]
    media_type: str


class TmdbResolver(Protocol):
    """TMDB 解析能力（由宿主适配器实现）。"""

    async def search(
        self,
        title: str,
        year: Optional[str],
        media_type: str,
        *,
        limit: int = ...,
    ) -> Sequence[dict]:
        """按标题+年份搜索，返回候选字典（含 ``tmdb_id``/``title``/``year``/``media_type``）。"""
        ...

    async def convert_to_tmdb(
        self,
        media_source: str,
        media_id: str,
        media_type: str,
    ) -> Optional[Dict[str, Any]]:
        """跨源换算为 TMDB；无法换算返回 ``None``。

        返回 ``{"tmdb_id": str, "year": str | None, "title": str | None}``。

        .. important::
           宿主的 Bangumi/豆瓣 → TMDB 换算**内部是标题+年份匹配**
           （``_build_bangumi_tmdb_match``），不是 ID 直映。所以调用方必须
           拿返回的 ``year`` 再做一次硬校验，否则可能把 A 番写成 B 番。
        """
        ...


class MappingCache(Protocol):
    """身份映射缓存（由插件自有存储实现）。"""

    def get_by_source_id(self, source: str, source_id: str) -> Optional[ResolvedIdentity]:
        """按来源内身份查缓存。"""
        ...

    def get_by_title(
        self, normalized_title: str, year: Optional[str], media_type: str
    ) -> Optional[ResolvedIdentity]:
        """按标准化标题+年份+类型查缓存。"""
        ...

    def remember(self, key: str, identity: ResolvedIdentity) -> None:
        """写入一条映射。"""
        ...


# --------------------------------------------------------------------- 标题归一

#: 需要剔除的噪声后缀/前缀（来源标题里常见的装饰）。
#:
#: 注意顺序与边界：
#: - 带括号的季号/年份先剥离（``沙丘（2026）`` → ``沙丘``）；
#: - 裸季号只匹配「有空白分隔」或「第N季」形式，避免把 ``复仇者联盟2026``
#:   这类年份属于片名的标题切坏；
#: - 分隔符归一（``：``/``·`` 等）放在最后，避免先变成空格再被季号模式吃到。
_NOISE_PATTERNS = (
    re.compile(r"[（(]\s*(?:第\s*[一二三四五六七八九十\d]+\s*季|\d{4})\s*[)）]"),
    re.compile(r"\s+第\s*[一二三四五六七八九十\d]+\s*[季部]"),
    re.compile(r"\b(?:S\d{1,2}|Season\s*\d{1,2})\b", re.IGNORECASE),
    re.compile(r"[“”\"'《》]"),
)

#: 全角 → 半角映射区间
_FULLWIDTH_START = 0xFF01
_FULLWIDTH_END = 0xFF5E
_FULLWIDTH_OFFSET = 0xFEE0


def normalize_title(title: Optional[str]) -> str:
    """标准化标题：全角转半角、去装饰、压空白、统一小写。

    用于缓存键与模糊比较；**不用于**需要展示的标题。
    """
    if not title:
        return ""
    text = unicodedata.normalize("NFKC", str(title))
    # 显式再做一次全角 ASCII 折叠：NFKC 对部分来源文本不生效
    chars: List[str] = []
    for char in text:
        code = ord(char)
        if _FULLWIDTH_START <= code <= _FULLWIDTH_END:
            chars.append(chr(code - _FULLWIDTH_OFFSET))
        else:
            chars.append(char)
    text = "".join(chars)
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub("", text)
    text = re.sub(r"[_\-–—:：·,，.。]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


#: 标题尾部的季号标记（第 2 期 / 第2季 / Season 2 / 末尾空格+数字）
_SEASON_SUFFIX = re.compile(
    r"[\s:：·\-]*(?:第\s*)?([0-9]{1,2}|[一二三四五六七八九十]{1,2})\s*[期季部]?\s*$"
)


def strip_season_suffix(title: Optional[str]) -> str:
    """去掉标题尾部的季号，得到「基础剧名」。

    动机（真机确认）：国产动画在 TMDB 常被建模成单季多集，Bangumi 的
    「牧神记5」对应的是 TMDB《牧神记》更靠后的集数，**不是第 5 季**。
    因此搜索 TMDB 时必须用基础名「牧神记」，用「牧神记5」搜不到。

    安全约束（避免把正常片名削坏）：

    - 数字前面一个字符**不能是数字或 ASCII 字母** —— 否则「1917」会被削成「19」；
    - 削完剩下的基础名至少 2 个字符；
    - 季号必须在 2~30 之间（1 通常不是「续作」语义，且容易误伤）。

    :return: 基础名；不满足上述约束时原样返回
    """
    text = str(title or "").strip()
    if not text:
        return text
    match = _SEASON_SUFFIX.search(text)
    if not match:
        return text
    start = match.start()
    # 数字前的边界校验：有明确分隔符（空格 / 冒号 / 间隔号 / 连字符）视为季号，
    # 否则要求前一个字符不是数字或字母（避免把 "1917" 削成 "19"）。
    matched_text = match.group(0)
    has_separator = bool(matched_text) and matched_text[0] in " \t:：·-"
    if not has_separator and start > 0:
        prev = text[start - 1]
        if prev.isdigit() or (prev.isascii() and prev.isalpha()):
            return text
    base = text[:start].strip(" :：·-")
    if len(base) < 2:
        return text
    # 基础名不能是纯数字（否则 "12 12 12" 会被削成 "12 12"）
    if base.replace(" ", "").replace("-", "").isdigit():
        return text
    raw = match.group(1)
    try:
        number = int(raw)
    except ValueError:
        return text
    if not 2 <= number <= 30:
        return text
    return base


def title_similarity(left: str, right: str) -> float:
    """返回两个标题的相似度（0~1），输入会先标准化。"""
    a = normalize_title(left)
    b = normalize_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _year_of(value: object) -> Optional[str]:
    """从任意日期/年份表示里取出 4 位年份字符串。"""
    parsed = parse_date(value)
    if parsed:
        return str(parsed.year)
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})", text)
    return match.group(1) if match else None


# --------------------------------------------------------------------- L1

def resolve_from_native_ids(item: DiscoveredItem) -> Optional[ResolvedIdentity]:
    """L1：直接从来源给出的辅助 ID 得到确定性身份。

    优先级：``tmdb`` → ``themoviedb`` → ``imdb`` → ``tvdb``。
    IMDb / TVDB 视为**同源可信**（宿主 ``convert_media_identity`` 能换算它们），
    因此也归入 L1 并直接以宿主 TMDB 值表达。

    .. note::
       IMDb / TVDB 仅在**同时**已知对应 TMDB ID 的场景下才能落到 L1；
       只给 IMDb 而没有 TMDB 时，本函数返回 ``None``，交由换算路径处理
       （见 :func:`resolve_item`），避免把未确认的换算当成确定性身份。
    """
    ids = {str(k).casefold(): str(v).strip() for k, v in (item.native_ids or {}).items()}
    for key in ("tmdb", "themoviedb"):
        value = ids.get(key)
        # "0" 与空白都不是有效身份（与宿主 resolve_media_identity 同口径）
        if value and value != "0":
            return ResolvedIdentity(
                media_source=HOST_SOURCE_TMDB,
                media_id=value,
                confidence=CONFIDENCE_L1,
                reason=f"native:{key}",
            )
    return None


# --------------------------------------------------------------------- L3

def match_candidate_year(
    candidates: Iterable[dict],
    item: DiscoveredItem,
    *,
    strict_year: bool = True,
) -> Optional[Tuple[dict, str]]:
    """L3：在候选中按「标题精确 + 年份硬校验」选出唯一目标。

    规则（宁缺毋滥）：

    1. 只接受 ``media_type`` 与条目一致的候选；
    2. 标题标准化后**完全相等**，或一方包含另一方（覆盖「副标题差异」）；
    3. 双方都有年份时**必须相等**；候选缺年份而条目有年份时**拒绝**
       （无法校验就不确认，避免同名不同年误匹配）；
    4. 多条候选同时满足 → 拒绝（歧义不猜）。

    :return: ``(候选, 说明)``；无唯一命中返回 ``None``。
    """
    wanted_year = _year_of(item.year or item.release_date)
    target_title = normalize_title(item.title)
    if not target_title:
        return None

    matched: List[Tuple[dict, str]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        tmdb_id = candidate.get("tmdb_id")
        if not tmdb_id:
            continue
        candidate_type = str(candidate.get("media_type") or "").strip().casefold()
        if candidate_type and candidate_type != item.media_type:
            continue

        candidate_title = normalize_title(candidate.get("title"))
        candidate_original = normalize_title(candidate.get("original_title"))
        exact = candidate_title == target_title or candidate_original == target_title
        contained = bool(candidate_title) and (
            target_title in candidate_title or candidate_title in target_title
        )
        if not (exact or contained):
            continue

        candidate_year = _year_of(candidate.get("year") or candidate.get("release_date"))
        if strict_year:
            if wanted_year and candidate_year != wanted_year:
                # 年份不符或缺年份 —— 电影不做任何「放宽」，直接不算命中
                continue
        elif not exact:
            # 剧集不校验年份，但**必须标题精确相等**才认 ——
            # 否则「包含」匹配 + 无年份约束会把同名前传之类错误配对放进来。
            continue

        reason = "search:title_exact" if exact else "search:title_contained"
        if wanted_year:
            reason = f"{reason}+year_match"
        matched.append((candidate, reason))

    if len(matched) != 1:
        # 0 条：未命中；>1 条：歧义 —— 两种情况都不确认
        return None
    return matched[0]


def review_candidates(
    candidates: Iterable[dict],
    item: DiscoveredItem,
    *,
    threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> Optional[float]:
    """L4：返回最相似候选的相似度分数（**仅用于待确认列表**，绝不写入）。

    无候选或全部低于阈值时返回 ``None``。
    """
    target = normalize_title(item.title)
    if not target:
        return None
    best = 0.0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if not candidate.get("tmdb_id"):
            continue
        candidate_type = str(candidate.get("media_type") or "").strip().casefold()
        if candidate_type and candidate_type != item.media_type:
            continue
        for field in ("title", "original_title"):
            score = title_similarity(item.title, candidate.get(field))
            best = max(best, score)
    return best if best >= threshold else None


# --------------------------------------------------------------------- 编排

class IdentityResolver:
    """按 L1 → L2 → L3 → L4 解析条目身份。

    :param tmdb: TMDB 解析能力（宿主适配器）
    :param cache: 映射缓存（插件自有存储），可为 ``None``（无缓存模式）
    """

    def __init__(
        self,
        tmdb: TmdbResolver,
        cache: Optional[MappingCache] = None,
        *,
        review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
        use_converted_season: bool = False,
    ) -> None:
        self._tmdb = tmdb
        self._cache = cache
        self._review_threshold = review_threshold
        #: 是否采用跨源换算回来的季号。**默认关**（见 _resolve_by_conversion 注释）
        self._use_converted_season = use_converted_season

    async def resolve(self, item: DiscoveredItem) -> DiscoveredItem:
        """就地解析条目身份并写回 ``resolved`` / ``review_score``。

        任何异常都不得向上抛 —— 单条解析失败只应影响该条（宁缺毋滥）。
        调用方负责记录日志。
        """
        # ---- L1 直通
        identity = resolve_from_native_ids(item)
        if identity:
            item.resolved = identity
            self._remember(item, identity)
            return item

        # ---- L1b：可换算来源（Bangumi / 豆瓣 / Simkl 的原生 ID → TMDB）
        identity = await self._resolve_by_conversion(item)
        if identity:
            item.resolved = identity
            self._remember(item, identity)
            return item

        # ---- L2 缓存
        identity = self._resolve_from_cache(item)
        if identity:
            item.resolved = identity
            return item

        # ---- L3 精确搜索 + 年份硬校验
        candidates = await self._search(item)
        if candidates:
            hit = match_candidate_year(
                candidates, item, strict_year=item.media_type == MEDIA_TYPE_MOVIE
            )
            if hit:
                candidate, reason = hit
                identity = ResolvedIdentity(
                    media_source=HOST_SOURCE_TMDB,
                    media_id=str(candidate["tmdb_id"]),
                    confidence=CONFIDENCE_L3,
                    reason=reason,
                )
                item.resolved = identity
                self._remember(item, identity)
                return item

            # ---- L4 模糊评分：只记录，永不写入
            item.review_score = review_candidates(
                candidates, item, threshold=self._review_threshold
            )

        return item

    # ------------------------------------------------------------------ 内部

    async def _resolve_by_conversion(self, item: DiscoveredItem) -> Optional[ResolvedIdentity]:
        """用来源原生 ID 走宿主跨源换算得到 TMDB 身份（归入 L1）。"""
        ids = {str(k).casefold(): str(v) for k, v in (item.native_ids or {}).items()}
        for source, keys in CONVERTIBLE_SOURCES.items():
            if source != item.source:
                continue
            for key in keys:
                media_id = ids.get(key)
                if not media_id:
                    continue
                try:
                    payload = await self._tmdb.convert_to_tmdb(source, media_id, item.media_type)
                except Exception:  # noqa: BLE001 - 单条换算失败不影响其余条目
                    return None
                if not payload:
                    return None
                tmdb_id = payload.get("tmdb_id")
                if not tmdb_id:
                    return None

                # **年份硬校验**（只对电影）：宿主的跨源换算内部是标题匹配，
                # 不是 ID 直映，必须用返回年份再核一次，否则可能把 A 片写成 B 片。
                #
                # 剧集**不能**做这个校验：TMDB 的剧集年份是「第一季首播年」，
                # 而 Bangumi 的续作条目（第 2 期 / 边缘行者 2）年份是**该季**的。
                # 真机踩过：`赛博朋克：边缘行者 2`（2026）换算到 TMDB 剧集
                # `Cyberpunk: Edgerunners`（first_air_date 2022）—— 年份必然不等，
                # 被这里的校验误杀，条目退化成「待确认」而永远订不上。
                wanted = _year_of(item.year or item.release_date)
                got = _year_of(payload.get("year"))
                if item.media_type == MEDIA_TYPE_MOVIE and wanted and got and wanted != got:
                    return None

                # 季号：**默认不采用**换算回来的季号。
                #
                # 原因（真机确认）：国产动画在 TMDB 通常被建模成「单季多集」——
                # 《牧神记》= 第 1 季 110 集，第 105 集 = 2026-10-18，正好对应
                # Bangumi「牧神记5」的开播日。也就是说 Bangumi 的「第 N 期」
                # 往往不是 TMDB 的第 N 季；传 season=N 会让宿主去找一个不存在的
                # 季，结果什么都订不到。
                #
                # 关掉后按 TMDB 默认季订阅、由宿主按集追踪，才是正确行为。
                # 需要严格按季拆分的媒体库可在配置里打开 bangumi_split_season。
                returned_season = payload.get("season")
                if self._use_converted_season and item.season is None and returned_season:
                    try:
                        item.season = int(returned_season)
                    except (TypeError, ValueError):
                        pass

                return ResolvedIdentity(
                    media_source=HOST_SOURCE_TMDB,
                    media_id=str(tmdb_id),
                    # 标 L2 而不是 L1：这是「宿主按标题匹配确认的映射」，
                    # 可信度低于源自带的确定性 ID。
                    confidence=CONFIDENCE_L2,
                    reason=(
                        f"convert:{source}"
                        + (f"+season({returned_season})" if returned_season else "")
                        + (f"+year_match({got})" if got and item.media_type == MEDIA_TYPE_MOVIE else "")
                    ),
                )
        return None

    def _resolve_from_cache(self, item: DiscoveredItem) -> Optional[ResolvedIdentity]:
        """L2：命中已确认映射即复用。"""
        if self._cache is None:
            return None
        cached = self._cache.get_by_source_id(item.source, item.source_id)
        if cached is None:
            cached = self._cache.get_by_title(
                normalize_title(item.title),
                _year_of(item.year or item.release_date),
                item.media_type,
            )
        if cached is None:
            return None
        # 缓存只应保存可写入的确定性身份；L4 不落缓存
        if not cached.writable:
            return None
        return ResolvedIdentity(
            media_source=cached.media_source,
            media_id=cached.media_id,
            confidence=CONFIDENCE_L2,
            reason="cache",
        )

    async def _search(self, item: DiscoveredItem) -> Sequence[dict]:
        """调用 TMDB 搜索；失败返回空序列（不抛）。"""
        try:
            return await self._tmdb.search(
                item.title,
                _year_of(item.year or item.release_date),
                item.media_type,
            )
        except Exception:  # noqa: BLE001 - 搜索失败等同「无候选」
            return ()

    def _remember(self, item: DiscoveredItem, identity: ResolvedIdentity) -> None:
        """把确定性身份写入缓存（L4 不写）。"""
        if self._cache is None or not identity.writable:
            return
        try:
            self._cache.remember(source_id_key(item.source, item.source_id), identity)
            self._cache.remember(
                title_key(
                    normalize_title(item.title),
                    _year_of(item.year or item.release_date),
                    item.media_type,
                ),
                identity,
            )
        except Exception:  # noqa: BLE001 - 缓存写失败不影响主流程
            pass


# --------------------------------------------------------------------- 缓存键

def source_id_key(source: str, source_id: str) -> str:
    """缓存键：来源内身份。"""
    return f"sid:{source}:{source_id}"


def title_key(normalized_title: str, year: Optional[str], media_type: str) -> str:
    """缓存键：标准化标题 + 年份 + 类型。"""
    return f"t:{media_type}:{year or ''}:{normalized_title}"


__all__ = [
    "CONFIDENCE_L1",
    "CONFIDENCE_L2",
    "CONFIDENCE_L3",
    "CONFIDENCE_L4",
    "DEFAULT_REVIEW_THRESHOLD",
    "HOST_SOURCE_TMDB",
    "IdentityResolver",
    "MappingCache",
    "TmdbResolver",
    "match_candidate_year",
    "normalize_title",
    "resolve_from_native_ids",
    "review_candidates",
    "source_id_key",
    "title_key",
    "title_similarity",
]
