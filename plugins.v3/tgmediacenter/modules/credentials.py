"""① TG 核心凭证模块：登录流程、会话持久化、对话列表缓存。

职责边界
--------
- 只管 TG 凭证与客户端运行时，不涉及资源监控 / 转发 / 缓存业务。
- 凭证与对话缓存都通过宿主基类接口读写（``update_config`` / ``save_data``），
  天然按插件实例隔离。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.sdk.logging import logger

from ..core import telegram as tg
from ..core.runtime import TelegramRuntime
from ..utils import mask_secret, parse_proxy_for_telethon

_PENDING_KEY = "pending_login"
_DIALOGS_KEY = "dialogs"
_DIALOGS_AT_KEY = "dialogs_updated_at"
_DIALOG_LIMIT = 800


class CredentialsModule:
    """TG 凭证与运行时编排。"""

    def __init__(self, plugin: Any) -> None:
        self._plugin = plugin
        self._runtime: Optional[TelegramRuntime] = None
        self._me: Optional[dict] = None
        self._dialogs: Optional[list[dict]] = None

    # ------------------------------------------------------------------ 配置读取

    @property
    def _config(self) -> dict:
        return getattr(self._plugin, "config", {}) or {}

    def _cfg(self, key: str, default: Any = None) -> Any:
        value = self._config.get(key)
        return default if value is None else value

    # ------------------------------------------------------------------ 运行时

    def ensure_runtime(self) -> Optional[TelegramRuntime]:
        """按当前配置建立运行时；凭证不全或依赖缺失时返回 None。"""
        api_id = self._cfg("tg_api_id")
        api_hash = self._cfg("tg_api_hash")
        if not api_id or not api_hash:
            return None

        runtime = self._runtime
        if runtime is not None and runtime.is_running():
            return runtime

        runtime = TelegramRuntime(
            api_id=api_id,
            api_hash=api_hash,
            session_string=self._cfg("tg_session_string", ""),
            proxy=self._resolve_proxy(),
            keep_alive_seconds=int(self._cfg("tg_keep_alive_seconds", 60) or 60),
            plugin_id=getattr(self._plugin, "__class__").__name__,
        )
        if not runtime.start():
            self._runtime = None
            return None
        self._runtime = runtime
        return runtime

    def _resolve_proxy(self) -> Optional[dict]:
        """继承宿主代理配置（settings.PROXY），转成 Telethon 需要的结构。"""
        try:
            from app.sdk.config import settings
        except Exception as err:  # pragma: no cover - 宿主接口缺失时直连
            logger.debug(f"读取宿主代理配置失败，按直连处理：{err}")
            return None
        try:
            return parse_proxy_for_telethon(getattr(settings, "PROXY", None))
        except Exception as err:  # pragma: no cover
            logger.warning(f"解析宿主代理配置失败，按直连处理：{err}")
            return None

    def stop(self) -> None:
        """停止运行时（插件停用或重载时调用）。"""
        runtime, self._runtime = self._runtime, None
        if runtime is not None:
            runtime.stop()
        self._me = None

    # ------------------------------------------------------------------ 状态

    def status(self) -> dict:
        """汇总 TG 凭证与运行时状态，供前端展示。

        任何子项查询失败都不应让整个状态接口失败，因此逐项兜底。
        """
        runtime = self._runtime
        running = bool(runtime and runtime.is_running())
        connected = bool(runtime and runtime.is_connected())
        authorized = False
        me = self._me
        if running:
            try:
                authorized = bool(runtime.call(tg.is_authorized(runtime.client), timeout=8))
            except Exception as err:
                logger.debug(f"查询 TG 授权状态失败：{err}")
                authorized = False
            if authorized and me is None:
                try:
                    me = runtime.call(tg.get_me_info(runtime.client), timeout=8)
                    self._me = me
                except Exception as err:
                    logger.debug(f"查询 TG 账号信息失败：{err}")

        try:
            dialogs = self.cached_dialogs()
        except Exception as err:  # pragma: no cover - 读取本地缓存异常不应影响状态
            logger.debug(f"读取对话缓存失败：{err}")
            dialogs = []
        try:
            dialogs_updated_at = str(self._plugin.get_data(_DIALOGS_AT_KEY) or "")
        except Exception:  # pragma: no cover
            dialogs_updated_at = ""

        return {
            "enabled": bool(self._plugin.get_state()),
            "telethon_available": TelegramRuntime.telethon_available(),
            "api_configured": bool(self._cfg("tg_api_id") and self._cfg("tg_api_hash")),
            "session_present": bool(str(self._cfg("tg_session_string", "") or "").strip()),
            "running": running,
            "connected": connected,
            "authorized": authorized,
            "me": me,
            "phone_masked": mask_secret(self._cfg("tg_phone", "")),
            "dialog_count": len(dialogs),
            "dialogs_updated_at": dialogs_updated_at,
            "user_cooldown_seconds": int(self._cfg("tg_user_cooldown_seconds", 5) or 5),
            "keep_alive_seconds": int(self._cfg("tg_keep_alive_seconds", 60) or 60),
            "aggregation_window_seconds": float(self._cfg("tg_aggregation_window_seconds", 3.0) or 3.0),
        }

    # ------------------------------------------------------------------ 登录流程

    def send_code(self, phone: str) -> dict:
        """请求验证码并暂存 phone_code_hash 与手机号。"""
        runtime = self.ensure_runtime()
        if runtime is None:
            raise tg.TelegramOperationError("请先填写 API ID / API Hash 并安装 telethon 依赖")

        result = runtime.call(tg.send_code(runtime.client, phone), timeout=40)
        self._plugin.save_data(_PENDING_KEY, {
            "phone": result.get("phone", ""),
            "phone_code_hash": result.get("phone_code_hash", ""),
            "at": datetime.now().isoformat(timespec="seconds"),
        })
        # 记录手机号，便于后续重新发码与状态展示
        self._plugin.save_config(tg_phone=result.get("phone", ""))
        return {"authorized": False, "need_password": False,
                "message": "验证码已发送，请查看 Telegram"}

    def _pending(self) -> dict:
        """读取待验证登录上下文。"""
        data = self._plugin.get_data(_PENDING_KEY) or {}
        return data if isinstance(data, dict) else {}

    def sign_in(self, phone: str, code: str = "", password: str = "") -> dict:
        """完成登录或两步验证，成功时持久化 StringSession。"""
        runtime = self.ensure_runtime()
        if runtime is None:
            raise tg.TelegramOperationError("请先填写 API ID / API Hash 并安装 telethon 依赖")

        pending = self._pending()
        effective_phone = str(phone or pending.get("phone") or self._cfg("tg_phone", "")).strip()

        result = runtime.call(
            tg.sign_in(
                runtime.client,
                phone=effective_phone,
                code=str(code or "").strip(),
                phone_code_hash=str(pending.get("phone_code_hash") or ""),
                password=str(password or "").strip() or None,
            ),
            timeout=40,
        )

        if result.get("authorized"):
            session_string = runtime.current_session_string()
            if not session_string:
                raise tg.TelegramOperationError("登录成功但会话导出失败，请重试")
            self._plugin.save_config(
                tg_session_string=session_string,
                tg_phone=effective_phone,
            )
            runtime.update_session_string(session_string)
            self._me = None
            self._plugin.del_data(_PENDING_KEY)
            try:
                self._me = runtime.call(tg.get_me_info(runtime.client), timeout=10)
            except Exception as err:  # pragma: no cover - 账号信息属展示增强
                logger.debug(f"登录后读取账号信息失败：{err}")
            logger.info(f"[{getattr(self._plugin, '__class__').__name__}] TG 登录成功")
            result["me"] = self._me
        return result

    def logout(self) -> dict:
        """注销会话并清除本地会话串。"""
        runtime = self._runtime
        if runtime is not None and runtime.is_running():
            try:
                runtime.call(tg.log_out(runtime.client), timeout=20)
            except Exception as err:
                logger.warning(f"TG 注销请求失败，仍将清除本地会话：{err}")
        self.stop()
        self._plugin.save_config(tg_session_string="")
        self._plugin.del_data(_PENDING_KEY)
        return {"authorized": False, "need_password": False, "message": "已退出登录"}

    # ------------------------------------------------------------------ 对话缓存

    def cached_dialogs(self) -> list[dict]:
        """读取本地缓存的对话列表。"""
        if self._dialogs is None:
            data = self._plugin.get_data(_DIALOGS_KEY)
            self._dialogs = data if isinstance(data, list) else []
        return self._dialogs

    def refresh_dialogs(self) -> list[dict]:
        """从 Telegram 重新拉取对话列表并缓存。"""
        runtime = self.ensure_runtime()
        if runtime is None:
            raise tg.TelegramOperationError("TG 客户端未就绪，无法刷新对话列表")
        dialogs = runtime.call(tg.fetch_dialogs(runtime.client, limit=_DIALOG_LIMIT), timeout=60)
        self._dialogs = dialogs
        self._plugin.save_data(_DIALOGS_KEY, dialogs)
        self._plugin.save_data(_DIALOGS_AT_KEY, datetime.now().isoformat(timespec="seconds"))
        logger.info(f"[{getattr(self._plugin, '__class__').__name__}] 对话列表已刷新，共 {len(dialogs)} 条")
        return dialogs
