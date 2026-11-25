"""匹配引擎：硬过滤 -> 软打分 -> 排序，全部为确定性纯函数（公司特质维度为 LLM 打分带确定性降级）。"""
from ..schemas.requirement import RequirementCard
from .constraints import check_hard_constraints
from .scoring import compute_score


def match(
    target: RequirementCard,
    candidates: list,
    direction: str,
    top_n: int = 10,
    min_score: float = 0.0,
):
    """返回 [(cand, score, matched_rules, reasons)]，按分数降序。

    target/candidates 均为 RequirementCard；cand 保留原对象（含 id），供调用方回填候选主键。
    """
    passed = []
    for cand in candidates:
        ok, rules, _failed = check_hard_constraints(target, cand, direction)
        if ok:
            passed.append((cand, rules))

    scored = []
    for cand, rules in passed:
        score, reasons = compute_score(target, cand, direction)
        if score >= min_score:
            scored.append((cand, score, rules, reasons))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]
