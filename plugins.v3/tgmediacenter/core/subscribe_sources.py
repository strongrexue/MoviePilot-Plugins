"""③ 订阅服务的订阅源常量表（双通道，纯数据，无网络）。

两条腿：
- **MP 榜单**（``channel="mp"``）：走宿主 ``TmdbChain`` / ``BangumiChain``，零配置；
- **豆瓣榜单**（``channel="douban"``）：走 RSSHub（``RssHelper.parse``）。

每个源统一描述为 ``SourceDef``，供前端渲染勾选列表、后端按 key 分发拉取。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SourceDef:
    """一个订阅源的静态描述。"""

    key: str                 # 唯一标识（配置里引用）
    channel: str             # mp | douban
    name: str                # 展示名
    media_type: str          # movie | tv | animation | all（建订阅时归一为 MediaType）
    path: str = ""           # 豆瓣源的 RSSHub 相对路径（mp 源为空）


# MP 榜单（走宿主 API）
MP_SOURCES: List[SourceDef] = [
    SourceDef("tmdb_trending", "mp", "TMDB 流行趋势", "all"),
    SourceDef("tmdb_movie", "mp", "TMDB 热门电影", "movie"),
    SourceDef("tmdb_tv", "mp", "TMDB 热门剧集", "tv"),
    SourceDef("bangumi_calendar", "mp", "Bangumi 每日放送", "animation"),
]

# 豆瓣榜单（走 RSSHub；path 为 /douban/ 之后的相对路径）
DOUBAN_SOURCES: List[SourceDef] = [
    SourceDef("movie_showing", "douban", "影院热映", "movie", "list/movie_showing"),
    SourceDef("movie_hot_gaia", "douban", "豆瓣热门电影", "movie", "list/movie_hot_gaia"),
    SourceDef("movie_soon", "douban", "院线即将上映", "movie", "list/movie_soon"),
    SourceDef("movie_weekly_best", "douban", "一周口碑电影榜", "movie", "list/movie_weekly_best"),
    SourceDef("tv_hot", "douban", "近期热门剧集", "tv", "list/tv_hot"),
    SourceDef("tv_domestic", "douban", "近期热门国产剧", "tv", "list/tv_domestic"),
    SourceDef("tv_american", "douban", "近期热门美剧", "tv", "list/tv_american"),
    SourceDef("tv_japanese", "douban", "近期热门日剧", "tv", "list/tv_japanese"),
    SourceDef("tv_korean", "douban", "近期热门韩剧", "tv", "list/tv_korean"),
    SourceDef("tv_animation", "douban", "近期热门动画", "animation", "list/tv_animation"),
    SourceDef("tv_documentary", "douban", "近期热门纪录片", "tv", "list/tv_documentary"),
    SourceDef("show_domestic", "douban", "近期热门国内综艺", "tv", "list/show_domestic"),
    SourceDef("show_foreign", "douban", "近期热门国外综艺", "tv", "list/show_foreign"),
    SourceDef("recommended_tv", "douban", "豆瓣推荐·剧集", "tv", "recommended/tv"),
    SourceDef("tv_coming", "douban", "剧集即将上线", "tv", "tv/coming"),
]

ALL_SOURCES: List[SourceDef] = MP_SOURCES + DOUBAN_SOURCES


def source_map() -> dict:
    """key → SourceDef，供后端按 key 快速分发。"""
    return {source.key: source for source in ALL_SOURCES}


def sources_by_channel(channel: str) -> List[SourceDef]:
    """按通道返回订阅源列表。"""
    return [source for source in ALL_SOURCES if source.channel == channel]


def to_dict(source: SourceDef) -> dict:
    """转为可序列化 dict（供前端 / API）。"""
    return {
        "key": source.key,
        "channel": source.channel,
        "name": source.name,
        "media_type": source.media_type,
        "path": source.path,
    }


def all_sources_dict() -> List[dict]:
    """全部订阅源的可序列化清单。"""
    return [to_dict(source) for source in ALL_SOURCES]


def rss_url(source: SourceDef, rsshub_base: str) -> str:
    """豆瓣源拼接完整 RSSHub 地址。"""
    base = str(rsshub_base or "").strip().rstrip("/")
    path = source.path.lstrip("/")
    return f"{base}/douban/{path}"


def lookup(key: str) -> Optional[SourceDef]:
    """按 key 查订阅源；不存在返回 None。"""
    return source_map().get(key)
