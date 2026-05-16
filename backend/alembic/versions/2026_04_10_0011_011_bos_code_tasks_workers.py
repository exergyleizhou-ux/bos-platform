"""011 add BOS Code task and worker tables

Revision ID: 011_bos_code_tasks_workers
Revises: 010_bos_code_lsp_sessions
Create Date: 2026-04-10 15:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011_bos_code_tasks_workers"
down_revision: Union[str, None] = "010_bos_code_lsp_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("task_status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("priority", sa.String(length=50), server_default="normal", nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_tasks_tenant_id"), "code_tasks", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_code_tasks_user_id"), "code_tasks", ["user_id"], unique=False)
    op.create_index(op.f("ix_code_tasks_workspace_id"), "code_tasks", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_tasks_session_id"), "code_tasks", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_tasks_task_status"), "code_tasks", ["task_status"], unique=False)
    op.create_index(op.f("ix_code_tasks_priority"), "code_tasks", ["priority"], unique=False)

    op.create_table(
        "code_workers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("worker_name", sa.String(length=150), nullable=False),
        sa.Column("worker_role", sa.String(length=100), nullable=False),
        sa.Column("worker_status", sa.String(length=50), server_default="spawning", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_event_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["code_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_workers_workspace_id"), "code_workers", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_workers_task_id"), "code_workers", ["task_id"], unique=False)
    op.create_index(op.f("ix_code_workers_worker_status"), "code_workers", ["worker_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_workers_worker_status"), table_name="code_workers")
    op.drop_index(op.f("ix_code_workers_task_id"), table_name="code_workers")
    op.drop_index(op.f("ix_code_workers_workspace_id"), table_name="code_workers")
    op.drop_table("code_workers")

    op.drop_index(op.f("ix_code_tasks_priority"), table_name="code_tasks")
    op.drop_index(op.f("ix_code_tasks_task_status"), table_name="code_tasks")
    op.drop_index(op.f("ix_code_tasks_session_id"), table_name="code_tasks")
    op.drop_index(op.f("ix_code_tasks_workspace_id"), table_name="code_tasks")
    op.drop_index(op.f("ix_code_tasks_user_id"), table_name="code_tasks")
    op.drop_index(op.f("ix_code_tasks_tenant_id"), table_name="code_tasks")
    op.drop_table("code_tasks")
