"""③ 订阅服务拉取：豆瓣榜单（走 RSSHub，``RssHelper.parse``）。

把 RSS 条目归一为统一条目 dict（与 ``mp_source`` 一致）：
``title / year / media_type / vote_average / douban_id / tmdb_id / bangumi_id / poster``。

豆瓣 RSS 条目结构（RSSHub 产出）：
- ``title``：片名
- ``link``：``https://movie.douban.com/subject/<douban_id>/``（从中抽豆瓣 ID）
- ``description``：含年份、评分、类型等富文本
"""
from __future__ import annotations

import re
from typing import Any, List, Optional

from app.sdk.logging import logger

from ..core.subscribe_sources import SourceDef, rss_url


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _extract_douban_id(link: str) -> str:
    """从链接里抽豆瓣 ID（movie.douban.com/subject/<id>/ 或 m.douban.com/.../<id>）。"""
    if not link:
        return ""
    for match in re.finditer(r"/subject/(\d+)/?", link):
        return match.group(1)
    for match in re.finditer(r"/(\d{6,})/?$", link):
        return match.group(1)
    return ""


def _extract_year(text: str) -> str:
    """从描述里抽 4 位年份（1900-2099）。"""
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text or "")
    return match.group(1) if match else ""


def _extract_rating(text: str) -> float:
    """从描述里抽豆瓣评分（如「评分：8.5」或「8.5 分」）。"""
    match = re.search(r"(\d\.\d)\s*分", text or "")
    if not match:
        match = re.search(r"(?:评分|rate)[\s:：]*(\d\.\d)", text or "")
    return _to_float(match.group(1)) if match else 0.0


def _extract_description_text(description: Any) -> str:
    """description 可能是富文本 HTML，尽量取纯文本用于提取年份/评分。"""
    text = str(description or "")
    # 去 HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _normalize_item(item: dict, source: SourceDef) -> Optional[dict]:
    """把一条 RSS 条目归一为统一条目；无法识别关键字段时返回 None。"""
    title = str(item.get("title") or "").strip()
    link = str(item.get("link") or "").strip()
    if not title and not link:
        return None
    description = _extract_description_text(item.get("description") or "")
    douban_id = _extract_douban_id(link)
    return {
        "title": title,
        "year": _extract_year(description),
        "media_type": source.media_type,
        "vote_average": _extract_rating(description),
        "douban_id": douban_id,
        "tmdb_id": "",
        "bangumi_id": "",
        "poster": "",
    }


def fetch_douban_source(source: SourceDef, rsshub_base: str, *, proxy: bool = False) -> List[dict]:
    """拉取一个豆瓣榜单源，返回统一条目列表。

    注意：``RssHelper().parse`` 是**同步方法**（V3 宿主源码如此），不要包进 run_sync——
    包了会把返回的 list 当协程送进事件循环，报
    「An asyncio.Future, a coroutine or an awaitable is required」。
    """
    url = rss_url(source, rsshub_base)
    try:
        from app.sdk.network import RssHelper
    except Exception as err:  # pragma: no cover - 宿主接口缺失
        logger.error(f"无法加载宿主 RssHelper：{err}")
        return []
    try:
        items = RssHelper().parse(url, proxy=proxy, timeout=20)
    except Exception as err:  # pragma: no cover - 网络/解析异常
        logger.warning(f"拉取豆瓣 RSS 失败 {url}：{err}")
        return []
    if items is None or items is False or not isinstance(items, list):
        logger.warning(f"豆瓣 RSS 无有效数据：{url}")
        return []
    result: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_item(item, source)
        if normalized:
            result.append(normalized)
    return result
