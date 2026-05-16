"""014 add BOS Code skill usage stats

Revision ID: 014_bos_code_skill_usage_stats
Revises: 013_bos_code_runtime_memory_reflection
Create Date: 2026-04-11 20:20:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014_bos_code_skill_usage_stats"
down_revision: Union[str, None] = "013_bos_code_runtime_memory_reflection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "code_skills",
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "code_skills",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_code_skills_last_used_at"), "code_skills", ["last_used_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_skills_last_used_at"), table_name="code_skills")
    op.drop_column("code_skills", "last_used_at")
    op.drop_column("code_skills", "usage_count")
