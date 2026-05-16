"""005 add BOS protocol-first objects

Revision ID: 005_bos_protocol_objects
Revises: 004_digital_twins
Create Date: 2024-04-01 00:05:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_bos_protocol_objects"
down_revision: Union[str, None] = "004_digital_twins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    timestamp_default = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "signal_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("signal_api_version", sa.String(length=50), nullable=False, server_default="SIG-1.0"),
        sa.Column("compiled_signal_id", sa.String(length=100), nullable=True),
        sa.Column("potency", sa.Float(), nullable=True),
        sa.Column("potency_unit", sa.String(length=50), nullable=True),
        sa.Column("potency_basis", sa.String(length=100), nullable=True),
        sa.Column("dose_window_min", sa.Float(), nullable=True),
        sa.Column("dose_window_max", sa.Float(), nullable=True),
        sa.Column("stability_window_hours", sa.Float(), nullable=True),
        sa.Column("kernel_residence_time_hours", sa.Float(), nullable=True),
        sa.Column("handover_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_state", sa.String(length=50), nullable=True),
        sa.Column("qc_markers", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_batches_batch_id", "signal_batches", ["batch_id"])
    op.create_index("ix_signal_batches_user_id", "signal_batches", ["user_id"])
    op.create_index("ix_signal_batches_tenant_id", "signal_batches", ["tenant_id"])
    op.create_index("ix_signal_batches_signal_api_version", "signal_batches", ["signal_api_version"])
    op.create_index("ix_signal_batches_compiled_signal_id", "signal_batches", ["compiled_signal_id"])
    op.create_index("ix_signal_batches_freshness_state", "signal_batches", ["freshness_state"])
    op.create_index("ix_signal_batches_created_at", "signal_batches", ["created_at"])

    op.create_table(
        "control_api_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("hal_min", sa.Float(), nullable=True),
        sa.Column("hal_max", sa.Float(), nullable=True),
        sa.Column("mtt", sa.Float(), nullable=True),
        sa.Column("dose_window_min", sa.Float(), nullable=True),
        sa.Column("dose_window_max", sa.Float(), nullable=True),
        sa.Column("stability_window_hours", sa.Float(), nullable=True),
        sa.Column("dwell_time_min_hours", sa.Float(), nullable=True),
        sa.Column("dwell_time_max_hours", sa.Float(), nullable=True),
        sa.Column("qc_thresholds", sa.JSON(), nullable=True),
        sa.Column("release_rules", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_control_api_profile_version"),
    )
    op.create_index("ix_control_api_profiles_tenant_id", "control_api_profiles", ["tenant_id"])
    op.create_index("ix_control_api_profiles_user_id", "control_api_profiles", ["user_id"])
    op.create_index("ix_control_api_profiles_version", "control_api_profiles", ["version"])
    op.create_index("ix_control_api_profiles_active", "control_api_profiles", ["active"])
    op.create_index("ix_control_api_profiles_created_at", "control_api_profiles", ["created_at"])

    op.create_table(
        "locality_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("site_code", sa.String(length=100), nullable=True),
        sa.Column("substrate_class", sa.String(length=100), nullable=True),
        sa.Column("waste_state", sa.JSON(), nullable=True),
        sa.Column("pretreat_flags", sa.JSON(), nullable=True),
        sa.Column("dose_window_shift_pct", sa.Float(), nullable=True),
        sa.Column("mtt_shift_pct", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_locality_profiles_tenant_id", "locality_profiles", ["tenant_id"])
    op.create_index("ix_locality_profiles_user_id", "locality_profiles", ["user_id"])
    op.create_index("ix_locality_profiles_site_code", "locality_profiles", ["site_code"])
    op.create_index("ix_locality_profiles_active", "locality_profiles", ["active"])
    op.create_index("ix_locality_profiles_created_at", "locality_profiles", ["created_at"])

    op.create_table(
        "executor_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("locality_profile_id", sa.Integer(), nullable=True),
        sa.Column("executor_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("executor_type", sa.String(length=100), nullable=True),
        sa.Column("hal_min", sa.Float(), nullable=True),
        sa.Column("hal_max", sa.Float(), nullable=True),
        sa.Column("mtt_nominal", sa.Float(), nullable=True),
        sa.Column("plugin_mode", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locality_profile_id"], ["locality_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "executor_code", name="uq_executor_profile_code"),
    )
    op.create_index("ix_executor_profiles_tenant_id", "executor_profiles", ["tenant_id"])
    op.create_index("ix_executor_profiles_user_id", "executor_profiles", ["user_id"])
    op.create_index("ix_executor_profiles_locality_profile_id", "executor_profiles", ["locality_profile_id"])
    op.create_index("ix_executor_profiles_executor_code", "executor_profiles", ["executor_code"])
    op.create_index("ix_executor_profiles_active", "executor_profiles", ["active"])
    op.create_index("ix_executor_profiles_created_at", "executor_profiles", ["created_at"])

    op.create_table(
        "boundary_ledgers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("signal_batch_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("d_prime", sa.Float(), nullable=True),
        sa.Column("g_prime", sa.Float(), nullable=True),
        sa.Column("ser_value", sa.Float(), nullable=True),
        sa.Column("delta_delta_ser", sa.Float(), nullable=True),
        sa.Column("closure_residual", sa.Float(), nullable=True),
        sa.Column("metering_completeness", sa.Float(), nullable=True),
        sa.Column("qc_flags", sa.JSON(), nullable=True),
        sa.Column("measured_vs_estimated", sa.JSON(), nullable=True),
        sa.Column("evidence_level", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_batch_id"], ["signal_batches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_boundary_ledgers_batch_id", "boundary_ledgers", ["batch_id"])
    op.create_index("ix_boundary_ledgers_signal_batch_id", "boundary_ledgers", ["signal_batch_id"])
    op.create_index("ix_boundary_ledgers_user_id", "boundary_ledgers", ["user_id"])
    op.create_index("ix_boundary_ledgers_tenant_id", "boundary_ledgers", ["tenant_id"])
    op.create_index("ix_boundary_ledgers_evidence_level", "boundary_ledgers", ["evidence_level"])
    op.create_index("ix_boundary_ledgers_created_at", "boundary_ledgers", ["created_at"])

    op.create_table(
        "release_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("signal_batch_id", sa.Integer(), nullable=True),
        sa.Column("boundary_ledger_id", sa.Integer(), nullable=True),
        sa.Column("control_profile_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=True),
        sa.Column("trigger_metrics", sa.JSON(), nullable=True),
        sa.Column("approver", sa.String(length=255), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("decision_time", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_batch_id"], ["signal_batches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["boundary_ledger_id"], ["boundary_ledgers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["control_profile_id"], ["control_api_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_decisions_batch_id", "release_decisions", ["batch_id"])
    op.create_index("ix_release_decisions_signal_batch_id", "release_decisions", ["signal_batch_id"])
    op.create_index("ix_release_decisions_boundary_ledger_id", "release_decisions", ["boundary_ledger_id"])
    op.create_index("ix_release_decisions_control_profile_id", "release_decisions", ["control_profile_id"])
    op.create_index("ix_release_decisions_user_id", "release_decisions", ["user_id"])
    op.create_index("ix_release_decisions_tenant_id", "release_decisions", ["tenant_id"])
    op.create_index("ix_release_decisions_decision", "release_decisions", ["decision"])
    op.create_index("ix_release_decisions_decision_time", "release_decisions", ["decision_time"])
    op.create_index("ix_release_decisions_created_at", "release_decisions", ["created_at"])

    op.create_table(
        "portability_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_batch_id", sa.Integer(), nullable=False),
        sa.Column("executor_profile_id", sa.Integer(), nullable=False),
        sa.Column("locality_profile_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("retuning_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("trigger_metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["signal_batch_id"], ["signal_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["executor_profile_id"], ["executor_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locality_profile_id"], ["locality_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portability_audits_signal_batch_id", "portability_audits", ["signal_batch_id"])
    op.create_index("ix_portability_audits_executor_profile_id", "portability_audits", ["executor_profile_id"])
    op.create_index("ix_portability_audits_locality_profile_id", "portability_audits", ["locality_profile_id"])
    op.create_index("ix_portability_audits_user_id", "portability_audits", ["user_id"])
    op.create_index("ix_portability_audits_tenant_id", "portability_audits", ["tenant_id"])
    op.create_index("ix_portability_audits_outcome", "portability_audits", ["outcome"])
    op.create_index("ix_portability_audits_retuning_required", "portability_audits", ["retuning_required"])
    op.create_index("ix_portability_audits_created_at", "portability_audits", ["created_at"])

    op.create_table(
        "audit_packets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("release_decision_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("packet_version", sa.String(length=50), nullable=False, server_default="AUD-1.0"),
        sa.Column("evidence_level", sa.String(length=50), nullable=True),
        sa.Column("packet", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_decision_id"], ["release_decisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_packets_batch_id", "audit_packets", ["batch_id"])
    op.create_index("ix_audit_packets_release_decision_id", "audit_packets", ["release_decision_id"])
    op.create_index("ix_audit_packets_user_id", "audit_packets", ["user_id"])
    op.create_index("ix_audit_packets_tenant_id", "audit_packets", ["tenant_id"])
    op.create_index("ix_audit_packets_packet_version", "audit_packets", ["packet_version"])
    op.create_index("ix_audit_packets_evidence_level", "audit_packets", ["evidence_level"])
    op.create_index("ix_audit_packets_generated_at", "audit_packets", ["generated_at"])
    op.create_index("ix_audit_packets_created_at", "audit_packets", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_packets")
    op.drop_table("portability_audits")
    op.drop_table("release_decisions")
    op.drop_table("boundary_ledgers")
    op.drop_table("executor_profiles")
    op.drop_table("locality_profiles")
    op.drop_table("control_api_profiles")
    op.drop_table("signal_batches")
