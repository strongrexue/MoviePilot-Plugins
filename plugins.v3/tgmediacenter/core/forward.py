"""⑥ TG 通用转发：转发规则引擎（两级匹配、内容转换、置顶）。

匹配语义（与设计文档 6. 转发规则、MA 自动化配置 8 对齐）：:

    逻辑一 ┌ 匹配订阅（消息识别出的媒体在宿主订阅列表里）
           └ 自定义关键词命中
           └─ 两者按 match_mode（OR / AND）组合；都关闭 = 逻辑一无约束
    逻辑二 ─ 文件扩展名命中（消息里出现指定扩展名）
    ─────────────────────────────────────────────
    最终 = 逻辑一 AND 逻辑二（两级之间恒为 AND，不受 match_mode 影响）

内容转换：``transform_rules`` 每行 ``原文 -> 替换文``，左侧按**正则**编译，
逐条 ``re.sub`` 顺序应用（前一条的结果喂给后一条）。非法正则只跳过该条并记进
``errors``，不让整条规则失效。

置顶：``pin_links_enabled`` 时，转发/发送后把该消息在目标会话内置顶；
``pin_link_keywords`` 非空时只在消息命中任一关键词时置顶（如只置顶「网盘链接」）。

本模块只做**纯逻辑**（不碰网络、不碰数据库），便于单测与复用：
- 匹配：:func:`match_rule`
- 转换：:func:`parse_transform_rules` / :func:`apply_transform`
- 置顶：:func:`should_pin`
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..model.hit_log import (
    DECISION_SKIPPED_EXTENSION,
    DECISION_SKIPPED_KEYWORD,
    DECISION_SKIPPED_NOT_SUBSCRIBED,
    DECISION_SKIPPED_UNRECOGNIZED,
)

# 转换规则的左右分隔符：`原文 -> 替换文`，兼容 => 与 →（日文箭头）
_TRANSFORM_SPLIT_RE = re.compile(r"\s*(?:->|=>|→)\s*")
# 匹配模式
MATCH_MODE_OR = "or"
MATCH_MODE_AND = "and"


def new_rule_id() -> str:
    """生成转发规则稳定 ID。

    前缀 ``f`` 与监控规则的 ``r`` 区分：两套规则共用一张流水表
    （``monitor_hit_log``），ID 前缀让"这条流水来自哪套规则"一眼可辨，
    也避免两套规则 ID 意外重名的极小概率事件。
    """
    return "f" + uuid.uuid4().hex[:8]


def normalize_match_mode(value: Any) -> str:
    """匹配模式归一：只接受 or / and，其余回落 or。"""
    mode = str(value or "").strip().lower()
    return MATCH_MODE_AND if mode == MATCH_MODE_AND else MATCH_MODE_OR


# ---------------------------------------------------------------------- 逻辑二：扩展名


def match_extensions(text: str, extensions: Iterable[str]) -> List[str]:
    """消息文本里出现的扩展名（``mp4`` / ``mkv`` …）。

    消息只有文本可用（插件不读 message.document），因此按下述形态判定：
    ``.mp4``（``2160p.WEB-DL.mp4``）或方括号包裹（``[mp4]`` / ``【MP4】``）。
    中文方括号先归一成 ASCII，避免「【MP4】」这类常见播报漏判。
    """
    haystack = str(text or "").lower().replace("【", "[").replace("】", "]")
    hit: List[str] = []
    for raw in extensions or []:
        ext = str(raw or "").strip().lstrip(".").lower()
        if not ext:
            continue
        if f".{ext}" in haystack or f"[{ext}]" in haystack:
            hit.append(ext)
    return hit


# ---------------------------------------------------------------------- 逻辑一：两级匹配


def match_rule(
    rule: Dict[str, Any],
    *,
    text: str,
    cleaned: str,
    title: str = "",
    year: str = "",
    season: Optional[int] = None,
    is_subscribed: Optional[bool] = None,
    links: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """判断一条转发规则是否命中。

    :param is_subscribed: 该消息识别出的媒体是否在宿主订阅里；
        ``None`` 表示订阅数据源不可用（无法判断）——此时「匹配订阅」条件不满足，
        原因里会写明，避免表现为「规则莫名不生效」。
    :returns: ``{"matched": bool, "reason": str, "stage": str, "detail": dict}``
    """
    haystack = str(cleaned or text or "")
    detail: Dict[str, Any] = {}

    # ---- 逻辑一：订阅 / 自定义关键词（按 match_mode 组合）
    want_subscription = bool(rule.get("match_subscription_keywords"))
    want_custom = bool(rule.get("match_custom_keywords"))
    mode = normalize_match_mode(rule.get("match_mode"))

    checks: List[Tuple[str, bool, str]] = []
    if want_subscription:
        if is_subscribed is None:
            checks.append(("订阅", False, "订阅数据源不可用，无法判断是否已订阅"))
        elif is_subscribed:
            checks.append(("订阅", True, f"「{title or '未识别'}」在订阅列表中"))
        else:
            checks.append(("订阅", False, f"「{title or '未识别'}」不在订阅列表中"))
    if want_custom:
        keywords = [str(kw) for kw in (rule.get("custom_keywords") or []) if str(kw).strip()]
        if not keywords:
            checks.append(("关键词", False, "已启用关键词过滤但未填写任何关键词"))
        else:
            hits = [kw for kw in keywords if kw in haystack]
            checks.append(("关键词", bool(hits), f"命中关键词：{'、'.join(hits)}" if hits else "未命中任何关键词"))

    if checks:
        passed = [item for item in checks if item[1]]
        if mode == MATCH_MODE_AND:
            ok = len(passed) == len(checks)
        else:
            ok = bool(passed)
        detail["logic_one"] = [{"name": name, "ok": hit, "note": note} for name, hit, note in checks]
        if not ok:
            reason = "；".join(f"{name}：{note}" for name, hit, note in checks if not hit)
            return {
                "matched": False,
                "reason": f"逻辑一（{mode.upper()}）未通过 —— {reason}",
                "stage": "logic_one",
                "detail": detail,
            }
    else:
        detail["logic_one"] = []

    # ---- 逻辑二：文件扩展名（与逻辑一恒为 AND）
    if rule.get("match_file_extensions"):
        extensions = [str(ext) for ext in (rule.get("file_extensions_to_match") or [])]
        if not extensions:
            return {
                "matched": False,
                "reason": "逻辑二：已启用扩展名过滤但未填写任何扩展名",
                "stage": "logic_two",
                "detail": detail,
            }
        hits = match_extensions(text, extensions)
        detail["logic_two"] = {"extensions": extensions, "hits": hits}
        if not hits:
            return {
                "matched": False,
                "reason": f"逻辑二：消息中未出现指定扩展名（{'/'.join(extensions)}）",
                "stage": "logic_two",
                "detail": detail,
            }

    return {"matched": True, "reason": "两级匹配通过", "stage": "ok", "detail": detail}


# ---------------------------------------------------------------------- 内容转换


def parse_transform_rules(raw: Any) -> List[Tuple[str, str]]:
    """把 ``["原文 -> 替换文", ...]`` 解析成 ``[(原文, 替换文)]``（跳过空行与注释）。"""
    pairs: List[Tuple[str, str]] = []
    for line in raw or []:
        value = str(line or "").strip()
        if not value or value.startswith("#"):
            continue
        parts = _TRANSFORM_SPLIT_RE.split(value, maxsplit=1)
        if len(parts) != 2:
            continue
        pattern, repl = parts[0].strip(), parts[1].strip()
        if pattern:
            pairs.append((pattern, repl))
    return pairs


def apply_transform(text: str, raw_rules: Any) -> Dict[str, Any]:
    """按顺序逐条应用转换规则。

    :returns: ``{"text": 结果, "applied": 生效条数, "errors": [非法正则说明], "parsed": 解析出的条数}``
    """
    result = str(text or "")
    applied = 0
    errors: List[str] = []
    pairs = parse_transform_rules(raw_rules)
    for pattern, repl in pairs:
        try:
            compiled = re.compile(pattern)
        except re.error as err:
            errors.append(f"正则非法（{pattern}）：{err}")
            continue
        try:
            replaced = compiled.sub(repl.replace("\\n", "\n"), result)
        except Exception as err:  # pragma: no cover - 替换串异常（少见的组引用错误）
            errors.append(f"替换失败（{pattern}）：{err}")
            continue
        if replaced != result:
            applied += 1
        result = replaced
    return {"text": result, "applied": applied, "errors": errors, "parsed": len(pairs)}


# ---------------------------------------------------------------------- 置顶


def should_pin(rule: Dict[str, Any], *, text: str, links: Optional[List[str]] = None) -> bool:
    """该消息是否需要在目标会话置顶。

    置顶以「链接」为对象：没有链接就不置顶（避免把纯文本播报顶上去）。
    ``pin_link_keywords`` 非空时要求消息命中任一关键词。
    """
    if not rule.get("pin_links_enabled"):
        return False
    if not (links or []):
        return False
    keywords = [str(kw) for kw in (rule.get("pin_link_keywords") or []) if str(kw).strip()]
    if not keywords:
        return True
    haystack = str(text or "")
    return any(kw in haystack for kw in keywords)


# ---------------------------------------------------------------------- 校验


def skip_decision(verdict: Dict[str, Any]) -> str:
    """把未命中的匹配结果归一为流水决策常量（转发面板与流水线共用同一口径）。"""
    detail = verdict.get("detail") or {}
    for item in detail.get("logic_one") or []:
        if item.get("name") == "订阅" and not item.get("ok"):
            note = str(item.get("note") or "")
            if "无法识别" in note or "数据源" in note:
                return DECISION_SKIPPED_UNRECOGNIZED
            return DECISION_SKIPPED_NOT_SUBSCRIBED
    if verdict.get("stage") == "logic_two":
        return DECISION_SKIPPED_EXTENSION
    return DECISION_SKIPPED_KEYWORD


def validate_rule(rule: Dict[str, Any]) -> str:
    """保存前校验，返回错误说明；通过返回空串。

    TG 转发最常出的配置事故是「没填目标会话」——转发会全部失败且原因分散在
    推送队列里，这里提前拦下来。
    """
    name = str(rule.get("name") or "未命名")
    if not str(rule.get("target_id") or "").strip():
        return f"规则「{name}」未填写转发目标会话 ID"
    if rule.get("match_file_extensions") and not (rule.get("file_extensions_to_match") or []):
        return f"规则「{name}」启用了扩展名过滤但未填写扩展名"
    if rule.get("match_custom_keywords") and not (rule.get("custom_keywords") or []):
        return f"规则「{name}」启用了关键词过滤但未填写关键词"
    return ""
