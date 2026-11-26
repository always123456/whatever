from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.extract import extract_card
from ..llm.pdf import PdfParseError, parse_pdf_text
from ..models.db_models import Application, Job, Resume, User
from ..schemas.requirement import RequirementParseResponse
from ..schemas.resume import ResumeCreate, ResumeDetailOut, ResumeOut
from ..services.matching_service import get_card, resume_to_card, upsert_card
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


@router.post("/parse-pdf", response_model=RequirementParseResponse)
async def parse_resume_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """上传简历 PDF：抽取文字层文本 → 复用需求理解 Agent 抽取需求卡预览（不落库）。

    两段式流程第一段：返回卡预览供校对，第二段由 /requirement/apply 合并写回。
    """
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者账号可上传简历 PDF")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, detail="仅支持 PDF 文件")
    data = await file.read()
    try:
        text = parse_pdf_text(data)
    except PdfParseError as e:
        raise HTTPException(422, detail=str(e))
    card, warnings = extract_card("seeker", text)
    return RequirementParseResponse(card=card, warnings=warnings)


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
    for resume, job, app in rows:
        out = by_resume.get(resume.id)
        if out is None:
            out = ResumeOut.model_validate(resume)
            # rows 按投递时间倒序，第一次遇到即该简历最近一次投递，取其回复期限
            out.reply_deadline_days = app.reply_deadline_days
            by_resume[resume.id] = out
        if job.title and job.title not in out.applied_job_titles:
            out.applied_job_titles.append(job.title)
    return list(by_resume.values())


@router.get("/{resume_id}", response_model=ResumeDetailOut)
def get_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """单份简历完整信息。求职者只能看自己的；企业只能看「投了本公司岗位」的简历。"""
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(404, "简历不存在")
    if user.role == "seeker":
        if resume.owner_id != user.id:
            raise HTTPException(404, "简历不存在")
    else:
        applied = (
            db.query(Application)
            .join(Job, Job.id == Application.job_id)
            .filter(Application.resume_id == resume.id, Job.owner_id == user.id)
            .first()
        )
        if applied is None:
            raise HTTPException(404, "简历不存在")

    out = ResumeDetailOut.model_validate(resume)
    if user.role == "enterprise":
        titles = (
            db.query(Job.title)
            .join(Application, Application.job_id == Job.id)
            .filter(Application.resume_id == resume.id, Job.owner_id == user.id)
            .distinct()
            .all()
        )
        out.applied_job_titles = [t[0] for t in titles if t[0]]
    card = get_card(db, "seeker", resume.id, resume_to_card(resume))
    out.facts = card.facts
    out.raw_text = card.raw_text or ""
    return out
