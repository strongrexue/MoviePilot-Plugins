"""AniList 数据源适配器。

.. important::
   以下每一条都是**实测**结论（2026-10，真机）：

   - ``graphql.anilist.co`` 只接受 **POST**；用 GET 带 query 会返回
     ``{"errors":[{"message":"Not Found.","hint":"Use POST request..."}]}``。
   - 直连时**必须带浏览器 UA**，否则 403 Forbidden（默认 Python UA 被拦）。
   - ``title.native`` 对 ``countryOfOrigin: CN`` 的条目**就是中文原名**
     （牧神记 / 凡人修仙传 第四季 / 遮天），对日番则是日文原名。
   - ``countryOfOrigin`` 可用于区分国漫与日番。
   - ``nextAiringEpisode`` 给出下一集的播出时间戳（秒），这是**连载中**作品
     唯一可用的窗口信号。

为什么需要两条发现通道（缺一不可）：

- **新番通道**：``season`` + ``seasonYear`` 查询，按 ``startDate`` 落窗口。
  覆盖「即将开播」的番。
- **连载通道**：``status: RELEASING`` 查询，按 ``nextAiringEpisode.airingAt``
  落窗口。**国漫只能靠这条通道发现** —— 它们多是长篇连载（《遮天》2023 年
  开播、208 集），开播日永远在窗口之外，用「开播日 + 窗口」的逻辑永远抓不到。
  这不是识别问题，是窗口语义问题。

为什么用 AniList 而不是只靠 Bangumi（实测对比）：

- Bangumi ``/calendar`` 当季 108 部，6 个知名国漫只出现 1 个（牧神记5），
  凡人修仙传 / 斗破苍穹 / 遮天 / 吞噬星空 / 完美世界 **全都不在**；
- AniList 全部覆盖，且国漫给的是中文原名 —— 对 TMDB 解析是最高质量输入。

Bangumi 因此降级为**标题翻译层**（见 ``core/host.py`` 的 ``bangumi_aliases``）：
日番的日文原名搜不到 TMDB 时，用 Bangumi 的中文名再试一次。
"""
import asyncio  # noqa: F401 - 保持与其他源一致的导入风格
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.constants import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    SOURCE_ANILIST,
)
from ..core.model import DiscoveredItem, is_special
from ..core.window import get_tz, in_window, parse_date, today

from app.sdk.logging import logger

#: AniList GraphQL 端点（只接受 POST）
ENDPOINT = "https://graphql.anilist.co"

#: 必须伪装成浏览器，否则 403
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

#: 单次请求超时（秒）
TIMEOUT_SECONDS = 25

#: 每次请求前的节流（秒）——AniList 对连续请求会限流
_THROTTLE = 0.3
#: 单个请求最多尝试几次
_MAX_ATTEMPTS = 3
#: 重试退避基数（秒），第 n 次等待 n * _BACKOFF
_BACKOFF = 1.5

#: 每页条数（AniList 上限 50）
PAGE_SIZE = 50

#: 连载通道最多翻几页（按热度倒序，2 页 = 100 部，够覆盖当季在播）
ONGOING_PAGES = 2

#: 国漫/日番统一按剧集处理；AniList 里 MOVIE / ONE_SHOT 才是电影
MOVIE_FORMATS = frozenset({"MOVIE", "ONE_SHOT"})

#: 字段集合：两条通道共用
MEDIA_FIELDS = """
    id
    idMal
    countryOfOrigin
    isAdult
    format
    status
    episodes
    popularity
    averageScore
    season
    seasonYear
    startDate { year month day }
    title { native romaji english }
    nextAiringEpisode { episode airingAt }
"""

SEASON_QUERY = (
    "query ($page: Int, $perPage: Int, $season: MediaSeason, $seasonYear: Int) {"
    "  Page(page: $page, perPage: $perPage) {"
    f"    media(season: $season, seasonYear: $seasonYear, type: ANIME,"
    "          sort: [START_DATE], isAdult: false) {"
    f"{MEDIA_FIELDS}"
    "    }"
    "  }"
    "}"
)

ONGOING_QUERY = (
    "query ($page: Int, $perPage: Int) {"
    "  Page(page: $page, perPage: $perPage) {"
    "    media(type: ANIME, status: RELEASING, sort: [POPULARITY_DESC], isAdult: false) {"
    f"{MEDIA_FIELDS}"
    "    }"
    "  }"
    "}"
)

#: 国漫专用查询：**必须按产地单独查**。
#:
#: 真机：连载通道按 popularity 倒序，前 100 条全是日番（ONE PIECE、药屋…），
#: 国漫热度（实测 1100~19000）根本挤不进来。而 ``countryOfOrigin: "CN"``
#: 过滤实测有效 —— 直接返回 时光代理人S3 / 仙逆(180集) / 遮天(208集) /
#: 炼气十万年(420集) 等。
DONGHUA_QUERY = (
    "query ($page: Int, $perPage: Int) {"
    "  Page(page: $page, perPage: $perPage) {"
    '    media(type: ANIME, status: RELEASING, countryOfOrigin: "CN",'
    "          sort: [POPULARITY_DESC], isAdult: false) {"
    f"{MEDIA_FIELDS}"
    "    }"
    "  }"
    "}"
)

#: 季度枚举（AniList 的 MediaSeason）
SEASONS = ("WINTER", "SPRING", "SUMMER", "FALL")


def season_of(day) -> tuple:
    """返回 ``(season, year)``：1-3 月 WINTER、4-6 SPRING、7-9 SUMMER、10-12 FALL。"""
    index = (day.month - 1) // 3
    return SEASONS[index], day.year


def next_season(season: str, year: int) -> tuple:
    """返回下一个季度。"""
    position = SEASONS.index(season)
    if position == len(SEASONS) - 1:
        return SEASONS[0], year + 1
    return SEASONS[position + 1], year


class AniListSource:
    """基于 AniList GraphQL 的番剧发现源。"""

    def __init__(self, client: Any = None) -> None:
        """:param client: 可选的自管 HTTP 客户端（测试注入）。"""
        self._client = client

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_ANILIST

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """拉取三条通道的条目，并按窗口过滤。

        - ① **新番**：当季 + 下季，按 ``startDate`` 落窗口；
        - ② **连载中（通用）**：按 ``nextAiringEpisode`` 落窗口；
        - ③ **连载中（国漫专用）**：按 ``countryOfOrigin: CN`` 单独查 ——
          国漫热度（1100~19000）挤不进通用通道的「热度前 100」。

        国漫里有一部分 AniList **不跟踪播出表**（``nextAiringEpisode = None``，
        实测 遮天 / 吞噬星空 就是这样）。这类条目用 ``date_unknown=True`` 放行，
        交给「TMDB 还有没有未播集」判定 —— 这是同一条纪律的复用：
        **缺失日期不等于该丢弃，剧集可以靠未播集判断。**
        """
        future_days = _as_int(config.get("anilist_future_days"), 3)
        include_donghua = bool(config.get("anilist_include_donghua", True))
        tz_name = config.get("timezone")

        anchor = today(tz_name)
        payloads: List[tuple] = []

        # 通道①：当季 + 下季的新番（按开播日落窗口）
        season, year = season_of(anchor)
        seasons = [(season, year), next_season(season, year)]
        for entry in seasons:
            for page in range(1, 3):
                data = await self._query(
                    SEASON_QUERY,
                    {
                        "page": page,
                        "perPage": PAGE_SIZE,
                        "season": entry[0],
                        "seasonYear": entry[1],
                    },
                )
                media = _page_media(data)
                payloads.extend(("start", row) for row in media)
                if len(media) < PAGE_SIZE:
                    break

        # 通道②：连载中（按下一集播出时间落窗口）
        for page in range(1, ONGOING_PAGES + 1):
            try:
                data = await self._query(ONGOING_QUERY, {"page": page, "perPage": PAGE_SIZE})
            except Exception as err:  # noqa: BLE001 - 单通道失败不拖垮整体
                logger.warning(f"[SubscribeCenter] AniList 连载通道失败：{err}")
                break
            media = _page_media(data)
            payloads.extend(("ongoing", row) for row in media)
            if len(media) < PAGE_SIZE:
                break

        # 通道③：国漫（按产地单查，只有一页 —— 热度前 50 已覆盖主流国漫）
        if include_donghua:
            try:
                data = await self._query(DONGHUA_QUERY, {"page": 1, "perPage": PAGE_SIZE})
            except Exception as err:  # noqa: BLE001 - 单通道失败不拖垮整体
                logger.warning(f"[SubscribeCenter] AniList 国漫通道失败：{err}")
            else:
                payloads.extend(("donghua", row) for row in _page_media(data))

        items: List[DiscoveredItem] = []
        seen: set = set()
        for channel, row in payloads:
            chinese = _is_chinese(row)
            if chinese and not include_donghua:
                continue

            item = self._to_item(row, channel, tz_name)
            if item is None:
                continue

            if item.release_date is None:
                # 只有国漫允许「没有日期」：AniList 不跟踪它的播出表，
                # 但 TMDB 会告诉我们它还有没有未播集。
                if not (channel == "donghua" and item.is_tv):
                    continue
                item.date_unknown = True
            else:
                # release_date 是「落进窗口的那一天」（新番=开播日，连载=下一集播出日），
                # 必须显式解析成 date 再判定，不能拿字符串比较。
                release = parse_date(item.release_date, tz_name=tz_name)
                if not in_window(release, future_days, tz_name=tz_name, now=anchor):
                    continue

            key = f"{item.source_id}:{item.release_date}"
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        return items

    # ------------------------------------------------------------------ 归一

    def _to_item(
        self,
        row: Dict[str, Any],
        channel: str,
        tz_name: Optional[str],
    ) -> Optional[DiscoveredItem]:
        """把一条 AniList media 归一为 DiscoveredItem。"""
        title, original_title = _titles(row)
        if not title:
            return None

        start = _date_of(row.get("startDate"))
        next_airing = _next_airing_date(row, tz_name)
        # release_date 必须是「**落进窗口的那一天**」，流水线的窗口过滤和
        # 日期自检都读它：
        #   新番通道 = 开播日；连载通道 = 下一集播出日。
        #
        # 国漫通道特殊：AniList 不跟踪部分国漫的播出表
        # （实测 遮天 / 吞噬星空 的 nextAiringEpisode 是 None）。
        # 这类条目**不给日期**（release_date=None），由 fetch() 标记
        # ``date_unknown`` 交给「TMDB 还有没有未播集」判定 ——
        # 若退回去用 2023 年的开播日，会被窗口直接丢掉，等于永远发现不了。
        if channel == "start":
            anchor_date = start
        else:
            anchor_date = next_airing
            if anchor_date is None and channel != "donghua":
                # 通用连载通道必须有下一集时间，否则会捞出大量长篇旧番
                return None

        format_name = str(row.get("format") or "").upper()
        media_type = MEDIA_TYPE_MOVIE if format_name in MOVIE_FORMATS else MEDIA_TYPE_TV
        anilist_id = str(row.get("id") or "")
        if not anilist_id:
            return None

        native_ids = {"anilist": anilist_id}
        if row.get("idMal"):
            native_ids["mal"] = str(row["idMal"])

        popularity = row.get("popularity")
        score = row.get("averageScore")

        return DiscoveredItem(
            source=self.name,
            source_id=anilist_id,
            title=title,
            media_type=media_type,
            year=str(start.year) if start else None,
            original_title=original_title,
            release_date=anchor_date.isoformat() if anchor_date else None,
            rating=float(score) / 10.0 if isinstance(score, (int, float)) else None,
            popularity=float(popularity) if isinstance(popularity, (int, float)) else None,
            native_ids=native_ids,
            special=is_special(title),
            raw={
                "anilist_status": row.get("status"),
                "anilist_format": format_name,
                "country": row.get("countryOfOrigin"),
                "episodes": row.get("episodes"),
                "start_date": start.isoformat() if start else None,
                "next_airing": next_airing.isoformat() if next_airing else None,
                "channel": channel,
            },
        )

    # ------------------------------------------------------------------ HTTP

    async def _query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """执行一次 GraphQL 查询（**带节流与重试**）。

        失败必须抛 —— 静默返回空会被当成「今天没新番」。

        真机：一轮连发 6 个请求（当季 2 页 + 下季 2 页 + 连载 + 国漫），
        AniList 被限流时偶尔返回**空响应体**，json 解析抛
        ``JSONDecodeError: Expecting value: line 1 column 1 (char 0)``，
        一个请求失败就把整个源打成「失败」。这里：
        1. 每次请求前节流 ``_THROTTLE`` 秒
        2. 空响应 / 非 JSON / 网络错误都按**可重试**处理，最多 3 次
        3. 3 次都失败才抛，并给出人话提示
        """
        await asyncio.sleep(_THROTTLE)
        body = {"query": query, "variables": variables}
        last_error = ""
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._post(body)
            except Exception as err:  # noqa: BLE001 - 统一按可重试处理
                last_error = f"{type(err).__name__}: {err}"
            else:
                if isinstance(response, dict):
                    if response.get("errors"):
                        errors = response["errors"] or []
                        message = (errors[0] or {}).get("message") or "未知错误"
                        raise RuntimeError(f"AniList 查询失败：{message}")
                    return response
                last_error = f"返回内容不是 JSON（{str(response)[:60]!r}）"

            if attempt < _MAX_ATTEMPTS:
                delay = _BACKOFF * attempt
                logger.warning(
                    f"[SubscribeCenter] AniList 第 {attempt} 次请求失败（{last_error}），"
                    f"{delay:.1f}s 后重试"
                )
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"AniList 连续 {_MAX_ATTEMPTS} 次请求失败（可能被限流）：{last_error}"
        )

    async def _post(self, body: Dict[str, Any]) -> Any:
        """POST 到 AniList，返回解析后的 JSON。"""
        if self._client is not None:
            response = await self._client.post(ENDPOINT, json=body)
            return getattr(response, "json", lambda: response)()

        from app.runtime.settings import get_runtime_setting
        from app.sdk.network import AsyncRequestUtils

        utils = AsyncRequestUtils(
            ua=USER_AGENT,
            proxies=get_runtime_setting("PROXY") or None,
            timeout=TIMEOUT_SECONDS,
        )
        response = await utils.post_res(
            ENDPOINT,
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            raise_exception=True,
        )
        if not response:
            raise RuntimeError("AniList 无响应")
        return response.json()


# ---------------------------------------------------------------------- 工具


def _page_media(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """取出 ``Page.media`` 列表。"""
    page = (data or {}).get("data", {}).get("Page") or {}
    media = page.get("media") or []
    return [row for row in media if isinstance(row, dict)]


def _titles(row: Dict[str, Any]) -> tuple:
    """返回 ``(首选标题, 原名/罗马音)``。

    国漫的 ``native`` 就是中文原名（最适合作首选）；日番的 ``native`` 是日文，
    此时用 ``romaji`` 作原名，日文原名留给 ``bangumi_aliases`` 去翻译。
    """
    title = row.get("title") or {}
    native = str(title.get("native") or "").strip()
    romaji = str(title.get("romaji") or "").strip()
    english = str(title.get("english") or "").strip()

    if _is_chinese(row) and native:
        return native, romaji or english or native
    return (native or romaji or english), (romaji or english or native)


def _is_chinese(row: Dict[str, Any]) -> bool:
    """是否国产动画。"""
    return str(row.get("countryOfOrigin") or "").upper() == "CN"


def _date_of(payload: Any) -> Optional[Any]:
    """把 AniList 的 ``{year,month,day}`` 转成 date（缺字段则返回 None）。"""
    if not isinstance(payload, dict):
        return None
    year = payload.get("year")
    month = payload.get("month") or 1
    day = payload.get("day") or 1
    if not year:
        return None
    try:
        return datetime(int(year), int(month), int(day)).date()
    except (TypeError, ValueError):
        return None


def _next_airing_date(row: Dict[str, Any], tz_name: Optional[str]) -> Optional[Any]:
    """下一集播出日期（按配置时区换算），没有则为 None。"""
    payload = row.get("nextAiringEpisode") or {}
    stamp = payload.get("airingAt")
    if not isinstance(stamp, (int, float)):
        return None
    moment = datetime.fromtimestamp(int(stamp), tz=timezone.utc)
    return moment.astimezone(get_tz(tz_name)).date()


def _as_int(value: Any, default: int) -> int:
    """安全转 int。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
