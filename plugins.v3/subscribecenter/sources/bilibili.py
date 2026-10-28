"""哔哩哔哩番剧「播出时间表」发现源（自建实测，2026-10）。

数据来自**公开**接口：

``GET https://api.bilibili.com/pgc/web/timeline?types=1&before=0&after=7``

返回按天分组的番剧更新列表（``result[].episodes[]``），每条带
``season_id``、``title``（番剧名）、``pub_index``（第 N 话）、
``pub_ts``（上映时间戳，秒）、``published``（0 = 还没播）。

.. important:: 这个源的定位是 **AniList 的备份**，不是替代
   - AniList 会被限流（连续请求返回空 body），官方也偶尔停服；
   - B 站的时间表只覆盖「近 7 天内有更新」的番，一年只抓到几十条；
   - 两者叠加，AniList 挂了也还有一份国内视角的番剧档期。

已知边界（实测）：

- ``types=1`` 是番剧；``types=5``（真人剧）返回空数组 —— B 站没有真人剧排播，
  所以本源只产出剧集，不含电影 / 电视剧 / 综艺。
- ``after`` 最大 7 天，再大也只返回 7 天。
- 同一部番一周可能更新多集，这里按「最早那一集未播的」定档，只产出 1 条。
"""
from datetime import datetime
from typing import Any, Dict, List

from app.sdk.logging import logger

from ..core.constants import MEDIA_TYPE_TV, SOURCE_BILIBILI
from ..core.model import DiscoveredItem
from ..core.window import get_tz

#: 时间表接口（公开，无需登录）
ENDPOINT = "https://api.bilibili.com/pgc/web/timeline"

#: 必须带 Referer，否则偶发 412
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

#: 单次请求超时（秒）
TIMEOUT_SECONDS = 25

#: 接口支持的最大天数（再大也只返回 7 天）
MAX_DAYS = 7


class BilibiliSource:
    """B 站番剧时间表源（作为 AniList 的备份）。"""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_BILIBILI

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """拉取近 N 天的番剧更新表，按番剧聚合出档期。"""
        import aiohttp

        days = _int(config.get("bilibili_future_days"), 7)
        days = max(1, min(days, MAX_DAYS))
        limit = _int(config.get("bilibili_max_items"), 30)
        params = {"types": "1", "before": "0", "after": str(days)}
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://www.bilibili.com/",
        }
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(ENDPOINT, params=params) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"B 站时间表接口 HTTP {resp.status}")
                data = await resp.json(content_type=None)

        if _int(data.get("code"), -1) != 0:
            raise RuntimeError(
                f"B 站时间表接口返回错误：code={data.get('code')} "
                f"{data.get('message') or ''}".strip()
            )

        items = self._to_items(data.get("result") or [], limit)
        if not items:
            raise RuntimeError(
                "B 站时间表：近 7 天没有待播番剧。"
                "可能是接口改了，或这段时间确实没有新番更新"
            )
        logger.info(f"[SubscribeCenter] B 站番剧时间表：取到 {len(items)} 条")
        return items

    @staticmethod
    def _to_items(days: List[Dict[str, Any]], limit: int) -> List[DiscoveredItem]:
        """按 ``season_id`` 聚合，取每部番最早的那集定档日期。"""
        tz = get_tz()
        now = datetime.now(tz).timestamp()
        earliest: Dict[int, Dict[str, Any]] = {}
        for day in days:
            if not isinstance(day, dict):
                continue
            for ep in day.get("episodes") or []:
                if not isinstance(ep, dict):
                    continue
                if _int(ep.get("published"), 0) == 1:
                    # 今天这一集已经播了，订它没意义；下一集在后面的日子里
                    continue
                try:
                    season_id = int(ep.get("season_id"))
                except (TypeError, ValueError):
                    continue
                ts = _int(ep.get("pub_ts"), 0)
                if ts <= 0:
                    continue
                old = earliest.get(season_id)
                if old is None or ts < _int(old.get("pub_ts"), 0):
                    earliest[season_id] = ep

        items: List[DiscoveredItem] = []
        for season_id, ep in earliest.items():
            title = str(ep.get("title") or "").strip()
            if not title:
                continue
            ts = _int(ep.get("pub_ts"), 0)
            if ts <= 0 or ts < now:
                # 已经播过的旧集没有订阅价值（时间表里也会带当天已播的）
                continue
            moment = datetime.fromtimestamp(ts, tz)
            items.append(
                DiscoveredItem(
                    source=SOURCE_BILIBILI,
                    source_id=str(season_id),
                    title=title,
                    media_type=MEDIA_TYPE_TV,
                    year=str(moment.year),
                    release_date=moment.strftime("%Y-%m-%d"),
                    native_ids={"bilibili": str(season_id)},
                )
            )
            if len(items) >= limit:
                break
        items.sort(key=lambda item: item.release_date or "")
        return items


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
