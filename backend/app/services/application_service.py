"""投递审批服务：状态机流转 + 时间线事件 + 详情组装。

状态机（与 schemas/application.py ALLOWED_TRANSITIONS 一致）：
  待处理 -> 已查看 | 面试 | 拒绝
  已查看 -> 面试 | 拒绝
  面试   -> 录用 | 拒绝
  录用/拒绝为终态。
投递创建时由求职者写首条事件（'' -> 待处理），此后每次流转由企业写一条。
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.db_models import Application, ApplicationEvent, Job, Resume, User
from ..schemas.application import (
    ALLOWED_TRANSITIONS,
    APPLICATION_STATUSES,
    ApplicationDetailOut,
    ApplicationEventOut,
    ResumeBrief,
)


# 求职者可确认的状态档位：同态确认事件（from==to），每档只能确认一次
SEEKER_CONFIRMABLE = {"面试": "确认参加面试", "录用": "确认入职"}


def log_event(
    db: Session,
    application_id: int,
    from_status: str,
    to_status: str,
    operator_id: int,
    note: str | None = None,
) -> ApplicationEvent:
    event = ApplicationEvent(
        application_id=application_id,
        from_status=from_status,
        to_status=to_status,
        operator_id=operator_id,
        note=note,
    )
    db.add(event)
    db.flush()
    return event


def apply_transition(
    db: Session,
    app: Application,
    to_status: str,
    operator: User,
    note: str | None = None,
) -> Application:
    """校验并执行一次状态流转（写时间线事件），返回更新后的投递记录。"""
    if to_status not in APPLICATION_STATUSES:
        raise HTTPException(400, detail=f"无效状态：{to_status}")
    allowed = ALLOWED_TRANSITIONS.get(app.status)
    if not allowed:
        raise HTTPException(400, detail=f"当前状态「{app.status}」为终态，不可再流转")
    if to_status not in allowed:
        detail = f"不允许从「{app.status}」流转到「{to_status}」"
        raise HTTPException(400, detail=detail)
    from_status = app.status
    app.status = to_status
    log_event(db, app.id, from_status, to_status, operator.id, note)
    return app


def confirm_by_seeker(
    db: Session,
    app: Application,
    user: User,
    note: str | None = None,
) -> Application:
    """求职者确认当前状态（面试/录用）：写一条同态确认事件（from==to）。

    - 仅面试/录用两档可确认；其他状态 400
    - 每档只能确认一次；重复确认 409
    """
    label = SEEKER_CONFIRMABLE.get(app.status)
    if label is None:
        raise HTTPException(400, detail=f"当前状态「{app.status}」无需求职者确认")
    dup = (
        db.query(ApplicationEvent)
        .filter(
            ApplicationEvent.application_id == app.id,
            ApplicationEvent.from_status == app.status,
            ApplicationEvent.to_status == app.status,
            ApplicationEvent.operator_id == user.id,
        )
        .first()
    )
    if dup is not None:
        raise HTTPException(409, detail=f"已确认过「{app.status}」")
    text = note.strip() if note and note.strip() else label
    log_event(db, app.id, app.status, app.status, user.id, text)
    return app


def _operator_names(db: Session, events: list[ApplicationEvent]) -> dict[int, str]:
    ids = {e.operator_id for e in events}
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: (u.display_name or u.username) for u in users}


def build_application_detail(db: Session, app: Application) -> ApplicationDetailOut:
    """组装投递详情：职位名 + 求职者名 + 简历摘要 + 状态时间线（按发生顺序）。"""
    job = db.get(Job, app.job_id)
    resume = db.get(Resume, app.resume_id)
    events = (
        db.query(ApplicationEvent)
        .filter(ApplicationEvent.application_id == app.id)
        .order_by(ApplicationEvent.id)
        .all()
    )
    names = _operator_names(db, events)
    # 求职者确认过的档位：同态事件（from==to）且操作人为投递人本人
    confirmed = (
        [e.to_status for e in events
         if e.from_status == e.to_status and resume is not None and e.operator_id == resume.owner_id]
    )
    return ApplicationDetailOut(
        id=app.id,
        job_id=app.job_id,
        resume_id=app.resume_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        job_title=job.title if job else "",
        seeker_name=resume.name if resume else "",
        resume=ResumeBrief.model_validate(resume) if resume else None,
        events=[
            ApplicationEventOut(
                id=e.id,
                application_id=e.application_id,
                from_status=e.from_status,
                to_status=e.to_status,
                operator_id=e.operator_id,
                operator_name=names.get(e.operator_id),
                note=e.note,
                created_at=e.created_at,
            )
            for e in events
        ],
        seeker_confirmed_statuses=confirmed,
    )


def get_owned_application(db: Session, application_id: int, user: User) -> Application:
    """按角色校验归属并返回投递记录：企业须是职位发布者，求职者须是投递人。"""
    app = db.get(Application, application_id)
    if app is None:
        raise HTTPException(404, detail="投递记录不存在")
    if user.role == "enterprise":
        job = db.get(Job, app.job_id)
        if job is None or job.owner_id != user.id:
            raise HTTPException(403, detail="只能操作本公司岗位的投递记录")
    else:
        resume = db.get(Resume, app.resume_id)
        if resume is None or resume.owner_id != user.id:
            raise HTTPException(403, detail="只能查看自己的投递记录")
    return app
