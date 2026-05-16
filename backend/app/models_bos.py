"""
BOS protocol ORM models.

These models back the protocol-first BOS surfaces exposed by the frontend.
The table definitions intentionally match the currently migrated schema.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003 - required for SQLAlchemy mapped annotation resolution

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SignalBatch(Base):
    __tablename__ = "signal_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_api_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="SIG-1.0", index=True)
    compiled_signal_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    potency: Mapped[float | None] = mapped_column(Float, nullable=True)
    potency_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    potency_basis: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dose_window_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    dose_window_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    stability_window_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    kernel_residence_time_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    handover_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    qc_markers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    batch = relationship("Batch")
    user = relationship("User")
    tenant = relationship("Tenant")


class ControlAPIProfile(Base):
    __tablename__ = "control_api_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", "version", name="uq_control_api_profile_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    hal_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    hal_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtt: Mapped[float | None] = mapped_column(Float, nullable=True)
    dose_window_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    dose_window_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    stability_window_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    dwell_time_min_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    dwell_time_max_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    qc_thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    release_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    tenant = relationship("Tenant")


class LocalityProfile(Base):
    __tablename__ = "locality_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    site_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    substrate_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    waste_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pretreat_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dose_window_shift_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtt_shift_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    tenant = relationship("Tenant")


class ExecutorProfile(Base):
    __tablename__ = "executor_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "executor_code", name="uq_executor_profile_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    locality_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("locality_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    executor_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    executor_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hal_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    hal_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtt_nominal: Mapped[float | None] = mapped_column(Float, nullable=True)
    plugin_mode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    tenant = relationship("Tenant")
    locality_profile = relationship("LocalityProfile")


class BoundaryLedger(Base):
    __tablename__ = "boundary_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_batch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("signal_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    d_prime: Mapped[float | None] = mapped_column(Float, nullable=True)
    g_prime: Mapped[float | None] = mapped_column(Float, nullable=True)
    ser_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_delta_ser: Mapped[float | None] = mapped_column(Float, nullable=True)
    closure_residual: Mapped[float | None] = mapped_column(Float, nullable=True)
    metering_completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    qc_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    measured_vs_estimated: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_level: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    batch = relationship("Batch")
    signal_batch = relationship("SignalBatch")
    user = relationship("User")
    tenant = relationship("Tenant")


class ReleaseDecision(Base):
    __tablename__ = "release_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_batch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("signal_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    boundary_ledger_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("boundary_ledgers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    control_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("control_api_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    trigger_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    blocking_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    warning_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    passed_checks: Mapped[list | None] = mapped_column(JSON, nullable=True)

    batch = relationship("Batch")
    signal_batch = relationship("SignalBatch")
    boundary_ledger = relationship("BoundaryLedger")
    control_profile = relationship("ControlAPIProfile")
    user = relationship("User")
    tenant = relationship("Tenant")


class PortabilityAudit(Base):
    __tablename__ = "portability_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signal_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    executor_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("executor_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locality_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("locality_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    retuning_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    signal_batch = relationship("SignalBatch")
    executor_profile = relationship("ExecutorProfile")
    locality_profile = relationship("LocalityProfile")
    user = relationship("User")
    tenant = relationship("Tenant")


class AuditPacket(Base):
    __tablename__ = "audit_packets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    release_decision_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("release_decisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    packet_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="AUD-1.0", index=True)
    evidence_level: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    packet: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    batch = relationship("Batch")
    release_decision = relationship("ReleaseDecision")
    user = relationship("User")
    tenant = relationship("Tenant")


class SimulationScenarioRecord(Base):
    __tablename__ = "simulation_scenarios"
    __table_args__ = (UniqueConstraint("simulation_id", name="uq_simulation_scenarios_simulation_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    species: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    feedstock: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    initial_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    cycles: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    policy: Mapped[str] = mapped_column(String(50), nullable=False, server_default="rule_based", index=True)
    evidence_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    tenant = relationship("Tenant")
    runs = relationship("SimulationRunRecord", back_populates="scenario_record", cascade="all, delete-orphan")


class SimulationRunRecord(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (UniqueConstraint("run_id", name="uq_simulation_runs_run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    simulation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    policy: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="completed", index=True)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="simulation_lab_v2_8", index=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    input_snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    input_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    replay_of_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    scenario_record = relationship("SimulationScenarioRecord", back_populates="runs")
    user = relationship("User")
    tenant = relationship("Tenant")
    cycles = relationship("SimulationCycleRecord", back_populates="run_record", cascade="all, delete-orphan")
    audit_events = relationship("SimulationAuditEventRecord", back_populates="run_record", cascade="all, delete-orphan")


class SimulationCycleRecord(Base):
    __tablename__ = "simulation_cycles"
    __table_args__ = (UniqueConstraint("run_id", "cycle_index", name="uq_simulation_cycles_run_cycle"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    simulation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    state_before: Mapped[dict] = mapped_column(JSON, nullable=False)
    sensor_observation: Mapped[dict] = mapped_column(JSON, nullable=False)
    supervisor_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_prediction: Mapped[dict] = mapped_column(JSON, nullable=False)
    visual_observation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    agent_action: Mapped[dict] = mapped_column(JSON, nullable=False)
    actuator_result: Mapped[dict] = mapped_column(JSON, nullable=False)
    state_after: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    run_record = relationship("SimulationRunRecord", back_populates="cycles")
    tenant = relationship("Tenant")


class SimulationAuditEventRecord(Base):
    __tablename__ = "simulation_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("simulation_cycles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    simulation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_index: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    evidence_chain: Mapped[list | None] = mapped_column(JSON, nullable=True)
    event_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    run_record = relationship("SimulationRunRecord", back_populates="audit_events")
    cycle = relationship("SimulationCycleRecord")
    tenant = relationship("Tenant")


class EvidencePackRecord(Base):
    __tablename__ = "evidence_packs"
    __table_args__ = (UniqueConstraint("evidence_pack_id", name="uq_evidence_packs_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_pack_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="created", index=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant = relationship("Tenant")
    user = relationship("User")
    items = relationship("EvidenceItemRecord", back_populates="pack", cascade="all, delete-orphan")


class EvidenceItemRecord(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("evidence_item_id", name="uq_evidence_items_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    evidence_pack_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("evidence_packs.evidence_pack_id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    uncertainty_level: Mapped[str] = mapped_column(String(50), nullable=False, server_default="low", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    pack = relationship("EvidencePackRecord", back_populates="items")
    tenant = relationship("Tenant")


class InputSnapshotRecord(Base):
    __tablename__ = "input_snapshots"
    __table_args__ = (UniqueConstraint("input_snapshot_id", name="uq_input_snapshots_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    input_snapshot_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant = relationship("Tenant")


class AssistantRunRecord(Base):
    __tablename__ = "assistant_runs"
    __table_args__ = (UniqueConstraint("run_id", name="uq_assistant_runs_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="created", index=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    tenant = relationship("Tenant")
    user = relationship("User")
    tool_calls = relationship("AssistantToolCallRecord", back_populates="assistant_run", cascade="all, delete-orphan")
    confirmation_requests = relationship(
        "AssistantConfirmationRequestRecord", back_populates="assistant_run", cascade="all, delete-orphan"
    )


class AssistantToolCallRecord(Base):
    __tablename__ = "assistant_tool_calls"
    __table_args__ = (UniqueConstraint("call_id", name="uq_assistant_tool_calls_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    assistant_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assistant_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    assistant_run = relationship("AssistantRunRecord", back_populates="tool_calls")
    tenant = relationship("Tenant")


class AssistantConfirmationRequestRecord(Base):
    __tablename__ = "assistant_confirmation_requests"
    __table_args__ = (UniqueConstraint("confirmation_id", name="uq_assistant_confirmation_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    confirmation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    assistant_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assistant_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    action_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    action_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    assistant_run = relationship("AssistantRunRecord", back_populates="confirmation_requests")
    tenant = relationship("Tenant")


class ReleasePacketAttachmentRecord(Base):
    __tablename__ = "release_packet_attachments"
    __table_args__ = (UniqueConstraint("attachment_id", name="uq_release_packet_attachments_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attachment_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    release_decision_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("release_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    simulation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    appendix_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    release_decision = relationship("ReleaseDecision")
    tenant = relationship("Tenant")
    user = relationship("User")


class HumanApprovalRequestRecord(Base):
    __tablename__ = "human_approval_requests"
    __table_args__ = (UniqueConstraint("approval_request_id", name="uq_human_approval_requests_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    release_decision_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("release_decisions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    release_decision = relationship("ReleaseDecision")
    tenant = relationship("Tenant")
    user = relationship("User")


class SustainabilityResultRecord(Base):
    __tablename__ = "sustainability_results"
    __table_args__ = (UniqueConstraint("result_id", name="uq_sustainability_results_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    result_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    functional_unit: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    system_boundary: Mapped[dict] = mapped_column(JSON, nullable=False)
    baseline_scenario: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alternative_scenario: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    activity_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    emission_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    uncertainty_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant = relationship("Tenant")
    user = relationship("User")


class BatchAssayRecord(Base):
    __tablename__ = "batch_assays"
    __table_args__ = (UniqueConstraint("assay_id", name="uq_batch_assays_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assay_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assay_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    batch = relationship("Batch")
    tenant = relationship("Tenant")
    user = relationship("User")


class ReleaseGateRecord(Base):
    __tablename__ = "release_gates"
    __table_args__ = (UniqueConstraint("gate_id", name="uq_release_gates_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gate_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    missing_assays: Mapped[list | None] = mapped_column(JSON, nullable=True)
    blocked_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    batch = relationship("Batch")
    tenant = relationship("Tenant")
    user = relationship("User")


class HistoricalReplayRunRecord(Base):
    __tablename__ = "historical_replay_runs"
    __table_args__ = (UniqueConstraint("replay_id", name="uq_historical_replay_runs_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    replay_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    immutable_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    counterfactual_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class BenchmarkCaseRecord(Base):
    __tablename__ = "benchmark_cases"
    __table_args__ = (UniqueConstraint("case_id", name="uq_benchmark_cases_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    scenario_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class BenchmarkRunRecord(Base):
    __tablename__ = "benchmark_runs"
    __table_args__ = (UniqueConstraint("benchmark_run_id", name="uq_benchmark_runs_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_run_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    suite_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    scorecard: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ModelRegistryRecord(Base):
    __tablename__ = "model_registry"
    __table_args__ = (UniqueConstraint("model_id", name="uq_model_registry_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ModelVersionRecord(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_version_id", name="uq_model_versions_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="candidate", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FinalActionAuditRecord(Base):
    __tablename__ = "final_action_audit_records"
    __table_args__ = (
        UniqueConstraint("final_action_id", name="uq_final_action_audit_records_public_id"),
        UniqueConstraint("tenant_id", "action_type", "idempotency_key", name="uq_final_action_audit_tenant_action_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    final_action_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    role_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_review_packet_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_evidence_pack_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    precondition_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    before_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="requested", index=True)
    effect_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class FinalActionRequestDraftRecord(Base):
    __tablename__ = "final_action_request_drafts"
    __table_args__ = (
        UniqueConstraint("final_action_request_id", name="uq_final_action_request_drafts_public_id"),
        UniqueConstraint("tenant_id", "action_type", "idempotency_key", name="uq_final_action_request_drafts_tenant_action_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    final_action_request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_review_packet_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_evidence_pack_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    preflight_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    role_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class ExternalReleaseShareRecord(Base):
    __tablename__ = "external_release_share_records"
    __table_args__ = (
        UniqueConstraint("share_id", name="uq_external_release_share_records_public_id"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_external_release_share_tenant_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    release_decision_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("release_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_packet_attachment_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient_scope: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    redaction_policy_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_review_packet_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    final_action_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="prepared_internal_share", index=True)
    delivery_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="not_sent", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant = relationship("Tenant")
    release_decision = relationship("ReleaseDecision")


class FinalActionReviewPacketSnapshot(Base):
    __tablename__ = "final_action_review_packet_snapshots"
    __table_args__ = (
        UniqueConstraint("source_review_packet_id", name="uq_final_action_review_packets_public_id"),
        UniqueConstraint("tenant_id", "packet_hash", name="uq_final_action_review_packets_tenant_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_review_packet_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    packet_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    packet_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    packet_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_pack_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    generated_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class KnowledgeRelationRecord(Base):
    __tablename__ = "knowledge_relations"
    __table_args__ = (UniqueConstraint("relation_id", name="uq_knowledge_relations_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    subject_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    evidence_pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExternalSourceRecord(Base):
    __tablename__ = "external_source_records"
    __table_args__ = (UniqueConstraint("source_id", name="uq_external_source_records_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    bos_module: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    evidence_source_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ingestion_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    auto_ingestion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ExternalSourceReviewCardRecord(Base):
    __tablename__ = "external_source_review_cards"
    __table_args__ = (
        UniqueConstraint("tenant_id", "card_id", name="uq_external_source_review_cards_tenant_card"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    shortlist_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("external_source_records.source_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    doi: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="pending_review", index=True)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False, server_default="unassigned")
    reviewer_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    license_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="pending_review", index=True)
    evidence_source_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ingestion_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    extracted_numeric_values_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    boundary_condition_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    allowed_use: Mapped[str] = mapped_column(Text, nullable=False)
    blocked_use: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    boundary_metadata: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source = relationship("ExternalSourceRecord")
    tenant = relationship("Tenant")
    reviewer_user = relationship("User")


class ExternalSourceExtractionRecord(Base):
    __tablename__ = "external_source_extraction_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "extraction_id", name="uq_external_source_extractions_tenant_extraction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    extraction_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    review_card_id: Mapped[int] = mapped_column(Integer, ForeignKey("external_source_review_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    extraction_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="staged_metadata_only", index=True)
    extracted_metadata: Mapped[dict] = mapped_column(JSON, nullable=False)
    extracted_numeric_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    numeric_values_included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    boundary_metadata: Mapped[dict] = mapped_column(JSON, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    review_card = relationship("ExternalSourceReviewCardRecord")
    tenant = relationship("Tenant")


class LiteratureExtractionCandidateRecord(Base):
    __tablename__ = "literature_extraction_candidate_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_literature_extraction_candidates_tenant_candidate"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("external_source_records.source_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    species: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    feedstock: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    treatment: Mapped[str] = mapped_column(Text, nullable=False)
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric_label: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(80), nullable=False)
    condition_context: Mapped[str] = mapped_column(Text, nullable=False)
    experiment_context: Mapped[str] = mapped_column(Text, nullable=False)
    table_or_section_ref: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_note: Mapped[str] = mapped_column(Text, nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(80), nullable=False, server_default="peer_reviewed_literature", index=True)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="pending_review", index=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    numeric_values_included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    release_evidence_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    runtime_activation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    validated_default_write_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    promotion_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    guardrails: Mapped[list] = mapped_column(JSON, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source = relationship("ExternalSourceRecord")
    tenant = relationship("Tenant")


class LiteratureExtractionReviewDraftRecord(Base):
    __tablename__ = "literature_extraction_review_draft_records"
    __table_args__ = (
        UniqueConstraint("review_draft_id", name="uq_literature_extraction_review_drafts_public_id"),
        UniqueConstraint(
            "tenant_id",
            "candidate_id",
            "idempotency_key",
            name="uq_literature_extraction_review_drafts_tenant_candidate_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_draft_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("external_source_records.source_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    review_intent: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reviewer_notes: Mapped[str] = mapped_column(Text, nullable=False)
    source_review_packet_export_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    source_review_packet_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    export_manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="draft_intent_recorded", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    source = relationship("ExternalSourceRecord")
    tenant = relationship("Tenant")


class LiteratureValuePromotionRequestRecord(Base):
    __tablename__ = "literature_value_promotion_requests"
    __table_args__ = (
        UniqueConstraint("promotion_request_id", name="uq_literature_value_promotion_requests_public_id"),
        UniqueConstraint(
            "tenant_id",
            "candidate_id",
            "idempotency_key",
            name="uq_literature_value_promotion_requests_tenant_candidate_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promotion_request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_review_packet_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_draft_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    comparison_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(80), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    target_use: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    request_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="requested", index=True)
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    tenant = relationship("Tenant")


class LiteratureValuePromotionApprovalRecord(Base):
    __tablename__ = "literature_value_promotion_approval_records"
    __table_args__ = (
        UniqueConstraint("approval_id", name="uq_literature_value_promotion_approvals_public_id"),
        UniqueConstraint(
            "tenant_id",
            "promotion_request_id",
            "idempotency_key",
            name="uq_literature_value_promotion_approvals_tenant_request_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    promotion_request_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_promotion_requests.id", ondelete="RESTRICT"), nullable=False, index=True)
    promotion_request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    approval_action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    request_status_before: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    request_status_after: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    approved_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    approver_notes: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_review_packet_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_draft_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    comparison_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_use: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    tenant = relationship("Tenant")
    promotion_request = relationship("LiteratureValuePromotionRequestRecord")


class LiteratureValueOverlayRecord(Base):
    __tablename__ = "literature_value_overlay_records"
    __table_args__ = (
        UniqueConstraint("overlay_id", name="uq_literature_value_overlays_public_id"),
        UniqueConstraint("tenant_id", "promotion_request_id", name="uq_literature_value_overlays_tenant_request"),
        UniqueConstraint(
            "tenant_id",
            "promotion_request_id",
            "idempotency_key",
            name="uq_literature_value_overlays_tenant_request_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    overlay_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    promotion_request_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_promotion_requests.id", ondelete="RESTRICT"), nullable=False, index=True)
    approval_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_promotion_approval_records.id", ondelete="RESTRICT"), nullable=False, index=True)
    promotion_request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    overlay_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="inactive", index=True)
    source_review_packet_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_draft_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    comparison_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(80), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    target_use: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    overlay_notes: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    tenant = relationship("Tenant")
    promotion_request = relationship("LiteratureValuePromotionRequestRecord")
    approval = relationship("LiteratureValuePromotionApprovalRecord")


class LiteratureValueRuntimeActivationRecord(Base):
    __tablename__ = "literature_value_runtime_activation_records"
    __table_args__ = (
        UniqueConstraint("activation_id", name="uq_literature_value_runtime_activations_public_id"),
        UniqueConstraint(
            "tenant_id",
            "overlay_id",
            "idempotency_key",
            name="uq_literature_value_runtime_activations_tenant_overlay_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    overlay_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_overlay_records.id", ondelete="RESTRICT"), nullable=False, index=True)
    overlay_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    promotion_request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    activation_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="active", index=True)
    activation_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    activated_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    operator_attestation: Mapped[str] = mapped_column(Text, nullable=False)
    deactivated_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    deactivation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    tenant = relationship("Tenant")
    overlay = relationship("LiteratureValueOverlayRecord")


class LiteratureValueReleaseEvidenceLinkRecord(Base):
    __tablename__ = "literature_value_release_evidence_links"
    __table_args__ = (
        UniqueConstraint("link_id", name="uq_literature_value_release_evidence_links_public_id"),
        UniqueConstraint(
            "tenant_id",
            "release_decision_id",
            "activation_id",
            "idempotency_key",
            name="uq_literature_value_release_evidence_links_tenant_release_activation_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    release_decision_id: Mapped[int] = mapped_column(Integer, ForeignKey("release_decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    activation_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_runtime_activation_records.id", ondelete="RESTRICT"), nullable=False, index=True)
    activation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    overlay_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    promotion_request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    link_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="active", index=True)
    rollback_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="none", index=True)
    activation_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_review_packet_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    comparison_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    release_decision_before: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    release_decision_after: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    linked_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    link_notes: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    tenant = relationship("Tenant")
    release_decision = relationship("ReleaseDecision")
    activation = relationship("LiteratureValueRuntimeActivationRecord")


class LiteratureValueRollbackRecord(Base):
    __tablename__ = "literature_value_rollback_records"
    __table_args__ = (
        UniqueConstraint("rollback_id", name="uq_literature_value_rollbacks_public_id"),
        UniqueConstraint(
            "tenant_id",
            "activation_id",
            "idempotency_key",
            name="uq_literature_value_rollbacks_tenant_activation_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rollback_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    activation_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_runtime_activation_records.id", ondelete="RESTRICT"), nullable=False, index=True)
    overlay_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("literature_value_overlay_records.id", ondelete="RESTRICT"), nullable=False, index=True)
    activation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    overlay_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    promotion_request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    rollback_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="completed", index=True)
    activation_status_before: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    activation_status_after: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    overlay_status_before: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    overlay_status_after: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    affected_release_evidence_link_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    release_evidence_link_status_updates: Mapped[list] = mapped_column(JSON, nullable=False)
    release_decision_states: Mapped[list] = mapped_column(JSON, nullable=False)
    rolled_back_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    rollback_reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator_attestation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    side_effects: Mapped[dict] = mapped_column(JSON, nullable=False)
    guardrail_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    tenant = relationship("Tenant")
    activation = relationship("LiteratureValueRuntimeActivationRecord")
    overlay = relationship("LiteratureValueOverlayRecord")


class ReviewedExternalCandidateRecord(Base):
    __tablename__ = "reviewed_external_candidate_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_reviewed_external_candidates_tenant_candidate"),
        UniqueConstraint("tenant_id", "card_id", name="uq_reviewed_external_candidates_tenant_card"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    candidate_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    review_card_id: Mapped[int] = mapped_column(Integer, ForeignKey("external_source_review_cards.id", ondelete="RESTRICT"), nullable=False, index=True)
    extraction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("external_source_extraction_records.id", ondelete="SET NULL"), nullable=True, index=True)
    card_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    license_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False, server_default="approved_for_candidate_use", index=True)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    boundary_condition: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_use: Mapped[str] = mapped_column(Text, nullable=False)
    blocked_use: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    promotion_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    runtime_activated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    validated_default_write_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    activation_relation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    audit_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    review_card = relationship("ExternalSourceReviewCardRecord")
    extraction = relationship("ExternalSourceExtractionRecord")
    tenant = relationship("Tenant")
