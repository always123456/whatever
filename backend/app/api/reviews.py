from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models.db_models import Job, JobReview, User
from ..schemas.review import (
    ReviewCreate,
    ReviewListOut,
    ReviewOut,
    ReviewStats,
    ReviewUpdate,
)
from .deps import get_current_user

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _get_visible_job(db: Session, job_id: int, user: User) -> Job:
    """取岗位并按角色校验可见性：求职者可看任意岗位，企业只能看自己发布的。"""
    job = db.query(Job).options(selectinload(Job.company)).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(404, detail="职位不存在")
    if user.role == "enterprise" and job.owner_id != user.id:
        raise HTTPException(403, detail="只能查看自己发布岗位的评价")
    return job


def _review_out(review: JobReview, reviewer_name: str, is_mine: bool) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        job_id=review.job_id,
        reviewer_id=review.reviewer_id,
        reviewer_name=reviewer_name,
        rating=review.rating,
        content=review.content,
        anonymous=review.anonymous,
        is_mine=is_mine,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _build_list(db: Session, job: Job, user: User) -> ReviewListOut:
    reviews = (
        db.query(JobReview)
        .filter(JobReview.job_id == job.id)
        .order_by(JobReview.created_at.desc())
        .all()
    )
    out_reviews: list[ReviewOut] = []
    for r in reviews:
        reviewer = db.get(User, r.reviewer_id)
        name = "" if reviewer is None else (reviewer.display_name or reviewer.username)
        if r.anonymous:
            name = "匿名求职者"
        out_reviews.append(_review_out(r, name, r.reviewer_id == user.id))

    stats = ReviewStats(job_id=job.id, count=len(reviews))
    if reviews:
        stats.avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 2)

    return ReviewListOut(
        job_id=job.id,
        job_title=job.title,
        company_name=job.company.name if job.company else "",
        stats=stats,
        reviews=out_reviews,
    )


@router.get("", response_model=ReviewListOut)
def list_reviews(
    job_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """某岗位的评价流 + 聚合评分（求职者可看任意岗位，企业只看自己发布的）。"""
    job = _get_visible_job(db, job_id, user)
    return _build_list(db, job, user)


@router.post("", response_model=ReviewOut, status_code=201)
def create_review(
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者评价某岗位：一人对同一岗位仅一条，重复提交 409。"""
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者可发表评价")
    job = _get_visible_job(db, payload.job_id, user)

    dup = (
        db.query(JobReview)
        .filter(JobReview.job_id == payload.job_id, JobReview.reviewer_id == user.id)
        .first()
    )
    if dup is not None:
        raise HTTPException(409, detail="你已评价过该岗位，可修改而非重复提交")

    review = JobReview(
        job_id=payload.job_id,
        reviewer_id=user.id,
        rating=payload.rating,
        content=payload.content,
        anonymous=payload.anonymous,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _review_out(review, user.display_name or user.username, True)


@router.patch("/{review_id}", response_model=ReviewOut)
def update_review(
    review_id: int,
    payload: ReviewUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者修改自己的评价：只更新显式给出的字段。"""
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者可修改评价")
    review = db.get(JobReview, review_id)
    if review is None:
        raise HTTPException(404, detail="评价不存在")
    if review.reviewer_id != user.id:
        raise HTTPException(403, detail="只能修改自己的评价")

    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        setattr(review, field, value)
    db.commit()
    db.refresh(review)
    return _review_out(review, user.display_name or user.username, True)


@router.delete("/{review_id}", status_code=204)
def delete_review(
    review_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """求职者删除自己的评价。"""
    if user.role != "seeker":
        raise HTTPException(403, detail="仅求职者可删除评价")
    review = db.get(JobReview, review_id)
    if review is None:
        raise HTTPException(404, detail="评价不存在")
    if review.reviewer_id != user.id:
        raise HTTPException(403, detail="只能删除自己的评价")
    db.delete(review)
    db.commit()
    return None
