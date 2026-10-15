"""Emby 计划任务中心：归一化宿主媒体服务器的 ScheduledTasks 数据与操作。

归一化层移植自 ChillPoster（中文标签、ticks ↔ 时/分/小时换算、触发器摘要、
运行状态与最近执行结果），操作层统一走 ``emby_gateway``。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import emby_gateway

TICKS_PER_SECOND = 10_000_000
TICKS_PER_MINUTE = TICKS_PER_SECOND * 60
TICKS_PER_HOUR = TICKS_PER_MINUTE * 60

CATEGORY_LABELS = {
    "application": "应用程序",
    "database": "数据库",
    "downloads & conversions": "下载与转换",
    "internet channels": "互联网频道",
    "library": "媒体库扫描",
    "maintenance": "日常维护",
    "subtitle": "字幕",
    "subtitles": "字幕",
    "sync": "同步",
    "livetv": "电视直播",
    "live tv": "电视直播",
    "plugins": "插件",
    "plugin": "插件",
    "people": "人员",
}

TASK_NAME_LABELS = {
    "Cache file cleanup": "清理缓存文件",
    "Check for application updates": "检查应用更新",
    "Check for plugin updates": "检查插件更新",
    "Convert media": "转换媒体",
    "Delete Persons": "删除人员数据",
    "Detect Episode Intros": "检测剧集片头",
    "Download OCR Data": "下载 OCR 数据",
    "Download subtitles": "下载字幕",
    "Extract Intro Fingerprint": "提取片头声纹",
    "Extract MediaInfo": "提取媒体信息",
    "Extract Video Thumbnail": "提取视频缩略图",
    "Hardware Detection": "硬件检测",
    "Log file cleanup": "清理日志文件",
    "Merge Multi Versions": "合并多版本",
    "Persist MediaInfo": "持久化媒体信息",
    "Refresh Episode": "刷新剧集",
    "Refresh Guide": "刷新电视指南",
    "Refresh Internet Channels": "刷新互联网频道",
    "Refresh Users": "刷新用户",
    "Rotate log file": "轮转日志文件",
    "Scan External Tracks": "扫描外挂轨道",
    "Scan media library": "扫描媒体库",
    "Scan Metadata Folder": "扫描元数据文件夹",
    "Send Download Notifications": "发送下载通知",
    "Transfer media": "转移媒体",
    "Update Plugin": "更新插件",
    "Vacuum Database": "整理数据库",
    "Video preview thumbnail extraction": "提取视频预览缩略图",
}

STATUS_LABELS = {
    "completed": "执行成功",
    "failed": "执行失败",
    "cancelled": "已取消",
    "canceled": "已取消",
    "aborted": "已取消",
}

DAY_OF_WEEK_LABELS = {
    "Monday": "周一",
    "Tuesday": "周二",
    "Wednesday": "周三",
    "Thursday": "周四",
    "Friday": "周五",
    "Saturday": "周六",
    "Sunday": "周日",
}

TRIGGER_TYPE_LABELS = {
    "DailyTrigger": "每天",
    "WeeklyTrigger": "每周",
    "IntervalTrigger": "按间隔",
    "StartupTrigger": "服务器启动时",
    "SystemEventTrigger": "系统事件",
}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _ticks_to_time(value: Any) -> str:
    """把 TimeOfDayTicks 换算成 HH:MM。"""
    try:
        total_minutes = int(int(value or 0) / TICKS_PER_MINUTE)
    except (TypeError, ValueError):
        total_minutes = 0
    total_minutes = max(0, min(total_minutes, 24 * 60 - 1))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _hours_from_ticks(value: Any) -> float:
    try:
        ticks = int(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if ticks <= 0:
        return 0.0
    return round(ticks / TICKS_PER_HOUR, 2)


def _ticks_from_hours(value: Any) -> int:
    try:
        hours = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if hours <= 0:
        return 0
    return int(hours * TICKS_PER_HOUR)


def _time_to_ticks(value: Any) -> int:
    text = _safe_str(value, "00:00")
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = max(0, min(23, int(hour_text)))
        minute = max(0, min(59, int(minute_text)))
    except Exception:
        hour, minute = 0, 0
    return (hour * 60 + minute) * TICKS_PER_MINUTE


def _format_interval_hours(hours: float) -> str:
    if hours <= 0:
        return "未设置间隔"
    if abs(hours - round(hours)) < 0.01:
        return f"每 {int(round(hours))} 小时"
    return f"每 {hours:g} 小时"


def normalize_trigger(trigger: Dict[str, Any]) -> Dict[str, Any]:
    """把 Emby 原始触发器归一化为展示结构。"""
    if not isinstance(trigger, dict):
        trigger = {}
    trigger_type = _safe_str(trigger.get("Type"), "DailyTrigger")
    day = _safe_str(trigger.get("DayOfWeek"))
    time_text = _ticks_to_time(trigger.get("TimeOfDayTicks"))
    interval_hours = _hours_from_ticks(trigger.get("IntervalTicks"))
    max_runtime_hours = _hours_from_ticks(trigger.get("MaxRuntimeTicks"))
    system_event = _safe_str(trigger.get("SystemEvent"))

    if trigger_type == "DailyTrigger":
        summary = f"每天 {time_text}"
    elif trigger_type == "WeeklyTrigger":
        summary = f"{DAY_OF_WEEK_LABELS.get(day, day or '每周')} {time_text}"
    elif trigger_type == "IntervalTrigger":
        summary = _format_interval_hours(interval_hours)
    elif trigger_type == "StartupTrigger":
        summary = "服务器启动时"
    elif trigger_type == "SystemEventTrigger":
        summary = f"系统事件：{system_event or '未指定'}"
    else:
        summary = TRIGGER_TYPE_LABELS.get(trigger_type, trigger_type or "触发器")

    if max_runtime_hours > 0:
        summary = f"{summary}，最多运行 {max_runtime_hours:g} 小时"

    return {
        "type": trigger_type,
        "type_label": TRIGGER_TYPE_LABELS.get(trigger_type, trigger_type),
        "time": time_text,
        "day_of_week": day,
        "day_label": DAY_OF_WEEK_LABELS.get(day, day),
        "interval_hours": interval_hours,
        "max_runtime_hours": max_runtime_hours,
        "system_event": system_event,
        "summary": summary,
    }


def normalize_triggers(value: Any) -> List[Dict[str, Any]]:
    """归一化触发器列表。"""
    if not isinstance(value, list):
        return []
    return [normalize_trigger(item) for item in value if isinstance(item, dict)]


def _build_trigger_summary(triggers: List[Dict[str, Any]]) -> str:
    summaries = [_safe_str(item.get("summary")) for item in triggers if _safe_str(item.get("summary"))]
    if not summaries:
        return "未设置计划"
    if len(summaries) <= 2:
        return "；".join(summaries)
    return f"{'；'.join(summaries[:2])} 等 {len(summaries)} 个计划"


def normalize_trigger_for_emby(trigger: Dict[str, Any]) -> Dict[str, Any]:
    """把前端草稿转换为 Emby 触发器格式；非法输入抛 ValueError。"""
    if not isinstance(trigger, dict):
        raise ValueError("触发器格式不正确")
    trigger_type = _safe_str(trigger.get("type") or trigger.get("Type"), "DailyTrigger")
    result: Dict[str, Any] = {"Type": trigger_type}
    max_runtime_ticks = _ticks_from_hours(trigger.get("max_runtime_hours") or trigger.get("MaxRuntimeHours"))

    if trigger_type == "DailyTrigger":
        result["TimeOfDayTicks"] = _time_to_ticks(trigger.get("time") or trigger.get("Time"))
    elif trigger_type == "WeeklyTrigger":
        result["TimeOfDayTicks"] = _time_to_ticks(trigger.get("time") or trigger.get("Time"))
        result["DayOfWeek"] = _safe_str(trigger.get("day_of_week") or trigger.get("DayOfWeek"), "Monday")
    elif trigger_type == "IntervalTrigger":
        interval_ticks = _ticks_from_hours(trigger.get("interval_hours") or trigger.get("IntervalHours"))
        if interval_ticks <= 0:
            raise ValueError("间隔触发器需要填写大于 0 的小时数")
        result["IntervalTicks"] = interval_ticks
    elif trigger_type == "StartupTrigger":
        pass
    elif trigger_type == "SystemEventTrigger":
        result["SystemEvent"] = _safe_str(trigger.get("system_event") or trigger.get("SystemEvent"))
    else:
        raise ValueError(f"不支持的触发类型: {trigger_type}")

    if max_runtime_ticks > 0:
        result["MaxRuntimeTicks"] = max_runtime_ticks
    return result


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = _safe_str(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except Exception:
        return None


def _format_task_time(value: Any) -> str:
    dt = _parse_datetime(value)
    if not dt:
        return ""
    now = datetime.now(dt.tzinfo)
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return f"{dt.month}/{dt.day} {dt.strftime('%H:%M')}"


def _normalize_category(value: Any) -> str:
    raw = _safe_str(value, "其他任务")
    return CATEGORY_LABELS.get(raw.lower().strip(), raw)


def _normalize_task_name(value: Any) -> str:
    raw = _safe_str(value, "未命名任务")
    return TASK_NAME_LABELS.get(raw, raw)


def normalize_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """把 Emby 原始任务归一化为展示结构。"""
    task = task if isinstance(task, dict) else {}
    last = task.get("LastExecutionResult") or {}
    if not isinstance(last, dict):
        last = {}
    state = _safe_str(task.get("State"), "Idle")
    last_status = _safe_str(last.get("Status"))
    last_status_key = last_status.lower()
    is_running = state.lower() == "running"

    try:
        progress_value = round(float(task.get("CurrentProgressPercentage") or 0), 1)
    except (TypeError, ValueError):
        progress_value = 0.0

    last_end = last.get("EndTimeUtc") or last.get("StartTimeUtc")
    status_label = "运行中" if is_running else STATUS_LABELS.get(last_status_key, "无记录")
    status_type = "running" if is_running else {
        "completed": "success",
        "failed": "error",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "aborted": "cancelled",
    }.get(last_status_key, "idle")
    triggers = normalize_triggers(task.get("Triggers"))

    return {
        "id": _safe_str(task.get("Id") or task.get("Key") or task.get("Name")),
        "key": _safe_str(task.get("Key")),
        "name": _normalize_task_name(task.get("Name")),
        "description": _safe_str(task.get("Description")),
        "category": _normalize_category(task.get("Category")),
        "raw_category": _safe_str(task.get("Category"), "其他任务"),
        "state": state,
        "is_running": is_running,
        "progress": progress_value,
        "last_status": last_status,
        "status_label": status_label,
        "status_type": status_type,
        "last_run_time": _format_task_time(last_end),
        "last_run_time_raw": _safe_str(last_end),
        "error_message": _safe_str(last.get("ErrorMessage")),
        "triggers": triggers,
        "trigger_summary": _build_trigger_summary(triggers),
    }


def _task_sort_key(task: Dict[str, Any]):
    return (0 if task.get("is_running") else 1, _safe_str(task.get("name")).lower())


def _category_sort_key(category: Dict[str, Any]):
    name = _safe_str(category.get("name"))
    if name == "媒体库扫描":
        return (0, name)
    return (1, name)


def build_payload(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """把归一化任务按分类分组，输出前端载荷。"""
    normalized = [normalize_task(task) for task in (tasks or []) if isinstance(task, dict)]
    normalized.sort(key=_task_sort_key)

    categories: List[Dict[str, Any]] = []
    for task in normalized:
        category = task["category"]
        group = next((item for item in categories if item["name"] == category), None)
        if not group:
            group = {"name": category, "count": 0, "tasks": []}
            categories.append(group)
        group["tasks"].append(task)
        group["count"] += 1
    categories.sort(key=_category_sort_key)

    running = [task for task in normalized if task.get("is_running")]
    return {
        "tasks": normalized,
        "categories": categories,
        "running_count": len(running),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_tasks(ref: emby_gateway.ServerRef) -> List[Dict[str, Any]]:
    """读取计划任务列表（兼容部分版本对隐藏 / 禁用任务的过滤）。"""
    tasks: List[Dict[str, Any]] = []
    seen = set()
    for query in (None, {"IsHidden": "true"}, {"IsHidden": "false"}, {"IsEnabled": "false"}):
        try:
            res = emby_gateway.get_json(ref, "ScheduledTasks", query=query)
        except emby_gateway.GatewayError:
            if not tasks:
                raise
            continue
        if not isinstance(res, list):
            continue
        for item in res:
            if not isinstance(item, dict):
                continue
            task_id = item.get("Id") or item.get("Key") or item.get("Name")
            if not task_id or task_id in seen:
                continue
            seen.add(task_id)
            tasks.append(item)
    return tasks


def list_tasks(server_name: str = "") -> Dict[str, Any]:
    """返回归一化后的任务列表载荷。"""
    ref = emby_gateway.resolve(server_name)
    return build_payload(fetch_tasks(ref))


def get_task(server_name: str, task_id: str) -> Dict[str, Any]:
    """返回单个任务的归一化结构与触发器。"""
    if not task_id:
        raise emby_gateway.GatewayError("缺少任务 ID")
    ref = emby_gateway.resolve(server_name)
    raw = emby_gateway.get_json(ref, f"ScheduledTasks/{task_id}")
    task = normalize_task(raw if isinstance(raw, dict) else {})
    return {
        "task": task,
        "triggers": task.get("triggers", []),
        "trigger_summary": task.get("trigger_summary", "未设置计划"),
    }


def save_triggers(server_name: str, task_id: str, triggers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """保存触发器并返回保存后的任务结构。"""
    if not task_id:
        raise emby_gateway.GatewayError("缺少任务 ID")
    if not isinstance(triggers, list):
        raise ValueError("触发器列表格式不正确")
    payload = [normalize_trigger_for_emby(item) for item in triggers]
    ref = emby_gateway.resolve(server_name)
    emby_gateway.post_json(ref, f"ScheduledTasks/{task_id}/Triggers", payload=payload)
    return get_task(server_name, task_id)


def run_task(server_name: str, task_id: str) -> None:
    """立即运行指定任务。"""
    if not task_id:
        raise emby_gateway.GatewayError("缺少任务 ID")
    ref = emby_gateway.resolve(server_name)
    emby_gateway.post_json(ref, f"ScheduledTasks/Running/{task_id}")


def stop_task(server_name: str, task_id: str) -> None:
    """停止正在运行的指定任务。"""
    if not task_id:
        raise emby_gateway.GatewayError("缺少任务 ID")
    ref = emby_gateway.resolve(server_name)
    emby_gateway.delete(ref, f"ScheduledTasks/Running/{task_id}")
