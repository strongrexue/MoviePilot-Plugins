"""Telegram 运行时：独立线程 asyncio 事件循环 + Telethon 客户端生命周期。

设计要点
--------
1. MoviePilot 主体是同步的，Telethon 需要事件循环；因此本运行时在**独立守护线程**里
   跑一个专属 loop，同步侧通过 ``run_coroutine_threadsafe`` 投递协程。
2. 客户端必须在 loop 内部创建与连接，避免跨 loop 使用内部 Future。
3. ``start()`` / ``stop()`` 幂等且线程安全，插件初始化与停用时可重复调用。
4. telethon 缺失或凭证不全时降级为不可用，不抛异常打断插件加载。
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Callable, Coroutine, Optional

from app.sdk.logging import logger

try:  # 依赖为可选：未安装时插件其余能力仍可加载
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    TELETHON_AVAILABLE = True
except Exception:  # pragma: no cover - 环境缺依赖时的降级分支
    TelegramClient = None  # type: ignore[assignment]
    StringSession = None  # type: ignore[assignment]
    TELETHON_AVAILABLE = False

try:  # Telethon 只在装上 python-socks 时才会真正使用代理
    from python_socks.async_.asyncio import Proxy as _PythonSocksProxy

    PROXY_SUPPORT_AVAILABLE = True
except Exception:  # pragma: no cover - 缺依赖或版本不兼容（3.x 改了模块路径）
    _PythonSocksProxy = None  # type: ignore[assignment]
    PROXY_SUPPORT_AVAILABLE = False


class TelegramRuntime:
    """管理单个插件实例的 Telethon 客户端与专属事件循环。"""

    def __init__(
        self,
        *,
        api_id: Any = None,
        api_hash: str = "",
        session_string: str = "",
        proxy: Optional[dict] = None,
        keep_alive_seconds: int = 60,
        plugin_id: str = "TgMediaCenter",
        on_flood: Optional[Callable[[BaseException], None]] = None,
    ) -> None:
        self._api_id = self._normalize_api_id(api_id)
        self._api_hash = str(api_hash or "").strip()
        self._session_string = str(session_string or "").strip()
        self._proxy = proxy
        self._keep_alive_seconds = max(15, int(keep_alive_seconds or 60))
        self._plugin_id = plugin_id or "TgMediaCenter"
        # FloodWait 上报回调：runtime 不持有插件引用（保持宿主无关），
        # 由调用方注入"把退避记到全局冷却门"的动作。
        self._on_flood = on_flood

        self._lock = threading.RLock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._client: Any = None
        self._keep_alive_task: Any = None
        # 最近一次 start() 未成功的原因：调用方据此给出可读错误，
        # 而不是把"凭证不合法"一律说成"连接超时"。
        self.last_start_error: str = ""

    # ------------------------------------------------------------------ 基础属性

    @staticmethod
    def _normalize_api_id(value: Any) -> Optional[int]:
        """把配置里的 api_id 归一为整数；非法值返回 None。"""
        return TelegramRuntime.parse_api_id(value)

    @staticmethod
    def parse_api_id(value: Any) -> Optional[int]:
        """把配置里的 api_id 归一为整数；非法值（如粘错成密码）返回 None。

        对外暴露：调用方需要在「建运行时之前」就判断出 api_id 不是数字，
        否则会掉进 ``start()`` 的 ``credentials_ready`` 分支静默返回 False，
        再被上层误报成「连接超时」。
        """
        if value is None or value == "":
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def telethon_available() -> bool:
        """当前环境是否具备 telethon 依赖。

        以静态方法暴露：``@property`` 在类上访问会得到 property 对象而不是布尔值，
        容易在组装响应时静默出错。
        """
        return TELETHON_AVAILABLE

    @staticmethod
    def proxy_support_available() -> bool:
        """当前环境是否具备 Telethon 走代理所需的 python-socks。

        Telethon 的代理支持是"软依赖"：缺 ``python-socks`` 时它只打一行
        ``UserWarning`` 就把 proxy 参数丢掉直连出去。宿主机房网络通常直连不通
        Telegram，于是表现为"代理明明配了、却在 45 秒后报连接失败"。
        这里显式探测一次，便于给出可读的提示。
        """
        return PROXY_SUPPORT_AVAILABLE

    def proxy_ignored_hint(self) -> str:
        """代理已配置但环境不支持代理时，返回给用户看的说明；否则返回空串。"""
        if not self._proxy or PROXY_SUPPORT_AVAILABLE:
            return ""
        addr = self._proxy.get("addr") or ""
        port = self._proxy.get("port") or ""
        return (
            f"已配置代理 {addr}:{port}，但当前环境缺少 python-socks（或版本不兼容），"
            "Telethon 会忽略代理直连——请更新/重装插件以安装依赖 python-socks[asyncio]<3"
        )

    @property
    def credentials_ready(self) -> bool:
        """是否已具备启动客户端所需的最小凭证。"""
        return bool(TELETHON_AVAILABLE and self._api_id and self._api_hash)

    def _creds_issue(self) -> str:
        """``credentials_ready`` 为假时的具体原因（用于日志与上层报错）。"""
        if not TELETHON_AVAILABLE:
            return "telethon 依赖未安装"
        if not self._api_hash:
            return "API Hash 为空"
        if not self._api_id:
            return "API ID 缺失或不是纯数字"
        return "凭证不可用"

    @property
    def client(self) -> Any:
        """返回当前客户端（未启动时为 None）。"""
        with self._lock:
            return self._client

    def is_running(self) -> bool:
        """运行时线程是否存活。"""
        with self._lock:
            return bool(self._thread and self._thread.is_alive() and self._loop and not self._loop.is_closed())

    def is_connected(self) -> bool:
        """客户端是否处于连接状态。"""
        client = self.client
        try:
            return bool(client and client.is_connected())
        except Exception:
            return False

    def ensure_connected(self, timeout: int = 12) -> bool:
        """确保客户端处于连接状态；已断开时尝试重连。

        ``start()`` 只保证"线程活着 + 客户端对象已创建"，网络层随时可能掉线
        （代理抖动、Telegram 主动断开）。此时若直接发请求，Telethon 会抛
        ``Cannot send requests while disconnected`` —— 用户看到的就是这个英文报错。
        所以每次真要发请求前，都应先过一遍这里。
        """
        client = self.client
        if client is None:
            return False
        if self.is_connected():
            return True

        with self._lock:
            loop = self._loop
        if loop is None or loop.is_closed():
            return False

        try:
            logger.info(f"[{self._plugin_id}] TG 连接已断开，正在重连")
            self.call(self._reconnect(client), timeout=max(5, int(timeout)))
        except Exception as err:
            logger.warning(f"[{self._plugin_id}] TG 重连失败：{err}")
            return False
        return self.is_connected()

    async def _reconnect(self, client: Any) -> None:
        """先断开再连接：直接 connect() 对"自认为已连接"的陈旧句柄可能空转。"""
        try:
            await client.disconnect()
        except Exception:  # pragma: no cover - 断开失败不影响后续连接
            pass
        await client.connect()

    def current_session_string(self) -> str:
        """导出当前 StringSession，用于持久化；不可用时返回空串。"""
        client = self.client
        if client is None or not TELETHON_AVAILABLE:
            return ""
        try:
            return StringSession.save(client.session) or ""
        except Exception as err:  # pragma: no cover - 会话尚未建立
            logger.debug(f"[{self._plugin_id}] 导出会话失败：{err}")
            return ""

    def update_session_string(self, session_string: str) -> None:
        """在运行时内替换会话串（供后续重连使用）。"""
        self._session_string = str(session_string or "").strip()

    # ------------------------------------------------------------------ 生命周期

    def start(self, connect_timeout: int = 30) -> bool:
        """启动运行时并连接客户端；已启动时直接返回 True。

        :param connect_timeout: 首次连接的时间预算（秒）。同步接口有网关超时上限
            （本插件遇到的 502 即为此），因此调用方应给出比"用户能等"更保守的值。
        """
        with self._lock:
            if self.is_running():
                return True
            if not self.credentials_ready:
                reason = self._creds_issue()
                self.last_start_error = reason
                logger.info(f"[{self._plugin_id}] 未配置 TG 凭证，跳过运行时启动：{reason}")
                return False
            hint = self.proxy_ignored_hint()
            if hint:
                logger.warning(f"[{self._plugin_id}] {hint}")

            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"{self._plugin_id}.telegram",
                daemon=True,
            )
            self._thread.start()

        try:
            client = self.call(self._connect_client(), timeout=max(5, int(connect_timeout)))
        except Exception as err:
            self.last_start_error = str(err)
            logger.warning(f"[{self._plugin_id}] TG 客户端连接失败：{err}")
            if hint:
                logger.warning(f"[{self._plugin_id}] {hint}")
            self.stop()
            return False

        with self._lock:
            self._client = client
        self._start_keep_alive()
        self.prime_updates()
        logger.info(f"[{self._plugin_id}] TG 运行时已启动")
        return True

    def prime_updates(self, limit: int = 200) -> None:
        """连接后拉一轮对话列表：预热实体缓存与频道更新状态（异步，不阻塞启动）。

        Telethon 的已知行为：会话实体缓存里没有的频道，服务端可能不下发
        （或客户端无法解析）新消息更新——刚登录的 StringSession 尤其明显。
        启动后主动 iter_dialogs 一轮，把账号可见的会话灌进缓存，监听才有
        稳定的事件流。
        """
        client = self.client
        if client is None:
            return

        async def _prime() -> None:
            try:
                count = 0
                async for _ in client.iter_dialogs(limit=max(1, int(limit))):
                    count += 1
                logger.info(f"[{self._plugin_id}] TG 对话缓存预热完成（{count} 个会话）")
            except Exception as err:
                # 预热撞 FloodWait 时把退避上报给全局门：否则紧接着的转发会继续撞
                self._report_flood(err)
                logger.warning(f"[{self._plugin_id}] TG 对话缓存预热失败（监听可能收不到部分频道消息）：{err}")

        try:
            self.submit(_prime())
        except Exception as err:
            logger.debug(f"[{self._plugin_id}] 投递对话缓存预热失败：{err}")

    def _report_flood(self, err: BaseException) -> None:
        """把 FloodWait 交给注入的上报回调（记到插件级冷却门）。"""
        callback = self._on_flood
        if not callable(callback):
            return
        try:
            callback(err)
        except Exception:  # pragma: no cover - 上报失败不影响调用方
            pass

    def stop(self) -> None:
        """断开客户端并释放线程与事件循环；可重复调用。"""
        with self._lock:
            client, self._client = self._client, None
            loop, self._loop = self._loop, None
            thread, self._thread = self._thread, None
            self._keep_alive_task = None

        if client is not None and loop is not None and not loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(self._disconnect(client), loop)
                future.result(timeout=15)
            except Exception as err:  # pragma: no cover - 断开阶段的异常只记录
                logger.warning(f"[{self._plugin_id}] 断开 TG 客户端时出错：{err}")

        if loop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=10)
        if loop is not None and not loop.is_closed():
            try:
                loop.close()
            except Exception:
                pass
        logger.info(f"[{self._plugin_id}] TG 运行时已停止")

    # ------------------------------------------------------------------ 协程投递

    def submit(self, coro: Coroutine) -> Future:
        """把协程投递到运行时 loop，返回 concurrent Future。"""
        with self._lock:
            loop = self._loop
        if loop is None or loop.is_closed():
            coro.close()
            raise RuntimeError("Telegram 运行时未启动")
        return asyncio.run_coroutine_threadsafe(coro, loop)

    def call(self, coro: Coroutine, timeout: int = 30) -> Any:
        """同步等待协程结果；超时抛 ``TimeoutError``。"""
        return self.submit(coro).result(timeout=timeout)

    # ------------------------------------------------------------------ 内部实现

    def _run_loop(self) -> None:
        """线程入口：运行专属事件循环直到被停止。"""
        loop = self._loop
        if loop is None:
            return
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            try:
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as err:  # pragma: no cover - 收尾阶段仅记录
                logger.debug(f"[{self._plugin_id}] 事件循环收尾异常：{err}")

    async def _connect_client(self) -> Any:
        """在 loop 内创建并连接客户端。

        重试与超时都压得比较紧：经代理连接 Telegram 时单次握手可能就要十几秒，
        而同步接口有网关超时上限（过长会直接 502，后端却仍在继续执行）。
        """
        session = StringSession(self._session_string) if self._session_string else StringSession()
        client = TelegramClient(
            session,
            self._api_id,
            self._api_hash,
            proxy=self._proxy,
            connection_retries=2,
            retry_delay=1,
            timeout=10,
            device_model="TGMediaCenter",
            system_version="1.0",
            app_version="1.0",
        )
        await client.connect()
        return client

    async def _disconnect(self, client: Any) -> None:
        """取消保活任务并断开客户端。"""
        task = self._keep_alive_task
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass
            self._keep_alive_task = None
        try:
            await client.disconnect()
        except Exception as err:  # pragma: no cover
            logger.debug(f"[{self._plugin_id}] 断开连接异常：{err}")

    def _start_keep_alive(self) -> None:
        """在 loop 内启动保活任务，断线时尝试重连。"""
        with self._lock:
            loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            self._keep_alive_task = asyncio.run_coroutine_threadsafe(self._keep_alive(), loop).result(timeout=5)
        except Exception as err:  # pragma: no cover - 保活属增强能力
            logger.debug(f"[{self._plugin_id}] 启动保活任务失败：{err}")

    async def _keep_alive(self) -> Any:
        """周期性探活；连接掉线时尝试恢复。

        探活只看本地连接标志（不发网络请求，开销可忽略），因此把检查间隔压到
        最长 30 秒，让掉线能尽快自愈，而不是等到用户点按钮时才发现是断的。
        """
        interval = max(10, min(int(self._keep_alive_seconds or 60), 30))
        while True:
            await asyncio.sleep(interval)
            client = self.client
            if client is None:
                return
            try:
                if not client.is_connected():
                    logger.info(f"[{self._plugin_id}] 探活发现 TG 连接已断开，尝试重连")
                    try:
                        await client.disconnect()
                    except Exception:  # pragma: no cover - 陈旧句柄断开可能报错
                        pass
                    await client.connect()
                    logger.info(f"[{self._plugin_id}] TG 重连完成")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                logger.warning(f"[{self._plugin_id}] TG 保活重连失败（下轮继续尝试）：{err}")
