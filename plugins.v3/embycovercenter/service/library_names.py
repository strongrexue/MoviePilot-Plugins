"""媒体库名的中英对照与分类文案词典（副标题 / 标语 / 题材标签的唯一来源）。

单独成一个模块是为了让 ``emby_assets``（素材层）和 ``cover_auto``（任务层）
都能用它，而两者之间不能互相 import（``cover_auto`` 依赖 ``emby_assets``）。
前端 ``src/components/cover/useCoverDesigner.js`` 里有一份同样的副本，
改动词典时两边要一起改。

``LIBRARY_COPY`` 是「分类横幅」这套版式的文案库：每个媒体库一条，含英文名、
中文标语、英文标语、题材标签。布局里的同名字段留空时就取这里的值，
所以预设模板不用为每个库各存一份。
"""
from __future__ import annotations

from typing import Any, Dict, List

# 分类文案：键统一小写，兼容「4K电影 / 4k电影」这类写法。
# slogan_cn 里的空格是「分段」，渲染时段与段之间用 slogan_spacing 控制间距，
# 不是换行 —— 中文标语始终只有一行。
LIBRARY_COPY: Dict[str, Dict[str, Any]] = {
    "儿童": {
        "en": "KIDS",
        "slogan_cn": "童心世界 欢乐成长",
        "slogan_en": "A WORLD OF WONDER AND JOY",
        "tags": ["动画", "冒险", "家庭", "成长", "亲子"],
        "watermark": "勇敢出发 快乐长大",
        "quote": ("冒险就在那里", "《飞屋环游记》"),
    },
    "少儿": {
        "en": "KIDS",
        "slogan_cn": "童心世界 欢乐成长",
        "slogan_en": "A WORLD OF WONDER AND JOY",
        "tags": ["动画", "冒险", "家庭", "成长", "亲子"],
        "watermark": "勇敢出发 快乐长大",
        "quote": ("冒险就在那里", "《飞屋环游记》"),
    },
    "国漫": {
        "en": "CHINESE ANIMATION",
        "slogan_cn": "东方美学 国创崛起",
        "slogan_en": "ORIENTAL AESTHETICS·RISING CHINESE CREATION",
        "tags": ["玄幻", "武侠", "修仙", "热血", "传承"],
    },
    "国产剧": {
        "en": "CHINESE SERIES",
        "slogan_cn": "好故事 好人生",
        "slogan_en": "GOOD STORIES, GOOD LIFE",
        "tags": ["爱情", "都市", "悬疑", "剧情", "家庭"],
    },
    "港台剧": {
        "en": "HONG KONG & TAIWAN SERIES",
        "slogan_cn": "警匪对决 江湖情义 时代风云",
        "slogan_en": "CRIME. LOYALTY. AN ERA OF LEGENDS.",
        "tags": ["警匪", "剧情", "悬疑", "犯罪", "卧底"],
        "watermark": "浪奔浪流 恩怨如潮",
        "quote": ("出来混，迟早要还的", "《无间道》"),
    },
    "日韩剧": {
        "en": "JAPANESE & KOREAN SERIES",
        "slogan_cn": "细腻情感 温暖人心",
        "slogan_en": "TENDER HEARTS, WARM STORIES",
        "tags": ["爱情", "家庭", "职场", "治愈", "悬疑"],
    },
    "欧美剧": {
        "en": "WESTERN SERIES",
        "slogan_cn": "真实世界 复杂人性 无尽权力",
        "slogan_en": "REAL WORLD, COMPLEX HUMANITY, ENDLESS POWER",
        "tags": ["剧情", "悬疑", "科幻", "犯罪", "权力", "人性"],
    },
    "日番": {
        "en": "JAPANESE ANIMATION",
        "slogan_cn": "梦想 指引 遇见未来",
        "slogan_en": "DREAMS GUIDE US TO THE FUTURE",
        "tags": ["青春", "奇幻", "冒险", "成长", "治愈"],
    },
    "欧美漫": {
        "en": "WESTERN COMICS",
        "slogan_cn": "英雄集结 正邪对决 热血史诗",
        "slogan_en": "HEROES. BATTLES. LEGENDS.",
        "tags": ["超英", "动作", "科幻", "奇幻", "冒险"],
        "watermark": "英雄不孤 热血不灭",
        "quote": ("能力越大，责任越大", "《蜘蛛侠》"),
    },
    "综艺": {
        "en": "VARIETY SHOW",
        "slogan_cn": "快乐相聚 精彩无限",
        "slogan_en": "JOY TOGETHER, WONDERFUL MOMENTS",
        "tags": ["真人秀", "游戏", "音乐", "脱口秀", "访谈", "旅行"],
    },
    "纪录片": {
        "en": "DOCUMENTARIES",
        "slogan_cn": "探索世界 见证真实",
        "slogan_en": "EXPLORE. DISCOVER. FOR REAL.",
        "tags": ["自然", "历史", "科学", "人文", "探险"],
        "watermark": "仰望星空 脚踏大地",
        "quote": ("我们都在阴沟里，但仍有人仰望星空", "王尔德"),
    },
    "动画电影": {
        "en": "ANIMATED MOVIES",
        "slogan_cn": "想象无界 故事无限",
        "slogan_en": "IMAGINATION HAS NO LIMITS, STORIES NEVER END",
        "tags": ["奇幻", "冒险", "科幻", "成长", "热血"],
    },
    "华语电影": {
        "en": "CHINESE FILMS",
        "slogan_cn": "故事无界·经典永恒",
        "slogan_en": "STORIES WITHOUT BORDERS, CLASSICS FOREVER",
        "tags": ["动作", "武侠", "奇幻", "剧情", "历史"],
    },
    "日韩电影": {
        "en": "JAPANESE & KOREAN FILMS",
        "slogan_cn": "光影物语 城市情绪",
        "slogan_en": "STORIES IN LIGHT AND RAIN",
        "tags": ["剧情", "爱情", "悬疑", "治愈", "文艺"],
        "watermark": "一期一会 光影为证",
        "quote": ("曾经发生的事不可能忘记，只是暂时想不起来而已", "《千与千寻》"),
    },
    "外语电影": {
        "en": "FOREIGN FILMS",
        "slogan_cn": "探索世界 看见更多可能",
        "slogan_en": "EXPLORE THE WORLD, SEE MORE POSSIBILITIES",
        "tags": ["科幻", "动作", "剧情", "悬疑", "冒险"],
    },
    "纪录影片": {
        "en": "DOCUMENTARY FILMS",
        "slogan_cn": "地球脉动 万物奇迹",
        "slogan_en": "THE PLANET. THE WILD. THE TRUE.",
        "tags": ["自然", "宇宙", "海洋", "地理", "生灵"],
        "watermark": "万物有灵 山海无恙",
        "quote": ("就在此刻，地球上某个角落，奇迹正在发生", "《地球脉动》"),
    },
    "演唱会": {
        "en": "CONCERTS",
        "slogan_cn": "声光盛宴 燃动现场",
        "slogan_en": "LIVE MUSIC FOREVER",
        "tags": ["流行", "摇滚", "现场", "音乐", "狂欢"],
        "watermark": "声浪不息 热爱不止",
        "quote": ("The show must go on", "《波西米亚狂想曲》"),
    },
}

# 未收录在 LIBRARY_COPY 里的常见库名，只给英文名（标语/标签留空，回退手填）。
EXTRA_EN_NAMES = {
    "电影": "Movies",
    "电影库": "Movies",
    "欧美电影": "Western Movies",
    "4k电影": "4K Movies",
    "电视剧": "TV Shows",
    "剧集": "TV Shows",
    "电视节目": "TV Shows",
    "动漫": "Anime",
    "动画": "Anime",
    "番剧": "Anime",
    "亲子": "Kids",
    "音乐": "Music",
    "mv": "Music Videos",
    "体育": "Sports",
    "教育": "Education",
    "有声书": "Audiobooks",
}

# 常见媒体库名的中英对照：命中则用英文，未命中回退库名本身。
LIBRARY_EN_NAMES = {**EXTRA_EN_NAMES, **{key: value["en"] for key, value in LIBRARY_COPY.items()}}


def english_name_for(name: Any) -> str:
    """按库名查内置英文名；未命中返回空串（键统一小写）。"""
    key = str(name or "").strip().lower()
    return LIBRARY_EN_NAMES.get(key, "")


def copy_for(name: Any) -> Dict[str, Any]:
    """按库名取整套分类文案；未收录返回空字典（调用方回退手填值）。"""
    key = str(name or "").strip().lower()
    return LIBRARY_COPY.get(key, {})


def slogan_cn_for(name: Any) -> str:
    """按库名取中文标语；未收录返回空串。"""
    return str(copy_for(name).get("slogan_cn") or "")


def slogan_en_for(name: Any) -> str:
    """按库名取英文标语；未收录返回空串。"""
    return str(copy_for(name).get("slogan_en") or "")


def tags_for(name: Any) -> List[str]:
    """按库名取题材标签列表；未收录返回空列表。"""
    tags = copy_for(name).get("tags") or []
    return [str(item).strip() for item in tags if str(item).strip()]


def watermark_for(name: Any) -> str:
    """按库名取书法水印文字（一句竖排短语）；未收录返回空串。"""
    return str(copy_for(name).get("watermark") or "")


def quote_for(name: Any) -> tuple:
    """按库名取右下角引文 (正文, 出处)；未收录返回 ("", "")。"""
    item = copy_for(name).get("quote") or ("", "")
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return str(item[0] or ""), str(item[1] or "")
    return str(item or ""), ""
