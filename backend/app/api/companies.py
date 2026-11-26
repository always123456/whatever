from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.extract import extract_company_profile
from ..llm.pdf import PdfParseError, parse_pdf_text
from ..models.db_models import Company, User
from ..schemas.company import (
    CompanyApplyRequest,
    CompanyExtraction,
    CompanyOut,
    CompanyParseResponse,
    CompanyUpdate,
)
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


def merge_company_extraction(company: Company, ext: CompanyExtraction) -> None:
    """把抽取结果合并进公司档案：非空字段覆盖、空字段保留原值，公司特质逐轴合并。"""
    for field in ("name", "abbr", "size", "industry", "overtime", "social_insurance"):
        v = getattr(ext, field)
        if v and v.strip():
            setattr(company, field, v.strip())
    if isinstance(ext.company_traits, dict) and ext.company_traits:
        existing = dict(company.company_traits or {})
        for aid, obj in ext.company_traits.items():
            if isinstance(obj, dict) and obj:
                existing[aid] = {**(existing.get(aid) or {}), **obj}
        company.company_traits = existing


@router.post("/parse-pdf", response_model=CompanyParseResponse)
async def parse_company_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """公司信息 PDF 两段式第一段：抽文字层 → 提取公司基本信息预览（不落库）。"""
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号可上传公司 PDF")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, detail="仅支持 PDF 文件")
    data = await file.read()
    try:
        text = parse_pdf_text(data)
    except PdfParseError as e:
        raise HTTPException(422, detail=str(e))
    company, warnings = extract_company_profile(text)
    return CompanyParseResponse(company=company, raw_text=text, warnings=warnings)


@router.post("/apply-extracted", response_model=CompanyOut)
def apply_company_extraction(
    payload: CompanyApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """公司信息 PDF 两段式第二段：确认后合并写入公司档案（非空覆盖、空保留）。"""
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号可写入公司档案")
    company = get_or_create_company(db, user)
    merge_company_extraction(company, payload.company)
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
