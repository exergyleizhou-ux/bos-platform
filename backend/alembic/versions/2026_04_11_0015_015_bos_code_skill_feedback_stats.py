"""015 add BOS Code skill feedback stats

Revision ID: 015_bos_code_skill_feedback_stats
Revises: 014_bos_code_skill_usage_stats
Create Date: 2026-04-11 20:50:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015_bos_code_skill_feedback_stats"
down_revision: Union[str, None] = "014_bos_code_skill_usage_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "code_skills",
        sa.Column("positive_feedback_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "code_skills",
        sa.Column("negative_feedback_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "code_skills",
        sa.Column("last_feedback_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_code_skills_last_feedback_at"), "code_skills", ["last_feedback_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_skills_last_feedback_at"), table_name="code_skills")
    op.drop_column("code_skills", "last_feedback_at")
    op.drop_column("code_skills", "negative_feedback_count")
    op.drop_column("code_skills", "positive_feedback_count")
