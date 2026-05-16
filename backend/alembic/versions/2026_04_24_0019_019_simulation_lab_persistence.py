"""019 add simulation lab persistence tables

Revision ID: 019_simulation_lab_persistence
Revises: 018_wechat_official_accounts
Create Date: 2026-04-24 08:45:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019_simulation_lab_persistence"
down_revision: Union[str, None] = "018_wechat_official_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_scenarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulation_id", sa.String(length=100), nullable=False),
        sa.Column("batch_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("species", sa.String(length=80), nullable=False),
        sa.Column("feedstock", sa.String(length=120), nullable=False),
        sa.Column("scenario", sa.String(length=50), nullable=False),
        sa.Column("initial_state", sa.JSON(), nullable=False),
        sa.Column("cycles", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("policy", sa.String(length=50), server_default="rule_based", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulation_id", name="uq_simulation_scenarios_simulation_id"),
    )
    for column in ("simulation_id", "batch_id", "tenant_id", "user_id", "species", "feedstock", "scenario", "policy", "status", "created_at"):
        op.create_index(op.f(f"ix_simulation_scenarios_{column}"), "simulation_scenarios", [column], unique=column == "simulation_id")

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("simulation_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("policy", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="completed", nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["simulation_scenarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_simulation_runs_run_id"),
    )
    for column in ("run_id", "scenario_id", "simulation_id", "tenant_id", "user_id", "policy", "status", "started_at", "completed_at", "created_at"):
        op.create_index(op.f(f"ix_simulation_runs_{column}"), "simulation_runs", [column], unique=column == "run_id")

    op.create_table(
        "simulation_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("simulation_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_before", sa.JSON(), nullable=False),
        sa.Column("sensor_observation", sa.JSON(), nullable=False),
        sa.Column("supervisor_decision", sa.JSON(), nullable=False),
        sa.Column("risk_prediction", sa.JSON(), nullable=False),
        sa.Column("agent_action", sa.JSON(), nullable=False),
        sa.Column("actuator_result", sa.JSON(), nullable=False),
        sa.Column("state_after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "cycle_index", name="uq_simulation_cycles_run_cycle"),
    )
    for column in ("run_id", "simulation_id", "tenant_id", "cycle_index", "timestamp", "created_at"):
        op.create_index(op.f(f"ix_simulation_cycles_{column}"), "simulation_cycles", [column], unique=False)

    op.create_table(
        "simulation_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=True),
        sa.Column("simulation_id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("evidence_chain", sa.JSON(), nullable=True),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["simulation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("run_id", "cycle_id", "simulation_id", "tenant_id", "cycle_index", "event_type", "payload_hash", "recorded_at", "created_at"):
        op.create_index(op.f(f"ix_simulation_audit_events_{column}"), "simulation_audit_events", [column], unique=False)


def downgrade() -> None:
    for column in ("run_id", "cycle_id", "simulation_id", "tenant_id", "cycle_index", "event_type", "payload_hash", "recorded_at", "created_at"):
        op.drop_index(op.f(f"ix_simulation_audit_events_{column}"), table_name="simulation_audit_events")
    op.drop_table("simulation_audit_events")

    for column in ("run_id", "simulation_id", "tenant_id", "cycle_index", "timestamp", "created_at"):
        op.drop_index(op.f(f"ix_simulation_cycles_{column}"), table_name="simulation_cycles")
    op.drop_table("simulation_cycles")

    for column in ("run_id", "scenario_id", "simulation_id", "tenant_id", "user_id", "policy", "status", "started_at", "completed_at", "created_at"):
        op.drop_index(op.f(f"ix_simulation_runs_{column}"), table_name="simulation_runs")
    op.drop_table("simulation_runs")

    for column in ("simulation_id", "batch_id", "tenant_id", "user_id", "species", "feedstock", "scenario", "policy", "status", "created_at"):
        op.drop_index(op.f(f"ix_simulation_scenarios_{column}"), table_name="simulation_scenarios")
    op.drop_table("simulation_scenarios")
