"""Bangumi 数据源的回归测试（0.6.0）。

真实 API 行为已实测确认（见 ``sources/bangumi.py`` 模块文档）：

- 只有 ``https://api.bgm.tv`` 可用（``api.bangumi.tv`` / ``bgm.tv`` 均失败）
- ``/v0/subjects?air_date=...`` 的过滤条件被服务端忽略，不能用
- ``/calendar`` 可用，条目带 ``air_date``（该番首播日）

本文件锁住两个最容易回归的点：
1. **窗口过滤**：只留「今天 ~ 今天+N 天」首播的番；
2. **不得给 popularity 赋值** —— 近期番评分人数极低，一旦塞进 popularity，
   会被流水线的「最低关注度」门槛整体误杀。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PLUGIN_ID = "subscribecenter"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins.v3"))

from subscribecenter.core import constants as C  # noqa: E402
from subscribecenter.sources.bangumi import BangumiSource, is_special  # noqa: E402

TODAY = date.today()


class FakeResponse:
    """最小 HTTP 响应替身。"""

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        """返回预设 JSON。"""
        return self._data


class FakeClient:
    """最小异步 HTTP 客户端替身。"""

    def __init__(self, data=None, status_code=200, raise_exc=None):
        self._data = data if data is not None else []
        self._status = status_code
        self._raise = raise_exc
        self.calls = []

    async def get(self, url):
        """记录并返回预设响应。"""
        self.calls.append(url)
        if self._raise:
            raise self._raise
        return FakeResponse(self._data, self._status)


def week(item_list):
    """把条目列表包成 ``/calendar`` 的「按星期分组」结构。"""
    return [{"weekday": {"id": 1, "cn": "星期一"}, "items": item_list}]


def anime(sid, air_date, name="某番", name_cn="", score=7.0, total=10):
    """构造一条 Bangumi calendar 条目。"""
    return {
        "id": sid,
        "name": name,
        "name_cn": name_cn,
        "air_date": air_date,
        "air_weekday": 1,
        "rating": {"score": score, "total": total},
        "images": {"large": "http://example/x.jpg"},
    }


CONFIG = {"bangumi_future_days": 3, "timezone": "Asia/Shanghai"}


# --------------------------------------------------------------------- 窗口

@pytest.mark.asyncio
async def test_keeps_only_airing_within_window():
    """只保留「今天 ~ 今天+N 天」首播的番。"""
    recent = (TODAY - timedelta(days=1)).isoformat()
    today_s = TODAY.isoformat()
    soon = (TODAY + timedelta(days=2)).isoformat()
    far = (TODAY + timedelta(days=10)).isoformat()

    client = FakeClient(week([
        anime(1, recent, name_cn="已开播"),
        anime(2, today_s, name_cn="今天"),
        anime(3, soon, name_cn="两天后"),
        anime(4, far, name_cn="太远"),
    ]))
    items = await BangumiSource(client).fetch(CONFIG)

    assert {i.source_id for i in items} == {"2", "3"}


@pytest.mark.asyncio
async def test_window_upper_bound_respects_config():
    """窗口上界跟随 ``bangumi_future_days``。"""
    day7 = (TODAY + timedelta(days=7)).isoformat()
    client = FakeClient(week([anime(1, day7, name_cn="七天后")]))

    assert await BangumiSource(client).fetch({**CONFIG, "bangumi_future_days": 3}) == []
    assert len(await BangumiSource(client).fetch({**CONFIG, "bangumi_future_days": 8})) == 1


@pytest.mark.asyncio
async def test_skips_items_without_air_date():
    """无 ``air_date`` 的条目无法判断开播日，丢弃。"""
    client = FakeClient(week([anime(1, ""), anime(2, None), anime(3, TODAY.isoformat())]))
    items = await BangumiSource(client).fetch(CONFIG)
    assert {i.source_id for i in items} == {"3"}


# --------------------------------------------------------------------- 归一

@pytest.mark.asyncio
async def test_prefers_chinese_title():
    """优先用 ``name_cn``（中文标题），缺省回落到原 ``name``。"""
    client = FakeClient(week([
        anime(1, TODAY.isoformat(), name="Sousou no Frieren", name_cn="葬送的芙莉莲"),
        anime(2, TODAY.isoformat(), name="English Only", name_cn=""),
    ]))
    items = {i.source_id: i for i in await BangumiSource(client).fetch(CONFIG)}

    assert items["1"].title == "葬送的芙莉莲"
    assert items["2"].title == "English Only"


@pytest.mark.asyncio
async def test_normalizes_bangumi_identity_and_type():
    """身份用 Bangumi subject id（后续由宿主换算成 TMDB），类型按剧集处理。"""
    client = FakeClient(week([anime(513878, TODAY.isoformat(), name_cn="赛博朋克")]))
    item = (await BangumiSource(client).fetch(CONFIG))[0]

    assert item.source == C.SOURCE_BANGUMI
    assert item.native_ids == {"bangumi": "513878"}
    assert item.media_type == C.MEDIA_TYPE_TV
    assert item.release_date == TODAY.isoformat()
    assert item.year == str(TODAY.year)


@pytest.mark.asyncio
async def test_popularity_must_stay_none():
    """**不得给 popularity 赋值**。

    近期番的 ``rating.total`` 只有个位数，若塞进 popularity，会被流水线的
    「最低关注度」门槛（默认 15）整体误杀 —— 等于 Bangumi 源静默失效。
    """
    client = FakeClient(week([anime(1, TODAY.isoformat(), name_cn="新番", total=3)]))
    item = (await BangumiSource(client).fetch(CONFIG))[0]

    assert item.popularity is None
    # 投票数仍保留在 raw 里供排查
    assert item.raw["rating_total"] == 3


@pytest.mark.asyncio
async def test_rating_mapping():
    """评分映射到 ``rating``；无评分时为 ``None``。"""
    client = FakeClient(week([
        anime(1, TODAY.isoformat(), score=8.2),
        anime(2, TODAY.isoformat(), score=0),
    ]))
    items = {i.source_id: i for i in await BangumiSource(client).fetch(CONFIG)}

    assert items["1"].rating == 8.2
    assert items["2"].rating is None


@pytest.mark.asyncio
async def test_dedupes_same_subject_across_weekdays():
    """同一 subject 出现在多个星期分组时只保留一条。"""
    dup = anime(999, TODAY.isoformat(), name_cn="重复番")
    client = FakeClient(week([dup]) + week([dict(dup)]))
    items = await BangumiSource(client).fetch(CONFIG)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_skips_items_without_id_or_title():
    """无 id / 无标题的条目丢弃。"""
    client = FakeClient(week([
        {"id": None, "name": "无 id", "air_date": TODAY.isoformat()},
        {"id": 7, "name": "", "name_cn": "", "air_date": TODAY.isoformat()},
        anime(8, TODAY.isoformat(), name_cn="正常"),
    ]))
    items = await BangumiSource(client).fetch(CONFIG)
    assert {i.source_id for i in items} == {"8"}


@pytest.mark.asyncio
async def test_output_sorted_by_release_date():
    """输出按开播日排序（便于预览阅读）。"""
    d2 = (TODAY + timedelta(days=2)).isoformat()
    d1 = (TODAY + timedelta(days=1)).isoformat()
    client = FakeClient(week([anime(1, d2, name_cn="后"), anime(2, d1, name_cn="先")]))
    items = await BangumiSource(client).fetch(CONFIG)
    assert [i.source_id for i in items] == ["2", "1"]


# --------------------------------------------------------------------- 特别篇

@pytest.mark.parametrize(
    "title,expected",
    [
        ("我的幸福婚姻 特别篇", True),
        ("罗小黑战记 学前篇", True),
        ("万圣街 特别篇 古堡的秘密", True),
        ("某番 番外篇", True),
        ("某番 OVA", True),
        ("某番 前传", True),
        ("赛博朋克：边缘行者 2", False),
        ("牧神记5", False),
        ("Dreamland", False),
    ],
)
def test_is_special(title, expected):
    """特别篇 / OVA / 番外等衍生内容的识别。

    TMDB 通常没有这类内容的独立条目，标题匹配必然失败。若不单独标注，
    日志会显示「无确定性身份（L4）」，看起来像插件有 bug（真机踩过 3 条）。
    """
    assert is_special(title) is expected


@pytest.mark.asyncio
async def test_special_items_are_flagged():
    """Bangumi 源要把特别篇标出来（供 writer 给出明确决策）。"""
    client = FakeClient(week([
        anime(1, TODAY.isoformat(), name_cn="某番 特别篇"),
        anime(2, TODAY.isoformat(), name_cn="某番 第2期"),
    ]))
    items = {i.source_id: i for i in await BangumiSource(client).fetch(CONFIG)}
    assert items["1"].special is True
    assert items["2"].special is False


# --------------------------------------------------------------------- 容错

@pytest.mark.asyncio
async def test_http_error_raises_for_pipeline_to_record():
    """HTTP 错误要抛出，让流水线把该源标记失败（而不是静默 0 条）。"""
    client = FakeClient([], status_code=503)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        await BangumiSource(client).fetch(CONFIG)


@pytest.mark.asyncio
async def test_non_list_payload_raises():
    """结构异常（非数组）也要抛出，避免静默吞掉。"""
    client = FakeClient({"error": "nope"})
    with pytest.raises(RuntimeError, match="结构异常"):
        await BangumiSource(client).fetch(CONFIG)


@pytest.mark.asyncio
async def test_uses_calendar_endpoint():
    """必须请求 ``/calendar``（``/v0/subjects`` 的 air_date 过滤实测无效）。"""
    client = FakeClient(week([]))
    await BangumiSource(client).fetch(CONFIG)
    assert client.calls == ["https://api.bgm.tv/calendar"]


# --------------------------------------------------------------------- 接线

def test_bangumi_is_implemented_source():
    """Bangumi 必须登记为已实现源，否则配置里打开也会被跳过。"""
    assert C.SOURCE_BANGUMI in C.IMPLEMENTED_SOURCES


def test_bangumi_window_default_is_3_days():
    """Bangumi 窗口默认与 TMDB 一致（3 天）。"""
    assert C.default_config()["bangumi_future_days"] == C.DEFAULT_FUTURE_DAYS == 3
