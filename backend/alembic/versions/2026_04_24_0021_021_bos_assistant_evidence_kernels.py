"""021 add BOS assistant, evidence, release, value, and compliance kernels

Revision ID: 021_bos_assistant_evidence_kernels
Revises: 020_simulation_lab_visual_observation
Create Date: 2026-04-24 10:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021_bos_assistant_evidence_kernels"
down_revision: Union[str, None] = "020_simulation_lab_visual_observation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _idx(table: str, column: str, unique: bool = False) -> None:
    op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=unique)


def upgrade() -> None:
    op.add_column("simulation_scenarios", sa.Column("evidence_sources", sa.JSON(), nullable=True))
    op.add_column("simulation_runs", sa.Column("engine_version", sa.String(length=50), server_default="simulation_lab_v2_8", nullable=False))
    op.add_column("simulation_runs", sa.Column("model_version", sa.String(length=100), nullable=True))
    op.add_column("simulation_runs", sa.Column("input_snapshot_id", sa.String(length=100), nullable=True))
    op.add_column("simulation_runs", sa.Column("input_snapshot_hash", sa.String(length=64), nullable=True))
    op.add_column("simulation_runs", sa.Column("replay_of_run_id", sa.String(length=100), nullable=True))
    op.add_column("simulation_runs", sa.Column("evidence_pack_id", sa.String(length=100), nullable=True))
    for column in ("engine_version", "model_version", "input_snapshot_id", "input_snapshot_hash", "replay_of_run_id", "evidence_pack_id"):
        _idx("simulation_runs", column)
    op.add_column("simulation_cycles", sa.Column("evidence_sources", sa.JSON(), nullable=True))

    op.create_table(
        "evidence_packs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("human_review_required", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_pack_id", name="uq_evidence_packs_public_id"),
    )
    for column in ("evidence_pack_id", "tenant_id", "user_id", "subject_type", "subject_id", "verification_status", "human_review_required", "created_at"):
        _idx("evidence_packs", column, unique=column == "evidence_pack_id")

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_item_id", sa.String(length=100), nullable=False),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("source_kind", sa.String(length=80), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("uncertainty_level", sa.String(length=50), server_default="low", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_pack_id"], ["evidence_packs.evidence_pack_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_item_id", name="uq_evidence_items_public_id"),
    )
    for column in ("evidence_item_id", "evidence_pack_id", "tenant_id", "kind", "source_kind", "uncertainty_level", "created_at"):
        _idx("evidence_items", column, unique=column == "evidence_item_id")

    op.create_table(
        "input_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("input_snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_snapshot_id", name="uq_input_snapshots_public_id"),
    )
    for column in ("input_snapshot_id", "tenant_id", "subject_type", "subject_id", "payload_hash", "created_at"):
        _idx("input_snapshots", column, unique=column == "input_snapshot_id")

    op.create_table(
        "assistant_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("parsed_intent", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_assistant_runs_public_id"),
    )
    for column in ("run_id", "tenant_id", "user_id", "status", "evidence_pack_id", "created_at", "completed_at"):
        _idx("assistant_runs", column, unique=column == "run_id")

    op.create_table(
        "assistant_tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", sa.String(length=100), nullable=False),
        sa.Column("assistant_run_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=160), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assistant_run_id"], ["assistant_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id", name="uq_assistant_tool_calls_public_id"),
    )
    for column in ("call_id", "assistant_run_id", "tenant_id", "tool_name", "status", "started_at", "completed_at"):
        _idx("assistant_tool_calls", column, unique=column == "call_id")

    op.create_table(
        "assistant_confirmation_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("confirmation_id", sa.String(length=100), nullable=False),
        sa.Column("assistant_run_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("action_name", sa.String(length=160), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assistant_run_id"], ["assistant_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("confirmation_id", name="uq_assistant_confirmation_public_id"),
    )
    for column in ("confirmation_id", "assistant_run_id", "tenant_id", "action_name", "status", "created_at", "resolved_at"):
        _idx("assistant_confirmation_requests", column, unique=column == "confirmation_id")

    op.create_table(
        "release_packet_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attachment_id", sa.String(length=100), nullable=False),
        sa.Column("release_decision_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("attachment_type", sa.String(length=80), nullable=False),
        sa.Column("simulation_id", sa.String(length=100), nullable=True),
        sa.Column("run_id", sa.String(length=100), nullable=True),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=True),
        sa.Column("appendix_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["release_decision_id"], ["release_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_id", name="uq_release_packet_attachments_public_id"),
    )
    for column in ("attachment_id", "release_decision_id", "tenant_id", "user_id", "attachment_type", "simulation_id", "run_id", "evidence_pack_id", "appendix_hash", "created_at"):
        _idx("release_packet_attachments", column, unique=column == "attachment_id")

    op.create_table(
        "human_approval_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("approval_request_id", sa.String(length=100), nullable=False),
        sa.Column("release_decision_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["release_decision_id"], ["release_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id", name="uq_human_approval_requests_public_id"),
    )
    for column in ("approval_request_id", "release_decision_id", "tenant_id", "user_id", "subject_type", "subject_id", "status", "created_at", "resolved_at"):
        _idx("human_approval_requests", column, unique=column == "approval_request_id")

    _create_json_result_tables()


def _create_json_result_tables() -> None:
    op.create_table(
        "sustainability_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("result_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("result_type", sa.String(length=50), nullable=False),
        sa.Column("functional_unit", sa.String(length=100), nullable=False),
        sa.Column("system_boundary", sa.JSON(), nullable=False),
        sa.Column("baseline_scenario", sa.JSON(), nullable=True),
        sa.Column("alternative_scenario", sa.JSON(), nullable=True),
        sa.Column("activity_data", sa.JSON(), nullable=True),
        sa.Column("emission_factors", sa.JSON(), nullable=True),
        sa.Column("cost_factors", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("uncertainty_warnings", sa.JSON(), nullable=True),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_id", name="uq_sustainability_results_public_id"),
    )
    for column in ("result_id", "tenant_id", "user_id", "result_type", "functional_unit", "evidence_pack_id", "created_at"):
        _idx("sustainability_results", column, unique=column == "result_id")

    op.create_table(
        "batch_assays",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assay_id", sa.String(length=100), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assay_type", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assay_id", name="uq_batch_assays_public_id"),
    )
    for column in ("assay_id", "batch_id", "tenant_id", "user_id", "assay_type", "created_at"):
        _idx("batch_assays", column, unique=column == "assay_id")

    op.create_table(
        "release_gates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gate_id", sa.String(length=100), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jurisdiction", sa.String(length=100), nullable=False),
        sa.Column("product_category", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("missing_assays", sa.JSON(), nullable=True),
        sa.Column("blocked_reasons", sa.JSON(), nullable=True),
        sa.Column("human_review_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gate_id", name="uq_release_gates_public_id"),
    )
    for column in ("gate_id", "batch_id", "tenant_id", "user_id", "jurisdiction", "product_category", "status", "human_review_required", "evidence_pack_id", "created_at"):
        _idx("release_gates", column, unique=column == "gate_id")

    op.create_table(
        "historical_replay_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("replay_id", sa.String(length=100), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("immutable_snapshot", sa.JSON(), nullable=False),
        sa.Column("counterfactual_actions", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.JSON(), nullable=True),
        sa.Column("evidence_pack_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_id", name="uq_historical_replay_runs_public_id"),
    )
    for column in ("replay_id", "batch_id", "tenant_id", "user_id", "evidence_pack_id", "created_at"):
        _idx("historical_replay_runs", column, unique=column == "replay_id")

    for table, public_id, columns in (
        ("benchmark_cases", "case_id", [sa.Column("tenant_id", sa.Integer(), nullable=True), sa.Column("name", sa.String(length=160), nullable=False), sa.Column("scenario_payload", sa.JSON(), nullable=False), sa.Column("expected_metrics", sa.JSON(), nullable=True)]),
        ("benchmark_runs", "benchmark_run_id", [sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("suite_name", sa.String(length=120), nullable=False), sa.Column("scorecard", sa.JSON(), nullable=False), sa.Column("evidence_pack_id", sa.String(length=100), nullable=True)]),
        ("model_registry", "model_id", [sa.Column("name", sa.String(length=160), nullable=False), sa.Column("task_type", sa.String(length=100), nullable=False), sa.Column("status", sa.String(length=50), server_default="active", nullable=False)]),
        ("model_versions", "model_version_id", [sa.Column("model_id", sa.String(length=100), nullable=False), sa.Column("version", sa.String(length=80), nullable=False), sa.Column("metadata_payload", sa.JSON(), nullable=True), sa.Column("status", sa.String(length=50), server_default="candidate", nullable=False)]),
        ("knowledge_relations", "relation_id", [sa.Column("tenant_id", sa.Integer(), nullable=True), sa.Column("subject_type", sa.String(length=100), nullable=False), sa.Column("subject_id", sa.String(length=160), nullable=False), sa.Column("predicate", sa.String(length=100), nullable=False), sa.Column("object_type", sa.String(length=100), nullable=False), sa.Column("object_id", sa.String(length=160), nullable=False), sa.Column("evidence_pack_id", sa.String(length=100), nullable=True), sa.Column("payload", sa.JSON(), nullable=True)]),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(public_id, sa.String(length=100), nullable=False),
            *columns,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(public_id, name=f"uq_{table}_public_id"),
        )
        _idx(table, public_id, unique=True)


def downgrade() -> None:
    for table in (
        "knowledge_relations",
        "model_versions",
        "model_registry",
        "benchmark_runs",
        "benchmark_cases",
        "historical_replay_runs",
        "release_gates",
        "batch_assays",
        "sustainability_results",
        "human_approval_requests",
        "release_packet_attachments",
        "assistant_confirmation_requests",
        "assistant_tool_calls",
        "assistant_runs",
        "input_snapshots",
        "evidence_items",
        "evidence_packs",
    ):
        op.drop_table(table)
    op.drop_column("simulation_cycles", "evidence_sources")
    for column in ("engine_version", "model_version", "input_snapshot_id", "input_snapshot_hash", "replay_of_run_id", "evidence_pack_id"):
        op.drop_index(op.f(f"ix_simulation_runs_{column}"), table_name="simulation_runs")
        op.drop_column("simulation_runs", column)
    op.drop_column("simulation_scenarios", "evidence_sources")
