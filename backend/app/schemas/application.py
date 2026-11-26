from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# 投递状态枚举（与 db_models.Application.status 注释一致）
APPLICATION_STATUSES = ("待处理", "已查看", "面试", "录用", "拒绝")

# 状态机：当前状态 -> 允许流转到的状态（录用/拒绝为终态，不可再流转）
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "待处理": {"已查看", "面试", "拒绝"},
    "已查看": {"面试", "拒绝"},
    "面试": {"录用", "拒绝"},
}


class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: Optional[int] = None  # 缺省用当前求职者最新一份简历


class ApplicationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    job_id: int
    resume_id: int
    status: str = Field(default="待处理")
    created_at: datetime
    updated_at: datetime


class ApplicationEventOut(BaseModel):
    """状态流转事件（时间线一条）。from_status='' 表示初始投递。"""

    id: int
    application_id: int
    from_status: str = ""
    to_status: str
    operator_id: int
    operator_name: Optional[str] = None  # 由 service 回填（昵称/用户名）
    note: Optional[str] = None
    created_at: datetime


class ResumeBrief(BaseModel):
    """审批时查看的简历摘要。"""

    model_config = {"from_attributes": True}

    id: int
    name: str
    location: str
    education: str
    experience_years: int
    skills: List[str] = []
    summary: str = ""


class ApplicationDetailOut(ApplicationOut):
    """投递详情：职位名 + 求职者名 + 简历摘要 + 状态时间线。"""

    job_title: str = ""
    seeker_name: str = ""
    resume: Optional[ResumeBrief] = None
    events: List[ApplicationEventOut] = []
    seeker_confirmed_statuses: List[str] = []  # 求职者已确认过的状态（面试/录用），前端据此展示确认按钮


class ApplicationStatusUpdate(BaseModel):
    """企业审批操作：目标状态须满足状态机；note 为可选备注。"""

    status: str
    note: Optional[str] = None


class ApplicationConfirmUpdate(BaseModel):
    """求职者确认动作（仅面试/录用两档可确认）：note 为可选补充说明。"""

    note: Optional[str] = None


class ApplicationManageOut(BaseModel):
    """企业「投递管理」列表行。"""

    id: int
    job_id: int
    job_title: str
    resume_id: int
    seeker_name: str
    status: str
    created_at: datetime
    updated_at: datetime
