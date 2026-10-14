"""P9 重复获取治理：宿主能力探针。

守住的契约：

- 探针**只读、不抛异常**：宿主缺哪块就红哪块，并给出真实的导入路径与失败原因；
- 下载器枚举不到时**单项报红不停摆**（闸门 A 的活跃性细化按 fail-open 降级）；
- 三个 P9 配置项默认值符合规格（全保守）。

> 历史：1.9.0 还包含「反向 R0 开关」（暂停宿主内置 new_subscribe_search）及其
> 6 项测试；1.9.1 真机验证否决（暂停 job 后新增订阅照旧被搜索——首次搜索是
> ``subscribe.added`` 事件驱动，job 只是 5 分钟兜底）后整体移除。
"""
import sys
import types

from app.plugins.tgmediacenter import TgMediaCenter
from app.plugins.tgmediacenter.services import pt_guard

# 探针会去试这些落点：测试里逐个注入假模块，或整体置空模拟"没有宿主"
_HOST_MODULES = (
    "app.sdk.queries",
    "app.sdk.services",
    "app.schemas.types",
    "app.schemas",
    "app.schemas.models",
)


def _module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _drop_host(monkeypatch):
    """让所有候选宿主模块都导入失败（``None`` 占位会让 import 直接报错）。"""
    for name in _HOST_MODULES:
        monkeypatch.setitem(sys.modules, name, None)


# --------------------------------------------------------------------- 探针：无宿主


def test_probe_without_host_is_all_red_but_never_raises(monkeypatch):
    """宿主能力一个都没有时：逐项报红、给出原因，且不抛异常。"""
    _drop_host(monkeypatch)
    result = pt_guard.probe()

    assert result["ok"] is False
    assert result["checked_at"]
    keys = [item["key"] for item in result["items"]]
    assert keys == [
        "download_history", "history_filter", "page_request",
        "downloader_helper", "downloader_instances", "torrent_enum",
    ]
    assert all(item["ok"] is False for item in result["items"])
    # 失败原因必须写进 detail，并带上要找的符号名——否则用户无从判断
    # "是宿主没有这个东西，还是插件找错了地方"
    assert all(item["detail"] for item in result["items"])
    details = {item["key"]: item["detail"] for item in result["items"]}
    assert "DownloadHistoryFilter" in details["history_filter"]
    assert "QueryPageRequest" in details["page_request"]
    assert "list_download_history" in details["download_history"]


# --------------------------------------------------------------------- 探针：有宿主


def _patch_full_host(monkeypatch, services=None, configs=None):
    """注入一套"宿主齐全"的假模块（探针应全绿）。"""
    class DownloadHistoryFilter:
        title: str = ""
        year: str = ""
        seasons: list = []

    class QueryPageRequest:
        page: int = 1
        count: int = 50

    monkeypatch.setitem(
        sys.modules, "app.sdk.queries",
        _module("app.sdk.queries",
                list_download_history=lambda *a, **k: None,
                DownloadHistoryFilter=DownloadHistoryFilter,
                QueryPageRequest=QueryPageRequest),
    )

    class DownloaderHelper:
        # 回归锁（1.9.2）：1.9.1 传了 type_filter="Downloader"，而宿主的
        # type_filter 匹配的是服务类型名（qbittorrent 等），导致永远枚举为空。
        # DownloaderHelper 已绑定模块类别，正确用法是不带过滤直接调。
        calls: list = []

        def get_services(self, type_filter=None):
            DownloaderHelper.calls.append(type_filter)
            if type_filter is not None:
                raise AssertionError("不应传 type_filter：它匹配的是 qbittorrent 等类型名")
            return services if services is not None else {"qBittorrent": object()}

        def get_configs(self):
            return configs if configs is not None else {"qBittorrent": object()}

    monkeypatch.setitem(
        sys.modules, "app.sdk.services",
        _module("app.sdk.services", DownloaderHelper=DownloaderHelper),
    )

    class TorrentStatus:
        ALL = "all"

    class DownloadTaskState:
        DOWNLOADING = "downloading"

    monkeypatch.setitem(
        sys.modules, "app.schemas.types",
        _module("app.schemas.types", TorrentStatus=TorrentStatus,
                DownloadTaskState=DownloadTaskState),
    )


def test_probe_reports_real_host_paths(monkeypatch):
    """宿主齐全时：探针全绿，并把命中的真实模块路径与字段写进 detail。"""
    _patch_full_host(monkeypatch)

    result = pt_guard.probe()
    assert result["ok"] is True
    items = {item["key"]: item for item in result["items"]}
    assert items["download_history"]["detail"] == "app.sdk.queries.list_download_history"
    assert "app.sdk.queries.DownloadHistoryFilter" in items["history_filter"]["detail"]
    assert "title" in items["history_filter"]["detail"]
    assert "qBittorrent" in items["downloader_instances"]["detail"]


def test_probe_flags_missing_downloader_as_red(monkeypatch):
    """下载器助手在、一个都没配置 → 细项报红且说明会自动降级（不拦推送）。"""
    _patch_full_host(monkeypatch, services={}, configs={})
    result = pt_guard.probe()
    items = {item["key"]: item for item in result["items"]}
    assert items["downloader_helper"]["ok"] is True
    assert items["downloader_instances"]["ok"] is False
    assert "未配置" in items["downloader_instances"]["detail"]
    assert "降级" in items["downloader_instances"]["detail"]


def test_probe_distinguishes_configured_but_no_instances(monkeypatch):
    """配置存在但枚举不到运行实例 → 提示可能是宿主尚未就绪（与"没配置"区分开）。"""
    _patch_full_host(monkeypatch, services={}, configs={"NAS-qB": object()})
    result = pt_guard.probe()
    items = {item["key"]: item for item in result["items"]}
    assert items["downloader_instances"]["ok"] is False
    assert "NAS-qB" in items["downloader_instances"]["detail"]
    assert "运行实例" in items["downloader_instances"]["detail"]


# --------------------------------------------------------------------- 配置默认值


def test_p9_config_defaults_are_conservative():
    """P9 全部新配置默认保守：闸门关，成熟期 2 小时、活跃性细化开。"""
    config = TgMediaCenter.default_config()
    assert config["p9_forward_gate_enabled"] is False
    assert config["p9_maturity_hours"] == 2
    assert config["p9_check_downloader"] is True
    # 反向 R0 开关已在 1.9.1 移除，配置里不应再有它的键
    assert "p9_pause_new_subscribe_search" not in config
