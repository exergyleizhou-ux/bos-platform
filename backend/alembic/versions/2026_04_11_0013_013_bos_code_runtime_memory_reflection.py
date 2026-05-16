"""013 add BOS Code runtime, memory, reflection, and skills tables

Revision ID: 013_bos_code_runtime_memory_reflection
Revises: 012_bos_code_worker_events
Create Date: 2026-04-11 18:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013_bos_code_runtime_memory_reflection"
down_revision: Union[str, None] = "012_bos_code_worker_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_automation_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("job_type", sa.String(length=50), server_default="cron", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("schedule_kind", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column("cron_expr", sa.String(length=120), nullable=True),
        sa.Column("interval_sec", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=True),
        sa.Column("prompt_template", sa.Text(), nullable=True),
        sa.Column("target_scope", sa.String(length=100), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=50), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_code_automation_jobs_workspace_name"),
    )
    op.create_index(op.f("ix_code_automation_jobs_tenant_id"), "code_automation_jobs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_code_automation_jobs_workspace_id"), "code_automation_jobs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_automation_jobs_job_type"), "code_automation_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_code_automation_jobs_enabled"), "code_automation_jobs", ["enabled"], unique=False)
    op.create_index(op.f("ix_code_automation_jobs_next_run_at"), "code_automation_jobs", ["next_run_at"], unique=False)
    op.create_index(op.f("ix_code_automation_jobs_last_run_at"), "code_automation_jobs", ["last_run_at"], unique=False)
    op.create_index(op.f("ix_code_automation_jobs_last_status"), "code_automation_jobs", ["last_status"], unique=False)

    op.create_table(
        "code_agent_runtime_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("heartbeat_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("memory_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("reflections_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_heartbeat_decision", sa.String(length=50), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_memory_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reflection_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_compressed_turn_index", sa.Integer(), nullable=True),
        sa.Column("runtime_metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_code_agent_runtime_states_workspace_id"),
    )
    op.create_index(op.f("ix_code_agent_runtime_states_workspace_id"), "code_agent_runtime_states", ["workspace_id"], unique=False)

    op.create_table(
        "code_memory_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_kind", sa.String(length=50), server_default="summary", nullable=False),
        sa.Column("source_turn_start", sa.Integer(), nullable=True),
        sa.Column("source_turn_end", sa.Integer(), nullable=True),
        sa.Column("summary_markdown", sa.Text(), nullable=False),
        sa.Column("history_excerpt", sa.Text(), nullable=True),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_memory_snapshots_workspace_id"), "code_memory_snapshots", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_memory_snapshots_session_id"), "code_memory_snapshots", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_memory_snapshots_snapshot_kind"), "code_memory_snapshots", ["snapshot_kind"], unique=False)
    op.create_index(op.f("ix_code_memory_snapshots_source_turn_end"), "code_memory_snapshots", ["source_turn_end"], unique=False)
    op.create_index(op.f("ix_code_memory_snapshots_created_at"), "code_memory_snapshots", ["created_at"], unique=False)

    op.create_table(
        "code_subagent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.Integer(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("run_status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["code_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["worker_id"], ["code_workers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_subagent_runs_workspace_id"), "code_subagent_runs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_subagent_runs_session_id"), "code_subagent_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_subagent_runs_task_id"), "code_subagent_runs", ["task_id"], unique=False)
    op.create_index(op.f("ix_code_subagent_runs_worker_id"), "code_subagent_runs", ["worker_id"], unique=False)
    op.create_index(op.f("ix_code_subagent_runs_run_status"), "code_subagent_runs", ["run_status"], unique=False)

    op.create_table(
        "code_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("origin_task_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("skill_status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("directory_path", sa.String(length=500), nullable=False),
        sa.Column("latest_revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["origin_task_id"], ["code_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_code_skills_workspace_slug"),
    )
    op.create_index(op.f("ix_code_skills_tenant_id"), "code_skills", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_code_skills_workspace_id"), "code_skills", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_skills_origin_task_id"), "code_skills", ["origin_task_id"], unique=False)
    op.create_index(op.f("ix_code_skills_created_by_user_id"), "code_skills", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_code_skills_skill_status"), "code_skills", ["skill_status"], unique=False)

    op.create_table(
        "code_reflection_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("skill_id", sa.Integer(), nullable=True),
        sa.Column("trigger_source", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column("reflection_status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("output_kind", sa.String(length=50), server_default="memory_update", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["code_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["code_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["code_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["skill_id"], ["code_skills.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_reflection_runs_workspace_id"), "code_reflection_runs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_session_id"), "code_reflection_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_task_id"), "code_reflection_runs", ["task_id"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_skill_id"), "code_reflection_runs", ["skill_id"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_trigger_source"), "code_reflection_runs", ["trigger_source"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_reflection_status"), "code_reflection_runs", ["reflection_status"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_output_kind"), "code_reflection_runs", ["output_kind"], unique=False)
    op.create_index(op.f("ix_code_reflection_runs_created_at"), "code_reflection_runs", ["created_at"], unique=False)

    op.create_table(
        "code_skill_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("reflection_run_id", sa.Integer(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("supporting_files", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["code_skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reflection_run_id"], ["code_reflection_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "revision_number", name="uq_code_skill_revisions_skill_revision"),
    )
    op.create_index(op.f("ix_code_skill_revisions_skill_id"), "code_skill_revisions", ["skill_id"], unique=False)
    op.create_index(op.f("ix_code_skill_revisions_reflection_run_id"), "code_skill_revisions", ["reflection_run_id"], unique=False)
    op.create_index(op.f("ix_code_skill_revisions_revision_status"), "code_skill_revisions", ["revision_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_skill_revisions_revision_status"), table_name="code_skill_revisions")
    op.drop_index(op.f("ix_code_skill_revisions_reflection_run_id"), table_name="code_skill_revisions")
    op.drop_index(op.f("ix_code_skill_revisions_skill_id"), table_name="code_skill_revisions")
    op.drop_table("code_skill_revisions")

    op.drop_index(op.f("ix_code_reflection_runs_created_at"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_output_kind"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_reflection_status"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_trigger_source"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_skill_id"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_task_id"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_session_id"), table_name="code_reflection_runs")
    op.drop_index(op.f("ix_code_reflection_runs_workspace_id"), table_name="code_reflection_runs")
    op.drop_table("code_reflection_runs")

    op.drop_index(op.f("ix_code_skills_skill_status"), table_name="code_skills")
    op.drop_index(op.f("ix_code_skills_created_by_user_id"), table_name="code_skills")
    op.drop_index(op.f("ix_code_skills_origin_task_id"), table_name="code_skills")
    op.drop_index(op.f("ix_code_skills_workspace_id"), table_name="code_skills")
    op.drop_index(op.f("ix_code_skills_tenant_id"), table_name="code_skills")
    op.drop_table("code_skills")

    op.drop_index(op.f("ix_code_subagent_runs_run_status"), table_name="code_subagent_runs")
    op.drop_index(op.f("ix_code_subagent_runs_worker_id"), table_name="code_subagent_runs")
    op.drop_index(op.f("ix_code_subagent_runs_task_id"), table_name="code_subagent_runs")
    op.drop_index(op.f("ix_code_subagent_runs_session_id"), table_name="code_subagent_runs")
    op.drop_index(op.f("ix_code_subagent_runs_workspace_id"), table_name="code_subagent_runs")
    op.drop_table("code_subagent_runs")

    op.drop_index(op.f("ix_code_memory_snapshots_created_at"), table_name="code_memory_snapshots")
    op.drop_index(op.f("ix_code_memory_snapshots_source_turn_end"), table_name="code_memory_snapshots")
    op.drop_index(op.f("ix_code_memory_snapshots_snapshot_kind"), table_name="code_memory_snapshots")
    op.drop_index(op.f("ix_code_memory_snapshots_session_id"), table_name="code_memory_snapshots")
    op.drop_index(op.f("ix_code_memory_snapshots_workspace_id"), table_name="code_memory_snapshots")
    op.drop_table("code_memory_snapshots")

    op.drop_index(op.f("ix_code_agent_runtime_states_workspace_id"), table_name="code_agent_runtime_states")
    op.drop_table("code_agent_runtime_states")

    op.drop_index(op.f("ix_code_automation_jobs_last_status"), table_name="code_automation_jobs")
    op.drop_index(op.f("ix_code_automation_jobs_last_run_at"), table_name="code_automation_jobs")
    op.drop_index(op.f("ix_code_automation_jobs_next_run_at"), table_name="code_automation_jobs")
    op.drop_index(op.f("ix_code_automation_jobs_enabled"), table_name="code_automation_jobs")
    op.drop_index(op.f("ix_code_automation_jobs_job_type"), table_name="code_automation_jobs")
    op.drop_index(op.f("ix_code_automation_jobs_workspace_id"), table_name="code_automation_jobs")
    op.drop_index(op.f("ix_code_automation_jobs_tenant_id"), table_name="code_automation_jobs")
    op.drop_table("code_automation_jobs")
