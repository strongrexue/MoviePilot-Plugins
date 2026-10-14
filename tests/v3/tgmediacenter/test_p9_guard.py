"""P9 重复获取治理：宿主能力探针与反向 R0 开关。

守住的契约：

- 探针**只读、不抛异常**：宿主缺哪块就红哪块，并给出真实的导入路径与失败原因；
- 旧调度 ABI 不可用时**降级不停摆**（返回 available=False，不影响插件其余能力）；
- R0 开关**幂等**，且宿主没有该任务时判「无需处理」而不是失败；
- 插件停用 / 配置关闭时一律**放行**，绝不留残留 pause；
- 四个 P9 配置项默认值符合规格（全保守）。
"""
import sys
import types
from datetime import datetime, timedelta

from app.plugins.tgmediacenter import TgMediaCenter
from app.plugins.tgmediacenter.services import pt_guard

JOB_ID = pt_guard.JOB_NEW_SUBSCRIBE_SEARCH
# 探针会去试这些落点：测试里逐个注入假模块，或整体置空模拟"没有宿主"
_HOST_MODULES = (
    "app.sdk.queries",
    "app.sdk.services",
    "app.scheduler",
    "app.schemas.types",
    "app.schemas",
    "app.schemas.models",
)


def _module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class _FakeJob:
    """APScheduler 任务的替身：暂停即把 next_run_time 置空（与 3.x 行为一致）。"""

    def __init__(self, running: bool = True):
        self.next_run_time = (datetime.now() + timedelta(minutes=3)) if running else None


class _FakeScheduler:
    def __init__(self, jobs=None):
        self.jobs = dict(jobs if jobs is not None else {JOB_ID: _FakeJob()})
        self.calls = []

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def pause_job(self, job_id):
        self.calls.append(("pause", job_id))
        job = self.jobs.get(job_id)
        if job is not None:
            job.next_run_time = None

    def resume_job(self, job_id):
        self.calls.append(("resume", job_id))
        job = self.jobs.get(job_id)
        if job is not None and job.next_run_time is None:
            job.next_run_time = datetime.now() + timedelta(minutes=3)


class _SchedulerHolder:
    """``Scheduler()`` 的替身：旧插件 ABI 里真正的调度器挂在 ``_scheduler``。"""

    def __init__(self, scheduler: _FakeScheduler):
        self._scheduler = scheduler


def _patch_scheduler(monkeypatch, scheduler):
    """把 ``app.scheduler.Scheduler`` 换成返回给定替身的工厂。"""
    monkeypatch.setitem(
        sys.modules, "app.scheduler",
        _module("app.scheduler", Scheduler=lambda: _SchedulerHolder(scheduler)),
    )


def _drop_host(monkeypatch):
    """让所有候选宿主模块都导入失败（``None`` 占位会让 import 直接报错）。"""
    for name in _HOST_MODULES:
        monkeypatch.setitem(sys.modules, name, None)


def _bare_plugin(config):
    """只带配置快照的插件实例（apply_p9_r0 只依赖 _config 与 _enabled）。"""
    plugin = TgMediaCenter.__new__(TgMediaCenter)
    plugin._config = dict(config)
    plugin._p9_r0 = None
    return plugin


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
        "downloader_helper", "downloader_instances",
        "torrent_enum", "scheduler_abi", "job_new_subscribe_search",
    ]
    assert all(item["ok"] is False for item in result["items"])
    # 失败原因必须写进 detail，并带上要找的符号名——否则用户无从判断
    # "是宿主没有这个东西，还是插件找错了地方"
    assert all(item["detail"] for item in result["items"])
    details = {item["key"]: item["detail"] for item in result["items"]}
    assert "DownloadHistoryFilter" in details["history_filter"]
    assert "QueryPageRequest" in details["page_request"]
    assert "list_download_history" in details["download_history"]


def test_job_state_without_host_is_unavailable(monkeypatch):
    """没有旧调度 ABI 时 job_state 返回 available=False，而不是抛异常。"""
    _drop_host(monkeypatch)
    state = pt_guard.job_state()
    assert state["available"] is False
    assert state["exists"] is False
    assert state["paused"] is False
    assert state["detail"]


def test_apply_pause_without_host_degrades_instead_of_crashing(monkeypatch):
    """旧 ABI 不可用 → 明确返回失败原因（降级），调用方据此继续跑其余能力。"""
    _drop_host(monkeypatch)
    result = pt_guard.apply_pause(True)
    assert result == {
        "available": False, "ok": False, "applied": False, "paused": False,
        "message": result["message"],
    }
    assert "不生效" in result["message"]


# --------------------------------------------------------------------- 探针：有宿主


def test_probe_reports_real_host_paths(monkeypatch):
    """宿主齐全时：探针全绿，并把命中的真实模块路径与字段写进 detail。"""
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
        def get_services(self, type_filter=None):  # noqa: ARG002 - 模拟宿主签名
            return {"qBittorrent": object()}

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
    _patch_scheduler(monkeypatch, _FakeScheduler())

    result = pt_guard.probe()
    assert result["ok"] is True
    items = {item["key"]: item for item in result["items"]}
    assert items["download_history"]["detail"] == "app.sdk.queries.list_download_history"
    assert "app.sdk.queries.DownloadHistoryFilter" in items["history_filter"]["detail"]
    assert "title" in items["history_filter"]["detail"]
    assert "qBittorrent" in items["downloader_instances"]["detail"]
    assert items["scheduler_abi"]["ok"] is True
    assert items["job_new_subscribe_search"]["ok"] is True


def test_probe_flags_missing_downloader_as_red(monkeypatch):
    """下载器助手在、但一个都没启用 → 细项报红（活跃性细化将不可用）。"""
    _drop_host(monkeypatch)
    monkeypatch.setitem(
        sys.modules, "app.sdk.services",
        _module("app.sdk.services", DownloaderHelper=lambda: type(
            "_H", (), {"get_services": lambda self, type_filter=None: {}})()),
    )
    result = pt_guard.probe()
    items = {item["key"]: item for item in result["items"]}
    assert items["downloader_helper"]["ok"] is True
    assert items["downloader_instances"]["ok"] is False
    assert "未枚举到" in items["downloader_instances"]["detail"]


# --------------------------------------------------------------------- R0 开关


def test_job_state_detects_paused_job(monkeypatch):
    """暂停后 next_run_time 为空 → paused=True（判「在管」的唯一依据）。"""
    scheduler = _FakeScheduler({JOB_ID: _FakeJob(running=False)})
    _patch_scheduler(monkeypatch, scheduler)
    state = pt_guard.job_state()
    assert state["available"] is True and state["exists"] is True
    assert state["paused"] is True and state["next_run"] == ""


def test_apply_pause_is_idempotent_and_reversible(monkeypatch):
    scheduler = _FakeScheduler()
    _patch_scheduler(monkeypatch, scheduler)

    first = pt_guard.apply_pause(True)
    assert first["ok"] is True and first["paused"] is True
    again = pt_guard.apply_pause(True)
    assert again["ok"] is True and again["paused"] is True

    resumed = pt_guard.apply_pause(False)
    assert resumed["ok"] is True and resumed["paused"] is False
    assert ("pause", JOB_ID) in scheduler.calls and ("resume", JOB_ID) in scheduler.calls


def test_apply_pause_reports_expected_state_mismatch(monkeypatch):
    """宿主侧状态没被改动（被别的机制重建/覆盖）→ ok=False 且如实说明，不谎报成功。"""

    class _Stubborn(_FakeScheduler):
        def pause_job(self, job_id):  # noqa: ARG002 - 故意不生效
            self.calls.append(("pause", job_id))

    scheduler = _Stubborn()
    _patch_scheduler(monkeypatch, scheduler)
    result = pt_guard.apply_pause(True)
    assert result["applied"] is True
    assert result["ok"] is False
    assert result["paused"] is False
    assert "未如预期" in result["message"]


def test_apply_pause_when_job_absent_is_noop(monkeypatch):
    """宿主没注册该任务（版本差异）→ 判「无需处理」，不算失败、不报红。"""
    _patch_scheduler(monkeypatch, _FakeScheduler(jobs={}))
    result = pt_guard.apply_pause(True)
    assert result["available"] is True and result["ok"] is True
    assert result["applied"] is False and result["paused"] is False
    assert "未注册" in result["message"]


# --------------------------------------------------------------------- 插件接线


def test_apply_p9_r0_passes_through_when_plugin_disabled(monkeypatch):
    """插件未启用：即使开关打开也必须放行（不留残留 pause）。"""
    scheduler = _FakeScheduler()
    _patch_scheduler(monkeypatch, scheduler)
    plugin = _bare_plugin({"enabled": False, "p9_pause_new_subscribe_search": True})

    result = plugin.apply_p9_r0()

    assert result["paused"] is False
    assert ("pause", JOB_ID) not in scheduler.calls
    assert plugin._p9_r0 == result


def test_apply_p9_r0_pauses_when_enabled_and_configured(monkeypatch):
    scheduler = _FakeScheduler()
    _patch_scheduler(monkeypatch, scheduler)
    plugin = _bare_plugin({"enabled": True, "p9_pause_new_subscribe_search": True})

    result = plugin.apply_p9_r0()

    assert result["ok"] is True and result["paused"] is True
    assert ("pause", JOB_ID) in scheduler.calls


def test_apply_p9_r0_resumes_when_switch_off(monkeypatch):
    """开关关掉后重贴：任务必须回到运行态（默认行为不变）。"""
    scheduler = _FakeScheduler({JOB_ID: _FakeJob(running=False)})
    _patch_scheduler(monkeypatch, scheduler)
    plugin = _bare_plugin({"enabled": True, "p9_pause_new_subscribe_search": False})

    result = plugin.apply_p9_r0()

    assert result["paused"] is False
    assert ("resume", JOB_ID) in scheduler.calls


# --------------------------------------------------------------------- 配置默认值


def test_p9_config_defaults_are_conservative():
    """P9 全部新配置默认保守：闸门与反向开关都关，成熟期 2 小时、活跃性细化开。"""
    config = TgMediaCenter.default_config()
    assert config["p9_forward_gate_enabled"] is False
    assert config["p9_maturity_hours"] == 2
    assert config["p9_check_downloader"] is True
    assert config["p9_pause_new_subscribe_search"] is False
