"""008 add BOS Code branch state table

Revision ID: 008_bos_code_branch_state
Revises: 007_bos_code_domain
Create Date: 2026-04-10 12:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_bos_code_branch_state"
down_revision: Union[str, None] = "007_bos_code_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_branch_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("branch_name", sa.String(length=255), nullable=False),
        sa.Column("base_branch", sa.String(length=255), nullable=False),
        sa.Column("head_commit", sa.String(length=64), nullable=True),
        sa.Column("base_commit", sa.String(length=64), nullable=True),
        sa.Column("merge_base_commit", sa.String(length=64), nullable=True),
        sa.Column("is_dirty", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_stale_against_base", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ahead_count", sa.Integer(), nullable=True),
        sa.Column("behind_count", sa.Integer(), nullable=True),
        sa.Column("branch_status", sa.String(length=50), server_default="clean", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "branch_name", name="uq_code_branch_states_workspace_branch"),
    )
    op.create_index(op.f("ix_code_branch_states_workspace_id"), "code_branch_states", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_branch_states_branch_name"), "code_branch_states", ["branch_name"], unique=False)
    op.create_index(op.f("ix_code_branch_states_is_dirty"), "code_branch_states", ["is_dirty"], unique=False)
    op.create_index(
        op.f("ix_code_branch_states_is_stale_against_base"),
        "code_branch_states",
        ["is_stale_against_base"],
        unique=False,
    )
    op.create_index(op.f("ix_code_branch_states_branch_status"), "code_branch_states", ["branch_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_branch_states_branch_status"), table_name="code_branch_states")
    op.drop_index(op.f("ix_code_branch_states_is_stale_against_base"), table_name="code_branch_states")
    op.drop_index(op.f("ix_code_branch_states_is_dirty"), table_name="code_branch_states")
    op.drop_index(op.f("ix_code_branch_states_branch_name"), table_name="code_branch_states")
    op.drop_index(op.f("ix_code_branch_states_workspace_id"), table_name="code_branch_states")
    op.drop_table("code_branch_states")
