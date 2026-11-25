# 需求卡数据处理流程：从原始文本到打分字段

> 本文档回答四个问题：求职者哪些字段参与匹配打分；简历设计与需求卡抽取设计各含哪些字段；
> 简历与需求卡的关系；原始文本如何一步步变成打分字段。
> 字段契约与打分算法细节见 [MATCHING_DESIGN.md](./MATCHING_DESIGN.md)，本文侧重数据流与字段来源。
>
> 代码落点：
> - 转卡 / 读卡 / 合并：`backend/app/services/matching_service.py`
> - LLM 抽取：`backend/app/llm/extract.py`、`backend/app/llm/client.py`
> - 归一化：`backend/app/matching/normalize.py`
> - 匹配引擎：`backend/app/matching/engine.py`（硬过滤 constraints.py → 软打分 scoring.py）
> - 抽取 API：`backend/app/api/requirement.py`；表单模型：`backend/app/schemas/resume.py`、`backend/app/models/db_models.py`（Resume）

---

## 1. 总览：数据流

```
表单（Resume 表 16 字段） ──resume_to_card──┐
                                            ├──→ RequirementCard（seeker）──→ 硬过滤 ──→ 软打分 ──→ 排序
原文（简历自述 / JD） ──LLM 抽取 extract_card──┘                                        （只有卡参与）
                                    │
                                    └──→ 校对 → _merge_cards 合并 ──→ requirement_cards 表落库
```

- 打分层（constraints.py / scoring.py）**只吃 RequirementCard**，代码中没有任何 Resume 表引用。
- 简历是卡的默认值来源（表单转卡），LLM 抽取是卡的补充来源（facts 独有字段）。
- 匹配读卡时二选一：有落库卡用整卡（已是两来源并集），无卡才现场从简历派生。

---

## 2. 求职者参与匹配打分的字段

求职者字段进入打分的位置分三类（方向不同维度不同，权重见 MATCHING_DESIGN.md 2.2）。

### 2.1 硬过滤（constraints.py，任一不过直接淘汰，不参与计分）

| 简历字段 | 卡字段 | 规则 |
| --- | --- | --- |
| location | hard.location | 同城，或任一方 remote |
| willing_remote | hard.remote | 参与上一条判断 |
| expected_salary_min | hard.salary_min | 岗位 salary_max >= 求职者下限 |
| education | hard.education | 求职者档 >= 岗位最低档 |
| experience_years | hard.experience_years | 求职者 >= 岗位最低年数 |
| skills | soft.skills | 岗位 must_skills ⊆ 求职者技能，缺一淘汰 |

None 一律视为通过（数据不全不误杀）。

### 2.2 软打分（scoring.py，权重：enterprise_to_seekers / seeker_to_jobs）

| 简历/卡字段 | 维度 | 算法 | 权重 |
| --- | --- | --- | --- |
| skills → soft.skills | skill | Jaccard 重合度 | 0.25 / 0.24 |
| expected_salary_min/max → hard.salary | salary | 岗位薪资覆盖期望区间比例 | 0.13 / 0.14 |
| experience_years → hard.experience_years | experience | 富余度：不足 0 / 持平 0.7 / 多 ≤2 年 0.85 / 更多 1.0 | 0.08 |
| industry → soft.industries | industry | 相同 1 / 未填 0.5 / 不同 0 | 0.09 / 0.08 |
| summary+name+skills+industry → raw_text+label | text | bigram 文本相似 | 0.20 / 0.14 |
| target_job_types → soft.target_job_types | job_types | 与岗位类型覆盖率；未填用 facts.is_student 兜底 | 0.03 |
| intended_titles → soft.intended_titles | title（仅 seeker_to_jobs） | 与岗位名文本相似取最大 | 0.14 |
| ideal_company_traits → facts.ideal_company_traits | company（仅 seeker_to_jobs） | 6 轴 LLM 打分，确定性降级 | 0.15 |
| self_traits → soft.traits | trait（仅 enterprise_to_seekers） | 档位比较，按企业 importance 加权 | 0.22 |

- `soft.importance`（求职卡维度权重覆盖）仅在 seeker_to_jobs 方向生效（该方向求职者是 target），覆盖后整表重归一化。
- company 维度是唯一 LLM 打分的维度（DeepSeek，temperature=0，进程内缓存；逐字段相等 1/不同 0/缺失 0.5 的确定性降级）。
- 打分前 skills / industries 统一过 normalize.py 别名归一（python→Python、vue3→Vue、后端→后端开发 等）。

### 2.3 不参与打分的字段

- job_status：仅企业端 availability 筛选 + 同分次级排序（随时到岗 > 本月到岗 > 观望了解），payload 透出展示。
- facts 预留键 certificates / work_experiences / projects / campus_roles / self_assessment：
  定义了、LLM 会抽取落卡，但当前打分代码不读；self_assessment 若抽取更新了 raw_text 会间接影响 text 维度。

---

## 3. 简历设计 vs 需求卡抽取设计

### 3.1 简历设计（resumes 表 / ResumeCreate / 前端 Resumes.vue，16 个业务字段）

- 基础 10 个：name、location、expected_salary_min/max、education、experience_years、industry（单值）、skills、willing_remote、summary
- 求职状态 1 个：job_status
- 匹配新增 4 个：intended_titles（≤5）、target_job_types（多选）、self_traits（12 特质 × 弱/中/强）、ideal_company_traits（JOB_FACT_AXES 6 轴结构）

### 3.2 需求卡抽取设计（llm/extract.py `_ROLE_FIELDS["seeker"]`，seeker 卡 17 组字段）

- hard 7 个 + label：label=姓名、hard.location/remote/salary_min/salary_max/education/experience_years/job_status
- soft 5 个：soft.skills、soft.industries（数组，表单是单值）、soft.intended_titles、soft.target_job_types、soft.traits（dimension 用 id 或中文名，value 弱/中/强，importance 默认 1.0）
- facts 7 键（抽取层独有，表单没有）：is_student、certificates、work_experiences、projects、campus_roles、self_assessment、ideal_company_traits
- 提示词附带共享上下文：12 项人才特质定义（C1-C3 认知 / A1-A3 行动 / S1-S3 社交 / M1-M3 动机）、6 轴字段规格（枚举/数值范围）；要求"缺失填 null/空，绝不编造"。

### 3.3 两者差异

| 项 | 简历设计 | 抽取设计 |
| --- | --- | --- |
| is_student 等 facts 5 键 | 无（表里没有列） | 有，只落卡表 |
| industry | 单个字符串 | 数组 |
| summary | 单字段 | 同落 raw_text + facts.self_assessment |
| 降级 | — | 无 key/失败/校验失败 → 只含 raw_text 的空卡 |

---

## 4. 简历与需求卡的关系

1. 物理独立两张表：resumes 存表单字段；requirement_cards 存整卡（role="seeker" + ref_id=简历 id + card JSON）。需求卡**永不回写简历表**。
2. 需求卡 = 简历字段与抽取 facts 的并集视图，谁优先看最后写操作（三个写路径）：
   - 表单落卡（创建简历时 upsert_card，resumes.py）：表单派生的 hard/soft 覆盖卡同名值；facts 按 `{**existing.facts, **card.facts}` 合并，表单派生的 3 个键（is_student=None / self_assessment=summary / ideal_company_traits）会压过卡里同名值。注意：is_student=None 会把 LLM 抽出的值冲掉，与"表单保留已有 facts"的设计意图有出入，属待修点。
   - 抽取写卡（_merge_cards）：抽取非空 hard/soft 覆盖、空的保留表单值；facts 逐键补非空、不覆盖已有非空；remote 仅抽取为 True 才覆盖；source 置 llm。
   - 匹配读卡（get_card）：有卡用卡、无卡派生，不做现场合并。
3. 简历表没有的信息（facts 独有键）只能靠抽取填进卡表；resumes API 目前只有 POST（创建）和 GET（列表），没有更新端点。

---

## 5. 原始文本 → 打分字段的处理流程

### 5.1 原文进卡（POST /api/requirement/parse → extract_card）

1. role 由后端从 user.role 派生，忽略前端传值（api/requirement.py）。
2. 拼提示词：_ROLE_FIELDS 字段清单 + 12 特质定义 + 6 轴规格 + JSON 输出格式约束 + 原文。
3. chat_json 调 DeepSeek chat/completions：response_format=json_object，temperature=0；key 读取顺序 settings.llm_api_key → 环境变量 DEEPSEEK_API_KEY → Windows 注册表 HKCU\Environment。
4. 失败兜底（无 key / 网络 / JSON 解析 / Pydantic 校验失败）→ 只含 raw_text 的空卡 + warning，不报错中断。
5. 校验通过后归一化：skills/must_skills 过 normalize_skills（别名表，未命中原样保留），industries 过 normalize_industry；traits 维度宽松校验（id 或中文名都收，未知进 warnings 不拒绝）。

### 5.2 校对合并写回（POST /api/requirement/apply → apply_extracted_card）

1. 归属校验：role 匹配账号，target 实体 owner_id == user.id，否则 403。
2. get_card 读现有卡（无卡则表单转卡派生）作为合并基底。
3. _merge_cards 合并（规则见 4.2），upsert_card 整卡落 requirement_cards 表。

### 5.3 匹配时读卡（matching_service.match → get_card）

- 优先读落库卡（含抽取 facts）；无卡/解析失败 → resume_to_card / job_to_card 表单派生。
- 两条路径产出结构一致的卡，且转卡层同样做技能/行业归一化，打分层不感知来源。

### 5.4 卡 → 打分（engine.match）

1. check_hard_constraints 硬过滤（2.1 五条，任一不过淘汰）。
2. compute_score 软打分：卡字段映射到各维度（2.2），weights 分方向两张表，soft.importance 覆盖后重归一化，总分 0-1。
3. 按分降序取 top_n；企业端按 job_status 次级排序（不进分）；结果快照落 match_records（含 target_card、reasons），返回 MatchItem。

---

## 6. 关键结论

1. 最终打分只用需求卡；简历字段经"转卡/合并"写进卡后才参与打分，打分层不感知数据来源。
2. 简历从未做过抽取时，卡等于简历本身；做过抽取后，卡是简历 + 抽取的并集。
3. 除 company 维度外全程确定性代码；LLM 只出现在卡生成（extract）与公司特质打分两处，均有确定性降级。
4. 待修点：表单落卡会以 is_student=None 冲掉抽取值（见 4.2）。
