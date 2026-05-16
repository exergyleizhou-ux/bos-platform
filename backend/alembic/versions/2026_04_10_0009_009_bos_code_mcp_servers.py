"""009 add BOS Code MCP server table

Revision ID: 009_bos_code_mcp_servers
Revises: 008_bos_code_branch_state
Create Date: 2026-04-10 13:10:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_bos_code_mcp_servers"
down_revision: Union[str, None] = "008_bos_code_branch_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_mcp_servers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("server_name", sa.String(length=150), nullable=False),
        sa.Column("transport", sa.String(length=50), server_default="stub", nullable=False),
        sa.Column("connection_status", sa.String(length=50), server_default="disconnected", nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "server_name", name="uq_code_mcp_servers_workspace_name"),
    )
    op.create_index(op.f("ix_code_mcp_servers_tenant_id"), "code_mcp_servers", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_code_mcp_servers_workspace_id"), "code_mcp_servers", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_mcp_servers_server_name"), "code_mcp_servers", ["server_name"], unique=False)
    op.create_index(
        op.f("ix_code_mcp_servers_connection_status"),
        "code_mcp_servers",
        ["connection_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_code_mcp_servers_connection_status"), table_name="code_mcp_servers")
    op.drop_index(op.f("ix_code_mcp_servers_server_name"), table_name="code_mcp_servers")
    op.drop_index(op.f("ix_code_mcp_servers_workspace_id"), table_name="code_mcp_servers")
    op.drop_index(op.f("ix_code_mcp_servers_tenant_id"), table_name="code_mcp_servers")
    op.drop_table("code_mcp_servers")
