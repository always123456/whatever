"""需求理解 Agent（企业/求职共用）：原文 → RequirementCard 抽取 + 校验 + 规则兜底。

- LLM 路径：chat_json 结构化输出（temperature=0），Pydantic 校验，输出归一化。
- 降级路径：无 key / 调用失败 / 校验失败 → 返回仅含 raw_text 的空卡，靠表单兜底。
- 特质维度宽松：LLM 输出中文名也兼容（unknown_trait_dimensions 转 warnings）。
"""
from ..matching.normalize import normalize_industry, normalize_skills
from ..schemas.company import (
    COMPANY_OVERTIMES,
    COMPANY_SIZES,
    COMPANY_SOCIAL_INSURANCES,
    CompanyExtraction,
)
from ..schemas.requirement import (
    JOB_FACT_AXES,
    TALENT_TRAITS,
    CardRole,
    RequirementCard,
)
from .client import LLMUnavailable, chat_json


def _traits_desc() -> str:
    lines = [f"- {tid} {m['name']}（{m['category']}）：{m['def']}" for tid, m in TALENT_TRAITS.items()]
    return "\n".join(lines)


def _field_spec(spec: dict) -> str:
    t = spec["type"]
    if t == "select":
        return f"枚举 {'/'.join(spec['options'])}"
    if t == "int":
        return f"整数 {spec['min']}-{spec['max']}"
    return "自由文本"


def _axes_desc() -> str:
    lines = []
    for aid, meta in JOB_FACT_AXES.items():
        fields = ", ".join(f"{k}（{name}，{_field_spec(spec)}）" for k, name, spec in meta["fields"])
        lines.append(f"- {aid} {meta['name']}：{fields}")
    return "\n".join(lines)


_ROLE_FIELDS = {
    "seeker": """从求职者的简历或自述中抽取「求职者需求卡」。字段：
- label：姓名
- hard.location：期望地点（省市）
- hard.remote：接受远程（bool）
- hard.salary_min / hard.salary_max：期望月薪上下限（千元，float）
- hard.education：本人学历（不限/大专/本科/硕士/博士）
- hard.experience_years：本人经验年数（int）
- hard.job_status：求职状态（随时到岗/本月到岗/观望了解）
- soft.skills：自身技能（字符串数组）
- soft.industries：意向行业（字符串数组）
- soft.intended_titles：意向职位（最多 5 个）
- soft.target_job_types：求职意向岗位类型（社招/应届校招/实习生/兼职，可多选）
- soft.traits：人才特质自评（数组，见下方特质定义；dimension 用 id 或中文名，value 弱/中/强，importance 默认 1.0）
- facts.is_student：学生与否（bool 或 null）
- facts.certificates：证书（字符串数组）
- facts.work_experiences：工作/实习经历（字符串数组）
- facts.projects：项目/竞赛经历（字符串数组）
- facts.campus_roles：在校经历（字符串数组）
- facts.self_assessment：自评
- facts.ideal_company_traits：理想公司特质（见下方 6 轴结构，抽不到填 null）
抽不到的字段填 null 或空数组，不要编造。""",
    "enterprise": """从岗位 JD 中抽取「企业需求卡」。字段：
- label：职位名称
- hard.location：工作地点（省市）
- hard.remote：可远程（bool）
- hard.salary_min / hard.salary_max：月薪上下限（千元，float）
- hard.education：最低学历（不限/大专/本科/硕士/博士）
- hard.experience_years：最低经验年数（int）
- hard.must_skills：必备技能（缺一淘汰，字符串数组）
- hard.job_types：岗位类型（社招/应届校招/实习生/兼职，可多选）
- soft.skills：岗位技能（字符串数组）
- soft.industries：行业归属（字符串数组）
- soft.traits：理想人才特质（数组，见下方特质定义；dimension 用 id 或中文名，value 期望最低档 弱/中/强，importance 默认 1.0、重点 2.0）
- facts.company_name / facts.company_abbr / facts.company_size / facts.industry / facts.overtime / facts.social_insurance：公司信息
- facts.company_traits：公司特质（见下方 6 轴结构，抽不到填 null）
抽不到的字段填 null 或空数组，不要编造。""",
}

_OUTPUT_FORMAT = """仅输出一个 JSON 对象，不要任何解释，结构：
{"label": "...", "hard": {...}, "soft": {...}, "facts": {...}}"""


def _prompt(role: str, raw_text: str) -> list[dict]:
    guide = _ROLE_FIELDS[role]
    user_msg = (
        f"{guide}\n\n"
        f"人才特质 9 项（3 大类）：\n{_traits_desc()}\n\n"
        f"岗位事实评估 6 轴（公司特质用，key:value 结构，如 {{\"P\": {{\"busy_months\": 3}}}}）：\n{_axes_desc()}\n\n"
        f"{_OUTPUT_FORMAT}\n\n"
        f"原文：\n{raw_text}"
    )
    return [
        {"role": "system", "content": "你是招聘领域的结构化信息抽取器，只输出 JSON，字段缺失填 null/空，绝不编造。"},
        {"role": "user", "content": user_msg},
    ]


def extract_card(role: CardRole, raw_text: str) -> tuple[RequirementCard, list[str]]:
    """原文 → 需求卡。返回 (card, warnings)。无 key / 失败 → 空卡兜底。"""
    if role not in _ROLE_FIELDS:
        role = "seeker"

    try:
        data = chat_json(_prompt(role, raw_text), temperature=0.0)
    except LLMUnavailable:
        return RequirementCard(role=role, raw_text=raw_text, source="llm"), \
            ["LLM 不可用（无 key 或调用失败），已返回空卡，请用表单补充"]

    try:
        data = {**data, "role": role, "source": "llm", "raw_text": raw_text}
        card = RequirementCard.model_validate(data)
    except Exception as e:  # noqa: BLE001  校验失败走兜底，不拒绝
        return RequirementCard(role=role, raw_text=raw_text, source="llm"), \
            [f"抽取结果校验失败，已返回空卡：{e}"]

    # 与表单转卡路径一致：技能/行业/必备技能归一化
    card.soft.skills = normalize_skills(card.soft.skills)
    card.hard.must_skills = normalize_skills(card.hard.must_skills)
    card.soft.industries = [normalize_industry(i) for i in card.soft.industries if i]

    warnings = card.unknown_trait_dimensions()
    return card, warnings


_COMPANY_ENUM_FIELDS = {
    "size": COMPANY_SIZES,
    "overtime": COMPANY_OVERTIMES,
    "social_insurance": COMPANY_SOCIAL_INSURANCES,
}


def extract_company_profile(raw_text: str) -> tuple[CompanyExtraction, list[str]]:
    """公司 PDF 原文 → CompanyExtraction（公司基本信息抽取）。

    与 extract_card 同风格：LLM 结构化输出 + Pydantic 校验；无 key / 失败 → 空结果兜底，
    枚举字段不在枚举内给出 warning（保留原值，交给用户在表单确认）。
    """
    user_msg = (
        "从公司资料原文（公司简介 / 营业执照 / 工商信息等）中抽取公司基本信息，仅输出一个 JSON 对象，不要任何解释：\n"
        "{\n"
        '  "name": "公司全称",\n'
        '  "abbr": "公司简称",\n'
        f'  "size": "公司规模枚举：{'/'.join(COMPANY_SIZES)}",\n'
        '  "industry": "所属行业",\n'
        f'  "overtime": "加班节奏枚举：{'/'.join(COMPANY_OVERTIMES)}",\n'
        f'  "social_insurance": "社保公积金枚举：{'/'.join(COMPANY_SOCIAL_INSURANCES)}",\n'
        '  "company_traits": "公司特质（下方 6 轴 key:value 结构，如 {\\"P\\": {\\"busy_months\\": 3}}，抽不到填 {}）",\n'
        '  "description": "公司简介/主营业务一句话概括"\n'
        "}\n"
        "抽不到的字段填空字符串或 {}，不要编造。\n\n"
        f"岗位事实评估 6 轴：\n{_axes_desc()}\n\n"
        f"原文：\n{raw_text}"
    )
    messages = [
        {"role": "system", "content": "你是企业信息的结构化抽取器，只输出 JSON，字段缺失填空，绝不编造。"},
        {"role": "user", "content": user_msg},
    ]

    try:
        data = chat_json(messages, temperature=0.0)
    except LLMUnavailable:
        return CompanyExtraction(), ["LLM 不可用（无 key 或调用失败），已返回空结果，请用表单补充"]

    try:
        ext = CompanyExtraction.model_validate(data)
    except Exception as e:  # noqa: BLE001
        return CompanyExtraction(), [f"抽取结果校验失败，已返回空结果：{e}"]

    warnings: list[str] = []
    for field, options in _COMPANY_ENUM_FIELDS.items():
        v = getattr(ext, field)
        if v and v not in options:
            warnings.append(f"{field}「{v}」不在枚举 {'/'.join(options)} 中，请在表单确认")
    return ext, warnings
