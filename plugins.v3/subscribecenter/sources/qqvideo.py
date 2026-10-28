"""腾讯视频「即将上线」发现源（自建抓包，2026-10 实测）。

数据来自腾讯视频 pc 频道页「即将上线」标签背后的私有接口：

``POST https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getCard``

**为什么能把这三份 payload 写死**：该接口不是公开 API，没有文档，
每个频道（电视剧 / 电影 / 综艺）的请求体里的
``page_params.tab_mvl_sub_mod_id``、``flip_info.page_module_id``、
``flip_info.flip_params.source_key`` 三者各不相同，缺一个就返回空列表。
这三份 payload 是从浏览器真实请求里原样复制下来的，只翻页时改
``page_context.page_index``。

.. important:: **只有前几条带日期**
   真机实测（2026-10-28）：电视剧 36 条里只有 2 条带 ``online_time``
   （「2026-10-29 12:00:00」），其余 34 条是「已上架待播」但没有定档日。
   带日期的按 :attr:`DiscoveredItem.release_date` 走时间窗口；不带日期的
   标 :attr:`DiscoveredItem.date_unknown`，交给身份解析阶段用
   「TMDB 是否还有未播集」判定（剧集可放行，电影会被跳过）。
   —— 这不是缺陷，而是平台自己的信息粒度：连腾讯也不知道哪天播。

``order_person_count`` 是「预约人数」，这是平台侧唯一的预热强度信号，
映射成 :attr:`DiscoveredItem.popularity` 供「最低关注度」筛选复用。
"""
import json
import re
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from ..core.constants import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, SOURCE_QQ_VIDEO
from ..core.model import DiscoveredItem

#: 单次请求超时（秒）
TIMEOUT_SECONDS = 25

#: 必须伪装成浏览器 + 带 Referer，否则 403
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

#: 接口地址（appid / 平台版本写死在 query 里）
ENDPOINT = (
    "https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getCard"
    "?video_appid=3000010&vversion_platform=2"
)

#: 频道定义：配置里的键 -> (展示名, 媒体类型, payload 键)
CHANNELS = (
    ("tv", "电视剧", MEDIA_TYPE_TV),
    ("movie", "电影", MEDIA_TYPE_MOVIE),
    ("variety", "综艺", MEDIA_TYPE_TV),
)

#: 三个频道各自的请求体（实测原样，翻页只改 page_index）
_PAYLOADS: Dict[str, str] = {
    'tv': r'''{"page_params":{"tab_mvl_sub_mod_id":"792ac_19e77Sub_107","tab_name":"即将上线","tab_type":"coming_soon","page_id":"scms_shake","page_type":"scms_shake","source_key":"","tag_id":"","tag_type":"","new_mark_label_enabled":"1"},"page_context":{"page_index":"1"},"flip_info":{"page_strategy_id":"","page_module_id":"792ac_19e77","module_strategy_id":{},"sub_module_id":"20251106065177","flip_params":{"folding_screen_show_num":"","is_mvl":"1","mvl_strategy_info":"{\"default_strategy_id\":\"06755800b45b49238582a6fa1ad0f5c5\",\"default_version\":\"8633\",\"hit_page_uuid\":\"b5080d97dc694a5fb50eb9e7c99326ac\",\"hit_tab_info\":null,\"gray_status_info\":null,\"bypass_to_un_exp_id\":\"\"}","mvl_sub_mod_id":"20251106065177","pad_post_show_num":"","pad_pro_post_show_num":"","pad_pro_small_hor_pic_display_num":"","pad_small_hor_pic_display_num":"","page_id":"scms_shake","page_num":"0","page_type":"scms_shake","post_show_num":"","shake_size":"","small_hor_pic_display_num":"","source_key":"100113","un_policy_id":"06755800b45b49238582a6fa1ad0f5c5","un_strategy_id":"06755800b45b49238582a6fa1ad0f5c5"},"relace_children_key":[]}}''',
    'movie': r'''{"page_params":{"tab_mvl_sub_mod_id":"792ac_195f1Sub_19e","tab_name":"即将上线","tab_type":"coming_soon","page_id":"scms_shake","page_type":"scms_shake","source_key":"","tag_id":"","tag_type":"","new_mark_label_enabled":"1"},"page_context":{"page_index":"1"},"flip_info":{"page_strategy_id":"","page_module_id":"792ac_195f1","module_strategy_id":{},"sub_module_id":"20190621006455","flip_params":{"folding_screen_show_num":"","is_mvl":"1","mvl_strategy_info":"{\"default_strategy_id\":\"9ba3a89c1dd54edc98c5cb4a57941754\",\"default_version\":\"10566\",\"hit_page_uuid\":\"0a60eb3ad0744d409495597de31328cd\",\"hit_tab_info\":null,\"gray_status_info\":null,\"bypass_to_un_exp_id\":\"\"}","mvl_sub_mod_id":"20190621006455","pad_post_show_num":"","pad_pro_post_show_num":"","pad_pro_small_hor_pic_display_num":"","pad_small_hor_pic_display_num":"","page_id":"scms_shake","page_num":"0","page_type":"scms_shake","post_show_num":"","shake_size":"","small_hor_pic_display_num":"","source_key":"100173","un_policy_id":"9ba3a89c1dd54edc98c5cb4a57941754","un_strategy_id":"9ba3a89c1dd54edc98c5cb4a57941754"},"relace_children_key":[]}}''',
    'variety': r'''{"page_params":{"need_banner_auto_fill":"0","tab_mvl_sub_mod_id":"792ac_13f49Sub_15f","tab_name":"即将上线","tab_type":"coming_soon","page_id":"scms_shake","page_type":"scms_shake","source_key":"","tag_id":"","tag_type":"","new_mark_label_enabled":"1"},"page_context":{"page_index":"1"},"flip_info":{"page_strategy_id":"","page_module_id":"792ac_13f49","module_strategy_id":{},"sub_module_id":"","flip_params":{"folding_screen_show_num":"","is_mvl":"1","mvl_strategy_info":"{\"default_strategy_id\":\"d7c626ece2604dc4b5ae7796cd239894\",\"default_version\":\"12464\",\"hit_page_uuid\":\"ad580fdd5e394e11a9be0e45dfbdc913\",\"hit_tab_info\":null,\"gray_status_info\":null,\"bypass_to_un_exp_id\":\"\"}","pad_post_show_num":"","pad_pro_post_show_num":"","pad_pro_small_hor_pic_display_num":"","pad_small_hor_pic_display_num":"","page_id":"scms_shake","page_num":"0","page_type":"scms_shake","post_show_num":"","shake_size":"","small_hor_pic_display_num":"","source_key":"100109","un_policy_id":"d7c626ece2604dc4b5ae7796cd239894","un_strategy_id":"d7c626ece2604dc4b5ae7796cd239894"},"relace_children_key":[]}}''',
}


class QqVideoSource:
    """腾讯视频「即将上线」源（电视剧 / 电影 / 综艺三频道）。"""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    @property
    def name(self) -> str:
        """源标识。"""
        return SOURCE_QQ_VIDEO

    async def fetch(self, config: Dict[str, Any]) -> List[DiscoveredItem]:
        """按频道拉取「即将上线」列表。"""
        import aiohttp

        channels = _channels(config.get("qq_video_channels"))
        if not channels:
            raise RuntimeError("腾讯视频：三个频道都没有勾选，抓不到任何内容")

        limit = _int(config.get("qq_video_max_items"), 40)
        items: List[DiscoveredItem] = []
        seen: set = set()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Referer": "https://v.qq.com/",
            "Origin": "https://v.qq.com",
        }
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for key, label, media_type in CHANNELS:
                if key not in channels:
                    continue
                try:
                    payload = json.loads(_PAYLOADS[key])
                    async with session.post(ENDPOINT, json=payload) as resp:
                        if resp.status != 200:
                            logger.warning(
                                f"[SubscribeCenter] 腾讯视频（{label}）HTTP {resp.status}"
                            )
                            continue
                        data = await resp.json(content_type=None)
                except Exception as err:  # noqa: BLE001 - 单频道失败不拖垮其他频道
                    logger.warning(
                        f"[SubscribeCenter] 腾讯视频（{label}）取数失败：{err}"
                    )
                    continue

                cards = _cards(data)
                if not cards:
                    logger.info(
                        f"[SubscribeCenter] 腾讯视频（{label}）：接口返回 0 条"
                    )
                    continue
                added = 0
                for card in cards:
                    item = _to_item(card, media_type)
                    if item is None or item.source_id in seen:
                        continue
                    seen.add(item.source_id)
                    items.append(item)
                    added += 1
                    if added >= limit:
                        break
                logger.info(
                    f"[SubscribeCenter] 腾讯视频（{label}）："
                    f"取到 {added} 条（接口共 {len(cards)} 条）"
                )

        if not items:
            raise RuntimeError(
                "腾讯视频：接口返回空数据。可能接口又改了参数，"
                "可以在「平台首播」分区先关掉这个源"
            )
        return items


def _cards(data: Any) -> List[Dict[str, Any]]:
    """从多层嵌套的响应里挖出卡片列表（结构变了就返回空）。"""
    try:
        card = data["data"]["card"]
        cards = card["children_list"]["list"]["cards"]
    except (KeyError, TypeError):
        return []
    return [c for c in cards if isinstance(c, dict)]


def _to_item(card: Dict[str, Any], media_type: str) -> Optional[DiscoveredItem]:
    """把一张卡片转成 :class:`DiscoveredItem`。"""
    params = card.get("params") or {}
    title = str(params.get("title") or "").strip()
    cid = str(params.get("cid") or "").strip()
    if not title or not cid:
        return None
    # 「会员版」「先导片」这类尾巴会干扰 TMDB 解析，去掉括号内容
    clean = _strip_suffix(title)
    online = str(params.get("online_time") or "").strip()
    release_date = online[:10] if len(online) >= 10 else None
    wants = _int(params.get("order_person_count"), 0)
    return DiscoveredItem(
        source=SOURCE_QQ_VIDEO,
        source_id=f"{media_type}:{cid}",
        title=clean,
        media_type=media_type,
        year=release_date[:4] if release_date else None,
        release_date=release_date,
        popularity=float(wants) if wants > 0 else None,
        date_unknown=release_date is None,
    )


#: 标题尾部噪音：平台会把「（会员版）」「· 花絮」这类挂上去
_NOISE = ("会员版", "先导片", "预告片", "花絮", "特辑", "纯享版", "加更版")

#: 括号包起来的噪音，例如「庆余年（会员版）」
_BRACKET_NOISE = re.compile(
    r"[\uff08(\u3010\[]\s*(?:" + "|".join(_NOISE) + r")\s*[\uff09)\u3011\]]\s*$"
)


def _strip_suffix(title: str) -> str:
    """去掉标题里的装饰性后缀，保留主标题。"""
    text = _BRACKET_NOISE.sub("", title).strip()
    for noise in _NOISE:
        if text.endswith(noise):
            text = text[: -len(noise)].rstrip(" ·-（(【[")
    # 「兰香如故·花胜秋宴」这类「主标题·副标题」：TMDB 只有主标题
    if "·" in text:
        head = text.split("·", 1)[0].strip()
        if len(head) >= 2:
            return head
    return text


def _channels(value: Any) -> List[str]:
    """把配置里的频道列表规范成字符串列表。"""
    if value is None or value == "":
        return ["tv", "movie", "variety"]
    raw = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    return [str(v).strip() for v in raw if str(v).strip()]


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
