"""手动回搜（1.13.38）：「胖虎 片名」→ 候选列表 → 点选推送。"""
from __future__ import annotations

import pytest

from app.plugins.tgmediacenter.modules.manual_search import (
    MARK_FLAT,
    MARK_LOWER,
    MARK_UNKNOWN,
    MARK_UPGRADE,
    ManualSearchModule,
)
from app.plugins.tgmediacenter.services import quality as quality_service


class _Event:
    def __init__(self, data: dict) -> None:
        self.event_data = data


class FakeCache:
    def __init__(self, rows=None, baselines=None, names=None) -> None:
        self.rows = list(rows or [])
        self.baselines = dict(baselines or {})
        self.names = dict(names or {})
        self.searched: list = []
        self.baseline_calls: list = []

    def search_by_title(self, title, limit=200):
        self.searched.append(title)
        return list(self.rows)

    def dialog_names(self):
        return dict(self.names)

    def wash_rules(self):
        return quality_service.default_rules()

    def wash_baselines(self, title, year=None, media_type="", season=None):
        self.baseline_calls.append((title, year, media_type, season))
        return dict(self.baselines)


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list = []

    def _enqueue_push(self, **kwargs):
        self.calls.append(kwargs)
        return len(self.calls)


class FakePlugin:
    def __init__(self, cache=None, pipeline=None, config=None) -> None:
        self._cache = cache
        self._pipeline = pipeline
        self._config = dict(config or {})
        self._data: dict = {}
        self.messages: list = []

    @property
    def config(self) -> dict:
        return self._config

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value

    def post_message(self, title="", text="", **kwargs) -> None:
        self.messages.append({"title": title, "text": text, "kwargs": kwargs})


def _row(episode, quality, *, size="8.2GB", message_id=100, links=None, title="凡人修仙传"):
    return {
        "title": title,
        "year": "2026",
        "season": 1,
        "episode": episode,
        "episode_end": None,
        "media_type": "tv",
        "text": f"{title} S01E{episode:02d} {quality} WEB-DL H.265 💾 大小: {size}",
        "links": links or [f"ed2k://|file|X.S01E{episode:02d}.{quality}.mkv|8589934592|abc{episode}|/"],
        "chat_id": -1004316104321,
        "message_id": message_id,
    }


def _module(cache=None, pipeline=None, config=None):
    plugin = FakePlugin(cache=cache, pipeline=pipeline, config=config)
    module = ManualSearchModule(plugin)
    # 宿主里插件 ID 就是类名（TgMediaCenter）；测试替身类名不同，这里对齐
    module._plugin_id = lambda: "TgMediaCenter"
    return module, plugin


# ------------------------------------------------------------------ 触发

def test_trigger_prefix_consumes_message(monkeypatch):
    module, plugin = _module(cache=FakeCache())
    started = []
    monkeypatch.setattr(module, "_run_search", lambda title, userid, channel="": started.append((title, userid)))

    consumed = module.handle_text(_Event({"text": "胖虎 凡人修仙传", "userid": "u1"}))

    assert consumed is True
    assert started == [("凡人修仙传", "u1")]


def test_trigger_without_title_replies_usage():
    module, plugin = _module(cache=FakeCache())

    assert module.handle_text(_Event({"text": "胖虎"})) is True
    assert plugin.messages and "用法" in plugin.messages[0]["text"]


def test_plain_text_is_not_consumed():
    module, _plugin = _module(cache=FakeCache())

    assert module.handle_text(_Event({"text": "这是一条普通消息"})) is False


def test_disabled_switch_ignores_trigger():
    module, _plugin = _module(cache=FakeCache(), config={"manual_search_enabled": False})

    assert module.handle_text(_Event({"text": "胖虎 凡人修仙传"})) is False


def test_trigger_survives_leading_question_mark(monkeypatch):
    """宿主把「纯片名」当媒体搜索吃掉，带标点的句子才会落到插件。"""
    module, _plugin = _module(cache=FakeCache())
    started = []
    monkeypatch.setattr(module, "_run_search", lambda title, userid, channel="": started.append((title, userid)))

    consumed = module.handle_text(_Event({"text": "？胖虎 凡人修仙传", "userid": "u1"}))

    assert consumed is True
    assert started == [("凡人修仙传", "u1")]


def test_trigger_tolerates_trailing_punctuation(monkeypatch):
    module, _plugin = _module(cache=FakeCache())
    started = []
    monkeypatch.setattr(module, "_run_search", lambda title, userid, channel="": started.append((title, userid)))

    assert module.handle_text(_Event({"text": "胖虎 凡人修仙传？", "userid": "u1"})) is True
    assert started == [("凡人修仙传", "u1")]


def test_match_trigger_variants():
    from app.plugins.tgmediacenter.modules.manual_search import match_trigger

    assert match_trigger("？胖虎 凡人修仙传") == "凡人修仙传"
    assert match_trigger("胖虎：凡人修仙传") == "凡人修仙传"
    assert match_trigger("胖虎") == ""
    assert match_trigger("这是一条普通消息") is None


def test_command_entry_starts_search(monkeypatch):
    """/胖虎 片名：宿主命令 → PluginAction 事件里的 arg_str。"""
    module, _plugin = _module(cache=FakeCache())
    started = []
    monkeypatch.setattr(module, "_run_search", lambda title, userid, channel="": started.append((title, userid)))

    consumed = module.handle_command(_Event({
        "action": "manual_search", "arg_str": "凡人修仙传", "user": "u1",
    }))

    assert consumed is True
    assert started == [("凡人修仙传", "u1")]


def test_command_entry_ignores_other_actions():
    module, _plugin = _module(cache=FakeCache())

    assert module.handle_command(_Event({"action": "other", "arg_str": "凡人修仙传"})) is False


def test_command_entry_without_title_replies_usage():
    module, plugin = _module(cache=FakeCache())

    assert module.handle_command(_Event({"action": "manual_search", "arg_str": "  "})) is True
    assert plugin.messages and "用法" in plugin.messages[0]["text"]


def test_plugin_declares_slash_command(monkeypatch):
    """插件必须在宿主命令表里暴露 /胖虎，否则纯文本会被媒体搜索吃掉。

    测试环境里 ``app`` 是桩包（没有 ``app.schemas.types``），这里注入一个假的事件类型
    模块，验证命令声明的形状（真实宿主里同一个键就是 ``EventType.PluginAction``）。
    """
    import sys
    import types

    from app.plugins.tgmediacenter import TgMediaCenter

    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []
    fake_types = types.ModuleType("app.schemas.types")

    class _EventType:
        PluginAction = "plugin.action"

    fake_types.EventType = _EventType
    monkeypatch.setitem(sys.modules, "app.schemas", schemas)
    monkeypatch.setitem(sys.modules, "app.schemas.types", fake_types)

    commands = TgMediaCenter.get_command(TgMediaCenter.__new__(TgMediaCenter))

    assert commands, "get_command() 至少要声明一条命令"
    command = commands[0]
    assert command["cmd"] == "/胖虎"
    assert command["data"]["action"] == "manual_search"
    assert command["event"] == "plugin.action"


# ------------------------------------------------------------------ 检索 / 分组

def test_lists_every_version_per_episode():
    """1.13.38：不再「同集只留最优」——每条资源都要列出来，只做标注。"""
    cache = FakeCache(rows=[
        _row(5, "1080p", message_id=101),
        _row(5, "2160p", message_id=102),
        _row(6, "720p", message_id=103),
    ])
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    # 三条都在（同集的两个版本各占一条），不再被合并
    assert len(items) == 3
    assert {item["message_id"] for item in items} == {101, 102, 103}
    # 排序仍是画质高的在前
    assert items[0]["profile"]["resolution"] == "2160p"
    assert items[0]["message_id"] == 102


def test_items_sort_by_quality_then_size():
    """1.13.38 起不再按「值不值得升级」排序，只按画质、体积排。"""
    cache = FakeCache(rows=[
        _row(5, "2160p", message_id=101),
        _row(6, "1080p", message_id=102),
    ])
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    assert len(items) == 2
    assert items[0]["profile"]["resolution"] == "2160p"
    assert items[1]["profile"]["resolution"] == "1080p"


def test_items_marked_against_baseline():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    key = quality_service.baseline_key("凡人修仙传", "2026", 1, 5)
    cache.baselines = {key: quality_service.parse_quality("1080p WEB-DL H.265")}
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    assert len(items) == 1
    assert items[0]["mark"] == MARK_UPGRADE
    assert "分辨率" in items[0]["reason"] or "更优" in items[0]["reason"]


def test_lower_when_baseline_is_better():
    """基线更好时标「↓ 更低」，而不是含混的「= 持平」。"""
    cache = FakeCache(rows=[_row(5, "1080p", message_id=101)])
    key = quality_service.baseline_key("凡人修仙传", "2026", 1, 5)
    cache.baselines = {key: quality_service.parse_quality("2160p WEB-DL H.265")}
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    assert items and items[0]["mark"] == MARK_LOWER
    assert "分辨率" in items[0]["reason"]


def test_unknown_mark_when_no_baseline():
    """没有基线时标「? 无基线」，不能冒充「可升级」。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=101)])
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    assert items and items[0]["mark"] == MARK_UNKNOWN


def test_rows_without_links_are_skipped():
    row = _row(5, "2160p")
    row["links"] = []
    cache = FakeCache(rows=[row])
    module, _plugin = _module(cache=cache)

    assert module._build_items(cache.rows, cache.wash_rules(), cache) == []


# ------------------------------------------------------------------ 渲染

def test_buttons_carry_request_and_index():
    module, _plugin = _module(cache=FakeCache())
    chunk = [{"profile": {"resolution": "2160p"}} for _ in range(3)]

    rows = module._buttons("abc123", 0, 2, chunk, 0)

    flat = [button for row in rows for button in row]
    prefix = "[PLUGIN]TgMediaCenter|"
    assert {"text": "1", "callback_data": prefix + "s:abc123:0"} in flat
    assert any(button["callback_data"] == prefix + "p:abc123:next" for button in flat)
    # 「全部可升级」「取消」按钮已按用户要求去掉（m24027）
    assert not any(button["callback_data"].startswith(prefix + "a:") for button in flat)
    assert not any(button["callback_data"].startswith(prefix + "x:") for button in flat)
    # 每个按钮都必须带宿主要求的 [PLUGIN] 前缀，否则会被判「回调数据格式错误」
    assert all(button["callback_data"].startswith(prefix) for button in flat)
    # callback_data 必须能塞进 TG 的 64 字节限制（前缀已计入）
    assert all(len(button["callback_data"].encode("utf-8")) <= 64 for button in flat)


def test_render_lists_items_without_judgement():
    """列表只给画质和体积，不再替用户判断值不值得升级（m24027）。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    key = quality_service.baseline_key("凡人修仙传", "2026", 1, 5)
    cache.baselines = {key: quality_service.parse_quality("1080p WEB-DL H.264")}
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "items": items, "page": 0, "message_id": 0, "chat_id": 0}

    module._send_page("abc123", request, edit=False)

    assert plugin.messages
    body = plugin.messages[0]["text"]
    assert "S01E05" in body
    assert "2160p" in body
    assert "值得升级" not in plugin.messages[0]["title"]
    # 1.13.38 v4：标题第一行只放片名（+年份，若请求里带 year）（用户 m24546）
    assert plugin.messages[0]["title"].startswith("凡人修仙传")
    assert "手动回搜" not in plugin.messages[0]["title"]
    for mark in (MARK_UPGRADE, MARK_FLAT, MARK_LOWER, MARK_UNKNOWN):
        assert mark not in body


def test_items_carry_dialog_source():
    """列表每行带来源频道名（1.13.38 排版：序号后面跟【频道名】）。"""
    cache = FakeCache(
        rows=[_row(5, "2160p", message_id=102)],
        names={-1004316104321: "资源转存"},
    )
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    assert items[0]["source"] == "资源转存"


def test_line_shows_source_and_clickable_title():
    """两行格式：第一行来源，第二行集数 · 🌟 画质 · 💾 体积（用户 m24638）。"""
    module, _plugin = _module(cache=FakeCache())
    item = {
        "profile": {"resolution": "2160p", "size_mb": 8192.0},
        "links": ["https://115.com/s/abc123?password=x"],
        "season": 1,
        "episode": 5,
        "episode_end": None,
        "source": "资源转存",
        "mark": MARK_UPGRADE,
    }

    head, detail = module._line(1, item).splitlines()

    assert head == "1. 🌐 资源转存"
    assert detail.startswith("[S01E05](https://115.com/s/abc123?password=x)")
    assert "🌟 2160p" in detail
    assert "💾 8.0GB" in detail
    assert MARK_UPGRADE not in detail


def test_line_keeps_ed2k_link_as_plain_text():
    """ed2k 链接带 ``|``，MarkdownV2 语法会断，只能当纯文本（m24060）。"""
    module, _plugin = _module(cache=FakeCache())
    ed2k = ("ed2k://|file|尚公主(2026)(tmdbid=286171).S01E12.WEB-DL.2160p.HDR."
            "H265.DDP Atmos.mkv|5443030315|e9502baaad5cc56d0d0823bd6fb206ae|/")
    item = {
        "profile": {"resolution": "2160p", "size_mb": 5120.0},
        "links": [ed2k],
        "season": 1,
        "episode": 12,
        "episode_end": None,
        "source": "资源转存",
    }

    line = module._line(1, item)

    assert line.splitlines()[1].startswith("S01E12")
    assert "](" not in line
    assert "ed2k://" not in line


def test_line_without_source_or_link_stays_plain():
    module, _plugin = _module(cache=FakeCache())
    item = {
        "profile": {"resolution": "1080p"},
        "links": [],
        "season": 1,
        "episode": 2,
        "episode_end": None,
        "source": "",
        "mark": MARK_FLAT,
    }

    line = module._line(3, item)

    assert line.startswith("3. S01E02")
    assert "🌐" not in line
    assert "](" not in line


def test_line_plain_when_channel_is_wechat():
    """企业微信应用消息是 msgtype=text，不认 Markdown，链接不能加。"""
    module, _plugin = _module(cache=FakeCache())
    item = {
        "profile": {"resolution": "2160p", "size_mb": 8192.0},
        "links": ["https://115.com/s/abc123?password=x"],
        "season": 1,
        "episode": 5,
        "episode_end": None,
        "source": "资源转存",
        "mark": MARK_UPGRADE,
    }

    line = module._line(1, item, markdown=False)

    assert line.splitlines()[1].startswith("S01E05")
    assert "](" not in line
    assert "https://115.com" not in line


def test_page_uses_plain_lines_for_wechat_request():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "items": items, "page": 0,
               "message_id": 0, "chat_id": 0, "poster": "", "channel": "微信"}

    module._send_page("abc123", request, edit=False)

    # 微信只有一条消息：标题+页码+列表+操作提示都在里面
    body = plugin.messages[-1]["text"]
    assert "](" not in body
    assert "S01E05" in body


def test_wechat_sends_single_news_message_with_poster():
    """微信一条图文消息：海报在上，标题/条数页码/列表/操作提示依次在下（m24613）。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "year": "2026", "items": items, "page": 0,
               "message_id": 0, "chat_id": 0,
               "poster": "https://image.tmdb.org/t/p/w500/poster.jpg", "channel": "微信"}

    module._send_page("abc123", request, edit=False)

    assert len(plugin.messages) == 1
    message = plugin.messages[0]
    assert message["title"] == "凡人修仙传 (2026)"
    assert message["kwargs"]["image"] == "https://image.tmdb.org/t/p/w500/poster.jpg"
    lines = message["text"].splitlines()
    assert lines[0] == "共 1 条"
    assert lines[1].startswith("1. S01E05")
    assert lines[-1].startswith("回复 /胖虎 1 推送第 1 条")


def test_wechat_list_has_no_buttons():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "items": items, "page": 0,
               "message_id": 0, "chat_id": 0, "poster": "", "channel": "微信"}

    module._send_page("abc123", request, edit=False)

    assert "buttons" not in plugin.messages[-1]["kwargs"]


def test_page_attaches_poster_image():
    """有海报就走图文（Telegram send_photo / 微信 news 卡）。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {
        "title": "凡人修仙传", "items": items, "page": 0,
        "message_id": 0, "chat_id": 0,
        "poster": "https://image.tmdb.org/t/p/w500/poster.jpg",
    }

    module._send_page("abc123", request, edit=False)

    assert plugin.messages[0]["kwargs"]["image"] == "https://image.tmdb.org/t/p/w500/poster.jpg"


def test_page_without_poster_stays_text_only():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "items": items, "page": 0,
               "message_id": 0, "chat_id": 0, "poster": ""}

    module._send_page("abc123", request, edit=False)

    assert "image" not in plugin.messages[0]["kwargs"]


def test_tg_page_has_no_operation_hint():
    """TG 下方有数字键盘和翻页按钮，正文不再写任何操作提示（用户 m24703）。"""
    cache = FakeCache(rows=[_row(episode, "2160p", message_id=100 + episode)
                            for episode in range(1, 12)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "items": items, "page": 0,
               "message_id": 0, "chat_id": 0, "poster": ""}

    module._send_page("abc123", request, edit=False)

    body = plugin.messages[0]["text"]
    assert body.splitlines()[0] == "共 11 条 · 第 1/2 页"
    assert "/胖虎" not in body
    assert body.splitlines()[-1].startswith("8. ")


def test_single_page_has_no_footer():
    """只有一页时 TG 不带尾行（没有可翻的页，也没必要提示点按钮）。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    request = {"title": "凡人修仙传", "items": items, "page": 0,
               "message_id": 0, "chat_id": 0, "poster": ""}

    module._send_page("abc123", request, edit=False)

    lines = plugin.messages[0]["text"].splitlines()
    assert lines[0] == "共 1 条"
    assert lines[-1].startswith("1. S01E05")


def test_search_stores_poster_once(monkeypatch):
    """海报在发起回搜时查一次并落进请求，翻页不再重复查。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, _plugin = _module(cache=cache)
    calls = []
    monkeypatch.setattr(module, "_poster", lambda title: calls.append(title) or "https://img/p.jpg")

    request_id = module._search_and_send("凡人修仙传", "u1", "Telegram")

    assert calls == ["凡人修仙传"]
    assert module._get_request(request_id)["poster"] == "https://img/p.jpg"


def _store_request(module, items):
    module._save_state({"req001": {
        "title": "凡人修仙传", "items": items, "page": 0, "created_at": __import__("time").time(),
        "userid": "u1", "message_id": 0, "chat_id": 0,
    }})


def test_action_select_enqueues_only_that_item():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102), _row(6, "2160p", message_id=103)])
    pipeline = FakePipeline()
    module, _plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "s:req001:0"}))

    assert len(pipeline.calls) == 1
    call = pipeline.calls[0]
    assert call["destination"] == "pan115"
    assert call["links"] == items[0]["links"]
    assert call["extra"]["wash"]["episodes"] == [5]
    # 请求保留，只记「已推送」——之后还能继续翻页 / 点其它集
    request = module._get_request("req001")
    assert request is not None
    assert request["pushed"] == [0]


def test_action_all_pushes_only_upgradable():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    key5 = quality_service.baseline_key("凡人修仙传", "2026", 1, 5)
    key6 = quality_service.baseline_key("凡人修仙传", "2026", 1, 6)
    cache.baselines = {
        key5: quality_service.parse_quality("1080p WEB-DL H.264"),
        key6: quality_service.parse_quality("2160p WEB-DL H.265"),
    }
    cache.rows.append(_row(6, "1080p", message_id=103))
    pipeline = FakePipeline()
    module, _plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "a:req001"}))

    assert len(pipeline.calls) == 1
    assert pipeline.calls[0]["extra"]["wash"]["episodes"] == [5]


def test_action_cancel_drops_request():
    module, _plugin = _module(cache=FakeCache())
    _store_request(module, [])

    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "x:req001"}))

    assert module._get_request("req001") is None


def test_action_ignores_other_plugin():
    pipeline = FakePipeline()
    module, _plugin = _module(cache=FakeCache(), pipeline=pipeline)
    _store_request(module, [])

    module.handle_action(_Event({"plugin_id": "OtherPlugin", "text": "a:req001"}))

    assert pipeline.calls == []


def test_command_number_pushes_that_item():
    """/胖虎 1：命令参数是序号，不是片名（用户 m24335 报的 bug）。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    pipeline = FakePipeline()
    module, _plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    consumed = module.handle_command(_Event({
        "action": "manual_search", "arg_str": "1", "user": "u1",
    }))

    assert consumed is True
    assert len(pipeline.calls) == 1


def test_command_number_does_not_start_search(monkeypatch):
    """/胖虎 3 不能拿去当片名检索（会把「3」搜出一堆无关整包）。"""
    module, _plugin = _module(cache=FakeCache())
    started = []
    monkeypatch.setattr(module, "_run_search", lambda title, userid, channel="": started.append(title))

    module.handle_command(_Event({"action": "manual_search", "arg_str": "3", "user": "u1"}))

    assert started == []


def test_command_number_without_request_hints():
    module, plugin = _module(cache=FakeCache())

    assert module.handle_command(_Event({
        "action": "manual_search", "arg_str": "1", "user": "u1",
    })) is True
    assert "没有正在进行的回搜" in plugin.messages[0]["text"]


def test_command_n_turns_page():
    cache = FakeCache(rows=[_row(episode, "2160p", message_id=100 + episode)
                            for episode in range(1, 12)])
    module, plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    assert module.handle_command(_Event({
        "action": "manual_search", "arg_str": "n", "user": "u1",
    })) is True
    assert module._get_request("req001")["page"] == 1
    assert plugin.messages


def test_command_cancel_drops_request():
    module, plugin = _module(cache=FakeCache())
    _store_request(module, [])

    assert module.handle_command(_Event({
        "action": "manual_search", "arg_str": "取消", "user": "u1",
    })) is True
    assert module._get_request("req001") is None
    assert "已取消" in plugin.messages[0]["title"]


def test_trigger_with_number_routes_to_reply():
    """「？胖虎 1」也要按命令处理，不能当片名搜。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    pipeline = FakePipeline()
    module, _plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    assert module.handle_text(_Event({"text": "？胖虎 1", "userid": "u1"})) is True
    assert len(pipeline.calls) == 1


def test_bare_number_is_not_consumed():
    """裸数字被宿主 interaction.py:289 吃掉，插件收不到，也不该认。"""
    module, _plugin = _module(cache=FakeCache())
    _store_request(module, [])

    assert module.handle_text(_Event({"text": "1", "userid": "u1"})) is False


def test_latest_request_falls_back_to_channel():
    """命令事件的 ``user`` 与消息事件的 ``userid`` 未必同名，同渠道也要认。"""
    module, _plugin = _module(cache=FakeCache())
    module._save_state({"req001": {
        "title": "凡人修仙传", "items": [], "page": 0,
        "created_at": __import__("time").time(),
        "userid": "DBONDL", "channel": "Telegram",
        "message_id": 0, "chat_id": 0,
    }})

    found = module._latest_request("7782217255", "Telegram")

    assert found and found[0] == "req001"


def test_latest_request_rejects_other_channel_and_user():
    module, _plugin = _module(cache=FakeCache())
    module._save_state({"req001": {
        "title": "凡人修仙传", "items": [], "page": 0,
        "created_at": __import__("time").time(),
        "userid": "someone", "channel": "微信",
        "message_id": 0, "chat_id": 0,
    }})

    assert module._latest_request("u1", "Telegram") is None


def test_push_receipt_looks_like_resource_card():
    """推送回执照宿主「📥 开始下载」那张卡：标题 + emoji 字段行。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)],
                      names={-1004316104321: "资源转存"})
    pipeline = FakePipeline()
    module, plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    module._push_items("req001", [0], channel="Telegram")

    card = plugin.messages[-1]
    assert card["title"] == "📥 开始推送\n凡人修仙传 (2026)"
    assert "🕒 时间：" in card["text"]
    assert "🌐 来源：资源转存" in card["text"]
    assert "🎬 集数：S01E05" in card["text"]
    assert "🌟 质量：2160p" in card["text"]
    assert "💾 大小：8.2GB" in card["text"]
    assert "🔗 链接：" in card["text"]


def test_wash_extra_carries_profile_and_episode():
    item = {
        "key": "凡人修仙传|2026|1|5|",
        "profile": {"resolution": "2160p"},
        "episode": 5,
    }

    extra = ManualSearchModule._wash_extra(item)

    assert extra["wash"]["keys"] == ["凡人修仙传|2026|1|5|"]
    assert extra["wash"]["profile"] == {"resolution": "2160p"}
    assert extra["wash"]["episodes"] == [5]


def test_search_reports_empty_cache():
    cache = FakeCache(rows=[])
    module, plugin = _module(cache=cache)

    assert module._search_and_send("不存在的片", "u1") is None
    assert "没有找到" in plugin.messages[0]["title"]


# ------------------------------------------------------ 整包候选（1.13.38 修）
def _pack_row(episode, episode_end, quality, *, size="9.2GB", message_id=200,
              title="凡人修仙传"):
    row = _row(episode, quality, size=size, message_id=message_id, title=title)
    row["episode_end"] = episode_end
    row["text"] = (
        f"{title} S01E{episode:02d}-E{episode_end:02d} {quality} WEB-DL H.265"
        f" 💾 大小: {size}"
    )
    return row


def test_pack_compares_against_per_episode_baseline():
    """整包要按集摊体积再逐集比，不能因为「整包体积更大」就放行。"""
    cache = FakeCache(rows=[_pack_row(1, 4, "2160p HDR EAC3", size="9.2GB")])
    cache.baselines = {
        quality_service.baseline_key("凡人修仙传", "2026", 1, ep):
            quality_service.parse_quality("凡人修仙传 S01E01 2160p HDR DTS 19.6GB")
        for ep in range(1, 5)
    }
    module, _plugin = _module(cache=cache)

    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    assert items, "整包候选不该被丢掉"
    item = items[0]
    assert item["mark"] == MARK_LOWER
    assert len(item["keys"]) == 4
    # 9.2GB 摊到 4 集 = 2.3GB/集，远小于基线 19.6GB
    assert all(abs(profile["size_mb"] - 2355.2) < 0.5
               for profile in item["profiles"].values())


def test_pack_pushes_carry_every_episode_key():
    cache = FakeCache(rows=[_pack_row(1, 3, "2160p HDR EAC3", size="9.2GB")])
    cache.baselines = {
        quality_service.baseline_key("凡人修仙传", "2026", 1, ep):
            quality_service.parse_quality("凡人修仙传 S01E01 1080p WEB-DL 2GB")
        for ep in range(1, 4)
    }
    module, _plugin = _module(cache=cache)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)

    extra = module._wash_extra(items[0])

    assert extra["wash"]["keys"] == [
        quality_service.baseline_key("凡人修仙传", "2026", 1, ep) for ep in range(1, 4)
    ]
    assert extra["wash"]["episodes"] == [1, 2, 3]
    assert set(extra["wash"]["profiles"]) == set(extra["wash"]["keys"])


# ------------------------------------------------------ 推送后列表仍可用
def test_push_keeps_request_and_blocks_double_push():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102),
                            _row(6, "2160p", message_id=103)])
    pipeline = FakePipeline()
    module, _plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "s:req001:0"}))
    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "s:req001:0"}))

    assert len(pipeline.calls) == 1, "同一条不该重复入队"
    assert module._get_request("req001") is not None


def test_push_after_push_can_still_page():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    pipeline = FakePipeline()
    module, plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "s:req001:0"}))
    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "p:req001:next"}))

    titles = [message["title"] for message in plugin.messages]
    assert not any("已结束" in title or "过期" in title for title in titles)


def test_action_all_skips_already_pushed():
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    key5 = quality_service.baseline_key("凡人修仙传", "2026", 1, 5)
    cache.baselines = {key5: quality_service.parse_quality("1080p WEB-DL H.264")}
    pipeline = FakePipeline()
    module, plugin = _module(cache=cache, pipeline=pipeline)
    items = module._build_items(cache.rows, cache.wash_rules(), cache)
    _store_request(module, items)

    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "a:req001"}))
    module.handle_action(_Event({"plugin_id": "TgMediaCenter", "text": "a:req001"}))

    assert len(pipeline.calls) == 1
    assert any("没有待推送" in message["title"] for message in plugin.messages)


def test_line_marks_pushed_item():
    item = {"profile": {"resolution": "2160p", "size_mb": 2048}, "mark": MARK_UPGRADE,
            "season": 1, "episode": 5}
    module, _plugin = _module(cache=FakeCache())

    assert "✓ 已推送" in module._line(1, item, pushed=True)
    assert "✓ 已推送" not in module._line(1, item, pushed=False)


# ------------------------------------------------- 渠道隔离（不串台）
def test_search_request_records_event_channel(monkeypatch):
    """请求要记住来源渠道，后续翻页/推送回复才不会广播到其它渠道。"""
    cache = FakeCache(rows=[_row(5, "2160p", message_id=102)])
    module, _plugin = _module(cache=cache)

    module.handle_text(_Event({"text": "？胖虎 凡人修仙传", "userid": "u1",
                               "channel": "Telegram"}))

    import time as _time
    for _ in range(100):
        request_id = module._latest_request("u1")
        if request_id:
            break
        _time.sleep(0.02)
    assert request_id is not None
    _rid, request = request_id
    assert request["channel"] == "Telegram"


def test_post_passes_channel_to_host(monkeypatch):
    """发消息必须带上 channel，否则宿主的 check_message 会广播到所有渠道。"""
    class _FakeChannel:
        def __init__(self, value):
            self.value = value

    class _FakeTypes:
        NotificationChannel = _FakeChannel

    import sys
    import types as _types

    fake_schemas = _types.ModuleType("app.schemas")
    fake_schemas.__path__ = []
    fake_types = _types.ModuleType("app.schemas.types")
    fake_types.NotificationChannel = _FakeChannel
    monkeypatch.setitem(sys.modules, "app.schemas", fake_schemas)
    monkeypatch.setitem(sys.modules, "app.schemas.types", fake_types)

    module, plugin = _module(cache=FakeCache())
    module._post(title="t", text="x", channel="Telegram")

    assert plugin.messages[-1]["kwargs"].get("channel") is not None
    assert plugin.messages[-1]["kwargs"]["channel"].value == "Telegram"


def test_post_without_channel_stays_backward_compatible():
    module, plugin = _module(cache=FakeCache())

    module._post(title="t", text="x")

    assert "channel" not in plugin.messages[-1]["kwargs"]
