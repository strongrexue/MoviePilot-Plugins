"""EmbyCoverCenter 插件 API 的响应模型。

响应统一使用宿主 ``schemas.Response[T]``，每个路由都要在 ``API_RESPONSE_MODELS``
中登记业务数据模型，由控制层据此声明 ``response_model``。
"""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class PingData(BaseModel):
    """连通性探针响应。"""

    plugin_version: str = ""
    enabled: bool = False
    message: str = "pong"


class EmbyServerInfo(BaseModel):
    """已启用的媒体服务器摘要。"""

    name: str = ""
    type: str = ""
    active: bool = False


class StatusData(BaseModel):
    """插件与媒体服务器运行状态。"""

    plugin_version: str = ""
    enabled: bool = False
    selected_servers: List[str] = Field(default_factory=list)
    servers: List[EmbyServerInfo] = Field(default_factory=list)


class EmbyTriggerInfo(BaseModel):
    """归一化后的触发器展示结构。"""

    type: str = ""
    type_label: str = ""
    time: str = ""
    day_of_week: str = ""
    day_label: str = ""
    interval_hours: float = 0
    max_runtime_hours: float = 0
    system_event: str = ""
    summary: str = ""


class EmbyTaskItem(BaseModel):
    """归一化后的 Emby 计划任务。"""

    id: str = ""
    key: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    raw_category: str = ""
    state: str = ""
    is_running: bool = False
    progress: float = 0
    last_status: str = ""
    status_label: str = ""
    status_type: str = ""
    last_run_time: str = ""
    last_run_time_raw: str = ""
    error_message: str = ""
    triggers: List[EmbyTriggerInfo] = Field(default_factory=list)
    trigger_summary: str = ""


class EmbyTaskCategory(BaseModel):
    """按分类分组的任务集合。"""

    name: str = ""
    count: int = 0
    tasks: List[EmbyTaskItem] = Field(default_factory=list)


class EmbyTaskListData(BaseModel):
    """计划任务列表载荷。"""

    tasks: List[EmbyTaskItem] = Field(default_factory=list)
    categories: List[EmbyTaskCategory] = Field(default_factory=list)
    running_count: int = 0
    updated_at: str = ""


class EmbyTaskData(BaseModel):
    """单个任务及其触发器。"""

    task: EmbyTaskItem
    triggers: List[EmbyTriggerInfo] = Field(default_factory=list)
    trigger_summary: str = ""


class EmbyTriggerDraft(BaseModel):
    """前端提交的触发器草稿。"""

    type: str = "DailyTrigger"
    time: str = "00:00"
    day_of_week: str = "Monday"
    interval_hours: float = 24
    max_runtime_hours: float = 0
    system_event: str = ""


class EmbyTriggerSaveRequest(BaseModel):
    """保存触发器的请求体。"""

    server: str = ""
    triggers: List[EmbyTriggerDraft] = Field(default_factory=list)


class EmbyActionData(BaseModel):
    """任务操作结果。"""

    status: str = "success"
    message: str = ""


API_RESPONSE_MODELS: Dict[str, type] = {
    "/ping": PingData,
    "/status": StatusData,
    "/emby_tasks": EmbyTaskListData,
    "/emby_tasks/{task_id}": EmbyTaskData,
    "/emby_tasks/{task_id}/triggers": EmbyTaskData,
    "/emby_tasks/{task_id}/run": EmbyActionData,
    "/emby_tasks/{task_id}/stop": EmbyActionData,
}
