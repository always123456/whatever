"""匹配引擎纯函数测试：硬过滤 + 打分排序。"""
from app.matching.constraints import check_hard_constraints
from app.matching.engine import match
from app.matching.scoring import compute_score


def _job(**kw):
    base = dict(
        id=1, kind="job", label="后端工程师", company="X",
        location="北京", salary_min=20, salary_max=35,
        education="本科", experience_years=2, industry="互联网",
        skills=["Python", "FastAPI"], remote=False,
        text="后端工程师 互联网 Python FastAPI",
    )
    base.update(kw)
    return base


def _resume(**kw):
    base = dict(
        id=1, kind="resume", label="张三",
        location="北京", salary_min=20, salary_max=30,
        education="本科", experience_years=3, industry="互联网",
        skills=["Python", "FastAPI", "Docker"], remote=False,
        text="张三 互联网 Python FastAPI Docker",
    )
    base.update(kw)
    return base


def test_location_hard_filter():
    r = _resume(location="北京")
    j = _job(location="上海", remote=False)
    ok, _passed, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "地点不符" in failed


def test_remote_allows_location_mismatch():
    r = _resume(location="北京")
    j = _job(location="上海", remote=True)
    ok, _, _ = check_hard_constraints(r, j, "seeker_to_jobs")
    assert ok


def test_education_hard_filter():
    r = _resume(education="大专")
    j = _job(education="本科")
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "学历不达标" in failed


def test_salary_hard_filter():
    r = _resume(salary_min=30)  # 期望至少 30k
    j = _job(salary_max=25)     # 岗位最多 25k
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "薪资不达标" in failed


def test_experience_hard_filter():
    r = _resume(experience_years=1)
    j = _job(experience_years=3)
    ok, _, failed = check_hard_constraints(r, j, "seeker_to_jobs")
    assert not ok
    assert "经验不足" in failed


def test_enterprise_direction_symmetric():
    job = _job(education="本科", experience_years=2, salary_max=35)
    resume = _resume(education="硕士", experience_years=3, salary_min=20)
    ok, _, _ = check_hard_constraints(job, resume, "enterprise_to_seekers")
    assert ok


def test_ranking_prefers_higher_skill_overlap():
    r = _resume(skills=["Python", "FastAPI", "Docker"])
    j1 = _job(id=1, skills=["Python", "FastAPI"], label="后端A")
    j2 = _job(id=2, skills=["Vue", "CSS"], label="前端B")
    results = match(r, [j1, j2], "seeker_to_jobs", top_n=5)
    assert results[0][0]["id"] == 1  # 技能重合更高的排前


def test_scores_within_unit_range():
    r = _resume()
    jobs = [
        _job(id=1, skills=["Python"]),
        _job(id=2, skills=["Java"]),
        _job(id=3, skills=["Go"]),
    ]
    results = match(r, jobs, "seeker_to_jobs", top_n=10)
    assert results
    for _, score, _, _ in results:
        assert 0.0 <= score <= 1.0


def test_compute_score_returns_reasons():
    r = _resume()
    j = _job()
    score, reasons = compute_score(r, j, "seeker_to_jobs")
    assert isinstance(score, float)
    assert len(reasons) == 5
