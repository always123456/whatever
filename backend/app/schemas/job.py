from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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


class JobOut(JobCreate):
    model_config = {"from_attributes": True}

    id: int
    owner_id: int
    created_at: datetime
