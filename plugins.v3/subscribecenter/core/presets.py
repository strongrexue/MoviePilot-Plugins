"""一键场景预设：把 60+ 个配置项按「你想追什么」压成三个按钮。

为什么需要：配置页现在有 9 个分区、66 个配置项，新用户根本不知道该开哪个源、
窗口写几天、阈值写多少。预设只改**和场景强相关**的十几项，其余（RSSHub 域名、
cron、通知、自动启停…）原样保留 —— 用户配过的东西不能被预设悄悄改掉。

三个场景的取舍（都基于真机实测数据）：

- ``anime`` 追番：AniList 为主（日番 + 国漫），B 站番剧时间表当备份；
  豆瓣榜单关掉（动画榜与 AniList 大量重合，白花 TMDB 请求）。
- ``domestic`` 国产剧/综艺：豆瓣榜单 + 腾讯「即将上线」为主，AniList 补国漫；
  外语过滤关掉（国产剧本来就不会被语言门槛拦，但用户可能想看日韩剧时不必再改）；
  想看人数门槛 300 挡掉冷门网剧。
- ``movie`` 院线新片：TMDB + 豆瓣「即将上映 / 实时热门 / 一周口碑」，
  发行日兜底打开（豆瓣榜单不给日期，靠 TMDB 补），窗口 30 天。
"""
import copy
from typing import Any, Dict, List

from .constants import DEFAULT_DOUBAN_LISTS, default_config

#: 预设标识 → 一句话说明（前端按钮文案与后端日志共用）
PRESETS: Dict[str, Dict[str, Any]] = {
    "anime": {
        "title": "追番",
        "desc": "日番 + 国漫，AniList 为主、B 站番剧时间表兜底",
        "patch": {
            "enable_tmdb": False,
            "enable_anilist": True,
            "anilist_include_donghua": True,
            "anilist_future_days": 7,
            "anilist_min_popularity": 500,
            "enable_bangumi": False,
            "enable_douban_rss": True,
            "enable_qq_video": False,
            "enable_bilibili": True,
            "bilibili_future_days": 7,
            "bilibili_max_items": 30,
            "daily_limit": 30,
        },
    },
    "domestic": {
        "title": "国产剧 / 综艺",
        "desc": "豆瓣榜单 + 腾讯即将上线，AniList 补国漫",
        "patch": {
            "enable_tmdb": False,
            "enable_anilist": True,
            "anilist_include_donghua": True,
            "anilist_future_days": 7,
            "enable_bangumi": False,
            "enable_douban_rss": True,
            "douban_future_days": 3,
            "douban_max_items_per_feed": 20,
            "douban_min_want": 300,
            "min_rating_douban": 6.0,
            "enable_qq_video": True,
            "qq_video_channels": ["tv", "variety"],
            "qq_video_max_items": 40,
            "enable_bilibili": False,
            "filter_original_language": False,
            "daily_limit": 30,
        },
    },
    "movie": {
        "title": "院线新片",
        "desc": "电影即将上映 + 热门/口碑，靠 TMDB 补发行日",
        "patch": {
            "enable_tmdb": True,
            "tmdb_future_days": 30,
            "min_rating_tmdb": 6.0,
            "min_popularity": 15.0,
            "enable_anilist": False,
            "enable_bangumi": False,
            "enable_douban_rss": True,
            "douban_future_days": 30,
            "douban_min_want": 0,
            "min_rating_douban": 6.0,
            "enable_qq_video": True,
            "qq_video_channels": ["movie"],
            "enable_bilibili": False,
            "movie_release_fallback": True,
            "movie_release_grace_days": 7,
            "daily_limit": 20,
        },
    },
}

#: 每个场景要开的豆瓣榜单（其余关掉，减少白跑）
_PRESET_FEEDS: Dict[str, List[str]] = {
    "anime": ["/douban/list/tv_animation"],
    "domestic": [
        "/douban/tv/coming",
        "/douban/list/tv_domestic",
        "/douban/list/show_domestic",
        "/douban/list/tv_animation",
    ],
    "movie": [
        "/douban/movie/coming",
        "/douban/list/movie_real_time_hotest",
        "/douban/list/movie_weekly_best",
    ],
}


def preset_keys() -> List[str]:
    """可用预设标识（不含 ``reset``）。"""
    return list(PRESETS)


def describe() -> List[Dict[str, str]]:
    """预设清单（喂给前端渲染按钮，避免文案两处维护）。"""
    return [
        {"key": key, "title": str(meta["title"]), "desc": str(meta["desc"])}
        for key, meta in PRESETS.items()
    ]


def build_douban_lists(urls: List[str]) -> List[Dict[str, Any]]:
    """按内置榜单表生成一份「只开这几条」的豆瓣源配置。

    参数化其它字段（每榜条数/窗口/想看）取内置默认值 —— 预设是「从零开始的
    一套合理配置」，不是在你现有配置上打补丁，所以这些也跟着回默认。
    """
    wanted = set(urls)
    entries: List[Dict[str, Any]] = []
    for preset in DEFAULT_DOUBAN_LISTS:
        entry = copy.deepcopy(preset)
        entry["enabled"] = str(entry.get("url") or "") in wanted
        entries.append(entry)
    return entries


def apply(config: Dict[str, Any], name: str) -> Dict[str, Any]:
    """返回套用预设后的**新配置**（不改原字典）。

    :param name: ``anime`` / ``domestic`` / ``movie`` / ``reset``
    :raises ValueError: 预设名不认识
    """
    key = str(name or "").strip().lower()
    if key == "reset":
        # 恢复出厂：整份默认值；但 RSSHub 域名与 cron 这类「环境相关」的保留
        fresh = copy.deepcopy(default_config())
        for keep in ("rsshub_domain", "timezone", "cron", "notify"):
            if config.get(keep) not in (None, ""):
                fresh[keep] = config[keep]
        return fresh
    meta = PRESETS.get(key)
    if meta is None:
        raise ValueError(f"未知的预设：{name}")

    updated = dict(config)
    updated.update(copy.deepcopy(dict(meta["patch"])))
    feeds = _PRESET_FEEDS.get(key) or []
    if feeds and updated.get("enable_douban_rss"):
        updated["douban_rss_sources"] = build_douban_lists(feeds)
    return updated


def title_of(name: str) -> str:
    """预设的中文名（回执/日志用）。"""
    key = str(name or "").strip().lower()
    if key == "reset":
        return "恢复默认"
    return str(PRESETS.get(key, {}).get("title") or key)


__all__ = ["PRESETS", "apply", "build_douban_lists", "describe", "preset_keys", "title_of"]
