"""TMDB 数据源适配器（P1）。

.. important::
   本模块**刻意绕过** ``TmdbChain.tmdb_discover``，直接调用宿主模块层的
   ``TmdbApi.async_discover_*``。原因是实机核验发现的硬限制：

   ``tmdb_discover`` 把日期过滤写死成 ``release_date.gte`` / ``first_air_date.gte``，
   **TMDB 并不接受 ``release_date.gte`` 作为过滤参数**（它只是排序字段），
   所以下界被静默忽略；再叠加「按日期升序」排序，TMDB 把 ``release_date`` 为空的
   条目当最小值排在最前 —— 结果就是拉回一堆 1926 年前后的老片（0.2.0 真实事故）。

   正确的过滤参数是 ``primary_release_date.gte/lte``（电影）与
   ``first_air_date.gte/lte``（剧集）。实机实测：
   - 错误用法：771 条全部落在窗口外（1926 年起的默片）；
   - 正确用法：1708 条全部落在目标窗口内。

   代价是耦合了 ``app.modules.themoviedb.tmdbapi`` 这一层（它属于官方文档
   「仍可稳定使用」的既有入口），收益是日期窗口真正生效。这一取舍是显式的。

取数策略（每种媒体类型最多 2×N 个查询）：

1. 按 ``popularity.desc``：拉「受关注的新片」，避免被同日上映的冷门片子淹没；
2. 按日期升序（``primary_release_date.asc`` / ``first_air_date.asc``）：补齐窗口内条目。

身份：TMDB 返回自带 ``id``，直接作为 L1 确定性身份，**不做任何标题匹配**。
"""
import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.constants import (
    DEFAULT_MIN_RATING,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    SOURCE_TMDB,
)
from ..core.model import DiscoveredItem
from ..core.window import today

#: 每种媒体类型每种排序的最大拉取页数
DEFAULT_MAX_PAGES = 3

#: 电影上映类型：2=限定上映, 3=院线上映
MOVIE_RELEASE_TYPES = "2|3"

#: TMDB 每页条数
PAGE_SIZE = 20


class TmdbSource:
    """基于宿主 ``TmdbApi`` 模块层的 TMDB 发现源。

    :param api: ``app.modules.themoviedb.tmdbapi.TmdbApi`` 实例（或同签名替身）
    """

    def __init__(self, api: Any, *, max_pages: int = DEFAULT_MAX_PAGES) -> None:
        self._api = api
        self._max_pages = max(1, int(max_pages))

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_TMDB

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """按配置拉取电影与剧集，返回标准化条目。"""
        future_days = _as_int(config.get("tmdb_future_days"), 30)
        min_rating = _as_float(config.get("min_rating_tmdb"), DEFAULT_MIN_RATING)
        tz_name = config.get("timezone")

        results = await asyncio.gather(
            self._fetch_type(MEDIA_TYPE_MOVIE, future_days, min_rating, tz_name),
            self._fetch_type(MEDIA_TYPE_TV, future_days, min_rating, tz_name),
            return_exceptions=True,
        )

        items: List[DiscoveredItem] = []
        errors: List[str] = []
        for result in results:
            if isinstance(result, BaseException):
                errors.append(f"{type(result).__name__}: {result}")
                continue
            items.extend(result)

        if errors and not items:
            raise RuntimeError("; ".join(errors))
        return items

    # ------------------------------------------------------------------ 内部

    async def _fetch_type(
        self,
        media_type: str,
        future_days: int,
        min_rating: float,
        tz_name: Optional[str],
    ) -> List[DiscoveredItem]:
        """拉取单一媒体类型：popularity 与日期两种排序各取若干页。"""
        start = today(tz_name)
        end = start + timedelta(days=max(1, future_days))
        seen: Dict[str, DiscoveredItem] = {}

        for sort_by in self._sort_keys(media_type):
            for page in range(1, self._max_pages + 1):
                params = self._build_params(
                    media_type=media_type,
                    sort_by=sort_by,
                    start=start.isoformat(),
                    end=end.isoformat(),
                    page=page,
                )
                raw = await self._discover(media_type, params)
                if not raw:
                    break

                added = 0
                for info in raw:
                    item = self._normalize(info, media_type)
                    if item is None or item.source_id in seen:
                        continue
                    seen[item.source_id] = item
                    added += 1
                # 整页都是已知条目说明该排序已翻到底，换下一种排序
                if added == 0:
                    break
                if len(raw) < PAGE_SIZE:
                    break

        return list(seen.values())

    @staticmethod
    def _sort_keys(media_type: str) -> Tuple[str, ...]:
        """返回要使用的排序组合（先关注度，再按日期补齐）。"""
        date_field = (
            "first_air_date.asc" if media_type == MEDIA_TYPE_TV else "primary_release_date.asc"
        )
        return ("popularity.desc", date_field)

    @staticmethod
    def _build_params(
        *,
        media_type: str,
        sort_by: str,
        start: str,
        end: str,
        page: int,
    ) -> Dict[str, Any]:
        """构造 TMDB discover 参数。

        两个**必须**遵守的实测结论：

        1. 日期过滤用 ``primary_release_date.gte/lte``（电影）或
           ``first_air_date.gte/lte``（剧集）。用 ``release_date.gte`` 会被 TMDB
           静默忽略（0.2.0 事故）。
        2. **不要加 ``vote_average.gte``**：未来 30 天内要上映的片子全都还没人评分
           （``vote_average=0``），任何服务端评分下界都会把它们整体滤掉
           —— 实测 ``vote_average.gte=5.0`` 把 1708 部电影压到 4 部、229 部剧集压到 0 部
           （0.2.1 事故）。评分判断只在流水线里对「**有评分且明确过低**」的条目生效。
        """
        params: Dict[str, Any] = {
            "sort_by": sort_by,
            "include_adult": "false",
            "page": page,
        }
        if media_type == MEDIA_TYPE_TV:
            params["first_air_date.gte"] = start
            params["first_air_date.lte"] = end
        else:
            params["primary_release_date.gte"] = start
            params["primary_release_date.lte"] = end
            params["with_release_type"] = MOVIE_RELEASE_TYPES
        return params

    async def _discover(self, media_type: str, params: Dict[str, Any]) -> Sequence[dict]:
        """调用宿主模块层的异步 discover。"""
        if media_type == MEDIA_TYPE_TV:
            return await self._api.async_discover_tvs(params) or ()
        return await self._api.async_discover_movies(params) or ()

    @staticmethod
    def _normalize(info: Any, media_type: str) -> Optional[DiscoveredItem]:
        """把 TMDB 原始字典归一为 :class:`DiscoveredItem`。

        直接用 TMDB 原始字典，**不经过** ``MediaInfo(tmdb_info=...)`` ——
        避免依赖宿主投影层的字段映射细节。
        """
        if not isinstance(info, dict):
            return None
        tmdb_id = info.get("id")
        if not tmdb_id:
            return None

        is_tv = media_type == MEDIA_TYPE_TV
        release_date = info.get("first_air_date") if is_tv else info.get("release_date")
        title = info.get("name") if is_tv else info.get("title")
        original_title = info.get("original_name") if is_tv else info.get("original_title")
        if not title or not release_date:
            # 没有定档日期就无法判断「即将开播」，直接丢弃（宁缺毋滥）
            return None

        vote = info.get("vote_average")
        return DiscoveredItem(
            source=SOURCE_TMDB,
            source_id=str(tmdb_id),
            title=str(title),
            media_type=media_type,
            year=str(release_date)[:4],
            original_title=original_title,
            release_date=str(release_date),
            rating=float(vote) if vote else None,
            popularity=_as_float(info.get("popularity"), None),
            native_ids={"tmdb": str(tmdb_id)},
            raw={
                "tmdb_id": tmdb_id,
                "release_date": release_date,
                "vote_count": info.get("vote_count"),
                "original_language": info.get("original_language"),
            },
        )


# --------------------------------------------------------------------- 工具

def _as_int(value: Any, default: int) -> int:
    """宽松整型转换。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: Optional[float]) -> Optional[float]:
    """宽松浮点转换。"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "DEFAULT_MAX_PAGES",
    "MOVIE_RELEASE_TYPES",
    "PAGE_SIZE",
    "TmdbSource",
]
