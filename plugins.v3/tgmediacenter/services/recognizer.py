"""标题识别服务：包装宿主识别引擎 ``MetaVideo``。

设计要点
--------
1. **不写正则、不接 AI**：识别一律交给宿主 ``app.sdk.media.MetaVideo``
   （MP 生产环境识别种子名用的同一套引擎），输出 name/year/season/episode 等。
2. **依赖可选**：宿主缺失（如本地测试环境）时整层降级为"不可用"，
   ``recognize()`` 返回 None，由上层按"无法识别"处理——插件其余能力不受影响。
3. **净化先行**：TG 资源消息常混入推广行，先按行过滤明显广告，再取首发名行识别；
   首行识别不出名称时按顺序尝试后续行（资源名不总在第一行）。
"""
from __future__ import annotations

from typing import Any, Optional

from app.sdk.logging import logger

try:  # 宿主识别引擎：缺失时整层降级
    from app.sdk.media import MetaVideo

    META_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境的降级分支
    MetaVideo = None  # type: ignore[assignment]
    META_AVAILABLE = False

# 明显广告/推广行特征（命中即整行丢弃）。宁少勿多：误杀资源名比漏过滤更糟。
_AD_LINE_MARKERS = (
    "加入群组", "加入频道", "加入我们", "订阅频道", "订阅我们", "关注我们",
    "商务合作", "广告合作", "投稿", "推广", "点击下载", "下载app", "下载 app",
    "注册即送", "免费领取", "破解版", "官方群", "备用群", "防失联",
)
# 控制字符与零宽字符（TG 消息里常见，会干扰识别）。
# 注意：\t(0x09) 转空格、\n(0x0A)/\r(0x0D) 必须保留——按行过滤广告依赖换行，
# 早年把 0x00-0x1F 全删会把整条消息拼成一行，含广告词时整条被误杀。
_CONTROL_CHARS = {
    code: None
    for code in list(range(0x00, 0x20)) + [0x7F, 0x200B, 0x200C, 0x200D, 0xFEFF]
    if code not in (0x09, 0x0A, 0x0D)
}
_CONTROL_CHARS[0x09] = " "


def meta_available() -> bool:
    """宿主识别引擎是否可用。"""
    return META_AVAILABLE


def purify_text(text: Any) -> str:
    """净化消息文本：去控制字符、丢广告行、压缩空行。"""
    raw = str(text or "")
    if not raw.strip():
        return ""
    cleaned = raw.translate(_CONTROL_CHARS)
    lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(marker in stripped or marker in lowered for marker in _AD_LINE_MARKERS):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _normalize_media_type(value: Any) -> str:
    """把宿主 MediaType 归一为 tv / movie（值为中文字符串，如 电视剧/电影）。"""
    raw = getattr(value, "value", value)
    text = str(raw or "").strip().lower()
    if "剧" in text or text == "tv":
        return "tv"
    if "电影" in text or text == "movie":
        return "movie"
    return ""


def _first_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _recognize_line(line: str, subtitle: Optional[str]) -> Optional[dict]:
    """对单行做 MetaVideo 识别；得到名称才算成功。"""
    try:
        meta = MetaVideo(line, subtitle)
    except Exception as err:  # pragma: no cover - 识别引擎内部异常按未识别处理
        logger.debug(f"MetaVideo 识别异常（忽略）：{err}")
        return None
    name = str(getattr(meta, "name", "") or "").strip()
    if not name:
        return None
    season = _first_int(getattr(meta, "begin_season", None))
    episode = _first_int(getattr(meta, "begin_episode", None))
    media_type = _normalize_media_type(getattr(meta, "type", None))
    # 是剧集却没识别出季时按 S01 处理（与 season_seq 的语义一致）
    if media_type == "tv" and season is None:
        season = 1
    return {
        "title": name,
        "year": str(getattr(meta, "year", "") or "").strip(),
        "season": season,
        "episode": episode,
        "media_type": media_type,
        "resource_type": str(getattr(meta, "resource_type", "") or "").strip(),
        "resource_pix": str(getattr(meta, "resource_pix", "") or "").strip(),
        "video_encode": str(getattr(meta, "video_encode", "") or "").strip(),
        "original": line,
    }


def recognize(text: Any) -> Optional[dict]:
    """识别消息文本中的媒体信息。

    :returns: ``{"title", "year", "season", "episode", "media_type", ...}``；
        无法识别（或宿主引擎不可用）时返回 None。
    """
    if not META_AVAILABLE:
        return None
    cleaned = purify_text(text)
    if not cleaned:
        return None
    lines = [line for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return None
    # 首发名行识别，其余行进 subtitle（季集信息常在副标题）
    for index, line in enumerate(lines[:6]):
        subtitle = "\n".join(lines[index + 1:index + 4]) or None
        result = _recognize_line(line, subtitle)
        if result:
            return result
    return None
