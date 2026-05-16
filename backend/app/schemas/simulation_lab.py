"""Schemas for the BOS Simulation Lab virtual closed-loop harness."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import SimulationEvidenceSource

SimulationScenario = Literal["normal", "moisture_drift", "temperature_spike", "underfeeding"]
SimulationPolicy = Literal["rule_based", "conservative", "growth_optimized", "risk_minimizing"]


class SimulationInitialState(BaseModel):
    biomass: float = Field(default=0.5, gt=0)
    substrate: float = Field(default=10.0, gt=0)
    temperature: float = Field(default=28.0, ge=0, le=60)
    moisture: float = Field(default=70.0, ge=0, le=100)
    nitrogen: float = Field(default=50.0, ge=0)


class LabAssayMeasurements(BaseModel):
    biomass: float | None = Field(default=None, ge=0)
    substrate: float | None = Field(default=None, ge=0)
    moisture: float | None = Field(default=None, ge=0, le=100)
    heavy_metal_index: float | None = Field(default=None, ge=0, le=1)


class SimulationScenarioCreate(BaseModel):
    species: str = Field(default="BSF", min_length=1, max_length=80)
    feedstock: str = Field(default="mixed_food_waste", min_length=1, max_length=120)
    scenario: SimulationScenario = "normal"
    initial_state: SimulationInitialState = Field(default_factory=SimulationInitialState)
    cycles: int = Field(default=8, ge=5, le=24)
    seed: int = Field(default=7, ge=0, le=1_000_000)
    policy: SimulationPolicy = "rule_based"
    lab_assay_measurements: LabAssayMeasurements | None = None


class SimulationScenarioResponse(BaseModel):
    simulation_id: str
    batch_id: str
    tenant_id: int
    species: str
    feedstock: str
    scenario: SimulationScenario
    initial_state: SimulationInitialState
    cycles: int
    seed: int
    policy: SimulationPolicy
    lab_assay_measurements: LabAssayMeasurements | None = None
    evidence_sources: list[SimulationEvidenceSource] = Field(default_factory=list)
    status: str
    created_at: datetime


class SimulationLabCycleResponse(BaseModel):
    cycle: int
    timestamp: datetime
    state_before: dict[str, Any]
    sensor_observation: dict[str, Any]
    supervisor_decision: dict[str, Any]
    risk_prediction: dict[str, Any]
    visual_observation: dict[str, Any] | None = None
    evidence_sources: list[SimulationEvidenceSource] = Field(default_factory=list)
    agent_action: dict[str, Any]
    actuator_result: dict[str, Any]
    state_after: dict[str, Any]
    audit_event: dict[str, Any]


class SimulationLabSummaryResponse(BaseModel):
    simulation_id: str
    cycle_count: int
    scenario: SimulationScenario
    policy: SimulationPolicy
    starting_risk: float
    ending_risk: float
    risk_delta: float
    action_count: int
    audit_event_count: int
    final_state: dict[str, Any]


class SimulationLabRunResponse(BaseModel):
    scenario: SimulationScenarioResponse
    summary: SimulationLabSummaryResponse
    cycles: list[SimulationLabCycleResponse]


class SimulationLabRunHistoryItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    simulation_id: str
    tenant_id: int
    policy: SimulationPolicy
    status: str
    engine_version: str = "simulation_lab_v2_8"
    model_version: str | None = None
    input_snapshot_id: str | None = None
    input_snapshot_hash: str | None = None
    replay_of_run_id: str | None = None
    evidence_pack_id: str | None = None
    cycle_count: int
    starting_risk: float
    ending_risk: float
    risk_delta: float
    action_count: int
    audit_event_count: int
    final_state: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime


class SimulationPolicyCompareRequest(BaseModel):
    policies: list[SimulationPolicy] = Field(
        default_factory=lambda: ["rule_based", "conservative", "growth_optimized", "risk_minimizing"],
        min_length=1,
        max_length=4,
    )
    baseline_policy: SimulationPolicy = "rule_based"


class SimulationScenarioImportRequest(BaseModel):
    reference_id: str = Field(..., min_length=1, max_length=160)
    scenario_name: str | None = Field(default=None, max_length=160)
    policy: SimulationPolicy = "rule_based"
    cycles: int = Field(default=8, ge=5, le=24)
    seed: int = Field(default=17, ge=0, le=1_000_000)


class SimulationScenarioImportMetadata(BaseModel):
    reference_id: str
    reference_source: str
    source_title: str
    review_status: str = "review_required"
    human_review_required: bool = True
    numeric_values_included: bool = True
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    extraction_confidence: float
    field_sources: dict[str, str]
    fallbacks: list[str] = Field(default_factory=list)
    environmental_drift_assumptions: dict[str, Any] = Field(default_factory=dict)
    expected_risk_constraints: dict[str, Any] = Field(default_factory=dict)


class SimulationScenarioImportResponse(BaseModel):
    scenario: SimulationScenarioResponse
    import_metadata: SimulationScenarioImportMetadata


class SimulationPolicyComparisonMetrics(BaseModel):
    risk_delta: float
    biomass_gain: float
    substrate_use: float
    intervention_count: int
    human_review_count: int
    audit_completeness: float
    conversion_rate_estimate: float
    mortality_risk: float
    moisture_risk: float
    nh3_risk: float
    energy_kwh_estimate: float
    water_kg_estimate: float
    co2e_estimate: float
    labor_hour_estimate: float
    gross_margin_estimate: float
    release_readiness: str
    missing_evidence: list[str] = Field(default_factory=list)
    human_review_required: bool = False


class SimulationPolicyComparisonRun(BaseModel):
    policy: SimulationPolicy
    run_id: str
    summary: SimulationLabSummaryResponse
    metrics: SimulationPolicyComparisonMetrics


class SimulationPolicyComparisonResponse(BaseModel):
    simulation_id: str
    baseline_policy: SimulationPolicy
    runs: list[SimulationPolicyComparisonRun]
    winner: dict[str, SimulationPolicy | None]


class SimulationReleaseAppendixAuditHash(BaseModel):
    cycle: int | None = None
    event_type: str
    payload_hash: str
    recorded_at: datetime


class SimulationReleaseAppendixResponse(BaseModel):
    simulation_id: str
    generated_at: datetime
    scenario: SimulationScenarioResponse
    selected_run: SimulationLabRunHistoryItem | None = None
    comparison_runs: list[SimulationPolicyComparisonRun] = Field(default_factory=list)
    audit_trace_hashes: list[SimulationReleaseAppendixAuditHash] = Field(default_factory=list)
    evidence_pack_id: str | None = None
    input_snapshot_id: str | None = None
    disclaimer: str


class SimulationEvidenceSourcesResponse(BaseModel):
    simulation_id: str
    scenario_sources: list[SimulationEvidenceSource] = Field(default_factory=list)
    latest_run_sources: list[SimulationEvidenceSource] = Field(default_factory=list)
    cycle_sources: list[dict[str, Any]] = Field(default_factory=list)


class SimulationReplayResponse(BaseModel):
    source_run_id: str
    replay_run: SimulationLabRunHistoryItem
    deterministic_core_match: bool
    warnings: list[str] = Field(default_factory=list)


class SimulationRunDiffResponse(BaseModel):
    run_id: str
    against_run_id: str
    deterministic_core_match: bool
    differences: list[dict[str, Any]] = Field(default_factory=list)


class SimulationLabCycleListResponse(BaseModel):
    simulation_id: str
    cycles: list[SimulationLabCycleResponse]


class SimulationLabAuditTraceResponse(BaseModel):
    simulation_id: str
    audit_trace: list[dict[str, Any]]


class SimulationLabExportResponse(BaseModel):
    simulation_id: str
    exported_at: datetime
    scenario: SimulationScenarioResponse
    summary: SimulationLabSummaryResponse | None = None
    cycles: list[SimulationLabCycleResponse] = Field(default_factory=list)
    audit_trace: list[dict[str, Any]] = Field(default_factory=list)
    evidence_sources: list[SimulationEvidenceSource] = Field(default_factory=list)
    evidence_pack_id: str | None = None
    input_snapshot_id: str | None = None
    disclaimer: str
