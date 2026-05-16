"""007 add BOS Code domain tables

Revision ID: 007_bos_code_domain
Revises: 006_release_decision_explanations
Create Date: 2026-04-10 10:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_bos_code_domain"
down_revision: Union[str, None] = "006_release_decision_explanations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_workspaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("repo_root", sa.String(length=500), nullable=False),
        sa.Column("worktree_root", sa.String(length=500), nullable=False),
        sa.Column("base_branch", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("active_branch", sa.String(length=255), nullable=False),
        sa.Column("workspace_status", sa.String(length=50), server_default="ready", nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=True),
        sa.Column("head_commit", sa.String(length=64), nullable=True),
        sa.Column("dirty_state", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_code_workspaces_tenant_id"),
    )
    op.create_index(op.f("ix_code_workspaces_tenant_id"), "code_workspaces", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_code_workspaces_workspace_status"), "code_workspaces", ["workspace_status"], unique=False)
    op.create_index(op.f("ix_code_workspaces_dirty_state"), "code_workspaces", ["dirty_state"], unique=False)

    op.create_table(
        "code_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("permission_mode", sa.String(length=50), nullable=False),
        sa.Column("session_branch", sa.String(length=255), nullable=False),
        sa.Column("session_status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("verification_status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_branch"),
    )
    op.create_index(op.f("ix_code_sessions_tenant_id"), "code_sessions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_code_sessions_user_id"), "code_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_code_sessions_workspace_id"), "code_sessions", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_sessions_session_branch"), "code_sessions", ["session_branch"], unique=True)
    op.create_index(op.f("ix_code_sessions_session_status"), "code_sessions", ["session_status"], unique=False)
    op.create_index(op.f("ix_code_sessions_verification_status"), "code_sessions", ["verification_status"], unique=False)
    op.create_index(op.f("ix_code_sessions_created_at"), "code_sessions", ["created_at"], unique=False)
    op.create_index(op.f("ix_code_sessions_updated_at"), "code_sessions", ["updated_at"], unique=False)

    op.create_table(
        "code_workspace_leases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("active_session_id", sa.Integer(), nullable=True),
        sa.Column("lease_owner_user_id", sa.Integer(), nullable=True),
        sa.Column("lease_status", sa.String(length=50), server_default="available", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["active_session_id"], ["code_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lease_owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_code_workspace_leases_workspace_id"),
    )
    op.create_index(op.f("ix_code_workspace_leases_workspace_id"), "code_workspace_leases", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_workspace_leases_active_session_id"), "code_workspace_leases", ["active_session_id"], unique=False)
    op.create_index(op.f("ix_code_workspace_leases_lease_owner_user_id"), "code_workspace_leases", ["lease_owner_user_id"], unique=False)
    op.create_index(op.f("ix_code_workspace_leases_lease_status"), "code_workspace_leases", ["lease_status"], unique=False)
    op.create_index(op.f("ix_code_workspace_leases_lease_expires_at"), "code_workspace_leases", ["lease_expires_at"], unique=False)
    op.create_index(op.f("ix_code_workspace_leases_heartbeat_at"), "code_workspace_leases", ["heartbeat_at"], unique=False)

    op.create_table(
        "code_turns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("assistant_summary", sa.Text(), nullable=True),
        sa.Column("turn_status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "turn_index", name="uq_code_turns_session_turn_index"),
    )
    op.create_index(op.f("ix_code_turns_session_id"), "code_turns", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_turns_turn_status"), "code_turns", ["turn_status"], unique=False)
    op.create_index(op.f("ix_code_turns_created_at"), "code_turns", ["created_at"], unique=False)

    op.create_table(
        "code_tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Integer(), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_class", sa.String(length=100), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("was_denied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("denial_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["code_turns.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_tool_calls_session_id"), "code_tool_calls", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_tool_calls_turn_id"), "code_tool_calls", ["turn_id"], unique=False)
    op.create_index(op.f("ix_code_tool_calls_tool_name"), "code_tool_calls", ["tool_name"], unique=False)
    op.create_index(op.f("ix_code_tool_calls_tool_class"), "code_tool_calls", ["tool_class"], unique=False)
    op.create_index(op.f("ix_code_tool_calls_was_denied"), "code_tool_calls", ["was_denied"], unique=False)
    op.create_index(op.f("ix_code_tool_calls_created_at"), "code_tool_calls", ["created_at"], unique=False)

    op.create_table(
        "code_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seq_no", name="uq_code_events_session_seq_no"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_code_events_session_idempotency_key"),
    )
    op.create_index(op.f("ix_code_events_session_id"), "code_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_events_event_type"), "code_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_code_events_request_id"), "code_events", ["request_id"], unique=False)
    op.create_index(op.f("ix_code_events_created_at"), "code_events", ["created_at"], unique=False)

    op.create_table(
        "code_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=100), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=True),
        sa.Column("head_commit", sa.String(length=64), nullable=True),
        sa.Column("changed_files", sa.JSON(), nullable=True),
        sa.Column("diff_summary", sa.Text(), nullable=True),
        sa.Column("export_path", sa.String(length=500), nullable=True),
        sa.Column("verification_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_artifacts_session_id"), "code_artifacts", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_artifacts_artifact_type"), "code_artifacts", ["artifact_type"], unique=False)
    op.create_index(op.f("ix_code_artifacts_created_at"), "code_artifacts", ["created_at"], unique=False)

    op.create_table(
        "code_verification_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("verification_stage", sa.String(length=50), nullable=False),
        sa.Column("verification_status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("log_excerpt", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_verification_runs_session_id"), "code_verification_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_verification_runs_verification_stage"), "code_verification_runs", ["verification_stage"], unique=False)
    op.create_index(op.f("ix_code_verification_runs_verification_status"), "code_verification_runs", ["verification_status"], unique=False)
    op.create_index(op.f("ix_code_verification_runs_started_at"), "code_verification_runs", ["started_at"], unique=False)
    op.create_index(op.f("ix_code_verification_runs_finished_at"), "code_verification_runs", ["finished_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_verification_runs_finished_at"), table_name="code_verification_runs")
    op.drop_index(op.f("ix_code_verification_runs_started_at"), table_name="code_verification_runs")
    op.drop_index(op.f("ix_code_verification_runs_verification_status"), table_name="code_verification_runs")
    op.drop_index(op.f("ix_code_verification_runs_verification_stage"), table_name="code_verification_runs")
    op.drop_index(op.f("ix_code_verification_runs_session_id"), table_name="code_verification_runs")
    op.drop_table("code_verification_runs")

    op.drop_index(op.f("ix_code_artifacts_created_at"), table_name="code_artifacts")
    op.drop_index(op.f("ix_code_artifacts_artifact_type"), table_name="code_artifacts")
    op.drop_index(op.f("ix_code_artifacts_session_id"), table_name="code_artifacts")
    op.drop_table("code_artifacts")

    op.drop_index(op.f("ix_code_events_created_at"), table_name="code_events")
    op.drop_index(op.f("ix_code_events_request_id"), table_name="code_events")
    op.drop_index(op.f("ix_code_events_event_type"), table_name="code_events")
    op.drop_index(op.f("ix_code_events_session_id"), table_name="code_events")
    op.drop_table("code_events")

    op.drop_index(op.f("ix_code_tool_calls_created_at"), table_name="code_tool_calls")
    op.drop_index(op.f("ix_code_tool_calls_was_denied"), table_name="code_tool_calls")
    op.drop_index(op.f("ix_code_tool_calls_tool_class"), table_name="code_tool_calls")
    op.drop_index(op.f("ix_code_tool_calls_tool_name"), table_name="code_tool_calls")
    op.drop_index(op.f("ix_code_tool_calls_turn_id"), table_name="code_tool_calls")
    op.drop_index(op.f("ix_code_tool_calls_session_id"), table_name="code_tool_calls")
    op.drop_table("code_tool_calls")

    op.drop_index(op.f("ix_code_turns_created_at"), table_name="code_turns")
    op.drop_index(op.f("ix_code_turns_turn_status"), table_name="code_turns")
    op.drop_index(op.f("ix_code_turns_session_id"), table_name="code_turns")
    op.drop_table("code_turns")

    op.drop_index(op.f("ix_code_workspace_leases_heartbeat_at"), table_name="code_workspace_leases")
    op.drop_index(op.f("ix_code_workspace_leases_lease_expires_at"), table_name="code_workspace_leases")
    op.drop_index(op.f("ix_code_workspace_leases_lease_status"), table_name="code_workspace_leases")
    op.drop_index(op.f("ix_code_workspace_leases_lease_owner_user_id"), table_name="code_workspace_leases")
    op.drop_index(op.f("ix_code_workspace_leases_active_session_id"), table_name="code_workspace_leases")
    op.drop_index(op.f("ix_code_workspace_leases_workspace_id"), table_name="code_workspace_leases")
    op.drop_table("code_workspace_leases")

    op.drop_index(op.f("ix_code_sessions_updated_at"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_created_at"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_verification_status"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_session_status"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_session_branch"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_workspace_id"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_user_id"), table_name="code_sessions")
    op.drop_index(op.f("ix_code_sessions_tenant_id"), table_name="code_sessions")
    op.drop_table("code_sessions")

    op.drop_index(op.f("ix_code_workspaces_dirty_state"), table_name="code_workspaces")
    op.drop_index(op.f("ix_code_workspaces_workspace_status"), table_name="code_workspaces")
    op.drop_index(op.f("ix_code_workspaces_tenant_id"), table_name="code_workspaces")
    op.drop_table("code_workspaces")
