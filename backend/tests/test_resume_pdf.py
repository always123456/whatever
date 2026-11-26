"""PDF 简历解析与简历列回填测试。"""
import pytest

from app.llm.pdf import PdfParseError, parse_pdf_text
from app.models.db_models import Resume
from app.schemas.requirement import (
    HardConstraint,
    RequirementCard,
    SoftPreference,
    TraitItem,
)
from app.services.matching_service import _sync_resume_columns


def _text_pdf(text: str) -> bytes:
    """手搓一个带文字层的最小 PDF（含正确 xref，供 pypdf 抽取）。仅 ASCII 文本。"""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def test_parse_pdf_extracts_text():
    text = parse_pdf_text(_text_pdf("Senior Backend Engineer Python 5 years"))
    assert "Python" in text
    assert "Backend" in text


def test_parse_pdf_rejects_empty_bytes():
    with pytest.raises(PdfParseError):
        parse_pdf_text(b"")


def test_parse_pdf_rejects_non_pdf():
    with pytest.raises(PdfParseError):
        parse_pdf_text(b"this is not a pdf at all")


def test_parse_pdf_rejects_no_text_layer():
    # 空白内容流 → 抽取为空 → 报「暂不支持」（模拟扫描件/图片型 PDF）
    with pytest.raises(PdfParseError):
        parse_pdf_text(_text_pdf(""))


def test_sync_resume_columns_fills_from_card():
    resume = Resume(owner_id=1, name="旧名", location="")
    card = RequirementCard(
        role="seeker",
        label="张三",
        hard=HardConstraint(location="上海", salary_min=15, salary_max=25,
                            education="本科", experience_years=3, job_status="随时到岗"),
        soft=SoftPreference(skills=["Python", "Docker"], industries=["互联网"],
                            intended_titles=["后端开发"], target_job_types=["社招"],
                            traits=[TraitItem(dimension="C1", value="强")]),
        facts={"self_assessment": "靠谱"},
    )
    _sync_resume_columns(resume, card)
    assert resume.name == "张三"
    assert resume.location == "上海"
    assert resume.expected_salary_min == 15
    assert resume.expected_salary_max == 25
    assert resume.education == "本科"
    assert resume.experience_years == 3
    assert resume.willing_remote is False
    assert resume.skills == ["Python", "Docker"]
    assert resume.industry == "互联网"
    assert resume.intended_titles == ["后端开发"]
    assert resume.target_job_types == ["社招"]
    assert resume.self_traits == [{"dimension": "C1", "value": "强", "importance": 1.0}]
    assert resume.summary == "靠谱"
