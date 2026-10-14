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

import re
from typing import Any, List, Optional

from app.sdk.logging import logger

try:  # 宿主识别引擎：缺失时整层降级
    from app.sdk.media import MetaVideo

    META_AVAILABLE = True
except Exception:  # pragma: no cover - 无宿主环境的降级分支
    MetaVideo = None  # type: ignore[assignment]
    META_AVAILABLE = False

# 链接行特征：命中则不作为标题候选（MetaVideo 会把 URL 硬解析成
# 《Https: 115 Com ...》这类假标题，真机已踩过）
_URL_LINE_RE = re.compile(r"https?://|magnet:\?|ed2k://", re.IGNORECASE)
# 识别结果防呆：名称里带链接特征或超长，基本可断定是误解析。
# 注意不能要求 "://"：URL 被 MetaVideo 拆词后的垃圾名形如 "Https: 115 Com ..."（无 //）。
_BAD_NAME_RE = re.compile(r"https?|www\.", re.IGNORECASE)
_MAX_NAME_LENGTH = 100

# 资源频道播报的类别前缀（"📺 电视剧：名称 (年份) S01E01"）——
# 显式类别比 MetaVideo 的猜测更可靠，优先采用
_CATEGORY_HINT_RE = re.compile(r"^(电视剧|电影|动漫|动画|综艺|纪录片|剧集|短剧)\s*[：:]\s*(.+)$")
_CATEGORY_HINT_TYPE = {
    "电视剧": "tv", "动漫": "tv", "动画": "tv", "综艺": "tv",
    "纪录片": "tv", "剧集": "tv", "短剧": "tv", "电影": "movie",
}
# 播报字段行（"转存入库: S01E01" / "TMDB ID: 295002" 等），不作标题候选，
# 否则上一行识别失败时会把"转存入库"这类字段名当成片名
_FIELD_LABEL_RE = re.compile(
    r"^(?:转存入库|转存|TMDB|豆瓣|IMDb|IMDB|评分|题材|地区|质量|大小|触发|频道|链接"
    r"|剧情简介|简介|状态|发布|尺寸|编码|音轨|字幕|收录|归档)\s*[：:]",
    re.IGNORECASE,
)
# 行首 emoji/符号噪声（"📺 电视剧：..." → "电视剧：..."）。
# \w 已覆盖中英文与数字，因此只保留全角括号/方括号等标题常用起手字符
_LEAD_NOISE_RE = re.compile(r"^[^\w（(【\[]+")

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


def _is_bad_name(name: str) -> bool:
    """识别出的名称是否像误解析（含链接特征或超长）。"""
    text = str(name or "")
    return bool(_BAD_NAME_RE.search(text)) or len(text) > _MAX_NAME_LENGTH


def _recognize_line(line: str, subtitle: Optional[str]) -> Optional[dict]:
    """对单行做 MetaVideo 识别；得到名称才算成功。"""
    # 链接行不作标题候选：纯链接消息（或链接在首行的消息）不该被解析出假标题
    if _URL_LINE_RE.search(line):
        return None
    # 去掉行首 emoji/符号噪声（"📺 电视剧：..." → "电视剧：..."）
    cleaned = _LEAD_NOISE_RE.sub("", line).strip()
    if not cleaned:
        return None
    # 类别前缀（"电视剧：名称 (年份) S01E01"）：提取显式类型提示 + 纯标题行
    type_hint = ""
    category = _CATEGORY_HINT_RE.match(cleaned)
    if category:
        type_hint = _CATEGORY_HINT_TYPE.get(category.group(1), "")
        cleaned = category.group(2).strip()
        if not cleaned:
            return None
    # 播报字段行（"转存入库: S01E01" 等）不是片名，跳过
    if _FIELD_LABEL_RE.match(cleaned):
        return None
    try:
        meta = MetaVideo(cleaned, subtitle)
    except Exception as err:  # pragma: no cover - 识别引擎内部异常按未识别处理
        logger.debug(f"MetaVideo 识别异常（忽略）：{err}")
        return None
    name = str(getattr(meta, "name", "") or "").strip()
    if not name or _is_bad_name(name):
        return None
    season = _first_int(getattr(meta, "begin_season", None))
    episode = _first_int(getattr(meta, "begin_episode", None))
    episode_end = _first_int(getattr(meta, "end_episode", None))
    media_type = _normalize_media_type(getattr(meta, "type", None))
    # 显式类别提示优先（播报格式的"电视剧：/电影："是频道给出的确定分类）
    if type_hint:
        media_type = type_hint
    # 是剧集却没识别出季时按 S01 处理（与 season_seq 的语义一致）
    if media_type == "tv" and season is None:
        season = 1
    return {
        "title": name,
        "year": str(getattr(meta, "year", "") or "").strip(),
        "season": season,
        "episode": episode,
        "episode_end": episode_end if (episode_end is not None and episode_end >= (episode or 0)) else None,
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


def label_for(text: Any, fallback: str = "") -> str:
    """把原始标题 / 文件名转成通知用媒体名（如「你行！你上！ (2025)」。

    用于链接转存回执这类「只有原始资源名、没有订阅上下文」的场景
    （1.7.6）：识别成功 → 与缓存回搜 / 115 转存通知同款的
    「片名 (年份) SxxExx」拼装；识别失败或原文为空 → 退回 fallback。

    真机依据：用户自建分享的 share_title 自带 ``{tmdbid=xxx}`` / ``(DoVi)``
    尾巴（MP 规范化命名），必须过识别器清洗后才适合进回执。

    拼装逻辑与 ``modules.cache._media_label`` /
    ``core.pipeline.MessagePipeline._media_label`` 一致——三处同款拼法，
    后续重构时收拢成单一实现即可，调用方不变。
    """
    raw = str(text or "").strip()
    if not raw:
        return str(fallback or "").strip()
    meta = recognize(raw)
    if not meta:
        return raw
    title = str(meta.get("title") or "").strip()
    if not title:
        return raw
    parts: List[str] = [title]
    year = str(meta.get("year") or "").strip()
    if year:
        parts.append(f"({year})")
    season = meta.get("season")
    episode = meta.get("episode")
    episode_end = meta.get("episode_end")
    if season:
        seg = f"S{int(season):02d}"
        if episode:
            seg += f"E{int(episode):02d}"
            if episode_end and int(episode_end) != int(episode):
                seg += f"-E{int(episode_end):02d}"
        parts.append(seg)
    return " ".join(parts)
