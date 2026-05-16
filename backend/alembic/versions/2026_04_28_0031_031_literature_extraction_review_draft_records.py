"""031 literature extraction review draft records

Revision ID: 031_literature_extraction_review_drafts
Revises: 030_literature_extraction_candidate_records
Create Date: 2026-04-28 07:45:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "031_literature_extraction_review_drafts"
down_revision: Union[str, None] = "030_literature_extraction_candidate_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_literature_extraction_review_draft_records_{column}"),
        "literature_extraction_review_draft_records",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "literature_extraction_review_draft_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_draft_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("review_intent", sa.String(length=80), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=False),
        sa.Column("source_review_packet_export_id", sa.String(length=180), nullable=False),
        sa.Column("source_review_packet_hash", sa.String(length=128), nullable=False),
        sa.Column("candidate_snapshot", sa.JSON(), nullable=False),
        sa.Column("export_manifest", sa.JSON(), nullable=False),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False),
        sa.Column("side_effects", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=80), server_default="draft_intent_recorded", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["external_source_records.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_draft_id", name="uq_literature_extraction_review_drafts_public_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "candidate_id",
            "idempotency_key",
            name="uq_literature_extraction_review_drafts_tenant_candidate_idempotency",
        ),
    )
    for column in (
        "review_draft_id",
        "tenant_id",
        "candidate_id",
        "source_id",
        "reviewer_user_id",
        "review_intent",
        "source_review_packet_export_id",
        "source_review_packet_hash",
        "idempotency_key",
        "status",
        "created_at",
        "updated_at",
    ):
        _idx(column, unique=column == "review_draft_id")


def downgrade() -> None:
    op.drop_table("literature_extraction_review_draft_records")
