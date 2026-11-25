"""软性偏好打分：各维度归一化到 0-1，加权求和（AI 排序层，权重分方向可调）。

输入为 RequirementCard。方向不同维度不同，权重表分两张（决策4，先简单分配，后续调）：
  seeker_to_jobs        含 company（求职者理想公司 vs 企业实际，LLM 打分带确定性降级）
  enterprise_to_seekers 含 trait（企业理想人才 vs 求职者自评，确定性档位比较）

soft.importance 可覆盖维度权重，覆盖后整表重新归一化，保证总分仍 0-1。
"""
from ..llm.company_traits import score_company_traits
from ..schemas.requirement import (
    TALENT_TRAITS,
    RequirementCard,
    normalize_trait_level,
)
from .embedding import text_similarity

WEIGHTS = {
    "seeker_to_jobs": {
        "skill": 0.24,
        "title": 0.14,
        "salary": 0.14,
        "industry": 0.08,
        "experience": 0.08,
        "text": 0.14,
        "job_types": 0.03,
        "company": 0.15,
    },
    "enterprise_to_seekers": {
        "skill": 0.25,
        "trait": 0.22,
        "salary": 0.13,
        "industry": 0.09,
        "experience": 0.08,
        "text": 0.20,
        "job_types": 0.03,
    },
}


def _skill_overlap(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _industry_match(a: str, b: str) -> float:
    if not a or not b:
        return 0.5  # 一方未填，中性
    return 1.0 if a == b else 0.0


def _salary_fit(job: RequirementCard, seeker: RequirementCard) -> float:
    """岗位薪资覆盖求职者期望区间的比例。"""
    smin = seeker.hard.salary_min
    smax = seeker.hard.salary_max
    jmin = job.hard.salary_min
    jmax = job.hard.salary_max
    if jmax is None or smin is None:
        return 0.5  # 数据不全，中性
    if jmax < smin:
        return 0.0
    seeker_span = (smax if smax is not None else smin) - smin
    if seeker_span <= 0:
        return 1.0
    lo = max(jmin if jmin is not None else smin, smin)
    hi = min(jmax, smax if smax is not None else jmax)
    overlap = max(0.0, hi - lo)
    return min(1.0, overlap / seeker_span)


def _experience_fit(seeker_exp, job_exp) -> float:
    if seeker_exp is None or job_exp is None:
        return 0.5
    extra = seeker_exp - job_exp
    if extra < 0:
        return 0.0
    if extra == 0:
        return 0.7
    if extra <= 2:
        return 0.85
    return 1.0


def _trait_dimension_id(dim: str) -> str:
    """归一化 dimension 到 TALENT_TRAITS 的 id（中文名也兼容）。未知维度原样返回。"""
    if dim in TALENT_TRAITS:
        return dim
    for tid, meta in TALENT_TRAITS.items():
        if meta["name"] == dim:
            return tid
    return dim


def _trait_match(enterprise_traits: list, seeker_traits: list) -> float:
    """企业理想人才特质 vs 求职者自评特质，按 importance 加权。

    - 企业没要求（traits 空）→ 中性 0.5
    - 求职者缺某维度记录 → 该维度 0 分
    - 求职档 >= 期望档 → 1.0；差一档 → 0.5；差两档 → 0.0
    """
    if not enterprise_traits:
        return 0.5
    seeker_by_dim = {
        _trait_dimension_id(t.dimension): normalize_trait_level(t.value)
        for t in (seeker_traits or [])
    }
    score = 0.0
    total_w = 0.0
    for t in enterprise_traits:
        dim = _trait_dimension_id(t.dimension)
        w = max(0.0, float(t.importance or 1.0))
        if w == 0.0:
            continue
        required = normalize_trait_level(t.value)
        if dim not in seeker_by_dim:
            per = 0.0
        else:
            diff = required - seeker_by_dim[dim]
            if diff <= 0:
                per = 1.0
            elif diff <= 0.5:
                per = 0.5
            else:
                per = 0.0
        score += per * w
        total_w += w
    return score / total_w if total_w else 0.5


def _title_match(intended_titles: list, job_title: str) -> float:
    """求职者意向职位 vs 岗位名称的文本相似，取最大值。空 → 中性 0.5。"""
    if not job_title or not intended_titles:
        return 0.5
    return max(text_similarity(t, job_title) for t in intended_titles)


def _job_types_match(job_types: list, target_job_types: list, is_student) -> float:
    """岗位类型 vs 求职意向类型，覆盖率。企业没填 → 中性；求职者没填用 is_student 兜底。"""
    if not job_types:
        return 0.5
    if not target_job_types:
        if is_student is True:
            target_job_types = ["应届校招", "实习生"]
        elif is_student is False:
            target_job_types = ["社招"]
        else:
            return 0.5
    inter = [t for t in job_types if t in target_job_types]
    return len(inter) / len(job_types)


def _card_text(card: RequirementCard) -> str:
    parts = [card.label, card.raw_text or ""]
    parts += list(card.soft.skills or [])
    parts += list(card.soft.industries or [])
    return " ".join(p for p in parts if p)


def compute_score(target: RequirementCard, cand: RequirementCard, direction: str):
    """返回 (总分, 原因列表)。target=搜索者卡, cand=候选卡。"""
    if direction == "seeker_to_jobs":
        job, seeker = cand, target
    else:
        job, seeker = target, cand

    dims = {
        "skill": _skill_overlap(seeker.soft.skills, job.soft.skills),
        "salary": _salary_fit(job, seeker),
        "experience": _experience_fit(seeker.hard.experience_years, job.hard.experience_years),
        "industry": _industry_match(
            (seeker.soft.industries or [""])[0], (job.soft.industries or [""])[0]
        ),
        "text": text_similarity(_card_text(seeker), _card_text(job)),
        "job_types": _job_types_match(
            job.hard.job_types, seeker.soft.target_job_types, seeker.facts.get("is_student")
        ),
    }

    company_reason = ""
    if direction == "seeker_to_jobs":
        dims["title"] = _title_match(seeker.soft.intended_titles, job.label)
        dims["company"], company_reason = score_company_traits(
            seeker.facts.get("ideal_company_traits"), job.facts.get("company_traits")
        )
    else:
        dims["trait"] = _trait_match(job.soft.traits, seeker.soft.traits)

    # 权重（soft.importance 覆盖后重归一化）
    w = dict(WEIGHTS[direction])
    for k, v in (target.soft.importance or {}).items():
        if k in w and v is not None:
            w[k] = float(v)
    wsum = sum(w[k] for k in dims)
    score = sum(w[k] * dims[k] for k in dims) / wsum if wsum else 0.0

    reasons = [
        f"技能重合 {dims['skill']:.2f}",
        f"薪资覆盖 {dims['salary']:.2f}",
        f"经验富余 {dims['experience']:.2f}",
        f"行业{'相同' if dims['industry'] == 1.0 else ('未知' if dims['industry'] == 0.5 else '不同')}",
        f"岗位类型匹配 {dims['job_types']:.2f}",
        f"文本相似 {dims['text']:.2f}",
    ]
    if direction == "seeker_to_jobs":
        reasons.insert(1, f"职位名匹配 {dims['title']:.2f}")
        reasons.append(f"公司特质 {dims['company']:.2f} ({company_reason})")
    else:
        reasons.append(f"特质匹配 {dims['trait']:.2f}")

    return round(score, 4), reasons
