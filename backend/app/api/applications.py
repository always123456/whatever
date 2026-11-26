import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import Application, Job, Resume, User
from ..schemas.application import (
    ApplicationConfirmUpdate,
    ApplicationCreate,
    ApplicationDetailOut,
    ApplicationManageOut,
    ApplicationOut,
    ApplicationStatusUpdate,
)
from ..services.application_service import (
    apply_transition,
    build_application_detail,
    confirm_by_seeker,
    get_owned_application,
    log_event,
)
from .deps import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者投递岗位：缺省用自己最新一份简历，同一简历对同一岗位只投一次。

    投递成功即写首条时间线事件（'' -> 待处理，操作人为求职者）。
    """
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

    app = Application(
        job_id=job.id,
        resume_id=resume.id,
        reply_deadline_days=random.choice([3, 5, 7]),  # 随机预置回复期限，供企业端展示「N天内需回复」
    )
    db.add(app)
    db.flush()
    log_event(db, app.id, "", "待处理", user.id)
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


@router.get("/manage", response_model=list[ApplicationManageOut])
def manage_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """企业「投递管理」列表：本公司岗位收到的投递，含求职者姓名与职位名。"""
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号可管理投递")
    rows = (
        db.query(Application, Job.title, Resume.name)
        .join(Job, Job.id == Application.job_id)
        .join(Resume, Resume.id == Application.resume_id)
        .filter(Job.owner_id == user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [
        ApplicationManageOut(
            id=a.id,
            job_id=a.job_id,
            job_title=title,
            resume_id=a.resume_id,
            seeker_name=name,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a, title, name in rows
    ]


@router.get("/{application_id}", response_model=ApplicationDetailOut)
def get_application_detail(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """投递详情（含状态时间线）：求职者看自己的，企业看本公司岗位的。"""
    app = get_owned_application(db, application_id, user)
    return build_application_detail(db, app)


@router.patch("/{application_id}/status", response_model=ApplicationDetailOut)
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """企业审批：按状态机流转（如退回=拒绝、邀约面试=面试），写时间线事件。"""
    if user.role != "enterprise":
        raise HTTPException(403, detail="仅企业账号可审批投递")
    app = get_owned_application(db, application_id, user)
    apply_transition(db, app, payload.status, user, payload.note)
    db.commit()
    db.refresh(app)
    return build_application_detail(db, app)


@router.post("/{application_id}/confirm", response_model=ApplicationDetailOut)
def confirm_application(
    application_id: int,
    payload: ApplicationConfirmUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者确认当前状态（面试=确认参加面试，录用=确认入职），写同态确认事件。"""
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者可确认")
    app = get_owned_application(db, application_id, user)
    confirm_by_seeker(db, app, user, payload.note)
    db.commit()
    db.refresh(app)
    return build_application_detail(db, app)
