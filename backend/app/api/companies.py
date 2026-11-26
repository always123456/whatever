from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import Company, User
from ..schemas.company import CompanyOut, CompanyUpdate
from .deps import get_current_user

router = APIRouter(prefix="/company", tags=["company"])


def get_or_create_company(db: Session, user: User) -> Company:
    """取企业用户的公司档案，不存在则建空档案（MVP 1:1：一个企业用户一家公司）。"""
    company = db.query(Company).filter(Company.owner_id == user.id).first()
    if company is None:
        company = Company(owner_id=user.id)
        db.add(company)
        db.flush()
    return company


@router.get("", response_model=CompanyOut)
def get_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号有公司档案")
    return get_or_create_company(db, user)


@router.put("", response_model=CompanyOut)
def update_company(
    payload: CompanyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号有公司档案")
    company = get_or_create_company(db, user)
    for field, value in payload.model_dump().items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


@router.post("/verify", response_model=CompanyOut)
async def verify_company(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """资质审查（简化版）：企业上传营业执照等资质文件即通过，标记 verified。"""
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号可提交资质审查")
    content = await file.read()
    if not content:
        raise HTTPException(400, detail="请上传资质文件")
    company = get_or_create_company(db, user)
    company.verified = True
    company.verified_at = datetime.now()
    db.commit()
    db.refresh(company)
    return company
