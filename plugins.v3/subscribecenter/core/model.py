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
        """是否具备可写入的确定性身份。"""
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
