# 需求卡（RequirementCard）待办清单

## 一、需求字段 → 表单对齐（已完成）

| 字段 | 落库 | 前端 | 状态 |
| --- | --- | --- | --- |
| 学历下拉 | 已有 | Jobs.vue / Resumes.vue | 已完成 |
| 岗位类型（社招/应届校招/实习生/兼职） | Job.job_types (JSON) | Jobs.vue 多选 | 已完成 |
| 必备技能 | Job.must_skills (JSON) | Jobs.vue 逗号分隔 | 已完成（硬过滤） |
| 求职状态（随时到岗/本月到岗/观望了解） | Resume.job_status | Resumes.vue 下拉 | 已完成 |
| 加班节奏 / 社保公积金 / 公司规模 | Job.overtime / social_insurance / company_size | Jobs.vue 下拉 | 已完成 |
| 理想人才特质（12 项） | Job.ideal_talents (JSON) | Jobs.vue 档位下拉（不限/弱/中/强）+ 重点开关 | 已完成（本轮改为水平档位） |
| 求职者人才特质自评（12 项） | Resume.self_traits (JSON) | Resumes.vue 档位下拉（未填/弱/中/强） | 已完成（自评兜底，正式测评模块待做） |
| 意向职位（≤5） | Resume.intended_titles (JSON) | Resumes.vue 逗号分隔 | 已完成 |
| 求职意向岗位类型 | Resume.target_job_types (JSON) | Resumes.vue 多选 | 已完成（软打分） |
| 公司特质（P-S-F-C-V-W 6 轴）双方 | facts.company_traits / ideal_company_traits | CompanyTraitsForm 组件 | 已完成（resumes 加 ideal_company_traits 列） |
| 学生与否 / 证书 | facts.is_student / certificates | 前端无 | Agent 抽取已落（extract.py），表单后补 |

新枚举在前后端各有一份常量（后端 schemas/requirement.py，前端 Jobs.vue / Resumes.vue），
改动时两边同步；后续可抽 /api/dict 端点统一维护。

## 二、特质枚举（已从 requirement.md 落地，原附图图片内容）

- 人才特质 4 大类 12 项（C-A-S-M）已固化进 schemas/requirement.py 的 TALENT_TRAITS。
- 岗位事实评估维度 6 轴（P-S-F-C-V-W）已固化进 JOB_FACT_AXES。
- 高分/低分行为锚点保留在 schemas/requirement.md，写 llm/extract.py 提示词时引用，不复制进代码。
- 若日后拿到原附图确认有出入，直接改这两个常量即可。

## 三、匹配算法（已完成，本轮）

- 匹配引擎升级吃 RequirementCard：matching_service.job_to_card / resume_to_card 做转换，profile dict 已删。
- 硬过滤（constraints.py）：地点/薪资/学历/经验 + 必备技能 must_skills 缺一淘汰。
- 软打分（scoring.py）分方向权重两张表：seeker_to_jobs 含 title/company，enterprise_to_seekers 含 trait。
- 特质档位 TRAIT_LEVELS 弱/中/强 → 0/0.5/1.0，企业=期望最低档、求职=自评水平，按 importance 加权比较。
- job_types 软打分（覆盖率 + is_student 兜底）；job_status 仅展示 + 企业端 availability 筛选/次级排序。
- 公司特质 6 轴 LLM 打分（llm/company_traits.py：DeepSeek，temperature=0 + 缓存 + 确定性降级）。
- 契约细节见 skill job-match-dev 的 references/matching.md。

## 四、需求理解 Agent 抽取（已完成本轮）

- llm/extract.py：原文（JD / 简历自述）→ RequirementCard 抽取 + Pydantic 校验 + 规则兜底，输出走 normalize 归一。
- POST /api/requirement/parse 端点（api/requirement.py，需登录）。
- 前端预览页 views/Requirement.vue（路由 /requirement + 菜单）。
- 公司特质 6 轴采集表单：共享组件 CompanyTraitsForm（企业端公司弹窗 + 求职端简历弹窗）；resumes 加 ideal_company_traits 列（迁移 f41e076a8551）。
- 技能/行业别名归一 matching/normalize.py，转卡层 job_to_card / resume_to_card 接入；job.industry 留空时回退 company.industry。

## 四-bis、仍待做

1. ~~抽取结果「合并进卡」写路径~~：已完成 —— POST /api/requirement/apply（matching_service.apply_extracted_card，非空合并 + 归属校验）。
2. 求职者人才特质测评模块（现状仍是自评下拉兜底）。
3. /api/dict 字典表：枚举与技能/行业字典统一维护（当前前后端各一份常量 + 内置别名表）。

## 五、数据库说明（已切 PostgreSQL）

- 统一 PostgreSQL（本地 127.0.0.1:5432 库 job_match/角色 job_match，密码在 backend/.env 的 JM_DATABASE_URL）。
- 迁移用 alembic（backend/alembic.ini + alembic/env.py，env.py 从 app.config 读 JM_ 环境变量）：改 db_models.py 后 `alembic revision --autogenerate` + `alembic upgrade head`；init_db() 启动时自动 upgrade head，_migrate_sqlite 已删除。
- 表：users / companies（企业主体 1:1）/ jobs（company_id 外键，去掉 company 字符串与 company_size/overtime/social_insurance）/ resumes（含 ideal_company_traits 列）/ requirement_cards（卡落库，facts 只进卡表）/ match_records（快照目标卡）。
- 写路径 upsert_card() 落卡、读卡 get_card()（无卡回退派生），见 services/matching_service.py；转卡层做技能/行业归一（matching/normalize.py）。
