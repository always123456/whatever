"""公司特质 6 轴匹配打分（决策5）：求职者理想公司 vs 企业实际公司。

- LLM 路径：结构化输入，DeepSeek 逐轴打分（temperature=0，结果进程内缓存）
- 确定性降级：逐字段枚举相等性比较（无 key / 调用失败 / 数据缺失时回退）
- 只在 seeker_to_jobs 方向有意义（企业无"理想公司"概念）
"""
import json

from ..schemas.requirement import JOB_FACT_AXES
from .client import LLMUnavailable, chat_json

# 进程内缓存：(理想 JSON, 实际 JSON) -> 总分
_cache: dict[tuple[str, str], float] = {}


def _normalize(traits) -> dict:
    """把 facts 里的公司特质归一化成 {axis: {field: value}}，缺失轴/字段补 None。"""
    traits = traits or {}
    out: dict = {}
    for axis, meta in JOB_FACT_AXES.items():
        raw = traits.get(axis)
        src = raw if isinstance(raw, dict) else {}
        out[axis] = {field_key: src.get(field_key) for field_key, _n, _e in meta["fields"]}
    return out


def _has_data(traits) -> bool:
    """判断某方是否填了任何公司特质数据。"""
    traits = traits or {}
    return any(isinstance(traits.get(a), dict) and bool(traits[a]) for a in JOB_FACT_AXES)


def _deterministic(ideal: dict, company: dict) -> float:
    """确定性降级：逐字段比较（相等=1，不同=0，缺失=0.5），6 轴均值。"""
    ideal_n = _normalize(ideal)
    company_n = _normalize(company)
    axis_scores = []
    for axis in JOB_FACT_AXES:
        field_scores = []
        for field_key, _n, _e in JOB_FACT_AXES[axis]["fields"]:
            iv = ideal_n[axis][field_key]
            cv = company_n[axis][field_key]
            if iv is None or cv is None:
                field_scores.append(0.5)
            else:
                field_scores.append(1.0 if iv == cv else 0.0)
        axis_scores.append(sum(field_scores) / len(field_scores))
    return round(sum(axis_scores) / len(axis_scores), 4)


def _llm_score(ideal: dict, company: dict) -> float:
    """LLM 逐轴打分，返回 0-1 总分。"""
    ideal_n = _normalize(ideal)
    company_n = _normalize(company)
    axes_desc = "\n".join(
        f"- {a} {JOB_FACT_AXES[a]['name']}: "
        + ", ".join(f"{k}({name})" for k, name, _e in JOB_FACT_AXES[a]["fields"])
        for a in JOB_FACT_AXES
    )
    user_msg = (
        "你是人岗匹配系统中的公司特质匹配评分器。比较求职者的【理想公司特质】与企业的【实际公司特质】，"
        "逐轴给出 0-1 匹配分和一句理由，并给出 6 轴等权加权总分。\n\n"
        f"6 个评估轴及字段：\n{axes_desc}\n\n"
        f"求职者理想公司特质(JSON)：{json.dumps(ideal_n, ensure_ascii=False)}\n"
        f"企业实际公司特质(JSON)：{json.dumps(company_n, ensure_ascii=False)}\n\n"
        '仅输出 JSON，格式：{"axes": {"P": {"score": 0.8, "reason": "..."}, "S": ..., "F": ..., '
        '"C": ..., "V": ..., "W": ...}, "total": 0.8}'
    )
    data = chat_json(
        [
            {"role": "system", "content": "你是客观的岗位匹配评分器，只输出 JSON。"},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )
    total = data.get("total")
    if total is None:
        return _deterministic(ideal, company)
    try:
        return max(0.0, min(1.0, float(total)))
    except (TypeError, ValueError):
        return _deterministic(ideal, company)


def score_company_traits(ideal, company) -> tuple[float, str]:
    """返回 (0-1 总分, 理由)。任一方无数据 → 中性 0.5；有 key 走 LLM（缓存），否则确定性降级。"""
    ideal = ideal or {}
    company = company or {}
    if not _has_data(ideal) or not _has_data(company):
        return 0.5, "公司特质未采集"
    cache_key = (
        json.dumps(ideal, sort_keys=True, ensure_ascii=False),
        json.dumps(company, sort_keys=True, ensure_ascii=False),
    )
    if cache_key in _cache:
        return _cache[cache_key], "公司特质匹配(LLM缓存)"
    try:
        score = _llm_score(ideal, company)
        reason = "公司特质匹配(LLM)"
    except LLMUnavailable:
        score = _deterministic(ideal, company)
        reason = "公司特质匹配(确定性降级)"
    _cache[cache_key] = score
    return score, reason
