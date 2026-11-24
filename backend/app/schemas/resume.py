from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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


class ResumeOut(ResumeCreate):
    model_config = {"from_attributes": True}

    id: int
    owner_id: int
    created_at: datetime
