"""真实 schemas 环境下自动封面接口的全链路调用验证。

回归背景：v1.6.0 曾因 controller/api.py 顶部漏 import cover_auto，
「立即运行」接口 NameError（宿主 500，前端只显示"未知错误"）；
当时仅有的路由注册测试不调用 endpoint，没能拦住。
"""
from app import schemas
from app.plugins.embycovercenter.controller import api as api_controller
from app.plugins.embycovercenter.controller import schemas as api_schemas
from app.plugins.embycovercenter.service import cover_auto


class _P:
    def __init__(self, enabled=True):
        self._config = {"enabled": enabled}

    def get_state(self):
        return bool(self._config.get("enabled"))


def test_manual_run_endpoint_calls_async_and_envelope_ok(monkeypatch):
    """立即运行：接口真实可调用，后台任务被启动，响应是合法的 Response[OkData]。"""
    plugin = _P()
    calls = []
    monkeypatch.setattr(cover_auto, "run_auto_cover_async", lambda p: calls.append(p))
    resp = api_controller.api_auto_cover_run(plugin)
    assert len(calls) == 1 and calls[0] is plugin
    assert isinstance(resp, schemas.Response)
    assert resp.success is True
    assert isinstance(resp.data, api_schemas.OkData)


def test_manual_run_endpoint_disabled(monkeypatch):
    """插件未启用时接口 400，不会启动后台任务。"""
    from fastapi import HTTPException

    plugin = _P(enabled=False)
    calls = []
    monkeypatch.setattr(cover_auto, "run_auto_cover_async", lambda p: calls.append(p))
    try:
        api_controller.api_auto_cover_run(plugin)
    except HTTPException as error:
        assert error.status_code == 400
    else:
        raise AssertionError("未启用时应抛 HTTPException(400)")
    assert calls == []
