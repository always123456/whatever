from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class IdealTalent(BaseModel):
    """理想人才特质：dimension 取 schemas/requirement.py TALENT_TRAITS 的 id。"""
    dimension: str
    value: str = "加分项"          # 期望水平描述
    importance: float = 1.0        # 权重（重要=2.0，加分=1.0）


class JobCreate(BaseModel):
    title: str
    company: str
    location: str
    salary_min: Optional[float] = Field(default=None, description="月薪下限（千元）")
    salary_max: Optional[float] = Field(default=None, description="月薪上限（千元）")
    education: str = "本科"  # 最低学历：不限/大专/本科/硕士/博士
    experience_years: int = 0  # 最低经验年数
    industry: str = ""
    skills: List[str] = []
    remote: bool = False
    description: str = ""
    # —— 信息采集细则新增字段 ——
    job_types: List[str] = []          # 社招/应届校招/实习生/兼职
    company_size: str = ""             # 人员规模
    overtime: str = ""                 # 加班节奏
    social_insurance: str = ""         # 社保、公积金
    ideal_talents: List[IdealTalent] = []  # 理想人才特质


class JobOut(JobCreate):
    model_config = {"from_attributes": True}

    id: int
    owner_id: int
    created_at: datetime
