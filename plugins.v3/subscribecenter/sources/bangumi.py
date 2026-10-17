"""Bangumi 数据源适配器。

.. important::
   本模块的每一个外部假设都在真机上实测过（0.6.0）：

   - **可用域名**：``https://api.bgm.tv``（经宿主代理）。``api.bangumi.tv`` 与
     ``bgm.tv`` 实测均失败（SSL/非 JSON），只有 ``api.bgm.tv`` 通。
   - **必须带 User-Agent**：Bangumi 对匿名默认 UA 会拒绝。
   - **``/calendar`` 是唯一可用的「未来开播」数据源**：
     ``/v0/subjects?air_date=...`` 的过滤条件**被忽略**（实测传
     ``>=今天`` 仍返回全库 29601 条、从 2029 年倒序），所以不能用。
   - ``/calendar`` 覆盖**当季**番剧（实测 107 部），条目自带
     ``air_date``（该番首播日）。当前窗口内要开播的新番就在其中
     （实测未来 3 天有 3 部，含《赛博朋克：边缘行者 2》）。

局限（已知且可接受）：

- ``/calendar`` 只覆盖当季，季末切档前后可能漏掉下季刚定档的番；
- 条目**不带 popularity**，所以本源的条目会跳过「最低关注度」门槛
  （流水线对缺失 popularity 的条目放行）—— 这是有意的：番剧当季列表
  本身是人工策展的，用 TMDB 的关注度量纲去卡它没有意义。
"""
from typing import Any, Dict, List, Optional, Sequence

from ..core.constants import MEDIA_TYPE_TV, SOURCE_BANGUMI
from ..core.model import DiscoveredItem, is_special
from ..core.window import parse_date, today

#: Bangumi 公开 API 基础地址（实测唯一可用域名）
BASE_URL = "https://api.bgm.tv"

#: 必填 UA —— Bangumi 会拒绝默认 UA
USER_AGENT = "SubscribeCenter/0.6.0 (MoviePilot plugin; +https://github.com/strongrexue)"

#: 单次请求超时（秒）
TIMEOUT_SECONDS = 20

#: Bangumi 番剧在 TMDB 侧统一按剧集处理
BANGUMI_MEDIA_TYPE = MEDIA_TYPE_TV


class BangumiSource:
    """基于 Bangumi 公开 ``/calendar`` 的当季新番发现源。

    :param client: 可选的自管异步 HTTP 客户端（便于测试注入）
    """

    def __init__(self, client: Any = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_BANGUMI

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """拉取当季番剧并筛出窗口内开播的条目。"""
        future_days = _as_int(config.get("bangumi_future_days"), 3)
        tz_name = config.get("timezone")
        payload = await self._fetch_calendar()
        items = self.normalize(payload, future_days, tz_name)
        return items

    # ------------------------------------------------------------------ 取数

    async def _fetch_calendar(self) -> Sequence[dict]:
        """请求 ``/calendar``；失败抛出，由流水线标记该源失败。"""
        url = f"{BASE_URL}/calendar"
        if self._client is not None:
            # 测试注入：只需实现 ``await client.get(url) -> 带 status_code/json() 的响应``
            return _parse_calendar(await self._client.get(url))

        # 真实路径用宿主的 AsyncRequestUtils：它内部处理代理与 httpx2 版本差异。
        # 直接 new httpx2.AsyncClient(proxies=...) 会失败 —— httpx 0.28+ 已把
        # proxies 改名（真机踩过：TypeError: unexpected keyword argument 'proxies'）。
        from app.runtime.settings import get_runtime_setting
        from app.sdk.network import AsyncRequestUtils

        proxy = get_runtime_setting("PROXY")
        utils = AsyncRequestUtils(
            ua=USER_AGENT,
            proxies=proxy or None,
            timeout=TIMEOUT_SECONDS,
        )
        response = await utils.get_res(url, raise_exception=True)
        if not response:
            raise RuntimeError("Bangumi /calendar 无响应")
        return _parse_calendar(response)

    # ------------------------------------------------------------------ 归一

    @staticmethod
    def normalize(
        payload: Sequence[dict],
        future_days: int,
        tz_name: Optional[str] = None,
        *,
        now: Any = None,
    ) -> List[DiscoveredItem]:
        """把 ``/calendar`` 结果筛成窗口内的发现条目。

        ``/calendar`` 是「按星期分组」的结构，这里拍平后按 ``air_date``
        过滤 —— 只保留「今天 ~ 今天+N 天」首播的番。
        """
        start = now or today(tz_name)
        end = start + _delta(future_days)
        items: List[DiscoveredItem] = []
        seen: set = set()

        for weekday in payload or ():
            if not isinstance(weekday, dict):
                continue
            for subject in weekday.get("items") or ():
                if not isinstance(subject, dict):
                    continue
                subject_id = subject.get("id")
                if not subject_id or subject_id in seen:
                    continue
                air_date = parse_date(subject.get("air_date"), tz_name)
                if air_date is None or air_date < start or air_date > end:
                    continue
                seen.add(subject_id)

                title = (
                    subject.get("name_cn")
                    or subject.get("name")
                    or ""
                ).strip()
                if not title:
                    continue

                rating = subject.get("rating") or {}
                score = rating.get("score") if isinstance(rating, dict) else None
                items.append(
                    DiscoveredItem(
                        source=SOURCE_BANGUMI,
                        source_id=str(subject_id),
                        title=title,
                        media_type=BANGUMI_MEDIA_TYPE,
                        year=str(air_date.year),
                        original_title=subject.get("name"),
                        release_date=air_date.isoformat(),
                        # 注意：不把 rating.total 当 popularity —— 近期番评分人数极低，
                        # 塞进去会被 popularity 门槛整体误杀。本源不带关注度。
                        popularity=None,
                        rating=float(score) if score else None,
                        native_ids={"bangumi": str(subject_id)},
                        special=is_special(title),
                        raw={
                            "bangumi_id": subject_id,
                            "air_date": subject.get("air_date"),
                            "air_weekday": subject.get("air_weekday"),
                            "rating_total": (rating or {}).get("total") if isinstance(rating, dict) else None,
                        },
                    )
                )

        items.sort(key=lambda item: (item.release_date or "", item.title))
        return items


# --------------------------------------------------------------------- 工具

def _parse_calendar(response: Any) -> Sequence[dict]:
    """把响应解析成 ``/calendar`` 的周数组；结构异常或 HTTP 错误抛出。"""
    status = getattr(response, "status_code", 0)
    if status and status >= 400:
        raise RuntimeError(f"Bangumi /calendar 返回 HTTP {status}")
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Bangumi /calendar 返回结构异常：{type(data).__name__}")
    return data


def _delta(days: int) -> Any:
    """返回 ``timedelta``；非法天数按 1 天。"""
    from datetime import timedelta

    count = days if isinstance(days, int) and days > 0 else 1
    return timedelta(days=count)


def _as_int(value: Any, default: int) -> int:
    """宽松整型转换。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = ["BASE_URL", "BANGUMI_MEDIA_TYPE", "BangumiSource", "USER_AGENT", "is_special"]
