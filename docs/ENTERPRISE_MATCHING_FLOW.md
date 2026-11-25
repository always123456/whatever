# 企业端匹配打分字段：从获取到打分

> 本文档回答企业端（方向 `enterprise_to_seekers`，企业找人才）的匹配打分字段有哪些、
> 从获取到打分的完整流程，以及各字段在硬过滤/软打分中的角色。
> 字段契约与算法定稿见 [MATCHING_DESIGN.md](./MATCHING_DESIGN.md)，数据流见 [REQUIREMENT_CARD_FLOW.md](./REQUIREMENT_CARD_FLOW.md)。
>
> 代码落点：
> - 转卡 / 读卡 / 合并：`backend/app/services/matching_service.py`（`job_to_card` / `get_card` / `_merge_cards`）
> - LLM 抽取：`backend/app/llm/extract.py`（`_ROLE_FIELDS["enterprise"]`）
> - 归一化：`backend/app/matching/normalize.py`
> - 硬过滤：`backend/app/matching/constraints.py`
> - 软打分：`backend/app/matching/scoring.py`
> - 引擎：`backend/app/matching/engine.py`

---

## 1. 企业端字段清单（企业需求卡 RequirementCard，role=enterprise）

企业卡由「岗位 Job + 公司 Company」两张表派生（`matching_service.job_to_card`），
或由 LLM 从 JD 原文抽取（`llm/extract.py` 的 `_ROLE_FIELDS["enterprise"]`），两者字段一致。

| 层 | 字段 | 来源 |
| --- | --- | --- |
| label | 职位名（job.title） | 表单 / LLM |
| raw_text | JD 描述（job.description） | 表单 / LLM |
| hard（硬条件） | location、remote、salary_min/max、education、experience_years、must_skills、job_types | Job 表 / LLM |
| soft（软偏好） | skills、industries、traits（=ideal_talents 理想人才特质） | Job 表 / LLM |
| facts（补充） | company_name、company_abbr、company_size、industry、overtime、social_insurance、company_traits | Companies 表 / LLM |

其中：

- `traits` 是 12 项人才特质（C1–C3 认知 / A1–A3 行动 / S1–S3 社交 / M1–M3 动机），
  每项带档位 弱/中/强 + importance（默认 1.0、重点 2.0），企业卡 traits = 理想人才特质（期望对方达到的档）。
- `company_traits` 是 6 轴结构（P 节奏 / S 结构 / F 反馈 / C 协作 / V 价值 / W 形态），各轴 3 字段。

## 2. 从获取到打分的流程

```
表单(Job+Company) ──job_to_card──┐
                                 ├─→ 企业卡 ──→ 硬过滤 ──→ 软打分 ──→ 次级排序 ──→ 落库+返回
JD原文 ──LLM抽取 extract_card────┘
              └─→ 校对 → _merge_cards 合并 ──→ requirement_cards 表
```

1. **获取**：两个来源。发布职位时表单落卡（`upsert_card`）；对 JD 原文调
   `POST /api/requirement/parse`（LLM 抽取）→ 校对 → `POST /api/requirement/apply`
   （`_merge_cards` 非空覆盖、空的保留表单值）写回卡表。
2. **读卡**（`get_card`）：匹配时优先读落库卡（含抽取 facts），无卡回退 `job_to_card`
   派生；技能/行业过 `normalize.py` 别名归一。industry 岗位留空时回退 company.industry。
3. **硬过滤**（`constraints.check_hard_constraints`）：企业卡作为 target，用自身条件筛求职者，5 条任一不过淘汰。
4. **软打分**（`scoring.compute_score`）：按 `WEIGHTS["enterprise_to_seekers"]` 加权求和，总分 0–1。
5. **次级排序 + 落库**：同分按求职状态 `job_status` 排序（随时到岗 > 本月到岗 > 观望了解，不进分），
   结果快照落 `match_records`，返回 MatchItem。

## 3. 真正进入打分/过滤的字段（企业端方向）

### 3.1 硬过滤（企业卡条件 → 筛求职者）

| 企业卡字段 | 规则 |
| --- | --- |
| hard.location | 同城，或任一方 remote |
| hard.remote | 参与上一条判断 |
| hard.salary_max | 岗位上限 >= 求职者 salary_min |
| hard.education | 求职者档 >= 岗位最低档 |
| hard.experience_years | 求职者 >= 岗位最低年数 |
| hard.must_skills | 全部被求职者技能覆盖，缺一淘汰 |

None 一律视为通过（数据不全不误杀）。

### 3.2 软打分维度与权重（`enterprise_to_seekers`）

| 维度 | 权重 | 用的企业字段 |
| --- | --- | --- |
| skill | 0.25 | soft.skills（Jaccard 重合） |
| trait | 0.22 | soft.traits（ideal_talents 档位加权比较） |
| salary | 0.13 | hard.salary_min/max（区间覆盖） |
| industry | 0.09 | soft.industries（岗位优先，回退公司行业） |
| experience | 0.08 | hard.experience_years（富余度） |
| text | 0.20 | label + raw_text + soft.skills + soft.industries（bigram 相似） |
| job_types | 0.03 | hard.job_types（覆盖率） |

`soft.importance` 可覆盖维度权重，覆盖后整表重归一化。

## 4. 不参与打分的企业字段

- `job_status`（求职者字段，非企业字段）：企业端只做 availability 筛选 + 同分次级排序，不进分。
- 公司 facts 里的 `company_name` / `company_abbr` / `company_size` / `overtime` / `social_insurance`：
  当前仅透出展示，不打分。
- `facts.company_traits`（公司 6 轴特质）：只在反向 `seeker_to_jobs` 的 company 维度（LLM 打分）生效，
  企业找人才方向不使用。

---

## 5. 一句话总结

企业端字段经「表单 / LLM 抽取 → 需求卡 → 硬过滤 → 软打分」四步；硬条件用
location / remote / salary / education / experience / must_skills，软打分用 skills、
ideal_talents(trait)、salary、industry、experience、JD 文本(text)、job_types，
公司 facts 字段除 industry 外均不进分。
