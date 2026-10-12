"""115 网盘接口客户端（自实现子集，零新增依赖）。

端点选择（关键，参照社区 p115client 的实现）
--------------------------------------------
- **Web 会话**（手动粘贴的浏览器 Cookie）：走 Web 端点 ``webapi.115.com``；
  但 115 对这类会话有设备风控，文件类接口会要求「安全密钥」二次验证。
- **App 会话**（扫码绑定设备后换取的 Cookie）：必须走 **App 通道端点**
  ``proapi.115.com/{app}/2.0/...``——App 会话 + Web 端点会被 115 判为异常，
  照样要求安全密钥。这是 1.2.3 及之前"扫码成功但校验目录仍报安全密钥"的根因。

只覆盖 v1 需要的能力：

- 登录态与账号信息、空间配额（Web 端点，任何会话可用）
- 目录列举（用于校验转存目录 CID）
- 分享链接转存（share/snap + share/receive）
- 磁力 / eD2k 离线下载（clouddownload lixianssp）
- 离线配额（尽力而为，115 侧经常拿不到，失败不影响其它能力）

依赖宿主的 ``AsyncRequestUtils``，不引入第三方 115 客户端库（社区库带 37 个传递依赖）。
"""
from __future__ import annotations

from typing import Any, Optional

from app.adapters.network.http import AsyncRequestUtils
from app.sdk.logging import logger

_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://115.com/",
    "Accept": "application/json, text/plain, */*",
}

_NAV_URL = "https://my.115.com/"
_SPACE_URL = "https://webapi.115.com/files/index_info"
_FILES_URL = "https://webapi.115.com/files"
_SHARE_SNAP_URL = "https://webapi.115.com/share/snap"
_SHARE_RECEIVE_URL = "https://webapi.115.com/share/receive"
# 云下载通道（离线下载）：lixianssp 需要加密签名，web 明文通道即可用（p115client type="web"）
_OFFLINE_BASE_URL = "https://clouddownload.115.com"
_OFFLINE_ADD_URL = _OFFLINE_BASE_URL + "/web/"
_OFFLINE_QUOTA_URL = _OFFLINE_BASE_URL + "/"

# 这些错误信息基本等同于"Cookie 失效/未登录"，需要引导用户重新获取
_AUTH_ERROR_HINTS = ("登录", "未登录", "登陆", "cookie", "token", "重新登录", "授权")


class Pan115Error(Exception):
    """可预期的 115 操作失败：消息可安全展示给用户。"""


class Pan115AuthError(Pan115Error):
    """Cookie 失效或未登录。"""


def parse_cookie(cookie: Any) -> dict:
    """把 Cookie 字符串/字典归一为字典。

    支持 ``"UID=x; CID=y; SEID=z; KID=k"`` 这类浏览器复制格式，也支持直接传 dict。
    额外容忍两种常见粘贴事故：
    - 整条 ``Cookie: xxx`` 一起粘进来；
    - 换行被单行输入框吃掉，导致 ``UID=x CID=y`` 挤在一段里。

    （Cookie 值本身不允许含空白，因此按空白再切一刀是安全的。）
    """
    if isinstance(cookie, dict):
        return {str(key).strip(): str(value).strip() for key, value in cookie.items() if str(key).strip()}
    text = str(cookie or "").strip()
    if not text:
        return {}
    if text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1]
    result: dict[str, str] = {}
    for chunk in text.replace("\r", ";").replace("\n", ";").split(";"):
        for token in chunk.split():
            if "=" not in token:
                continue
            name, _, value = token.partition("=")
            name = name.strip()
            if name:
                result[name] = value.strip()
    return result


def _format_bytes(size: Any) -> str:
    """把字节数格式化成可读大小；无法解析时原样返回字符串。"""
    if isinstance(size, str) and any(ch.isalpha() for ch in size):
        return size
    try:
        value = float(size)
    except (TypeError, ValueError):
        return str(size or "")
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    return f"{value:.2f}{units[index]}"


class Pan115Client:
    """115 Web 接口的薄封装：每个方法返回归一化后的 dict，失败抛 ``Pan115Error``。"""

    def __init__(
        self,
        cookie: Any,
        *,
        app: str = "web",
        proxies: Optional[dict] = None,
        timeout: int = 20,
    ) -> None:
        self._cookie = parse_cookie(cookie)
        self._app = str(app or "web").strip() or "web"
        self._proxies = proxies
        self._timeout = max(5, int(timeout or 20))

    @property
    def app(self) -> str:
        """当前会话绑定的设备标识；``web`` 表示网页会话。"""
        return self._app

    @property
    def app_session(self) -> bool:
        """是否为 App 通道会话（决定文件类接口走哪套端点）。"""
        return self._app not in ("", "web")

    # ------------------------------------------------------------------ 端点选择

    @property
    def files_url(self) -> str:
        """目录列举端点。"""
        if self.app_session:
            return f"https://proapi.115.com/{self._app}/2.0/ufile/files"
        return _FILES_URL

    @property
    def share_snap_url(self) -> str:
        """分享快照端点。"""
        if self.app_session:
            return f"https://proapi.115.com/{self._app}/2.0/share/snap"
        return _SHARE_SNAP_URL

    @property
    def share_receive_url(self) -> str:
        """分享转存端点。"""
        if self.app_session:
            return f"https://proapi.115.com/{self._app}/2.0/share/receive"
        return _SHARE_RECEIVE_URL

    # ------------------------------------------------------------------ 基础请求

    @property
    def cookie_configured(self) -> bool:
        """是否配置了看起来可用的 Cookie（不发起网络请求）。"""
        return bool(self._cookie.get("UID") and self._cookie.get("CID"))

    async def _request(self, method: str, url: str, *, params: dict = None, data: dict = None, headers: dict = None) -> dict:
        """发起请求并返回 JSON；非 200 / 非 JSON / 网络失败统一抛错。"""
        client = AsyncRequestUtils(
            headers=headers or _BASE_HEADERS,
            cookies=self._cookie,
            proxies=self._proxies,
            timeout=self._timeout,
        )
        try:
            if method == "post":
                response = await client.post_res(url, data=data or {}, params=params)
            else:
                response = await client.get_res(url, params=params or {})
        except Exception as err:
            raise Pan115Error(f"请求 115 失败：{err}") from err

        if response is None:
            raise Pan115Error("请求 115 失败：网络不可达或代理异常")
        if response.status_code != 200:
            raise Pan115Error(f"115 返回异常状态码 HTTP {response.status_code}")
        try:
            payload = response.json()
        except Exception as err:
            raise Pan115Error("115 返回内容无法解析（Cookie 可能已失效，或触发了风控）") from err
        if not isinstance(payload, dict):
            raise Pan115Error("115 返回内容格式异常")
        return payload

    @staticmethod
    def _error_text(payload: dict) -> str:
        """从响应里提取错误描述（115 各通道字段名不统一）。"""
        for key in ("error", "error_msg", "errmsg", "message", "msg"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _raise_if_auth_error(self, message: str) -> None:
        """把疑似未登录/失效的错误转成 ``Pan115AuthError``，便于前端引导重新获取 Cookie。"""
        lowered = message.lower()
        if any(hint in lowered for hint in _AUTH_ERROR_HINTS):
            raise Pan115AuthError(f"115 登录态无效：{message}（请重新获取 Cookie 并保存）")

    def _raise_if_security_key(self, message: str) -> None:
        """把"请先验证安全密钥"翻译成可操作的解释。

        成因：115 对**浏览器 Cookie** 的会话做设备风控——读取账号/空间可以，但
        「文件读写类」接口（列目录、转存、离线）会要求账号级二次验证（安全密钥）。
        社区所有第三方 115 工具因此都改用扫码登录（App 通道）。
        """
        if "安全密钥" not in message:
            return
        raise Pan115Error(
            "115 要求先验证安全密钥：用浏览器 Cookie 从服务器调用时，115 会把「文件读写类」"
            "接口视为新设备的敏感操作，从而要求账号级二次验证。"
            "请改用上面的「扫码登录」（选 App 设备，如支付宝小程序），该通道不会触发这个验证。"
        )

    def _unwrap(self, payload: dict, action: str) -> dict:
        """检查 ``state`` 字段；失败时抛出带上下文的错误。"""
        if payload.get("state") is False or payload.get("state") == 0:
            message = self._error_text(payload) or "未知原因"
            self._raise_if_security_key(message)
            self._raise_if_auth_error(message)
            raise Pan115Error(f"{action}失败：{message}")
        return payload

    # ------------------------------------------------------------------ 账号与配额

    async def user_info(self) -> dict:
        """读取当前登录账号（115 的 nav 接口）。"""
        payload = await self._request(
            "get", _NAV_URL, params={"ct": "ajax", "ac": "nav"},
        )
        self._unwrap(payload, "获取账号信息")
        data = payload.get("data") or {}
        return {
            "user_id": str(data.get("user_id") or data.get("userid") or ""),
            "user_name": str(data.get("user_name") or data.get("username") or ""),
            "vip": bool(data.get("vip") or data.get("is_vip")),
        }

    async def space_info(self) -> dict:
        """读取空间配额（总容量 / 已用 / 剩余）。"""
        payload = await self._request("get", _SPACE_URL)
        self._unwrap(payload, "获取空间信息")
        info = (payload.get("data") or {}).get("space_info") or {}
        all_total = info.get("all_total") or {}
        all_use = info.get("all_use") or {}
        remain = info.get("remain") or {}
        return {
            "total": _format_bytes(all_total.get("size") or all_total.get("size_raw") or info.get("all_total_size") or ""),
            "used": _format_bytes(all_use.get("size") or all_use.get("size_raw") or info.get("all_use_size") or ""),
            "remain": _format_bytes(remain.get("size") or remain.get("size_raw") or info.get("remain_size") or ""),
        }

    async def offline_quota(self) -> dict:
        """读取云下载配额（``GET clouddownload.115.com/?ac=get_quota_info``）。

        拿不到就返回 ``available=False``，不影响其它能力与整体状态。
        """
        try:
            payload = await self._request(
                "get", _OFFLINE_QUOTA_URL,
                params={"ac": "get_quota_info"},
            )
        except Pan115Error as err:
            logger.debug(f"读取 115 离线配额失败：{err}")
            return {"available": False, "text": "获取失败"}
        if payload.get("state") in (False, 0):
            message = self._error_text(payload)
            logger.debug(f"115 未返回离线配额：{message or '未知原因'}")
            return {"available": False, "text": "获取失败"}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        info = data.get("quota_info") or data.get("quota") or data
        if isinstance(info, dict):
            total = info.get("size_total") or info.get("total") or info.get("all_total") or info.get("size")
            used = info.get("size_use") or info.get("size_used") or info.get("use") or info.get("all_use")
            if total:
                text = f"{_format_bytes(used)} / {_format_bytes(total)}" if used else _format_bytes(total)
                return {"available": True, "text": f"剩余 {text}"}
        # 兜底：结构未知时宽松扫描字符串字段
        for source in (payload, data, info if isinstance(info, dict) else {}):
            for key in ("quota", "space", "text", "remain"):
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    return {"available": True, "text": value.strip()}
                if isinstance(value, (int, float)) and value:
                    return {"available": True, "text": _format_bytes(value)}
        return {"available": False, "text": "获取失败"}

    # ------------------------------------------------------------------ 目录

    async def list_dir(self, cid: str, limit: int = 30) -> dict:
        """列举目录内容；用于校验"转存目录 CID"是否有效。

        Web 端点（``/files``）返回 ``data`` 为列表、``path``/``count`` 在顶层；
        App 2.0 端点返回 ``data`` 为 ``{list, path, count}``——两种都要兼容。
        """
        payload = await self._request(
            "get", self.files_url,
            params={
                "aid": 1,
                "cid": str(cid or "0"),
                "o": "user_ptime",
                "asc": 0,
                "show_dir": 1,
                "natsort": 1,
                "format": "json",
                "limit": max(1, min(int(limit or 30), 200)),
                "offset": 0,
            },
        )
        self._unwrap(payload, "读取目录")
        data = payload.get("data")
        if isinstance(data, dict):
            items = data.get("list") or []
            path = data.get("path") or payload.get("path") or []
            count = data.get("count") or len(items)
        else:
            items = data or []
            path = payload.get("path") or []
            count = payload.get("count") or len(items)
        return {
            "cid": str(payload.get("cid") or cid or ""),
            "count": int(count or 0),
            "dirname": str((path[-1].get("name") if path else "") or ""),
            "items": [
                {
                    "name": str(item.get("n") or item.get("name") or ""),
                    "is_dir": bool(item.get("fid") in (None, "", 0)),
                }
                for item in items
                if isinstance(item, dict)
            ][:20],
        }

    async def ensure_dir(self, cid: str) -> dict:
        """确认目标目录存在且可写（返回目录名与条目数）。"""
        if not str(cid or "").strip():
            raise Pan115Error("请先填写转存文件夹 CID")
        info = await self.list_dir(cid, limit=1)
        if not info.get("cid"):
            raise Pan115Error("目标目录不存在或无权访问，请检查 CID")
        return info

    # ------------------------------------------------------------------ 分享转存

    async def share_snap(self, share_code: str, password: str = "") -> dict:
        """读取分享快照，拿到顶层文件 id 列表（转存必需）。"""
        payload = await self._request(
            "get", self.share_snap_url,
            params={
                "share_code": str(share_code or "").strip(),
                "receive_code": str(password or "").strip(),
                "cid": 0,
                "offset": 0,
                "limit": 100,
            },
        )
        if payload.get("state") is False:
            message = self._error_text(payload) or "分享不可用"
            if "密码" in message or "提取" in message:
                raise Pan115Error("提取码错误或未填写，请检查分享链接的提取码")
            self._raise_if_security_key(message)
            raise Pan115Error(f"读取分享失败：{message}")
        data = payload.get("data") or {}
        # 新版返回 {data: {shareinfo, list}}；旧版可能直接是 list
        listing = data.get("list") if isinstance(data, dict) else None
        if listing is None and isinstance(data, list):
            listing = data
        file_ids = [
            str(item.get("fid") or item.get("file_id") or item.get("cid") or "")
            for item in (listing or [])
            if isinstance(item, dict)
        ]
        file_ids = [item for item in file_ids if item]
        share_info = (data.get("shareinfo") if isinstance(data, dict) else None) or {}
        return {
            "share_code": str(share_code or ""),
            "file_ids": file_ids,
            "file_count": len(file_ids),
            "title": str(
                share_info.get("share_title")
                or share_info.get("title")
                or (data.get("file_name") if isinstance(data, dict) else "")
                or ""
            ),
        }

    async def share_receive(self, share_code: str, password: str, file_ids: list[str], cid: str) -> dict:
        """把分享内容转存到目标目录。"""
        if not file_ids:
            raise Pan115Error("分享里没有可转存的文件")
        payload = await self._request(
            "post", self.share_receive_url,
            data={
                "share_code": str(share_code or "").strip(),
                "receive_code": str(password or "").strip(),
                "file_id": ",".join(str(item) for item in file_ids),
                "cid": str(cid or "").strip(),
            },
        )
        if payload.get("state") is False:
            message = self._error_text(payload) or "未知原因"
            if "已转存" in message or "重复" in message:
                return {"ok": True, "message": "该分享此前已转存过（跳过）"}
            self._raise_if_security_key(message)
            self._raise_if_auth_error(message)
            raise Pan115Error(f"转存失败：{message}")
        return {"ok": True, "message": "转存成功"}

    # ------------------------------------------------------------------ 离线下载

    async def offline_add(self, url: str, cid: str = "") -> dict:
        """提交磁力 / eD2k 离线下载任务。

        走云下载通道的**明文 web 端点**（``clouddownload.115.com/web/``，
        p115client 的 ``type="web"``）。默认的 lixianssp 通道要求 RSA+ECDH 加密签名，
        明文请求只会得到无法解析的响应——这是 1.2.4 ed2k 推送失败的根因。
        """
        target = str(cid or "").strip()
        if not target:
            raise Pan115Error("离线下载需要指定保存目录 CID")
        payload = await self._request(
            "post", _OFFLINE_ADD_URL,
            data={
                "ac": "add_task_url",
                "url": str(url or "").strip(),
                "wp_path_id": target,
            },
        )
        if payload.get("state") in (False, 0):
            message = self._error_text(payload) or "未知原因"
            if "已存在" in message or "重复" in message:
                return {"ok": True, "message": "该任务已存在（跳过）"}
            if "请验证账号" in message:
                raise Pan115Error(
                    "115 要求验证账号：当前会话被云下载通道风控。"
                    "请换一个登录设备（推荐 115 Android 端）重新扫码后再试"
                )
            self._raise_if_auth_error(message)
            raise Pan115Error(f"离线下载提交失败：{message}")
        return {"ok": True, "message": "离线任务已提交"}
