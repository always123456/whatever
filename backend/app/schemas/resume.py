from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .requirement import TraitItem


class ResumeCreate(BaseModel):
    name: str
    location: str
    expected_salary_min: Optional[float] = Field(default=None, description="期望月薪下限（千元）")
    expected_salary_max: Optional[float] = Field(default=None, description="期望月薪上限（千元）")
    education: str = "本科"
    experience_years: int = 0
    industry: str = ""
    skills: List[str] = []
    willing_remote: bool = False
    summary: str = ""
    job_status: str = ""  # 随时到岗/本月到岗/观望了解
    # —— 匹配算法新增字段 ——
    intended_titles: List[str] = []    # 意向职位（最多5个，软打分 title 维度）
    target_job_types: List[str] = []   # 求职意向岗位类型（社招/应届校招/实习生/兼职，软打分）
    self_traits: List[TraitItem] = []  # 人才特质自评（弱/中/强，trait 匹配）
    ideal_company_traits: dict = Field(default_factory=dict)  # 理想公司特质（JOB_FACT_AXES 6 轴）


class ResumeOut(ResumeCreate):
    model_config = {"from_attributes": True}

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    applied_job_titles: List[str] = []  # 企业视角：该简历投递的本公司岗位标题（求职者视角恒为空）
