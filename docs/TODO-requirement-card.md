# 需求卡（RequirementCard）待办清单

## 一、前端表单对齐（用户要求：必须一致）

| 字段 | 后端常量 | 前端现状 | 处理 |
| --- | --- | --- | --- |
| 学历下拉 | EDUCATION_LEVELS（不限/大专/本科/硕士/博士） | Jobs.vue / Resumes.vue 已有，枚举一致 | 已完成 |
| 岗位类型（社招/应届校招/实习生/兼职） | JOB_TYPES | Jobs.vue 已加多选下拉，落库 Job.job_types (JSON) | 已完成 |
| 求职状态（随时到岗/本月到岗/观望了解） | JOB_STATUSES | Resumes.vue 已加下拉，落库 Resume.job_status | 已完成 |
| 加班节奏 / 社保公积金 / 公司规模 | facts 自由字段 | Jobs.vue 已加下拉（选项见前端常量），落库 Job.overtime / social_insurance / company_size | 已完成 |
| 理想人才特质（12 项） | TALENT_TRAITS | Jobs.vue 已加 12 项三档选择（不限/加分项/重要），落库 Job.ideal_talents (JSON) | 已完成 |
| 求职者人才特质（12 项） | TALENT_TRAITS | 前端无 | 待测评模块（小测评&场景模拟 → 人才特质报告） |
| 公司特质（P-S-F-C-V-W 6 轴）双方 | JOB_FACT_AXES | 前端无 | 待表单扩展（6 轴 × 3 字段，MVP 暂不做） |
| 学生与否 / 证书 / 意向职位（≤5）等 | facts / soft.intended_titles | 前端无 | Agent 抽取优先，表单后续补充 |

新枚举在前后端各有一份常量（后端 schemas/requirement.py，前端 Jobs.vue / Resumes.vue），
改动时两边同步；后续可抽 /api/dict 端点统一维护。

## 二、特质枚举（已从 requirement.md 落地，原附图图片内容）

- 人才特质 4 大类 12 项（C-A-S-M）已固化进 schemas/requirement.py 的 TALENT_TRAITS。
- 岗位事实评估维度 6 轴（P-S-F-C-V-W）已固化进 JOB_FACT_AXES。
- 高分/低分行为锚点保留在 schemas/requirement.md，写 llm/extract.py 提示词时引用，不复制进代码。
- 若日后拿到原附图确认有出入，直接改这两个常量即可。

## 三、后续实施步骤（AGENT_DESIGN.md 实施顺序 2-5，本会话暂不做）

1. job_to_card / resume_to_card 转换函数，engine 输入从 profile dict 升级为 RequirementCard，保持 tests/test_engine.py 通过。
   （转换时把新字段带上：Job.job_types→hard.job_types，Job.ideal_talents→soft.traits，Resume.job_status→hard.job_status，加班/社保/规模→facts）
2. llm/client.py FakeLLM 占位（无 key 闭环可跑）。
3. 接真实 client（DeepSeek，OpenAI 兼容协议），extract.py 抽取 + Pydantic 校验 + 规则兜底。
4. POST /api/requirement/parse 端点 + 前端需求卡预览/校对页（views/Requirement.vue）。

## 四、数据库说明

- MVP 用 SQLite + db.py 里 _migrate_sqlite() 幂等补列（新增字段无需重建库）。
- 切 PostgreSQL 时删掉 _migrate_sqlite，改用正式迁移工具（alembic）。
