"""020 add simulation lab visual observation metadata

Revision ID: 020_simulation_lab_visual_observation
Revises: 019_simulation_lab_persistence
Create Date: 2026-04-24 09:15:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020_simulation_lab_visual_observation"
down_revision: Union[str, None] = "019_simulation_lab_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("simulation_cycles", sa.Column("visual_observation", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_cycles", "visual_observation")
