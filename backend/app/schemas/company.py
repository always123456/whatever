from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# 公司枚举常量（与前端 Jobs.vue 的 COMPANY_SIZES / OVERTIMES / SOCIAL_INSURANCES 保持一致）
COMPANY_SIZES = ["1-49人", "50-99人", "100-499人", "500-999人", "1000人以上"]
COMPANY_OVERTIMES = ["不加班", "偶尔加班", "经常加班", "大小周", "996"]
COMPANY_SOCIAL_INSURANCES = ["全额缴纳", "按最低基数缴纳", "无公积金", "面议"]


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


class CompanyExtraction(BaseModel):
    """公司 PDF（简介/营业执照等）抽取结果：字段含义同 CompanyUpdate。

    非空字段在写入时覆盖、空字段保留原值（与需求卡抽取的合并规则一致）。
    """

    name: str = ""
    abbr: str = ""
    size: str = ""
    industry: str = ""
    overtime: str = ""
    social_insurance: str = ""
    company_traits: dict = Field(default_factory=dict)  # JOB_FACT_AXES 6 轴，逐轴合并
    description: str = ""  # 公司简介一句话概括（仅供预览，不入库）


class CompanyParseResponse(BaseModel):
    """PDF 解析第一段：抽取预览 + 原文 + 提示（不落库）。"""

    company: CompanyExtraction
    raw_text: str = ""
    warnings: List[str] = Field(default_factory=list)


class CompanyApplyRequest(BaseModel):
    """PDF 解析第二段：确认后把抽取结果合并写入公司档案。"""

    company: CompanyExtraction


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
