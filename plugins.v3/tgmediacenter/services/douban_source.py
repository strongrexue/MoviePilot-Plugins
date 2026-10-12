"""③ 订阅服务拉取：豆瓣榜单（走 RSSHub，RequestUtils 同步取回 + 标准库解析）。

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

    **不走宿主 ``RssHelper``**：其内部装配链路（组合根端口/快照配置）随宿主构建
    版本变动过，曾出现难以定位的异步桥接报错。这里直接用宿主 ``RequestUtils``
    （同步 requests）取回 XML，再用标准库解析成与 RssHelper 兼容的条目 dict。
    """
    url = rss_url(source, rsshub_base)
    xml_text, err = _fetch_xml(url, proxy=proxy, timeout=20)
    if xml_text is None:
        logger.warning(f"拉取豆瓣 RSS 失败 {url}：{err}")
        return []
    items = _parse_rss_xml(xml_text)
    if not items:
        logger.warning(f"豆瓣 RSS 无有效条目：{url}")
        return []
    result: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_item(item, source)
        if normalized:
            result.append(normalized)
    return result


def _fetch_xml(url: str, *, proxy: bool, timeout: int) -> tuple[Optional[str], str]:
    """同步取回 RSS XML 文本；失败返回 ``(None, 原因)``。"""
    try:
        from app.sdk.network import RequestUtils
    except Exception as err:  # pragma: no cover - 宿主接口缺失
        return None, f"无法加载宿主 RequestUtils：{err}"
    proxies = None
    if proxy:
        try:
            from app.sdk.config import settings

            proxies = getattr(settings, "PROXY", None)
        except Exception:  # pragma: no cover - 读不到代理配置按直连
            proxies = None
    try:
        resp = RequestUtils(proxies=proxies, timeout=timeout).get_res(url)
    except Exception as err:
        return None, f"{type(err).__name__}: {err}"
    if resp is None:
        return None, "请求返回空值（网络不通或被拦截）"
    status = getattr(resp, "status_code", 0)
    if status != 200:
        return None, f"HTTP {status}"
    return (getattr(resp, "text", "") or ""), ""


def _parse_rss_xml(text: str) -> List[dict]:
    """标准库解析 RSS 2.0/RDF，产出与 RssHelper 兼容的条目 dict。"""
    import xml.etree.ElementTree as ET

    if not text or not text.strip().startswith("<"):
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    items: List[dict] = []
    for node in root.iter("item"):
        def _text(tag: str) -> str:
            child = node.find(tag)
            if child is not None and child.text:
                return child.text.strip()
            return ""

        items.append({
            "title": _text("title"),
            "link": _text("link"),
            "description": _text("description"),
            "pubdate": _text("pubDate"),
            "guid": _text("guid"),
        })
    return items
