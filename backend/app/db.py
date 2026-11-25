import os

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
    """用 alembic 迁移到最新（PostgreSQL 正式迁移；不再 create_all + SQLite 补列）。"""
    from alembic import command
    from alembic.config import Config

    from . import models  # noqa: F401  确保模型已注册

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    command.upgrade(Config(os.path.join(backend_dir, "alembic.ini")), "head")
