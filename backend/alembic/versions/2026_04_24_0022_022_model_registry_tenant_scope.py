"""022 scope model registry to tenants

Revision ID: 022_model_registry_tenant_scope
Revises: 021_bos_assistant_evidence_kernels
Create Date: 2026-04-24 12:35:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "022_model_registry_tenant_scope"
down_revision: Union[str, None] = "021_bos_assistant_evidence_kernels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("model_registry", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("model_registry", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_model_registry_tenant_id_tenants",
        "model_registry",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_model_registry_user_id_users",
        "model_registry",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_model_registry_tenant_id"), "model_registry", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_model_registry_user_id"), "model_registry", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_model_registry_user_id"), table_name="model_registry")
    op.drop_index(op.f("ix_model_registry_tenant_id"), table_name="model_registry")
    op.drop_constraint("fk_model_registry_user_id_users", "model_registry", type_="foreignkey")
    op.drop_constraint("fk_model_registry_tenant_id_tenants", "model_registry", type_="foreignkey")
    op.drop_column("model_registry", "user_id")
    op.drop_column("model_registry", "tenant_id")
