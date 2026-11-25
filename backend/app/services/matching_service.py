from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..matching.engine import match as engine_match
from ..models.db_models import Job, MatchRecord, RequirementCardRecord, Resume, User
from ..schemas.matching import MatchItem, MatchResult
from ..schemas.requirement import (
    HardConstraint,
    RequirementCard,
    SoftPreference,
    TraitItem,
)

# 企业端筛选/次级排序：到岗状态越早越靠前（决策3，仅排序不参与打分）
AVAILABILITY_RANK = {"随时到岗": 0, "本月到岗": 1, "观望了解": 2}


def job_to_card(job: Job) -> RequirementCard:
    """岗位 ORM → 企业需求卡。公司级字段取自 job.company（companies 表）。"""
    company = job.company
    return RequirementCard(
        id=job.id,
        role="enterprise",
        label=job.title,
        hard=HardConstraint(
            location=job.location,
            remote=job.remote,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            education=job.education,
            experience_years=job.experience_years,
            must_skills=job.must_skills or [],
            job_types=job.job_types or [],
        ),
        soft=SoftPreference(
            skills=job.skills or [],
            industries=[job.industry] if job.industry else [],
            traits=[TraitItem(**t) for t in (job.ideal_talents or [])],
        ),
        facts={
            "company_name": company.name if company else "",
            "company_abbr": company.abbr if company else "",
            "company_size": company.size if company else "",
            "industry": job.industry or (company.industry if company else ""),
            "overtime": company.overtime if company else "",
            "social_insurance": company.social_insurance if company else "",
            "company_traits": (company.company_traits or {}) if company else {},
        },
        source="form",
        raw_text=job.description,
    )


def resume_to_card(r: Resume) -> RequirementCard:
    """简历 ORM → 求职者需求卡。self_traits 是 [{dimension,value}] 列表（自评弱/中/强）。"""
    return RequirementCard(
        id=r.id,
        role="seeker",
        label=r.name,
        hard=HardConstraint(
            location=r.location,
            remote=r.willing_remote,
            salary_min=r.expected_salary_min,
            salary_max=r.expected_salary_max,
            education=r.education,
            experience_years=r.experience_years,
            job_status=r.job_status,
        ),
        soft=SoftPreference(
            skills=r.skills or [],
            industries=[r.industry] if r.industry else [],
            intended_titles=r.intended_titles or [],
            target_job_types=r.target_job_types or [],
            traits=[TraitItem(**t) for t in (r.self_traits or [])],
        ),
        facts={
            "is_student": None,  # 学生与否：Agent 抽取优先，表单后补（MVP 中性）
            "self_assessment": r.summary,
        },
        source="form",
        raw_text=r.summary,
    )


def upsert_card(db: Session, role: str, ref_id: int, card: RequirementCard, source: str = "form") -> None:
    """写路径统一落卡。表单更新时保留卡里已有 facts（Agent 抽取字段不被表单覆盖）。"""
    row = db.query(RequirementCardRecord).filter_by(role=role, ref_id=ref_id).first()
    if row is None:
        row = RequirementCardRecord(role=role, ref_id=ref_id, source=source)
        db.add(row)
    else:
        try:
            existing = RequirementCard.model_validate(row.card) if row.card else None
            if existing is not None and existing.facts:
                card.facts = {**existing.facts, **card.facts}
        except Exception:
            pass
    card.id = ref_id  # 回填实体主键，匹配结果 candidate_id 用
    row.card = card.model_dump(mode="json")
    row.raw_text = card.raw_text
    row.source = source
    db.flush()


def get_card(db: Session, role: str, ref_id: int, fallback: RequirementCard) -> RequirementCard:
    """优先读落库卡（含 Agent 抽取的 facts），无卡则用表单派生的 fallback。"""
    row = db.query(RequirementCardRecord).filter_by(role=role, ref_id=ref_id).first()
    if row and row.card:
        try:
            return RequirementCard.model_validate(row.card)
        except Exception:
            pass
    return fallback


def _fmt_salary(card: RequirementCard) -> str:
    lo = card.hard.salary_min
    hi = card.hard.salary_max
    if lo is None and hi is None:
        return "面议"
    if lo is None:
        return f"≤{hi:.0f}k"
    if hi is None:
        return f"≥{lo:.0f}k"
    return f"{lo:.0f}-{hi:.0f}k"


def _payload(card: RequirementCard) -> dict:
    base = {
        "name": card.label,
        "location": card.hard.location,
        "skills": card.soft.skills,
        "industry": (card.soft.industries or [""])[0],
        "education": card.hard.education,
        "experience_years": card.hard.experience_years,
        "salary": _fmt_salary(card),
    }
    if card.role == "enterprise":
        base["company"] = card.facts.get("company_name", "")
        base["job_types"] = card.hard.job_types
    else:
        base["job_status"] = card.hard.job_status
        base["intended_titles"] = card.soft.intended_titles
        base["target_job_types"] = card.soft.target_job_types
        base["self_traits"] = [t.model_dump() for t in card.soft.traits]
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
        target = get_card(db, "seeker", resume.id, resume_to_card(resume))
        candidates = [
            get_card(db, "enterprise", j.id, job_to_card(j))
            for j in db.query(Job).options(selectinload(Job.company)).all()
        ]
    else:
        job = _target_for_enterprise(db, user, req.target_id)
        target = get_card(db, "enterprise", job.id, job_to_card(job))
        candidates = [
            get_card(db, "seeker", r.id, resume_to_card(r))
            for r in db.query(Resume).all()
        ]

    # 决策3：企业端按求职状态筛选（不进打分）
    if direction == "enterprise_to_seekers" and req.availability:
        candidates = [c for c in candidates if c.hard.job_status == req.availability]

    results = engine_match(target, candidates, direction, top_n)

    # 决策3：企业端同分时按到岗状态做次级排序（主分降序优先）
    if direction == "enterprise_to_seekers":
        results = sorted(
            results,
            key=lambda x: (-x[1], AVAILABILITY_RANK.get(x[0].hard.job_status or "", 2)),
        )

    # 落匹配记录：快照目标卡，历史分数不因卡后续变化而漂移
    target_dump = target.model_dump(mode="json")
    for cand, score, rules, reasons in results:
        db.add(MatchRecord(
            user_id=user.id,
            direction=direction,
            target_role=target.role,
            target_id=target.id,
            target_card=target_dump,
            candidate_role=cand.role,
            candidate_id=cand.id,
            score=score,
            matched_rules=rules,
            reasons=reasons,
        ))
    db.commit()

    items = [
        MatchItem(
            candidate_id=cand.id,
            score=score,
            matched_rules=rules,
            reasons=reasons,
            payload=_payload(cand),
        )
        for cand, score, rules, reasons in results
    ]
    return MatchResult(direction=direction, results=items)
