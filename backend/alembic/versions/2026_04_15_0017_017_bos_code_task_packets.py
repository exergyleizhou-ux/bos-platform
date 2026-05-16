"""017 add BOS Code task packet payload

Revision ID: 017_bos_code_task_packets
Revises: 016_bos_code_session_titles
Create Date: 2026-04-15 08:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017_bos_code_task_packets"
down_revision: Union[str, None] = "016_bos_code_session_titles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("code_tasks", sa.Column("task_packet", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("code_tasks", "task_packet")
