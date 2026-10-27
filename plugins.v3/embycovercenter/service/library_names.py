"""媒体库名的中英对照词典（副标题 / 英文名的唯一来源）。

单独成一个模块是为了让 ``emby_assets``（素材层）和 ``cover_auto``（任务层）
都能用它，而两者之间不能互相 import（``cover_auto`` 依赖 ``emby_assets``）。
前端 ``src/components/cover/useCoverDesigner.js`` 里有一份同样的副本，
改动词典时两边要一起改。
"""
from __future__ import annotations

from typing import Any

# 常见媒体库名的中英对照：命中则用英文，未命中回退库名本身。
# 键统一小写，兼容「4K电影 / 4k电影」这类写法。
LIBRARY_EN_NAMES = {
    "电影": "Movies",
    "电影库": "Movies",
    "欧美电影": "Western Movies",
    "华语电影": "Chinese Movies",
    "日韩电影": "Asian Movies",
    "4k电影": "4K Movies",
    "电视剧": "TV Shows",
    "剧集": "TV Shows",
    "电视节目": "TV Shows",
    "动漫": "Anime",
    "动画": "Anime",
    "番剧": "Anime",
    "日番": "Anime",
    "国漫": "Chinese Animation",
    "综艺": "Variety Shows",
    "纪录片": "Documentaries",
    "儿童": "Kids",
    "少儿": "Kids",
    "亲子": "Kids",
    "音乐": "Music",
    "mv": "Music Videos",
    "体育": "Sports",
    "教育": "Education",
    "有声书": "Audiobooks",
}


def english_name_for(name: Any) -> str:
    """按库名查内置英文名；未命中返回空串（键统一小写）。"""
    key = str(name or "").strip().lower()
    return LIBRARY_EN_NAMES.get(key, "")
