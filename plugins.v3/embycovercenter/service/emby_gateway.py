"""Emby 系媒体服务器访问网关：复用宿主媒体服务器模块的通用 HTTP 透传。

- GET / POST 一律走模块实例的 ``get_data`` / ``post_data``（URL 内的 ``[HOST]`` /
  ``[APIKEY]`` 由宿主模块替换），插件不维护独立凭据、不复制模块实例；
- ``emby`` / ``zspace``（极影视，宿主按 Emby 4.7 兼容层实现，URL 同样带 ``emby/``
  前缀）走同一套 URL 与透传；``jellyfin`` 用根路径；
- 极影视没有静态 ``apikey`` 配置：登录后的 AccessToken 只存在于运行时的
  ``instance._apikey``，故 ``resolve()`` 在配置缺 apikey 时从实例回落（供
  ``real_url()`` / ``delete()`` 拼真实 URL，透传本身仍用占位符）；
- 宿主模块未提供 DELETE 透传，任务中心的「停止任务」用 ``RequestUtils.delete_res``
  补齐——服务器地址与密钥仍取自宿主 ``MediaServerHelper.get_configs()``，不另存凭据。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.sdk.logging import logger

# 支持的媒体服务器类型（Emby / 极影视走 emby/ 前缀，Jellyfin 用根路径）。
# 极影视 = 宿主的 zspace 模块，按 Emby 4.7 兼容层实现：System/Info 返回
# ServerVersion=4.7.0.0，认证用用户名密码换 AccessToken，get_data/post_data
# 与 Emby 模块一样支持 [HOST]/[APIKEY]/[USER] 占位符（参考 wio-ki 插件 v1.8.2）。
SUPPORTED_TYPES = ("emby", "zspace", "jellyfin")
# 与 Emby 同协议的服务器类型（决定 emby/ 前缀，以及运行时凭据/用户 ID 的回落策略）。
EMBY_COMPATIBLE_TYPES = ("emby", "zspace")


class GatewayError(RuntimeError):
    """媒体服务器访问失败：无法定位服务器、请求失败或响应异常。"""


@dataclass
class ServerRef:
    """一个已启用媒体服务器的最小引用。"""

    name: str
    type: str
    instance: Any
    host: str = ""
    apikey: str = ""


def _helper():
    """延迟获取宿主媒体服务器助手，避免导入期依赖宿主。"""
    from app.sdk.services import MediaServerHelper

    return MediaServerHelper()


def list_servers() -> List[Dict[str, Any]]:
    """返回已启用且受支持的媒体服务器摘要（名称 / 类型 / 是否连接）。

    飞牛影视（trimemedia）等未适配类型直接不展示，避免前端选择器扫到后
    resolve 失败弹无意义警告。
    """
    try:
        services = _helper().get_services()
    except Exception as error:  # pragma: no cover - 宿主不可用时降级
        logger.error(f"[EmbyCoverCenter] 读取媒体服务器失败: {error}")
        return []
    result: List[Dict[str, Any]] = []
    for name, service in (services or {}).items():
        if str(getattr(service, "type", "") or "") not in SUPPORTED_TYPES:
            continue
        instance = getattr(service, "instance", None)
        active = True
        if instance is not None:
            try:
                active = not bool(instance.is_inactive())
            except Exception:
                active = False
        result.append(
            {
                "name": str(name),
                "type": str(getattr(service, "type", "") or ""),
                "active": active,
            }
        )
    return result


def resolve(server_name: str = "") -> ServerRef:
    """按名称解析已启用的媒体服务器；未指定时使用第一个。"""
    helper = _helper()
    try:
        services = helper.get_services()
        configs = helper.get_configs()
    except Exception as error:
        raise GatewayError(f"读取媒体服务器失败：{error}") from error
    if not services:
        raise GatewayError("未配置已启用的媒体服务器")

    name = server_name if server_name else next(iter(services), "")
    if name not in services:
        raise GatewayError(f"未找到媒体服务器：{server_name}")

    service = services[name]
    server_type = str(getattr(service, "type", "") or "")
    if server_type not in SUPPORTED_TYPES:
        raise GatewayError(f"暂不支持该媒体服务器类型：{server_type or '未知'}")
    instance = getattr(service, "instance", None)
    if instance is None:
        raise GatewayError(f"媒体服务器 {name} 实例不可用")

    conf = (configs or {}).get(name)
    conf_data = getattr(conf, "config", None)
    if not isinstance(conf_data, dict):
        conf_data = {}
    # 极影视（zspace）配置里没有静态 apikey：登录得到的 AccessToken 只保存在
    # 运行时实例上（zspace.py 的 reconnect() 写入 self._apikey）。透传 URL 用
    # [APIKEY] 占位符由宿主替换，不受影响；但 real_url()/delete() 需要拼真实
    # URL，这里从实例回落。每次 resolve() 都现取，避免重连换 token 后用到旧值。
    apikey = str(conf_data.get("apikey") or "")
    if not apikey:
        apikey = str(getattr(instance, "_apikey", "") or "")
    return ServerRef(
        name=str(name),
        type=server_type,
        instance=instance,
        host=str(conf_data.get("host") or ""),
        apikey=apikey,
    )


def _relative_path(server_type: str, path: str) -> str:
    """按服务器类型拼接 API 相对路径（极影视与 Emby 同带 emby/ 前缀）。"""
    suffix = str(path or "").lstrip("/")
    return f"emby/{suffix}" if server_type in EMBY_COMPATIBLE_TYPES else suffix


def _placeholder_url(ref: ServerRef, path: str, query: Optional[dict] = None) -> str:
    """构建透传 URL；``[HOST]`` / ``[APIKEY]`` 由宿主模块替换。"""
    url = f"[HOST]{_relative_path(ref.type, path)}?api_key=[APIKEY]"
    if query:
        url = f"{url}&{urlencode(query)}"
    return url


def real_url(ref: ServerRef, path: str, query: Optional[dict] = None) -> str:
    """构建真实 URL（供 RequestUtils 直接请求 / 前端展示图片）。"""
    from app.sdk.network import UrlUtils

    host = UrlUtils.standardize_base_url(ref.host) if ref.host else ""
    url = f"{host}{_relative_path(ref.type, path)}?api_key={ref.apikey}"
    if query:
        url = f"{url}&{urlencode(query)}"
    return url


def get_json(ref: ServerRef, path: str, query: Optional[dict] = None) -> Any:
    """GET 并解析 JSON；失败抛 ``GatewayError``。"""
    res = ref.instance.get_data(url=_placeholder_url(ref, path, query))
    status = getattr(res, "status_code", 0)
    if not res or status != 200:
        raise GatewayError(f"GET {path} 失败：HTTP {status or '无响应'}")
    try:
        return res.json()
    except Exception as error:
        raise GatewayError(f"GET {path} 返回内容不是合法 JSON") from error


def get_raw(ref: ServerRef, path: str, query: Optional[dict] = None) -> Optional[bytes]:
    """GET 原始字节（备份当前封面等场景）。

    资源不存在（HTTP 404）返回 None；其余请求失败抛 ``GatewayError``。
    """
    res = ref.instance.get_data(url=_placeholder_url(ref, path, query))
    status = getattr(res, "status_code", 0)
    if not res:
        raise GatewayError(f"GET {path} 失败：无响应")
    if status == 404:
        return None
    if status != 200:
        raise GatewayError(f"GET {path} 失败：HTTP {status or '无响应'}")
    return getattr(res, "content", b"") or b""


def post_json(ref: ServerRef, path: str, payload: Any = None, query: Optional[dict] = None) -> None:
    """POST 并校验状态码；200/204 视为成功。"""
    data = None
    headers = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False)
        headers = {"Content-Type": "application/json"}
    res = ref.instance.post_data(url=_placeholder_url(ref, path, query), data=data, headers=headers)
    status = getattr(res, "status_code", 0)
    if not res or status not in (200, 204):
        raise GatewayError(f"POST {path} 失败：HTTP {status or '无响应'}")


def post_raw(ref: ServerRef, path: str, data: Any, content_type: str, query: Optional[dict] = None) -> None:
    """POST 原始字符串 body（用于封面 base64 上传等非 JSON 场景）。

    极影视（zspace）的 Emby 兼容层没有真机验证过 ``Items/{id}/Images/Primary``
    写入：wio-ki/mediacovergenerator v1.8.2 也是按 Emby 兼容接口盲写的，作者明确
    说明「没有极影视的设备实测」。这里对 zspace 的失败补一段可操作的指引，避免
    用户只看到一句 HTTP 状态码而不知所措；其余类型的报错文案保持原样。
    """
    res = ref.instance.post_data(
        url=_placeholder_url(ref, path, query),
        data=data,
        headers={"Content-Type": content_type},
    )
    status = getattr(res, "status_code", 0)
    if not res or status not in (200, 204):
        message = f"POST {path} 失败：HTTP {status or '无响应'}"
        if ref.type == "zspace" and path.endswith("/Images/Primary"):
            message += (
                "（极影视的 Emby 兼容层可能未实现封面写入；可先「生成预览」后"
                "在媒体服务器里手动把图片设为媒体库封面。若你的设备支持写入，"
                "请把此 HTTP 状态码与插件日志反馈给作者）"
            )
        raise GatewayError(message)


def delete(ref: ServerRef, path: str, query: Optional[dict] = None) -> None:
    """DELETE（宿主模块透传不提供该动词，用 RequestUtils 补齐）。"""
    if not ref.host or not ref.apikey:
        raise GatewayError("媒体服务器地址或密钥缺失，无法发送 DELETE")
    from app.sdk.network import RequestUtils

    res = RequestUtils(headers={"X-Emby-Token": ref.apikey}, timeout=20).delete_res(
        url=real_url(ref, path, query)
    )
    status = getattr(res, "status_code", 0)
    if not res or status not in (200, 204):
        raise GatewayError(f"DELETE {path} 失败：HTTP {status or '无响应'}")
