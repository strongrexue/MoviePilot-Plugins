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


#: 需要从标题里清掉的隐形/零宽字符（真机：豆瓣标题尾部带 U+200B）
_INVISIBLE = dict.fromkeys(
    map(
        ord,
        "\u200b\u200c\u200d\u2060\ufeff\u00a0\u3000\u2000\u2001\u2002\u2003\u2004\u2005",
    ),
    " ",
)


def sanitize_title(title: Optional[str]) -> str:
    """清掉标题里的零宽字符与异常空白。

    真机：《豫见她们 第2季》的豆瓣标题实际是 ``'豫见她们 第2季\\u200b'`` ——
    尾部一个零宽空格。它让「第2季」剥不掉（正则 ``$`` 匹配不到），于是拿
    带隐藏字符的整串去搜 TMDB，命中率必然为 0。

    所有标题工具（``normalize_title`` / ``strip_season_suffix`` /
    ``strip_trailing_year`` / ``extract_season_hint``）都先走这一步。
    """
    text = str(title or "").translate(_INVISIBLE)
    return " ".join(text.split()).strip()


def normalize_title(title: Optional[str]) -> str:
    """标准化标题：全角转半角、去装饰、压空白、统一小写。

    用于缓存键与模糊比较；**不用于**需要展示的标题。
    """
    if not title:
        return ""
    text = unicodedata.normalize("NFKC", sanitize_title(title))
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

#: 英文 / 日式季号后缀（AniList 的日番标题大量使用这种写法）：
#:
#:   Black Clover 2nd Season  /  Season 2  /  第2クール  /  Part 2
#:
#: 真机教训：AniList 给的是日文原名，其中「第2期」我们的正则能识别，
#: 但 ``2nd Season`` 这类**完全没覆盖** —— 季号提示缺失后，
#: 宿主的季号裁决只能取「该条目最大的在播季」，一旦条目认错（认成上一季），
#: 就会稳定订到 S01。
_SEASON_SUFFIX_EN = re.compile(
    r"[\s:：·\-,]*(?:"
    r"(?:season|series|cour|part)\s*([0-9]{1,2})"
    r"|([0-9]{1,2})\s*(?:st|nd|rd|th)\s*(?:season|cour|part)"
    # 日式：第2クール / 第2クール目 / 第2部
    r"|第\s*([0-9]{1,2}|[一二三四五六七八九十]{1,2})\s*(?:クール|部)"
    r")\s*$",
    re.IGNORECASE,
)


#: 中文数字 -> 阿拉伯数字（季号用）
_CN_DIGITS = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}


def _season_number(raw: str) -> Optional[int]:
    """把季号文本转成整数，支持阿拉伯数字与中文数字。

    真机踩过：豆瓣「信号 第二季」「镀金时代 第四季」这类标题，季号是中文数字，
    原实现直接 `int("二")` 抛 ValueError 后放弃，导致基础名没剥出来、
    TMDB 搜不到 -> 误判为待确认。
    """
    text = str(raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = _CN_DIGITS.get(left, 1) if left else 1
        ones = _CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CN_DIGITS.get(text)


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
    text = sanitize_title(title)
    if not text:
        return text
    # 英文/日式季号（2nd Season / Season 2 / 第2クール / Part 2）先剥掉
    english = _SEASON_SUFFIX_EN.search(text)
    if english:
        base_en = text[: english.start()].strip(" :：·-,")
        number_en = _season_number(english.group(1) or english.group(2) or english.group(3) or "")
        if len(base_en) >= 2 and number_en is not None and 2 <= number_en <= 30:
            return base_en
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
    number = _season_number(match.group(1))
    if number is None or not 2 <= number <= 30:
        return text
    return base


#: 标题尾部的年份（「妻子的浪漫旅行2026」这类综艺命名）
_TRAILING_YEAR = re.compile(r"[\s:：·\-]*((?:19|20)\d{2})\s*$")


def strip_trailing_year(title: Optional[str], tz_name: Optional[str] = None) -> str:
    """去掉标题尾部的年份，得到「基础名」。

    真机：豆瓣综艺常把年份写进标题（妻子的浪漫旅行2026、歌手2026、
    披荆斩棘2026、我家那闺女2026），而 TMDB 里是不带年份的
    （妻子的浪漫旅行 2018 / 歌手 / 披荆斩棘 2021 / 我家那闺女 2019）。
    直接搜全名命中率为 0，去掉年份才搜得到。

    安全约束：

    - 只削 **2000 ~ 今年+1** 之间的年份 —— 「银翼杀手2099」「1917」不受伤；
    - 削完基础名至少 2 个字符。
    """
    text = sanitize_title(title)
    if not text:
        return text
    match = _TRAILING_YEAR.search(text)
    if not match:
        return text
    year = int(match.group(1))
    from .window import today as _today

    limit = (_today(tz_name) or _today()).year + 1
    if not 2000 <= year <= limit:
        return text
    base = text[: match.start()].strip(" :：·-")
    return base if len(base) >= 2 else text


def search_variants(title: Optional[str], tz_name: Optional[str] = None) -> List[str]:
    """返回依次尝试的搜索词（去重、保序）。

    1. 原名的去季号版本（牧神记5 -> 牧神记）
    2. 再去掉尾部年份（妻子的浪漫旅行2026 -> 妻子的浪漫旅行）
    """
    first = strip_season_suffix(title) or str(title or "").strip()
    second = strip_trailing_year(first, tz_name)
    variants: List[str] = []
    for value in (first, second):
        if value and value not in variants:
            variants.append(value)
    # 去掉副标题再试：TMDB 里很多国漫只有主名（真机：诛仙 最终季 -> 诛仙、
    # 逆天邪神 年番 -> 逆天邪神、师兄啊师兄 年番2 -> 师兄啊师兄）。
    for value in list(variants):
        head = value.split(' ')[0].strip()
        if head and len(head) >= 2 and head != value and head not in variants:
            variants.append(head)
    return variants


def match_by_unique_year(
    candidates: Iterable[dict],
    item: DiscoveredItem,
    *,
    max_delta: int = 1,
) -> Optional[dict]:
    """宽松匹配：**唯一**一个同年（±1）且同类型的候选才算命中。

    动机（真机）：豆瓣译名与 TMDB 中文名不同时，标题比对必然失败，
    但 TMDB 的原始搜索能靠 alternative_titles / 原名把它们搜出来::

        豆瓣「闹鬼酒店」  -> TMDB「酒店有鬼」(255752)  标题完全不像
        豆瓣「虚无的十字架」-> TMDB「空洞的十字架」(326140)
        豆瓣「人生交换」  -> TMDB「交换人生」(333359)

    这时能用的判据只剩「年份 + 类型 + 唯一性」：

    - 类型必须一致；
    - 候选必须有年份，且与条目年份相差 ≤ `max_delta`；
    - 满足条件的候选**必须恰好一个**，多个则视为歧义、放弃。

    这三个条件同时满足时，误配概率很低（同类型、同年、且没有竞争候选）。
    """
    wanted = _year_of(item.year or item.release_date)
    if not wanted:
        return None
    target_year = int(wanted)
    matches: List[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if not candidate.get("tmdb_id"):
            continue
        candidate_type = str(candidate.get("media_type") or "").strip().casefold()
        if candidate_type and candidate_type != item.media_type:
            continue
        year = _year_of(candidate.get("year") or candidate.get("release_date"))
        if not year:
            continue
        if abs(int(year) - target_year) > max_delta:
            continue
        matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def extract_season_hint(title: Optional[str]) -> Optional[int]:
    """从标题尾部提取季号提示（牧神记5 -> 5、第2期 -> 2、2nd Season -> 2）。

    只是**提示**，不直接用于订阅 —— TMDB 未必有同号季（真机：《牧神记5》
    在 TMDB 只有第 1 季）。真正的季号由宿主按「TMDB 哪个季有未播内容」
    决定，这里只提供线索。
    """
    text = sanitize_title(title)
    if not text or strip_season_suffix(text) == text:
        return None
    # 英文/日式写法优先（2nd Season / Season 2 / 第2クール / Part 2）
    english = _SEASON_SUFFIX_EN.search(text)
    if english:
        number = _season_number(english.group(1) or english.group(2) or english.group(3) or "")
        if number and 2 <= number <= 30:
            return number
    match = _SEASON_SUFFIX.search(text)
    if not match:
        return None
    return _season_number(match.group(1))


def is_continuation_title(title: Optional[str]) -> bool:
    """标题是否明显是**续作**（季号 >= 2）。

    用途：续作条目绝不允许匹配到**更旧年份**的 TMDB 条目 ——
    那几乎一定是「上一季那部」，订下去就是 S01（真机：2026 的续作被
    匹配到 2025 的基础条目，然后在该条目里选了第 1 季）。
    """
    hint = extract_season_hint(title)
    return bool(hint and hint >= 2)


def _is_donghua(item: DiscoveredItem) -> bool:
    """是否国产动画（AniList 的 countryOfOrigin=CN）。"""
    return str((item.raw or {}).get("country") or "").upper() == "CN"


def _prefers_latest_year(item: DiscoveredItem) -> bool:
    """同名多条目时是否应取「年份最大」的那条（仅国漫续作）。

    日番续作在 TMDB 通常是**独立条目**（年份本来就接近），取最大年份会
    误选到「下一季的新条目」；而国漫是「单条目多年」，最近的那条才是对的。
    """
    # **所有国漫**都启用：TMDB 里国漫常有多条同名条目（遮天 2023 / 遮天 2025、
    # 完美世界 2021 / 完美世界 2000），靠「年份最接近」才能选中对应那部。
    return str((item.raw or {}).get("country") or "").upper() == "CN"


def _continuation_floor(item: DiscoveredItem) -> Optional[int]:
    """续作条目的「年份下限」：``min_year`` 参数的取值。

    只有续作（季号 >= 2）才设下限，普通作品返回 ``None`` 表示不限制 ——
    否则「同名老片/翻拍」会被误杀。
    """
    if not is_continuation_title(item.title):
        return None
    # **国漫豁免**：国漫长篇在 TMDB 通常是「单条目、首播年很早、按季/集推进」，
    # 而 AniList 的条目年份是「该季年份」（2026）。真机：完美世界 第七季、
    # 妖神记 第十季、万界独尊 第三季、逆天邪神 第2季 全部卡在这一层 ——
    # 候选年份 2018~2021 被全部拒绝，直接退化成待确认。
    # 国漫的正确性由季号裁决 + 「TMDB 还有没有未播集」把关，不需要年份下限。
    if str((item.raw or {}).get("country") or "").upper() == "CN":
        return None
    year = _year_of(item.year or item.release_date)
    try:
        return int(year) if year else None
    except (TypeError, ValueError):
        return None


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
    target_title: Optional[str] = None,
    min_year: Optional[int] = None,
    prefer_latest_year: bool = False,
    allow_contained: bool = False,
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
    # 换策略重试时用「变体词」作为目标标题（条目原名与候选名可能不同）
    raw_target = target_title or item.title
    target_title = normalize_title(raw_target)
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

        # 「基础名相等」：条目带季号尾巴、候选是基础名的情况。
        #
        # 真机确认：宿主识别 赛博朋克：边缘行者 2 会返回**基础名**
        # 《赛博朋克：边缘行者》—— 条目名与候选名相差「 2」，
        # 若只认「精确相等」会把宿主已经成功识别的结果拒掉（0.6.3 踩过）。
        base_equiv = bool(candidate_title) and candidate_title in {
            normalize_title(strip_season_suffix(raw_target)),
            normalize_title(strip_season_suffix(item.original_title)),
        }

        contained = bool(candidate_title) and (
            target_title in candidate_title or candidate_title in target_title
        )
        if contained:
            shorter = min(len(target_title), len(candidate_title))
            longer = max(len(target_title), len(candidate_title))
            contained = shorter >= 3 and bool(longer) and shorter / longer >= 0.5
        if not (exact or base_equiv or contained):
            continue

        candidate_year = _year_of(candidate.get("year") or candidate.get("release_date"))
        # 续作闸门：标题带季号（>=2）时，**绝不接受比条目更旧的条目**。
        #
        # 真机：AniList 的「野生のラスボスが現れた！ 第2期」(2026) 搜日文命中 0，
        # 退化成中文基础名「野生的最终BOSS出现了」后 TMDB 只返回 2025 那部
        # （上一季）。TV 又不做年份硬校验，于是认成 2025 条目 → 订 S01。
        # 这不是季号裁决错，是**条目认错**；这里把它挡在识别阶段。
        if min_year and candidate_year and int(candidate_year) < int(min_year):
            continue
        if strict_year:
            if wanted_year and candidate_year != wanted_year:
                # 年份不符或缺年份 —— 电影不做任何「放宽」，直接不算命中
                continue
        elif not (exact or base_equiv or (allow_contained and contained)):
            # 剧集不校验年份，但必须「标题精确相等」或「基础名相等」才认 ——
            # 只认「包含」会把同名前传之类错误配对放进来（如
            # 条目《牧神记》配上候选《牧神记外传》）。
            continue

        reason = "search:title_exact" if exact else "search:title_contained"
        if wanted_year:
            reason = f"{reason}+year_match"
        matched.append((candidate, reason))

    # 优先排除「分季版 / 合集版」这类重复条目。
    #
    # 真机（一念永恒）：TMDB 同时存在主条目（107371，1 季 200 集 + Seasons 分组）
    # 和「分季版」（331477，S1~S4）。两者标题都能匹配、年份都是 2020，
    # 季号裁决会挑「真有第 4 季」的分季版，于是订到了 S04/30 集而不是主条目。
    # 规则：多候选时优先不要带括号限定词的那条（分季/合集/总集篇/剧场版）。
    if prefer_latest_year and len(matched) > 1:
        # **国漫优先动画类型条目**：TMDB 里很多国漫同时有「动画版」和「真人剧版」
        # 两个同名条目（真机：凡人修仙传 / 武神主宰 / 万界独尊 / 紫川）。
        # 选到真人剧版就会「已播完」→ 跳过，而动画版其实在更新。
        animated = [
            entry for entry in matched if 16 in (entry[0].get("genre_ids") or [])
        ]
        if animated:
            matched = animated

    if len(matched) > 1 and prefer_latest_year:
        wanted = int(_year_of(item.year or item.release_date) or 0)

        def _score(entry: Tuple[dict, str]) -> Tuple[int, int]:
            """年份越接近条目年份越好；并列时取 tmdb_id 更小的主条目。"""
            year = int(_year_of(entry[0].get("year") or entry[0].get("release_date")) or 0)
            distance = abs(year - wanted) if (year and wanted) else 9999
            return (distance, int(entry[0].get("tmdb_id") or 0))

        return min(matched, key=_score)

    if len(matched) > 1 and prefer_latest_year:
        # 国漫续作：同名多条目时取**年份最大**的那个。
        #
        # 真机：完美世界 第七季 -> TMDB 有「完美世界 2021」和「完美世界 2000」
        # 两个同名条目；旧逻辑判定歧义（年份都不在 ±1 内）且续作又跳过兜底，
        # 直接退化成待确认。国漫的正确条目就是最近的那部。
        # 同年再取 tmdb_id 最小 —— 主条目通常最早创建，分季版/合集是后补的
        # （一念永恒：107371 主条目 vs 331477 分季版）。
        best = max(
            matched,
            key=lambda entry: (
                int(_year_of(entry[0].get("year") or entry[0].get("release_date")) or 0),
                -int(entry[0].get("tmdb_id") or 0),
            ),
        )
        return best

    if len(matched) > 1:
        primary = [
            entry
            for entry in matched
            if not _is_split_entry(
                entry[0].get("title"), entry[0].get("original_title")
            )
        ]
        if len(primary) == 1:
            return primary[0]

    if len(matched) != 1:
        # 0 条：未命中；>1 条：先试「年份就近」消歧，仍不行才算歧义。
        #
        # 真机：搜「信号」返回 11 条（心动的信号 / 信号 / 心脏信号 …），
        # 搜「半熟恋人」返回两条同名（2021 / 2012）。只要其中**恰好一条**
        # 落在条目年份 ±2 内，就能唯一确定。
        if not strict_year and wanted_year and len(matched) > 1:
            close: List[Tuple[dict, str]] = []
            for candidate, desc in matched:
                year = _year_of(candidate.get("year") or candidate.get("release_date"))
                if year and abs(int(year) - int(wanted_year)) <= 2:
                    close.append((candidate, desc))
            if len(close) == 1:
                return close[0]
        return None
    return matched[0]


#: 括号里的「分季/合集」等限定词 —— 这类条目通常是同一部作品的重复条目
_SPLIT_MARKERS = ("分季", "合集", "总集篇", "剧场版", "特别篇", "split", "seasons")


def _is_split_entry(*titles: Optional[str]) -> bool:
    """标题是否带「分季版 / 合集」这类限定词（重复条目）。"""
    for title in titles:
        text = str(title or "").casefold()
        if not text:
            continue
        # 只认括号里的限定词，避免误伤「剧场版」这类真·独立作品标题
        for marker in _SPLIT_MARKERS:
            if f"（{marker}" in text or f"({marker}" in text or f" {marker}" in text:
                return True
    return False


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
        prefer_episode_group: bool = True,
    ) -> None:
        self._tmdb = tmdb
        self._cache = cache
        self._review_threshold = review_threshold
        #: 是否采用跨源换算回来的季号。**默认关**（见 _resolve_by_conversion 注释）
        self._use_converted_season = use_converted_season
        #: 是否用 TMDB episode group 精确订阅被压成单季的番剧
        self._prefer_episode_group = prefer_episode_group
        #: tmdb_id -> poster_path。流水页要显示封面，但海报只在候选里出现过；
        #: 这里顺手记下来，成功解析后回填到 item.raw["poster"]。
        self._poster_index: Dict[str, str] = {}

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
            await self._resolve_target_season(item)
            return item

        # ---- L1b：可换算来源（Bangumi / 豆瓣 / Simkl 的原生 ID → TMDB）
        identity = await self._resolve_by_conversion(item)
        if identity:
            item.resolved = identity
            self._remember(item, identity)
            await self._resolve_target_season(item)
            return item

        # ---- L2 缓存
        identity = self._resolve_from_cache(item)
        if identity:
            item.resolved = identity
            await self._resolve_target_season(item)
            return item

        # ---- L3 精确搜索 + 年份硬校验
        # 记录尝试过的搜索词，供「待确认」给出可操作原因
        item.raw.setdefault("search_variants", search_variants(item.title))
        candidates = await self._search(item)
        if candidates:
            hit = match_candidate_year(
                candidates,
                item,
                strict_year=item.media_type == MEDIA_TYPE_MOVIE,
                min_year=_continuation_floor(item),
                prefer_latest_year=_prefers_latest_year(item),
                allow_contained=_is_donghua(item),
            )
            if hit:
                candidate, reason = hit
                self._stash_genres(item, candidate)
                identity = ResolvedIdentity(
                    media_source=HOST_SOURCE_TMDB,
                    media_id=str(candidate["tmdb_id"]),
                    confidence=CONFIDENCE_L3,
                    reason=reason,
                )
                item.resolved = identity
                self._remember(item, identity)
                await self._resolve_target_season(item)
                return item

            # ---- L3 按季号消歧
            #
            # 真机：搜「信号」返回 11 条同名候选，「信号 第二季」的正确条目是
            # 韩剧《信号》(64840, 2016)，靠标题+年份都定不下来 —— 但它的
            # 第 2 季确实有未播集。所以用「候选是否真有该季未播集」来唯一确定。
            by_season = await self._disambiguate_by_season(candidates, item)
            if by_season:
                candidate, season_no = by_season
                self._stash_genres(item, candidate)
                identity = ResolvedIdentity(
                    media_source=HOST_SOURCE_TMDB,
                    media_id=str(candidate["tmdb_id"]),
                    confidence=CONFIDENCE_L3,
                    reason=f"search:season_hint({season_no})",
                )
                item.resolved = identity
                self._remember(item, identity)
                await self._resolve_target_season(item)
                return item

            # ---- L3 换策略重试
            #
            # 真机：豆瓣综艺把年份写进标题（妻子的浪漫旅行2026），而 TMDB 里
            # 不带年份；只搜一次全名命中率为 0。这里依次尝试「去年份」等变体，
            # 只在宿主提供 search_raw 时生效。
            hit = await self._retry_with_variants(item)
            if hit:
                return item

            # ---- L4 模糊评分：只记录，永不写入
            item.review_score = review_candidates(
                candidates, item, threshold=self._review_threshold
            )
        else:
            # 首次搜索完全没有候选，同样值得换策略再试一次
            if await self._retry_with_variants(item):
                return item

        return item

    async def _disambiguate_by_season(
        self, candidates: Sequence[dict], item: DiscoveredItem
    ) -> Optional[Tuple[dict, int]]:
        """用「候选是否真有该季的未播集」在多个同名候选里唯一确定。

        真机场景：豆瓣「信号 第二季」→ 搜「信号」得到 11 条同名/近名候选，
        标题与年份都无法消歧（韩剧《信号》首播 2016，而豆瓣条目是 2026 的第二季）。
        但只有正确那条的**第 2 季有未播集**，所以按这个条件筛就唯一了。
        """
        if not item.is_tv:
            return None
        hint = extract_season_hint(item.title)
        if not hint:
            return None
        checker = getattr(self._tmdb, "resolve_target_season", None)
        if checker is None:
            return None

        target = normalize_title(strip_season_suffix(item.title))
        same_show: List[dict] = []
        for candidate in candidates[:8]:
            title = normalize_title(candidate.get("title"))
            original = normalize_title(candidate.get("original_title"))
            if target and target not in (title, original):
                continue
            same_show.append(candidate)
        if not same_show:
            return None

        # 第一优先：只有它「该季还有未播集」
        winners: List[dict] = []
        for candidate in same_show:
            try:
                verdict = await checker(str(candidate.get("tmdb_id")), item.media_type, hint)
            except Exception:  # noqa: BLE001 - 单个候选查询失败不影响其余
                continue
            if verdict and verdict[0] and verdict[1] == hint:
                winners.append(candidate)
        if len(winners) == 1:
            return winners[0], hint

        # 第二优先：只有它「该季存在」（哪怕已经播完）。
        # 这样「已播完」会由 finished 闸门明确标出，而不是误报成「搜不到」。
        exists_checker = getattr(self._tmdb, "season_exists", None)
        if exists_checker is None:
            return None
        existing: List[dict] = []
        for candidate in same_show:
            try:
                if await exists_checker(str(candidate.get("tmdb_id")), item.media_type, hint):
                    existing.append(candidate)
            except Exception:  # noqa: BLE001
                continue
        if len(existing) == 1:
            return existing[0], hint
        return None

    async def _retry_with_variants(self, item: DiscoveredItem) -> bool:
        """用备选名重试搜索（去尾部年份、豆瓣又名/原名）。

        真机：豆瓣与 TMDB 的中文译名经常不同，TMDB 的搜索索引里没有豆瓣那个
        译名，直接搜命中率为 0：

            豆瓣「闹鬼酒店」  -> TMDB 搜 0 条（TMDB 叫「酒店有鬼」）
            豆瓣「虚无的十字架」-> TMDB 搜 0 条（TMDB 叫「空洞的十字架」）
            豆瓣「人生交换」  -> TMDB 搜 0 条（TMDB 叫「交换人生」）

        而豆瓣条目的 ``aka`` / ``original_title`` 里带着 TMDB 认识的名字
        （「Haunted Hotel Season 2」「虚ろな十字架」「ライフトレード」），
        所以先向豆瓣要别名，再拿去搜 TMDB。
        """
        search_raw = getattr(self._tmdb, "search_raw", None)
        if search_raw is None:
            return False

        # 先用**条目标题本身**做一次原始搜索：主搜索走的是宿主 API，
        # 它在结果上还有一层「条目名必须包含查询词」的过滤，会把 TMDB 明明
        # 搜到的跨语言结果丢掉（真机：闹鬼酒店 -> 酒店有鬼）。
        variants = [variant for variant in search_variants(item.title) if variant]
        terms: List[tuple] = []
        if variants:
            terms.append((variants[0], f"raw:{variants[0]}"))
        terms.extend((variant, f"variant:{variant}") for variant in variants[1:])

        # Bangumi 翻译层：AniList 的日番条目给的是日文原名，TMDB 搜日文命中率
        # 很差（实测 ライフトレード / 虚ろな十字架 都是 0 条），而 Bangumi 的
        # name_cn 就是主流中文译名。这是 Bangumi 降级为「翻译层」后的唯一职责。
        translator = getattr(self._tmdb, "bangumi_aliases", None)
        if translator is not None:
            try:
                names = await translator(item.title, item.media_type)
            except Exception:  # noqa: BLE001 - 翻译失败不影响其余策略
                names = []
            seen = {item.title, *(term for term, _ in terms)}
            for name in names or ():
                if name and name not in seen:
                    seen.add(name)
                    terms.append((name, f"bgm:{name}"))

        aliases = getattr(self._tmdb, "douban_aliases", None)
        if aliases is not None:
            try:
                names = await aliases(item.title, item.media_type, item.year)
            except Exception:  # noqa: BLE001 - 别名查询失败不影响其余策略
                names = []
            seen = {item.title, *(term for term, _ in terms)}
            for name in names or ():
                if name and name not in seen:
                    seen.add(name)
                    terms.append((name, f"alias:{name}"))

        attempts: List[str] = item.raw.setdefault("search_attempts", [])
        for term, label in terms:
            attempts.append(term)
            try:
                extra = await search_raw(term, item.media_type)
            except Exception:  # noqa: BLE001 - 单个备选名失败继续下一个
                continue
            if not extra:
                continue
            self._index_posters(extra)
            hit = match_candidate_year(
                extra,
                item,
                strict_year=item.media_type == MEDIA_TYPE_MOVIE,
                target_title=term,
                min_year=_continuation_floor(item),
                prefer_latest_year=_prefers_latest_year(item),
                allow_contained=_is_donghua(item),
            )
            if not hit:
                # 标题比对失败时用「唯一同年候选」兜底（豆瓣/TMDB 译名差异）。
                #
                # **但续作绝不能用这个兜底**：它的容差是 ±1 年，
                # 而续作最典型的错误恰恰是「2026 的续作匹配到 2025 的上一季」
                # —— 正好落在容差内，会把上面刚挡住的错误从后门放回来。
                if is_continuation_title(item.title):
                    continue
                relaxed = match_by_unique_year(extra, item)
                if not relaxed:
                    continue
                hit = (relaxed, "search:relaxed_unique_year")
            candidate, reason = hit
            self._stash_genres(item, candidate)
            identity = ResolvedIdentity(
                media_source=HOST_SOURCE_TMDB,
                media_id=str(candidate["tmdb_id"]),
                confidence=CONFIDENCE_L3,
                reason=f"{reason}|{label}",
            )
            item.resolved = identity
            self._remember(item, identity)
            await self._resolve_target_season(item)
            return True
        return False

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
        # ① **手动修正优先**：用户明确指定的条目永远压过自动匹配结果。
        # 真机：修正映射写入了 v2:t:tv:2026:凡人修仙传 -> 106449(manual_fix)，
        # 但旧的自动结果（243224）以 source_id 为键仍在缓存里，
        # 先查 source_id 就让手动修正永远不生效。
        manual = self._lookup_title_cache(item, manual_only=True)
        if manual is not None:
            return manual
        cached = self._cache.get_by_source_id(item.source, item.source_id)
        if cached is None:
            # 标题键要**多试几种写法**：手动修正映射时写入的是「去掉季号」的
            # 基础名（诛仙 最终季 -> 诛仙），而这里以前只查原始标题，
            # 于是「修正映射」写进去了却永远查不到（真机：改了 ID 重跑还是旧条目）。
            year = _year_of(item.year or item.release_date)
            title_variants = [
                normalize_title(item.title),
                normalize_title(strip_season_suffix(item.title)),
                normalize_title(strip_trailing_year(item.title)),
                normalize_title(item.original_title),
                normalize_title(strip_season_suffix(item.original_title)),
            ]
            for value in title_variants:
                if not value:
                    continue
                cached = self._cache.get_by_title(value, year, item.media_type)
                if cached is not None:
                    break
                # 年份写法不一致时也要能命中（同一部剧在两个源年份可能差一年）
                for delta in (-1, 1):
                    if not year:
                        break
                    try:
                        alt_year = str(int(year) + delta)
                    except (TypeError, ValueError):
                        break
                    cached = self._cache.get_by_title(value, alt_year, item.media_type)
                    if cached is not None:
                        break
                if cached is not None:
                    break
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

    def _lookup_title_cache(
        self, item: DiscoveredItem, *, manual_only: bool = False
    ) -> Optional[ResolvedIdentity]:
        """按标题查映射缓存（多种写法 + 年份 ±1）。

        ``manual_only=True`` 时只认「手动修正」写入的条目 —— 让人工指定
        永远压过自动匹配。
        """
        if self._cache is None:
            return None
        year = _year_of(item.year or item.release_date)
        variants = [
            normalize_title(item.title),
            normalize_title(strip_season_suffix(item.title)),
            normalize_title(strip_trailing_year(item.title)),
            normalize_title(item.original_title),
            normalize_title(strip_season_suffix(item.original_title)),
        ]
        seen = set()
        for value in variants:
            if not value or value in seen:
                continue
            seen.add(value)
            years = [year]
            try:
                if year:
                    years.extend([str(int(year) - 1), str(int(year) + 1)])
            except (TypeError, ValueError):
                pass
            for alt_year in years:
                cached = self._cache.get_by_title(value, alt_year, item.media_type)
                if cached is None:
                    continue
                if manual_only and str(getattr(cached, "reason", "")) != "manual_fix":
                    continue
                if not cached.writable:
                    continue
                return ResolvedIdentity(
                    media_source=cached.media_source,
                    media_id=cached.media_id,
                    confidence=CONFIDENCE_L2,
                    reason=str(getattr(cached, "reason", "cache") or "cache"),
                )
        return None

    async def _search(self, item: DiscoveredItem) -> Sequence[dict]:
        """调用 TMDB 搜索；失败返回空序列（不抛）。"""
        try:
            candidates = await self._tmdb.search(
                item.title,
                _year_of(item.year or item.release_date),
                item.media_type,
            )
        except Exception:  # noqa: BLE001 - 搜索失败等同「无候选」
            return ()
        self._index_posters(candidates)
        return candidates

    def _index_posters(self, candidates) -> None:
        """记住候选的 tmdb_id -> poster_path，供解析成功后回填封面。"""
        for candidate in candidates or ():
            if not isinstance(candidate, dict):
                continue
            tmdb_id = candidate.get("tmdb_id")
            poster = candidate.get("poster_path")
            if tmdb_id and poster:
                self._poster_index[str(tmdb_id)] = str(poster)

    @staticmethod
    def _stash_genres(item: DiscoveredItem, candidate: Any) -> None:
        """把候选自带的 TMDB ``genre_ids`` 存进条目。

        为什么需要：黑名单第一遍跑在**身份解析之前**（省请求），那时豆瓣榜单
        这类来源只有标题 —— ``/douban/list/*`` 的 RSS 连 ``<category>`` 都没有，
        所以「排除类型：真人秀/脱口秀」一条都拦不住。而 TMDB 搜索响应本来就
        带着 ``genre_ids``，顺手留下来，解析完再过一遍类型即可拦住，
        **不额外发任何请求**。
        """
        if not isinstance(candidate, dict):
            return
        ids: List[int] = []
        for value in candidate.get("genre_ids") or ():
            try:
                genre_id = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if genre_id > 0:
                ids.append(genre_id)
        if ids:
            item.raw.setdefault("genre_ids", ids)

    async def _attach_poster(self, item: DiscoveredItem) -> None:
        """回填海报路径（流水页显示封面用）。

        两条来源：① 候选里带回来的 poster_path；② 宿主适配器记下的
        （``resolve_target_season`` 拉详情时顺带存的，零额外请求）。
        电影走第三条：让宿主补查一次详情。
        """
        if not item.resolved or (item.raw or {}).get("poster"):
            return
        media_id = str(item.resolved.media_id)
        poster = self._poster_index.get(media_id)
        if not poster:
            getter = getattr(self._tmdb, "poster_path", None)
            if getter is not None:
                try:
                    poster = getter(media_id)
                except Exception:  # noqa: BLE001 - 海报只是展示用
                    poster = None
        if not poster:
            fetcher = getattr(self._tmdb, "async_poster_path", None)
            if fetcher is not None:
                try:
                    poster = await fetcher(media_id, item.media_type)
                except Exception:  # noqa: BLE001
                    poster = None
        if poster:
            # 归一化成路径：完整 URL 会让浏览器直连 image.tmdb.org（国内不可达）
            from .host import _poster_path

            normalized = _poster_path(poster)
            if normalized:
                item.raw["poster"] = normalized

    async def _resolve_target_season(self, item: DiscoveredItem) -> None:
        """确定该订阅哪一季，并判断是否还有未播内容。

        把 Bangumi 标题里的季号作为**提示**交给宿主，由宿主按 TMDB 实际数据
        裁决（见 `HostTmdbResolver.resolve_target_season`）：

        - 《赛博朋克：边缘行者 2》→ 提示 2，TMDB 第 2 季有未播集 → 订第 2 季
        - 《牧神记5》→ 提示 5，TMDB 只有第 1 季有未播集 → 订第 1 季
        - 《ゲルぴよ 第2期》→ 提示 2，TMDB 只有第 1 季且已播完 → 不可订

        `TmdbResolver` 未实现该能力时跳过（向后兼容）。
        """
        if not item.resolved:
            return
        resolver = getattr(self._tmdb, "resolve_target_season", None)
        if not item.is_tv or resolver is None:
            # 电影不走季号裁决，直接取海报（会额外查一次详情）
            await self._attach_poster(item)
            return
        try:
            verdict = await resolver(
                item.resolved.media_id,
                item.media_type,
                extract_season_hint(item.title),
                prefer_episode_group=self._prefer_episode_group,
            )
        except Exception:  # noqa: BLE001 - 校验失败 fail-open
            await self._attach_poster(item)
            return
        # 海报必须在**裁决之后**取：宿主裁决季号时会拉 TMDB 详情，
        # poster_path 就在那份 JSON 里（零额外请求）。
        # 顺序写反过一次，结果每部剧都多查了一次 TMDB。
        await self._attach_poster(item)
        # 兼容二元组（早期实现）与三元组
        writable, season = verdict[0], verdict[1]
        episode_group = verdict[2] if len(verdict) > 2 else None

        if not writable:
            item.finished = True
            return
        if _is_donghua(item):
            # 国漫的季号处理分两种情况 —— 真机教训：
            #
            # ① **真实季存在**（诛仙有第 4 季、斗破苍穹有第 5 季）：
            #    必须按季订。一律退回默认季会订成 S01，而库里 S01 已完结，
            #    于是「立即完成」，新季度永远订不到。
            # ② **只有剧集组**（一念永恒主条目只有 1 季 200 集，第四季只是
            #    剧集组）：按季订会订成 S04/35 集，和库里的单季条目打架。
            #
            # 判据：解析结果里带 episode_group 就说明走的是「剧集组」路线。
            if episode_group or season is None:
                # 只有剧集组 / 没有季号 -> 订默认季
                item.season = None
                item.episode_group = None
            else:
                # 真实季存在 -> 按季订（诛仙 S04、斗破苍穹 S05 都走这里）
                item.season = int(season)
                item.episode_group = None
            return
        if season is not None and item.season is None:
            item.season = int(season)
        if episode_group and item.episode_group is None:
            # 「被压成单季」的番剧按真实季精确订阅，避免补一大堆旧集
            item.episode_group = str(episode_group)

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
    return f"v2:sid:{source}:{source_id}"


def title_key(normalized_title: str, year: Optional[str], media_type: str) -> str:
    """缓存键：标准化标题 + 年份 + 类型。"""
    return f"v2:t:{media_type}:{year or ''}:{normalized_title}"


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
