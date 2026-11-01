"""洗版判定门（1.13.35）。

监控链路的唯一质量门：解析候选画质 → 准入过滤 → 逐集取基线 → 逐维字典序比较
→ 汇总「推 / 不推」。这里只做纯逻辑，宿主依赖（媒体库画质、下载历史）由调用方
注入基线字典，方便单测。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import quality as quality_service

STATE_PUSH = "push"
STATE_FLAT = "flat"
STATE_LOWER = "lower"
STATE_REJECTED = "rejected"


def judge(
    profile: Dict[str, Any],
    rules: Dict[str, Any],
    baselines: Optional[Dict[str, Dict[str, Any]]] = None,
    keys: Optional[List[str]] = None,
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """判定一条候选资源是否值得推送。

    :param profile: ``quality.parse_quality`` 的结果
    :param rules: 归一化后的洗版规则
    :param baselines: 基线键 → 基线 profile（已按三源合并后的最优）
    :param keys: 该资源覆盖的逐集基线键（电影为单个键）
    :param profiles: 逐集候选画像（键 → profile）。整包资源逐集体积不同，
        或单集 eD2k 能取到真实字节数时由调用方注入；缺省时整条资源共用
        ``profile``。
    :returns: ``{"state": push|flat|rejected, "reason": str, "details": [...],
        "upgraded": [...], "downgraded": [...]}``
    """
    ok, why = quality_service.filter_profile(profile, rules)
    if not ok:
        return {"state": STATE_REJECTED, "reason": why, "details": [], "upgraded": [], "downgraded": []}

    baselines = baselines or {}
    profiles = profiles or {}
    keys = list(keys or [])
    if not keys:
        return {"state": STATE_PUSH, "reason": "无季集信息，按首推处理", "details": [], "upgraded": [], "downgraded": []}

    details: List[Dict[str, Any]] = []
    upgraded: List[str] = []
    downgraded: List[str] = []
    lowered: List[str] = []
    flat = 0
    for key in keys:
        candidate = profiles.get(key) or profile
        state, reason = quality_service.compare(baselines.get(key), candidate, rules)
        details.append({"key": key, "state": state, "reason": reason})
        if state == quality_service.STATE_UPGRADE:
            upgraded.append(key)
        elif state == quality_service.STATE_FLAT:
            flat += 1
        elif state == quality_service.STATE_LOWER:
            # 明确不如基线（分辨率/片源/音频/体积等任一维更差）
            lowered.append(key)
            downgraded.append(key)
        else:
            # unknown：基线缺失或画质解析不出——按「首推」放行
            upgraded.append(key)

    if upgraded:
        first = next(item for item in details if item["key"] == upgraded[0])
        return {
            "state": STATE_PUSH,
            "reason": f"{first['reason']}（{len(upgraded)}/{len(keys)} 集可推）",
            "details": details,
            "upgraded": upgraded,
            "downgraded": downgraded,
        }
    if lowered:
        first = next(item for item in details if item["key"] == lowered[0])
        return {
            "state": STATE_LOWER,
            "reason": f"{first['reason']}（{len(lowered)}/{len(keys)} 集不如现有版本）",
            "details": details,
            "upgraded": [],
            "downgraded": downgraded,
        }
    return {
        "state": STATE_FLAT,
        "reason": f"全部 {flat} 集都不比现有版本更好",
        "details": details,
        "upgraded": [],
        "downgraded": [],
    }


def merge_baselines(*sources: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """把多个来源的基线合并，同一键保留「更优」的那条（按规则逐维比较）。"""
    merged: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        for key, profile in (source or {}).items():
            if not isinstance(profile, dict):
                continue
            current = merged.get(key)
            if current is None:
                merged[key] = profile
                continue
            # 用 compare 判断谁更优：current 相对新 profile
            # compare(base, cand) == upgrade 表示 cand 更优
            # 这里想要「保留更优者」，等价于把 profile 当候选与 current 比
            state, _ = quality_service.compare(current, profile, quality_service.default_rules())
            if state == quality_service.STATE_UPGRADE:
                merged[key] = profile
    return merged


def covered_keys(details: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """从判定明细里挑出「确实更优」与「持平」的键，供部分转存使用。

    ``lower``（明确不如基线）既不算更优也不算持平，直接忽略。
    """
    better: List[str] = []
    same: List[str] = []
    for item in details or []:
        state = item.get("state")
        if state == quality_service.STATE_FLAT:
            same.append(str(item.get("key") or ""))
        elif state == quality_service.STATE_LOWER:
            continue
        else:
            better.append(str(item.get("key") or ""))
    return better, same
