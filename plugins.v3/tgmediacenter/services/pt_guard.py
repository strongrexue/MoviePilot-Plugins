"""P9 重复获取治理：宿主能力探针。

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

> 历史：本模块曾自带「反向 R0 开关」（暂停宿主内置任务 ``new_subscribe_search``）。
> 1.9.1 真机验证否决：暂停该 job 后新增订阅**照旧被搜索**（首次搜索确为
> ``subscribe.added`` 事件驱动，job 只是 5 分钟兜底），开关无收益，已整体移除。
"""
from __future__ import annotations

import importlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

__all__ = ["probe"]

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


def _load_module(dotted: str) -> Tuple[Any | None, str]:
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

    # 4) 下载器实例（活跃性细化；枚举不到也不致命——闸门按 fail-open 降级）
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

    return {
        "ok": all(item["ok"] for item in items),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "items": items,
    }
