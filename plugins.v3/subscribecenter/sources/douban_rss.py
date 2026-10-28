"""豆瓣数据源（经 RSSHub 的豆瓣路线）。

.. important::
   本模块的外部假设都在真机上实测过（0.7.0，RSSHub `diygod/rsshub:latest`）：

   - **可用路线**（实测 HTTP 200 且有内容）：
     ``/douban/movie/coming``（即将上映）、``/douban/movie/playing``（正在上映）、
     ``/douban/movie/weekly``（一周口碑榜）
   - **已 404 的路线**：``/douban/movie/ustop250``、``/douban/movie/new``
     —— RSSHub 新版已移除，别照旧文档写。
   - 条目结构（真实样本）::

        <title>生日快乐</title>
        <link>https://movie.douban.com/subject/37322586/</link>
        <description>… <li>上映日期：2026-10-23(中国大陆)</li> … <li>想看：27357</li> …</description>

     所以**上映日期可解析**、**豆瓣 subject id 可提取**（供宿主换算 TMDB）、
     **想看数**可作参考。
   - 宿主容器里**没有 feedparser**（实测 `No module named 'feedparser'`），
     因此这里用标准库 ``xml.etree.ElementTree`` 解析，不引入依赖。

关于 popularity：豆瓣的「想看数」与 TMDB 的 popularity 量纲完全不同
（前者动辄上万），直接塞进去会让「最低关注度」门槛形同虚设。
按 README 的数据源接入契约，**缺失的数值就留 ``None``**，
想看数只放进 ``raw`` 供排查。
"""
import html
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from ..core.constants import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, SOURCE_DOUBAN_RSS
from ..core.identity import sanitize_title
from ..core.model import DiscoveredItem, is_special
from ..core.window import parse_date

#: 请求超时（秒）
TIMEOUT_SECONDS = 25

#: 每个榜单默认只取前 N 条。
#:
#: 榜单按名次排列，取前 N 即取最热的。实测 /douban/list/tv_hot 有 241 条，
#: 不限量会把每日写入额度一次吃光，也会让 TMDB 查询次数暴涨。
DEFAULT_MAX_ITEMS_PER_FEED = 10

#: User-Agent —— RSSHub 本身不限，但保持可识别
USER_AGENT = "SubscribeCenter/0.7.0 (MoviePilot plugin; +https://github.com/strongrexue)"

#: 上映日期：``上映日期：2026-10-23(中国大陆)``
_RELEASE_DATE = re.compile(r"上映日期[：:]\s*(\d{4}-\d{2}-\d{2})")

#: 想看人数，**两种文案都要认**：
#:
#: - 电影即将上映：``想看：27357``
#: - 剧集即将播出：``想看人数：21035``（中间多「人数」两字）
#:
#: 真机实测（2026-10-28，RSSHub 自建实例）：只认前一种时
#: ``/douban/tv/coming`` 10 条里 0 条解析到想看数，导致剧集那条路线的
#: 「想看人数门槛」形同虚设（缺失即放行）。
_WANT_COUNT = re.compile(r"想看(?:人数)?[：:]\s*([\d,]+)")

#: 豆瓣条目 id：``https://movie.douban.com/subject/37322586/``
_SUBJECT_ID = re.compile(r"subject/(\d+)")


class DoubanRssSource:
    """基于 RSSHub 豆瓣路线的发现源。

    :param client: 可选的自管 HTTP 客户端（便于测试注入），需提供
        ``await client.get(url) -> 带 status_code / text 的响应``
    """

    def __init__(self, client: Any = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_DOUBAN_RSS

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """拉取所有已配置的豆瓣 RSS 并归一为发现条目。"""
        urls = parse_sources(config.get("douban_rss_sources"))
        if not urls:
            # 明确报错，避免「启用了但什么都没发生」的静默状态
            raise RuntimeError(
                "豆瓣 RSS 未配置地址（在配置页填入 RSSHub 的豆瓣路线 URL，如 "
                "http://<你的RSSHub>:1200/douban/movie/coming）"
            )

        tz_name = config.get("timezone")
        default_limit = _as_int(
            config.get("douban_max_items_per_feed"), DEFAULT_MAX_ITEMS_PER_FEED
        )
        default_days = _as_int(config.get("douban_future_days"), 0)
        default_want = _as_int(config.get("douban_min_want"), 0)
        items: List[DiscoveredItem] = []
        errors: List[str] = []

        domain = config.get("rsshub_domain")
        for entry in urls:
            url = build_feed_url(domain, entry["url"])
            limit = entry["max_items"] or default_limit
            try:
                text = await self._fetch_text(url)
            except Exception as exc:  # noqa: BLE001 - 单条 URL 失败不拖垮其余
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
                continue
            parsed = self.parse(text, url, tz_name, limit)
            # 每榜独立参数：写进 raw，流水线按条目覆盖全局阈值
            window = entry["future_days"] or default_days
            want = entry["min_want"] or default_want
            for item in parsed:
                item.raw["douban_list"] = entry["name"]
                if window:
                    item.raw["future_days"] = window
                if want:
                    item.raw["min_want"] = want
            items.extend(parsed)

        if not items and errors:
            # 全部失败才算该源失败（部分成功时保留已拿到的内容）
            raise RuntimeError("；".join(errors))

        # 有日期的排前面（按日升序），无日期的排后面
        items.sort(key=lambda item: (item.release_date is None, item.release_date or "", item.title))
        return _dedupe(items)

    # ------------------------------------------------------------------ 取数

    async def _fetch_text(self, url: str) -> str:
        """取回 RSS 原文。"""
        if self._client is not None:
            response = await self._client.get(url)
            status = getattr(response, "status_code", 0)
            if status and status >= 400:
                raise RuntimeError(f"HTTP {status}")
            return str(getattr(response, "text", "") or "")

        from app.runtime.settings import get_runtime_setting
        from app.sdk.network import AsyncRequestUtils

        utils = AsyncRequestUtils(
            ua=USER_AGENT,
            proxies=get_runtime_setting("PROXY") or None,
            timeout=TIMEOUT_SECONDS,
        )
        response = await utils.get_res(url, raise_exception=True)
        if not response:
            raise RuntimeError("无响应")
        return str(response.text or "")

    # ------------------------------------------------------------------ 解析

    @staticmethod
    def parse(
        text: str,
        url: str = "",
        tz_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[DiscoveredItem]:
        """把 RSS 原文解析为发现条目。

        两类路线都要支持（实测结构完全不同）：

        - **上映类**（`/douban/movie/coming`）：description 里有
          `上映日期：2026-10-23`，link 里有豆瓣 subject id。
        - **榜单类**（`/douban/list/*`、`/douban/recommended/*`、
          `/douban/tv/coming`）：**没有上映日期**，且 `/douban/list/*`
          连 `<link>` 都是空的（没有豆瓣 id），只有 title 和
          `<category>` 里的年份。

        没有日期的条目不在这里丢弃，而是标记 `date_unknown=True`：
        剧集交由「TMDB 是否还有未播集」决定，电影由流水线跳过。
        """
        media_type = _media_type_of(url)
        feed_title = _channel_title(text)
        # 列表类路线没有 <category>：按路线补题材提示（见 _ROUTE_GENRE_HINTS）
        genre_hint = _genre_hint_of(url)

        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            raise RuntimeError(f"RSS 解析失败：{exc}") from exc

        items: List[DiscoveredItem] = []
        for node in root.iter("item"):
            # 清洗零宽字符：真机豆瓣标题会带 U+200B，导致季号剥不掉、搜不到
            title = sanitize_title(node.findtext("title"))
            if not title:
                continue
            description = html.unescape(node.findtext("description") or "")
            link = (node.findtext("link") or "").strip()
            # 榜单类没有 <category>，题材在 description 的那一行里（见
            # _category_from_description）；两条路都取不到时再退回路线提示。
            category = (node.findtext("category") or "").strip() or _category_from_description(
                description
            )

            subject_id = _extract(_SUBJECT_ID, link) or _extract(_SUBJECT_ID, description)
            release = parse_date(_extract(_RELEASE_DATE, description), tz_name)
            year = _extract_year(category) or _extract_year(description)
            want = _extract(_WANT_COUNT, description)

            items.append(
                DiscoveredItem(
                    source=SOURCE_DOUBAN_RSS,
                    # 榜单类没有豆瓣 id -> 用标题造一个稳定 id（仅用于源内去重）
                    source_id=subject_id or f"title:{title}",
                    title=title,
                    media_type=media_type,
                    year=year or (str(release.year) if release else None),
                    release_date=release.isoformat() if release else None,
                    # 豆瓣「想看数」量纲与 TMDB popularity 完全不同，按接入契约
                    # 不冒充 popularity，只留在 raw 里。
                    popularity=None,
                    rating=None,
                    native_ids={"douban": subject_id} if subject_id else {},
                    special=is_special(title),
                    date_unknown=release is None,
                    raw={
                        "douban_id": subject_id,
                        "want": int(want.replace(",", "")) if want else None,
                        "genre": " ".join(part for part in (category, genre_hint) if part),
                        "feed": feed_title,
                        "url": url,
                    },
                )
            )
            if limit is not None and len(items) >= limit:
                break
        return items


# --------------------------------------------------------------------- 工具

#: 内置榜单名 —— **一律取 RSSHub 实测的频道标题**，与阅读器里看到的一致，
#: 方便一眼对上是哪条路线。用户可覆盖。
_LIST_NAMES = {
    # —— 即将上映（带精确日期）——
    "movie_coming": "豆瓣电影-即将上映",
    "tv_coming": "豆瓣剧集-即将播出",
    # —— 榜单类（无日期，靠 TMDB 未播集判断）——
    "tv_domestic": "豆瓣 - 近期热门国产剧",
    "show_domestic": "豆瓣 - 近期热门国内综艺",
    "tv_variety": "豆瓣 - 近期热门国内综艺",
    "tv_animation": "豆瓣 - 近期热门动画",
    "movie_real_time_hotest": "豆瓣 - 实时热门电影",
    "movie_hot": "豆瓣 - 新片榜",
    "movie_hot_gaia": "豆瓣 - 豆瓣热门",
    "movie_weekly_best": "豆瓣 - 一周口碑电影榜",
    "movie_top250": "豆瓣电影 Top250",
    "movie_showing": "正在上映",
    # —— 按语种/产地的剧集榜单 ——
    "tv_japanese": "豆瓣 - 近期热门日剧",
    "tv_korean": "豆瓣 - 近期热门韩剧",
    "tv_american": "豆瓣 - 近期热门美剧",
    "tv_british": "英剧",
    "tv_hongkong": "港剧",
    "tv_taiwan": "台剧",
    "tv_thai": "泰剧",
    "tv_documentary": "豆瓣 - 近期热门纪录片",
    "tv_show": "综艺",
}

#: 通用后缀 -> 中文（``xxx_hot`` 之类先按词干推断，避免界面上出现裸英文）
_NAME_SUFFIXES = (
    ("_real_time_hotest", "近期热门"),
    ("_chinese_best_weekly", "华语口碑"),
    ("_global_best_weekly", "全球口碑"),
    ("_weekly_best", "口碑榜"),
    ("_coming", "即将上映"),
    ("_showing", "正在上映"),
)


def build_feed_url(domain: Any, route: Any) -> str:
    """拼接完整 RSS 地址：``域名 + 路由``。

    榜单里只存**路由**（``/douban/movie/coming``），域名由全局
    ``rsshub_domain`` 统一提供 —— 换 RSSHub 地址只改一处。
    已经是完整 URL 的条目原样返回（兼容自定义外部 RSS）。
    """
    text = str(route or "").strip()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    base = str(domain or "").strip().rstrip("/")
    if not base:
        return text
    if not base.startswith("http"):
        base = "https://" + base
    return base + (text if text.startswith("/") else "/" + text)


def list_name_of(url: str) -> str:
    """从 RSSHub 路线推导可读榜单名。

    真实安装里用户可能保留老的完整 URL（``.../douban/list/tv_japanese``），
    所以这里做多级回退，**尽量不把裸英文留给界面**：

    1. 完整 key（末两段拼起来，如 ``movie_coming``）→ 表里查
    2. 末段（如 ``tv_domestic``）→ 表里查
    3. 末段按后缀推断（``xxx_real_time_hotest`` → 「近期热门」）
    4. 仍然没有 → 用末段原文（自定义路线）
    """
    parts = [p for p in str(url or "").split("/") if p]
    tail = parts[-1] if parts else ""
    key = "_".join(parts[-2:]) if len(parts) >= 2 else tail
    if key in _LIST_NAMES:
        return _LIST_NAMES[key]
    if tail in _LIST_NAMES:
        return _LIST_NAMES[tail]
    for suffix, label in _NAME_SUFFIXES:
        if tail.endswith(suffix):
            stem = tail[: -len(suffix)].replace("_", " ")
            return f"{stem} {label}".strip() if stem else label
    return tail or "自定义榜单"


def normalize_list_entry(entry: Any) -> Dict[str, Any]:
    """把一条榜单配置归一化为固定字段。

    兼容老的字符串 URL 与新 dict 两种形态；缺省值走全局配置，
    所以老配置升级后行为不变。
    """
    if isinstance(entry, str):
        entry = {"url": entry}
    if not isinstance(entry, dict):
        entry = {}
    url = str(entry.get("url") or "").strip()
    stored_name = str(entry.get("name") or "").strip()
    # 旧数据 / 迁移时写的名字可能还是裸英文（tv_japanese）—— 等于末段时视为
    # 「没起过名」，用可读名重算，界面上就不会再看到裸英文。
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    if not stored_name or stored_name == tail:
        stored_name = list_name_of(url)
    return {
        "name": stored_name,
        "url": url,
        "enabled": bool(entry.get("enabled", True)),
        # 0 = 跟随全局 douban_max_items_per_feed（老配置迁移过来时走这条）
        "max_items": _as_int(entry.get("max_items"), 0),
        "future_days": _as_int(entry.get("future_days"), 0),
        "min_want": _as_int(entry.get("min_want"), 0),
    }


def parse_sources(value: Any) -> List[Dict[str, Any]]:
    """解析榜单配置，返回**已归一化且启用**的列表。

    支持 list / dict / 字符串 / 换行或逗号分隔（老配置是最后一种）。
    ``enabled=False`` 的条目会被跳过。
    """
    if not value:
        return []
    entries: List[Any] = []
    if isinstance(value, str):
        entries = re.split(r"[\n,，]+", value)
    elif isinstance(value, dict):
        entries = [value]
    elif isinstance(value, (list, tuple)):
        for entry in value:
            if isinstance(entry, dict):
                entries.append(entry)
            else:
                entries.extend(re.split(r"[\n,，]+", str(entry)))

    result: List[Dict[str, Any]] = []
    seen: set = set()
    for entry in entries:
        normalized = normalize_list_entry(entry)
        url = normalized["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        if not normalized["enabled"]:
            continue
        result.append(normalized)
    return result


#: 行首四位年份（19xx / 20xx）
_YEAR_LINE = re.compile(r"^\s*((?:19|20)\d{2})\s*(?:/|$)")
_TAG = re.compile(r"<[^>]+>")


def _extract_year(text: str) -> Optional[str]:
    """从 category / description 里取年份。

    真实结构（实测）：

    - `/douban/tv/coming`：`<category>2026 / 韩国 / 剧情 悬疑 犯罪 / …</category>`
    - `/douban/list/*`：**没有 category**，年份在 description 里::

          <p>嫁金钗</p><p>2026 / 中国大陆 / 剧情 爱情 古装 / 杨龙 / 田曦薇 闫桉</p>

    因此先剥掉 HTML 标签，再要求年份出现在**行首**：

    - 命中：`2026 / 中国大陆 / …`  -> 2026
    - 不命中：`银翼杀手2099`（片名里的数字）、剧情简介里的年代
    """
    if not text:
        return None
    plain = _TAG.sub("\n", str(text))
    for line in plain.splitlines():
        match = _YEAR_LINE.match(line)
        if match:
            return match.group(1)
    return None


def _as_int(value: Any, default: int) -> int:
    """宽松整型转换。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _media_type_of(url: str) -> str:
    """按 RSSHub 路线名判断媒体类型。

    实测路线形态（注意 `/list/tv_hot` 里并没有独立的 `/tv/` 段）::

        /douban/movie/coming                  -> movie
        /douban/list/movie_weekly_best        -> movie
        /douban/tv/coming                     -> tv
        /douban/list/tv_hot                   -> tv
        /douban/recommended/tv                -> tv
        /douban/list/show_domestic            -> tv（综艺按剧集处理）
    """
    lowered = str(url or "").lower()
    if "movie" in lowered:
        return MEDIA_TYPE_MOVIE
    if "/tv" in lowered or "tv_" in lowered or "/show_" in lowered:
        return MEDIA_TYPE_TV
    return MEDIA_TYPE_MOVIE


#: 榜单路线 -> 题材提示。
#:
#: 为什么需要它：``/douban/list/*`` 的 RSS **没有 ``<category>`` 字段**
#: （实测综艺榜 26 条全是空的），条目只剩标题。而「综艺」这个信息其实写在
#: **频道**上 —— 用户勾了「排除题材：综艺 / 排除类型：真人秀」，却一条都
#: 拦不住，因为这些字幕根本没有进入条目的任何字段。
#: 这里按路线补一个题材串，等价于「把频道性质下放到每一条」：
#: 既让题材词匹配得到，也让 ``item_genre_ids`` 反查出 10764 / 99。
_ROUTE_GENRE_HINTS: Tuple[Tuple[str, str], ...] = (
    ("show_domestic", "综艺"),
    ("tv_variety", "综艺"),
    ("tv_show", "综艺"),
    ("tv_documentary", "纪录"),
)


def _genre_hint_of(url: str) -> str:
    """按榜单路线给出题材提示（列表类路线没有 ``<category>``）。"""
    lowered = str(url or "").lower()
    for key, hint in _ROUTE_GENRE_HINTS:
        if key in lowered:
            return hint
    return ""


#: 榜单 description 里那行的结构：``2026 / 中国大陆 / 真人秀 / 沈腾 白敬亭``
_DESC_YEAR = re.compile(r"^\s*(\d{4})\s*$")


def _category_from_description(description: str) -> str:
    """从 description 里抠出题材串（榜单类路线唯一可靠的题材来源）。

    真机实测 ``/douban/list/show_domestic`` 的条目：**没有 ``<category>``**，
    但 description 里写着::

        2026 / 中国大陆 / 真人秀 / 张泉灵 李维嘉

    第 3 段就是题材。少了它，「排除题材：真人秀」和「排除类型：真人秀(10764)」
    两条规则都会静默失效 —— 用户明明勾了，综艺照样被订进来。
    """
    if not description:
        return ""
    plain = _TAG.sub("\n", str(description))
    for line in plain.splitlines():
        parts = [part.strip() for part in line.split("/")]
        if len(parts) >= 3 and _DESC_YEAR.match(parts[0] or ""):
            return parts[2]
    return ""


def _channel_title(text: str) -> str:
    """取 RSS 的频道标题（仅用于排查展示）。"""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return ""
    channel = root.find("channel")
    return (channel.findtext("title") if channel is not None else "") or ""


def _extract(pattern: re.Pattern, text: str) -> Optional[str]:
    """取第一个匹配分组。"""
    if not text:
        return None
    match = pattern.search(text)
    return match.group(1) if match else None


def _dedupe(items: Sequence[DiscoveredItem]) -> List[DiscoveredItem]:
    """按豆瓣 id 去重（多个 RSS 可能有交集）。"""
    seen: set = set()
    result: List[DiscoveredItem] = []
    for item in items:
        if item.source_id in seen:
            continue
        seen.add(item.source_id)
        result.append(item)
    return result


__all__ = [
    "DEFAULT_MAX_ITEMS_PER_FEED",
    "DoubanRssSource",
    "TIMEOUT_SECONDS",
    "USER_AGENT",
    "parse_sources",
]
