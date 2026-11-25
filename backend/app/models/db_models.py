from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="seeker")  # seeker | enterprise
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Company(Base):
    """企业主体：MVP 一个企业用户对应一家公司（owner_id 唯一）。公司级字段从 Job 拆出。"""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), default="")
    abbr: Mapped[str] = mapped_column(String(64), default="")          # 公司简称
    size: Mapped[str] = mapped_column(String(32), default="")          # 人员规模
    industry: Mapped[str] = mapped_column(String(64), default="")      # 行业归属
    overtime: Mapped[str] = mapped_column(String(32), default="")      # 加班节奏
    social_insurance: Mapped[str] = mapped_column(String(32), default="")  # 社保公积金
    logo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_traits: Mapped[dict] = mapped_column(JSON, default=dict)   # JOB_FACT_AXES 6 轴
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(64))
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    education: Mapped[str] = mapped_column(String(16), default="本科")
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    industry: Mapped[str] = mapped_column(String(64), default="")
    skills: Mapped[List[str]] = mapped_column(JSON, default=list)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    # —— 信息采集细则新增字段（需求卡 hard.job_types / soft.traits）——
    must_skills: Mapped[List[str]] = mapped_column(JSON, default=list)  # 必备技能（硬过滤）
    job_types: Mapped[List[str]] = mapped_column(JSON, default=list)  # 社招/应届校招/实习生/兼职
    ideal_talents: Mapped[List[dict]] = mapped_column(JSON, default=list)  # 理想人才特质
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | closed

    company: Mapped[Optional["Company"]] = relationship()

    @property
    def company_name(self) -> str:
        """展示用公司名，由 company 关系回填（供 JobOut.company_name）。"""
        return self.company.name if self.company else ""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    location: Mapped[str] = mapped_column(String(64))
    expected_salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    education: Mapped[str] = mapped_column(String(16), default="本科")
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    industry: Mapped[str] = mapped_column(String(64), default="")
    skills: Mapped[List[str]] = mapped_column(JSON, default=list)
    willing_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    job_status: Mapped[str] = mapped_column(String(16), default="")  # 随时到岗/本月到岗/观望了解
    # —— 匹配算法新增字段 ——
    intended_titles: Mapped[List[str]] = mapped_column(JSON, default=list)  # 意向职位（最多5个）
    target_job_types: Mapped[List[str]] = mapped_column(JSON, default=list)  # 求职意向岗位类型
    self_traits: Mapped[List[dict]] = mapped_column(JSON, default=list)  # 人才特质自评
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RequirementCardRecord(Base):
    """需求卡落库：role + ref_id 指向 job/resume，card 存完整 hard/soft/facts。"""

    __tablename__ = "requirement_cards"
    __table_args__ = (UniqueConstraint("role", "ref_id", name="uq_card_role_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(16), index=True)   # seeker | enterprise
    ref_id: Mapped[int] = mapped_column(Integer, index=True)    # job.id 或 resume.id
    source: Mapped[str] = mapped_column(String(16), default="form")  # form|llm|rule|manual
    card: Mapped[dict] = mapped_column(JSON, default=dict)      # 完整 RequirementCard
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MatchRecord(Base):
    """匹配记录：快照式，历史分数不因卡后续变化而漂移。"""

    __tablename__ = "match_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    direction: Mapped[str] = mapped_column(String(32))  # seeker_to_jobs | enterprise_to_seekers
    target_role: Mapped[str] = mapped_column(String(16))  # 搜索方角色 seeker | enterprise
    target_id: Mapped[int] = mapped_column(Integer)        # 搜索方实体 id
    target_card: Mapped[dict] = mapped_column(JSON, default=dict)  # 搜索卡快照
    candidate_role: Mapped[str] = mapped_column(String(16))
    candidate_id: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    matched_rules: Mapped[List[str]] = mapped_column(JSON, default=list)
    reasons: Mapped[List[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
