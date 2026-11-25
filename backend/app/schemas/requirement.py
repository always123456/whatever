"""需求卡 RequirementCard：三个 Agent 之间的统一中间表示（契约）。

- 企业端 / 求职端需求理解 Agent 输出同一张卡（按 role 区分），匹配 Agent 只吃卡、吐分。
- 字段来源：实现思路(1).html《信息采集细则》的求职者清单 / 招聘者清单，
  以及 AGENT_DESIGN.md 的硬条件/软偏好两分法。
- 硬条件 HardConstraint：不满足直接淘汰；None/空 = 无要求，不过滤。
- 软偏好 SoftPreference：只影响排序，importance 为维度权重。
- 补充信息 facts：清单里其余字段（经历、自评、加班节奏等），不进硬过滤、
  暂不打分，但 Agent 要抽取出来，供展示、推荐语与后续扩展用。

特质枚举来源：requirement.md（同目录）——
- 人才特质 4 大类 12 项（C-A-S-M）→ TALENT_TRAITS，双方卡 soft.traits 使用；
- 岗位事实评估维度 6 轴（P-S-F-C-V-W）→ JOB_FACT_AXES，用于
  求职卡 facts.ideal_company_traits / 企业卡 facts.company_traits。
  高分/低分行为锚点仍在 requirement.md，写抽取提示词时引用。

待办见 docs/TODO-requirement-card.md。
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

CardRole = Literal["seeker", "enterprise"]
CardSource = Literal["form", "llm", "rule", "manual"]

# 学历枚举（与前端 Jobs.vue / Resumes.vue 下拉一致，与 matching/constraints.py EDU_LEVELS 同步）
EDUCATION_LEVELS = ("不限", "大专", "本科", "硕士", "博士")
# 企业端岗位类型（信息采集细则；前端尚无下拉，待表单扩展时对齐）
JOB_TYPES = ("社招", "应届校招", "实习生", "兼职")
# 求职者求职状态（信息采集细则；前端尚无下拉，待表单扩展时对齐）
JOB_STATUSES = ("随时到岗", "本月到岗", "观望了解")
# 企业规模 / 加班节奏 / 社保公积金（前端 Jobs.vue 公司档案下拉一致）
COMPANY_SIZES = ("1-49人", "50-99人", "100-499人", "500-999人", "1000人以上")
OVERTIMES = ("不加班", "偶尔加班", "经常加班", "大小周", "996")
SOCIAL_INSURANCES = ("全额缴纳", "按最低基数缴纳", "无公积金", "面议")
# 人才特质水平档位（决策1）：企业卡 value=期望最低档，求职卡 value=自身水平档
TRAIT_LEVELS = ("弱", "中", "强")
TRAIT_LEVEL_SCORES = {"弱": 0.0, "中": 0.5, "强": 1.0}

# 档位归一化（宽松）：LLM 抽取可能输出自由描述，映射不进枚举的落中性 0.5
_TRAIT_LEVEL_ALIASES = {
    0.0: ("弱", "欠缺", "不足", "较差", "很少"),
    0.5: ("中", "一般", "尚可", "良好", "中等"),
    1.0: ("强", "优秀", "突出", "很强", "出色"),
}


def normalize_trait_level(value: str) -> float:
    """把特质 value 归一化到 0.0/0.5/1.0 档位分，未知值落中性 0.5。"""
    v = (value or "").strip()
    if not v:
        return 0.5
    if v in TRAIT_LEVEL_SCORES:
        return TRAIT_LEVEL_SCORES[v]
    for score, aliases in _TRAIT_LEVEL_ALIASES.items():
        if v in aliases:
            return score
    return 0.5

# 人才特质（附图1 / requirement.md）：4 大类 12 项
# 采集来源：认知/动机靠情境题，行动靠经历，社交靠自由文本
TALENT_TRAITS: Dict[str, Dict[str, str]] = {
    "C1": {"name": "结构化", "category": "认知", "def": "把模糊目标拆成可执行步骤"},
    "C2": {"name": "判断力", "category": "认知", "def": "信息不全时敢做取舍并说依据"},
    "C3": {"name": "学习迁移", "category": "认知", "def": "把旧场景的方法用到新问题"},
    "A1": {"name": "主动性", "category": "行动", "def": "未被要求就推进"},
    "A2": {"name": "交付", "category": "行动", "def": "拆解、排期、按时交付"},
    "A3": {"name": "韧性", "category": "行动", "def": "受阻后换路径继续"},
    "S1": {"name": "表达", "category": "社交", "def": "把复杂说简单"},
    "S2": {"name": "澄清", "category": "社交", "def": "先确认约束再动手"},
    "S3": {"name": "冲突", "category": "社交", "def": "直面分歧不回避"},
    "M1": {"name": "成就驱动", "category": "动机", "def": "有内部标准，不只对齐 KPI"},
    "M2": {"name": "稳定性", "category": "动机", "def": "动机与岗位条件一致"},
    "M3": {"name": "价值取向", "category": "动机", "def": "结果/过程、个人/团队、稳定/变化偏好"},
}

# 岗位事实评估维度（附图2 / requirement.md，P-S-F-C-V-W）：
# 求职卡 facts.ideal_company_traits 与企业卡 facts.company_traits 共用此结构。
# 每个字段 (key, 中文名, 采集定义)：type=select(带 options)/int(带 min/max)/text，
# 前端据此渲染控件；company_traits.py 只解包前两元，采集定义不影响打分。
JOB_FACT_AXES: Dict[str, Dict[str, Any]] = {
    "P": {"name": "节奏", "fields": [
        ("busy_months", "忙季每年几个月", {"type": "int", "min": 0, "max": 12}),
        ("busy_week_hours", "忙季周工时", {"type": "int", "min": 0, "max": 168}),
        ("response_hours", "日常消息响应期望", {"type": "int", "min": 0, "max": 168}),
    ]},
    "S": {"name": "结构", "fields": [
        ("decision_layers", "到决策者几层", {"type": "int", "min": 1, "max": 5}),
        ("decision_days", "需求平均决策天数", {"type": "int", "min": 0, "max": 365}),
        ("process_docs", "流程文档化", {"type": "select", "options": ["无", "部分", "完整"]}),
    ]},
    "F": {"name": "反馈", "fields": [
        ("one_on_one", "1v1 频率", {"type": "select", "options": ["周", "月", "季", "无"]}),
        ("feedback_from", "谁给反馈", {"type": "select", "options": ["直属", "上级", "无"]}),
        ("promotion_cycle", "晋升评审周期", {"type": "text"}),
    ]},
    "C": {"name": "协作", "fields": [
        ("division", "分工方式", {"type": "select", "options": ["按模块", "按人", "混合"]}),
        ("channel", "主沟通渠道", {"type": "select", "options": ["口头", "文档", "两者"]}),
        ("dispute_owner", "分歧谁定", {"type": "select", "options": ["直属", "上级", "集体"]}),
    ]},
    "V": {"name": "价值", "fields": [
        ("perf_metric", "绩效看结果还是过程", {"type": "select", "options": ["结果", "过程"]}),
        ("reward", "奖励团队还是个人", {"type": "select", "options": ["团队", "个人"]}),
        ("stability", "偏好稳定还是变化", {"type": "select", "options": ["稳定", "变化"]}),
    ]},
    "W": {"name": "形态", "fields": [
        ("office_days", "每周到岗天数", {"type": "int", "min": 0, "max": 7}),
        ("travel_days", "每月出差天数", {"type": "int", "min": 0, "max": 31}),
        ("cross_tz", "跨时区协作", {"type": "select", "options": ["有", "无"]}),
    ]},
}

# facts 的键清单（信息采集细则中「硬/软」之外的字段）
FACTS_KEYS: Dict[CardRole, List[str]] = {
    "seeker": [
        "is_student",           # 学生与否
        "certificates",         # 语言/职业证书（四六级等）
        "work_experiences",     # 工作/实习经历
        "projects",             # 竞赛/项目经历
        "campus_roles",         # 在校经历（学生会职务等）
        "self_assessment",      # 自评能力
        "ideal_company_traits", # 理想公司特质（JOB_FACT_AXES 结构）
    ],
    "enterprise": [
        "company_name",         # 公司名
        "company_abbr",         # 公司简称
        "company_size",         # 人员规模
        "industry",             # 行业归属
        "overtime",             # 加班节奏
        "social_insurance",     # 社保、公积金
        "company_traits",       # 公司特质（JOB_FACT_AXES 结构）
    ],
}


class HardConstraint(BaseModel):
    """硬条件：不满足直接淘汰；None/空 = 无要求。

    教育/经验字段是双语义（与现有 matching_service 的 profile dict 一致）：
    - 企业卡：education=最低学历要求，experience_years=最低经验年数；
    - 求职卡：education=本人学历，experience_years=本人经验年数；
    匹配引擎按 direction 比较两侧取值。
    """
    location: Optional[str] = None            # 工作地点（企业）/ 期望地点（求职者），省市
    remote: bool = False                      # 可远程（企业）/ 接受远程（求职者）
    salary_min: Optional[float] = None        # 月薪下限（千元）
    salary_max: Optional[float] = None        # 月薪上限（千元）
    education: Optional[str] = None           # 不限/大专/本科/硕士/博士
    experience_years: Optional[int] = None    # 经验年数（企业=最低要求，求职=自身水平）
    must_skills: List[str] = Field(default_factory=list)  # 必备技能，缺一淘汰（企业卡）
    job_types: List[str] = Field(default_factory=list)    # 企业卡：社招/应届校招/实习生/兼职
    job_status: Optional[str] = None          # 求职卡：随时到岗/本月到岗/观望了解


class TraitItem(BaseModel):
    """一条人才特质记录：dimension 取 TALENT_TRAITS 的 id（C1..M3，名字也兼容）。

    - 求职卡：人才特质报告（测评/自评的自身水平）
    - 企业卡：理想人才特质（期望对方达到的水平）
    """
    dimension: str
    value: str
    importance: float = 1.0      # 企业卡可对每条特质加权；求职卡通常不用


class SoftPreference(BaseModel):
    """软偏好：只影响排序，不淘汰；空 = 未填，对应维度给中性分。

    importance 为维度权重（缺省由匹配引擎按默认权重表解释）：
    skill / industry / title / trait / salary / text
    """
    skills: List[str] = Field(default_factory=list)        # 技能集合（重合度打分；求职卡为自身技能）
    industries: List[str] = Field(default_factory=list)    # 行业（企业=归属，求职=意向）
    intended_titles: List[str] = Field(default_factory=list)  # 意向职位（求职卡，最多5个）
    target_job_types: List[str] = Field(default_factory=list)  # 求职意向岗位类型（求职卡，软打分）
    traits: List[TraitItem] = Field(default_factory=list)  # 人才特质（TALENT_TRAITS）
    importance: Dict[str, float] = Field(default_factory=dict)  # 维度权重覆盖


class RequirementCard(BaseModel):
    """统一需求卡：三个 Agent 的契约。求职卡=seeker 画像，企业卡=岗位需求。"""
    id: Optional[int] = None                # 关联数据库主键（匹配服务回填，便于结果返回），非内容语义
    role: CardRole
    label: str = ""                        # 职位名称（企业卡）/ 姓名（求职卡）
    hard: HardConstraint = Field(default_factory=HardConstraint)
    soft: SoftPreference = Field(default_factory=SoftPreference)
    facts: Dict[str, Any] = Field(default_factory=dict)  # 键见 FACTS_KEYS，其余字段落这里
    source: CardSource = "form"            # 卡的来源：表单 / LLM 抽取 / 规则兜底 / 人工校对
    raw_text: Optional[str] = None         # 抽取来源原文（落库可回溯）

    def unknown_trait_dimensions(self) -> List[str]:
        """返回不在 TALENT_TRAITS 中的特质维度（按 id 或名字比对）。

        LLM 抽取层用它生成 warnings（宽松校验，不拒绝，便于原文与枚举对齐）。
        """
        ids = set(TALENT_TRAITS)
        names = {v["name"] for v in TALENT_TRAITS.values()}
        return [
            t.dimension for t in self.soft.traits
            if t.dimension not in ids and t.dimension not in names
        ]


class RequirementParseRequest(BaseModel):
    """POST /api/requirement/parse 的入参：原文 -> 需求卡预览。"""
    role: CardRole
    raw_text: str = Field(min_length=1, description="JD 原文 / 简历或自述原文")


class RequirementParseResponse(BaseModel):
    """需求卡预览：供用户校对，warnings 提示缺失/不确定字段。"""
    card: RequirementCard
    warnings: List[str] = Field(default_factory=list)


class RequirementApplyRequest(BaseModel):
    """POST /api/requirement/apply 的入参：把预览卡合并写回目标实体（简历/职位）的需求卡。"""
    role: CardRole
    target_id: Optional[int] = None  # resume_id 或 job_id；缺省用当前用户最新一份
    card: RequirementCard  # 抽取预览卡（前端原样传回）
