# 需求卡字段设计与匹配打分方式（定稿）

> 本文档是需求卡（RequirementCard）字段契约与匹配算法的定稿说明，与代码同步。
> 代码落点：`backend/app/schemas/requirement.py`（字段/枚举）、
> `backend/app/matching/`（引擎）、`backend/app/services/matching_service.py`（ORM→卡转换）。

---

## 1. 需求卡 RequirementCard

需求卡是三个 Agent 之间的统一中间表示：企业端/求职端需求理解 Agent 输出同一张卡
（`role` 区分），匹配 Agent 只吃卡、吐分。字段分三类：

| 类型 | 含义 | 作用 |
| --- | --- | --- |
| `hard` HardConstraint | 硬条件 | 不满足直接淘汰 |
| `soft` SoftPreference | 软偏好 | 只影响排序，带 importance 权重 |
| `facts` dict | 补充信息 | 不进硬过滤、暂不打分，供展示/推荐语/后续扩展 |

卡顶层字段：`id`（数据库主键，匹配服务回填）、`role`（seeker|enterprise）、`label`
（职位名/姓名）、`hard`、`soft`、`facts`、`source`（form|llm|rule|manual）、`raw_text`
（抽取来源原文）。

### 1.1 硬条件 HardConstraint

| 字段 | 类型 | 企业卡语义 | 求职卡语义 |
| --- | --- | --- | --- |
| location | str\|None | 工作地点（省市） | 期望地点（省市） |
| remote | bool | 可远程 | 接受远程 |
| salary_min / salary_max | float\|None | 月薪上下限（千元） | 期望月薪上下限（千元） |
| education | str\|None | 最低学历 | 本人学历 |
| experience_years | int\|None | 最低经验年数 | 本人经验年数 |
| must_skills | list[str] | 必备技能（缺一淘汰） | 无 |
| job_types | list[str] | 岗位类型（社招/应届校招/实习生/兼职） | 无 |
| job_status | str\|None | 无 | 求职状态（随时到岗/本月到岗/观望了解） |

`education` / `experience_years` 是双语义字段：企业卡=最低要求，求职卡=自身水平，
匹配引擎按 direction 比较两侧取值。`None`/空 = 无要求，不过滤。

### 1.2 软偏好 SoftPreference

| 字段 | 说明 |
| --- | --- |
| skills | 技能集合（求职卡=自身技能，企业卡=岗位技能） |
| industries | 行业（企业=归属，求职=意向） |
| intended_titles | 意向职位（求职卡，最多 5 个） |
| target_job_types | 求职意向岗位类型（求职卡，软打分） |
| traits | 人才特质 TraitItem 列表 |
| importance | 维度权重覆盖字典（如 {"skill": 0.8}） |

`TraitItem`：`dimension`（取 TALENT_TRAITS 的 id，中文名也兼容）、`value`（水平档：
弱/中/强）、`importance`（该特质权重，默认 1.0，重点=2.0）。企业卡 traits=理想人才特质
（期望对方达到的档），求职卡 traits=自评水平档。

### 1.3 补充信息 facts（自由字典）

- 求职卡 7 键：`is_student`（学生与否）、`certificates`（证书）、`work_experiences`、
  `projects`、`campus_roles`、`self_assessment`（自评）、`ideal_company_traits`（理想公司特质）
- 企业卡 7 键：`company_name`、`company_abbr`、`company_size`、`industry`、`overtime`、
  `social_insurance`、`company_traits`（公司实际特质）

`ideal_company_traits` / `company_traits` 使用 JOB_FACT_AXES 结构，供公司特质匹配（见 2.8）。

### 1.4 枚举

- 学历 EDUCATION_LEVELS：不限 / 大专 / 本科 / 硕士 / 博士
- 岗位类型 JOB_TYPES：社招 / 应届校招 / 实习生 / 兼职
- 求职状态 JOB_STATUSES：随时到岗 / 本月到岗 / 观望了解
- 特质档位 TRAIT_LEVELS：弱(0.0) / 中(0.5) / 强(1.0)
- 人才特质 TALENT_TRAITS 9 项（3 大类）：
  - C 认知：C1 结构化、C2 判断力、C3 学习迁移
  - A 行动：A1 主动性、A2 交付、A3 韧性
  - S 社交：S1 表达、S2 澄清、S3 冲突
- 岗位事实评估 JOB_FACT_AXES 6 轴（各 3 字段）：
  - P 节奏：忙季每年几个月(0-12)、忙季周工时(h)、日常消息响应期望(小时)
  - S 结构：到决策者几层(1-5)、需求平均决策天数、流程文档化(无/部分/完整)
  - F 反馈：1v1 频率(周/月/季/无)、谁给反馈(直属/上级/无)、晋升评审周期
  - C 协作：分工方式(按模块/按人/混合)、主沟通渠道(口头/文档/两者)、分歧谁定(直属/上级/集体)
  - V 价值：绩效看结果还是过程(结果/过程)、奖励团队还是个人(团队/个人)、偏好稳定还是变化(稳定/变化)
  - W 形态：每周到岗天数(0-7)、每月出差天数(0-31)、跨时区协作(有/无)

### 1.5 数据库 / 表单映射

- Job 表：`title→label`、`must_skills→hard.must_skills`、`job_types→hard.job_types`、
  `ideal_talents→soft.traits`、`description→raw_text`、
  其余薪资/学历/经验/地点/远程/技能直接对应。
- Companies 表（经 `job.company` 关系）：`company_name/company_abbr/company_size/
  industry/overtime/social_insurance/company_traits→facts`。
- Resume 表：`job_status→hard.job_status`、`intended_titles/target_job_types→soft`、
  `self_traits→soft.traits`、`summary→raw_text + facts.self_assessment`、
  其余薪资/学历/经验/地点/远程/技能直接对应。

---

## 2. 匹配打分方式

流水线：硬过滤 → 软打分 → 归一化加权 → 排序 →（可选）LLM 解释。
全部为确定性代码，唯一例外是公司特质 6 轴（语义匹配，由 LLM 打分，带确定性降级）。

### 2.1 硬过滤（constraints.py）

统一抽成 `job`/`seeker` 后按同一条规则比较（不再分方向写两份），任一条不满足即淘汰：

1. 地点：同城，或任一方支持远程
2. 薪资：岗位 `salary_max >=` 求职者 `salary_min`（区间有交集）
3. 学历：求职者学历档 `>=` 岗位最低档（EDU_LEVELS 索引比较）
4. 经验：求职者 `experience_years >=` 岗位最低年数
5. 必备技能：岗位 `must_skills` 全部被求职者技能覆盖（缺一淘汰）

数据不全（None）视为通过，避免误过滤。

### 2.2 软打分（scoring.py）

各维度归一化到 0-1 后加权求和。`soft.importance` 可覆盖维度权重，覆盖后整表重归一化，
总分仍落在 0-1。

| 维度 | 算法 |
| --- | --- |
| skill | 技能集合 Jaccard 重合度 |
| title | 意向职位与岗位名的文本相似度取最大值（求职卡） |
| salary | 岗位薪资覆盖求职者期望区间的比例 |
| industry | 相等=1.0，一方未填=0.5，不同=0.0 |
| experience | 经验富余度（不足=0，持平=0.7，富余≤2 年=0.85，>2 年=1.0） |
| text | 拼接 label+raw_text+skills+industries 的 bigram 余弦相似度 |
| job_types | 岗位类型覆盖率（见 2.4） |
| trait | 特质档位加权比较（见 2.3，仅 enterprise_to_seekers） |
| company | 公司特质 6 轴匹配（见 2.8，仅 seeker_to_jobs） |

分方向权重（先简单分配，后续可调）：

- seeker_to_jobs（求职者找岗位）：skill 0.24 / title 0.14 / salary 0.14 / industry 0.08 /
  experience 0.08 / text 0.14 / job_types 0.03 / company 0.15
- enterprise_to_seekers（企业找人才）：skill 0.25 / trait 0.22 / salary 0.13 / industry 0.09 /
  experience 0.08 / text 0.20 / job_types 0.03

### 2.3 特质档位比较（trait）

- `normalize_trait_level` 把 value 归一到 0/0.5/1.0（含中文名、同义别名，未知值落中性 0.5）。
- 对每个企业要求的特质维度（按 importance 加权）：
  - 求职者缺该维度记录 → 0 分
  - 求职档 >= 期望档 → 1.0；差一档 → 0.5；差两档 → 0.0
- 企业没要求任何特质 → 中性 0.5。
- `dimension` 归一化：中文名（如"结构化"）映射回 id（C1），兼容 LLM 抽取输出。

### 2.4 岗位类型软打分（job_types）

- 企业没填岗位类型 → 中性 0.5
- 覆盖率 = |企业 job_types ∩ 求职 target_job_types| / |企业 job_types|
- 求职者没填 target_job_types 时用 `facts.is_student` 兜底：学生→[应届校招, 实习生]，
  非学生→[社招]；未知→中性 0.5。

### 2.5 求职状态（仅展示 + 企业端筛选，不进打分）

- 求职状态不参与打分。
- 企业端匹配可用 `availability` 参数筛选（随时到岗/本月到岗/观望了解）。
- 企业端结果在同分时按到岗状态做次级排序：随时到岗 > 本月到岗 > 观望了解。
- 匹配结果 payload 透出 `job_status` 供前端展示。

### 2.6 公司特质 6 轴 LLM 打分（company）

- 只在 seeker_to_jobs 方向有意义（求职者理想公司 vs 企业实际）。
- LLM 路径：把双方 JOB_FACT_AXES 键值结构化成 JSON 喂给 DeepSeek，逐轴输出 0-1 分 +
  一句理由，总分 6 轴等权；`temperature=0`，结果进程内缓存（同组合不重复调用）。
- 确定性降级（无 key / 调用失败 / 解析失败）：逐字段比较——相等=1.0、不同=0.0、
  缺失=0.5，取 6 轴均值。
- 任一方无数据 → 中性 0.5（打分不生效，不扣分）。
- 仅输出 JSON，schema 过校验，分数夹到 [0,1]。

### 2.7 方向性小结

| 维度 | seeker_to_jobs | enterprise_to_seekers |
| --- | --- | --- |
| title（意向职位） | ✓ | — |
| trait（人才特质） | — | ✓ |
| company（公司特质） | ✓ | — |
| skill / salary / industry / experience / text / job_types | ✓ | ✓ |
