"""027 add tenant-scoped user role grants

Revision ID: 027_user_role_grants
Revises: 026_external_release_share_records
Create Date: 2026-04-26 02:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027_user_role_grants"
down_revision: Union[str, None] = "026_external_release_share_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str) -> None:
    op.create_index(
        op.f(f"ix_user_role_grants_{column}"),
        "user_role_grants",
        [column],
        unique=False,
    )


def upgrade() -> None:
    op.create_table(
        "user_role_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "role", name="uq_user_role_grants_tenant_user_role"),
    )
    for column in (
        "tenant_id",
        "user_id",
        "role",
        "granted_by_user_id",
        "is_active",
    ):
        _idx(column)


def downgrade() -> None:
    op.drop_table("user_role_grants")
