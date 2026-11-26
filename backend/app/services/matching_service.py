from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..matching.engine import match as engine_match
from ..matching.normalize import normalize_industry, normalize_skills
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
    """岗位 ORM → 企业需求卡。公司级字段取自 job.company（companies 表）。

    industry 双来源：岗位行业优先，未填回退公司行业（避免行业维度因岗位留空而中性化）。
    """
    company = job.company
    industry = job.industry or (company.industry if company else "")
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
            must_skills=normalize_skills(job.must_skills),
            job_types=job.job_types or [],
        ),
        soft=SoftPreference(
            skills=normalize_skills(job.skills),
            industries=[normalize_industry(industry)] if industry else [],
            traits=[TraitItem(**t) for t in (job.ideal_talents or [])],
        ),
        facts={
            "company_name": company.name if company else "",
            "company_abbr": company.abbr if company else "",
            "company_size": company.size if company else "",
            "industry": industry,
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
            skills=normalize_skills(r.skills),
            industries=[normalize_industry(r.industry)] if r.industry else [],
            intended_titles=r.intended_titles or [],
            target_job_types=r.target_job_types or [],
            traits=[TraitItem(**t) for t in (r.self_traits or [])],
        ),
        facts={
            "is_student": None,  # 学生与否：Agent 抽取优先，表单后补（MVP 中性）
            "self_assessment": r.summary,
            "ideal_company_traits": r.ideal_company_traits or {},
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
        if r.owner_id != user.id:
            raise HTTPException(403, "只能使用自己的简历进行匹配")
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
        if j.owner_id != user.id:
            raise HTTPException(403, "只能使用自己发布的职位进行匹配")
        return j
    j = db.query(Job).filter(Job.owner_id == user.id).order_by(Job.id.desc()).first()
    if j is None:
        raise HTTPException(400, "请先发布职位")
    return j


def match(db: Session, user: User, req) -> MatchResult:
    direction = req.direction
    top_n = req.top_n or settings.top_n

    # 匹配方向必须与账号角色一致：求职者只能「求职者→职位」，企业只能「企业→求职者」
    expected = "seeker_to_jobs" if user.role == "seeker" else "enterprise_to_seekers"
    if direction != expected:
        raise HTTPException(403, f"当前账号仅支持 {expected} 方向的匹配")

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


def _non_empty(v) -> bool:
    """抽取字段「非空」判定：None/空串/空容器视为空；False/0 视为有效值（如 is_student=False）。"""
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return bool(v)
    return True


def _merge_cards(existing: RequirementCard, extracted: RequirementCard) -> RequirementCard:
    """抽取卡合并进已有卡：抽取的非空 hard/soft 覆盖，facts 逐键补非空、不覆盖已有非空。"""
    merged = existing.model_copy(deep=True)
    xh, xs, xf = extracted.hard, extracted.soft, extracted.facts

    # hard 标量：抽取非 None 才覆盖；remote 仅抽取为 True 时覆盖（避免误清表单）
    for field in ("location", "salary_min", "salary_max", "education", "experience_years", "job_status"):
        v = getattr(xh, field)
        if v is not None:
            setattr(merged.hard, field, v)
    if xh.remote:
        merged.hard.remote = True
    if xh.must_skills:
        merged.hard.must_skills = xh.must_skills
    if xh.job_types:
        merged.hard.job_types = xh.job_types

    # soft：抽取非空才覆盖
    for field in ("skills", "industries", "intended_titles", "target_job_types"):
        v = getattr(xs, field)
        if v:
            setattr(merged.soft, field, v)
    if xs.traits:
        merged.soft.traits = xs.traits

    # facts：逐键补非空，已有非空不被空值覆盖
    for k, v in (xf or {}).items():
        if _non_empty(v):
            merged.facts[k] = v

    merged.source = "llm"
    if extracted.raw_text:
        merged.raw_text = extracted.raw_text
    return merged


def _resume_for_apply(db: Session, user: User, target_id, card: RequirementCard) -> Resume:
    """apply 的目标简历：显式 target_id 校验归属；缺省取最新一份，没有则从抽取卡自动建一份。

    PDF/原文抽取场景求职者可能尚未建简历，此时自动建档，抽取字段随后由 _sync_resume_columns 回填。
    """
    if target_id is not None:
        resume = db.get(Resume, target_id)
        if resume is None:
            raise HTTPException(404, "简历不存在")
        if resume.owner_id != user.id:
            raise HTTPException(403, "只能写自己的简历")
        return resume
    resume = db.query(Resume).filter(Resume.owner_id == user.id).order_by(Resume.id.desc()).first()
    if resume is None:
        resume = Resume(
            owner_id=user.id,
            name=card.label or "未命名简历",
            location=card.hard.location or "",
        )
        db.add(resume)
        db.flush()
    return resume


def _sync_resume_columns(resume: Resume, card: RequirementCard) -> None:
    """把合并后的需求卡回填到 resumes 表结构化列（简历列表/企业投递视角据此展示）。

    merged 卡已是「表单值 + 抽取值」合并后的最终态，直接整体同步即等价于增量回填。
    """
    h, s, f = card.hard, card.soft, card.facts
    if card.label:
        resume.name = card.label
    if h.location is not None:
        resume.location = h.location
    resume.expected_salary_min = h.salary_min
    resume.expected_salary_max = h.salary_max
    if h.education is not None:
        resume.education = h.education
    if h.experience_years is not None:
        resume.experience_years = h.experience_years
    resume.willing_remote = h.remote
    if h.job_status is not None:
        resume.job_status = h.job_status
    if s.skills:
        resume.skills = s.skills
    if s.industries:
        resume.industry = s.industries[0]
    if s.intended_titles:
        resume.intended_titles = s.intended_titles
    if s.target_job_types:
        resume.target_job_types = s.target_job_types
    if s.traits:
        resume.self_traits = [t.model_dump() for t in s.traits]
    if f.get("self_assessment"):
        resume.summary = f["self_assessment"]


def apply_extracted_card(db: Session, user: User, role: str, target_id, card: RequirementCard) -> RequirementCard:
    """把抽取预览卡合并写回目标实体（简历/职位）的需求卡。校验归属：只能写自己的实体。"""
    if role == "seeker":
        if user.role != "seeker":
            raise HTTPException(403, "仅求职者可写求职卡")
        resume = _resume_for_apply(db, user, target_id, card)
        existing = get_card(db, "seeker", resume.id, resume_to_card(resume))
        merged = _merge_cards(existing, card)
        _sync_resume_columns(resume, merged)
        upsert_card(db, "seeker", resume.id, merged, source="llm")
    else:
        if user.role != "enterprise":
            raise HTTPException(403, "仅企业可写岗位卡")
        job = _target_for_enterprise(db, user, target_id)
        if job.owner_id != user.id:
            raise HTTPException(403, "只能写自己的职位")
        existing = get_card(db, "enterprise", job.id, job_to_card(job))
        merged = _merge_cards(existing, card)
        upsert_card(db, "enterprise", job.id, merged, source="llm")
    db.commit()
    return merged
