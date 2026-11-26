"""公司 PDF 信息抽取：降级路径 + 合并规则测试。"""
import pytest

from app.llm import client as llm_client
from app.llm.extract import extract_company_profile
from app.models.db_models import Company
from app.schemas.company import CompanyExtraction


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(llm_client, "api_key", lambda: "")


def test_extract_company_profile_llm_unavailable_returns_empty():
    ext, warnings = extract_company_profile("某某科技有限公司，主营软件")
    assert ext.name == ""
    assert ext.company_traits == {}
    assert warnings, "降级路径应带提示"


def test_merge_company_extraction_overwrites_nonempty_keeps_empty():
    company = Company(
        owner_id=1,
        name="旧公司名",
        abbr="旧简称",
        size="50-99人",
        industry="旧行业",
        overtime="",
        social_insurance="",
        company_traits={"P": {"busy_months": 3}},
    )
    ext = CompanyExtraction(
        name="新公司名",
        abbr="",
        size="",
        industry="互联网",
        overtime="偶尔加班",
        social_insurance="全额缴纳",
        company_traits={"P": {"busy_week_hours": 45}, "S": {"decision_days": 2}},
    )
    from app.api.companies import merge_company_extraction

    merge_company_extraction(company, ext)
    assert company.name == "新公司名"
    assert company.abbr == "旧简称"  # 空保留原值
    assert company.size == "50-99人"  # 空保留原值
    assert company.industry == "互联网"
    assert company.overtime == "偶尔加班"
    assert company.social_insurance == "全额缴纳"
    # 特质逐轴合并：同轴字段级合并，不同轴新增
    assert company.company_traits == {
        "P": {"busy_months": 3, "busy_week_hours": 45},
        "S": {"decision_days": 2},
    }


def test_merge_company_extraction_ignores_invalid_traits():
    company = Company(owner_id=1, name="旧名", company_traits={})
    ext = CompanyExtraction(
        name="新名",
        company_traits={"P": "not-a-dict", "S": {"decision_days": 2}},
    )
    from app.api.companies import merge_company_extraction

    merge_company_extraction(company, ext)
    assert company.company_traits == {"S": {"decision_days": 2}}
