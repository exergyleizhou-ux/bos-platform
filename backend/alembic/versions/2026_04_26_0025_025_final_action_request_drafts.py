"""025 add final action request draft schema

Revision ID: 025_final_action_request_drafts
Revises: 024_final_action_review_packets
Create Date: 2026-04-26 00:42:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "025_final_action_request_drafts"
down_revision: Union[str, None] = "024_final_action_review_packets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_final_action_request_drafts_{column}"),
        "final_action_request_drafts",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "final_action_request_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("final_action_request_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=160), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("source_review_packet_id", sa.String(length=160), nullable=False),
        sa.Column("source_evidence_pack_ids", sa.JSON(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("preflight_snapshot", sa.JSON(), nullable=False),
        sa.Column("role_snapshot", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=80), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("final_action_request_id", name="uq_final_action_request_drafts_public_id"),
        sa.UniqueConstraint("tenant_id", "action_type", "idempotency_key", name="uq_final_action_request_drafts_tenant_action_idempotency"),
    )
    for column in (
        "final_action_request_id",
        "tenant_id",
        "action_type",
        "target_type",
        "target_id",
        "requested_by_user_id",
        "source_review_packet_id",
        "idempotency_key",
        "status",
        "created_at",
        "updated_at",
    ):
        _idx(column, unique=column == "final_action_request_id")


def downgrade() -> None:
    op.drop_table("final_action_request_drafts")
