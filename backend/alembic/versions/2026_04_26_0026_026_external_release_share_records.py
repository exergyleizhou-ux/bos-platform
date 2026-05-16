"""026 add external release share records

Revision ID: 026_external_release_share_records
Revises: 025_final_action_request_drafts
Create Date: 2026-04-26 01:20:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "026_external_release_share_records"
down_revision: Union[str, None] = "025_final_action_request_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_external_release_share_records_{column}"),
        "external_release_share_records",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "external_release_share_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("share_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("release_decision_id", sa.Integer(), nullable=False),
        sa.Column("release_packet_attachment_id", sa.String(length=100), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_scope", sa.String(length=160), nullable=False),
        sa.Column("redaction_policy_id", sa.String(length=160), nullable=False),
        sa.Column("source_review_packet_id", sa.String(length=160), nullable=False),
        sa.Column("final_action_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=80), server_default="prepared_internal_share", nullable=False),
        sa.Column("delivery_status", sa.String(length=80), server_default="not_sent", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["release_decision_id"], ["release_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_id", name="uq_external_release_share_records_public_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_external_release_share_tenant_idempotency"),
    )
    for column in (
        "share_id",
        "tenant_id",
        "release_decision_id",
        "release_packet_attachment_id",
        "requested_by_user_id",
        "reviewed_by_user_id",
        "recipient_scope",
        "redaction_policy_id",
        "source_review_packet_id",
        "final_action_id",
        "idempotency_key",
        "status",
        "delivery_status",
        "created_at",
    ):
        _idx(column, unique=column == "share_id")


def downgrade() -> None:
    op.drop_table("external_release_share_records")
