"""统一数据模型：发现条目与身份解析结果。

本模块**不导入宿主**，保证纯逻辑可离线单测（开发文档 §14.1）。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .constants import (
    CONFIDENCE_L1,
    CONFIDENCE_L2,
    CONFIDENCE_L3,
    CONFIDENCE_L4,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    WRITABLE_CONFIDENCE,
)


@dataclass(frozen=True)
class ResolvedIdentity:
    """一条发现条目的确定性身份解析结果。

    ``media_source`` 用字符串（宿主 ``MediaSource`` 的值，如 ``"themoviedb"``），
    避免模型层依赖宿主枚举。
    """

    media_source: str
    media_id: str
    confidence: str = CONFIDENCE_L1
    #: 解析来源说明，便于日志排查（如 ``native:tmdb`` / ``cache`` / ``search:year_match``）
    reason: str = ""
    #: L4 候选的相似度分数（仅用于待确认列表展示）
    score: Optional[float] = None

    def __post_init__(self) -> None:
        """校验身份成对、非空、非 ``"0"``，与宿主 ``resolve_media_identity`` 同口径。"""
        source = (self.media_source or "").strip()
        media_id = str(self.media_id or "").strip()
        if not source or not media_id or media_id == "0":
            raise ValueError(f"媒体身份无效：media_source={source!r} media_id={media_id!r}")

    @property
    def writable(self) -> bool:
        """该身份是否允许写入订阅（L4 永不写入，见开发文档 §6.2）。"""
        return self.confidence in WRITABLE_CONFIDENCE

    def as_key(self) -> str:
        """返回稳定的去重键：``source:media_id``。"""
        return f"{self.media_source}:{self.media_id}"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可落盘/可回传的字典。"""
        return {
            "media_source": self.media_source,
            "media_id": self.media_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "score": self.score,
        }


#: 特别篇 / OVA / 番外等衍生内容的标题标记。
#:
#: 这类内容在 TMDB 里通常**没有独立条目**（或归到剧集的 Season 0），
#: 靠标题匹配必然失败。因此凡是有这种标题的来源都要标出来，
#: 由 writer 统一给出「特别篇不处理」的明确原因，
#: 而不是报成「无确定性身份」让人误以为匹配有 bug。
SPECIAL_MARKERS = (
    "特别篇", "特別篇", "特别版", "特別版", "番外", "外传", "前传", "学前篇",
    "剧场版", "劇場版", "特典", "OVA", "OAD", "ONA", "SP",
)


def is_special(title: Optional[str]) -> bool:
    """判断标题是否为特别篇 / OVA / 番外等衍生内容。"""
    if not title:
        return False
    text = str(title).upper()
    return any(marker.upper() in text for marker in SPECIAL_MARKERS)


@dataclass
class DiscoveredItem:
    """一个标准化后的发现条目。

    来源侧身份（``source`` + ``source_id``）**必填且不可省略**；
    宿主侧身份（``resolved``）由身份解析阶段填充。
    """

    # ---------------- 来源侧身份（原生）
    source: str
    source_id: str
    # ---------------- 元数据
    title: str
    media_type: str = MEDIA_TYPE_MOVIE
    year: Optional[str] = None
    original_title: Optional[str] = None
    release_date: Optional[str] = None
    season: Optional[int] = None
    rating: Optional[float] = None
    popularity: Optional[float] = None
    # ---------------- 来源给出的原生辅助 ID
    #: 形如 ``{"tmdb": "12345", "imdb": "tt123", "bangumi": "67890"}``
    native_ids: Dict[str, str] = field(default_factory=dict)
    # ---------------- 解析结果（由 identity 层填充）
    resolved: Optional[ResolvedIdentity] = None
    #: 未解析出确定性身份时的模糊候选相似度（进待确认列表）
    review_score: Optional[float] = None
    #: 是否为特别篇 / OVA / 番外等衍生内容（这类内容 TMDB 通常没有独立条目）
    special: bool = False
    #: 匹配到的 TMDB 剧集是否**已无未播出内容**（订了也没意义）
    finished: bool = False
    #: 来源没有给出定档日期（榜单类 RSS 常见）。
    #:
    #: 这类条目无法做时间窗口过滤，**只对剧集放行** —— 改用「TMDB 是否还有
    #: 未播集」来替代窗口判定（见 IdentityResolver._resolve_target_season）；
    #: 电影没有日期就无从判断是否即将上映，直接跳过。
    date_unknown: bool = False
    #: 原始载荷（排查用，落流水时可截断）
    raw: Dict[str, Any] = field(default_factory=dict)
    discovered_at: str = ""

    # ------------------------------------------------------------------ 只读属性

    @property
    def confidence(self) -> str:
        """当前置信度级别；未解析时为 L4（按「不可写」处理）。"""
        return self.resolved.confidence if self.resolved else CONFIDENCE_L4

    @property
    def writable(self) -> bool:
        """是否**真的**可以写入订阅。

        这是唯一的「能不能写」判定，必须同时满足：

        - 身份置信度在可写级别（L1~L3；L4 永不写入，见开发文档 §6.2）；
        - 不是特别篇 / OVA / 番外（TMDB 通常没有独立条目）；
        - 匹配到的剧集还有未播内容（否则会订到已完结的旧季）。

        合并判断的原因：分散判断会形成多个真相来源 —— 真机事故正是
        「身份看起来可写」但「内容已播完」，结果仍被写进了订阅。
        """
        if self.special or self.finished:
            return False
        return bool(self.resolved and self.resolved.writable)

    @property
    def is_tv(self) -> bool:
        """是否剧集。"""
        return self.media_type == MEDIA_TYPE_TV

    @property
    def is_movie(self) -> bool:
        """是否电影。"""
        return self.media_type == MEDIA_TYPE_MOVIE

    @property
    def title_year(self) -> str:
        """``片名 (年份)`` 形式的展示名。"""
        return f"{self.title} ({self.year})" if self.year else self.title

    @property
    def dedupe_key(self) -> str:
        """跨源去重键：优先用解析后的确定性身份，否则退回来源内身份。"""
        if self.resolved:
            return self.resolved.as_key()
        return f"{self.source}:{self.source_id}"

    # ------------------------------------------------------------------ 工具

    def to_log_dict(self) -> Dict[str, Any]:
        """返回适合落流水/日志的精简字典。"""
        data: Dict[str, Any] = {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "year": self.year,
            "media_type": self.media_type,
            "release_date": self.release_date,
            "season": self.season,
            "rating": self.rating,
            "confidence": self.confidence,
        }
        if self.resolved:
            data.update(self.resolved.to_dict())
        if self.review_score is not None:
            data["review_score"] = self.review_score
        return data


def parse_native_ids(payload: Any) -> Dict[str, str]:
    """把来源返回的外部 ID 归一为 ``{"tmdb": "123"}`` 形式。

    只保留非空、非 ``"0"`` 的值；键统一小写。
    """
    if not isinstance(payload, dict):
        return {}
    result: Dict[str, str] = {}
    for key, value in payload.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text or text == "0":
            continue
        result[str(key).strip().casefold()] = text
    return result


def item_sort_key(item: DiscoveredItem) -> tuple:
    """发现条目的稳定排序键：定档日期升序 → 评分降序 → 来源 → 标题。

    用于保证同一批数据多次运行产出一致（便于测试与人工核对）。
    """
    return (
        item.release_date or "9999-99-99",
        -(item.rating or 0.0),
        item.source,
        item.title_year,
    )


__all__ = [
    "CONFIDENCE_L1",
    "CONFIDENCE_L2",
    "CONFIDENCE_L3",
    "CONFIDENCE_L4",
    "DiscoveredItem",
    "ResolvedIdentity",
    "item_sort_key",
    "parse_native_ids",
]
