"""P9 重复获取治理：宿主能力探针 + 反向 R0 开关。

为什么需要「探针」
------------------
P9 的前向闸门（闸门 A）要用到两组**本插件目前一处都没用过**的宿主能力：

- ``app.sdk.queries.list_download_history`` + ``DownloadHistoryFilter``（下载历史）
- ``app.sdk.services.DownloaderHelper`` → ``list_torrents``（下载器里的活跃种子）

宿主的模块落点与签名在版本之间会变（例如 ``DownloadHistoryFilter`` 究竟在
``app.sdk.queries`` 还是 ``app.schemas.types``，本插件无法凭猜测确定）。所以在
动手写闸门之前，先用一个**只读探针**把"到底能不能导入、真实落在哪个模块、
字段有哪些"问清楚——否则闸门只能靠猜，猜错的代价是判定链静默退化。

探针只读，不写任何状态；任何一项失败都只影响该项结论，不抛异常。

反向 R0 开关
------------
- **开** = 暂停宿主内置任务 ``new_subscribe_search``（新增订阅搜索，5 分钟、硬编码）；
- **关**（默认）= 放行，宿主行为不变。

实现走**旧插件 ABI**（``from app.scheduler import Scheduler`` → ``._scheduler``），
因为 ``app.sdk.scheduler`` 门面只提供 list / start / add / remove，**没有**
pause / resume。宿主配置热重载会重建 job（pause 可能被冲掉），因此
``init_plugin`` 与手动「重贴」都要重跑一次本模块的 ``apply_pause``（幂等）。
"""
from __future__ import annotations

import importlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger

__all__ = [
    "JOB_NEW_SUBSCRIBE_SEARCH",
    "apply_pause",
    "job_state",
    "probe",
]

# 宿主内置调度任务 id（``app/scheduler/catalog.py``）：新增订阅搜索。
# 频率 5 分钟、硬编码、无配置键；新增订阅的**首次**搜索是事件驱动（与它无关）。
JOB_NEW_SUBSCRIBE_SEARCH = "new_subscribe_search"

# 「下载历史过滤器 / 分页请求 / 枚举」可能的落点：宿主版本间位置会变，逐个试。
# 顺序即优先级，命中即止。
_SCHEMA_CANDIDATES: Tuple[str, ...] = (
    "app.sdk.queries",
    "app.schemas.types",
    "app.schemas",
    "app.schemas.models",
)

# 字段名候选（dataclass / pydantic v2 / pydantic v1 / namedtuple 各一种）
_FIELD_ATTRS: Tuple[str, ...] = (
    "model_fields",
    "__dataclass_fields__",
    "__annotations__",
    "_fields",
)


# --------------------------------------------------------------------------- 通用


def _load_module(dotted: str) -> Tuple[Optional[Any], str]:
    """导入模块；失败返回 ``(None, 原因)``，绝不抛异常。"""
    try:
        return importlib.import_module(dotted), ""
    except Exception as err:  # pragma: no cover - 依赖宿主环境
        return None, str(err)


def _find_symbol(name: str, modules: Tuple[str, ...]) -> Tuple[bool, str, str]:
    """在候选模块里找属性。

    :returns: ``(是否找到, 命中模块名, 详情)``。未找到时详情会带上**要找的符号名**
        与逐个模块的尝试记录——探针结果给用户看，必须能回答"是宿主没这个东西，
        还是我们找错了地方"。
    """
    tried: List[str] = []
    for dotted in modules:
        module, err = _load_module(dotted)
        if module is None:
            tried.append(f"{dotted}（导入失败：{err}）")
            continue
        if getattr(module, name, None) is not None:
            return True, dotted, f"{dotted}.{name}"
        tried.append(f"{dotted}（无 {name}）")
    return False, "", f"{name} 未命中：" + "；".join(tried)


def _fields_of(value: Any) -> List[str]:
    """取模型/数据类的字段名（兼容 dataclass / pydantic v1·v2 / namedtuple）。"""
    for attr in _FIELD_ATTRS:
        fields = getattr(value, attr, None)
        if isinstance(fields, dict) and fields:
            return [str(key) for key in fields.keys()]
    return []


def _item(key: str, label: str, ok: bool, detail: str) -> Dict[str, Any]:
    """一条探针结论。"""
    return {"key": key, "label": label, "ok": bool(ok), "detail": str(detail or "")}


# --------------------------------------------------------------------------- 调度


def _apscheduler() -> Tuple[Optional[Any], str]:
    """取 apscheduler 实例（走 MP 特意保留的旧插件 ABI）。

    :returns: ``(实例, 原因)``；不可用时实例为 None，原因可直接展示给用户。
    """
    module, err = _load_module("app.scheduler")
    if module is None:
        return None, f"app.scheduler 不可用（{err}）"
    factory = getattr(module, "Scheduler", None)
    if factory is None:
        return None, "app.scheduler 里没有 Scheduler（宿主未保留旧接口）"
    try:
        holder = factory()
    except Exception as err:  # pragma: no cover - 依赖宿主实现
        return None, f"构造 Scheduler 失败（{err}）"
    instance = getattr(holder, "_scheduler", None)
    if instance is None:
        return None, "Scheduler()._scheduler 不存在（宿主未保留底层调度实例）"
    if not hasattr(instance, "pause_job") or not hasattr(instance, "resume_job"):
        return None, "底层调度实例没有 pause_job / resume_job"
    return instance, ""


def _state_of(instance: Any) -> Dict[str, Any]:
    """把调度实例上的内置任务状态归一（APScheduler 3.x：暂停时 next_run_time 为空）。"""
    try:
        job = instance.get_job(JOB_NEW_SUBSCRIBE_SEARCH)
    except Exception as err:  # pragma: no cover - 依赖宿主实现
        return {"available": True, "exists": False, "paused": False, "next_run": "",
                "detail": f"查询任务失败：{err}"}
    if job is None:
        return {"available": True, "exists": False, "paused": False, "next_run": "",
                "detail": f"未注册任务 {JOB_NEW_SUBSCRIBE_SEARCH}（宿主版本差异或已被移除）"}
    next_run = getattr(job, "next_run_time", None)
    if next_run is None:
        return {"available": True, "exists": True, "paused": True, "next_run": "",
                "detail": "已暂停（任务下次运行时间为空）"}
    try:
        text = next_run.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:  # pragma: no cover - 极端宿主可能给非 datetime
        text = str(next_run)
    return {"available": True, "exists": True, "paused": False, "next_run": text,
            "detail": f"运行中，下次 {text}"}


def job_state() -> Dict[str, Any]:
    """内置任务 ``new_subscribe_search`` 的当前状态（只读）。"""
    instance, detail = _apscheduler()
    if instance is None:
        return {"available": False, "exists": False, "paused": False, "next_run": "",
                "detail": detail}
    return _state_of(instance)


def apply_pause(enabled: bool, *, warn_on_unavailable: bool = True) -> Dict[str, Any]:
    """按需暂停 / 放行内置任务 ``new_subscribe_search``（幂等）。

    :param enabled: True=暂停（R0 开），False=放行（R0 关）。
    :param warn_on_unavailable: 旧 ABI 不可用时是否打 WARNING。插件生命周期钩子
        会频繁调用本函数，只有在**用户确实要求暂停**时才值得刷日志，避免给不用
        P9 的人凭空制造警告。
    :returns: ``{"available", "ok", "applied", "paused", "message"}``
        ``applied=False`` 表示无需处理（宿主没有这个任务）；
        ``ok=False`` 表示尝试了但没达到预期状态（原因写在 message）。
    """
    enabled = bool(enabled)
    instance, detail = _apscheduler()
    if instance is None:
        log = logger.warning if warn_on_unavailable else logger.debug
        log(f"[P9] R0 开关不生效：{detail}")
        return {"available": False, "ok": False, "applied": False, "paused": False,
                "message": f"旧调度接口不可用，R0 开关不生效：{detail}"}

    state = _state_of(instance)
    if not state.get("exists"):
        return {"available": True, "ok": True, "applied": False,
                "paused": bool(state.get("paused")),
                "message": str(state.get("detail") or "宿主未注册该任务，无需处理")}

    action = "暂停" if enabled else "恢复"
    try:
        if enabled:
            instance.pause_job(JOB_NEW_SUBSCRIBE_SEARCH)
        else:
            instance.resume_job(JOB_NEW_SUBSCRIBE_SEARCH)
    except Exception as err:
        logger.warning(f"[P9] {action}任务 {JOB_NEW_SUBSCRIBE_SEARCH} 失败：{err}")
        return {"available": True, "ok": False, "applied": False,
                "paused": bool(state.get("paused")), "message": f"{action}失败：{err}"}

    after = _state_of(instance)
    actual = bool(after.get("paused"))
    if actual == enabled:
        message = ("已暂停「新增订阅搜索」（反向 R0 生效）" if enabled
                   else "已恢复「新增订阅搜索」")
        logger.info(f"[P9] {message}")
        return {"available": True, "ok": True, "applied": True, "paused": actual,
                "message": message}

    # 暂停/恢复后状态没变：宿主可能有别的机制在改这个 job（配置热重载重建等）
    message = f"{action}后状态未如预期（当前 {'已暂停' if actual else '运行中'}）"
    logger.warning(f"[P9] R0 开关状态未如预期：期望 paused={enabled}，实际 {actual}")
    return {"available": True, "ok": False, "applied": True, "paused": actual,
            "message": message}


# --------------------------------------------------------------------------- 探针


def _probe_downloaders(helper_found: bool) -> Dict[str, Any]:
    """枚举已启用的下载器（闸门 A 的「活跃性细化」要用）。"""
    label = "下载器实例"
    if not helper_found:
        return _item("downloader_instances", label, False, "下载器助手不可用，跳过")
    try:
        from app.sdk.services import DownloaderHelper  # type: ignore[import-not-found]

        helper = DownloaderHelper()
    except Exception as err:  # pragma: no cover - 依赖宿主实现
        return _item("downloader_instances", label, False, f"构造下载器助手失败：{err}")

    services = None
    try:
        services = helper.get_services(type_filter="Downloader")
    except TypeError:
        # 部分宿主版本签名不同（无 type_filter 或需要位置参数）
        try:
            services = helper.get_services("Downloader")
        except Exception as err:
            return _item("downloader_instances", label, False, f"枚举下载器失败：{err}")
    except Exception as err:
        return _item("downloader_instances", label, False, f"枚举下载器失败：{err}")

    names: List[str] = []
    if isinstance(services, dict):
        names = [str(key) for key in services.keys()]
    elif services:
        try:
            names = [str(getattr(item, "name", "") or item) for item in services]
        except Exception:  # pragma: no cover - 不可迭代的返回值
            names = []
    if names:
        return _item("downloader_instances", label, True,
                     f"已启用 {len(names)} 个：{'、'.join(names)}")
    return _item("downloader_instances", label, False,
                 "未枚举到已启用的下载器（闸门 A 的活跃性细化将不可用）")


def probe() -> Dict[str, Any]:
    """探测 P9 判定链所需的宿主能力。

    只读、无副作用；任何一项失败只影响该项，不抛异常。
    返回 ``{"ok", "checked_at", "items": [{key,label,ok,detail}]}``，``ok`` 取
    所有项的交集（任一项红即整体红，便于一眼判断"能不能开工"）。
    """
    items: List[Dict[str, Any]] = []

    # 1) 下载历史查询（闸门 A 的 A2 步）
    found, _where, detail = _find_symbol("list_download_history", ("app.sdk.queries",))
    items.append(_item("download_history", "下载历史查询 list_download_history",
                       found, detail))

    # 2) 过滤器与分页请求（查询入参；落点最容易随宿主版本漂移）
    for key, name, label in (
        ("history_filter", "DownloadHistoryFilter", "下载历史过滤器 DownloadHistoryFilter"),
        ("page_request", "QueryPageRequest", "分页请求 QueryPageRequest"),
    ):
        found, where, detail = _find_symbol(name, _SCHEMA_CANDIDATES)
        if not found:
            items.append(_item(key, label, False, detail))
            continue
        module, _err = _load_module(where)
        fields = _fields_of(getattr(module, name, None)) if module is not None else []
        extra = f"，字段 {len(fields)} 个：{'/'.join(fields[:16])}" if fields else ""
        items.append(_item(key, label, True, f"{detail}{extra}"))

    # 3) 下载器助手
    helper_found, _where, helper_detail = _find_symbol("DownloaderHelper", ("app.sdk.services",))
    items.append(_item("downloader_helper", "下载器助手 DownloaderHelper",
                       helper_found, helper_detail))

    # 4) 下载器实例（活跃性细化）
    items.append(_probe_downloaders(helper_found))

    # 5) 种子状态枚举
    ok_torrent, _w1, d1 = _find_symbol("TorrentStatus", _SCHEMA_CANDIDATES)
    ok_state, _w2, d2 = _find_symbol("DownloadTaskState", _SCHEMA_CANDIDATES)
    if ok_torrent or ok_state:
        parts = []
        for name, found, where in (("TorrentStatus", ok_torrent, _w1),
                                   ("DownloadTaskState", ok_state, _w2)):
            parts.append(f"{name} {'在 ' + where if found else '缺失'}")
        items.append(_item("torrent_enum", "种子状态枚举 TorrentStatus / DownloadTaskState",
                           ok_torrent and ok_state, "；".join(parts)))
    else:
        items.append(_item("torrent_enum", "种子状态枚举 TorrentStatus / DownloadTaskState",
                           False, f"{d1}；{d2}"))

    # 6) 旧调度 ABI（R0 开关的前提）
    instance, sched_detail = _apscheduler()
    items.append(_item("scheduler_abi", "旧调度接口 Scheduler()._scheduler",
                       instance is not None,
                       "可用（可 pause / resume 内置任务）" if instance is not None
                       else sched_detail))

    # 7) 反向开关的作用对象是否存在
    state = job_state()
    items.append(_item("job_new_subscribe_search",
                       f"内置任务 {JOB_NEW_SUBSCRIBE_SEARCH}",
                       bool(state.get("exists")), str(state.get("detail") or "")))

    return {
        "ok": all(item["ok"] for item in items),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "items": items,
    }
