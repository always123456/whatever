# 需求卡字段采集方式（前端）

> 本文记录需求卡（RequirementCard）每个字段「从哪来、怎么采」，与代码同步。
> 代码落点：
> - 前端 `frontend/src/views/Jobs.vue`、`Resumes.vue`、`Requirement.vue`、`components/CompanyTraitsForm.vue`
> - 后端 `backend/app/schemas/requirement.py`（契约）、`services/matching_service.py`（转卡/落卡/合并）、
>   `llm/extract.py`（抽取）、`matching/normalize.py`（归一）
> 字段契约与打分见 `docs/MATCHING_DESIGN.md`；表结构见 `docs/DATABASE_DESIGN.md`。

---

## 1. 三条采集途径

需求卡字段按性质走三条途径，落到同一张卡：

| 途径 | 适用字段 | 前端落点 | 后端 |
| --- | --- | --- | --- |
| 结构化表单 | hard 全部、soft 技能/行业/意向、facts 公司信息 | Jobs.vue / Resumes.vue / CompanyTraitsForm | JobCreate / ResumeCreate / CompanyUpdate → upsert_card |
| 自由文本 LLM 抽取 | soft 技能/特质、facts 证书/经历/项目/在校/学生与否等 | Requirement.vue（粘贴原文） | POST /api/requirement/parse → /apply 合并写回 |
| 量表/问答 | 人才特质 12 项（测评）、公司特质 6 轴 | CompanyTraitsForm（6 轴）、特质档位下拉 | 转卡进 soft.traits / facts |

原则：结构化字段用表单直接填（不靠 LLM，可复现）；自由文本字段靠抽取（LLM 只做「理解」，
打分永远确定性代码）；难以客观自评的特质走测评，公司事实走结构化问答。

---

## 2. 逐字段获取方式

### 2.1 硬条件 hard（结构化表单为主，不依赖 LLM）

| 字段 | 求职端语义 | 企业端语义 | 控件 | 前端落点 |
| --- | --- | --- | --- | --- |
| location | 期望地点 | 工作地点 | 文本框（建议后续换省市下拉） | Jobs.vue / Resumes.vue |
| remote / willing_remote | 接受远程 | 支持远程 | 开关 el-switch | Jobs.vue / Resumes.vue |
| salary_min / salary_max | 期望月薪上下限（千元） | 月薪上下限（千元） | 数字 el-input-number | Jobs.vue / Resumes.vue |
| education | 本人学历 | 最低学历 | 单选下拉（不限/大专/本科/硕士/博士） | Jobs.vue / Resumes.vue |
| experience_years | 本人经验年数 | 最低经验年数 | 数字 el-input-number | Jobs.vue / Resumes.vue |
| must_skills | — | 必备技能（缺一淘汰） | 逗号分隔文本 | Jobs.vue |
| job_types | — | 岗位类型（社招/应届校招/实习生/兼职） | 多选 el-select | Jobs.vue |
| job_status | 求职状态（随时到岗/本月到岗/观望了解） | — | 单选下拉 | Resumes.vue |

> education / experience_years 是双语义字段：企业卡=最低要求、求职卡=自身水平，匹配引擎按方向比较。
> 硬条件也可由 LLM 抽取（extract.py 会抽），但表单是权威来源；抽取写回时「抽取非空才覆盖、空的保留表单值」。

### 2.2 软偏好 soft

| 字段 | 求职端 | 企业端 | 获取方式 |
| --- | --- | --- | --- |
| skills | 自身技能 | 岗位技能 | 表单逗号分隔 + LLM 抽取；转卡层 normalize 归一 |
| industries | 意向行业 | 行业归属 | 表单文本框 + LLM 抽取；归一；job.industry 留空回退 company.industry |
| intended_titles | 意向职位（≤5） | — | 表单逗号分隔 + LLM 抽取 |
| target_job_types | 求职意向岗位类型 | — | 表单多选 + LLM 抽取 |
| traits | 人才特质自评 | 理想人才特质 | 见 3.1 |
| importance | 维度权重覆盖 | 维度权重覆盖 | 企业端「重点」开关映射为 2.0；LLM 抽取可给 |

### 2.3 补充信息 facts（自由字典）

求职卡 7 键：

| 键 | 获取方式 | 说明 |
| --- | --- | --- |
| is_student | LLM 抽取（bool） | 表单暂无；抽取落地后 job_types 软打分的学生兜底生效 |
| certificates | LLM 抽取（数组） | 证书，表单暂无 |
| work_experiences | LLM 抽取（数组） | 工作/实习经历，表单暂无 |
| projects | LLM 抽取（数组） | 项目/竞赛经历，表单暂无 |
| campus_roles | LLM 抽取（数组） | 在校经历，表单暂无 |
| self_assessment | 表单 summary 文本框 | 同时作为 raw_text |
| ideal_company_traits | CompanyTraitsForm 6 轴问答 | 存 resumes.ideal_company_traits 列 → 转卡进 facts |

企业卡 7 键：

| 键 | 获取方式 | 说明 |
| --- | --- | --- |
| company_name / company_abbr | 公司档案表单 | Jobs.vue 公司弹窗 |
| company_size | 公司档案表单（下拉：1-49人…1000人以上） | COMPANY_SIZES |
| industry | 公司档案表单 + 岗位表单 | 岗位行业优先，留空回退公司行业 |
| overtime | 公司档案表单（下拉：不加班…996） | OVERTIMES |
| social_insurance | 公司档案表单（下拉：全额缴纳…面议） | SOCIAL_INSURANCES |
| company_traits | CompanyTraitsForm 6 轴问答 | 存 companies.company_traits 列 → 转卡进 facts |

---

## 3. 两个特殊结构

### 3.1 人才特质 12 项（C-A-S-M）

- 采集来源因类别不同（见 `backend/app/schemas/requirement.md`）：认知（C）/动机（M）靠情境题，行动（A）靠经历，社交（S）靠自由文本。
- 现状（MVP）：双方表单档位下拉——
  - 企业端：每项「不限/弱/中/强」+ 重点开关（重点 → importance=2.0），表达「期望对方达到的最低档」。
  - 求职端：每项「未填/弱/中/强」自评，表达自身水平。
- 待做：求职者正式测评模块（自评不可靠，应改情境题/行为题，答案由规则或 LLM 判档成 0/0.5/1.0）。
- 落点：soft.traits（TraitItem：dimension + value + importance），企业端参与 trait 维度打分。

### 3.2 公司特质 6 轴（P-S-F-C-V-W）

- 采集：共享组件 `CompanyTraitsForm`，6 轴 × 3 字段 = 18 题，控件类型由 `JOB_FACT_AXES` 的采集定义驱动
  （`type=int` 数字、`type=select` 下拉、`type=text` 文本）。
- 企业端如实回答「我们公司实际是…」；求职端同结构问「你理想的公司…」。
- 存储：`companies.company_traits` / `resumes.ideal_company_traits`（JSON dict，`{轴: {字段键: 值}}`）→ 转卡进 facts。
- 打分：仅 seeker_to_jobs 方向，company 维度；LLM 逐轴打分（temperature=0 + 缓存），无 key 走确定性降级；任一方无数据 → 中性 0.5。

---

## 4. 获取后的处理链路

```
表单字段 ──┐
           ├─> job_to_card / resume_to_card（转卡 + normalize 归一）──┐
原文 ──> extract.py 抽取 ──> parse 预览 ──> apply 合并写回 ──────────┴─> upsert_card 落卡
                                                                          （role+ref_id 唯一，facts 只进卡表）
匹配：get_card 读卡 ──> 硬过滤（constraints.py）──> 软打分（scoring.py）──> 排序 ──> 快照落 match_records
```

关键约定：

1. 归一化：`matching/normalize.py` 对 skills / must_skills / industries 做确定性别名归一
   （Python/python、js/JavaScript、k8s/Kubernetes、后端/后端开发、IT/互联网…），转卡层统一接入，
   保证 Jaccard 重合与行业比较不被别名稀释。
2. 写回合并：`matching_service.apply_extracted_card`（POST /api/requirement/apply）——
   抽取的非空 hard/soft 覆盖、空的保留表单值；facts 逐键补非空、已有非空不被空值覆盖；落卡 source=llm；
   并做归属校验（只能写自己的简历/职位）。
3. facts 只进卡表（requirement_cards.card.facts），resumes / jobs 操作表不存抽取类字段
   （例外：ideal_company_traits / company_traits 因需表单编辑，落操作表列）。
