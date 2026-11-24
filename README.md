# 企业与求职者双向匹配平台

前后端一体的完整网站。后端 FastAPI + SQLAlchemy，前端 Vue3 + Vite + Element Plus，
匹配引擎采用「规则硬过滤 → 多维度打分排序」，文本相似度层可插拔（默认关键词，可换 bge 向量）。

## 目录结构

```
job-match/
├── backend/                 # Python 后端（FastAPI）
│   ├── app/
│   │   ├── main.py          # 入口，挂载路由，启动时建表+播种演示数据
│   │   ├── config.py        # pydantic-settings（JM_ 前缀环境变量）
│   │   ├── db.py            # SQLAlchemy engine/session（默认 SQLite，可切 PostgreSQL）
│   │   ├── api/             # 路由：auth / jobs / resumes / match
│   │   ├── schemas/         # Pydantic 契约
│   │   ├── models/          # ORM 模型
│   │   ├── matching/        # 匹配引擎（纯函数）：constraints / scoring / embedding / engine
│   │   └── services/        # 匹配编排 + 演示数据播种
│   ├── tests/               # pytest 单元测试
│   └── requirements.txt
└── frontend/                # Vue3 前端（Vite + Element Plus + Pinia + Router）
    ├── src/
    │   ├── views/           # Login / Match / Jobs / Resumes
    │   ├── stores/          # Pinia（auth）
    │   ├── router/          # 路由 + 登录守卫
    │   └── api/             # axios 客户端（自动带 token）
    └── package.json
```

## 快速开始（开发模式）

后端（端口 8080）：

    cd /data/job-match/backend
    /root/miniconda3/bin/python -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080

前端（端口 5173，/api 代理到 8080）：

    cd /data/job-match/frontend
    npm install
    npm run dev

浏览器访问 http://<服务器IP>:5173

## 演示账号（密码均 123456）

    企业：enterprise1
    求职者：seeker1（张三/后端）、seeker2（李四/前端）、seeker3（王五/算法）、seeker4（赵六/运维）

首次启动自动写入 6 个职位和 4 份简历，登录后到「智能匹配」页即可体验双向匹配。

## API 一览（前缀 /api）

    POST /auth/register      注册（返回 JWT）
    POST /auth/login         登录（返回 JWT）
    POST /jobs               发布职位（仅企业）
    GET  /jobs               职位列表
    POST /resumes            创建简历（仅求职者）
    GET  /resumes            简历列表
    POST /match              双向匹配（需 Authorization: Bearer <token>）
    GET  /health             健康检查

匹配请求体：

    {"direction": "seeker_to_jobs", "target_id": null}      # 求职者→职位
    {"direction": "enterprise_to_seekers", "target_id": 1}  # 企业→求职者（指定职位ID）

## 匹配设计

    1) 硬过滤（规则兜底）：地点（同城或远程）、薪资、学历、经验，任一不满足直接排除。
    2) 打分排序（AI 层）：技能重合 0.35 + 行业 0.15 + 薪资覆盖 0.20 + 经验 0.10 + 文本相似 0.20，
       各维度归一化到 0-1 后加权求和，权重在 app/matching/scoring.py 可调。
    3) 文本相似度：默认 KeywordEmbedder（确定性、零依赖）；要启用 bge 语义向量，
       设置 JM_EMBEDDING_BACKEND=semantic 并安装 sentence-transformers（见下）。

## 切换语义嵌入（可选）

    .venv/bin/pip install sentence-transformers
    # 设置环境变量后重启：
    export JM_EMBEDDING_BACKEND=semantic
    export JM_SEMANTIC_MODEL=BAAI/bge-small-zh-v1.5

引擎其余部分不变，只替换 app/matching/embedding.py 的相似度实现。

## 切换 PostgreSQL（可选）

本机 127.0.0.1:5432 已有 PostgreSQL。将 JM_DATABASE_URL 设为
postgresql+psycopg://user:pass@127.0.0.1:5432/job_match 并安装 psycopg[binary] 即可；
建表仍由启动时的 init_db() 自动完成。默认 SQLite 免部署，适合 MVP。

## 测试

    cd /data/job-match/backend && .venv/bin/python -m pytest -q

## Docker 部署（需先安装 Docker）

    docker compose up -d

见 docker-compose.yml（db=pgvector、backend、frontend=nginx）。
