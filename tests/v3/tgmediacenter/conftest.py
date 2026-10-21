"""tgmediacenter 测试的环境补齐（只影响本插件，不碰另外两个插件）。

为什么需要
----------
插件的运行时依赖是**可选**的：``telethon`` 缺失时整层降级为不可用，
``apscheduler`` 缺失时 ``get_service()`` 降级为空列表。这是产品上正确的取舍
（插件装到没有这些包的宿主上仍能加载），但它让单测的结果取决于**跑测试的机器上
装没装包**——同一份用例在 CI、宿主 venv、裸 venv 里表现不同，非常容易被误读成
「代码坏了」。

所以这里统一两条约定：

1. **依赖可用性一律由用例显式打桩**：涉及 ``telethon`` 的断言用 ``monkeypatch``
   把 ``TELETHON_AVAILABLE`` / ``sys.modules['telethon']`` 置成期望状态，不再靠
   「本机恰好装没装」推断。
2. **只有纯调度类型（``CronTrigger``）在这里补桩**：它只负责校验 cron 表达式，
   没有任何网络或状态行为，补一个最小实现就能让 ``get_service()`` 的注册逻辑
   在任何环境下都被真正覆盖（与 embycovercenter 用例里的做法一致）。

这样同一份用例在三种环境里结果一致：
- 裸 venv（无 telethon / apscheduler）；
- 装了依赖的 venv；
- 宿主 venv（有宿主模块，但未必装 telethon）。
"""
import sys
import types

import pytest


def _ensure_apscheduler() -> None:
    """缺 ``apscheduler`` 时补一个最小桩，保证 ``get_service()`` 可被真实执行。"""
    try:
        import apscheduler.triggers.cron  # noqa: F401
        return
    except Exception:  # pragma: no cover - 只在缺依赖的环境走到
        pass

    root = types.ModuleType("apscheduler")
    triggers = types.ModuleType("apscheduler.triggers")
    cron = types.ModuleType("apscheduler.triggers.cron")

    class CronTrigger:
        """最小替身：只保留 ``from_crontab`` 的字段数校验语义。"""

        def __init__(self, expression: str = "") -> None:
            self.expression = expression

        @classmethod
        def from_crontab(cls, expression, timezone=None):
            fields = str(expression or "").split()
            if len(fields) != 5:
                raise ValueError(
                    f"Wrong number of fields; got {len(fields)}, expected 5"
                )
            return cls(str(expression))

    cron.CronTrigger = CronTrigger
    root.triggers = triggers
    triggers.cron = cron
    sys.modules.setdefault("apscheduler", root)
    sys.modules.setdefault("apscheduler.triggers", triggers)
    sys.modules.setdefault("apscheduler.triggers.cron", cron)


_ensure_apscheduler()


# --------------------------------------------------------------- telethon 打桩
# 这三类断言必须能在「没装 telethon」的机器上跑：
#   - api_id / api_hash 归一与凭证就绪判断（依赖 TELETHON_AVAILABLE）；
#   - ``_register_handler`` 注册给 telethon 的回调形状（调用时 import events）；
#   - 代理被忽略的提示文案（依赖 PROXY_SUPPORT_AVAILABLE）。
# 它们测的都是**本插件自己的分支逻辑**，与 telethon 是否真装无关，所以统一用
# 下面这个 fixture 把依赖"置为已安装"，避免结果随机器而变。

_FAKE_TELETHON_MODULES = (
    "telethon",
    "telethon.errors",
    "telethon.sessions",
    "telethon.events",
)


class _FakeNewMessage:
    """``events.NewMessage`` 的最小替身：只作为事件过滤器传给 add_event_handler。"""


def _install_fake_telethon(monkeypatch) -> None:
    """在 ``sys.modules`` 里临时装一套最小 telethon。

    必须用 ``monkeypatch.setitem`` 而不是直接赋值：真实环境里可能已经装了
    telethon，直接覆盖会把它泄漏给同一会话里后面的用例（跨文件污染）。
    """
    root = types.ModuleType("telethon")
    errors = types.ModuleType("telethon.errors")
    sessions = types.ModuleType("telethon.sessions")
    events = types.ModuleType("telethon.events")

    class _FakeFloodWaitError(Exception):
        def __init__(self, seconds: int = 0) -> None:
            super().__init__(f"flood wait {seconds}s")
            self.seconds = seconds

    class _FakeStringSession:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def save(self) -> str:
            return self.value

    class _FakeTelegramClient:
        """占位客户端：真实网络行为不在单测覆盖范围内。"""

    errors.FloodWaitError = _FakeFloodWaitError
    sessions.StringSession = _FakeStringSession
    events.NewMessage = _FakeNewMessage
    root.errors = errors
    root.sessions = sessions
    root.events = events
    root.TelegramClient = _FakeTelegramClient

    for name, module in zip(_FAKE_TELETHON_MODULES, (root, errors, sessions, events)):
        monkeypatch.setitem(sys.modules, name, module)


@pytest.fixture()
def telethon_available(monkeypatch):
    """把 telethon 视为已安装（同时修正 runtime 模块里的可用性探针与符号）。

    用例显式声明它，就不再依赖「跑测试的机器装没装 telethon」。
    """
    _install_fake_telethon(monkeypatch)
    from app.plugins.tgmediacenter.core import runtime as runtime_module

    fake = sys.modules["telethon"]
    monkeypatch.setattr(runtime_module, "TELETHON_AVAILABLE", True)
    # 缺依赖时模块级符号被置成了 None；一并换成桩，让"已安装"这个状态在
    # 模块命名空间里也自洽（例如 current_session_string / _connect_client）。
    monkeypatch.setattr(runtime_module, "TelegramClient", fake.TelegramClient)
    monkeypatch.setattr(runtime_module, "StringSession", fake.sessions.StringSession)
    return runtime_module
