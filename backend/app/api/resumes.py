from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import Application, Job, Resume, User
from ..schemas.resume import ResumeCreate, ResumeOut
from ..services.matching_service import resume_to_card, upsert_card
from .deps import get_current_user

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeOut, status_code=201)
def create_resume(
    payload: ResumeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者账号可创建简历")
    resume = Resume(owner_id=user.id, **payload.model_dump())
    db.add(resume)
    db.flush()
    upsert_card(db, "seeker", resume.id, resume_to_card(resume), source="form")
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者只能看自己的简历；企业只能看「投了本公司岗位」的求职者简历。"""
    if user.role == "seeker":
        return db.query(Resume).filter(Resume.owner_id == user.id).order_by(Resume.id.desc()).all()

    # 企业：投递了本公司（owner_id == user.id）岗位的简历，按最近投递时间倒序
    rows = (
        db.query(Resume, Job, Application)
        .join(Application, Application.resume_id == Resume.id)
        .join(Job, Job.id == Application.job_id)
        .filter(Job.owner_id == user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    by_resume: dict[int, ResumeOut] = {}
    for resume, job, _app in rows:
        out = by_resume.get(resume.id)
        if out is None:
            out = ResumeOut.model_validate(resume)
            by_resume[resume.id] = out
        if job.title and job.title not in out.applied_job_titles:
            out.applied_job_titles.append(job.title)
    return list(by_resume.values())
