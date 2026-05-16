"""016 add BOS Code session titles

Revision ID: 016_bos_code_session_titles
Revises: 015_bos_code_skill_feedback_stats
Create Date: 2026-04-12 23:10:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016_bos_code_session_titles"
down_revision: Union[str, None] = "015_bos_code_skill_feedback_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "code_sessions",
        sa.Column("title", sa.String(length=255), nullable=True),
    )
    op.create_index(op.f("ix_code_sessions_title"), "code_sessions", ["title"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_sessions_title"), table_name="code_sessions")
    op.drop_column("code_sessions", "title")
