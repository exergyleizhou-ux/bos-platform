"""023 add final action audit record schema

Revision ID: 023_final_action_audit_records
Revises: 022_model_registry_tenant_scope
Create Date: 2026-04-25 13:35:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "023_final_action_audit_records"
down_revision: Union[str, None] = "022_model_registry_tenant_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(op.f(f"ix_final_action_audit_records_{column}"), "final_action_audit_records", [column], unique=unique)


def upgrade() -> None:
    op.create_table(
        "final_action_audit_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("final_action_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=160), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("role_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_review_packet_id", sa.String(length=160), nullable=False),
        sa.Column("source_evidence_pack_ids", sa.JSON(), nullable=False),
        sa.Column("precondition_snapshot", sa.JSON(), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=False),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("decision", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=80), server_default="requested", nullable=False),
        sa.Column("effect_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("final_action_id", name="uq_final_action_audit_records_public_id"),
        sa.UniqueConstraint("tenant_id", "action_type", "idempotency_key", name="uq_final_action_audit_tenant_action_idempotency"),
    )
    for column in (
        "final_action_id",
        "tenant_id",
        "action_type",
        "target_type",
        "target_id",
        "requested_by_user_id",
        "reviewed_by_user_id",
        "source_review_packet_id",
        "decision",
        "idempotency_key",
        "status",
        "created_at",
        "resolved_at",
    ):
        _idx(column, unique=column == "final_action_id")


def downgrade() -> None:
    op.drop_table("final_action_audit_records")
