"""新增订阅回搜（1.13.39）的回归测试。

为什么单独一个文件
------------------
1.13.34 把「新增订阅回搜」整块下线（连带删掉定时快照对比与 ``cache_subscribe_cron``），
1.13.39 按**纯事件驱动**加回来：宿主广播 ``subscribe.added`` → 防抖合并 → 按片名回搜缓存。
这里锁住四件事：

- 事件入口只在「缓存启用 + 开关打开」时才干活，批量添加被防抖合并成一次回搜；
- 回搜的跳过口径（无链接 / 频道关键词过滤 / 已推送 / 洗版不达标 / 入队失败）；
- 事件自带 ``mediainfo`` 优先，缺失时回查宿主订阅表补片名；
- 开关本身可经 ``/cache/settings`` 读写。

只用 ``object.__new__`` 造最小实例（不碰数据库/宿主），避免把整个缓存链路拖进用例。
"""
import threading
import types

import pytest

from app.plugins.tgmediacenter.modules import cache as cache_module
from app.plugins.tgmediacenter.modules.cache import CacheModule


class _FakePlugin:
    """只提供缓存模块读取配置 / 写配置所需的两样东西。"""

    def __init__(self, config=None):
        self.config = dict(config or {})

    def save_config(self, **kwargs):
        self.config.update(kwargs)


class _FakePipeline:
    """推送流水线替身：记录入队，可按用例指定洗版判定结果。"""

    def __init__(self, *, verdict=None, task_id=1):
        self.verdict = verdict
        self.task_id = task_id
        self.enqueued = []
        self.wash_calls = 0

    def _evaluate_wash(self, *, meta, text, rules, links=None):
        self.wash_calls += 1
        return self.verdict

    @staticmethod
    def _wash_extra(verdict):
        return {"wash": {"keys": [], "profile": {}}}

    def _enqueue_push(self, **kwargs):
        self.enqueued.append(kwargs)
        return self.task_id


def _bare(config=None):
    """最小 CacheModule 实例：只补新代码用到的几个字段。"""
    module = object.__new__(CacheModule)
    module._plugin = _FakePlugin(config)
    module._lock = threading.RLock()
    module._evt_lock = threading.RLock()
    module._evt_timer = None
    module._pending_events = []
    module._listener_installed = False
    module._event_runs = 0
    return module


def _candidate(**overrides):
    item = {
        "chat_id": 100,
        "message_id": 200,
        "text": "青与碧 (2026) S01E01 2160p",
        "title": "青与碧",
        "year": "2026",
        "media_type": "tv",
        "season": 1,
        "episode": 1,
        "links": ["https://115.com/s/abc?password=1"],
    }
    item.update(overrides)
    return item


def _prepare(module, items, *, pipeline=None):
    """把回搜链路上的外部依赖换成替身，返回记录容器。"""
    module.search_by_title = lambda title, year="", limit=200: list(items)
    module.rule_filter_reason = lambda chat_id, text: ""
    module._hit_exists = lambda chat_id, message_id: False
    module._pipeline = lambda: pipeline
    module._notify_search_result = lambda new_count, details: None
    recorded = []
    module._record_hit = lambda item, title, verdict, task_id: recorded.append(
        {"title": title, "task_id": task_id}
    )
    return recorded


# ---------------------------------------------------------------- 开关与事件入口


def test_subscribe_enabled_defaults_to_true():
    """默认开：缓存启用即回搜，用户不需要额外打开什么。"""
    assert _bare({"cache_enabled": True}).subscribe_enabled() is True
    assert _bare({"cache_enabled": True, "cache_subscribe_enabled": False}).subscribe_enabled() is False


def test_event_ignored_when_cache_disabled():
    """缓存总开关关着时不收集事件（省掉无意义的后台回搜）。"""
    module = _bare({})
    module.on_subscribe_event({"subscribe_id": 1, "mediainfo": {"title": "青与碧"}})
    assert module._pending_events == []


def test_event_ignored_when_switch_off():
    """「新增订阅回搜」单独关掉时同样不收集。"""
    module = _bare({"cache_enabled": True, "cache_subscribe_enabled": False})
    module.on_subscribe_event({"subscribe_id": 1, "mediainfo": {"title": "青与碧"}})
    assert module._pending_events == []


def test_event_accepts_object_payload():
    """宿主事件对象（``event_data``）与裸 dict 都要能吃。"""
    module = _bare({"cache_enabled": True})
    module._schedule_event_check = lambda: None
    event = types.SimpleNamespace(event_data={"subscribe_id": 42, "mediainfo": {"title": "青与碧"}})
    module.on_subscribe_event(event)
    assert module._pending_events == [{"id": 42, "info": {"title": "青与碧"}}]


def test_event_ignores_payload_without_id_and_mediainfo():
    """既没 ID 也没 mediainfo 的事件直接丢弃（避免空跑一次回搜）。"""
    module = _bare({"cache_enabled": True})
    module._schedule_event_check = lambda: None
    module.on_subscribe_event({"subscribe_id": 0})
    assert module._pending_events == []


def test_debounce_merges_batch_adds():
    """一次加多个订阅：事件逐条收集，但定时器只重置不新增。"""
    module = _bare({"cache_enabled": True})
    module._schedule_event_check = lambda: None
    for sid in (1, 2, 3):
        module.on_subscribe_event({"subscribe_id": sid, "mediainfo": {"title": f"片{sid}"}})
    assert [event["id"] for event in module._pending_events] == [1, 2, 3]


def test_run_pending_search_dispatches_and_clears():
    """防抖到点：把攒下的事件一次性交给回搜，并清空队列。"""
    module = _bare({"cache_enabled": True})
    seen = []
    module._search_event_subscriptions = lambda events: seen.append(list(events))
    module._pending_events = [{"id": 1, "info": {}}, {"id": 2, "info": {}}]
    module._run_pending_search()
    assert len(seen) == 1 and len(seen[0]) == 2
    assert module._pending_events == []


def test_run_pending_search_swallows_errors():
    """后台线程里的回搜异常不能抛出去（否则定时器线程会带崩日志）。"""
    module = _bare({"cache_enabled": True})

    def boom(events):
        raise RuntimeError("回搜炸了")

    module._search_event_subscriptions = boom
    module._pending_events = [{"id": 1, "info": {}}]
    module._run_pending_search()  # 不抛异常即通过


def test_cancel_event_timer_is_safe_without_timer():
    """插件停止时即便没有待执行定时器也不能报错。"""
    module = _bare({"cache_enabled": True})
    module.cancel_event_timer()
    assert module._evt_timer is None


# ---------------------------------------------------------------- 媒体信息归一


def test_meta_from_mediainfo_maps_host_fields():
    meta = cache_module._meta_from_mediainfo(
        {"title": "青与碧", "year": 2026, "type": "tv", "season": 2}
    )
    assert meta == {"title": "青与碧", "year": "2026", "media_type": "tv", "season": 2}


def test_meta_from_mediainfo_falls_back_to_name_and_begin_season():
    meta = cache_module._meta_from_mediainfo({"name": "青与碧", "begin_season": 1})
    assert meta["title"] == "青与碧"
    assert meta["season"] == 1


def test_meta_from_mediainfo_requires_title():
    assert cache_module._meta_from_mediainfo({"year": 2026}) == {}
    assert cache_module._meta_from_mediainfo(None) == {}


# ---------------------------------------------------------------- 回搜与跳过口径


def test_search_subscription_pushes_candidate():
    """命中候选且无拦截 → 入队一次、记一条流水。"""
    module = _bare({"cache_enabled": True})
    pipeline = _FakePipeline()
    recorded = _prepare(module, [_candidate()], pipeline=pipeline)

    result = module.search_subscription({"title": "青与碧", "year": "2026"})

    assert result["candidates"] == 1
    assert result["pushed"] == 1
    assert len(pipeline.enqueued) == 1
    assert pipeline.enqueued[0]["links"] == ["https://115.com/s/abc?password=1"]
    assert recorded == [{"title": "青与碧", "task_id": 1}]


def test_search_subscription_skips_without_links():
    """无可用链接的缓存消息不进队列。"""
    module = _bare({"cache_enabled": True})
    pipeline = _FakePipeline()
    _prepare(module, [_candidate(links=[])], pipeline=pipeline)

    result = module.search_subscription({"title": "青与碧"})

    assert result["pushed"] == 0
    assert result["reasons"]["无可用链接"] == 1
    assert pipeline.enqueued == []


def test_search_subscription_skips_channel_filtered():
    """频道关键词过滤命中时跳过（与监控同一口径）。"""
    module = _bare({"cache_enabled": True})
    pipeline = _FakePipeline()
    _prepare(module, [_candidate()], pipeline=pipeline)
    module.rule_filter_reason = lambda chat_id, text: "命中排除关键词"

    result = module.search_subscription({"title": "青与碧"})

    assert result["pushed"] == 0
    assert result["reasons"]["命中排除关键词"] == 1


def test_search_subscription_skips_already_pushed():
    """命中流水里已有的（频道 + 消息）不再重复推送。"""
    module = _bare({"cache_enabled": True})
    pipeline = _FakePipeline()
    _prepare(module, [_candidate()], pipeline=pipeline)
    module._hit_exists = lambda chat_id, message_id: True

    result = module.search_subscription({"title": "青与碧"})

    assert result["pushed"] == 0
    assert result["reasons"]["已推送过"] == 1


def test_search_subscription_respects_wash_gate():
    """洗版规则开启且判定不通过 → 跳过，且不会入队。"""
    module = _bare({"cache_enabled": True})
    pipeline = _FakePipeline(verdict={"state": "flat", "reason": "画质不达标"})
    _prepare(module, [_candidate()], pipeline=pipeline)
    module.wash_rules = lambda: {"enabled": True}

    result = module.search_subscription({"title": "青与碧"})

    assert pipeline.wash_calls == 1
    assert result["pushed"] == 0
    assert result["reasons"]["画质不达标"] == 1


def test_search_subscription_skips_when_enqueue_fails():
    """流水线不可用 / 入队失败时计入「入队失败」而不是假装成功。"""
    module = _bare({"cache_enabled": True})
    _prepare(module, [_candidate()], pipeline=None)

    result = module.search_subscription({"title": "青与碧"})

    assert result["pushed"] == 0
    assert result["reasons"]["入队失败"] == 1


def test_search_subscription_without_title_returns_early():
    module = _bare({"cache_enabled": True})
    module.search_by_title = lambda *a, **k: pytest.fail("无片名不应检索")
    assert module.search_subscription({})["pushed"] == 0


# ---------------------------------------------------------------- 事件 → 订阅兜底


def test_event_falls_back_to_subscription_table(monkeypatch):
    """事件只带 subscribe_id 时，从宿主订阅表补片名。"""
    module = _bare({"cache_enabled": True})
    item = types.SimpleNamespace(id=42, name="青与碧", year="2026", type="tv", season=1)
    monkeypatch.setattr(cache_module.matcher_service, "iter_subscriptions", lambda: [item])

    seen = []
    module.search_subscription = lambda meta, trigger="新增订阅": seen.append(meta) or {"pushed": 0}
    module._notify_search_result = lambda new_count, details: None

    module._search_event_subscriptions([{"id": 42, "info": {}}])

    assert seen == [{"title": "青与碧", "year": "2026", "media_type": "tv", "season": 1}]
    assert module.event_runs == 1


def test_event_skips_subscription_without_title(monkeypatch):
    """订阅表也查不到片名时跳过该条，不影响其它订阅。"""
    module = _bare({"cache_enabled": True})
    monkeypatch.setattr(cache_module.matcher_service, "iter_subscriptions", lambda: [])
    module.search_subscription = lambda meta, trigger="新增订阅": pytest.fail("无片名不应回搜")
    module._notify_search_result = lambda new_count, details: None

    assert module._search_event_subscriptions([{"id": 42, "info": {}}])["pushed"] == 0


# ---------------------------------------------------------------- 设置读写


def test_settings_exposes_subscribe_switch():
    module = _bare({"cache_enabled": True, "cache_subscribe_enabled": False})
    assert module.settings()["subscribe_enabled"] is False


def test_save_settings_persists_subscribe_switch():
    module = _bare({"cache_enabled": True})
    module.save_settings({"subscribe_enabled": False})
    assert module._plugin.config["cache_subscribe_enabled"] is False
    assert module.subscribe_enabled() is False
