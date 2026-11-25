# 数据库设计文档

> 本文件记录 job-match 平台的数据库结构，与代码同步。
> 代码落点：`backend/app/models/db_models.py`（ORM 模型）、
> `backend/alembic/versions/`（迁移）、`backend/app/db.py`（引擎 + init_db）。
> 需求卡字段契约见 `docs/MATCHING_DESIGN.md`。

---

## 1. 技术栈

- 数据库：PostgreSQL 18（本地 127.0.0.1:5432，库/角色均为 `job_match`；连接密码在 `backend/.env` 的 `JM_DATABASE_URL`，不提交）。
- ORM：SQLAlchemy 2.x（Declarative + Mapped 注解）。
- 迁移：alembic（`backend/alembic.ini` + `backend/alembic/env.py`）。改模型后执行
  `alembic revision --autogenerate -m "..."` 再 `alembic upgrade head`；应用启动时
  `init_db()` 自动 `upgrade head`。
- 列表/字典类字段用 JSON 列（SQLAlchemy 通用 JSON，Postgres 下为 json 类型）；暂不按 JSON 内容建索引，匹配 MVP 是整表加载进内存打分。

---

## 2. 表关系概览

```
users 1 ── 1 companies        （一个企业用户绑定一家公司，MVP 1:1）
users 1 ── N jobs             （企业用户发布多个职位）
users 1 ── N resumes          （求职者创建简历）
companies 1 ── N jobs         （职位挂在公司下，company_id 外键）
jobs    1 ── 1 requirement_cards   （role='enterprise', ref_id=job.id）
resumes 1 ── 1 requirement_cards   （role='seeker', ref_id=resume.id）
users   1 ── N match_records  （用户发起的匹配历史）
```

需求卡（RequirementCard）是三个 Agent 的统一中间表示：表单字段 / LLM 抽取结果都落成
一张卡，匹配引擎只吃卡吐分。`jobs` / `resumes` 是「表单可编辑 + 列表筛选」的操作表，
`requirement_cards` 是「匹配契约 + 抽取 facts」的落库表。详见 `docs/MATCHING_DESIGN.md` 1.5 节。

---

## 3. 表详情

### 3.1 users —— 用户账号

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 主键 |
| username | varchar(64) unique | 登录名 |
| password_hash | varchar(128) | bcrypt 哈希（不存明文） |
| role | varchar(16) | `seeker` 求职者 / `enterprise` 企业 |
| display_name | varchar(64) nullable | 显示昵称 |
| created_at / updated_at | timestamp | 创建 / 更新时间 |

### 3.2 companies —— 企业主体（公司）

公司级字段从 jobs 拆出，避免「一个企业发多条职位时公司信息重复/漂移」。

| 字段 | 类型 | 说明 | 对应需求卡 |
| --- | --- | --- | --- |
| id | int PK | 主键 | — |
| owner_id | int FK users.id, unique | 所属企业用户（1:1） | — |
| name | varchar(128) | 公司名 | facts.company_name |
| abbr | varchar(64) | 公司简称 | facts.company_abbr |
| size | varchar(32) | 人员规模（1-49人 / 50-99人 / 100-499人 / 500-999人 / 1000人以上） | facts.company_size |
| industry | varchar(64) | 行业归属 | facts.industry（兜底） |
| overtime | varchar(32) | 加班节奏（不加班 / 偶尔加班 / 经常加班 / 大小周 / 996） | facts.overtime |
| social_insurance | varchar(32) | 社保公积金（全额缴纳 / 按最低基数缴纳 / 无公积金 / 面议） | facts.social_insurance |
| logo_url | varchar(255) nullable | 公司 Logo | 展示用 |
| company_traits | JSON dict | 公司特质 6 轴（JOB_FACT_AXES 的 P-S-F-C-V-W） | facts.company_traits |
| created_at / updated_at | timestamp | 创建 / 更新时间 | — |

### 3.3 jobs —— 职位（企业端）

| 字段 | 类型 | 说明 | 对应需求卡 |
| --- | --- | --- | --- |
| id | int PK | 主键 | card.id |
| owner_id | int FK users.id | 发布企业用户 | — |
| company_id | int FK companies.id, nullable | 所属公司 | — |
| title | varchar(128) | 职位名称 | label |
| location | varchar(64) | 工作地点（省市） | hard.location |
| salary_min / salary_max | float nullable | 月薪上下限（千元） | hard.salary_min / hard.salary_max |
| education | varchar(16) | 最低学历（不限/大专/本科/硕士/博士） | hard.education（最低要求） |
| experience_years | int | 最低经验年数 | hard.experience_years（最低要求） |
| industry | varchar(64) | 岗位行业 | soft.industries |
| skills | JSON list | 岗位技能集合 | soft.skills |
| remote | bool | 是否支持远程 | hard.remote |
| description | text | 岗位描述原文 | raw_text |
| must_skills | JSON list | 必备技能（缺一淘汰） | hard.must_skills |
| job_types | JSON list | 岗位类型（社招/应届校招/实习生/兼职） | hard.job_types |
| ideal_talents | JSON list[dict] | 理想人才特质 `[{dimension,value,importance}]` | soft.traits |
| status | varchar(16) | `active` 在招 / `closed` 关闭 | 展示/筛选 |
| created_at / updated_at | timestamp | 创建 / 更新时间 | — |

### 3.4 resumes —— 简历（求职端）

| 字段 | 类型 | 说明 | 对应需求卡 |
| --- | --- | --- | --- |
| id | int PK | 主键 | card.id |
| owner_id | int FK users.id | 求职者用户 | — |
| name | varchar(64) | 姓名 | label |
| location | varchar(64) | 期望地点（省市） | hard.location |
| expected_salary_min / max | float nullable | 期望月薪上下限（千元） | hard.salary_min / hard.salary_max |
| education | varchar(16) | 本人学历 | hard.education（自身水平） |
| experience_years | int | 本人经验年数 | hard.experience_years（自身水平） |
| industry | varchar(64) | 意向行业 | soft.industries |
| skills | JSON list | 自身技能 | soft.skills |
| willing_remote | bool | 是否接受远程 | hard.remote |
| summary | text | 简介/自述 | raw_text + facts.self_assessment |
| job_status | varchar(16) | 求职状态（随时到岗/本月到岗/观望了解） | hard.job_status |
| intended_titles | JSON list | 意向职位（最多 5 个） | soft.intended_titles |
| target_job_types | JSON list | 求职意向岗位类型 | soft.target_job_types |
| self_traits | JSON list[dict] | 人才特质自评 `[{dimension,value}]` | soft.traits |
| created_at / updated_at | timestamp | 创建 / 更新时间 | — |

### 3.5 requirement_cards —— 需求卡落库

需求卡的持久化：表单字段和 Agent 抽取结果统一落成一张卡，匹配只读卡。
`role` + `ref_id` 联合唯一，指向 job 或 resume。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 主键 |
| role | varchar(16) | `seeker` / `enterprise`，区分卡方向 |
| ref_id | int | 指向 jobs.id 或 resumes.id |
| source | varchar(16) | 卡来源：`form` / `llm` / `rule` / `manual` |
| card | JSON | 完整需求卡（hard + soft + facts，结构见 MATCHING_DESIGN.md） |
| raw_text | text nullable | 抽取来源原文（JD / 简历原文），可回溯 |
| created_at / updated_at | timestamp | 创建 / 更新时间 |
| — | unique(role, ref_id) | 每个实体只有一张卡 |

说明：`jobs` / `resumes` 不再单独存 facts（证书/项目/在校经历/学生与否/公司特质等抽取字段
只进卡表 `card.facts`）；写路径由 `matching_service.upsert_card()` 统一落卡（表单更新保留
已有 facts、只覆盖 hard/soft），读卡走 `get_card()`（无卡回退 `job_to_card` / `resume_to_card` 派生）。

### 3.6 match_records —— 匹配记录（快照）

匹配历史的落库。采用「快照」：保存目标卡 JSON 副本，历史分数不因卡后续修改而漂移。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 主键 |
| user_id | int FK users.id | 发起匹配的用户 |
| direction | varchar(32) | `seeker_to_jobs` / `enterprise_to_seekers` |
| target_role | varchar(16) | 搜索方角色（seeker / enterprise） |
| target_id | int | 搜索方实体 id（job.id 或 resume.id） |
| target_card | JSON | 搜索卡快照（完整 RequirementCard） |
| candidate_role | varchar(16) | 候选方角色 |
| candidate_id | int | 候选方实体 id |
| score | float | 匹配分（0-1） |
| matched_rules | JSON list | 通过哪些硬条件 |
| reasons | JSON list | 各维度评分说明 |
| created_at | timestamp | 匹配时间 |

### 3.7 alembic_version —— 迁移版本（内部表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| version_num | varchar(32) | 当前已应用的迁移版本号（alembic 自动维护，勿手动改） |

---

## 4. 枚举（与 schemas/requirement.py 同步）

- 学历 EDUCATION_LEVELS：不限 / 大专 / 本科 / 硕士 / 博士
- 岗位类型 JOB_TYPES：社招 / 应届校招 / 实习生 / 兼职
- 求职状态 JOB_STATUSES：随时到岗 / 本月到岗 / 观望了解
- 人才特质 TALENT_TRAITS：C-A-S-M 四类 12 项（C1..M3）
- 特质档位 TRAIT_LEVELS：弱 / 中 / 强（打分映射 0 / 0.5 / 1.0）
- 岗位事实评估 JOB_FACT_AXES：P 节奏 / S 结构 / F 反馈 / C 协作 / V 价值 / W 形态，各 3 字段

---

## 5. 迁移方式

- 新库初始化：`alembic upgrade head`（或启动应用自动执行）。
- 改表：改 `db_models.py` → `alembic revision --autogenerate -m "..."` → 核对生成的
  migration → `alembic upgrade head`。
- 本地连接：`PGPASSWORD=<密码> psql -U job_match -h 127.0.0.1 -d job_match`，`\dt` 看表。
