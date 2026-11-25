# 双向匹配平台：三 Agent 设计与前后端交互方案

> 本文档基于项目现有骨架（FastAPI 后端 + Vue3 前端 + 匹配引擎）整理，
> 说明三个 Agent（企业端需求理解、求职者端需求理解、双向匹配）的设计、
> 融入方式、数据库设计以及前后端交互约定。

---

## 目录

1. [三个 Agent 的设计](#1-三个-agent-的设计)
2. [融入后的项目骨架](#2-融入后的项目骨架)
3. [数据库设计](#3-数据库设计)
4. [前后端交互](#4-前后端交互)
5. [实施顺序建议](#5-实施顺序建议)

---

## 1. 三个 Agent 的设计

### 1.1 核心原则

- **LLM 只做「理解」和「解释」，匹配打分永远是确定性代码。**
  这样结果可复现、可解释、可单测，没有 API key 也能跑通。
  现有 `app/matching/engine.py`、`scoring.py` 已经在遵守这一原则。
- **三个 Agent 不是三个微服务，而是同一个模块化单体里的三个模块。**
  MVP 阶段不引入多 Agent 框架。

### 1.2 统一中间表示：需求卡（RequirementCard）

这是三个 Agent 之间的「契约」：企业端和求职端理解 Agent 输出的都是
同一张卡，匹配 Agent 只吃卡、吐分。卡分两类字段：

| 类型 | 含义 | 作用 |
| --- | --- | --- |
| HardConstraint 硬条件 | 地点/远程、薪资上下限、最低学历、最低经验、必备技能 | 不满足直接淘汰 |
| SoftPreference 软偏好 | 技能重合、行业匹配、薪资覆盖、文本相似（含 importance 权重） | 只影响排序，不淘汰 |

> 现有 `matching_service.job_to_profile` / `resume_to_profile` 返回的 dict
> 就是需求卡的雏形，只是硬/软条件混在一起。第一步是把它显式结构化为
> RequirementCard 的 Pydantic 模型（`app/schemas/requirement.py`）。

### 1.3 Agent 1 / Agent 2：需求理解 Agent（企业端 + 求职端）

两者完全对称，同一个类按 `role` 区分。

- **输入**：一段自然语言（企业 JD 原文 / 求职者简历或自述）
- **输出**：结构化的 RequirementCard（Pydantic 模型）
- **实现**：`app/llm/` 模块，OpenAI 兼容 chat client + 结构化输出，
  输出后必须过 Pydantic 校验；校验失败回退到规则抽取。
- **降级路径**：无 key 或配置 FakeLLM 时返回空卡，系统仍靠用户手动
  填写的表单字段跑通。现有表单字段就是「人工版需求卡」，Agent 只把
  「自由文本 → 结构化」这一步自动化，两者落到同一张表。

### 1.4 Agent 3：双向匹配 Agent

- **输入**：两张需求卡（一张 target + 一张候选集）
- **流程**：硬过滤 → 软打分 → 归一化加权 → 排序 → 生成解释
- **实现**：现有 `app/matching/` 的 `engine.py + constraints.py + scoring.py`
  就是 Agent 3 的确定性核心，**不用重写**，只需两处改造：
  1. 输入从 profile dict 升级为显式 RequirementCard 结构；
  2. 加一个可选的 LLM explainer，把 `scoring.py` 已算好的 reasons
     翻译成一段自然语言推荐语（不影响分数）。
- **双向**：由 `direction` 参数控制（`seeker_to_jobs` / `enterprise_to_seekers`），
  现有代码已支持。

---

## 2. 融入后的项目骨架

变化是增量，不是推倒。新增 `llm/`、`agents/` 两个包，并扩展
`schemas/`、`models/`：

```
backend/app/
  main.py              不变，挂路由
  config.py            加 llm 配置（api_key/base_url/model/llm_enabled）
  db.py                不变
  api/
    auth.py jobs.py resumes.py matching.py   已有
    applications.py    新增：投递/收藏（传统招聘闭环）
  schemas/
    requirement.py     新增：RequirementCard / HardConstraint / SoftPreference
  models/db_models.py  加 Application / Favorite / MatchRecord / RequirementCard 表
  matching/            Agent 3 确定性核心（保留 constraints/scoring/embedding/engine）
  llm/                 新增：Agent 1 + Agent 2 的实现
    client.py          OpenAI 兼容 client，无 key 走 Fake
    extract.py         自然语言 → RequirementCard 抽取 + Pydantic 校验
    explain.py         可选的推荐语生成
  agents/              新增：三个 Agent 的对外门面
    requirement_agent.py   需求理解（企业/求职共用一个类）
    matching_agent.py      调 matching/engine + llm/explain
  services/
    matching_service.py    改造：先走 requirement agent 抽取，再喂 engine
    application_service.py 新增
```

分层关系：`agents/` 是「叫 Agent 的门面」，`matching/` 和 `llm/` 是可替换的
实现；`matching_service` 编排整条链路：

```
原文 → Agent1/2 出卡 → Agent3 打分 → 落库 → 返回
```

---

## 3. 数据库设计

在现有 `users / jobs / resumes` 基础上补充：

| 表 | 说明 | 优先级 |
| --- | --- | --- |
| companies | 企业主体：公司名、规模、行业、简介、logo（替代 Job.company 冗余字段） | 中 |
| applications | 投递记录：job_id + resume_id + status(待处理/已查看/面试/录用/拒绝) + 时间 | **高** |
| favorites | 收藏：双向（求职者收藏职位 / 企业收藏简历） | 中 |
| match_records | 匹配记录：谁用哪张卡匹配了谁，score、reasons、方向；可回溯、做匹配历史页 | 中 |
| requirement_cards | 需求卡落库：Agent 抽取结果持久化，与 resume/job 关联，存 JSON；「原文理解」只跑一次 | **高** |
| interviews | 面试邀约：application 的下一步状态机 | 低 |
| messages / notifications | 站内信：投递/收藏/匹配的触达 | 低 |
| 字典表 | 行业、技能、学历枚举，做下拉与归一化 | 低 |

**存储层建议**：MVP 的 SQLite（`job_match.db`）够用；要上 Agent 和完整功能时，
把 `database_url` 切到 PostgreSQL 即可（改一行配置，SQLAlchemy 模型不用动）。
JSON 列存技能列表和需求卡等非结构化数据。

---

## 4. 前后端交互

### 4.1 现状（沿用）

- 前端 Vue3 + Vite，axios 实例 `baseURL=/api`，请求拦截器自动加
  `Authorization: Bearer <token>`（存 localStorage）。
- 开发期 vite proxy 把 `/api` 转发到 `127.0.0.1:8080`；生产用 nginx 反代
  （`frontend/nginx.conf` 已有）。
- 后端 FastAPI 提供 REST JSON，JWT 鉴权（`get_current_user` 从 Authorization
  头解析 user_id，**从不信任客户端传的 user_id**）。

### 4.2 Agent 相关交互（两种模式）

- **模式一（同步，先做）**：扩展现有 `POST /api/match`，MatchRequest 加可选
  `raw_text`。用户在匹配页粘贴 JD 或简历原文，后端同步「抽取 → 打分 → 返回」。
- **模式二（异步，大模型慢时用）**：`POST /api/requirement/parse` 提交原文
  返回需求卡预览，用户校对后再 `POST /api/match`。

### 4.3 端点清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | /api/requirement/parse | 输入 `{role, raw_text}` → 返回 RequirementCard（理解可见、可校对） |
| POST | /api/match | 已有，扩展 `raw_text` 可选 → 内部先 parse 再 match |
| GET/POST | /api/applications | 投递与查询 |
| POST/DELETE | /api/favorites | 收藏 |
| GET | /api/matches | 匹配历史 |

前端层面：新增 `views/Requirement.vue`（需求卡预览+校对）、扩展 `Match.vue`
（加「粘贴原文」入口和自然语言推荐语展示）。auth store、axios 拦截器不动。

---

## 5. 实施顺序建议

1. 定义 `app/schemas/requirement.py` 的 Pydantic 契约（RequirementCard /
   HardConstraint / SoftPreference）。
2. 把 `matching/engine.py` 的输入改成 RequirementCard，并保持现有测试
   （`backend/tests/test_engine.py`）通过。
3. 加 `llm/client.py` 的 FakeLLM 占位，保证无 key 闭环可跑。
4. 接真实 client（DeepSeek 走 OpenAI 兼容协议）。
5. 补 applications / favorites / match_records 等传统招聘功能与对应端点。

---

## 一句话总结

三个 Agent = 两个「文本 → 需求卡」的抽取器（新增 `llm/`）+ 一个
「需求卡 → 分数」的确定性引擎（已有 `matching/`，改造输入结构即可）。
数据库先补 applications（投递闭环）和 requirement_cards（Agent 落库），
其余按需补。前后端沿用现有 JWT + axios + vite 代理，只加原始文本入口和
需求卡预览两个新端点。
