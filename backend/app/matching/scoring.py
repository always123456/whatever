"""软性偏好打分：各维度归一化到 0-1，加权求和（AI 排序层，权重可调）。"""
from .embedding import text_similarity

WEIGHTS = {
    "skill": 0.35,
    "industry": 0.15,
    "salary": 0.20,
    "experience": 0.10,
    "text": 0.20,
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


def _salary_fit(job: dict, seeker: dict) -> float:
    """岗位薪资覆盖求职者期望区间的比例。"""
    smin = seeker["salary_min"]
    smax = seeker["salary_max"]
    jmin = job["salary_min"]
    jmax = job["salary_max"]
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


def _experience_fit(seeker_exp: int, job_exp: int) -> float:
    extra = seeker_exp - job_exp
    if extra < 0:
        return 0.0
    if extra == 0:
        return 0.7
    if extra <= 2:
        return 0.85
    return 1.0


def compute_score(target: dict, cand: dict, direction: str):
    """返回 (总分, 原因列表)。target=搜索者画像, cand=候选画像。"""
    if direction == "seeker_to_jobs":
        job, seeker = cand, target
    else:
        job, seeker = target, cand

    skill = _skill_overlap(target["skills"], cand["skills"])
    industry = _industry_match(target["industry"], cand["industry"])
    salary = _salary_fit(job, seeker)
    experience = _experience_fit(seeker["experience_years"], job["experience_years"])
    text = text_similarity(target["text"], cand["text"])

    score = (
        WEIGHTS["skill"] * skill
        + WEIGHTS["industry"] * industry
        + WEIGHTS["salary"] * salary
        + WEIGHTS["experience"] * experience
        + WEIGHTS["text"] * text
    )

    reasons = [
        f"技能重合 {skill:.2f}",
        f"行业{'相同' if industry == 1.0 else ('未知' if industry == 0.5 else '不同')}",
        f"薪资覆盖 {salary:.2f}",
        f"经验富余 {experience:.2f}",
        f"文本相似 {text:.2f}",
    ]
    return round(score, 4), reasons
