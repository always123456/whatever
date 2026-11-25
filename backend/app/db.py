from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite():
    """MVP 轻量补列：SQLite 建表后新增字段用 ALTER TABLE 幂等补上（不引 alembic）。"""
    if not settings.database_url.startswith("sqlite"):
        return
    adds = {
        "jobs": [
            ("job_types", "JSON"),
            ("company_size", "VARCHAR(32)"),
            ("overtime", "VARCHAR(32)"),
            ("social_insurance", "VARCHAR(32)"),
            ("ideal_talents", "JSON"),
        ],
        "resumes": [
            ("job_status", "VARCHAR(16)"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in adds.items():
            have = {r[1] for r in conn.exec_driver_sql(f'PRAGMA table_info("{table}")')}
            for name, typ in cols:
                if name not in have:
                    conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {name} {typ}')
