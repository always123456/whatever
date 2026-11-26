from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..api.companies import get_or_create_company
from ..db import get_db
from ..matching.constraints import check_hard_constraints
from ..matching.scoring import compute_score
from ..models.db_models import Application, Job, Resume, User
from ..schemas.job import JobCreate, JobDetailOut, JobOut, MatchAnalysis
from ..services.application_service import build_application_detail
from ..services.matching_service import get_card, job_to_card, resume_to_card, upsert_card
from .deps import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号可发布职位")
    company = get_or_create_company(db, user)
    job = Job(owner_id=user.id, company_id=company.id, **payload.model_dump())
    db.add(job)
    db.flush()
    upsert_card(db, "enterprise", job.id, job_to_card(job), source="form")
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者看全部职位；企业只看自己发布的职位。"""
    q = db.query(Job).options(selectinload(Job.company))
    if user.role == "enterprise":
        q = q.filter(Job.owner_id == user.id)
    return q.order_by(Job.id.desc()).all()


@router.get("/{job_id}/detail", response_model=JobDetailOut)
def job_detail(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """职位详情：岗位情况 + 公司档案 +（求职者）匹配度分析与投递进度。

    - 求职者：可看任意职位；匹配度用自己最新一份简历实时计算（不落库），
      投递进度取本人对该职位的投递记录。
    - 企业：只能看自己发布的职位，match/application 恒为空。
    """
    job = db.query(Job).options(selectinload(Job.company)).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(404, detail="职位不存在")
    if user.role == "enterprise" and job.owner_id != user.id:
        raise HTTPException(403, detail="只能查看自己发布的职位")

    detail = JobDetailOut(job=job, company=job.company)
    if user.role != "seeker":
        return detail

    # 投递进度：本人对该职位的投递记录（唯一约束 job_id+resume_id，取最近一条），含状态时间线
    application = (
        db.query(Application)
        .join(Resume, Resume.id == Application.resume_id)
        .filter(Application.job_id == job.id, Resume.owner_id == user.id)
        .order_by(Application.created_at.desc())
        .first()
    )
    detail.application = build_application_detail(db, application) if application else None

    # 匹配度分析：最新一份简历 vs 该岗位（与 /match 默认口径一致）
    resume = (
        db.query(Resume)
        .filter(Resume.owner_id == user.id)
        .order_by(Resume.id.desc())
        .first()
    )
    if resume is None:
        detail.match = MatchAnalysis(hard_passed=False)
        return detail

    seeker_card = get_card(db, "seeker", resume.id, resume_to_card(resume))
    job_card = get_card(db, "enterprise", job.id, job_to_card(job))
    passed, rules, failed = check_hard_constraints(seeker_card, job_card, "seeker_to_jobs")
    if passed:
        score, reasons = compute_score(seeker_card, job_card, "seeker_to_jobs")
    else:
        score, reasons = None, []
    detail.match = MatchAnalysis(
        resume_id=resume.id,
        resume_name=resume.name,
        hard_passed=passed,
        score=score,
        matched_rules=rules,
        failed_rules=failed,
        reasons=reasons,
    )
    return detail
