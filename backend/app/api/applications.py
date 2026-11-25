from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import Application, Job, Resume, User
from ..schemas.application import ApplicationCreate, ApplicationOut
from .deps import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者投递岗位：缺省用自己最新一份简历，同一简历对同一岗位只投一次。"""
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者可投递岗位")

    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(404, detail="职位不存在")

    if payload.resume_id is not None:
        resume = db.get(Resume, payload.resume_id)
        if resume is None:
            raise HTTPException(404, detail="简历不存在")
        if resume.owner_id != user.id:
            raise HTTPException(403, detail="只能使用自己的简历投递")
    else:
        resume = (
            db.query(Resume)
            .filter(Resume.owner_id == user.id)
            .order_by(Resume.id.desc())
            .first()
        )
        if resume is None:
            raise HTTPException(400, detail="请先完善你的简历再投递")

    dup = (
        db.query(Application)
        .filter(Application.job_id == job.id, Application.resume_id == resume.id)
        .first()
    )
    if dup is not None:
        raise HTTPException(409, detail="已投递过该职位")

    app = Application(job_id=job.id, resume_id=resume.id)
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者查自己的投递；企业查投了本公司岗位的投递记录。"""
    q = db.query(Application)
    if user.role == "seeker":
        q = (
            q.join(Resume, Resume.id == Application.resume_id)
            .filter(Resume.owner_id == user.id)
        )
    else:
        q = q.join(Job, Job.id == Application.job_id).filter(Job.owner_id == user.id)
    return q.order_by(Application.created_at.desc()).all()
