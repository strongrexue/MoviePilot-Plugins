"""TMDB 数据源适配器（P1 唯一实现的源）。

实现要点（开发文档 §5.1）——**这里的取舍是本次核验最重要的发现**：

宿主的 ``tmdb_discover`` 对电影拼 ``release_date.gte``、对剧集拼
``first_air_date.gte``，**两处都没有上界**，也不暴露 ``region`` 与
``with_release_type``。因此「未来 N 天」无法在服务端表达，只能：

1. ``sort_by`` 用日期**升序**（``primary_release_date.asc`` / ``first_air_date.asc``），
   让下界之后最近的条目排在最前；
2. ``release_date`` 传今天，把历史条目挡在服务端之外；
3. **本地按上界过滤**（由流水线的窗口过滤完成，这里只负责取数和翻页）。

分页策略：逐页取，直到「本页最新一条都已超出窗口」或达到页数上限。
"""
import asyncio
from typing import Any, Dict, List, Optional, Sequence

from ..core.constants import (
    DEFAULT_MIN_RATING,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    SOURCE_TMDB,
)
from ..core.model import DiscoveredItem
from ..core.window import parse_date, release_sort_ascending, to_iso, today

#: discover 最多翻的页数（每页 20 条）。窗口靠升序 + 本地过滤收紧，
#: 翻太多页对「未来 30 天」没有收益。
DEFAULT_MAX_PAGES = 5

#: 服务端评分下界的松弛量：比最终阈值低一档，避免因四舍五入漏掉边界条目
RATING_RELAX = 0.5

#: 每页结果条数（TMDB 固定 20，仅用于日志估算）
PAGE_SIZE = 20


class TmdbSource:
    """基于宿主 ``TmdbChain`` 的 TMDB 发现源。

    :param chain: 宿主 ``TmdbChain`` 实例（或同签名的替身，便于单测）
    """

    def __init__(self, chain: Any, *, max_pages: int = DEFAULT_MAX_PAGES) -> None:
        self._chain = chain
        self._max_pages = max(1, int(max_pages))

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_TMDB

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """按配置拉取电影与剧集，返回标准化条目。

        电影与剧集并行拉取；任一分支异常都不应让另一分支失败。
        """
        future_days = _as_int(config.get("tmdb_future_days"), 30)
        min_rating = _as_float(config.get("min_rating_tmdb"), DEFAULT_MIN_RATING)
        tz_name = config.get("timezone")
        start = today(tz_name)

        results = await asyncio.gather(
            self._fetch_type(MEDIA_TYPE_MOVIE, future_days, min_rating, start, tz_name),
            self._fetch_type(MEDIA_TYPE_TV, future_days, min_rating, start, tz_name),
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
            # 两个分支都失败时才算源失败，让流水线记录真实原因
            raise RuntimeError("; ".join(errors))
        return items

    # ------------------------------------------------------------------ 内部

    async def _fetch_type(
        self,
        media_type: str,
        future_days: int,
        min_rating: float,
        start: Any,
        tz_name: Optional[str],
    ) -> List[DiscoveredItem]:
        """拉取单一媒体类型的全部页。"""
        items: List[DiscoveredItem] = []
        sort_by = release_sort_ascending(media_type)

        for page in range(1, self._max_pages + 1):
            infos = await self._discover(
                media_type=media_type,
                sort_by=sort_by,
                min_rating=min_rating,
                start=start,
                page=page,
            )
            if not infos:
                break

            page_items = [self._normalize(info, media_type, tz_name) for info in infos]
            page_items = [item for item in page_items if item is not None]

            if not page_items:
                # 整页都是无法归一的条目（缺 ID/缺日期）——继续翻页没有意义
                break
            items.extend(page_items)

            # 升序排序下：本页最晚的定档日期已超出窗口 → 后续页只会更晚，停止翻页
            latest = max(
                (parse_date(item.release_date, tz_name) for item in page_items
                 if parse_date(item.release_date, tz_name) is not None),
                default=None,
            )
            if latest is None:
                break
            if (latest - start).days > future_days:
                break
            if len(infos) < PAGE_SIZE:
                break

        return items

    async def _discover(
        self,
        *,
        media_type: str,
        sort_by: str,
        min_rating: float,
        start: Any,
        page: int,
    ) -> Sequence[Any]:
        """调用宿主 ``async_tmdb_discover``；把媒体类型字符串换成宿主枚举。"""
        media_type_enum = _media_type_enum(media_type)
        if media_type_enum is None:
            return ()
        return await self._chain.async_tmdb_discover(
            mtype=media_type_enum,
            sort_by=sort_by,
            with_genres="",
            with_original_language="",
            with_keywords="",
            with_watch_providers="",
            vote_average=max(0.0, float(min_rating) - RATING_RELAX),
            vote_count=0,
            release_date=start.isoformat(),
            page=page,
        ) or ()

    @staticmethod
    def _normalize(info: Any, media_type: str, tz_name: Optional[str]) -> Optional[DiscoveredItem]:
        """把宿主 ``MediaInfo`` 归一为 :class:`DiscoveredItem`。

        身份直接取 ``tmdb_id``（TMDB 源自带确定性 ID，归入 L1），
        因此本条目的身份解析不需要任何网络搜索。
        """
        tmdb_id = getattr(info, "tmdb_id", None)
        if not tmdb_id:
            return None

        title = getattr(info, "title", None) or getattr(info, "original_title", None)
        if not title:
            return None

        release_date = to_iso(getattr(info, "release_date", None), tz_name)
        if not release_date:
            # 没有定档日期就无法判断「即将开播」，直接丢弃（宁缺毋滥）
            return None

        year = getattr(info, "year", None)
        rating = getattr(info, "vote_average", None)

        return DiscoveredItem(
            source=SOURCE_TMDB,
            source_id=str(tmdb_id),
            title=str(title),
            media_type=media_type,
            year=str(year) if year else release_date[:4],
            original_title=getattr(info, "original_title", None),
            release_date=release_date,
            rating=_as_float(rating, None) if rating is not None else None,
            popularity=_as_float(getattr(info, "popularity", None), None),
            native_ids={"tmdb": str(tmdb_id)},
            raw={"tmdb_id": tmdb_id, "release_date": release_date},
        )


# --------------------------------------------------------------------- 工具

def _media_type_enum(media_type: str) -> Any:
    """把 ``"movie"``/``"tv"`` 换成宿主 ``MediaType``；失败返回 ``None``。"""
    try:
        from app.schemas.types import MediaType
    except Exception:  # noqa: BLE001 - 无宿主环境（离线单测）时按不可用处理
        return None
    return MediaType.MOVIE if media_type == MEDIA_TYPE_MOVIE else MediaType.TV


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


__all__ = ["DEFAULT_MAX_PAGES", "PAGE_SIZE", "TmdbSource"]
