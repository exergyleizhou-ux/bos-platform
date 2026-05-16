"""029 reviewed external candidate foundation

Revision ID: 029_reviewed_external_candidate_foundation
Revises: 028_user_role_grant_audit_records
Create Date: 2026-04-27 00:20:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029_reviewed_external_candidate_foundation"
down_revision: Union[str, None] = "028_user_role_grant_audit_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(table: str, column: str) -> None:
    op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        "external_source_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=500), nullable=False),
        sa.Column("source_owner", sa.String(length=255), nullable=True),
        sa.Column("source_category", sa.String(length=120), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("bos_module", sa.String(length=160), nullable=True),
        sa.Column("evidence_source_kind", sa.String(length=80), nullable=False),
        sa.Column("ingestion_mode", sa.String(length=80), nullable=False),
        sa.Column("auto_ingestion_note", sa.Text(), nullable=True),
        sa.Column("human_review_note", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", name="uq_external_source_records_source_id"),
    )
    for column in ("source_id", "source_category", "bos_module", "evidence_source_kind", "ingestion_mode", "created_at"):
        _idx("external_source_records", column)

    op.create_table(
        "external_source_review_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.String(length=100), nullable=False),
        sa.Column("shortlist_id", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=80), server_default="pending_review", nullable=False),
        sa.Column("reviewer", sa.String(length=255), server_default="unassigned", nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_status", sa.String(length=80), server_default="pending_review", nullable=False),
        sa.Column("evidence_source_kind", sa.String(length=80), nullable=False),
        sa.Column("ingestion_mode", sa.String(length=80), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("extracted_numeric_values_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("boundary_condition_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("allowed_use", sa.Text(), nullable=False),
        sa.Column("blocked_use", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("boundary_metadata", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["external_source_records.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "card_id", name="uq_external_source_review_cards_tenant_card"),
    )
    for column in (
        "tenant_id",
        "card_id",
        "shortlist_id",
        "source_id",
        "doi",
        "review_status",
        "reviewer_user_id",
        "reviewed_at",
        "license_status",
        "evidence_source_kind",
        "ingestion_mode",
        "human_review_required",
        "created_at",
    ):
        _idx("external_source_review_cards", column)

    op.create_table(
        "external_source_extraction_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("extraction_id", sa.String(length=120), nullable=False),
        sa.Column("review_card_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("extraction_status", sa.String(length=80), server_default="staged_metadata_only", nullable=False),
        sa.Column("extracted_metadata", sa.JSON(), nullable=False),
        sa.Column("extracted_numeric_values", sa.JSON(), nullable=False),
        sa.Column("numeric_values_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("boundary_metadata", sa.JSON(), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["review_card_id"], ["external_source_review_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "extraction_id", name="uq_external_source_extractions_tenant_extraction"),
    )
    for column in (
        "tenant_id",
        "extraction_id",
        "review_card_id",
        "card_id",
        "source_id",
        "extraction_status",
        "human_review_required",
        "created_at",
    ):
        _idx("external_source_extraction_records", column)

    op.create_table(
        "reviewed_external_candidate_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=120), nullable=False),
        sa.Column("candidate_type", sa.String(length=120), nullable=False),
        sa.Column("candidate_key", sa.String(length=160), nullable=False),
        sa.Column("review_card_id", sa.Integer(), nullable=False),
        sa.Column("extraction_id", sa.Integer(), nullable=True),
        sa.Column("card_id", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("source_kind", sa.String(length=80), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("license_status", sa.String(length=80), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("ingestion_mode", sa.String(length=80), nullable=False),
        sa.Column("review_status", sa.String(length=80), server_default="approved_for_candidate_use", nullable=False),
        sa.Column("reviewer", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("boundary_condition", sa.Text(), nullable=False),
        sa.Column("allowed_use", sa.Text(), nullable=False),
        sa.Column("blocked_use", sa.Text(), nullable=False),
        sa.Column("candidate_payload", sa.JSON(), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("promotion_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("runtime_activated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("validated_default_write_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("activation_relation_id", sa.String(length=100), nullable=True),
        sa.Column("audit_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["extraction_id"], ["external_source_extraction_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_card_id"], ["external_source_review_cards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "candidate_id", name="uq_reviewed_external_candidates_tenant_candidate"),
        sa.UniqueConstraint("tenant_id", "card_id", name="uq_reviewed_external_candidates_tenant_card"),
    )
    for column in (
        "tenant_id",
        "candidate_id",
        "candidate_type",
        "candidate_key",
        "review_card_id",
        "extraction_id",
        "card_id",
        "source_id",
        "source_kind",
        "license_status",
        "ingestion_mode",
        "review_status",
        "reviewed_at",
        "human_review_required",
        "runtime_activated",
        "activation_relation_id",
        "created_at",
    ):
        _idx("reviewed_external_candidate_records", column)


def downgrade() -> None:
    op.drop_table("reviewed_external_candidate_records")
    op.drop_table("external_source_extraction_records")
    op.drop_table("external_source_review_cards")
    op.drop_table("external_source_records")
