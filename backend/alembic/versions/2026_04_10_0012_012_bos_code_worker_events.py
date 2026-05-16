"""012 add BOS Code worker events table

Revision ID: 012_bos_code_worker_events
Revises: 011_bos_code_tasks_workers
Create Date: 2026-04-10 15:40:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012_bos_code_worker_events"
down_revision: Union[str, None] = "011_bos_code_tasks_workers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_worker_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.Integer(), nullable=True),
        sa.Column("lane", sa.String(length=100), nullable=False),
        sa.Column("event_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["code_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["worker_id"], ["code_workers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_worker_events_workspace_id"), "code_worker_events", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_worker_events_task_id"), "code_worker_events", ["task_id"], unique=False)
    op.create_index(op.f("ix_code_worker_events_worker_id"), "code_worker_events", ["worker_id"], unique=False)
    op.create_index(op.f("ix_code_worker_events_lane"), "code_worker_events", ["lane"], unique=False)
    op.create_index(op.f("ix_code_worker_events_event_name"), "code_worker_events", ["event_name"], unique=False)
    op.create_index(op.f("ix_code_worker_events_status"), "code_worker_events", ["status"], unique=False)
    op.create_index(op.f("ix_code_worker_events_created_at"), "code_worker_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_worker_events_created_at"), table_name="code_worker_events")
    op.drop_index(op.f("ix_code_worker_events_status"), table_name="code_worker_events")
    op.drop_index(op.f("ix_code_worker_events_event_name"), table_name="code_worker_events")
    op.drop_index(op.f("ix_code_worker_events_lane"), table_name="code_worker_events")
    op.drop_index(op.f("ix_code_worker_events_worker_id"), table_name="code_worker_events")
    op.drop_index(op.f("ix_code_worker_events_task_id"), table_name="code_worker_events")
    op.drop_index(op.f("ix_code_worker_events_workspace_id"), table_name="code_worker_events")
    op.drop_table("code_worker_events")
