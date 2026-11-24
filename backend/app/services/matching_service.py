from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..matching.engine import match as engine_match
from ..models.db_models import Job, Resume, User
from ..schemas.matching import MatchItem, MatchResult


def _fmt_salary(profile: dict) -> str:
    lo = profile["salary_min"]
    hi = profile["salary_max"]
    if lo is None and hi is None:
        return "面议"
    if lo is None:
        return f"≤{hi:.0f}k"
    if hi is None:
        return f"≥{lo:.0f}k"
    return f"{lo:.0f}-{hi:.0f}k"


def job_to_profile(job: Job) -> dict:
    return {
        "id": job.id,
        "kind": "job",
        "label": job.title,
        "company": job.company,
        "location": job.location,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "education": job.education,
        "experience_years": job.experience_years,
        "industry": job.industry,
        "skills": job.skills or [],
        "remote": job.remote,
        "text": " ".join([job.title, job.industry, job.description, " ".join(job.skills or [])]),
    }


def resume_to_profile(r: Resume) -> dict:
    return {
        "id": r.id,
        "kind": "resume",
        "label": r.name,
        "location": r.location,
        "salary_min": r.expected_salary_min,
        "salary_max": r.expected_salary_max,
        "education": r.education,
        "experience_years": r.experience_years,
        "industry": r.industry,
        "skills": r.skills or [],
        "remote": r.willing_remote,
        "text": " ".join([r.name, r.industry, r.summary, " ".join(r.skills or [])]),
    }


def _payload(profile: dict) -> dict:
    base = {
        "name": profile["label"],
        "location": profile["location"],
        "skills": profile["skills"],
        "industry": profile["industry"],
        "education": profile["education"],
        "experience_years": profile["experience_years"],
        "salary": _fmt_salary(profile),
    }
    if profile["kind"] == "job":
        base["company"] = profile.get("company", "")
    return base


def _target_for_seeker(db: Session, user: User, target_id):
    if target_id is not None:
        r = db.get(Resume, target_id)
        if r is None:
            raise HTTPException(404, "简历不存在")
        return r
    r = db.query(Resume).filter(Resume.owner_id == user.id).order_by(Resume.id.desc()).first()
    if r is None:
        raise HTTPException(400, "请先完善你的简历")
    return r


def _target_for_enterprise(db: Session, user: User, target_id):
    if target_id is not None:
        j = db.get(Job, target_id)
        if j is None:
            raise HTTPException(404, "职位不存在")
        return j
    j = db.query(Job).filter(Job.owner_id == user.id).order_by(Job.id.desc()).first()
    if j is None:
        raise HTTPException(400, "请先发布职位")
    return j


def match(db: Session, user: User, req) -> MatchResult:
    direction = req.direction
    top_n = req.top_n or settings.top_n

    if direction == "seeker_to_jobs":
        resume = _target_for_seeker(db, user, req.target_id)
        target = resume_to_profile(resume)
        candidates = [job_to_profile(j) for j in db.query(Job).all()]
    else:
        job = _target_for_enterprise(db, user, req.target_id)
        target = job_to_profile(job)
        candidates = [resume_to_profile(r) for r in db.query(Resume).all()]

    items = []
    for cand, score, rules, reasons in engine_match(target, candidates, direction, top_n):
        items.append(
            MatchItem(
                candidate_id=cand["id"],
                score=score,
                matched_rules=rules,
                reasons=reasons,
                payload=_payload(cand),
            )
        )
    return MatchResult(direction=direction, results=items)
