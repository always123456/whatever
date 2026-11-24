"""硬性条件过滤：必须全部满足，否则直接排除（规则兜底层）。

方向说明：
  seeker_to_jobs         target=求职者简历, candidate=职位
  enterprise_to_seekers  target=职位,       candidate=简历
"""
EDU_LEVELS = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}


def _edu(text: str) -> int:
    return EDU_LEVELS.get(text, 2)  # 未知学历按本科处理，避免误伤


def _ge_or_none(a, b) -> bool:
    """a >= b；任一方为 None（数据不全）视为通过，避免误过滤。"""
    if a is None or b is None:
        return True
    return a >= b


def check_hard_constraints(target: dict, cand: dict, direction: str):
    """返回 (通过, 通过的规则名列表, 未通过的规则名列表)。"""
    passed: list[str] = []
    failed: list[str] = []

    # 地点：同城 或 任一方支持远程
    if target["location"] == cand["location"] or target.get("remote") or cand.get("remote"):
        passed.append("地点匹配")
    else:
        failed.append("地点不符")

    if direction == "seeker_to_jobs":
        # target=简历(seeker)  cand=职位(job)
        if _ge_or_none(cand["salary_max"], target["salary_min"]):
            passed.append("薪资匹配")
        else:
            failed.append("薪资不达标")
        if _edu(target["education"]) >= _edu(cand["education"]):
            passed.append("学历达标")
        else:
            failed.append("学历不达标")
        if _ge_or_none(target["experience_years"], cand["experience_years"]):
            passed.append("经验达标")
        else:
            failed.append("经验不足")
    else:
        # target=职位(job)  cand=简历(seeker)
        if _ge_or_none(target["salary_max"], cand["salary_min"]):
            passed.append("薪资匹配")
        else:
            failed.append("薪资不达标")
        if _edu(cand["education"]) >= _edu(target["education"]):
            passed.append("学历达标")
        else:
            failed.append("学历不达标")
        if _ge_or_none(cand["experience_years"], target["experience_years"]):
            passed.append("经验达标")
        else:
            failed.append("经验不足")

    return (len(failed) == 0, passed, failed)
