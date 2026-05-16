"""028 add user role grant audit records

Revision ID: 028_user_role_grant_audit_records
Revises: 027_user_role_grants
Create Date: 2026-04-26 08:55:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "028_user_role_grant_audit_records"
down_revision: Union[str, None] = "027_user_role_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str) -> None:
    op.create_index(
        op.f(f"ix_user_role_grant_audit_records_{column}"),
        "user_role_grant_audit_records",
        [column],
        unique=False,
    )


def upgrade() -> None:
    op.create_table(
        "user_role_grant_audit_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_grant_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("previous_is_active", sa.Boolean(), nullable=True),
        sa.Column("new_is_active", sa.Boolean(), nullable=True),
        sa.Column("previous_reason", sa.Text(), nullable=True),
        sa.Column("new_reason", sa.Text(), nullable=True),
        sa.Column("previous_granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("new_granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_grant_id"], ["user_role_grants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "tenant_id",
        "user_id",
        "role_grant_id",
        "actor_user_id",
        "role",
        "action",
    ):
        _idx(column)


def downgrade() -> None:
    op.drop_table("user_role_grant_audit_records")
