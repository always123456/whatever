"""匹配引擎纯函数测试：硬过滤 + 打分排序（输入为 RequirementCard）。"""
import pytest

from app.matching.constraints import check_hard_constraints
from app.matching.engine import match
from app.matching.scoring import compute_score
from app.schemas.requirement import (
    HardConstraint,
    RequirementCard,
    SoftPreference,
    TraitItem,
)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """测试环境禁用真实 LLM 调用（无 key → 走确定性降级）。"""
    from app.llm import client
    monkeypatch.setattr(client, "api_key", lambda: "")


def _job(**kw):
    args = dict(
        id=1,
        role="enterprise",
        label="后端工程师",
        hard=HardConstraint(
            location="北京", salary_min=20, salary_max=35,
            education="本科", experience_years=2,
        ),
        soft=SoftPreference(skills=["Python", "FastAPI"], industries=["互联网"]),
        raw_text="后端工程师 互联网 Python FastAPI",
    )
    args.update(kw)
    return RequirementCard(**args)


def _resume(**kw):
    args = dict(
        id=1,
        role="seeker",
        label="张三",
        hard=HardConstraint(
            location="北京", salary_min=20, salary_max=30,
            education="本科", experience_years=3,
        ),
        soft=SoftPreference(skills=["Python", "FastAPI", "Docker"], industries=["互联网"]),
        raw_text="张三 互联网 Python FastAPI Docker",
    )
    args.update(kw)
    return RequirementCard(**args)


def test_location_hard_filter():
    r = _resume()
    j = _job()
    j.hard.location = "上海"
    j.hard.remote = False
    ok, _passed, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "地点不符" in failed


def test_remote_allows_location_mismatch():
    r = _resume()
    j = _job()
    j.hard.location = "上海"
    j.hard.remote = True
    ok, _, _ = check_hard_constraints(r, j, "seeker_to_jobs")
    assert ok


def test_education_hard_filter():
    r = _resume()
    j = _job()
    r.hard.education = "大专"
    j.hard.education = "本科"
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "学历不达标" in failed


def test_salary_hard_filter():
    r = _resume()
    j = _job()
    r.hard.salary_min = 30  # 期望至少 30k
    j.hard.salary_max = 25  # 岗位最多 25k
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "薪资不达标" in failed


def test_experience_hard_filter():
    r = _resume()
    j = _job()
    r.hard.experience_years = 1
    j.hard.experience_years = 3
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "经验不足" in failed


def test_must_skills_hard_filter():
    r = _resume()  # skills=["Python","FastAPI","Docker"]
    j = _job()
    j.hard.must_skills = ["Kubernetes"]  # 求职者没有
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "必备技能缺失" in failed


def test_must_skills_passes_when_covered():
    r = _resume()
    j = _job()
    j.hard.must_skills = ["Python", "FastAPI"]
    ok, _, _ = check_hard_constraints(r, j, "seeker_to_jobs")
    assert ok


def test_enterprise_direction_symmetric():
    job = _job()
    resume = _resume()
    resume.hard.education = "硕士"
    resume.hard.experience_years = 3
    ok, _, _ = check_hard_constraints(job, resume, "enterprise_to_seekers")
    assert ok


def test_ranking_prefers_higher_skill_overlap():
    r = _resume(skills=SoftPreference(skills=["Python", "FastAPI", "Docker"], industries=["互联网"]))
    j1 = _job(id=1)
    j2 = _job(id=2)
    j2.soft.skills = ["Vue", "CSS"]
    results = match(r, [j1, j2], "seeker_to_jobs", top_n=5)
    assert results[0][0].id == 1  # 技能重合更高的排前


def test_scores_within_unit_range():
    r = _resume()
    jobs = [_job(id=i) for i in range(1, 4)]
    results = match(r, jobs, "seeker_to_jobs", top_n=10)
    assert results
    for _, score, _, _ in results:
        assert 0.0 <= score <= 1.0


def test_compute_score_returns_reasons():
    r = _resume()
    j = _job()
    score, reasons = compute_score(r, j, "seeker_to_jobs")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
    assert reasons
    # seeker_to_jobs 含公司特质维度
    assert any("公司特质" in s for s in reasons)


def test_trait_match_levels_and_weights():
    from app.matching.scoring import _trait_match
    ent_strong = [TraitItem(dimension="C1", value="强", importance=2.0)]
    assert _trait_match(ent_strong, [TraitItem(dimension="C1", value="强")]) == 1.0
    assert _trait_match(ent_strong, [TraitItem(dimension="C1", value="中")]) == 0.5
    assert _trait_match(ent_strong, [TraitItem(dimension="C1", value="弱")]) == 0.0
    assert _trait_match(ent_strong, []) == 0.0  # 求职者缺记录
    assert _trait_match([], [TraitItem(dimension="C1", value="强")]) == 0.5  # 企业没要求


def test_trait_match_chinese_dimension_name_compatible():
    from app.matching.scoring import _trait_match
    ent = [TraitItem(dimension="结构化", value="强")]  # 中文名
    seeker = [TraitItem(dimension="C1", value="强")]  # id
    assert _trait_match(ent, seeker) == 1.0


def test_job_types_match():
    from app.matching.scoring import _job_types_match
    assert _job_types_match(["社招"], ["社招"], None) == 1.0
    assert _job_types_match(["社招"], ["实习生"], None) == 0.0
    assert _job_types_match([], ["社招"], None) == 0.5  # 企业没填岗位类型
    assert _job_types_match(["社招"], [], False) == 1.0  # 求职者没填，非学生兜底社招
    assert _job_types_match(["应届校招"], [], True) == 1.0  # 学生兜底校招
    assert _job_types_match(["社招"], [], None) == 0.5  # 双方都没信息


def test_company_traits_neutral_when_empty():
    from app.llm.company_traits import score_company_traits
    score, reason = score_company_traits({}, {})
    assert score == 0.5
    assert reason == "公司特质未采集"


def test_company_traits_deterministic_fallback():
    from app.llm.company_traits import score_company_traits
    # P 轴 3 字段全相等=1，其余 5 轴缺失=0.5，均值 = (1 + 0.5*5) / 6
    ideal = {"P": {"busy_months": 2, "busy_week_hours": 40, "response_hours": 8}}
    company = {"P": {"busy_months": 2, "busy_week_hours": 40, "response_hours": 8}}
    score, reason = score_company_traits(ideal, company)
    assert score == round((1 + 0.5 * 5) / 6, 4)
    assert "降级" in reason or "确定性" in reason
