# -*- coding: utf-8 -*-
"""画质画像与「洗版规则」逐维比较（1.13.32）。

设计（见仓库 ``.devtools/wash_rules_design.md``）：

- 七个维度按配置顺序**逐维字典序**比较，第一个分出胜负的维度直接决定结果，
  不再用加权总分（加权会把「4K WEB」和「1080p REMUX」这类问题变成玄学）。
- 每个维度的取值是一个**有序列表**：位置越靠前越优；``on=False`` 表示淘汰。
- 未出现在列表里的值按该维 ``unlisted`` 策略处理：
  ``deny``（默认，整条候选淘汰）/ ``bottom``（垫底纳入）/ ``top``（置顶纳入）。
- 解析不出来的值不参与该维比较（视为相同），由 TopN 兜底。
- 体积维度带 ±容差；容差内视为同大小。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- 常量

DIMENSIONS: Tuple[str, ...] = (
    "quality", "resolution", "effect", "audio", "codec", "ext", "size",
)

DIM_LABELS: Dict[str, str] = {
    "quality": "质量",
    "resolution": "分辨率",
    "effect": "色彩模式",
    "audio": "音频规格",
    "codec": "视频编码",
    "ext": "扩展名",
    "size": "文件体积",
}

# 各维默认取值顺序（越靠前越优）
DEFAULT_VALUES: Dict[str, Tuple[str, ...]] = {
    "quality": ("remux", "bluray", "webdl", "webrip", "hdtv", "cam", "ts"),
    "resolution": ("2160p", "1080p", "720p"),
    "effect": ("dv_hdr", "dv", "hdr10p", "hdr10", "hdr", "sdr"),
    "audio": ("atmos", "truehd", "dtshd", "dtsx", "dts", "eac3", "ac3", "flac", "aac"),
    "codec": ("av1", "hevc", "h264", "vp9", "other"),
    "ext": ("mkv", "mp4", "ts", "iso", "rmvb", "avi", "mov", "mpeg", "mpg", "wmv", "other"),
}

# 默认「淘汰」（打叉）的取值，其余默认保留
DEFAULT_OFF: Dict[str, Tuple[str, ...]] = {
    "quality": ("hdtv", "cam", "ts"),
    "ext": ("mov", "mpeg", "mpg", "wmv", "other"),
}

DEFAULT_UNLISTED = "deny"
UNLISTED_POLICIES = ("deny", "bottom", "top")

DEFAULT_SIZE: Dict[str, Any] = {"min_mb": 0, "max_gb": 0, "prefer": "desc"}
DEFAULT_TOLERANCE_PCT = 5
DEFAULT_TOP_N = 1
DEFAULT_SOURCES: Tuple[str, ...] = ("pushed", "library", "history")
SOURCE_LABELS = {"pushed": "已推送基线", "library": "媒体库已存在", "history": "下载历史（PT）"}

STATE_UPGRADE = "upgrade"
STATE_FLAT = "flat"
STATE_UNKNOWN = "unknown"

# --------------------------------------------------------------------------- 正则

_RESOLUTION_RE = re.compile(
    r"(?<![0-9a-z])(8k|2160p|4k|1080p|1080i|720p|576p|480p)(?![0-9a-z])", re.I
)
_QUALITY_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("remux", r"(?<![0-9a-z])remux(?![0-9a-z])"),
    ("bluray", r"(?<![0-9a-z])(bluray|blu-ray|bdrip|bdremux)(?![0-9a-z])"),
    ("webdl", r"(?<![0-9a-z])web[- .]?dl(?![0-9a-z])"),
    ("webrip", r"(?<![0-9a-z])web[- .]?rip(?![0-9a-z])"),
    ("hdtv", r"(?<![0-9a-z])hd[- .]?tv(?![0-9a-z])"),
    ("cam", r"(?<![0-9a-z])(hdcam|cam)(?![0-9a-z])"),
    ("ts", r"(?<![0-9a-z.])ts(?![0-9a-z])"),
)
_AUDIO_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("atmos", r"(?<![0-9a-z])atmos(?![0-9a-z])"),
    ("truehd", r"(?<![0-9a-z])true[- .]?hd(?![0-9a-z])"),
    ("dtshd", r"(?<![0-9a-z])dts[- .]?hd(?![0-9a-z])"),
    ("dtsx", r"(?<![0-9a-z])dts[- .]?x(?![0-9a-z])"),
    ("dts", r"(?<![0-9a-z])dts(?![0-9a-z])"),
    ("eac3", r"(?<![0-9a-z])e[- .]?ac[- .]?3(?![0-9a-z])"),
    ("ac3", r"(?<![0-9a-z])ac[- .]?3(?![0-9a-z])"),
    ("flac", r"(?<![0-9a-z])flac(?![0-9a-z])"),
    ("aac", r"(?<![0-9a-z])aac(?![0-9a-z])"),
)
_CODEC_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("av1", r"(?<![0-9a-z])av1(?![0-9a-z])"),
    ("hevc", r"(?<![0-9a-z])(hevc|h[ .]?265|x265)(?![0-9a-z])"),
    ("h264", r"(?<![0-9a-z])(h[ .]?264|x264|avc)(?![0-9a-z])"),
    ("vp9", r"(?<![0-9a-z])vp9(?![0-9a-z])"),
)
_EXT_RE = re.compile(
    r"\.(mkv|mp4|ts|iso|rmvb|avi|mov|mpeg|mpg|wmv)(?![0-9a-z])", re.I
)
_SIZE_RE = re.compile(r"(?<![0-9.])(\d+(?:\.\d+)?)\s*(gb|g|mb|m)(?![0-9a-z])", re.I)
_SDR_RE = re.compile(r"(?<![0-9a-z])sdr(?![0-9a-z])", re.I)
_DV_RE = re.compile(r"(?<![0-9a-z])(dovi|dolby[ .]?vision|dv)(?![0-9a-z])", re.I)
_HDR10P_RE = re.compile(r"hdr10\+|hdr10p", re.I)
_HDR10_RE = re.compile(r"hdr10(?![+p0-9a-z])", re.I)
_HDR_RE = re.compile(r"(?<![0-9a-z])hdr(?![0-9a-z+])", re.I)


# --------------------------------------------------------------------------- 工具


def _as_dict(raw: Any) -> Dict[str, Any]:
    """配置可能是 dict、JSON 字符串或空值，统一成 dict。"""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _coerce_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _coerce_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


# --------------------------------------------------------------------------- 配置


def default_rules() -> Dict[str, Any]:
    """默认洗版规则（与效果图 v9 一致）。"""
    return normalize_rules({})


def normalize_rules(raw: Any) -> Dict[str, Any]:
    """把外部配置归一成内部结构，任何脏数据都退回默认值。"""
    data = _as_dict(raw)

    # ① 维度顺序：质量锁定第一，其余按用户顺序，缺的补在末尾
    raw_order = data.get("order")
    order: List[str] = []
    if isinstance(raw_order, (list, tuple)):
        for item in raw_order:
            name = str(item or "").strip()
            if name in DIMENSIONS and name not in order:
                order.append(name)
    order = ["quality"] + [dim for dim in order if dim != "quality"]
    for dim in DIMENSIONS:
        if dim not in order:
            order.append(dim)

    # ② 各维取值列表（有序）+ 保留/淘汰
    raw_values = data.get("values")
    raw_values = raw_values if isinstance(raw_values, dict) else {}
    values: Dict[str, List[Dict[str, Any]]] = {}
    for dim in DIMENSIONS[:-1]:
        fallback = [
            {"v": token, "on": token not in DEFAULT_OFF.get(dim, ())}
            for token in DEFAULT_VALUES[dim]
        ]
        entries = raw_values.get(dim)
        if not isinstance(entries, (list, tuple)) or not entries:
            values[dim] = fallback
            continue
        cleaned: List[Dict[str, Any]] = []
        seen = set()
        for entry in entries:
            if isinstance(entry, dict):
                token = str(entry.get("v") or "").strip()
                on = bool(entry.get("on", True))
            else:
                token, on = str(entry or "").strip(), True
            if not token or token in seen:
                continue
            seen.add(token)
            cleaned.append({"v": token, "on": on})
        values[dim] = cleaned or fallback

    # ③ 未列出值的策略
    raw_unlisted = data.get("unlisted")
    raw_unlisted = raw_unlisted if isinstance(raw_unlisted, dict) else {}
    unlisted: Dict[str, str] = {}
    for dim in DIMENSIONS[:-1]:
        policy = str(raw_unlisted.get(dim) or DEFAULT_UNLISTED).strip().lower()
        unlisted[dim] = policy if policy in UNLISTED_POLICIES else DEFAULT_UNLISTED

    # ④ 体积维度
    raw_size = data.get("size")
    raw_size = raw_size if isinstance(raw_size, dict) else {}
    prefer = str(raw_size.get("prefer") or DEFAULT_SIZE["prefer"]).strip().lower()
    size = {
        "min_mb": _coerce_int(raw_size.get("min_mb"), 0, 0, 10 ** 7),
        "max_gb": _coerce_int(raw_size.get("max_gb"), 0, 0, 10 ** 6),
        "prefer": prefer if prefer in ("desc", "asc", "none") else "desc",
    }

    # ⑤ 比对来源
    raw_sources = data.get("compare_sources")
    sources: List[str] = []
    if isinstance(raw_sources, (list, tuple)):
        for item in raw_sources:
            name = str(item or "").strip().lower()
            if name in DEFAULT_SOURCES and name not in sources:
                sources.append(name)
    if not sources:
        sources = list(DEFAULT_SOURCES)

    return {
        "order": order,
        "values": values,
        "unlisted": unlisted,
        "size": size,
        "size_tolerance_pct": _coerce_float(
            data.get("size_tolerance_pct"), DEFAULT_TOLERANCE_PCT, 0.0, 50.0
        ),
        "top_n": _coerce_int(data.get("top_n"), DEFAULT_TOP_N, 0, 50),
        "compare_sources": sources,
    }


# --------------------------------------------------------------------------- 解析


def _first_match(patterns: Tuple[Tuple[str, str], ...], text: str) -> Optional[str]:
    for token, pattern in patterns:
        if re.search(pattern, text, re.I):
            return token
    return None


def _effect_of(text: str) -> Optional[str]:
    has_dv = bool(_DV_RE.search(text))
    has_hdr10p = bool(_HDR10P_RE.search(text))
    has_hdr10 = bool(_HDR10_RE.search(text))
    has_hdr = has_hdr10p or has_hdr10 or bool(_HDR_RE.search(text))
    if has_dv and has_hdr:
        return "dv_hdr"
    if has_dv:
        return "dv"
    if has_hdr10p:
        return "hdr10p"
    if has_hdr10:
        return "hdr10"
    if has_hdr:
        return "hdr"
    if _SDR_RE.search(text):
        return "sdr"
    return None


def _size_mb_of(text: str) -> Optional[float]:
    best: Optional[float] = None
    for value, unit in _SIZE_RE.findall(text):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        mb = number * 1024.0 if unit.lower() in ("gb", "g") else number
        if best is None or mb > best:
            best = mb
    return best


def parse_quality(text: str) -> Dict[str, Any]:
    """从发布名/正文里解析七维画像（纯正则，便宜）。"""
    raw = str(text or "")
    resolution: Optional[str] = None
    match = _RESOLUTION_RE.search(raw)
    if match:
        token = match.group(1).lower()
        resolution = {"4k": "2160p", "8k": "2160p"}.get(token, token)
    ext_match = _EXT_RE.search(raw)
    profile: Dict[str, Any] = {
        "quality": _first_match(_QUALITY_PATTERNS, raw),
        "resolution": resolution,
        "effect": _effect_of(raw),
        "audio": _first_match(_AUDIO_PATTERNS, raw),
        "codec": _first_match(_CODEC_PATTERNS, raw),
        "ext": ext_match.group(1).lower() if ext_match else None,
        "size_mb": _size_mb_of(raw),
    }
    profile["known"] = bool(profile["resolution"] or profile["quality"])
    return profile


# --------------------------------------------------------------------------- 比较


def _values_map(rules: Dict[str, Any], dim: str) -> Tuple[List[str], Dict[str, bool]]:
    entries = rules.get("values", {}).get(dim) or []
    ordered: List[str] = []
    enabled: Dict[str, bool] = {}
    for entry in entries:
        token = str(entry.get("v") or "")
        if not token:
            continue
        ordered.append(token)
        enabled[token] = bool(entry.get("on", True))
    return ordered, enabled


def rank_of(dim: str, token: Optional[str], rules: Dict[str, Any]) -> Optional[int]:
    """取值在维度内的名次：0 = 最优，越小越好；None = 不参与比较。"""
    if not token:
        return None
    ordered, _enabled = _values_map(rules, dim)
    if token in ordered:
        return ordered.index(token)
    policy = rules.get("unlisted", {}).get(dim, DEFAULT_UNLISTED)
    if policy == "bottom":
        return len(ordered)
    if policy == "top":
        return -1
    return None


def filter_profile(profile: Dict[str, Any], rules: Dict[str, Any]) -> Tuple[bool, str]:
    """准入过滤：被淘汰的取值、未列出且策略为 deny 的取值、体积越界。

    :returns: ``(是否保留, 淘汰原因)``
    """
    for dim in rules.get("order", []):
        if dim == "size":
            continue
        token = profile.get(dim)
        if not token:
            continue
        ordered, enabled = _values_map(rules, dim)
        label = DIM_LABELS.get(dim, dim)
        if token in ordered:
            if not enabled.get(token, True):
                return False, f"{label}「{token}」已淘汰"
            continue
        policy = rules.get("unlisted", {}).get(dim, DEFAULT_UNLISTED)
        if policy == "deny":
            return False, f"{label}「{token}」不在白名单"
    size_cfg = rules.get("size") or {}
    size_mb = profile.get("size_mb")
    if size_mb:
        min_mb = int(size_cfg.get("min_mb") or 0)
        max_gb = int(size_cfg.get("max_gb") or 0)
        if min_mb and size_mb < min_mb:
            return False, f"体积小于 {min_mb} MB"
        if max_gb and size_mb > max_gb * 1024:
            return False, f"体积大于 {max_gb} GB"
    return True, ""


def sort_key(profile: Dict[str, Any], rules: Dict[str, Any]) -> Tuple:
    """TopN 用的排序键：越小越优（未知值排在最后）。"""
    key: List[float] = []
    prefer = (rules.get("size") or {}).get("prefer") or "desc"
    for dim in rules.get("order", []):
        if dim == "size":
            size_mb = profile.get("size_mb")
            if size_mb is None:
                key.append(0.0)
            elif prefer == "asc":
                key.append(float(size_mb))
            else:
                key.append(-float(size_mb))
            continue
        rank = rank_of(dim, profile.get(dim), rules)
        key.append(float(rank) if rank is not None else 10 ** 6)
    return tuple(key)


def _size_close(base_mb: Any, cand_mb: Any, pct: float) -> bool:
    if not base_mb or not cand_mb:
        return False
    base = float(base_mb)
    cand = float(cand_mb)
    return abs(base - cand) <= max(base, cand) * (float(pct) / 100.0)


def compare(
    base: Optional[Dict[str, Any]],
    candidate: Optional[Dict[str, Any]],
    rules: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """基线 vs 候选的逐维比较。

    :returns: ``(STATE_UPGRADE|STATE_FLAT|STATE_UNKNOWN, 原因)``
    """
    rules = rules or default_rules()
    if not candidate or not candidate.get("known"):
        return STATE_UNKNOWN, "画质无法解析"
    if not base:
        return STATE_UPGRADE, "首次推送（无基线）"
    tolerance = float(rules.get("size_tolerance_pct") or 0)

    # 「同质量 + 同分辨率 + 同体积」直接判持平（效果图里那条规则）
    if (
        candidate.get("quality")
        and candidate.get("quality") == base.get("quality")
        and candidate.get("resolution")
        and candidate.get("resolution") == base.get("resolution")
        and _size_close(base.get("size_mb"), candidate.get("size_mb"), tolerance)
    ):
        return STATE_FLAT, "同质量同分辨率同体积（±{:g}% 容差）".format(tolerance)

    prefer = (rules.get("size") or {}).get("prefer") or "desc"
    for dim in rules.get("order", []):
        label = DIM_LABELS.get(dim, dim)
        if dim == "size":
            base_mb = base.get("size_mb")
            cand_mb = candidate.get("size_mb")
            if not base_mb or not cand_mb:
                continue
            if _size_close(base_mb, cand_mb, tolerance):
                continue
            if prefer == "none":
                continue
            bigger = float(cand_mb) > float(base_mb)
            if (prefer == "desc" and bigger) or (prefer == "asc" and not bigger):
                return STATE_UPGRADE, f"{label}更优（{float(cand_mb):.0f}MB > {float(base_mb):.0f}MB）"
            return STATE_FLAT, f"{label}更小（{float(cand_mb):.0f}MB < {float(base_mb):.0f}MB）"
        base_rank = rank_of(dim, base.get(dim), rules)
        cand_rank = rank_of(dim, candidate.get(dim), rules)
        if base_rank is None or cand_rank is None:
            continue
        if cand_rank < base_rank:
            return STATE_UPGRADE, f"{label}更优（{candidate.get(dim)} > {base.get(dim)}）"
        if cand_rank > base_rank:
            return STATE_FLAT, f"{label}低于基线（{candidate.get(dim)} < {base.get(dim)}）"
    return STATE_FLAT, "逐维相同"


def describe(profile: Optional[Dict[str, Any]]) -> str:
    """把画像压成一行中文描述（通知/日志用）。"""
    if not profile:
        return "画质未知"
    parts: List[str] = []
    labels = (
        ("quality", "质量"), ("resolution", "分辨率"), ("effect", "色彩"),
        ("audio", "音频"), ("codec", "编码"), ("ext", "格式"),
    )
    for key, label in labels:
        value = profile.get(key)
        if value:
            parts.append(f"{label} {value}")
    size_mb = profile.get("size_mb")
    if size_mb:
        parts.append(f"{float(size_mb) / 1024.0:.1f}GB" if size_mb >= 1024
                     else f"{float(size_mb):.0f}MB")
    return "、".join(parts) if parts else "画质未知"


def baseline_key(
    title: str,
    year: Any,
    season: Any = None,
    episode: Any = None,
    episode_end: Any = None,
) -> str:
    """基线键：标题 + 年 + 季 + 集区间（与 1.13.27 完全一致，老数据可直接读）。"""
    def _norm(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text

    return "|".join([
        _norm(title),
        _norm(year),
        _norm(season),
        _norm(episode),
        _norm(episode_end),
    ])
