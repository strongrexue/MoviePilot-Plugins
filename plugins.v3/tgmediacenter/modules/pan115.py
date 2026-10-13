"""② 115 网盘模块：Cookie 登录态、空间配额、分享转存、磁力/eD2k 离线、分批推送。

编排职责
--------
- 配置读写与状态缓存（缓存写**插件数据**，不放配置，避免被"保存配置"整份覆盖）；
- 把同步的插件接口与异步的 115 客户端桥接起来（``run_sync``）；
- 分批与限速：单批最多 ``pan115_batch_max_size`` 条，且整次调用有总时间预算，
  超时就停下并如实汇报剩余条数（同步接口受网关超时约束，不能无限跑）。

后续 P4（资源监控）/ P6（通用转发）复用 ``push()`` 作为推送目标之一。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

from app.sdk.logging import logger

from ..core import links as link_utils
from ..core.pan115_client import Pan115AuthError, Pan115Client, Pan115Error
from ..core.pan115_login import (
    DEFAULT_APP,
    Pan115QrError,
    Pan115QrLogin,
    app_options,
)
from ..utils import elapsed_seconds as _elapsed_seconds
from ..utils import run_sync

_STATE_KEY = "pan115_state"
_QR_KEY = "pan115_qr"
# Cookie 实际存放点 = 插件数据（配置里的 pan115_cookie 只是手动粘贴的入口）。
# 根因：宿主「保存配置」是整份覆盖，前端表单不回显 Cookie 真实值，
# 用户点一次保存就会把扫码写入配置的 Cookie 清空——所以登录态必须存插件数据。
_COOKIE_DATA_KEY = "pan115_cookie_data"
# 二维码有效期（115 侧约 5 分钟）
_QR_TTL_SECONDS = 300
# 单次同步调用的总时间预算（秒）：必须小于同步接口的网关超时
_PUSH_DEADLINE_SECONDS = 40
# 单次同步调用处理的条目上限（其余返回 remaining，由前端提示再次点击）
_PUSH_MAX_ITEMS = 30
# 连续提交之间的间隔，降低触发风控的概率
_ITEM_INTERVAL_SECONDS = 0.6


class Pan115Module:
    """115 网盘能力编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin

    # ------------------------------------------------------------------ 配置

    @property
    def _config(self) -> dict:
        return getattr(self._plugin, "config", {}) or {}

    def _cfg(self, key: str, default: Any = None) -> Any:
        value = self._config.get(key)
        return default if value is None else value

    def enabled(self) -> bool:
        """是否在配置里启用 115 作为推送目标。"""
        return bool(self._cfg("pan115_enabled"))

    def target_cid(self, override: Optional[str] = None) -> str:
        """转存/离线使用的目标目录 CID。"""
        return str(override or self._cfg("pan115_target_cid", "") or "").strip()

    def batch_size(self, override: Optional[int] = None) -> int:
        """单批最大链接数。"""
        value = override if override is not None else self._cfg("pan115_batch_max_size", 20)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 20

    def _stored_cookie(self) -> str:
        """从插件数据读 Cookie（真实存放点）。"""
        value = self._plugin.get_data(_COOKIE_DATA_KEY)
        return str(value or "").strip() if not isinstance(value, dict) else str(value.get("value") or "").strip()

    def _effective_cookie(self) -> str:
        """生效 Cookie：插件数据优先；配置里有值（手动粘贴）时迁移到插件数据。

        迁移判断必须用原始来源读（这里直接读 get_data 与 config 两个字段），
        不能用本方法自身做条件，否则恒假会丢数据。
        """
        stored = self._stored_cookie()
        if stored:
            return stored
        from_config = str(self._cfg("pan115_cookie", "") or "").strip()
        if from_config:
            try:
                self._plugin.save_data(_COOKIE_DATA_KEY, from_config)
            except Exception as err:  # pragma: no cover
                logger.debug(f"迁移 115 Cookie 到插件数据失败：{err}")
        return from_config

    def _save_cookie(self, cookie: str) -> None:
        """写入 Cookie（插件数据）；同时清掉配置里的旧值，避免双源不一致。"""
        self._plugin.save_data(_COOKIE_DATA_KEY, str(cookie or "").strip())
        try:
            self._plugin.drop_config("pan115_cookie")
        except Exception:
            # 宿主未提供 drop_config 时退化为置空（整份覆盖语义下等价于删除该自管字段）
            try:
                self._plugin.save_config(pan115_cookie="")
            except Exception as err:  # pragma: no cover
                logger.debug(f"清理配置中的旧 115 Cookie 失败：{err}")

    def _client(self, timeout: int = 20) -> Pan115Client:
        """构造 115 客户端；未配置 Cookie 时给出可操作错误。

        会话绑定的设备（``qr_app``）决定文件类接口走哪套端点：
        App 会话必须打 ``proapi.115.com/{app}/2.0/...``，打 Web 端点会被要求安全密钥。
        """
        cookie = self._effective_cookie()
        app = str(self._state().get("qr_app") or "web")
        client = Pan115Client(cookie, app=app, proxies=self._resolve_proxy(), timeout=timeout)
        if not client.cookie_configured:
            raise Pan115Error("未登录 115：请在「账号与授权」里扫码登录")
        return client

    def _resolve_proxy(self) -> Optional[dict]:
        """继承宿主代理（与 TG 侧一致）。"""
        try:
            from app.sdk.config import settings
        except Exception as err:  # pragma: no cover - 宿主接口缺失时直连
            logger.debug(f"读取宿主代理配置失败，按直连处理：{err}")
            return None
        try:
            proxies = getattr(settings, "PROXY", None)
        except Exception:  # pragma: no cover
            return None
        return proxies if isinstance(proxies, dict) and proxies else None

    # ------------------------------------------------------------------ 状态缓存

    def _state(self) -> dict:
        data = self._plugin.get_data(_STATE_KEY) or {}
        return data if isinstance(data, dict) else {}

    def _save_state(self, **patch: Any) -> dict:
        merged = self._state()
        merged.update(patch)
        merged["at"] = datetime.now().isoformat(timespec="seconds")
        self._plugin.save_data(_STATE_KEY, merged)
        return merged

    def status(self) -> dict:
        """返回 115 状态（**不联网**，只用缓存，保证接口快且稳）。"""
        state = self._state()
        cookie = self._effective_cookie()
        try:
            configured = Pan115Client(cookie).cookie_configured
        except Exception:  # pragma: no cover - Cookie 解析异常按未配置处理
            configured = False
        qr_app = str(state.get("qr_app") or "")
        device_label = ""
        if qr_app:
            device_label = next(
                (option["title"] for option in app_options() if option["value"] == qr_app),
                qr_app,
            )
        return {
            "enabled": self.enabled(),
            "cookie_configured": configured,
            "authorized": bool(state.get("authorized")),
            "account": str(state.get("account") or ""),
            "qr_app": qr_app,
            "login_device": device_label,
            "space": state.get("space") if isinstance(state.get("space"), dict) else {},
            "last_check": str(state.get("at") or ""),
            "target_cid": self.target_cid(),
            "batch_max_size": self.batch_size(),
            "qr_apps": app_options(),
            "qr_pending": self._qr_pending_view(),
        }

    # ------------------------------------------------------------------ 扫码登录

    def _qr_login(self, timeout: int = 20) -> Pan115QrLogin:
        """构造扫码登录客户端（继承宿主代理）。"""
        return Pan115QrLogin(proxies=self._resolve_proxy(), timeout=timeout)

    def _qr_pending(self) -> dict:
        data = self._plugin.get_data(_QR_KEY) or {}
        return data if isinstance(data, dict) else {}

    def _qr_pending_view(self) -> Optional[dict]:
        """待扫码状态的对外视图（不含 uid/sign 等内部字段）。"""
        pending = self._qr_pending()
        if not pending.get("uid"):
            return None
        age = _elapsed_seconds(pending.get("at"))
        if age is not None and age > _QR_TTL_SECONDS:
            return None
        return {
            "app": str(pending.get("app") or DEFAULT_APP),
            "image": str(pending.get("image") or ""),
            "expires_in": max(0, _QR_TTL_SECONDS - int(age or 0)),
        }

    def qr_start(self, app: Optional[str] = None) -> dict:
        """获取登录二维码（App 通道，不会触发 Web 安全密钥）。"""
        use_app = str(app or DEFAULT_APP).strip() or DEFAULT_APP
        client = self._qr_login()
        token = run_sync(client.token)
        image = run_sync(lambda: client.image_data_url(token["uid"]))
        self._plugin.save_data(_QR_KEY, {
            "uid": token["uid"],
            "time": token["time"],
            "sign": token["sign"],
            "app": use_app,
            "image": image,
            "at": datetime.now().isoformat(timespec="seconds"),
        })
        return {
            "app": use_app,
            "image": image,
            "status": "waiting",
            "status_text": "等待扫码",
            "message": f"请用 115 App 扫描二维码（设备将绑定为：{use_app}）",
            "expires_in": _QR_TTL_SECONDS,
        }

    def qr_poll(self) -> dict:
        """查询扫码状态；确认后自动写入 Cookie 并检测连接。"""
        pending = self._qr_pending()
        if not pending.get("uid"):
            return {
                "app": "",
                "image": "",
                "status": "expired",
                "status_text": "二维码已失效",
                "message": "没有进行中的扫码登录，请重新获取二维码",
                "expires_in": 0,
            }

        age = _elapsed_seconds(pending.get("at")) or 0
        if age > _QR_TTL_SECONDS:
            self._clear_qr()
            return {
                "app": str(pending.get("app") or ""),
                "image": "",
                "status": "expired",
                "status_text": "二维码已过期",
                "message": "二维码已过期，请重新获取",
                "expires_in": 0,
            }

        client = self._qr_login()
        state = run_sync(lambda: client.status(pending["uid"], pending.get("time"), pending.get("sign")))
        code = state.get("code")

        if code in (-1, -2):
            self._clear_qr()
            return {
                "app": str(pending.get("app") or ""),
                "image": "",
                "status": "expired" if code == -1 else "canceled",
                "status_text": state.get("text") or "扫码已结束",
                "message": state.get("text") or "扫码已结束，请重新获取二维码",
                "expires_in": 0,
            }

        if code != 2:
            return {
                "app": str(pending.get("app") or ""),
                "image": str(pending.get("image") or ""),
                "status": "scanned" if code == 1 else "waiting",
                "status_text": state.get("text") or "等待扫码",
                "message": state.get("text") or "等待扫码",
                "expires_in": max(0, _QR_TTL_SECONDS - int(age)),
            }

        # 已确认：换取 Cookie 并落盘（存插件数据，防止被「保存配置」整份覆盖清空）
        cookie = run_sync(lambda: client.result(pending["uid"], pending.get("app") or DEFAULT_APP))
        self._save_cookie(cookie)
        # 记录会话绑定的设备：之后所有文件类接口都要走对应的 App 通道端点
        self._save_state(qr_app=str(pending.get("app") or DEFAULT_APP))
        self._clear_qr()
        status = self.check()
        return {
            "app": str(pending.get("app") or ""),
            "image": "",
            "status": "success",
            "status_text": "登录成功",
            "message": f"115 扫码登录成功：{status.get('account') or ''}",
            "expires_in": 0,
            "status_data": status,
        }

    def qr_cancel(self) -> dict:
        """取消扫码登录。"""
        self._clear_qr()
        return {
            "app": "",
            "image": "",
            "status": "canceled",
            "status_text": "已取消",
            "message": "已取消扫码登录",
            "expires_in": 0,
        }

    def _clear_qr(self) -> None:
        try:
            self._plugin.del_data(_QR_KEY)
        except Exception as err:  # pragma: no cover
            logger.debug(f"清除扫码状态失败：{err}")

    # ------------------------------------------------------------------ 账号与授权

    def check(self) -> dict:
        """测试连接：读取账号与空间配额，并写入状态缓存。"""
        client = self._client(timeout=20)

        account = run_sync(client.user_info)
        try:
            space = run_sync(client.space_info)
        except Pan115Error as err:
            logger.warning(f"读取 115 空间配额失败：{err}")
            space = {}

        self._save_state(
            authorized=True,
            account=str(account.get("user_name") or account.get("user_id") or ""),
            account_id=str(account.get("user_id") or ""),
            space=space,
        )
        logger.info(f"[{getattr(self._plugin, '__class__').__name__}] 115 连接正常：{account.get('user_name') or account.get('user_id')}")
        return self.status()

    def logout(self) -> dict:
        """清除 Cookie 与状态缓存。"""
        self._save_cookie("")
        for key in (_STATE_KEY, _QR_KEY):
            try:
                self._plugin.del_data(key)
            except Exception as err:  # pragma: no cover
                logger.debug(f"清除 115 缓存 {key} 失败：{err}")
        return self.status()

    # ------------------------------------------------------------------ 目录

    def verify_dir(self, cid: Optional[str] = None) -> dict:
        """校验目标目录可用，并返回目录信息。"""
        client = self._client(timeout=20)
        target = self.target_cid(cid)
        info = run_sync(lambda: client.ensure_dir(target))
        return {
            "cid": info.get("cid", target),
            "dirname": info.get("dirname", ""),
            "count": info.get("count", 0),
            "message": f"目录可用：{info.get('dirname') or info.get('cid')}（{{count}} 项）".format(count=info.get("count", 0)),
        }

    # ------------------------------------------------------------------ 推送

    def push(
        self,
        links: list[str],
        *,
        cid: Optional[str] = None,
        batch_size: Optional[int] = None,
        dry_run: bool = False,
        deadline_seconds: int = _PUSH_DEADLINE_SECONDS,
        max_items: int = _PUSH_MAX_ITEMS,
    ) -> dict:
        """把链接批量推送到 115。

        :param links: 链接或含链接的文本（每个元素都会做一次解析）
        :param dry_run: 只解析不推送（未配置 Cookie 时也能看解析结果）
        :returns: ``{total, processed, remaining, succeeded, failed, skipped, batches, results, message}``
        """
        items = link_utils.make_items(links)
        total = len(items)
        supported = [item for item in items if item.supported]
        skipped_items = [item for item in items if not item.supported]

        result: dict[str, Any] = {
            "total": total,
            "processed": 0,
            "remaining": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": len(skipped_items),
            "batches": 0,
            "results": [],
            "message": "",
        }

        if not total:
            result["message"] = "没有解析到可推送的链接（支持 115 分享链接、磁力、eD2k）"
            return result
        if dry_run:
            result["processed"] = total
            result["batches"] = len(link_utils.split_batches(supported, self.batch_size(batch_size)))
            result["results"] = [
                {"target": item.describe(), "source": item.source, "ok": True, "message": "解析成功（仅测试）"}
                for item in supported
            ]
            result["message"] = f"解析到 {len(supported)} 条可推送链接（{result['batches']} 批），未实际提交"
            return result

        if not supported:
            result["message"] = "解析到的链接暂不支持推送（支持 115 分享链接、磁力、eD2k）"
            return result

        client = self._client(timeout=20)
        target = self.target_cid(cid)
        if not target:
            raise Pan115Error("请先配置「转存文件夹 CID」（转存与离线都需要保存目录）")

        size = self.batch_size(batch_size)
        batches = link_utils.split_batches(supported, size)
        result["batches"] = len(batches)
        deadline = time.monotonic() + max(5, int(deadline_seconds))

        for index, batch in enumerate(batches, start=1):
            for item in batch:
                if result["processed"] >= max_items:
                    break
                if time.monotonic() > deadline:
                    logger.warning("115 推送达到时间预算，提前结束")
                    break
                ok, message = self._push_one(client, item, target)
                if ok:
                    result["succeeded"] += 1
                else:
                    result["failed"] += 1
                result["processed"] += 1
                if len(result["results"]) < 50:
                    # source = 调用方传入的那条链接，供合并下发时把结果回填到任务
                    result["results"].append({
                        "target": item.describe(),
                        "source": item.source,
                        "ok": ok,
                        "message": message,
                    })
                time.sleep(_ITEM_INTERVAL_SECONDS)
            if result["processed"] >= max_items or time.monotonic() > deadline:
                break
            logger.debug(f"115 推送：已完成第 {index}/{len(batches)} 批")

        result["remaining"] = max(0, len(supported) - result["processed"])
        parts = [f"成功 {result['succeeded']}"]
        if result["failed"]:
            parts.append(f"失败 {result['failed']}")
        if result["skipped"]:
            parts.append(f"忽略 {result['skipped']}")
        if result["remaining"]:
            parts.append(f"剩余 {result['remaining']}（可再次点击继续）")
        result["message"] = "推送完成：" + "，".join(parts)
        return result

    def _push_one(self, client: Pan115Client, item: link_utils.PushItem, cid: str) -> tuple[bool, str]:
        """推送单条链接，返回 ``(是否成功, 说明)``。"""
        try:
            if item.kind == "share":
                snap = run_sync(lambda: client.share_snap(item.code, item.password))
                received = run_sync(
                    lambda: client.share_receive(item.code, item.password, snap["file_ids"], cid)
                )
                return True, received.get("message") or f"转存成功（{snap.get('file_count', 0)} 个文件）"
            if item.kind in ("magnet", "ed2k"):
                added = run_sync(lambda: client.offline_add(item.url, cid))
                return True, added.get("message") or "离线任务已提交"
            return False, "不支持的链接类型"
        except Pan115AuthError as err:
            # Cookie 失效属于全局问题，直接中断整次推送更有意义
            raise err
        except Pan115Error as err:
            return False, str(err)
        except Exception as err:  # pragma: no cover - 兜底避免单条异常打断整批
            logger.warning(f"115 推送单条异常：{err}")
            return False, f"异常：{err}"
