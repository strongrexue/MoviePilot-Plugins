"""缓存类推送的「频道级过滤」（1.13.30）。

背景
----
缓存回搜 / 存量补扫 / 洗版回搜此前**完全不经过**监控规则的关键词闸：判定链只有
「有链接 → 未推送过 → 媒体库缺失」就入队，推送时用虚拟规则 id（``cache_search`` /
``cache_backfill``）落流水。于是「关键词=电影、排除词=iso」这类**频道级意图**
对缓存翻出来的资源一律失效——同一个频道里已订阅的电视剧会从缓存路径被推走，
而用户明明只想要电影。

作用域（本文件重点锁定）：过滤**只看这条缓存消息来自哪个频道**，取该频道启用的
监控规则逐条套用与实时监控同一套判定（逻辑零排除词 → 逻辑一关键词），任一规则
放行即放行。它表达的是「这个频道只给我电影」，不是全局「我不要电视剧」：
同一部剧若能从别的频道补档，照旧会推。

覆盖：
- 电视剧被拦 / 电影放行 / 排除词优先 / 带电影页脚的电视剧照旧放行
- 频道无监控规则 → 不误杀（只缓存不监控）
- 多规则任一放行即放行；停用规则不参与；别的频道的规则不跨界
- 无监控模块时容错放行
"""
from __future__ import annotations

from app.plugins.tgmediacenter.modules.cache import CacheModule
from app.plugins.tgmediacenter.modules.monitor import MonitorModule

CHAT = -1001234567890
OTHER_CHAT = -100999

MOVIE_TEXT = "电影 | 沙丘2 | 2024 | 4K HDR\nhttps://115.com/s/aaa"
TV_TEXT = "电视剧 | 某某某 | S01E01 | 1080P\nhttps://115.com/s/bbb"
MOVIE_ISO_TEXT = "电影 | 沙丘2 | 2024 | iso 原盘\nhttps://115.com/s/ccc"


class _Plugin:
    """最小插件替身：只提供缓存模块与监控模块用到的配置 / 数据接口。"""

    def __init__(self, config: dict | None = None) -> None:
        self._config = dict(config or {})
        self._data: dict = {}
        self.plugin_id = "tgmediacenter"

    @property
    def config(self) -> dict:
        return self._config

    def save_config(self, **patch) -> None:
        self._config.update(patch)

    def get_data(self, key, default=None):
        return self._data.get(key, default)

    def save_data(self, key, value) -> None:
        self._data[key] = value


def _module(rules: list | None) -> CacheModule:
    plugin = _Plugin({"monitor_rules": rules or []})
    plugin._monitor = MonitorModule(plugin)
    return CacheModule(plugin)


def _rule(**overrides) -> dict:
    rule = {
        "id": "r1",
        "name": "只推电影",
        "source_ids": [CHAT],
        "destination": "none",
        "enabled": True,
        "match_custom_keywords": True,
        "custom_keywords": ["电影"],
        "exclude_keywords": ["iso"],
    }
    rule.update(overrides)
    return rule


# ---------------------------------------------------------------------- 核心过滤


def test_tv_is_blocked_by_movie_keyword():
    """电视剧（正文无「电影」）必须被拦下——这是本次要修的现象。"""
    module = _module([_rule()])
    assert "关键词" in module.rule_filter_reason(CHAT, TV_TEXT)


def test_movie_passes():
    module = _module([_rule()])
    assert module.rule_filter_reason(CHAT, MOVIE_TEXT) == ""


def test_exclude_keyword_blocks_even_when_whitelist_hits():
    """排除词优先：命中 iso 的电影也要拦（与实时监控逻辑零口径一致）。"""
    module = _module([_rule()])
    assert "iso" in module.rule_filter_reason(CHAT, MOVIE_ISO_TEXT)


def test_tv_with_movie_footer_passes():
    """正文里带「电影」字样的电视剧照旧放行——关键词仍是全文子串，未改变语义。"""
    module = _module([_rule()])
    text = "电视剧 | 某某某 | S01E02\n更多电影电视剧资源请关注本频道"
    assert module.rule_filter_reason(CHAT, text) == ""


# ---------------------------------------------------------------------- 作用域边界


def test_chat_without_monitor_rule_is_not_filtered():
    """只缓存不监控的频道：无规则约束，保持旧行为（不误杀）。"""
    module = _module([])
    assert module.rule_filter_reason(CHAT, TV_TEXT) == ""


def test_other_chat_rule_does_not_apply():
    """别的频道的规则不能拦本频道的资源——过滤是频道级的，不是全局的。"""
    module = _module([_rule(source_ids=[OTHER_CHAT])])
    assert module.rule_filter_reason(CHAT, TV_TEXT) == ""


def test_rule_without_whitelist_passes_everything():
    """规则没启用关键词过滤时白名单不设限（仅排除词生效）。"""
    module = _module([_rule(match_custom_keywords=False)])
    assert module.rule_filter_reason(CHAT, TV_TEXT) == ""
    assert "iso" in module.rule_filter_reason(CHAT, MOVIE_ISO_TEXT)


def test_any_rule_passing_is_enough():
    """多规则时任一规则放行即放行——与实时监控「任一规则命中即推」语义一致。"""
    module = _module([
        _rule(id="r1"),
        _rule(id="r2", match_custom_keywords=False, custom_keywords=[]),
    ])
    assert module.rule_filter_reason(CHAT, TV_TEXT) == ""


def test_all_rules_blocked_returns_reason():
    module = _module([
        _rule(id="r1"),
        _rule(id="r2", custom_keywords=["纪录片"]),
    ])
    assert module.rule_filter_reason(CHAT, TV_TEXT) != ""


def test_disabled_rule_is_ignored():
    """停用中的规则不参与过滤（与 rules_for_chat 口径一致）。"""
    module = _module([_rule(enabled=False)])
    assert module.rule_filter_reason(CHAT, TV_TEXT) == ""


# ---------------------------------------------------------------------- 容错


def test_missing_monitor_module_passes():
    plugin = _Plugin({})
    module = CacheModule(plugin)
    assert module.rule_filter_reason(CHAT, TV_TEXT) == ""
