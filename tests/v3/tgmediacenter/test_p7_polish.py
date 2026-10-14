"""P7 打磨测试：通知封装、推送汇总通知、/overview 聚合接口。

覆盖：
- ``core.notify.Notifier``：正常发送 / 按 key 节流 / 渠道缺失 / 渠道异常吞掉 / 开关读取；
- 流水线的 115 转存汇总通知：成功汇总、失败汇总、开关关闭、登录态失效引导与节流、转发不通知；
- ``/overview`` 聚合：各模块状态拼装、单模块异常容错、最近流水（仅监控）排序。

宿主依赖（通知渠道 / 插件 DB / 各模块）用可注入替身驱动，真机行为以部署验证为准。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.plugins.tgmediacenter.controller import api as controller_api
from app.plugins.tgmediacenter.core import pipeline as pipeline_module
from app.plugins.tgmediacenter.core.cooldown import CooldownGate, report_flood_wait
from app.plugins.tgmediacenter.core.notify import Notifier
from app.plugins.tgmediacenter.core.pipeline import MessagePipeline, _looks_like_auth_error
from app.plugins.tgmediacenter.model.hit_log import TgHitLog
from app.plugins.tgmediacenter.model.push_task import STATUS_PENDING, TgPushTask
from app.plugins.tgmediacenter.modules.cache import CACHE_SEARCH_RULE_ID


# ---------------------------------------------------------------------- 测试替身


class FakeDatabase:
    """内存 SQLite 插件数据库句柄（session 是方法，与宿主一致）。"""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        TgHitLog.__table__.create(self.engine)
        TgPushTask.__table__.create(self.engine)
        self._factory = sessionmaker(bind=self.engine)

    def session(self):
        return self._factory()


class FakeNotifyPlugin:
    """只提供配置与通知渠道的插件替身。"""

    def __init__(self, config: Optional[dict] = None, *, posts: bool = True, boom: bool = False) -> None:
        self._config = dict(config or {})
        self.messages: List[Dict[str, str]] = []
        self._posts = posts
        self._boom = boom
        if posts:
            self.post_message = self._post

    def _post(self, title="", text="") -> None:
        if self._boom:
            raise RuntimeError("通知渠道炸了")
        self.messages.append({"title": title, "text": text})

    @property
    def config(self) -> dict:
        return self._config


class ModuleStub:
    """状态模块替身：status() / hits() 都可注入返回值或异常。"""

    def __init__(self, status: Any = None, hits: Any = None) -> None:
        self._status = status if status is not None else {}
        self._hits = hits if hits is not None else {"items": [], "total": 0}
        self.calls: List[str] = []

    def status(self) -> dict:
        self.calls.append("status")
        if isinstance(self._status, Exception):
            raise self._status
        return dict(self._status)

    def hits(self, *, page: int = 1, page_size: int = 20, decision: str = "", kind: str = "monitor") -> dict:
        self.calls.append(f"hits:{kind}")
        if isinstance(self._hits, Exception):
            raise self._hits
        return dict(self._hits)


class OverviewPlugin:
    """/overview 用的插件替身：挂载各模块与插件级属性。"""

    def __init__(self, **modules: Any) -> None:
        self._config = {"notify_on_hit": True, "notify_on_error": False}
        self.plugin_version = "1.7.6"
        self._state = True
        for name, value in modules.items():
            setattr(self, name, value)

    @property
    def config(self) -> dict:
        return self._config

    def get_state(self) -> bool:
        return self._state

    def get_database(self):
        return FakeDatabase()


# ---------------------------------------------------------------------- Notifier


class TestNotifier:
    def test_send_reaches_host_channel(self):
        plugin = FakeNotifyPlugin()
        notifier = Notifier(plugin)
        assert notifier.send("标题", "正文") is True
        assert plugin.messages == [{"title": "标题", "text": "正文"}]
        assert notifier.stats()["sent"] == 1

    def test_empty_title_is_skipped(self):
        plugin = FakeNotifyPlugin()
        assert Notifier(plugin).send("  ", "正文") is False
        assert plugin.messages == []

    def test_dedupe_window_blocks_repeat(self):
        plugin = FakeNotifyPlugin()
        notifier = Notifier(plugin)
        assert notifier.send("登录失效", "重新扫码", key="cred", window=3600) is True
        assert notifier.send("登录失效", "重新扫码", key="cred", window=3600) is False
        assert len(plugin.messages) == 1

    def test_dedupe_without_window_always_sends(self):
        plugin = FakeNotifyPlugin()
        notifier = Notifier(plugin)
        notifier.send("A", "1", key="k")
        notifier.send("A", "2", key="k")
        assert len(plugin.messages) == 2

    def test_missing_channel_is_safe(self):
        plugin = FakeNotifyPlugin(posts=False)
        assert Notifier(plugin).send("标题") is False

    def test_channel_exception_is_swallowed(self):
        plugin = FakeNotifyPlugin(boom=True)
        # 通知渠道抛异常不能影响主流程：返回 False 而不是往外冒
        assert Notifier(plugin).send("标题") is False

    def test_enabled_reads_config_flags(self):
        notifier = Notifier(FakeNotifyPlugin({"notify_on_hit": False, "notify_on_error": "off"}))
        assert notifier.enabled("notify_on_hit", True) is False
        assert notifier.enabled("notify_on_error", True) is False
        assert notifier.enabled("notify_missing_key", True) is True
        assert notifier.enabled("notify_missing_key", False) is False

    def test_reset_clears_throttle(self):
        plugin = FakeNotifyPlugin()
        notifier = Notifier(plugin)
        notifier.send("A", key="k", window=3600)
        notifier.reset()
        assert notifier.send("A", key="k", window=3600) is True
        assert len(plugin.messages) == 2


class TestAuthErrorHint:
    def test_detects_credential_failures(self):
        assert _looks_like_auth_error("115 未启用（请扫码登录）") is True
        assert _looks_like_auth_error("请先验证安全密钥") is True
        assert _looks_like_auth_error("Cookie 失效") is True

    def test_ignores_ordinary_failures(self):
        assert _looks_like_auth_error("链接格式不支持") is False
        assert _looks_like_auth_error("") is False


# ---------------------------------------------------------------------- 退避收口


class _FloodErr(Exception):
    """带 seconds 属性的 FloodWait 替身（真实代码按属性识别，不导入具名类）。"""

    def __init__(self, seconds: int) -> None:
        super().__init__(f"flood wait {seconds}")
        self.seconds = seconds


class TestFloodReporting:
    def test_report_flood_pushes_shared_gate(self):
        gate = CooldownGate(5.0)
        plugin = type("TgMediaCenter", (), {"_gate": gate})()
        seconds = report_flood_wait(plugin, _FloodErr(120))
        assert seconds == 120
        assert gate.flood_remaining() > 100

    def test_report_flood_ignores_other_errors(self):
        gate = CooldownGate(5.0)
        plugin = type("TgMediaCenter", (), {"_gate": gate})()
        assert report_flood_wait(plugin, ValueError("普通错误")) == 0
        assert gate.flood_remaining() == 0

    def test_report_flood_survives_missing_gate(self):
        plugin = type("TgMediaCenter", (), {})()
        assert report_flood_wait(plugin, _FloodErr(30)) == 30

    def test_monitor_reuses_plugin_gate(self):
        """监控模块必须复用插件级冷却门（读/写共享同一份退避状态）。"""
        from app.plugins.tgmediacenter.modules.monitor import MonitorModule

        gate = CooldownGate(7.0)
        plugin = type("TgMediaCenter", (), {"_gate": gate, "config": {}})()
        module = MonitorModule(plugin)
        assert module._gate is gate

    def test_monitor_falls_back_to_own_gate(self):
        from app.plugins.tgmediacenter.modules.monitor import MonitorModule

        plugin = type("TgMediaCenter", (), {"config": {}})()
        module = MonitorModule(plugin)
        assert isinstance(module._gate, CooldownGate)


# ---------------------------------------------------------------------- 推送汇总通知


class NotifyPipelinePlugin:
    """流水线用插件替身：内存库 + 通知渠道 + 配置开关。

    类名即插件 ID（流水线用 ``plugin.__class__.__name__`` 标识自己）。
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        self._config = dict(config or {"notify_on_hit": True, "notify_on_error": True})
        self._db = FakeDatabase()
        self.messages: List[Dict[str, str]] = []
        self._data: Dict[str, Any] = {}

    @property
    def config(self) -> dict:
        return self._config

    def get_database(self):
        return self._db

    def post_message(self, title="", text="") -> None:
        self.messages.append({"title": title, "text": text})

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value


# 类名必须叫 TgMediaCenter：流水线用 __class__.__name__ 当 plugin_id
TgMediaCenter = type("TgMediaCenter", (NotifyPipelinePlugin,), {})


@pytest.fixture
def push_env():
    """带内存库与通知渠道的插件替身（两个通知开关默认都开）。"""
    return TgMediaCenter()


def _seed_task(plugin, *, task_id: int = 1, destination: str = "pan115", title: str = "青与碧 (2026)",
               chat_id: int = -1004316104321, links: Optional[List[str]] = None,
               rule_id: str = "r1") -> Dict[str, Any]:
    """往任务表塞一条待推送任务并返回后端视图 dict。"""
    import json

    if links is None:
        links = ["https://115.com/s/abc"]
    with plugin.get_database().session() as session:
        session.add(TgPushTask(
            id=task_id,
            plugin_id="TgMediaCenter",
            rule_id=rule_id,
            chat_id=chat_id,
            message_id=2234753,
            destination=destination,
            target_id="",
            payload=json.dumps({"links": links, "title": title}, ensure_ascii=False),
            status=STATUS_PENDING,
        ))
        session.commit()
    return {
        "id": task_id,
        "rule_id": rule_id,
        "chat_id": chat_id,
        "message_id": 2234753,
        "destination": destination,
        "payload": {"links": links, "title": title},
        "retries": 0,
    }


class _Target:
    def __init__(self, name: str, ok: bool, message: str, retryable: bool = False,
                 detail: Any = None) -> None:
        self.name = name
        self._ok = ok
        self._message = message
        self._retryable = retryable
        self._detail = detail
        self.calls = 0

    def push(self, payload: Dict[str, Any]):
        from app.plugins.tgmediacenter.destinations.base import PushResult

        self.calls += 1
        return PushResult(ok=self._ok, message=self._message, retryable=self._retryable,
                          detail=self._detail)


def _duplicate_detail(links: List[str]) -> Dict[str, Any]:
    """115 把"已转存过"报成成功时的逐条结果（message 是判定依据）。"""
    return {
        "results": [
            {"source": link, "ok": True, "message": "该分享此前已转存过（跳过）"}
            for link in links
        ]
    }


class TestPushNotifications:
    def test_media_label_format(self):
        assert MessagePipeline._media_label(
            {"title": "美人余", "year": "2026", "season": 1, "episode": 1, "episode_end": 11}
        ) == "美人余 (2026) S01E01-E11"
        assert MessagePipeline._media_label(
            {"title": "青与碧", "year": "2026", "season": 1, "episode": 1}
        ) == "青与碧 (2026) S01E01"
        assert MessagePipeline._media_label({"title": "无季"}) == "无季"
        assert MessagePipeline._media_label(None) == ""
        assert MessagePipeline._media_label({}) == ""

    def test_success_notification_aggregates(self, push_env, monkeypatch):
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="115 推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        assert "115 转存完成" in push_env.messages[0]["title"]
        text = push_env.messages[0]["text"]
        assert "青与碧" in text
        # 1.6.9：转存完成通知末尾附上真实链接，便于直接点开核对
        assert "https://115.com/s/abc" in text
        # 1.6.10：去「· 」前缀、首字对齐，并附来源（测试无对话缓存时退回 chat_id）
        assert "· " not in text
        assert "（1 条链接）" in text
        assert "来源：" in text
        assert str(task["chat_id"]) in text

    def test_success_notification_blocks_and_source(self, push_env, monkeypatch):
        """1.6.10：多条 / 多频道任务各自成块，每块带自己的来源，链接行左对齐。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="115 推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task1 = _seed_task(push_env, task_id=1, chat_id=-1004316104321,
                           title="希望 (2026)", links=["https://115.com/s/aaa"])
        task2 = _seed_task(push_env, task_id=2, chat_id=-1003751539830,
                           title="伟大的长征 (2025)", links=["https://115.com/s/bbb"])
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task1)
        pipeline._execute_push(task2)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        text = push_env.messages[0]["text"]
        assert "· " not in text
        # 两条资源各自成块
        assert "希望 (2026)（1 条链接）" in text
        assert "伟大的长征 (2025)（1 条链接）" in text
        assert "https://115.com/s/aaa" in text
        assert "https://115.com/s/bbb" in text
        # 来源各自的频道 ID（测试无对话缓存，退回原始 ID）
        assert f"来源：{task1['chat_id']}" in text
        assert f"来源：{task2['chat_id']}" in text

    def test_failure_notification_lists_reason(self, push_env, monkeypatch):
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=False, message="115 推送失败：分享链接已失效", retryable=False)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        assert "115 转存失败" in push_env.messages[0]["title"]
        assert "分享链接已失效" in push_env.messages[0]["text"]

    def test_failure_notification_blocks_and_source(self, push_env, monkeypatch):
        """1.6.11：失败通知与成功同款版式——去「· 」、块内含链接 / 来源 / 失败原因。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=False, message="转存失败：分享链接已失效", retryable=False)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env, chat_id=-1004316104321,
                          title="希望 (2026)", links=["https://115.com/s/aaa"])
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        text = push_env.messages[0]["text"]
        assert "· " not in text
        assert "希望 (2026)（1 条链接）" in text
        assert "https://115.com/s/aaa" in text
        assert "来源：-1004316104321" in text
        assert "失败原因：转存失败：分享链接已失效" in text
        # 「链接已失效」是资源本身的问题 ≠ 登录态失效：不能挂重新扫码引导
        # （误挂会触发 6 小时去重，把后续真正的失败通知一起吞掉）
        assert "重新扫码" not in text

    def test_duplicate_notification_marks_already_saved(self, push_env, monkeypatch):
        """1.6.11：115 把「已转存过」报成成功，通知里必须说清"本次未重复保存"。

        1.7.6：标题纯化（不带条数与已转存过标注），只由正文块表达。
        """
        links = ["https://115.com/s/aaa"]
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="推送完成：成功 1",
                         detail=_duplicate_detail(links))
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env, chat_id=-1004316104321, title="希望 (2026)", links=links)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        # 1.7.6：标题纯化，条数/已转存过标注只由正文表达
        assert push_env.messages[0]["title"] == "TG媒体中心 · 115 转存完成"
        text = push_env.messages[0]["text"]
        # 1.7.6：去「已转存到 115（N 条）：」头行，直接从块开始
        assert "已转存到 115" not in text
        assert text.startswith("希望 (2026)")
        assert "已转存过，本次未重复保存" in text
        assert "https://115.com/s/aaa" in text
        assert "来源：-1004316104321" in text

    def test_duplicate_mixed_marks_only_duplicate_block(self, push_env, monkeypatch):
        """1.6.11：混排时只有"已转存过"那块带标注。

        1.7.6：标题纯化后由正文块区分，新转存块不带标注。
        """
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        dup_links = ["https://115.com/s/aaa"]
        target = _Target("pan115", ok=True, message="推送完成：成功 1",
                         detail=_duplicate_detail(dup_links))
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task_dup = _seed_task(push_env, task_id=1, chat_id=-1004316104321,
                              title="希望 (2026)", links=dup_links)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task_dup)
        # 第二条是真正的新转存（无 detail → 无"已转存过"判据）
        fresh = _Target("pan115", ok=True, message="推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: fresh)
        task_new = _seed_task(push_env, task_id=2, chat_id=-1003751539830,
                              title="伟大的长征 (2025)", links=["https://115.com/s/bbb"])
        pipeline._execute_push(task_new)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        # 1.7.6：标题纯化，无「（2 条，其中 1 条已转存过）」标注
        assert push_env.messages[0]["title"] == "TG媒体中心 · 115 转存完成"
        text = push_env.messages[0]["text"]
        assert text.count("已转存过，本次未重复保存") == 1
        assert "已转存到 115" not in text

    def test_credential_failure_adds_guidance_and_throttles(self, push_env, monkeypatch):
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=False, message="115 未启用（请在「115 网盘」面板开启并完成扫码登录）")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert "重新扫码登录" in push_env.messages[0]["text"]

        # 同一故障 6 小时内只提醒一次
        task2 = _seed_task(push_env, task_id=2)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task2)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1

    def test_switches_off_silence_notifications(self, push_env, monkeypatch):
        push_env._config = {"notify_on_hit": False, "notify_on_error": False}
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="115 推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert push_env.messages == []

    def test_retryable_failure_does_not_notify(self, push_env, monkeypatch):
        """重试挂起（未到终态）不该进通知桶，避免同一条反复提醒。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=False, message="网络抖动", retryable=True)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert push_env.messages == []

    def test_push_cycle_flushes_each_round(self, push_env, monkeypatch):
        """_push_cycle 一轮结束后自动发通知（不必手动 flush）。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="115 推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        _seed_task(push_env)
        pipeline._push_cycle()
        assert len(push_env.messages) == 1
        assert "115 转存完成" in push_env.messages[0]["title"]

    def test_forward_failure_not_notified(self, push_env, monkeypatch):
        """通用转发不发通知（通知只覆盖 115 转存），转发结果去详情页看。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("tg_forward", ok=False, message="任务缺少消息定位", retryable=False)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env, destination="tg_forward")
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert push_env.messages == []
        assert pipeline._cycle.get("other_failed") is None

    def test_forward_success_also_not_notified(self, push_env, monkeypatch):
        """转发成功同样不进通知桶（桶里只有 pan115 两类）。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("tg_forward", ok=True, message="转发完成")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env, destination="tg_forward")
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert push_env.messages == []
        assert pipeline._cycle == {"pan115_done": [], "pan115_failed": []}

    def test_cache_search_success_not_notified(self, push_env, monkeypatch):
        """1.7.4：缓存回搜来源的任务不发「115 转存完成」——回搜通知已列过链接，
        完成通知再发一遍就是同样内容重复。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="115 推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env, rule_id=CACHE_SEARCH_RULE_ID)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert push_env.messages == []
        assert pipeline._cycle["pan115_done"] == []
        assert pipeline._cycle["pan115_failed"] == []

    def test_cache_search_failure_still_notified(self, push_env, monkeypatch):
        """1.7.4：回搜任务只免「成功」通知，失败照发（排障不能被静音）。"""
        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=False, message="115 登录态失效，请重新扫码", retryable=False)
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        task = _seed_task(push_env, rule_id=CACHE_SEARCH_RULE_ID)
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        pipeline._flush_notifications()
        assert len(push_env.messages) == 1
        assert "115 转存失败" in push_env.messages[0]["title"]

    def test_cache_search_rule_id_literal_consistent(self):
        """pipeline 里的 cache_search 字面量必须与 modules.cache 的常量同源
        （core 不能反向 import modules，靠测试兜底防漂移）。"""
        from app.plugins.tgmediacenter.modules.cache import CACHE_SEARCH_RULE_ID

        assert pipeline_module._CACHE_SEARCH_RULE_ID == CACHE_SEARCH_RULE_ID

    def test_pipeline_records_transfer_ledger_on_done(self, push_env, monkeypatch):
        """1.7.5：115 转存成功要记入已转存台账（缓存回搜任务同样要记），
        供私聊交互判「已转存过」。"""
        from app.plugins.tgmediacenter.core import transfer_ledger

        pipeline = MessagePipeline(push_env, monitor=None, matcher=None)
        target = _Target("pan115", ok=True, message="115 推送完成：成功 1")
        monkeypatch.setattr(pipeline_module, "resolve_destination",
                            lambda name, plugin, gate=None: target)
        link = "https://115.com/s/swledger1"
        task = _seed_task(push_env, rule_id=CACHE_SEARCH_RULE_ID, links=[link])
        pipeline._cycle = pipeline._empty_cycle()
        pipeline._execute_push(task)
        # 回搜任务不发完成通知，但台账必须已记录
        assert push_env.messages == []
        hits = transfer_ledger.lookup(
            push_env, [transfer_ledger.link_identity("share", code="swledger1")]
        )
        assert hits
        assert "青与碧" in hits[transfer_ledger.link_identity("share", code="swledger1")]["label"]


# ---------------------------------------------------------------------- /overview


def test_overview_aggregates_modules():
    """聚合接口把各模块状态与最近流水一次返回。"""
    hits = {
        "items": [
            {"id": 1, "kind": "monitor", "rule_name": "资源转存", "decision": "hit",
             "created_at": "2026-10-13T14:00:00", "title": "青与碧", "year": "2026"},
        ],
        "total": 1,
    }
    plugin = OverviewPlugin(
        _credentials=ModuleStub({"connected": True, "authorized": True, "phone_masked": "138****8888"}),
        _pan115=ModuleStub({"enabled": True, "authorized": True, "account": "DBOND"}),
        _cache=ModuleStub({"enabled": True, "total": 42, "chats": 2}),
        _monitor=ModuleStub({"enabled": True, "rules_count": 1, "pipeline": {"running": True, "hit": 3}}),
        _forward=ModuleStub({"enabled": True, "rules_count": 2}),
    )
    plugin._monitor.hits = lambda **kwargs: hits

    response = controller_api.api_overview(plugin)
    data = response.data
    assert data.plugin_version == "1.7.6"
    assert data.enabled is True
    assert data.tg.connected is True
    assert data.pan115.account == "DBOND"
    assert data.cache.total == 42
    assert data.monitor.pipeline.running is True
    assert data.forward.rules_count == 2
    assert data.notify.on_hit is True and data.notify.on_error is False


def test_overview_recent_hits_monitor_only():
    """最近流水只取监控（转发流水不进总览），按时间倒序且不超过上限。"""
    monitor_hits = {
        "items": [
            {"id": 1, "kind": "monitor", "created_at": "2026-10-13T10:00:00"},
            {"id": 3, "kind": "monitor", "created_at": "2026-10-13T12:00:00"},
        ],
        "total": 2,
    }
    forward_hits = {
        "items": [
            {"id": 2, "kind": "forward", "created_at": "2026-10-13T13:00:00"},
        ],
        "total": 1,
    }
    plugin = OverviewPlugin(
        _credentials=ModuleStub({}),
        _pan115=ModuleStub({}),
        _cache=ModuleStub({}),
        _monitor=ModuleStub({"pipeline": {}}),
        _forward=ModuleStub({}),
    )
    plugin._monitor.hits = lambda **kwargs: monitor_hits
    plugin._forward.hits = lambda **kwargs: forward_hits

    data = controller_api.api_overview(plugin).data
    ids = [item.id for item in data.recent_hits]
    assert ids == [3, 1]
    assert all(item.kind == "monitor" for item in data.recent_hits)


def test_overview_survives_module_failure():
    """单个模块异常不影响整页：该块回落默认值，其余照常返回。"""
    plugin = OverviewPlugin(
        _credentials=ModuleStub(status=RuntimeError("TG 模块炸了")),
        _pan115=ModuleStub({"enabled": True, "account": "DBOND"}),
        _cache=ModuleStub(status=Exception("缓存炸了")),
        _monitor=ModuleStub({"pipeline": {}}, hits={"items": [], "total": 0}),
        _forward=ModuleStub({}, hits=RuntimeError("流水炸了")),
    )

    data = controller_api.api_overview(plugin).data
    assert data.tg.connected is False          # 异常块回落默认
    assert data.pan115.account == "DBOND"      # 正常块照常
    assert data.cache.enabled is False
    assert data.recent_hits == []


def test_overview_handles_missing_modules():
    """模块未初始化（None）时接口仍要能返回，详情页不至于整页 500。"""
    plugin = OverviewPlugin(_credentials=None, _pan115=None, _cache=None, _monitor=None, _forward=None)
    data = controller_api.api_overview(plugin).data
    assert data.tg.connected is False
    assert data.recent_hits == []
