"""024 add immutable final action review packet snapshots

Revision ID: 024_final_action_review_packets
Revises: 023_final_action_audit_records
Create Date: 2026-04-25 16:20:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "024_final_action_review_packets"
down_revision: Union[str, None] = "023_final_action_audit_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(column: str, unique: bool = False) -> None:
    op.create_index(
        op.f(f"ix_final_action_review_packet_snapshots_{column}"),
        "final_action_review_packet_snapshots",
        [column],
        unique=unique,
    )


def upgrade() -> None:
    op.create_table(
        "final_action_review_packet_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_review_packet_id", sa.String(length=160), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("packet_type", sa.String(length=120), nullable=False),
        sa.Column("packet_hash", sa.String(length=128), nullable=False),
        sa.Column("packet_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_pack_ids", sa.JSON(), nullable=False),
        sa.Column("generated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_review_packet_id", name="uq_final_action_review_packets_public_id"),
        sa.UniqueConstraint("tenant_id", "packet_hash", name="uq_final_action_review_packets_tenant_hash"),
    )
    for column in (
        "source_review_packet_id",
        "tenant_id",
        "packet_type",
        "packet_hash",
        "generated_by_user_id",
        "created_at",
    ):
        _idx(column, unique=column == "source_review_packet_id")


def downgrade() -> None:
    op.drop_table("final_action_review_packet_snapshots")
