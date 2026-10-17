"""SubscribeCenter API 请求/响应模型。

约定与 ``tgmediacenter`` 一致：每个路由显式声明
``response_model = schemas.Response[业务模型]``。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------- 状态

class SourceState(BaseModel):
    """单个数据源的运行状态。"""

    source: str = Field(description="源标识")
    enabled: bool = Field(default=False, description="是否已启用")
    implemented: bool = Field(default=True, description="该源当前版本是否已实现")
    last_run: Optional[str] = Field(default=None, description="最近一次拉取时间")
    last_count: int = Field(default=0, description="最近一次拉取条数")
    last_error: str = Field(default="", description="最近一次失败原因")


class PluginStatus(BaseModel):
    """插件运行状态。"""

    plugin_version: str = Field(description="后端插件版本")
    enabled: bool = Field(description="插件是否启用")
    dry_run: bool = Field(description="当前是否 dry-run")
    first_run_completed: bool = Field(description="首次试运行是否已完成")
    busy: bool = Field(description="是否有流水线正在运行")
    today: str = Field(description="当前日期（插件时区）")
    daily_limit: int = Field(description="每日写入上限")
    written_today: int = Field(description="今日已写入条数")
    last_run: Optional[str] = Field(default=None, description="最近一次运行完成时间")
    last_summary: Dict[str, Any] = Field(default_factory=dict, description="最近一次运行汇总")
    sources: List[SourceState] = Field(default_factory=list, description="各源状态")
    mapping_cache_size: int = Field(default=0, description="映射缓存条数")
    timezone: str = Field(description="插件时区")


# --------------------------------------------------------------------- 流水

class HistoryRecord(BaseModel):
    """一条发现/写入流水。"""

    decision: str = Field(description="决策常量")
    success: bool = Field(default=False, description="是否成功")
    subscribe_id: Optional[int] = Field(default=None, description="宿主订阅 ID")
    message: str = Field(default="", description="宿主返回信息")
    reason: str = Field(default="", description="跳过/待确认原因")
    source: str = Field(default="", description="来源")
    source_id: str = Field(default="", description="来源内 ID")
    title: str = Field(default="", description="标题")
    year: Optional[str] = Field(default=None, description="年份")
    media_type: str = Field(default="", description="movie / tv")
    release_date: Optional[str] = Field(default=None, description="定档日期")
    season: Optional[int] = Field(default=None, description="季号")
    rating: Optional[float] = Field(default=None, description="评分")
    confidence: str = Field(default="", description="身份置信度级别")
    media_source: Optional[str] = Field(default=None, description="解析出的来源")
    media_id: Optional[str] = Field(default=None, description="解析出的媒体 ID")
    review_score: Optional[float] = Field(default=None, description="L4 待确认相似度")
    #: TMDB 海报路径（形如 ``/abc.jpg``）。前端据此走插件后端代理取图 ——
    #: 浏览器直连 image.tmdb.org 在国内网络下不可用。
    #:
    #: **必须在这里声明**，否则 pydantic 会把库里记录的该字段直接丢弃，
    #: 前端拿不到 poster、也就不会发出 /poster 请求（真机现象：F12 里
    #: 完全看不到 poster 请求，一行 placeholder 图标）。
    poster: Optional[str] = Field(default=None, description="海报路径")
    run_at: str = Field(default="", description="所属运行时间")


class HistoryPage(BaseModel):
    """分页流水。"""

    items: List[HistoryRecord] = Field(default_factory=list, description="当前页记录")
    total: int = Field(default=0, description="总条数")
    page: int = Field(default=1, description="当前页")
    count: int = Field(default=20, description="每页条数")
    #: 各决策的条数（不受 decision 筛选影响，只受 source/keyword 影响）。
    #: 前端顶部 tab 直接用它显示「新增 24 / 待确认 30 …」，不必额外请求。
    counts: Dict[str, int] = Field(default_factory=dict, description="按决策的条数")


# --------------------------------------------------------------------- 手动运行

class RunOnceResult(BaseModel):
    """手动触发一次发现的结果。"""

    accepted: bool = Field(description="是否受理本次触发")
    skipped: bool = Field(default=False, description="是否因已有运行而跳过")
    summary: Dict[str, Any] = Field(default_factory=dict, description="运行汇总")


# --------------------------------------------------------------------- 只读预览

class PreviewItem(BaseModel):
    """预览中的一条候选。"""

    title: str = Field(description="标题")
    year: Optional[str] = Field(default=None, description="年份")
    media_type: str = Field(default="", description="movie / tv")
    release_date: Optional[str] = Field(default=None, description="定档日期")
    popularity: Optional[float] = Field(default=None, description="关注度")
    rating: Optional[float] = Field(default=None, description="评分")
    language: str = Field(default="", description="原始语言")
    source: str = Field(default="", description="数据源")
    confidence: str = Field(default="", description="身份置信度")
    media_source: str = Field(default="", description="解析出的媒体来源")
    media_id: str = Field(default="", description="解析出的媒体 ID")
    decision: str = Field(default="", description="决策")
    reason: str = Field(default="", description="原因")


class PreviewResult(BaseModel):
    """只读预览结果：会订哪些、被拦下多少、原因分布。"""

    skipped: bool = Field(default=False, description="是否因已有运行而跳过")
    summary: Dict[str, Any] = Field(default_factory=dict, description="运行汇总")
    items: List[PreviewItem] = Field(default_factory=list, description="候选明细（按关注度降序）")
    rejections: Dict[str, int] = Field(default_factory=dict, description="被拦下的原因分布")


# --------------------------------------------------------------------- 映射缓存

class MappingEntry(BaseModel):
    """一条身份映射缓存。"""

    key: str = Field(description="缓存键")
    media_source: str = Field(description="媒体来源")
    media_id: str = Field(description="媒体 ID")
    confidence: str = Field(default="", description="置信度级别")
    reason: str = Field(default="", description="产生原因")


class MappingCacheView(BaseModel):
    """映射缓存视图。"""

    size: int = Field(default=0, description="缓存条数")
    entries: List[MappingEntry] = Field(default_factory=list, description="缓存内容")


class MappingFixRequest(BaseModel):
    """人工修正映射请求。"""

    key: str = Field(description="要修正/新增的缓存键")
    media_source: str = Field(default="themoviedb", description="媒体来源")
    media_id: str = Field(description="媒体 ID")


class MappingFixResult(BaseModel):
    """人工修正映射结果。"""

    success: bool = Field(description="是否写入成功")
    key: str = Field(description="缓存键")


#: 路由 → 响应业务模型
API_RESPONSE_MODELS: Dict[str, Any] = {
    "/status": PluginStatus,
    "/history": HistoryPage,
    "/run_once": RunOnceResult,
    "/preview": PreviewResult,
    "/mapping_cache": MappingCacheView,
    "/mapping_cache/fix": MappingFixResult,
}


__all__ = [
    "API_RESPONSE_MODELS",
    "HistoryPage",
    "HistoryRecord",
    "MappingCacheView",
    "MappingEntry",
    "MappingFixRequest",
    "MappingFixResult",
    "PluginStatus",
    "PreviewItem",
    "PreviewResult",
    "RunOnceResult",
    "SourceState",
]
