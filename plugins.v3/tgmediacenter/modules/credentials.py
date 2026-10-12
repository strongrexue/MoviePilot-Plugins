"""① TG 核心凭证模块：登录流程、会话持久化、对话列表缓存。

职责边界
--------
- 只管 TG 凭证与客户端运行时，不涉及资源监控 / 转发 / 缓存业务。
- 凭证与对话缓存都通过宿主基类接口读写（``update_config`` / ``save_data``），
  天然按插件实例隔离。
"""
from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Any, Optional

from app.sdk.logging import logger

from ..core import telegram as tg
from ..core.runtime import TelegramRuntime
from ..utils import (
    describe_delivery,
    mask_secret,
    parse_proxy_for_telethon,
    remaining_seconds,
)

_PENDING_KEY = "pending_login"
_DIALOGS_KEY = "dialogs"
_DIALOGS_AT_KEY = "dialogs_updated_at"
# 会话串存在**插件数据**里，不放配置：宿主「保存配置」是整份覆盖，
# 前端表单不含此字段，一旦回写就会把会话清空。
_SESSION_KEY = "tg_session_string"
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

    # ------------------------------------------------------------------ 会话存储

    def _session_from_data(self) -> str:
        """只读取插件数据里的会话串（不回退配置）。"""
        try:
            data = self._plugin.get_data(_SESSION_KEY)
        except Exception as err:  # pragma: no cover - 读取失败按未登录处理
            logger.debug(f"读取 TG 会话失败：{err}")
            return ""
        return data.strip() if isinstance(data, str) else ""

    def session_string(self) -> str:
        """读取已登录会话串（以插件数据为准，兼容旧版本的配置存储）。"""
        return self._session_from_data() or str(self._cfg("tg_session_string", "") or "").strip()

    def migrate_session_from_config(self) -> None:
        """把旧版本存在配置里的会话串迁到插件数据，并从配置中移除。

        配置会被「保存配置」整份覆盖（前端表单不含会话串，回写即清空），
        数据则不受影响 —— 这是会话丢失问题的根治手段。
        """
        legacy = str(self._cfg("tg_session_string", "") or "").strip()
        if not legacy:
            return
        # 注意：这里必须只看数据，不能走 session_string()（它会回退到配置），
        # 否则条件恒为假 → 只删配置键而不落数据，等于把会话直接丢掉。
        if not self._session_from_data():
            self._plugin.save_data(_SESSION_KEY, legacy)
            logger.info(f"[{getattr(self._plugin, '__class__').__name__}] 已把 TG 会话从配置迁移到插件数据")
        drop = getattr(self._plugin, "drop_config", None)
        if callable(drop):
            try:
                drop("tg_session_string")
            except Exception as err:  # pragma: no cover - 清理失败不影响会话可用
                logger.debug(f"从配置中移除旧会话字段失败：{err}")

    # ------------------------------------------------------------------ 运行时

    def api_configured(self) -> bool:
        """是否已配置可用的 TG API 凭证。"""
        return bool(self._cfg("tg_api_id") and self._cfg("tg_api_hash"))

    def ensure_runtime(self, connect_timeout: int = 30) -> TelegramRuntime:
        """按当前配置建立运行时并连接。

        失败原因分三类抛出可展示的错误（而不是统一返回 None 让人猜）：
        凭证缺失 / 依赖缺失 / 连接失败。

        :param connect_timeout: 首次连接的时间预算（秒），调用方按自己的接口
            网关超时上限给值 —— 首次发码要现连 Telegram，经代理可能很慢。
        """
        if not self.api_configured():
            raise tg.TelegramOperationError("请先填写 API ID / API Hash 并保存配置")
        if not TelegramRuntime.telethon_available():
            raise tg.TelegramOperationError("telethon 依赖未安装，请重新安装插件以拉取依赖")

        runtime = self._runtime
        if runtime is not None and runtime.is_running():
            # 线程活着不等于连接可用：网络层随时可能掉线，这里顺手补一次连接，
            # 否则后续请求会直接抛 "Cannot send requests while disconnected"。
            if runtime.ensure_connected(timeout=10):
                return runtime
            logger.warning(f"[{getattr(self._plugin, '__class__').__name__}] TG 连接不可用，重建运行时")
            self._runtime = None
            runtime.stop()

        runtime = TelegramRuntime(
            api_id=self._cfg("tg_api_id"),
            api_hash=self._cfg("tg_api_hash"),
            session_string=self.session_string(),
            proxy=self._resolve_proxy(),
            keep_alive_seconds=int(self._cfg("tg_keep_alive_seconds", 60) or 60),
            plugin_id=getattr(self._plugin, "__class__").__name__,
        )
        if not runtime.start(connect_timeout=connect_timeout):
            self._runtime = None
            raise tg.TelegramOperationError(
                f"连接 Telegram 失败（超过 {connect_timeout} 秒未成功）："
                "请检查服务器网络与代理设置（代理继承 MoviePilot 设置）后重试"
            )
        self._runtime = runtime
        return runtime

    def _call_tg(self, runtime: TelegramRuntime, factory, *, timeout: int, retries: int = 1) -> Any:
        """在运行时上执行 TG 调用；遇到"连接已断开"时重连并重试一次。

        :param factory: 返回协程的可调用对象（协程不可重复使用，必须现造）
        """
        attempt = 0
        while True:
            try:
                return runtime.call(factory(), timeout=timeout)
            except Exception as err:
                if attempt >= retries or not tg.is_disconnected_error(err):
                    raise
                attempt += 1
                logger.warning(f"[{getattr(self._plugin, '__class__').__name__}] TG 连接已断开，重连后重试")
                if not runtime.ensure_connected(timeout=12):
                    raise

    def connect_now(self) -> dict:
        """手动触发一次连接（供界面的「重连」按钮使用），返回最新状态。"""
        self.ensure_runtime(connect_timeout=25)
        return self.status()

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
        try:
            pending_login = self.pending_login()
        except Exception as err:  # pragma: no cover - 展示增强，失败不影响状态
            logger.debug(f"读取待登录上下文失败：{err}")
            pending_login = None

        return {
            # 供前端比对自身构建版本：不一致说明浏览器还缓存着旧的联邦组件
            "plugin_version": str(getattr(self._plugin, "plugin_version", "") or ""),
            "enabled": bool(self._plugin.get_state()),
            "telethon_available": TelegramRuntime.telethon_available(),
            "api_configured": bool(self._cfg("tg_api_id") and self._cfg("tg_api_hash")),
            "session_present": bool(self.session_string()),
            "running": running,
            "connected": connected,
            "authorized": authorized,
            "me": me,
            "phone_masked": mask_secret(self._cfg("tg_phone", "")),
            "dialog_count": len(dialogs),
            "dialogs_updated_at": dialogs_updated_at,
            "pending_login": pending_login,
            "user_cooldown_seconds": int(self._cfg("tg_user_cooldown_seconds", 5) or 5),
            "keep_alive_seconds": int(self._cfg("tg_keep_alive_seconds", 60) or 60),
            "aggregation_window_seconds": float(self._cfg("tg_aggregation_window_seconds", 3.0) or 3.0),
        }

    # ------------------------------------------------------------------ 登录流程

    def send_code(self, phone: str) -> dict:
        """请求验证码并暂存待登录上下文。

        Telegram 对同一号码的发码有最小间隔（``SentCode.timeout``）。间隔内再次请求
        必然失败（表现为 ``SEND_CODE_UNAVAILABLE``），因此在本地先挡住并给出可操作提示，
        而不是把英文报错丢给用户。
        """
        normalized = str(phone or "").strip()
        pending = self._pending()
        # 仅当目标号码与上次发码号码一致时才做冷却拦截，换号不拦
        if normalized and normalized == str(pending.get("phone") or "").strip():
            left = self.resend_in()
            if left > 0:
                raise tg.TelegramOperationError(
                    f"验证码已于 {pending.get('at') or '刚刚'} 发送"
                    f"（{describe_delivery(pending.get('delivery'))}）。"
                    f"请先使用已收到的验证码；{left} 秒后可重新发送。"
                )

        # 首次发码要现连 Telegram（经代理可能十几秒），预算必须压在网关超时之内，
        # 否则前端收到 502 而后端其实把码发出去了，体验极差。
        runtime = self.ensure_runtime(connect_timeout=20)
        try:
            result = self._call_tg(runtime, lambda: tg.send_code(runtime.client, normalized), timeout=25)
        except (FutureTimeoutError, TimeoutError) as err:
            raise tg.TelegramOperationError(
                "请求验证码超时：Telegram 响应过慢（代理可能不稳定）。"
                "若 Telegram 里已收到验证码，请直接输入验证码登录；否则请等待约 10 秒后重试"
            ) from err
        delivery = str(result.get("delivery") or "unknown")
        context = {
            "phone": result.get("phone", ""),
            "phone_code_hash": result.get("phone_code_hash", ""),
            "at": datetime.now().isoformat(timespec="seconds"),
            "delivery": delivery,
            "timeout": int(result.get("timeout") or 0),
        }
        self._plugin.save_data(_PENDING_KEY, context)
        # 记录手机号，便于后续重新发码与状态展示
        self._plugin.save_config(tg_phone=context["phone"])
        return {
            "authorized": False,
            "need_password": False,
            "message": f"验证码{describe_delivery(delivery)}",
            "delivery": delivery,
            "delivery_text": describe_delivery(delivery),
            "resend_in": int(context["timeout"]),
            "phone_masked": mask_secret(context["phone"]),
        }

    def _pending(self) -> dict:
        """读取待验证登录上下文。"""
        data = self._plugin.get_data(_PENDING_KEY) or {}
        return data if isinstance(data, dict) else {}

    def resend_in(self) -> int:
        """距离允许重新发送验证码的剩余秒数（0 表示可立即发送）。"""
        pending = self._pending()
        return remaining_seconds(pending.get("at"), pending.get("timeout"))

    def pending_login(self) -> Optional[dict]:
        """待登录上下文的对外视图（手机号掩码）。

        前端在硬刷新后据此恢复登录向导，避免用户因“页面状态丢失”而重复点发码。
        """
        pending = self._pending()
        if not pending or not pending.get("phone_code_hash"):
            return None
        channel = str(pending.get("delivery") or "unknown")
        return {
            "phone_masked": mask_secret(pending.get("phone")),
            "sent_at": str(pending.get("at") or ""),
            "delivery": channel,
            "delivery_text": describe_delivery(channel),
            "resend_in": self.resend_in(),
        }

    def sign_in(self, phone: str, code: str = "", password: str = "") -> dict:
        """完成登录或两步验证，成功时持久化 StringSession。"""
        runtime = self.ensure_runtime(connect_timeout=20)

        pending = self._pending()
        effective_phone = str(phone or pending.get("phone") or self._cfg("tg_phone", "")).strip()

        try:
            result = self._call_tg(
                runtime,
                lambda: tg.sign_in(
                    runtime.client,
                    phone=effective_phone,
                    code=str(code or "").strip(),
                    # 留空则交回 Telethon 使用客户端内缓存的 hash
                    phone_code_hash=str(pending.get("phone_code_hash") or "") or None,
                    password=str(password or "").strip() or None,
                ),
                timeout=30,
            )
        except (FutureTimeoutError, TimeoutError) as err:
            raise tg.TelegramOperationError(
                "登录请求超时：Telegram 响应过慢，请稍后重试（验证码有效期约 5 分钟）"
            ) from err

        if result.get("authorized"):
            session_string = runtime.current_session_string()
            if not session_string:
                raise tg.TelegramOperationError("登录成功但会话导出失败，请重试")
            # 会话写入插件数据：配置会被「保存配置」整份覆盖，不能放配置里
            self._plugin.save_data(_SESSION_KEY, session_string)
            self._plugin.save_config(tg_phone=effective_phone)
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
        self._plugin.del_data(_SESSION_KEY)
        drop = getattr(self._plugin, "drop_config", None)
        if callable(drop):
            try:
                drop("tg_session_string")
            except Exception as err:  # pragma: no cover
                logger.debug(f"清除旧会话配置字段失败：{err}")
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
        """从 Telegram 重新拉取对话列表并缓存。

        拉取要遍历账号全部对话，经代理时可能耗时较久。但预算必须**小于同步接口的
        网关超时**（否则前端只会收到 502，而后端仍在继续跑），因此这里给出
        "连接 10s + 拉取 45s" 的上限，超时则明确告知原因。
        """
        runtime = self.ensure_runtime(connect_timeout=10)
        if not runtime.is_running():
            raise tg.TelegramOperationError("TG 运行时未运行，请先建立连接后重试")

        try:
            dialogs = self._call_tg(
                runtime,
                lambda: tg.fetch_dialogs(runtime.client, limit=_DIALOG_LIMIT),
                timeout=40,
            )
        except (FutureTimeoutError, TimeoutError) as err:
            raise tg.TelegramOperationError(
                "拉取对话列表超时（40 秒）：账号对话较多或 Telegram/代理响应过慢，请稍后重试"
            ) from err
        except RuntimeError as err:
            # 运行中被停止（例如插件被重新加载）
            raise tg.TelegramOperationError(
                "TG 运行时已停止（可能插件被重载），请重新点「刷新对话列表」"
            ) from err

        self._dialogs = dialogs
        self._plugin.save_data(_DIALOGS_KEY, dialogs)
        self._plugin.save_data(_DIALOGS_AT_KEY, datetime.now().isoformat(timespec="seconds"))
        logger.info(f"[{getattr(self._plugin, '__class__').__name__}] 对话列表已刷新，共 {len(dialogs)} 条")
        return dialogs
