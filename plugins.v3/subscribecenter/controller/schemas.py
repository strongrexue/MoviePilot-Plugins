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
    country: Optional[str] = Field(default=None, description="产地（CN/JP/...）")
    run_at: str = Field(default="", description="所属运行时间")


class CardThemeRequest(BaseModel):
    """保存订阅卡片配色。"""

    colors: Optional[Dict[str, str]] = Field(default=None, description="状态色；传 null 或 reset=true 表示恢复默认")
    reset: bool = Field(default=False, description="恢复默认（删除插件写入的 CSS）")


class CardThemeResult(BaseModel):
    """配色写入结果。"""

    success: bool = Field(description="是否写入成功")
    error: str = Field(default="", description="失败原因")
class CardTheme(BaseModel):
    """当前订阅卡片配色。"""

    colors: Dict[str, str] = Field(default_factory=dict, description="状态色")
    applied: bool = Field(default=False, description="是否已写入宿主 CSS")


class CalendarItem(BaseModel):
    """今日日历的一条。"""

    id: int = Field(description="订阅 ID")
    name: str = Field(description="标题")
    season: int = Field(default=0, description="季")
    poster: str = Field(default="", description="海报路径")
    media_source: str = Field(default="", description="媒体来源")
    media_id: str = Field(default="", description="媒体 ID")
    total_episode: int = Field(default=0, description="总集数")
    lack_episode: int = Field(default=0, description="缺失集数")
    start_episode: int = Field(default=1, description="起始集")
    state: str = Field(default="", description="订阅状态")
    best_version: bool = Field(default=False, description="是否洗版")
    kind: str = Field(default="updated", description="updated=今日已入库 / pending=今日待播")
    episodes: List[int] = Field(default_factory=list, description="当天播出的集号")
    air_time: str = Field(default="", description="播出时间 HH:MM")
    air_date: str = Field(default="", description="播出日期")
    today: str = Field(default="", description="今天的日期")
    searched: Optional[bool] = Field(
        default=None,
        description="今天会不会被刷新搜到（自动启停的判定，None=未开启自动启停或非今日）",
    )
    search_note: str = Field(default="", description="不会被搜的原因")
    release_kind: str = Field(
        default="", description="电影用的哪种发行日：digital/physical/theatrical/…"
    )


class CalendarView(BaseModel):
    """今日日历视图。"""

    today: str = Field(description="所选日期（YYYY-MM-DD）")
    total: int = Field(default=0)
    updated: int = Field(default=0, description="今日已入库")
    pending: int = Field(default=0, description="今日待播")
    best_version: int = Field(default=0, description="其中洗版条数")
    items: List[CalendarItem] = Field(default_factory=list)


class CalendarMonth(BaseModel):
    """整月日历（复刻 MoviePilot 日历页）。"""

    month: str = Field(description="月份 YYYY-MM")
    today: str = Field(default="", description="服务器本地今天（前端高亮用）")
    total: int = Field(default=0, description="本月条目总数")
    per_day_limit: int = Field(default=5, description="每格默认展示条数")
    days: Dict[str, List[CalendarItem]] = Field(
        default_factory=dict, description="日期 → 当天条目"
    )


class HistoryPage(BaseModel):
    """分页流水。"""

    items: List[HistoryRecord] = Field(default_factory=list, description="当前页记录")
    total: int = Field(default=0, description="总条数")
    page: int = Field(default=1, description="当前页")
    count: int = Field(default=20, description="每页条数")
    #: 各决策的条数（不受 decision 筛选影响，只受 source/keyword 影响）。
    #: 前端顶部 tab 直接用它显示「新增 24 / 待确认 30 …」，不必额外请求。
    counts: Dict[str, int] = Field(default_factory=dict, description="按决策的条数")
    #: 各数据源条数（同样在筛选之前统计），供前端「按源」tab 使用
    source_counts: Dict[str, int] = Field(default_factory=dict, description="按数据源的条数")


# --------------------------------------------------------------------- 手动运行

class SystemShareState(BaseModel):
    """订阅数据共享开关状态。"""

    enabled: bool = Field(default=False, description="是否开启")


class SystemShareRequest(BaseModel):
    """设置订阅数据共享。"""

    enabled: bool = Field(default=False, description="是否开启")


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

    key: str = Field(default="", description="映射缓存键（可留空，由 title 生成）")
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

    #: 也可不传 key，直接用「标题 + 年份 + 类型」表达 —— 前端只需让用户填
    #: TMDB ID，键由后端归一化生成（真机：国漫有动画版/真人版两条同名条目，
    #: 自动区分需要 genre 数据，人工指定最可靠）。
    title: Optional[str] = Field(default=None, description="标题（替代 key）")
    year: Optional[str] = Field(default=None, description="年份")
    media_type: str = Field(default="tv", description="movie / tv")
    key: str = Field(default="", description="要修正/新增的缓存键")
    media_source: str = Field(default="themoviedb", description="媒体来源")
    media_id: str = Field(default="", description="媒体 ID")


class MappingFixResult(BaseModel):
    """人工修正映射结果。"""

    success: bool = Field(description="是否写入成功")
    key: str = Field(description="缓存键")


# --------------------------------------------------------------------- 自动启停

class AutoToggleItem(BaseModel):
    """自动启停：一条订阅的判定结论。"""

    id: int = Field(description="订阅 ID")
    name: str = Field(description="标题")
    season: int = Field(default=0, description="季")
    state: str = Field(default="", description="当前状态")
    target: str = Field(default="", description="判定后应处的状态")
    action: str = Field(description="pause / resume / keep / skip")
    reason: str = Field(description="原因码")
    reason_label: str = Field(default="", description="原因中文名")
    detail: str = Field(default="", description="一句中文说明")
    #: 已播但还没入库的集号 —— 用户最关心的是「为什么它还在搜」，这就是答案
    pending: List[int] = Field(default_factory=list, description="已播未入库的集号")
    next_air: str = Field(default="", description="下一集播出日")
    last_air: str = Field(default="", description="已播最新一集的播出日")
    aired: int = Field(default=0, description="已播集数")
    downloaded: int = Field(default=0, description="已入库集数")
    owned: bool = Field(default=False, description="是否由本插件暂停（接管中）")
    #: 电影专用的基准日：TMDB 的发行日（剧集为空）
    basis: str = Field(default="", description="电影的发行基准日")
    basis_kind: str = Field(
        default="", description="基准日类型：digital / physical / theatrical …"
    )


class AutoToggleConfig(BaseModel):
    """自动启停的生效配置（已收敛边界，前端直接展示）。"""

    enabled: bool = Field(default=False, description="总开关")
    cron: str = Field(default="", description="判定时间（cron）")
    lookahead_days: int = Field(default=0, description="提前天数")
    keep_days: int = Field(default=0, description="已播未入库的保留天数")
    best_keep_days: int = Field(default=0, description="洗版订阅的保留天数")
    movie_enabled: bool = Field(default=True, description="是否连电影一起管")
    max_changes: int = Field(default=0, description="单次改动上限（0=不限）")
    notify: bool = Field(default=False, description="是否通知")


class AutoToggleLastRun(BaseModel):
    """自动启停：上次执行摘要（没跑过时全是 0/空）。"""

    at: str = Field(default="", description="执行时间")
    today: str = Field(default="", description="判定日期")
    reason: str = Field(default="", description="cron / manual")
    planned: int = Field(default=0, description="计划改动条数")
    applied: int = Field(default=0, description="实际成功条数")
    paused: int = Field(default=0, description="暂停条数")
    resumed: int = Field(default=0, description="恢复条数")
    failed: int = Field(default=0, description="失败条数")
    truncated: bool = Field(default=False, description="是否被单次上限截断")


class AutoToggleView(BaseModel):
    """自动启停：预览/状态视图。"""

    today: str = Field(description="判定日期（插件时区）")
    items: List[AutoToggleItem] = Field(default_factory=list, description="全部判定")
    changes: List[AutoToggleItem] = Field(default_factory=list, description="会改库的条目")
    planned: int = Field(default=0, description="计划改动条数")
    paused: int = Field(default=0, description="计划暂停条数")
    resumed: int = Field(default=0, description="计划恢复条数")
    kept: int = Field(default=0, description="保持不动的条数")
    skipped: int = Field(default=0, description="跳过（不归本功能管）的条数")
    reasons: Dict[str, int] = Field(default_factory=dict, description="各原因条数")
    truncated: bool = Field(default=False, description="是否被单次上限截断")
    config: AutoToggleConfig = Field(description="生效配置")
    last_run: AutoToggleLastRun = Field(
        default_factory=AutoToggleLastRun, description="上次执行摘要"
    )
    owned: int = Field(default=0, description="当前被本插件暂停的订阅数")


class AutoToggleResult(BaseModel):
    """自动启停：执行结果。"""

    today: str = Field(description="判定日期")
    reason: str = Field(default="", description="cron / manual")
    planned: int = Field(default=0, description="计划改动条数")
    applied: int = Field(default=0, description="成功条数")
    paused: int = Field(default=0, description="暂停条数")
    resumed: int = Field(default=0, description="恢复条数")
    failed: List[Dict[str, Any]] = Field(
        default_factory=list, description="失败明细（id/name/error）"
    )
    truncated: bool = Field(default=False, description="是否被单次上限截断")
    kept: int = Field(default=0)
    skipped: int = Field(default=0)
    reasons: Dict[str, int] = Field(default_factory=dict)
    owned: int = Field(default=0, description="执行后接管中的订阅数")
    last_run: AutoToggleLastRun = Field(
        default_factory=AutoToggleLastRun, description="执行摘要"
    )


#: 路由 → 响应业务模型
API_RESPONSE_MODELS: Dict[str, Any] = {
    "/status": PluginStatus,
    "/history": HistoryPage,
    "/calendar": CalendarMonth,
    "/calendar/day": CalendarView,
    "/auto_toggle": AutoToggleView,
    "/auto_toggle/apply": AutoToggleResult,
    "/card_theme": CardTheme,
    "/card_theme/save": CardThemeResult,
    "/run_once": RunOnceResult,
    "/preview": PreviewResult,
    "/system_share": SystemShareState,
    "/system_share/save": SystemShareState,
    "/mapping_cache": MappingCacheView,
    "/mapping_cache/fix": MappingFixResult,
}


__all__ = [
    "API_RESPONSE_MODELS",
    "AutoToggleConfig",
    "AutoToggleItem",
    "AutoToggleLastRun",
    "AutoToggleResult",
    "AutoToggleView",
    "CalendarItem",
    "CalendarMonth",
    "CalendarView",
    "HistoryPage",
    "CardTheme",
    "CardThemeRequest",
    "CardThemeResult",
    "HistoryRecord",
    "MappingCacheView",
    "MappingEntry",
    "MappingFixRequest",
    "MappingFixResult",
    "PluginStatus",
    "PreviewItem",
    "PreviewResult",
    "SystemShareState",
    "SystemShareRequest",
    "RunOnceResult",
    "SourceState",
]
