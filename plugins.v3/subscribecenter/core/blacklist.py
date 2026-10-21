"""发现黑名单：按「类型」与「题材」排除不想订阅的条目。

设计取舍（全部来自真机数据与用户反馈）：

1. **默认关闭、默认空词表**。内置词表只是「预设」，必须用户勾选才生效
   —— 否则别人装了插件，自己爱看的题材会被静默拦掉。
2. **拆成两个区**：``排除类型``（TMDB genre id，结构化、准）与
   ``排除题材``（文本词，能抓到 TMDB 类型表里没有的东西）。
   关键事实：TMDB 的 genre 列表里**没有「同性」**（电影 18 类 / 剧集 16 类，
   见 :data:`GENRE_NAMES`），它只是豆瓣 ``category`` 里的一个词、或 TMDB
   keyword。所以「拦同性剧」只能靠题材词，靠类型勾选永远拦不住。
3. **过滤放在身份解析之前**（:func:`core.pipeline.run_pipeline` 第 2.5 步）。
   命中的条目不该再花一次 TMDB 请求去解析身份 —— 参考插件
   ``z2561221/MoviePilot-Plugins`` 的 doubancenter 也是这个位置，实测省一次
   网络往返。
4. **匹配语法照着 doubancenter 的成熟做法**：一行一条、空格分词为「同时包含」
   （AND）、``regex:`` 走正则、``case:`` 区分大小写。唯一改进是**英文按整词
   边界**匹配（``BL`` 不该命中 ``BLADE``、``gay`` 不该命中 ``Gaynor``），
   这是 doubancenter 用纯子串时的已知误伤。

本模块是纯函数：不碰网络、不碰宿主，可离线单测。
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Pattern, Sequence, Set, Tuple

from .constants import MEDIA_TYPE_TV

# --------------------------------------------------------------------- 类型表

#: TMDB genre id -> 中文名（与前端 ``Config.vue`` 的 MOVIE_GENRES / TV_GENRES 一致）
GENRE_NAMES: Dict[int, str] = {
    28: "动作",
    12: "冒险",
    16: "动画",
    35: "喜剧",
    80: "犯罪",
    99: "纪录",
    18: "剧情",
    10751: "家庭",
    14: "奇幻",
    36: "历史",
    27: "恐怖",
    10402: "音乐",
    9648: "悬疑",
    10749: "爱情",
    878: "科幻",
    53: "惊悚",
    10752: "战争",
    37: "西部",
    10759: "动作冒险",
    10762: "儿童",
    10763: "新闻",
    10764: "真人秀",
    10765: "科幻奇幻",
    10766: "肥皂剧",
    10767: "脱口秀",
    10768: "战争政治",
}

#: 类型别名 -> id。用于「来源只给了中文/英文字样」的场景：
#: 豆瓣 RSS 的 ``<category>`` 是 ``2026 / 韩国 / 剧情 同性 犯罪`` 这种文本，
#: 没有 TMDB id；AniList 给的是英文类型名。两边都要能落到 id 上。
GENRE_ALIASES: Dict[str, int] = {
    # 电影 / 剧集共有的
    "动作": 28,
    "action": 28,
    "冒险": 12,
    "adventure": 12,
    "动画": 16,
    "animation": 16,
    "动漫": 16,
    "喜剧": 35,
    "comedy": 35,
    "犯罪": 80,
    "crime": 80,
    "纪录": 99,
    "纪录片": 99,
    "documentary": 99,
    "剧情": 18,
    "drama": 18,
    "家庭": 10751,
    "family": 10751,
    "奇幻": 14,
    "fantasy": 14,
    "历史": 36,
    "history": 36,
    "恐怖": 27,
    "horror": 27,
    "音乐": 10402,
    "music": 10402,
    "悬疑": 9648,
    "mystery": 9648,
    "爱情": 10749,
    "romance": 10749,
    "科幻": 878,
    "science fiction": 878,
    "sci-fi": 878,
    "惊悚": 53,
    "thriller": 53,
    "战争": 10752,
    "war": 10752,
    "西部": 37,
    "western": 37,
    # 剧集侧
    "动作冒险": 10759,
    "action & adventure": 10759,
    "儿童": 10762,
    "kids": 10762,
    "新闻": 10763,
    "news": 10763,
    "真人秀": 10764,
    "综艺": 10764,
    "reality": 10764,
    "科幻奇幻": 10765,
    "sci-fi & fantasy": 10765,
    "肥皂剧": 10766,
    "soap": 10766,
    "脱口秀": 10767,
    "talk": 10767,
    "战争政治": 10768,
    "war & politics": 10768,
}

#: 内置题材预设。**只有用户勾选才会生效**（见 ``default_config()`` 的
#: ``blacklist_presets`` 默认空列表）。
#:
#: 每条 ``words`` 是独立词组：中文按包含匹配，英文按整词匹配，
#: 词组里带空格的（``boys love``）整条按「词组」匹配，不会被拆成 AND。
PRESETS: Tuple[Dict[str, Any], ...] = (
    {
        "key": "lgbt",
        "label": "同性倾向",
        "hint": "同性 / lgbt / gay / lesbian / bisexual / transgender / queer",
        "words": ("同性", "lgbt", "gay", "lesbian", "bisexual", "transgender", "queer"),
    },
    {
        "key": "bl",
        "label": "耽美 BL",
        "hint": "耽美 / BL / boys love / shounen ai / yaoi",
        "words": ("耽美", "BL", "boys love", "shounen ai", "yaoi"),
    },
    {
        "key": "gl",
        "label": "百合 GL",
        "hint": "百合 / GL / girls love / yuri",
        "words": ("百合", "GL", "girls love", "yuri"),
    },
    {
        "key": "variety",
        "label": "综艺 真人秀",
        "hint": "综艺 / 真人秀",
        "words": ("综艺", "真人秀"),
    },
    {
        "key": "talkshow",
        "label": "脱口秀 访谈",
        "hint": "脱口秀 / 访谈",
        "words": ("脱口秀", "访谈"),
    },
    {
        "key": "short",
        "label": "短剧",
        "hint": "短剧 / 微短剧",
        "words": ("短剧", "微短剧"),
    },
)

#: 预设 key -> 预设定义（前端下拉/勾选按这个顺序展示）
PRESET_MAP: Dict[str, Dict[str, Any]] = {preset["key"]: preset for preset in PRESETS}

_ASCII_WORD = re.compile(r"^[0-9A-Za-z][0-9A-Za-z '\-\.]*$")


# --------------------------------------------------------------------- 规则结构


@dataclass(frozen=True)
class _WordRule:
    """一条题材规则的编译结果。"""

    #: 展示用原文（命中时写进流水，用户要能一眼看懂是哪条拦的）
    display: str
    #: 正则模式（``regex:`` 行）；``None`` 表示走分词匹配
    pattern: Optional[Pattern[str]] = None
    #: 分词匹配的 token（全部命中才算命中，即 AND）
    tokens: Tuple[str, ...] = ()
    #: 是否区分大小写
    case_sensitive: bool = False


@dataclass(frozen=True)
class BlacklistRules:
    """一次运行生效的黑名单规则（由配置编译而来，之后只读）。"""

    #: 排除的电影类型（TMDB genre id）
    movie_genres: Tuple[int, ...] = ()
    #: 排除的剧集类型（TMDB genre id）
    tv_genres: Tuple[int, ...] = ()
    #: 题材词规则
    words: Tuple[_WordRule, ...] = ()
    #: 是否匹配片名 / 原名
    match_title: bool = True
    #: 是否匹配来源给的题材串（豆瓣 category / AniList genres+tags）
    match_tags: bool = True
    #: 是否额外查 TMDB keyword（有请求成本，默认关）
    tmdb_keywords: bool = False

    @property
    def active(self) -> bool:
        """有没有任何一条规则 —— 全空时整层跳过，零成本。"""
        return bool(self.movie_genres or self.tv_genres or self.words)

    @property
    def genres_for(self) -> Dict[bool, Tuple[int, ...]]:
        """``{是否剧集: 类型 id 元组}``，便于按媒体类型取。"""
        return {False: self.movie_genres, True: self.tv_genres}


def _as_id_list(value: Any) -> Tuple[int, ...]:
    """把配置里的类型列表归一成去重排序的 id 元组（容忍字符串/空值）。"""
    if isinstance(value, str):
        value = [chunk for chunk in re.split(r"[\s,，]+", value) if chunk]
    if not isinstance(value, (list, tuple, set)):
        return ()
    ids: Set[int] = set()
    for entry in value:
        try:
            genre_id = int(str(entry).strip())
        except (TypeError, ValueError):
            continue
        if genre_id > 0:
            ids.add(genre_id)
    return tuple(sorted(ids))


def _ascii_word_pattern(token: str) -> Pattern[str]:
    """英文/数字 token 的整词匹配（前后不能紧邻字母数字）。"""
    body = r"\s+".join(re.escape(part) for part in token.split())
    return re.compile(rf"(?<![0-9A-Za-z]){body}(?![0-9A-Za-z])")


def _compile_phrase(word: str) -> Optional[_WordRule]:
    """编译「预设词组」：整条一个词，空格按 ``\\s+`` 处理，不拆 AND。"""
    text = str(word or "").strip()
    if not text:
        return None
    if _ASCII_WORD.match(text):
        return _WordRule(display=text, pattern=_ascii_word_pattern(text))
    return _WordRule(display=text, tokens=(text,))


def compile_line(line: str) -> Optional[_WordRule]:
    """编译一行用户自定义题材词。

    语法（与 doubancenter 对齐，多一条英文整词边界）：

    - ``foo bar`` —— 同时包含 ``foo`` 与 ``bar``（AND）
    - ``regex:^\\[.+\\]`` —— 正则
    - ``case:Studio`` —— 区分大小写（可与 ``regex:`` 组合，书写顺序不限）
    - 空行、``#`` 开头 —— 忽略
    """
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None
    case_sensitive = False
    while True:
        lowered = text.lower()
        if lowered.startswith("case:"):
            case_sensitive = True
            text = text[5:].strip()
        elif lowered.startswith("regex:"):
            pattern_text = text[6:].strip()
            if not pattern_text:
                return None
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                pattern = re.compile(pattern_text, flags)
            except re.error:
                # 正则写错就按字面量处理 —— 配置错误不该让整轮发现失败
                return _WordRule(display=f"regex:{pattern_text}", tokens=(pattern_text,))
            return _WordRule(
                display=f"regex:{pattern_text}", pattern=pattern, case_sensitive=True
            )
        else:
            break
    tokens = tuple(part for part in text.split() if part)
    if not tokens:
        return None
    return _WordRule(display=text, tokens=tokens, case_sensitive=case_sensitive)


def rules_from_config(config: Dict[str, Any]) -> BlacklistRules:
    """从插件配置编译出规则；总开关关闭时返回空规则（:attr:`active` 为假）。"""
    if not isinstance(config, dict) or not config.get("blacklist_enabled"):
        return BlacklistRules()

    compiled: List[_WordRule] = []
    presets = config.get("blacklist_presets") or []
    if isinstance(presets, str):
        presets = [chunk for chunk in re.split(r"[\s,，]+", presets) if chunk]
    for key in presets if isinstance(presets, (list, tuple, set)) else ():
        preset = PRESET_MAP.get(str(key).strip())
        if not preset:
            continue
        for word in preset["words"]:
            rule = _compile_phrase(word)
            if rule:
                compiled.append(rule)

    raw_words = config.get("blacklist_words") or ""
    if isinstance(raw_words, (list, tuple)):
        raw_words = "\n".join(str(entry) for entry in raw_words)
    for line in str(raw_words).splitlines():
        rule = compile_line(line)
        if rule:
            compiled.append(rule)

    return BlacklistRules(
        movie_genres=_as_id_list(config.get("blacklist_genre_movie")),
        tv_genres=_as_id_list(config.get("blacklist_genre_tv")),
        words=tuple(compiled),
        match_title=bool(config.get("blacklist_match_title", True)),
        match_tags=bool(config.get("blacklist_match_tags", True)),
        tmdb_keywords=bool(config.get("blacklist_tmdb_keywords", False)),
    )


# --------------------------------------------------------------------- 匹配

def _normalize(text: str, case_sensitive: bool) -> str:
    """统一大小写（中文不受影响）。"""
    return text if case_sensitive else text.lower()


def _token_hit(token: str, haystack: str) -> bool:
    """单个 token 是否命中。

    - 纯英文/数字 token：**整词**匹配（``BL`` 不命中 ``BLADE``）
    - 其它（含中文）：子串匹配（``同性`` 命中 ``同性恋``）
    """
    if not token:
        return False
    if _ASCII_WORD.match(token):
        return bool(_ascii_word_pattern(token).search(haystack))
    return token in haystack


def _rule_hit(rule: _WordRule, haystack: str) -> bool:
    """一条规则是否命中给定的待查文本。"""
    if rule.pattern is not None:
        return bool(rule.pattern.search(haystack))
    text = _normalize(haystack, rule.case_sensitive)
    return all(_token_hit(_normalize(token, rule.case_sensitive), text) for token in rule.tokens)


def match_words(rules: BlacklistRules, texts: Iterable[str]) -> str:
    """在若干段文本里找第一条命中的题材规则；返回展示用原文（未命中返回空串）。"""
    haystacks = [str(text) for text in texts if text]
    if not haystacks:
        return ""
    for rule in rules.words:
        for haystack in haystacks:
            if _rule_hit(rule, haystack):
                return rule.display
    return ""


def _raw_of(item: Any) -> Dict[str, Any]:
    raw = getattr(item, "raw", None)
    return raw if isinstance(raw, dict) else {}


def item_genre_ids(item: Any) -> Set[int]:
    """收集条目的 TMDB 类型 id。

    三个来源，按可靠性排序，取并集：

    1. ``raw["genre_ids"]`` —— TMDB discover 响应、宿主识别候选自带的 id（最准）
    2. ``raw["genres"]`` —— AniList 的英文类型名，靠 :data:`GENRE_ALIASES` 反查
    3. ``raw["genre"]`` —— 豆瓣 ``<category>`` 的中文题材串（``剧情 同性 犯罪``），
       按别名表逐词反查
    """
    ids: Set[int] = set()
    raw = _raw_of(item)
    for entry in raw.get("genre_ids") or ():
        try:
            ids.add(int(str(entry).strip()))
        except (TypeError, ValueError):
            continue
    for entry in raw.get("genres") or ():
        genre_id = GENRE_ALIASES.get(str(entry).strip().lower())
        if genre_id:
            ids.add(genre_id)
    category = raw.get("genre")
    if isinstance(category, str) and category:
        for chunk in re.split(r"[\s/、,，]+", category):
            genre_id = GENRE_ALIASES.get(chunk.strip().lower())
            if genre_id:
                ids.add(genre_id)
    return ids


def item_tag_texts(item: Any) -> List[str]:
    """收集「题材串」文本（给题材词匹配用）。

    豆瓣的 ``category`` 是 ``2026 / 韩国 / 剧情 同性 犯罪`` 这种整串，
    地区和题材都在里面 —— 所以「韩国 同性」这类 AND 规则天然可用。
    """
    raw = _raw_of(item)
    texts: List[str] = []
    for key in ("genre", "genres", "tags", "category"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            texts.append(value)
        elif isinstance(value, (list, tuple, set)):
            texts.extend(str(entry) for entry in value if entry)
    return texts


def genre_label(genre_id: int) -> str:
    """类型 id 的中文名（未知 id 退回数字）。"""
    return f"{GENRE_NAMES.get(genre_id, str(genre_id))}({genre_id})"


def check_item(rules: BlacklistRules, item: Any) -> str:
    """判定单条条目是否被黑名单拦下。

    :return: 命中原因（直接写进流水的 ``reason``）；未命中返回空串。
    """
    if not rules.active:
        return ""

    # ① 排除类型：结构化 id 优先
    excluded = rules.tv_genres if getattr(item, "media_type", "") == MEDIA_TYPE_TV else rules.movie_genres
    if excluded:
        hit = sorted(item_genre_ids(item) & set(excluded))
        if hit:
            return "命中排除类型：" + "、".join(genre_label(genre_id) for genre_id in hit)

    # ② 排除题材：标题 / 原名
    if rules.match_title and rules.words:
        titles = [
            getattr(item, "title", "") or "",
            getattr(item, "original_title", "") or "",
        ]
        hit_word = match_words(rules, titles)
        if hit_word:
            return f"命中排除题材（标题）：{hit_word}"

    # ③ 排除题材：来源题材串
    if rules.match_tags and rules.words:
        hit_word = match_words(rules, item_tag_texts(item))
        if hit_word:
            return f"命中排除题材（题材）：{hit_word}"

    return ""


def check_keywords(rules: BlacklistRules, keywords: Iterable[str]) -> str:
    """用 TMDB keyword 列表再判一次（只对题材词生效）。"""
    if not rules.active or not rules.words:
        return ""
    hit_word = match_words(rules, [str(entry) for entry in keywords if entry])
    if hit_word:
        return f"命中排除题材（TMDB 关键词）：{hit_word}"
    return ""


__all__ = [
    "BlacklistRules",
    "GENRE_ALIASES",
    "GENRE_NAMES",
    "PRESETS",
    "PRESET_MAP",
    "check_item",
    "check_keywords",
    "compile_line",
    "genre_label",
    "item_genre_ids",
    "item_tag_texts",
    "match_words",
    "rules_from_config",
]
