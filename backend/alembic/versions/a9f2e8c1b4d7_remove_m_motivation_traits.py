"""remove M (动机) talent traits M1/M2/M3 from stored data

Revision ID: a9f2e8c1b4d7
Revises: 6f57d305bf1b
Create Date: 2026-11-26

人才特质由 12 项（C-A-S-M）缩减为 9 项（C-A-S），删除动机类 M1 成就驱动 /
M2 稳定性 / M3 价值取向。本迁移为纯数据迁移：清理存量 JSON 数据里这些维度，
避免已删除特质继续参与特质匹配打分。表结构列不变（仍是 JSON）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a9f2e8c1b4d7'
down_revision: Union[str, Sequence[str], None] = '6f57d305bf1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 待删除的特质维度：id 或中文名都匹配
REMOVED_DIMENSIONS = {"M1", "M2", "M3", "成就驱动", "稳定性", "价值取向"}


def _filter_traits(items):
    """过滤掉已删除维度的特质项；无变化返回 None（避免无谓 UPDATE）。"""
    if not items:
        return None
    kept = [t for t in items if isinstance(t, dict) and t.get("dimension") not in REMOVED_DIMENSIONS]
    return kept if kept != items else None


def upgrade() -> None:
    bind = op.get_bind()

    jobs = sa.table("jobs", sa.column("id", sa.Integer), sa.column("ideal_talents", sa.JSON))
    for row in bind.execute(sa.select(jobs.c.id, jobs.c.ideal_talents)):
        cleaned = _filter_traits(row.ideal_talents)
        if cleaned is not None:
            bind.execute(sa.update(jobs).where(jobs.c.id == row.id).values(ideal_talents=cleaned))

    resumes = sa.table("resumes", sa.column("id", sa.Integer), sa.column("self_traits", sa.JSON))
    for row in bind.execute(sa.select(resumes.c.id, resumes.c.self_traits)):
        cleaned = _filter_traits(row.self_traits)
        if cleaned is not None:
            bind.execute(sa.update(resumes).where(resumes.c.id == row.id).values(self_traits=cleaned))

    cards = sa.table("requirement_cards", sa.column("id", sa.Integer), sa.column("card", sa.JSON))
    for row in bind.execute(sa.select(cards.c.id, cards.c.card)):
        card = row.card or {}
        traits = (card.get("soft") or {}).get("traits") or []
        cleaned = _filter_traits(traits)
        if cleaned is not None:
            new_card = dict(card)
            new_card.setdefault("soft", {})["traits"] = cleaned
            bind.execute(sa.update(cards).where(cards.c.id == row.id).values(card=new_card))


def downgrade() -> None:
    # 数据删除不可逆：已删除的特质项无法恢复，降级为 no-op。
    pass
