"""035 literature value runtime activations

Revision ID: 035_literature_value_runtime_activations
Revises: 034_literature_value_overlays
Create Date: 2026-04-28 11:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "035_literature_value_runtime_activations"
down_revision: Union[str, None] = "034_literature_value_overlays"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_literature_value_runtime_activation_records_{column}"),
        "literature_value_runtime_activation_records",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "literature_value_runtime_activation_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activation_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("overlay_record_id", sa.Integer(), nullable=False),
        sa.Column("overlay_id", sa.String(length=120), nullable=False),
        sa.Column("promotion_request_id", sa.String(length=120), nullable=False),
        sa.Column("approval_id", sa.String(length=120), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("activation_status", sa.String(length=80), server_default="active", nullable=False),
        sa.Column("activation_scope", sa.JSON(), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("activated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("operator_attestation", sa.Text(), nullable=False),
        sa.Column("deactivated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("side_effects", sa.JSON(), nullable=False),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deactivated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["overlay_record_id"], ["literature_value_overlay_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activation_id", name="uq_literature_value_runtime_activations_public_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "overlay_id",
            "idempotency_key",
            name="uq_literature_value_runtime_activations_tenant_overlay_idempotency",
        ),
    )
    for column in (
        "activation_id",
        "tenant_id",
        "overlay_record_id",
        "overlay_id",
        "promotion_request_id",
        "approval_id",
        "candidate_id",
        "activation_status",
        "scope_key",
        "activated_by_user_id",
        "deactivated_by_user_id",
        "deactivated_at",
        "idempotency_key",
        "created_at",
        "updated_at",
    ):
        _idx(column, unique=column == "activation_id")


def downgrade() -> None:
    op.drop_table("literature_value_runtime_activation_records")
