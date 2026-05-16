"""036 literature value release evidence links

Revision ID: 036_literature_value_release_evidence_links
Revises: 035_literature_value_runtime_activations
Create Date: 2026-04-28 12:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "036_literature_value_release_evidence_links"
down_revision: Union[str, None] = "035_literature_value_runtime_activations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_literature_value_release_evidence_links_{column}"),
        "literature_value_release_evidence_links",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "literature_value_release_evidence_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("link_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("release_decision_id", sa.Integer(), nullable=False),
        sa.Column("activation_record_id", sa.Integer(), nullable=False),
        sa.Column("activation_id", sa.String(length=120), nullable=False),
        sa.Column("overlay_id", sa.String(length=120), nullable=False),
        sa.Column("promotion_request_id", sa.String(length=120), nullable=False),
        sa.Column("approval_id", sa.String(length=120), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("link_status", sa.String(length=80), server_default="active", nullable=False),
        sa.Column("rollback_status", sa.String(length=80), server_default="none", nullable=False),
        sa.Column("activation_scope", sa.JSON(), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("source_review_packet_hash", sa.String(length=128), nullable=False),
        sa.Column("comparison_hash", sa.String(length=128), nullable=False),
        sa.Column("release_decision_before", sa.String(length=80), nullable=False),
        sa.Column("release_decision_after", sa.String(length=80), nullable=False),
        sa.Column("linked_by_user_id", sa.Integer(), nullable=False),
        sa.Column("link_notes", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("side_effects", sa.JSON(), nullable=False),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activation_record_id"], ["literature_value_runtime_activation_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["linked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["release_decision_id"], ["release_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link_id", name="uq_literature_value_release_evidence_links_public_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "release_decision_id",
            "activation_id",
            "idempotency_key",
            name="uq_literature_value_release_evidence_links_tenant_release_activation_idempotency",
        ),
    )
    for column in (
        "link_id",
        "tenant_id",
        "release_decision_id",
        "activation_record_id",
        "activation_id",
        "overlay_id",
        "promotion_request_id",
        "approval_id",
        "candidate_id",
        "link_status",
        "rollback_status",
        "scope_key",
        "source_review_packet_hash",
        "comparison_hash",
        "release_decision_before",
        "release_decision_after",
        "linked_by_user_id",
        "idempotency_key",
        "created_at",
        "updated_at",
    ):
        _idx(column, unique=column == "link_id")


def downgrade() -> None:
    op.drop_table("literature_value_release_evidence_links")
