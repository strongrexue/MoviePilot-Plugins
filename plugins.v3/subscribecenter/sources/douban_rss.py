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
from typing import Any, Dict, List, Optional, Sequence
from xml.etree import ElementTree

from ..core.constants import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, SOURCE_DOUBAN_RSS
from ..core.model import DiscoveredItem, is_special
from ..core.window import parse_date

#: 请求超时（秒）
TIMEOUT_SECONDS = 25

#: User-Agent —— RSSHub 本身不限，但保持可识别
USER_AGENT = "SubscribeCenter/0.7.0 (MoviePilot plugin; +https://github.com/strongrexue)"

#: 上映日期：``上映日期：2026-10-23(中国大陆)``
_RELEASE_DATE = re.compile(r"上映日期[：:]\s*(\d{4}-\d{2}-\d{2})")

#: 想看人数：``想看：27357``
_WANT_COUNT = re.compile(r"想看[：:]\s*([\d,]+)")

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
        items: List[DiscoveredItem] = []
        errors: List[str] = []

        for url in urls:
            try:
                text = await self._fetch_text(url)
            except Exception as exc:  # noqa: BLE001 - 单条 URL 失败不拖垮其余
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
                continue
            items.extend(self.parse(text, url, tz_name))

        if not items and errors:
            # 全部失败才算该源失败（部分成功时保留已拿到的内容）
            raise RuntimeError("；".join(errors))

        items.sort(key=lambda item: (item.release_date or "", item.title))
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
    def parse(text: str, url: str = "", tz_name: Optional[str] = None) -> List[DiscoveredItem]:
        """把 RSS 原文解析为发现条目。

        只保留**上映日期可解析**的条目 —— 没有日期就无法做窗口过滤，
        留着只会在后面的环节被当成「无法判断是否即将开播」再丢一次。
        """
        media_type = MEDIA_TYPE_TV if "/tv/" in url else MEDIA_TYPE_MOVIE
        source_label = _channel_title(text)

        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            raise RuntimeError(f"RSS 解析失败：{exc}") from exc

        items: List[DiscoveredItem] = []
        for node in root.iter("item"):
            title = (node.findtext("title") or "").strip()
            if not title:
                continue
            description = html.unescape(node.findtext("description") or "")
            link = (node.findtext("link") or "").strip()

            subject_id = _extract(_SUBJECT_ID, link) or _extract(_SUBJECT_ID, description)
            if not subject_id:
                continue

            release_text = _extract(_RELEASE_DATE, description)
            release = parse_date(release_text, tz_name)
            if release is None:
                continue

            want = _extract(_WANT_COUNT, description)
            genre = (node.findtext("category") or "").strip()

            items.append(
                DiscoveredItem(
                    source=SOURCE_DOUBAN_RSS,
                    source_id=subject_id,
                    title=title,
                    media_type=media_type,
                    year=str(release.year),
                    release_date=release.isoformat(),
                    # 豆瓣「想看数」量纲与 TMDB popularity 完全不同，
                    # 按接入契约不冒充 popularity，只留在 raw 里。
                    popularity=None,
                    rating=None,
                    native_ids={"douban": subject_id},
                    special=is_special(title),
                    raw={
                        "douban_id": subject_id,
                        "want": int(want.replace(",", "")) if want else None,
                        "genre": genre,
                        "feed": source_label,
                        "url": url,
                    },
                )
            )
        return items


# --------------------------------------------------------------------- 工具

def parse_sources(value: Any) -> List[str]:
    """把配置里的地址解析成 URL 列表（支持 list / 逗号 / 换行分隔）。"""
    if not value:
        return []
    if isinstance(value, str):
        raw = re.split(r"[\n,，]+", value)
    elif isinstance(value, (list, tuple)):
        raw = []
        for entry in value:
            raw.extend(re.split(r"[\n,，]+", str(entry)))
    else:
        return []
    urls: List[str] = []
    for piece in raw:
        url = piece.strip()
        if url and url not in urls:
            urls.append(url)
    return urls


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


__all__ = ["DoubanRssSource", "parse_sources", "TIMEOUT_SECONDS", "USER_AGENT"]
