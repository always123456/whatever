"""硬性条件过滤：必须全部满足，否则直接排除（规则兜底层）。

输入为 RequirementCard（三个 Agent 的契约），按 direction 比较两侧取值。

方向说明：
  seeker_to_jobs         target=求职者卡, candidate=岗位卡
  enterprise_to_seekers  target=岗位卡,   candidate=求职者卡

双语义字段（education / experience_years）：企业卡=最低要求，求职卡=自身水平，
本层统一抽成 job/seeker 后按同一条规则比较，不再分方向写两份。
数据不全（None）视为通过，避免误过滤；必备技能缺一淘汰。
"""
from ..schemas.requirement import RequirementCard

EDU_LEVELS = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}


def _edu(text) -> int:
    return EDU_LEVELS.get(text, 2)  # 未知学历按本科处理，避免误伤


def _ge_or_none(a, b) -> bool:
    """a >= b；任一方为 None（数据不全）视为通过，避免误过滤。"""
    if a is None or b is None:
        return True
    return a >= b


def _split_direction(target: RequirementCard, cand: RequirementCard, direction: str):
    """按方向抽成 (job_card, seeker_card)。"""
    if direction == "seeker_to_jobs":
        return cand, target
    return target, cand


def check_hard_constraints(target: RequirementCard, cand: RequirementCard, direction: str):
    """返回 (通过, 通过的规则名列表, 未通过的规则名列表)。"""
    passed: list[str] = []
    failed: list[str] = []
    job, seeker = _split_direction(target, cand, direction)

    # 地点：同城 或 任一方支持远程
    if job.hard.location == seeker.hard.location or job.hard.remote or seeker.hard.remote:
        passed.append("地点匹配")
    else:
        failed.append("地点不符")

    # 薪资：岗位上限 >= 求职者下限（区间有交集才不淘汰）
    if _ge_or_none(job.hard.salary_max, seeker.hard.salary_min):
        passed.append("薪资匹配")
    else:
        failed.append("薪资不达标")

    # 学历：求职者 >= 岗位最低
    if _edu(seeker.hard.education) >= _edu(job.hard.education):
        passed.append("学历达标")
    else:
        failed.append("学历不达标")

    # 经验：求职者 >= 岗位最低
    if _ge_or_none(seeker.hard.experience_years, job.hard.experience_years):
        passed.append("经验达标")
    else:
        failed.append("经验不足")

    # 必备技能：岗位 must_skills 全被求职者技能覆盖，缺一淘汰
    missing = [s for s in job.hard.must_skills if s not in set(seeker.soft.skills)]
    if not missing:
        passed.append("必备技能达标")
    else:
        failed.append("必备技能缺失")

    return (len(failed) == 0, passed, failed)


def _fmt_salary_range(card: RequirementCard) -> str:
    """把卡片薪资区间格式化为可读字符串（单位 k）。"""
    lo = card.hard.salary_min
    hi = card.hard.salary_max
    if lo is None and hi is None:
        return "面议"
    if lo is None:
        return f"≤{hi:.0f}k"
    if hi is None:
        return f"≥{lo:.0f}k"
    return f"{lo:.0f}-{hi:.0f}k"


def _fmt_exp_years(years) -> str:
    return "不限" if years is None else f"{years} 年"


def hard_constraint_detail(target: RequirementCard, cand: RequirementCard, direction: str) -> list:
    """结构化硬条件明细：每条含岗位要求、求职者情况、是否通过。

    与 check_hard_constraints 同一套规则，供前端「查看详情」弹窗展示
    「该岗位要求 vs 求职者具体信息」的逐条对比。
    """
    job, seeker = _split_direction(target, cand, direction)

    loc_ok = job.hard.location == seeker.hard.location or job.hard.remote or seeker.hard.remote
    sal_ok = _ge_or_none(job.hard.salary_max, seeker.hard.salary_min)
    edu_ok = _edu(seeker.hard.education) >= _edu(job.hard.education)
    exp_ok = _ge_or_none(seeker.hard.experience_years, job.hard.experience_years)
    missing = [s for s in job.hard.must_skills if s not in set(seeker.soft.skills)]
    skill_ok = not missing

    return [
        {
            "key": "location",
            "label": "地点",
            "job_value": (job.hard.location or "不限") + ("（支持远程）" if job.hard.remote else ""),
            "seeker_value": (seeker.hard.location or "不限") + ("（可远程）" if seeker.hard.remote else ""),
            "passed": loc_ok,
        },
        {
            "key": "salary",
            "label": "薪资",
            "job_value": _fmt_salary_range(job),
            "seeker_value": _fmt_salary_range(seeker),
            "passed": sal_ok,
        },
        {
            "key": "education",
            "label": "学历",
            "job_value": f"最低 {job.hard.education or '不限'}",
            "seeker_value": seeker.hard.education or "未填",
            "passed": edu_ok,
        },
        {
            "key": "experience",
            "label": "经验",
            "job_value": f"最低 {_fmt_exp_years(job.hard.experience_years)}",
            "seeker_value": _fmt_exp_years(seeker.hard.experience_years),
            "passed": exp_ok,
        },
        {
            "key": "must_skills",
            "label": "必备技能",
            "job_value": "、".join(job.hard.must_skills) if job.hard.must_skills else "无",
            "seeker_value": "、".join(seeker.soft.skills) if seeker.soft.skills else "未填",
            "passed": skill_ok,
        },
    ]
