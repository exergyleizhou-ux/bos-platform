"""030 literature extraction candidate records

Revision ID: 030_literature_extraction_candidate_records
Revises: 029_reviewed_external_candidate_foundation
Create Date: 2026-04-28 06:58:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "030_literature_extraction_candidate_records"
down_revision: Union[str, None] = "029_reviewed_external_candidate_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(table: str, column: str) -> None:
    op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        "literature_extraction_candidate_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("source_ref", sa.String(length=500), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("species", sa.String(length=160), nullable=False),
        sa.Column("feedstock", sa.String(length=160), nullable=False),
        sa.Column("treatment", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_label", sa.String(length=255), nullable=False),
        sa.Column("raw_value", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=80), nullable=False),
        sa.Column("condition_context", sa.Text(), nullable=False),
        sa.Column("experiment_context", sa.Text(), nullable=False),
        sa.Column("table_or_section_ref", sa.Text(), nullable=False),
        sa.Column("extraction_note", sa.Text(), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=80), server_default="peer_reviewed_literature", nullable=False),
        sa.Column("review_status", sa.String(length=80), server_default="pending_review", nullable=False),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("numeric_values_included", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("release_evidence_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("runtime_activation_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("validated_default_write_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("promotion_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("guardrails", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["external_source_records.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "candidate_id", name="uq_literature_extraction_candidates_tenant_candidate"),
    )
    for column in (
        "tenant_id",
        "candidate_id",
        "source_id",
        "doi",
        "species",
        "feedstock",
        "metric_key",
        "source_kind",
        "review_status",
        "human_review_required",
        "created_at",
    ):
        _idx("literature_extraction_candidate_records", column)


def downgrade() -> None:
    op.drop_table("literature_extraction_candidate_records")
