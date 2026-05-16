"""032 literature value promotion requests

Revision ID: 032_literature_value_promotion_requests
Revises: 031_literature_extraction_review_drafts
Create Date: 2026-04-28 09:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "032_literature_value_promotion_requests"
down_revision: Union[str, None] = "031_literature_extraction_review_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_literature_value_promotion_requests_{column}"),
        "literature_value_promotion_requests",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "literature_value_promotion_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promotion_request_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("source_review_packet_hash", sa.String(length=128), nullable=False),
        sa.Column("review_draft_id", sa.String(length=120), nullable=False),
        sa.Column("comparison_hash", sa.String(length=128), nullable=False),
        sa.Column("raw_value", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=80), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("target_use", sa.String(length=120), nullable=False),
        sa.Column("target_scope", sa.JSON(), nullable=False),
        sa.Column("request_status", sa.String(length=80), server_default="requested", nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("side_effects", sa.JSON(), nullable=False),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promotion_request_id", name="uq_literature_value_promotion_requests_public_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "candidate_id",
            "idempotency_key",
            name="uq_literature_value_promotion_requests_tenant_candidate_idempotency",
        ),
    )
    for column in (
        "promotion_request_id",
        "tenant_id",
        "candidate_id",
        "source_review_packet_hash",
        "review_draft_id",
        "comparison_hash",
        "target_use",
        "request_status",
        "requested_by_user_id",
        "idempotency_key",
        "created_at",
        "updated_at",
    ):
        _idx(column, unique=column == "promotion_request_id")


def downgrade() -> None:
    op.drop_table("literature_value_promotion_requests")
