from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import Resume, User
from ..schemas.resume import ResumeCreate, ResumeOut
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
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(db: Session = Depends(get_db)):
    return db.query(Resume).order_by(Resume.id.desc()).all()
