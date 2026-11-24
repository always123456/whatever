from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="seeker")  # seeker | enterprise
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(128))
    company: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(64))
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    education: Mapped[str] = mapped_column(String(16), default="本科")
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    industry: Mapped[str] = mapped_column(String(64), default="")
    skills: Mapped[List[str]] = mapped_column(JSON, default=list)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
