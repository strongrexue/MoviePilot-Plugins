"""洗版质量对比服务（1.13.27）：解析资源画质，判断「是否真的升级」。

背景
----
1.13.24 的洗版回搜是「命中即推」——频道里只要有链接、这条消息还没推过，就入队。
结果是一堆 1080p / 低码率 / 同片源的重复版本灌满推送，用户没法挑。

这里提供与 ``media_automator`` 洗版同构的**两层对比**（不依赖媒体库返回画质，
本插件只拿得到标题与正文，因此基线取自「该订阅历次已推送的最优画质」）：

1. **第一层（硬门槛，不可配）**：分辨率、片源不得倒退。
   1080p 的候选永远不会盖掉已经推过的 2160p。
2. **第二层（加权总分）**：分辨率 / 片源 / 编码 / 特效 / 音轨 按权重求和，
   总分必须**严格高于**基线才算升级。

无法解析画质的候选（标题里没写分辨率）不参与比较，交给「每季集区间取最优
TopN」兜底——既不会误杀，也不会无限推。

设计要点
--------
- **纯正则、无依赖**：不调用宿主 ``MetaVideo``，本地测试与宿主缺失时行为一致。
- **可解释**：``compare()`` 返回 ``(state, reason)``，状态进日志与推送说明。
- **幂等**：基线是普通 dict，序列化进插件数据，重启不丢。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Tuple

# 画质维度阶梯：数值越大越好。键是匹配用的字面量（已小写）。
RESOLUTION_LADDER: Dict[str, int] = {
    "8k": 7, "2160p": 6, "4k": 6, "1080p": 5, "1080i": 4,
    "720p": 3, "576p": 2, "480p": 1,
}
SOURCE_LADDER: Dict[str, int] = {
    "remux": 8, "bluray": 7, "bdrip": 6, "webdl": 5, "webrip": 4,
    "hdtvrip": 3, "hdtv": 3, "dvdrip": 2, "hdrip": 2,
    "hdcam": 1, "cam": 1, "ts": 1, "tc": 1,
}
CODEC_LADDER: Dict[str, int] = {
    "av1": 4, "hevc": 3, "x265": 3, "h265": 3,
    "h264": 2, "x264": 2, "avc": 2, "vp9": 1,
}
EFFECT_LADDER: Dict[str, int] = {
    "dolbyvision": 4, "dovi": 4, "dv": 4,
    "hdr10+": 3, "hdr10": 3, "hdr": 2, "sdr": 0,
}
AUDIO_LADDER: Dict[str, int] = {
    "atmos": 5, "truehd": 4, "dtshd": 3, "flac": 3,
    "dts": 2, "ddp": 2, "eac3": 2, "dd+": 2,
    "ac3": 1, "aac": 1, "opus": 1,
}

# 第二层加权总分权重（分辨率权重最高：4K→1080p 的落差远大于编码差异）
DEFAULT_WEIGHTS: Dict[str, int] = {
    "resolution": 40,
    "source": 25,
    "codec": 15,
    "effect": 15,
    "audio": 5,
}

# 匹配用正则：按「长的写法在前」排列，避免 hdtvrip 被 hdtv 截断、
# hdr10+ 被 hdr10 截断。短词（ts/tc/cam/dv）要求前后不是字母数字。
_RESOLUTION_RE = re.compile(
    r"(?<![a-z0-9])(8k|4k|2160p|1080p|1080i|720p|576p|480p)(?![a-z0-9])"
)
_SOURCE_RE = re.compile(
    r"(remux|blu-?ray|bdrip|web-?dl|webrip|hdtvrip|hdtv|dvdrip|hdrip|hdcam|cam|ts|tc)"
    r"(?![a-z0-9])"
)
_CODEC_RE = re.compile(
    r"(?<![a-z0-9])(av1|hevc|x265|h\.?265|x264|h\.?264|avc|vp9)(?![a-z0-9])"
)
_EFFECT_RE = re.compile(
    r"(dolby\s*vision|dovi|hdr10\+|hdr10|hdr|(?<![a-z0-9])dv(?![a-z0-9])|sdr)"
)
_AUDIO_RE = re.compile(
    r"(?<![a-z0-9])(atmos|truehd|dts-?hd|dts|ddp|eac3|dd\+|ac3|aac|flac|opus)(?![a-z0-9])"
)

# 归一化：只留字母数字与汉字，用于拼基线键
_NORM_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")

# 已知画质（至少解析出分辨率）才算可比
STATE_UPGRADE = "upgrade"
STATE_FLAT = "flat"
STATE_UNKNOWN = "unknown"


def _normalize_token(value: str) -> str:
    """把匹配到的字面量归一成阶梯键：``Blu-ray``→``bluray``、``WEB-DL``→``webdl``。"""
    return _NORM_RE.sub("", str(value or "").lower())


def _match_ladder(text: str, pattern: "re.Pattern[str]", ladder: Mapping[str, int]
                  ) -> Tuple[str, int]:
    """在文本里找出阶梯值最高的一项，返回 ``(原始匹配, 阶梯值)``。"""
    best_raw, best_rank = "", 0
    for match in pattern.finditer(text):
        raw = str(match.group(1) or "")
        key = _normalize_token(raw)
        rank = int(ladder.get(key) or 0)
        if rank > best_rank:
            best_raw, best_rank = raw, rank
    return best_raw, best_rank


def parse_quality(text: Any) -> Dict[str, Any]:
    """从消息正文解析画质画像。

    :returns: ``{"resolution","source","codec","effect","audio",
                 "resolution_rank","source_rank","codec_rank","effect_rank",
                 "audio_rank","score","known"}``
    """
    raw = str(text or "")
    lowered = raw.lower()
    resolution, resolution_rank = _match_ladder(lowered, _RESOLUTION_RE, RESOLUTION_LADDER)
    source, source_rank = _match_ladder(lowered, _SOURCE_RE, SOURCE_LADDER)
    codec, codec_rank = _match_ladder(lowered, _CODEC_RE, CODEC_LADDER)
    effect, effect_rank = _match_ladder(lowered, _EFFECT_RE, EFFECT_LADDER)
    audio, audio_rank = _match_ladder(lowered, _AUDIO_RE, AUDIO_LADDER)
    profile: Dict[str, Any] = {
        "resolution": resolution,
        "source": source,
        "codec": codec,
        "effect": effect,
        "audio": audio,
        "resolution_rank": resolution_rank,
        "source_rank": source_rank,
        "codec_rank": codec_rank,
        "effect_rank": effect_rank,
        "audio_rank": audio_rank,
        "known": resolution_rank > 0,
    }
    profile["score"] = score_of(profile)
    return profile


def score_of(profile: Mapping[str, Any], weights: Optional[Mapping[str, int]] = None) -> int:
    """按权重算总分（只算已知维度）。"""
    used = dict(DEFAULT_WEIGHTS)
    if weights:
        used.update({key: int(value) for key, value in weights.items() if key in used})
    total = 0
    for dimension, weight in used.items():
        total += int(weight) * int(profile.get(f"{dimension}_rank") or 0)
    return total


def describe(profile: Mapping[str, Any]) -> str:
    """画质画像的人话描述（日志 / 推送说明用）。"""
    parts = []
    for field, label in (("resolution", "分辨率"), ("source", "片源"),
                         ("codec", "编码"), ("effect", "特效"), ("audio", "音轨")):
        value = str(profile.get(field) or "").strip()
        if value:
            parts.append(f"{label} {value}")
    if not parts:
        return "画质未知"
    return "、".join(parts)


def compare(base: Optional[Mapping[str, Any]], candidate: Mapping[str, Any]
            ) -> Tuple[str, str]:
    """两层对比：候选是否相对基线升级。

    :returns: ``(state, reason)``，state ∈ ``upgrade`` / ``flat`` / ``unknown``。
        ``unknown`` 表示候选画质解析不出来——不参与比较，由 TopN 兜底。
    """
    if not candidate or not candidate.get("known"):
        return STATE_UNKNOWN, "画质无法解析"
    if not base or not base.get("known"):
        return STATE_UPGRADE, "首次推送（无基线）"
    # 第一层：硬门槛，分辨率与片源都不得倒退
    base_resolution = int(base.get("resolution_rank") or 0)
    candidate_resolution = int(candidate.get("resolution_rank") or 0)
    if candidate_resolution < base_resolution:
        return STATE_FLAT, (
            f"分辨率低于基线（{candidate.get('resolution') or '?'}"
            f" < {base.get('resolution') or '?'}）"
        )
    base_source = int(base.get("source_rank") or 0)
    candidate_source = int(candidate.get("source_rank") or 0)
    if candidate_source < base_source:
        return STATE_FLAT, (
            f"片源低于基线（{candidate.get('source') or '?'}"
            f" < {base.get('source') or '?'}）"
        )
    # 第二层：加权总分必须严格更高
    base_score = int(base.get("score") or 0)
    candidate_score = int(candidate.get("score") or 0)
    if candidate_score > base_score:
        return STATE_UPGRADE, f"总分更高（{candidate_score} > {base_score}）"
    return STATE_FLAT, f"与基线持平（{candidate_score} ≤ {base_score}）"


def baseline_key(title: Any, year: Any, season: Any = None,
                 episode: Any = None, episode_end: Any = None) -> str:
    """基线键：订阅标题 + 年份 + 季集区间（电影只到年份）。"""
    def _part(value: Any) -> str:
        if value is None or value == "":
            return ""
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return _NORM_RE.sub("", str(value).lower())

    return "|".join((
        _NORM_RE.sub("", str(title or "").lower()),
        _part(year),
        _part(season),
        _part(episode),
        _part(episode_end),
    ))
