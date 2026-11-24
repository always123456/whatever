"""演示数据：首次启动且表为空时自动写入，方便直接体验匹配闭环。

演示账号（密码均为 123456）：
  企业：enterprise1
  求职者：seeker1 / seeker2 / seeker3 / seeker4
"""
from sqlalchemy.orm import Session

from ..api.deps import hash_password
from ..db import SessionLocal
from ..models.db_models import Job, Resume, User

DEMO_JOBS = [
    dict(title="后端工程师", company="示例科技", location="北京", salary_min=20, salary_max=35,
         education="本科", experience_years=2, industry="互联网", remote=False,
         skills=["Python", "FastAPI", "PostgreSQL"], description="负责后端服务与匹配引擎开发"),
    dict(title="前端工程师", company="示例科技", location="北京", salary_min=18, salary_max=30,
         education="本科", experience_years=1, industry="互联网", remote=False,
         skills=["Vue", "TypeScript", "CSS"], description="负责平台前端开发"),
    dict(title="算法工程师", company="智算科技", location="上海", salary_min=30, salary_max=60,
         education="硕士", experience_years=3, industry="人工智能", remote=True,
         skills=["Python", "PyTorch", "推荐系统"], description="负责推荐与匹配算法"),
    dict(title="数据分析师", company="数联科技", location="深圳", salary_min=15, salary_max=25,
         education="本科", experience_years=1, industry="数据", remote=False,
         skills=["SQL", "Python", "数据分析"], description="负责业务数据分析"),
    dict(title="产品经理", company="示例科技", location="北京", salary_min=18, salary_max=28,
         education="本科", experience_years=2, industry="互联网", remote=False,
         skills=["产品设计", "需求分析", "项目管理"], description="负责平台产品规划"),
    dict(title="运维工程师", company="云智科技", location="杭州", salary_min=16, salary_max=26,
         education="大专", experience_years=1, industry="云计算", remote=True,
         skills=["Linux", "Docker", "Kubernetes"], description="负责服务部署与运维"),
]

DEMO_RESUMES = [
    dict(name="张三", location="北京", expected_salary_min=20, expected_salary_max=30,
         education="本科", experience_years=3, industry="互联网", willing_remote=False,
         skills=["Python", "FastAPI", "PostgreSQL", "Docker"], summary="3 年后端开发，熟悉高并发服务"),
    dict(name="李四", location="北京", expected_salary_min=15, expected_salary_max=25,
         education="本科", experience_years=2, industry="互联网", willing_remote=False,
         skills=["Vue", "TypeScript", "CSS"], summary="2 年前端开发，熟悉组件库与工程化"),
    dict(name="王五", location="上海", expected_salary_min=35, expected_salary_max=55,
         education="硕士", experience_years=5, industry="人工智能", willing_remote=True,
         skills=["Python", "PyTorch", "推荐系统"], summary="5 年算法经验，专注推荐与召回"),
    dict(name="赵六", location="杭州", expected_salary_min=15, expected_salary_max=20,
         education="大专", experience_years=2, industry="云计算", willing_remote=True,
         skills=["Linux", "Docker", "Shell"], summary="2 年运维经验，熟悉容器化部署"),
]


def seed_if_empty():
    db: Session = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        ent = User(username="enterprise1", password_hash=hash_password("123456"),
                   role="enterprise", display_name="示例企业账号")
        seekers = [
            User(username="seeker1", password_hash=hash_password("123456"),
                 role="seeker", display_name="张三"),
            User(username="seeker2", password_hash=hash_password("123456"),
                 role="seeker", display_name="李四"),
            User(username="seeker3", password_hash=hash_password("123456"),
                 role="seeker", display_name="王五"),
            User(username="seeker4", password_hash=hash_password("123456"),
                 role="seeker", display_name="赵六"),
        ]
        db.add(ent)
        db.add_all(seekers)
        db.flush()

        for d in DEMO_JOBS:
            db.add(Job(owner_id=ent.id, **d))
        for i, d in enumerate(DEMO_RESUMES):
            db.add(Resume(owner_id=seekers[i].id, **d))
        db.commit()
    finally:
        db.close()
