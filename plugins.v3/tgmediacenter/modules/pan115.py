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
from ..utils import run_sync

_STATE_KEY = "pan115_state"
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

    def _client(self, timeout: int = 20) -> Pan115Client:
        """构造 115 客户端；未配置 Cookie 时给出可操作错误。"""
        cookie = self._cfg("pan115_cookie", "")
        client = Pan115Client(cookie, proxies=self._resolve_proxy(), timeout=timeout)
        if not client.cookie_configured:
            raise Pan115Error(
                "未配置有效的 115 Cookie：请从浏览器复制 115 登录后的 Cookie（需含 UID 与 CID）并保存"
            )
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
        cookie = self._cfg("pan115_cookie", "")
        try:
            configured = Pan115Client(cookie).cookie_configured
        except Exception:  # pragma: no cover - Cookie 解析异常按未配置处理
            configured = False
        return {
            "enabled": self.enabled(),
            "cookie_configured": configured,
            "authorized": bool(state.get("authorized")),
            "account": str(state.get("account") or ""),
            "space": state.get("space") if isinstance(state.get("space"), dict) else {},
            "offline": state.get("offline") if isinstance(state.get("offline"), dict) else {"available": False, "text": "未检测"},
            "last_check": str(state.get("at") or ""),
            "target_cid": self.target_cid(),
            "batch_max_size": self.batch_size(),
        }

    # ------------------------------------------------------------------ 账号与授权

    def check(self) -> dict:
        """测试连接：读取账号、空间配额与离线配额，并写入状态缓存。"""
        client = self._client(timeout=20)

        account = run_sync(client.user_info)
        try:
            space = run_sync(client.space_info)
        except Pan115Error as err:
            logger.warning(f"读取 115 空间配额失败：{err}")
            space = {}
        # 离线配额在 115 侧不稳定，失败不影响整体判定
        offline = run_sync(client.offline_quota)

        self._save_state(
            authorized=True,
            account=str(account.get("user_name") or account.get("user_id") or ""),
            account_id=str(account.get("user_id") or ""),
            space=space,
            offline=offline,
        )
        logger.info(f"[{getattr(self._plugin, '__class__').__name__}] 115 连接正常：{account.get('user_name') or account.get('user_id')}")
        return self.status()

    def logout(self) -> dict:
        """清除 Cookie 与状态缓存。"""
        self._plugin.save_config(pan115_cookie="")
        try:
            self._plugin.del_data(_STATE_KEY)
        except Exception as err:  # pragma: no cover
            logger.debug(f"清除 115 状态缓存失败：{err}")
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
                {"target": item.describe(), "ok": True, "message": "解析成功（仅测试）"} for item in supported
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
                    result["results"].append({"target": item.describe(), "ok": ok, "message": message})
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
