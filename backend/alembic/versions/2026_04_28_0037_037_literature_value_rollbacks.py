"""037 literature value rollbacks

Revision ID: 037_literature_value_rollbacks
Revises: 036_literature_value_release_evidence_links
Create Date: 2026-04-28 13:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "037_literature_value_rollbacks"
down_revision: Union[str, None] = "036_literature_value_release_evidence_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_literature_value_rollback_records_{column}"),
        "literature_value_rollback_records",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "literature_value_rollback_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rollback_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("activation_record_id", sa.Integer(), nullable=False),
        sa.Column("overlay_record_id", sa.Integer(), nullable=False),
        sa.Column("activation_id", sa.String(length=120), nullable=False),
        sa.Column("overlay_id", sa.String(length=120), nullable=False),
        sa.Column("promotion_request_id", sa.String(length=120), nullable=False),
        sa.Column("approval_id", sa.String(length=120), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("rollback_status", sa.String(length=80), server_default="completed", nullable=False),
        sa.Column("activation_status_before", sa.String(length=80), nullable=False),
        sa.Column("activation_status_after", sa.String(length=80), nullable=False),
        sa.Column("overlay_status_before", sa.String(length=80), nullable=False),
        sa.Column("overlay_status_after", sa.String(length=80), nullable=False),
        sa.Column("affected_release_evidence_link_ids", sa.JSON(), nullable=False),
        sa.Column("release_evidence_link_status_updates", sa.JSON(), nullable=False),
        sa.Column("release_decision_states", sa.JSON(), nullable=False),
        sa.Column("rolled_back_by_user_id", sa.Integer(), nullable=False),
        sa.Column("rollback_reason", sa.Text(), nullable=False),
        sa.Column("operator_attestation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("side_effects", sa.JSON(), nullable=False),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activation_record_id"], ["literature_value_runtime_activation_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["overlay_record_id"], ["literature_value_overlay_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rolled_back_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rollback_id", name="uq_literature_value_rollbacks_public_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "activation_id",
            "idempotency_key",
            name="uq_literature_value_rollbacks_tenant_activation_idempotency",
        ),
    )
    for column in (
        "rollback_id",
        "tenant_id",
        "activation_record_id",
        "overlay_record_id",
        "activation_id",
        "overlay_id",
        "promotion_request_id",
        "approval_id",
        "candidate_id",
        "rollback_status",
        "activation_status_before",
        "activation_status_after",
        "overlay_status_before",
        "overlay_status_after",
        "rolled_back_by_user_id",
        "idempotency_key",
        "created_at",
        "updated_at",
    ):
        _idx(column, unique=column == "rollback_id")


def downgrade() -> None:
    op.drop_table("literature_value_rollback_records")
