from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..api.companies import get_or_create_company
from ..db import get_db
from ..models.db_models import Job, User
from ..schemas.job import JobCreate, JobOut
from ..services.matching_service import job_to_card, upsert_card
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
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).options(selectinload(Job.company)).order_by(Job.id.desc()).all()
