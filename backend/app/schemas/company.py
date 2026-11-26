from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CompanyUpdate(BaseModel):
    """公司档案更新：企业用户在「公司信息」表单提交全量字段。"""

    name: str = ""
    abbr: str = ""
    size: str = ""
    industry: str = ""
    overtime: str = ""
    social_insurance: str = ""
    logo_url: Optional[str] = None
    company_traits: dict = Field(default_factory=dict)  # JOB_FACT_AXES 6 轴（MVP 表单暂不采集）


class CompanyOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    owner_id: int
    name: str
    abbr: str
    size: str
    industry: str
    overtime: str
    social_insurance: str
    logo_url: Optional[str] = None
    company_traits: dict
    verified: bool = False
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
