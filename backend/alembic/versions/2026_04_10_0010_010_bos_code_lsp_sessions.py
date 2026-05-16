"""010 add BOS Code LSP session table

Revision ID: 010_bos_code_lsp_sessions
Revises: 009_bos_code_mcp_servers
Create Date: 2026-04-10 13:45:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010_bos_code_lsp_sessions"
down_revision: Union[str, None] = "009_bos_code_mcp_servers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_lsp_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=100), nullable=False),
        sa.Column("server_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="idle", nullable=False),
        sa.Column("root_uri", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "language", name="uq_code_lsp_sessions_workspace_language"),
    )
    op.create_index(op.f("ix_code_lsp_sessions_workspace_id"), "code_lsp_sessions", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_lsp_sessions_language"), "code_lsp_sessions", ["language"], unique=False)
    op.create_index(op.f("ix_code_lsp_sessions_status"), "code_lsp_sessions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_lsp_sessions_status"), table_name="code_lsp_sessions")
    op.drop_index(op.f("ix_code_lsp_sessions_language"), table_name="code_lsp_sessions")
    op.drop_index(op.f("ix_code_lsp_sessions_workspace_id"), table_name="code_lsp_sessions")
    op.drop_table("code_lsp_sessions")
