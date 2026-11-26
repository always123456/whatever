from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .application import ApplicationDetailOut
from .company import CompanyOut


class IdealTalent(BaseModel):
    """理想人才特质：dimension 取 schemas/requirement.py TALENT_TRAITS 的 id。

    value 为期望对方达到的最低水平档（弱/中/强，见 TRAIT_LEVELS）；
    importance 为该特质权重（不限=不入卡，重点=2.0，默认 1.0）。
    """
    dimension: str
    value: str = "中"              # 期望最低档：弱/中/强
    importance: float = 1.0        # 权重（重点=2.0，默认=1.0）


class JobCreate(BaseModel):
    title: str
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
    must_skills: List[str] = []       # 必备技能，缺一淘汰（硬过滤）
    job_types: List[str] = []          # 社招/应届校招/实习生/兼职
    ideal_talents: List[IdealTalent] = []  # 理想人才特质
    # 公司归属：企业用户发布职位时后端自动绑定其公司（company_id），不再由前端传公司字符串


class JobOut(JobCreate):
    model_config = {"from_attributes": True}

    id: int
    owner_id: int
    company_id: Optional[int] = None
    company_name: Optional[str] = None  # 展示用，由 Job.company 关系回填
    status: str = "active"
    created_at: datetime
    updated_at: datetime


class MatchAnalysis(BaseModel):
    """求职者简历 vs 单个岗位的匹配度分析（详情页实时计算，不落 match_records）。"""

    resume_id: Optional[int] = None   # 分析所用简历；无简历时为 None
    resume_name: Optional[str] = None
    hard_passed: bool                 # 硬条件是否全部通过
    score: Optional[float] = None     # 0-1；硬条件不通过时为 None
    matched_rules: List[str] = []     # 通过的硬条件（如「薪资匹配」）
    failed_rules: List[str] = []      # 未通过的硬条件（如「学历不达标」）
    reasons: List[str] = []           # 软打分维度明细


class JobDetailOut(BaseModel):
    """职位详情：岗位 + 公司档案 + 匹配度分析（求职者）+ 投递进度（求职者）。"""

    job: JobOut
    company: Optional[CompanyOut] = None
    match: Optional[MatchAnalysis] = None
    application: Optional[ApplicationDetailOut] = None  # 含状态时间线
