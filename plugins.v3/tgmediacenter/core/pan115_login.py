"""115 扫码登录（App 通道）——用于绕开 Web Cookie 的"安全密钥"限制。

为什么需要它
------------
115 对**浏览器 Cookie** 的会话会做设备风控：读取账号信息（nav）与空间配额（index_info）
可以通过，但**文件类接口**（列目录、转存、离线）会返回
``请先验证安全密钥``（账号级二次验证）。社区所有第三方 115 工具
（xiaoya-alist、alist 的 115 驱动、p115client）都不使用浏览器 Cookie，而是**扫码登录**，
并用 **App 设备标识**（``alipaymini`` / ``115ios`` / ``115android`` …）绑定会话——
App 通道被 115 视为官方客户端，因此不会触发 Web 安全密钥。

流程（已实测可用）
------------------
1. ``GET  /api/1.0/web/1.0/token/``            → ``{uid, time, sign, qrcode}``
2. ``GET  /api/1.0/web/1.0/qrcode?uid=``       → 二维码图片（PNG）
3. ``GET  /get/status/?uid&time&sign``         → ``{status}``：
   ``0`` 未扫 / ``1`` 已扫待确认 / ``2`` 已确认 / ``-1`` 过期 / ``-2`` 取消
4. ``POST /app/1.0/{app}/1.0/login/qrcode/``   → 带 ``account={uid}``，返回 ``data.cookie``

注：第 4 步在未完成扫码时返回 ``{"state":0,"error":"老乡验证失败！"}``，属预期行为。
"""
from __future__ import annotations

import base64
from typing import Any, Optional

from app.adapters.network.http import AsyncRequestUtils
from app.sdk.logging import logger

_TOKEN_URL = "https://qrcodeapi.115.com/api/1.0/web/1.0/token/"
_IMAGE_URL = "https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode"
_STATUS_URL = "https://qrcodeapi.115.com/get/status/"
_RESULT_URL = "https://qrcodeapi.115.com/app/1.0/{app}/1.0/login/qrcode/"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://115.com/",
    "Accept": "application/json, text/plain, */*",
}

# 扫码绑定的设备标识（115 侧支持列表）→ 界面展示名
QRCODE_APPS: dict[str, str] = {
    # 与 ChillPoster 生产实现同款全集（115 官方端表，p115client 设备表核对），
    # 网页版除外——Web 会话打文件接口必要求安全密钥（1.2.3 真机事故根因）。
    # 标签按 115 官方命名：裸名=115生活系，115xxx=115网盘系，qxxx=115管理系。
    "alipaymini": "115生活（支付宝小程序）",
    "wechatmini": "115生活（微信小程序）",
    "android": "115生活（Android端）",
    "ios": "115生活（iOS端）",
    "ipad": "115生活（iPad端）",
    "115android": "115网盘（Android端）",
    "115ios": "115网盘（iOS端）",
    "115ipad": "115网盘（iPad端）",
    "harmony": "115网盘（鸿蒙端）",
    "tv": "115生活（Android电视端）",
    "apple_tv": "115生活（Apple TV端）",
    "windows": "115生活（Windows端）",
    "mac": "115生活（macOS端）",
    "linux": "115生活（Linux端）",
    "qandroid": "115管理（Android端）",
    "qios": "115管理（iOS端）",
    "qipad": "115管理（iPad端）",
}
DEFAULT_APP = "alipaymini"

# 状态码 → 文案
QR_STATUS_TEXT = {
    0: "等待扫码",
    1: "已扫码，请在手机上点击确认",
    2: "已确认",
    -1: "二维码已过期",
    -2: "扫码已取消",
}


class Pan115QrError(Exception):
    """扫码登录过程中的可预期失败。"""


def app_options() -> list[dict[str, str]]:
    """供前端下拉使用的设备清单。"""
    return [{"value": key, "title": f"{label}（{key}）"} for key, label in QRCODE_APPS.items()]


class Pan115QrLogin:
    """扫码登录客户端（无状态，pending 由调用方持久化）。"""

    def __init__(self, *, proxies: Optional[dict] = None, timeout: int = 20) -> None:
        self._proxies = proxies
        self._timeout = max(5, int(timeout or 20))

    async def _json(self, method: str, url: str, *, params: dict = None, data: dict = None) -> dict:
        """请求并解析 JSON。

        115 的二维码接口对请求头比较敏感（实测：带自定义头的个别客户端会被 WAF
        重定向到首页）。因此这里做一次降级重试：带浏览器头失败就改用最小头再试一次。
        """
        last_error: Optional[Exception] = None
        for headers in (_BROWSER_HEADERS, {"Accept": "application/json, text/plain, */*"}):
            client = AsyncRequestUtils(headers=headers, proxies=self._proxies, timeout=self._timeout)
            try:
                if method == "post":
                    response = await client.post_res(url, data=data or {}, params=params)
                else:
                    response = await client.get_res(url, params=params or {})
            except Exception as err:
                last_error = err
                continue
            if response is None:
                last_error = Pan115QrError("网络不可达或代理异常")
                continue
            if response.status_code != 200:
                last_error = Pan115QrError(f"115 返回 HTTP {response.status_code}")
                continue
            try:
                payload = response.json()
            except Exception:
                last_error = Pan115QrError("115 返回的不是 JSON（可能被风控拦截）")
                continue
            if isinstance(payload, dict):
                return payload

        raise Pan115QrError(f"请求 115 二维码接口失败：{last_error}")

    async def token(self) -> dict:
        """获取二维码 token 与其携带的二维码链接。"""
        payload = await self._json("get", _TOKEN_URL)
        data = payload.get("data") or {}
        uid = str(data.get("uid") or "")
        if not uid:
            raise Pan115QrError(f"获取二维码失败：{payload.get('message') or payload.get('error') or '响应缺少 uid'}")
        return {
            "uid": uid,
            "time": int(data.get("time") or 0),
            "sign": str(data.get("sign") or ""),
            "qrcode": str(data.get("qrcode") or ""),
        }

    async def image_data_url(self, uid: str) -> str:
        """取二维码图片并转成 data URL，前端可直接 <img :src>。"""
        client = AsyncRequestUtils(headers=_BROWSER_HEADERS, proxies=self._proxies, timeout=self._timeout)
        try:
            response = await client.get_res(_IMAGE_URL, params={"uid": uid})
        except Exception as err:
            raise Pan115QrError(f"获取二维码图片失败：{err}") from err
        if response is None or response.status_code != 200:
            raise Pan115QrError("获取二维码图片失败：115 未返回图片")
        content = response.content or b""
        if not content:
            raise Pan115QrError("获取二维码图片失败：图片内容为空")
        return "data:image/png;base64," + base64.b64encode(content).decode("ascii")

    async def status(self, uid: str, time_value: Any, sign: str) -> dict:
        """查询扫码状态。"""
        payload = await self._json(
            "get", _STATUS_URL,
            params={"uid": uid, "time": int(time_value or 0), "sign": sign},
        )
        data = payload.get("data") or {}
        code = data.get("status")
        try:
            code_int = int(code)
        except (TypeError, ValueError):
            code_int = None
        return {
            "code": code_int,
            "text": QR_STATUS_TEXT.get(code_int, str(data.get("msg") or "未知状态")),
            "msg": str(data.get("msg") or ""),
        }

    async def result(self, uid: str, app: str) -> str:
        """完成登录并返回 Cookie 字符串。"""
        use_app = str(app or DEFAULT_APP).strip()
        if use_app not in QRCODE_APPS:
            raise Pan115QrError(f"不支持的登录设备：{use_app}")
        payload = await self._json(
            "post", _RESULT_URL.format(app=use_app),
            data={"account": str(uid)},
        )
        if payload.get("state") in (0, False):
            message = str(payload.get("error") or payload.get("message") or "未知原因")
            # 未确认完成时 115 会返回这个（属预期，不代表失败）
            if "验证失败" in message or "老乡" in message:
                raise Pan115QrError("尚未在手机上点击确认，请完成确认后稍候重试")
            raise Pan115QrError(f"扫码登录失败：{message}")
        data = payload.get("data") or {}
        cookie = data.get("cookie") or {}
        if not isinstance(cookie, dict) or not cookie:
            raise Pan115QrError("扫码登录成功但未取得 Cookie，请重试")
        cookie_str = "; ".join(f"{key}={value}" for key, value in cookie.items())
        logger.info(f"[Pan115] 扫码登录成功（设备：{use_app}）")
        return cookie_str
