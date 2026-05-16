"""006 persist BOS release explanation fields

Revision ID: 006_release_decision_explanations
Revises: 005_bos_protocol_objects
Create Date: 2026-04-06 17:35:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_release_decision_explanations"
down_revision: Union[str, None] = "005_bos_protocol_objects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("release_decisions", sa.Column("blocking_factors", sa.JSON(), nullable=True))
    op.add_column("release_decisions", sa.Column("warning_factors", sa.JSON(), nullable=True))
    op.add_column("release_decisions", sa.Column("passed_checks", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("release_decisions", "passed_checks")
    op.drop_column("release_decisions", "warning_factors")
    op.drop_column("release_decisions", "blocking_factors")
