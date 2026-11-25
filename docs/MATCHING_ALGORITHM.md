# 匹配打分算法：从需求卡到排序（解释性说明）

> 本文档解释匹配打分算法「怎么算、为什么这么设计」，配一个完整的手算例子，帮助理解。
> 字段契约与枚举定稿见 [MATCHING_DESIGN.md](./MATCHING_DESIGN.md)（规范），
> 数据流与字段关系见 [REQUIREMENT_CARD_FLOW.md](./REQUIREMENT_CARD_FLOW.md)，
> 企业端字段从获取到打分见 [ENTERPRISE_MATCHING_FLOW.md](./ENTERPRISE_MATCHING_FLOW.md)。
>
> 代码落点（`backend/app/matching/`）：
> - 引擎：`engine.py`（`match()`：硬过滤 → 软打分 → 排序）
> - 硬过滤：`constraints.py`（`check_hard_constraints()`）
> - 软打分：`scoring.py`（`compute_score()` + 分方向权重表 `WEIGHTS`）
> - 文本相似：`embedding.py`（`text_similarity()`，零依赖确定性分词）
> - 别名归一：`normalize.py`（技能/行业别名合并）
> - 公司特质 LLM 打分：`../llm/company_traits.py`（`score_company_traits()`）
> - LLM 调用封装：`../llm/client.py`（`chat_json()` / `api_key()`，DeepSeek）

---

## 0. 一句话概括

需求卡构建完毕后，匹配 Agent 只吃卡、吐分：先按硬条件过滤掉不合格的候选，
再对剩下的候选按多个维度分别量化成 0-1 的分数，加权求和得到一个总分，最后按总分降序排序。
整条链路是确定性纯函数（可复现、可单测），唯一的 LLM 介入点是「公司特质 6 轴」一个维度，
且带确定性降级。

## 1. 总体流水线

```
engine.match(target, candidates, direction, top_n, min_score)
  │
  ├─ 1) 硬过滤  check_hard_constraints()  逐候选跑 5 条规则，任一不满足即淘汰
  │
  ├─ 2) 软打分  compute_score()           每个维度归一化到 0-1，加权求和
  │
  └─ 3) 排序    按总分降序，截取 top_n（分数低于 min_score 的也丢弃）
```

输入是三 Agent 的统一契约 `RequirementCard`（企业端/求职端同一张卡，`role` 区分）。
匹配方向分两种，决定了「谁在找谁」以及「哪些维度参与打分」：

| 方向 | 含义 | target（搜索者） | candidate（候选） |
| --- | --- | --- | --- |
| `seeker_to_jobs` | 求职者找岗位 | 求职者卡 | 岗位卡 |
| `enterprise_to_seekers` | 企业找人才 | 岗位卡 | 求职者卡 |

引擎内部先把 target/candidate 统一抽成 `job`/`seeker` 两个角色，之后所有规则都不再
分方向写两份，而是按同一条规则比较（`constraints._split_direction`）。

## 2. 硬过滤：为什么先过滤再打分

打分只衡量「有多匹配」，不回答「能不能匹配」。把「硬伤」（地点不对、薪资谈不拢、
学历不够）混进分数会稀释分数的语义，所以先做一轮门槛过滤。任一规则不满足即淘汰，
剩下的才进入打分。

5 条规则（`constraints.py`）：

| # | 规则 | 判定 |
| --- | --- | --- |
| 1 | 地点 | 同城，或任一方支持远程 |
| 2 | 薪资 | 岗位 `salary_max >=` 求职者 `salary_min`（区间有交集） |
| 3 | 学历 | 求职者学历档 `>=` 岗位最低档（`EDU_LEVELS` 索引比较） |
| 4 | 经验 | 求职者 `experience_years >=` 岗位最低年数 |
| 5 | 必备技能 | 岗位 `must_skills` 全部被求职者技能覆盖，缺一淘汰 |

两个设计原则：

- **数据不全视为通过**（`_ge_or_none`）：任一字段是 `None` 就不过滤。宁可放进来交给
  软打分用中性分处理，也不因采集不全误杀。
- **双语义字段按方向比较**：`education` / `experience_years` 在企业卡是「最低要求」、
  在求职卡是「自身水平」，同一字段两套语义，抽成 job/seeker 后天然正确。

## 3. 软打分：把「匹配程度」量化到 0-1

每个维度都归一化到 0-1，最后加权求和。`None`/缺失的数据不当作 0 扣分，而是给一个
「中性分」（通常是 0.5），语义是「不知道，不奖励也不惩罚」。

### 3.1 通用维度（两个方向都参与）

**skill — 技能 Jaccard 重合度**

```
score = |A ∩ B| / |A ∪ B|
```

交集占并集的比例，衡量技能集合的重叠程度。用 Jaccard 而不是单纯交集数，是因为它
同时惩罚「求职者会一堆无关技能」和「岗位要求一堆求职者不会的技能」。

**salary — 岗位薪资覆盖求职者期望区间的比例**

```
seeker_span = 求职者期望区间长度
overlap     = 岗位区间与求职者期望区间的重叠长度
score       = min(1.0, overlap / seeker_span)
```

衡量「岗位能给的薪资，覆盖求职者想要的范围多少」。区间完全包住期望 = 1.0；
岗位上限低于求职者下限（已在硬过滤拦下）= 0；数据不全 = 中性 0.5。

**experience — 经验富余度（阶梯）**

| 情况 | 分数 |
| --- | --- |
| 求职者经验 < 岗位要求 | 0.0（本应在硬过滤拦下，这里兜底） |
| 持平 | 0.7 |
| 富余 ≤ 2 年 | 0.85 |
| 富余 > 2 年 | 1.0 |

用阶梯而不是线性，因为「刚好达标」已经很好（0.7 起），「经验远超」边际收益递减。
缺数据 = 中性 0.5。

**industry — 行业相等**

```
相等 = 1.0   一方未填 = 0.5   不同 = 0.0
```

行业是离散枚举，没有「相似度」，只能二值。求职者/岗位各取第一个行业比较。

**text — 整卡文本相似度**

把双方卡的 `label + raw_text + skills + industries` 拼接成一段文本，做余弦相似度。
这是对「自由文本 JD / 简历摘要」的兜底匹配，能抓到结构化字段没覆盖到的措辞相近。

文本相似度实现（`embedding.py`）是零依赖的确定性 KeywordEmbedder，**不是**向量模型：

```
分词：英文/数字按单词（python、vue），中文按逐字 bigram（"后端开发" → 后端/端开/开发）
相似度：两边 token 的带频次余弦相似度  dot / (|a| * |b|)
```

选确定性实现是为了在无模型、无网络的环境里也能跑通闭环和单测；后续可在 config 把
`embedding_backend` 切到 semantic，换成 bge 向量余弦，引擎其余部分不变（AI 层可插拔）。

**job_types — 岗位类型覆盖率**

```
score = |企业 job_types ∩ 求职 target_job_types| / |企业 job_types|
```

企业没填 = 中性 0.5。求职者没填 `target_job_types` 时用 `facts.is_student` 兜底：
学生 → [应届校招, 实习生]，非学生 → [社招]，未知 → 中性 0.5。

### 3.2 分方向专属维度

三个维度只在某一个方向有意义（方向性小结见 [MATCHING_DESIGN.md](./MATCHING_DESIGN.md#27-方向性小结)）：

**title（仅 seeker_to_jobs）** — 求职者意向职位 vs 岗位名

```
score = max( text_similarity(t, job.label) for t in seeker.soft.intended_titles )
```

取意向职位列表里最接近的一个，空 → 中性 0.5。求职者有明确想去的岗位名，企业端
「岗位」没有「想找的人才名」，所以只有这个方向有 title。

**trait（仅 enterprise_to_seekers）** — 企业理想人才特质 vs 求职者自评

- 档位归一：`normalize_trait_level` 把 弱/中/强 映射到 0.0/0.5/1.0（含中文名、别名，未知落中性 0.5）。
- 逐维度按 importance 加权比较：求职档 >= 期望档 → 1.0；差一档 → 0.5；差两档 → 0.0；
  求职者缺该维度记录 → 0.0。
- 企业没要求任何特质 → 中性 0.5。
- `dimension` 归一化：中文名（如「结构化」）映射回 id（C1），兼容 LLM 抽取输出。

这是「企业找人才」方向的核心维度——企业招人本质是招「具备某些特质的人」，求职卡的自评
特质和岗位卡的理想人才特质在这里对上。

**company（仅 seeker_to_jobs）** — 求职者理想公司 vs 企业实际公司（6 轴）

全链路唯一的 LLM 打分点，见第 5 节。

### 3.3 分方向权重表

各维度重要性不同，权重分方向两张表（`scoring.WEIGHTS`，当前为先简单分配，后续可调）：

```
seeker_to_jobs        skill 0.24 / company 0.15 / title 0.14 / salary 0.14 / text 0.14
                      industry 0.08 / experience 0.08 / job_types 0.03
enterprise_to_seekers skill 0.25 / trait 0.22 / text 0.20 / salary 0.13
                      industry 0.09 / experience 0.08 / job_types 0.03
```

两个方向权重刻意不同：求职者方向没有 trait（给了 company），企业方向没有 title/company
（给了 trait，且 text 权重更高，因为企业主要靠 JD 文本和简历文本兜底匹配）。

### 3.4 importance 覆盖与重归一化

`target.soft.importance` 允许某次搜索临时覆盖某个维度的权重（例如用户强调「技能优先」）。
覆盖后**整张权重表重新归一化**，保证总分仍落在 0-1：

```
score = Σ( w[k] * dims[k] ) / Σ( w[k] )    只对参与方向的维度求和
```

## 4. 完整手算例子（seeker_to_jobs）

求职者张三找后端岗位，假设已转成如下两张卡（薪资单位：千元/月）：

**求职卡（target）**
```
label="张三", raw_text="两年 Python 后端开发经验，做过数据后台"
hard:  location=北京, remote=False, salary_min=15, salary_max=25, education=本科, experience_years=2
soft:  skills=[Python, Vue, PostgreSQL, 数据分析], industries=[互联网],
       intended_titles=[Python后端开发], target_job_types=[社招]
facts: is_student=False
```

**岗位卡（candidate）**
```
label="后端开发工程师", raw_text="负责后端服务开发与数据库设计"
hard:  location=北京, remote=True, salary_min=18, salary_max=30, education=本科,
       experience_years=2, must_skills=[Python, PostgreSQL], job_types=[社招]
soft:  skills=[Python, Java, PostgreSQL, Docker], industries=[互联网]
facts: company_traits={...}
```

**第 1 步：硬过滤**

| 规则 | 判定 | 结果 |
| --- | --- | --- |
| 地点 | 北京 == 北京 | 通过 |
| 薪资 | 30 >= 15 | 通过 |
| 学历 | 本科(2) >= 本科(2) | 通过 |
| 经验 | 2 >= 2 | 通过 |
| 必备技能 | {Python, PostgreSQL} ⊆ {Python, Vue, PostgreSQL, 数据分析} | 通过 |

全部通过，进入打分。

**第 2 步：软打分（各维度 0-1）**

```
skill:      求职 {Python,Vue,PostgreSQL,数据分析}  ∩ 岗位 {Python,Java,PostgreSQL,Docker}
            交集 {Python,PostgreSQL}=2，并集=6  →  2/6 = 0.33
title:      "Python后端开发" vs "后端开发工程师"
            tokenize("python后端开发") = [python, 后端, 端开, 开发]
            tokenize("后端开发工程师") = [后端, 端开, 开发, 发工, 工程, 程师]
            余弦 = 3 / (2 * √6) ≈ 0.61
salary:     岗位[18,30] vs 求职期望[15,25]，重叠 [18,25] 长度 7，期望长度 10  →  7/10 = 0.70
experience: 2 vs 2，持平  →  0.70
industry:   互联网 == 互联网  →  1.00
text:       （label+raw_text+skills+industries 拼接后的 bigram 余弦，这里取示意值）≈ 0.55
job_types:  {社招} ∩ {社招} / 1  →  1.00
company:    （LLM 或确定性降级打分，这里取示意值）≈ 0.83
```

**第 3 步：加权求和**（权重 seeker_to_jobs，见 3.3）

```
score = 0.24*0.33 + 0.14*0.61 + 0.14*0.70 + 0.08*1.00
      + 0.08*0.70 + 0.14*0.55 + 0.03*1.00 + 0.15*0.83
      = 0.079 + 0.085 + 0.098 + 0.080 + 0.056 + 0.077 + 0.030 + 0.125
      ≈ 0.63
```

> 说明：`text` 与 `company` 两项依赖自由文本内容和 LLM 输出，上例取的是示意值；
> 其余维度（skill/title/salary/industry/experience/job_types）都是按代码公式精确算出的值。

`compute_score` 返回 `(round(score, 4), 原因列表)`，原因列表供前端展示：

```
技能重合 0.33 / 职位名匹配 0.61 / 薪资覆盖 0.70 / 经验富余 0.70 / 行业相同
岗位类型匹配 1.00 / 文本相似 0.55 / 公司特质 0.83 (公司特质匹配(LLM))
```

## 5. 为什么「打分不进 LLM」（唯一例外：公司特质 6 轴）

所有维度打分都是确定性纯函数，理由有二：

1. **可复现、可单测**：同样的输入永远同样的分数，匹配排序可回归测试，不依赖外部 API 稳定性。
2. **零延迟、零成本**：一次匹配要过几十上百个候选 × 若干维度，每维都调 LLM 会慢且烧钱。

唯一例外是 **company（公司特质 6 轴）**：求职者的「理想公司」和企业「实际公司」都是
JOB_FACT_AXES 结构化的语义描述（如「忙季周工时 60h vs 45h」），逐字段相等没法表达
「接近但不相等」，必须语义判断，所以交给 LLM。但它带三层保险（`company_traits.py`）：

1. **任一方无数据** → 直接中性 0.5，不调 LLM。
2. **有 key 走 LLM**：结构化 JSON 喂 DeepSeek，逐轴 0-1 分 + 一句理由，6 轴等权，`temperature=0`，结果进程内缓存（同组合不重复调用）。
3. **确定性降级**：无 key / 调用失败 / 解析失败时回退到逐字段比较——相等=1.0、不同=0.0、缺失=0.5，取 6 轴均值。

所以即使 LLM 完全不可用，company 维度也能给出一个合理但不精确的分数，整条链路不断。

### 5.1 用哪个 LLM：DeepSeek

- 服务与模型：DeepSeek，模型 `deepseek-chat`。
- 接口：`https://api.deepseek.com/chat/completions`（OpenAI 兼容协议），httpx 直连，不依赖 openai 库。
- 配置：`backend/app/config.py`（`llm_base_url` / `llm_model` / `llm_timeout=30.0`）。
- API key 读取顺序（`llm/client.py:api_key()`）：
  1. `settings.llm_api_key`
  2. 环境变量 `DEEPSEEK_API_KEY`
  3. Windows 注册表 HKCU\Environment 兜底（本机开发环境）
- 调用封装：`chat_json(messages, temperature)`，强制 `response_format=json_object`，
  默认 `temperature=0.0`；无 key / 网络失败 / 超时 / 解析失败统一抛 `LLMUnavailable`，
  由调用方走确定性降级。

项目里走这一套 DeepSeek client 的调用点有两处：

- 需求卡抽取：`llm/extract.py`（原文 → 卡预览，`temperature=0`）
- 公司特质 6 轴打分：`llm/company_traits.py`（见上）

其中匹配打分链路里的 LLM 介入只有 company 一处；其余维度打分全部是确定性代码。

## 6. 归一化前置（打分之前）

技能和行业在转卡阶段就做了别名归一（`normalize.py`），保证同一件事不被当作两件事：

- 技能别名：`python/py/python3/python开发` → `Python`；`vue/vuejs/vue3` → `Vue`；`k8s` → `Kubernetes` 等。
- 行业别名：`it/互联网行业/web` → `互联网`；`大数据` → `数据` 等。
- 只合并「同义别名/拼写变体」，不合并语义不同的词（MySQL 与 PostgreSQL 保持独立）。
- 未命中 strip 后原样返回，避免误改 C++ / Node.js / Go 等特殊大小写。

这一步在 `job_to_card` / `resume_to_card`（转卡层）统一调用，所以 `skill`/`must_skills`/`industry`
在硬过滤和软打分里用的都是归一化后的值。

## 7. 排序与输出

`engine.match()` 最后：

1. 过滤：丢掉未过硬的候选。
2. 打分：算出每个候选的总分，低于 `min_score` 的丢弃。
3. 排序：按总分降序，截取 `top_n`。
4. 返回：`[(cand, score, 命中的硬规则, 原因列表), ...]`，`cand` 保留原对象（含 id），供调用方回填候选主键落库。

企业端（`enterprise_to_seekers`）在分数相同时还有一次次级排序：按求职者的到岗状态
`随时到岗 > 本月到岗 > 观望了解`，并在 payload 里透出 `job_status` 供前端展示（求职状态
不参与打分，只做筛选与展示，见 MATCHING_DESIGN.md 2.5）。
