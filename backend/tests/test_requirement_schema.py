"""需求卡 schema 契约测试：默认值、角色枚举、软硬字段落位。"""
import pytest

from app.schemas.requirement import (
    FACTS_KEYS,
    JOB_FACT_AXES,
    TALENT_TRAITS,
    HardConstraint,
    RequirementCard,
    RequirementParseRequest,
    SoftPreference,
    TraitItem,
)


def test_empty_card_defaults():
    card = RequirementCard(role="seeker")
    assert card.hard.must_skills == []
    assert card.hard.salary_min is None
    assert card.soft.importance == {}
    assert card.source == "form"


def test_role_rejects_unknown_value():
    with pytest.raises(Exception):
        RequirementCard(role="admin")


def test_enterprise_card_fields():
    card = RequirementCard(
        role="enterprise",
        label="后端工程师",
        hard=HardConstraint(
            location="北京", salary_min=20, salary_max=35,
            education="本科", experience_years=2,
            must_skills=["Python"], job_types=["社招"],
        ),
        soft=SoftPreference(
            skills=["FastAPI"],
            importance={"skill": 0.8},
            traits=[TraitItem(dimension="C1", value="强")],
        ),
        facts={"company_name": "示例公司", "company_size": "50-100人"},
    )
    assert card.hard.job_types == ["社招"]
    assert card.facts["company_name"] == "示例公司"


def test_seeker_card_expected_salary_and_titles():
    card = RequirementCard(
        role="seeker",
        label="张三",
        hard=HardConstraint(location="上海", salary_min=15, salary_max=25,
                            education="本科", experience_years=3, job_status="随时到岗"),
        soft=SoftPreference(skills=["Python", "Docker"], intended_titles=["后端开发", "全栈开发"]),
        facts={"is_student": False},
    )
    assert card.hard.job_status == "随时到岗"
    assert len(card.soft.intended_titles) <= 5
    assert "is_student" in FACTS_KEYS["seeker"]


def test_parse_request_requires_text():
    with pytest.raises(Exception):
        RequirementParseRequest(role="enterprise", raw_text="")


def test_talent_traits_and_job_fact_axes_complete():
    assert len(TALENT_TRAITS) == 12  # C1-C3 / A1-A3 / S1-S3 / M1-M3
    assert len(JOB_FACT_AXES) == 6   # P-S-F-C-V-W
    for axis in ("P", "S", "F", "C", "V", "W"):
        assert len(JOB_FACT_AXES[axis]["fields"]) == 3


def test_unknown_trait_dimensions_reports_only_unknowns():
    card = RequirementCard(
        role="seeker",
        soft=SoftPreference(traits=[
            TraitItem(dimension="C1", value="强"),
            TraitItem(dimension="结构化", value="中"),  # 名字也兼容
            TraitItem(dimension="创造力", value="高"),
        ]),
    )
    assert card.unknown_trait_dimensions() == ["创造力"]
