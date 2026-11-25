from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# 投递状态枚举（与 db_models.Application.status 注释一致）
APPLICATION_STATUSES = ("待处理", "已查看", "面试", "录用", "拒绝")


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
