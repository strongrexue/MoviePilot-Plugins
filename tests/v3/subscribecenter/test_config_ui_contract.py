"""配置页结构契约：这些名字被删掉时，界面上会整块消失或直接崩溃。

都是真机踩过的坑：

- ``switchRows`` 被误删 → 「写入与调度」渲染时 ``undefined.filter`` 抛错，
  宿主把插件弹窗直接关掉（看起来像「点一下就退出」）
- ``VTabs`` / ``VTab`` 宿主未注册为全局组件 → 豆瓣分区的两个 tab 静默不渲染
- 豆瓣分区的外层 ``<template>`` 必须在 ``routes`` tab 之后闭合，
  否则会把后面所有分区包进 ``v-if="activeSection === 'douban'"``
"""
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
CONFIG = (
    Path(__file__).resolve().parents[3]
    / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Config.vue"
)


def _text() -> str:
    if not CONFIG.exists():
        pytest.skip("前端源码缺失")
    return CONFIG.read_text(encoding="utf-8")


def test_switch_rows_is_declared_and_rendered():
    """``switchRows`` 必须声明且被 filter 渲染（否则写入与调度崩）。"""
    text = _text()
    assert "const switchRows = [" in text, "switchRows 定义丢失（会导致写入与调度崩溃）"
    assert "switchRows.filter(" in text, "switchRows 应过滤后逐项渲染"
    assert "key: 'notify'" in text, "运行摘要通知开关不能丢"


def test_no_vuetify_tabs_component():
    """不要用 ``VTabs`` / ``VTab``：宿主没把它们注册成全局组件。"""
    text = _text()
    assert "<VTabs" not in text, "宿主未注册 VTabs，改用原生按钮"
    assert "<VTab" not in text, "宿主未注册 VTab，改用原生按钮"


def test_douban_panel_has_two_subtabs_and_closes():
    """豆瓣分区要有两个子 tab，并且外层 template 在该分区内闭合。"""
    text = _text()
    assert "doubanTab === 'basic'" in text
    assert "doubanTab === 'routes'" in text
    assert "sc-subtab" in text, "子 tab 用原生按钮渲染"

    # 豆瓣分区的 <template> 必须在下一个分区（tmdb）之前闭合
    start = text.find("<template v-if=\"activeSection === 'douban'\">")
    nxt = text.find("<template v-if=\"activeSection === 'tmdb'\">")
    assert 0 < start < nxt
    assert text.count("</template>", start, nxt) >= 3, "豆瓣分区缺少闭合标签"


def test_no_stray_summary_tag():
    """``<summary>`` 只能出现在 ``<details>`` 里；这里的残留会把区块当成折叠标题。"""
    text = _text()
    assert "<summary>" not in text


def test_page_has_calendar_tab_default_and_month_grid():
    """详情页：日历是默认 tab，复刻 MP 月历网格（7 列、格子内滚动、可用 +N 展开）。"""
    page = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Page.vue"
    )
    text = page.read_text(encoding="utf-8")
    assert "const viewTab = ref('calendar')" in text, "日历必须是默认 tab"
    assert "sc-cal-scroll" in text, "月历要在自己板块里滚动"
    assert "overflow-y: auto" in text
    assert "grid-template-columns: repeat(7" in text, "月历固定 7 列（周一到周日）"
    assert "sc-cal-more" in text, "超过每格上限要有 +N 展开"
    assert "viewTab === 'history'" in text, "发现流水仍可切换"


def test_calendar_uses_month_api():
    """前端必须走整月接口，且支持上/下月。"""
    page = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Page.vue"
    )
    text = page.read_text(encoding="utf-8")
    assert "calendar?month=" in text
    assert "function shiftMonth(" in text
    assert "calMonthTitle" in text


def test_calendar_defaults_to_today_list():
    """默认是「今天列表」，月历保留为可切换项。"""
    page = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3" / PLUGIN_ID / "src" / "components" / "Page.vue"
    )
    text = page.read_text(encoding="utf-8")
    assert "const calMode = ref('today')" in text, "默认必须是今天列表"
    assert "switchCalMode" in text and "sc-calmode" in text, "要有 今天/月历 切换"
    assert "calendar/day" in text, "今天视图走单日接口"
    assert "sc-today-grid" in text
    assert "sc-cal-weekhead" in text, "月历保留"
