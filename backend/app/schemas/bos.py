"""
BOS protocol schemas.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_BOS_VERSION = "BOS-1.0"
DEFAULT_BOS_SIGNAL_COMPILER = "BOS-2.0"


class BaseBosModel(BaseModel):
    version: str = DEFAULT_BOS_VERSION

    model_config = ConfigDict(from_attributes=True)


class SignalBatchCreate(BaseModel):
    batch_id: int
    source_mode: str = Field(default="manual", max_length=50)
    compiler_version: str = Field(default=DEFAULT_BOS_SIGNAL_COMPILER, max_length=50)
    signal_api_version: str = Field(default="SIG-1.0", max_length=50)
    compiled_signal_id: str | None = Field(None, max_length=100)
    potency: float | None = Field(None, ge=0)
    potency_unit: str | None = Field(None, max_length=50)
    potency_basis: str | None = Field(None, max_length=100)
    dose_window_min: float | None = Field(None, ge=0)
    dose_window_max: float | None = Field(None, ge=0)
    stability_window_hours: float | None = Field(None, ge=0)
    kernel_residence_time_hours: float | None = Field(None, ge=0)
    handover_time: datetime | None = None
    freshness_state: str | None = Field(None, max_length=50)
    qc_markers: dict[str, Any] | None = None
    notes: str | None = None
    released_at: datetime | None = None
    expires_at: datetime | None = None
    compiled_from_batch_version: str | None = Field(None, max_length=50)
    compile_context: dict[str, Any] | None = None
    freshness_score: float | None = Field(None, ge=0, le=1)
    stability_score: float | None = Field(None, ge=0, le=1)
    release_readiness_score: float | None = Field(None, ge=0, le=1)


class SignalBatchResponse(BaseBosModel, SignalBatchCreate):
    id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime


class SignalCompileRequest(BaseModel):
    batch_id: int
    control_profile_id: int | None = None
    locality_profile_id: int | None = None
    dose_window_min: float | None = Field(None, ge=0)
    dose_window_max: float | None = Field(None, ge=0)
    stability_window_hours: float | None = Field(None, ge=0)
    kernel_residence_time_hours: float | None = Field(None, ge=0)
    compiler_version: str = Field(default=DEFAULT_BOS_SIGNAL_COMPILER, max_length=50)
    notes: str | None = None
    apply_locality_shifts: bool = True


class SignalCompileResponse(SignalBatchResponse):
    compile_status: str = "compiled"
    source_mode: str = "compiled"


class SignalRefreshResponse(BaseBosModel):
    signal_batch: SignalBatchResponse
    refreshed_state: str
    metering_age_hours: float | None = None
    freshness_score: float
    release_readiness_score: float


class ControlAPIProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(..., min_length=1, max_length=50)
    hal_min: float | None = Field(None, ge=0)
    hal_max: float | None = Field(None, ge=0)
    mtt: float | None = Field(None, ge=0)
    dose_window_min: float | None = Field(None, ge=0)
    dose_window_max: float | None = Field(None, ge=0)
    stability_window_hours: float | None = Field(None, ge=0)
    dwell_time_min_hours: float | None = Field(None, ge=0)
    dwell_time_max_hours: float | None = Field(None, ge=0)
    qc_thresholds: dict[str, Any] | None = None
    release_rules: dict[str, Any] | None = None
    active: bool = True
    notes: str | None = None


class ControlAPIProfileResponse(BaseBosModel, ControlAPIProfileCreate):
    id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime


class LocalityProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    site_code: str | None = Field(None, max_length=100)
    substrate_class: str | None = Field(None, max_length=100)
    waste_state: dict[str, Any] | None = None
    pretreat_flags: dict[str, Any] | None = None
    dose_window_shift_pct: float | None = None
    mtt_shift_pct: float | None = None
    notes: str | None = None
    active: bool = True


class LocalityProfileResponse(BaseBosModel, LocalityProfileCreate):
    id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    active_shift_summary: dict[str, float] | None = None


class ExecutorProfileCreate(BaseModel):
    locality_profile_id: int | None = None
    executor_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    executor_type: str | None = Field(None, max_length=100)
    hal_min: float | None = Field(None, ge=0)
    hal_max: float | None = Field(None, ge=0)
    mtt_nominal: float | None = Field(None, ge=0)
    plugin_mode: str | None = Field(None, max_length=100)
    notes: str | None = None
    active: bool = True


class ExecutorProfileResponse(BaseBosModel, ExecutorProfileCreate):
    id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    effective_contract_shift: dict[str, Any] | None = None


class BoundaryLedgerCreate(BaseModel):
    batch_id: int
    signal_batch_id: int | None = None
    d_prime: float | None = None
    g_prime: float | None = None
    ser_value: float | None = None
    ser_system: float | None = None
    delta_delta_ser: float | None = None
    closure_residual: float | None = None
    closure_penalty: float | None = None
    evidence_penalty: float | None = None
    metering_completeness: float | None = None
    qc_flags: list[str] | None = None
    measured_vs_estimated: dict[str, Any] | None = None
    evidence_level: str | None = Field(None, max_length=50)
    decision_confidence: float | None = Field(None, ge=0, le=1)
    notes: str | None = None


class BoundaryLedgerResponse(BaseBosModel, BoundaryLedgerCreate):
    id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime


class ReleaseExplanation(BaseModel):
    decision: str = Field(..., min_length=1, max_length=50)
    reason_codes: list[str] = Field(default_factory=list)
    blocking_factors: list[str] = Field(default_factory=list)
    warning_factors: list[str] = Field(default_factory=list)
    passed_checks: list[str] = Field(default_factory=list)
    trigger_metrics: dict[str, Any] = Field(default_factory=dict)
    decision_confidence: float | None = Field(None, ge=0, le=1)
    rationale: str | None = None


class ReleaseDecisionCreate(BaseModel):
    batch_id: int
    signal_batch_id: int | None = None
    boundary_ledger_id: int | None = None
    control_profile_id: int | None = None
    decision: str = Field(..., min_length=1, max_length=50)
    reason_codes: list[str] | None = None
    blocking_factors: list[str] | None = None
    warning_factors: list[str] | None = None
    passed_checks: list[str] | None = None
    trigger_metrics: dict[str, Any] | None = None
    approver: str | None = Field(None, max_length=255)
    rationale: str | None = None
    applied_contract: dict[str, Any] | None = None
    applied_locality_shift: dict[str, Any] | None = None
    decision_confidence: float | None = Field(None, ge=0, le=1)


class ReleaseDecisionResponse(BaseBosModel, ReleaseDecisionCreate):
    id: int
    user_id: int
    tenant_id: int
    decision_time: datetime
    created_at: datetime


class PortabilityAuditCreate(BaseModel):
    signal_batch_id: int
    executor_profile_id: int
    locality_profile_id: int | None = None
    outcome: str = Field(..., min_length=1, max_length=50)
    retuning_required: bool = False
    override_outcome: str | None = Field(None, max_length=50)
    notes: str | None = None
    trigger_metrics: dict[str, Any] | None = None


class PortabilityAuditResponse(BaseBosModel, PortabilityAuditCreate):
    id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    recommended_outcome: str | None = None
    rationale: str | None = None
    recommended_action: str | None = None
    requires_requalification: bool = False
    retuning_axes: list[str] | None = None
    retuning_magnitude: float | None = Field(None, ge=0)
    portability_score: float | None = Field(None, ge=0, le=1)


class PortabilityRecommendationRequest(BaseModel):
    signal_batch_id: int
    executor_profile_id: int
    locality_profile_id: int | None = None


class PortabilityRecommendationResponse(BaseBosModel):
    signal_batch_id: int
    executor_profile_id: int
    locality_profile_id: int | None = None
    recommended_outcome: str
    rationale: str
    recommended_action: str
    requires_requalification: bool = False
    retuning_axes: list[str] = Field(default_factory=list)
    retuning_magnitude: float | None = None
    override_outcome: str | None = None
    portability_score: float | None = Field(None, ge=0, le=1)


class AuditPacketBatchSnapshot(BaseModel):
    id: int
    batch_id: str
    species: str
    status: str


class AuditPacketSignalSnapshot(BaseModel):
    id: int
    signal_api_version: str
    compiled_signal_id: str | None = None
    potency: float | None = None
    potency_unit: str | None = None
    freshness_state: str | None = None


class AuditPacketControlSnapshot(BaseModel):
    id: int
    name: str
    version: str
    mtt: float | None = None
    hal_min: float | None = None
    hal_max: float | None = None
    dose_window_min: float | None = None
    dose_window_max: float | None = None
    stability_window_hours: float | None = None


class AuditPacketBoundarySnapshot(BaseModel):
    id: int | None = None
    d_prime: float | None = None
    g_prime: float | None = None
    ser_value: float | None = None
    ser_system: float | None = None
    delta_delta_ser: float | None = None
    closure_residual: float | None = None
    closure_penalty: float | None = None
    evidence_penalty: float | None = None
    metering_completeness: float | None = None
    qc_flags: list[str] = Field(default_factory=list)
    evidence_level: str | None = None
    notes: str | None = None


class AuditPacketPortabilityEntry(BaseModel):
    id: int
    executor_profile_id: int
    locality_profile_id: int | None = None
    executor_name: str | None = None
    locality_name: str | None = None
    outcome: str
    retuning_required: bool
    recommended_outcome: str | None = None
    rationale: str | None = None
    recommended_action: str | None = None
    requires_requalification: bool = False
    retuning_axes: list[str] | None = None
    retuning_magnitude: float | None = None
    portability_score: float | None = Field(None, ge=0, le=1)
    trigger_metrics: dict[str, Any] | None = None


class AuditPacketGenerationContext(BaseModel):
    schema_version: str
    compiled_at: datetime
    compiled_by_user_id: int
    source_ids: dict[str, Any] = Field(default_factory=dict)
    hash: str
    source_mode: str | None = None


class AuditPacketPayload(BaseModel):
    batch: AuditPacketBatchSnapshot
    signal_batch: AuditPacketSignalSnapshot | None = None
    control_profile: AuditPacketControlSnapshot | None = None
    boundary_ledger: AuditPacketBoundarySnapshot | None = None
    release_decision: ReleaseExplanation | None = None
    portability_audits: list[AuditPacketPortabilityEntry] = Field(default_factory=list)
    native_model_stack: dict[str, Any] | None = None
    native_forecast_evidence: dict[str, Any] | None = None
    generation_context: AuditPacketGenerationContext


class AuditPacketResponse(BaseBosModel):
    id: int
    batch_id: int
    release_decision_id: int | None = None
    user_id: int
    tenant_id: int
    packet_version: str
    evidence_level: str | None = None
    contract_evaluation: dict[str, Any] | None = None
    signal_validity: dict[str, Any] | None = None
    retuning_axes: dict[str, Any] | None = None
    packet: AuditPacketPayload | None = None
    generated_at: datetime
    created_at: datetime


class ReleaseEvaluationRequest(BaseModel):
    batch_id: int
    control_profile_id: int | None = None
    signal_batch_id: int | None = None
    persist: bool = True
    locality_profile_id: int | None = None


class BatchBOSOverview(BaseBosModel):
    signal_batch: SignalBatchResponse | None = None
    control_profile: ControlAPIProfileResponse | None = None
    boundary_ledger: BoundaryLedgerResponse | None = None
    release_decision: ReleaseDecisionResponse | None = None
    audit_packet: AuditPacketResponse | None = None
    portability_audits: list[PortabilityAuditResponse] = Field(default_factory=list)
    compile_status: str | None = None
    latest_signal_status: str | None = None
    latest_native_run: Optional["NativeModelRunSummaryResponse"] = None


class GuidanceItemResponse(BaseModel):
    code: str
    severity: str = Field(..., pattern=r"^(info|warning|critical)$")
    title: str
    message: str
    recommended_action: str
    blocking: bool = False


class BatchGuidanceResponse(BaseBosModel):
    batch_id: int
    gap_items: list[GuidanceItemResponse] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class BrainRuntimeDocumentResponse(BaseBosModel):
    key: str
    title: str
    relative_path: str
    content: str
    updated_at: datetime | None = None
    line_count: int
    is_missing: bool = False


class BrainRuntimeResponse(BaseBosModel):
    root_path: str
    documents: list[BrainRuntimeDocumentResponse] = Field(default_factory=list)
    total_line_count: int = 0
    last_updated_at: datetime | None = None


class BrainRuntimeUpdateRequest(BaseModel):
    content: str


class NativeModelSourceResponse(BaseModel):
    label: str
    url: str
    provider: str


class NativeModelCapabilityResponse(BaseModel):
    key: str
    name: str
    family: str
    frontier_window: str
    modality: str
    maturity: str
    primary_fit: str
    dialectical_role: str
    native_outputs: list[str] = Field(default_factory=list)
    bos_touchpoints: list[str] = Field(default_factory=list)
    operational_triggers: list[str] = Field(default_factory=list)
    recommended_deployment: list[str] = Field(default_factory=list)
    sources: list[NativeModelSourceResponse] = Field(default_factory=list)


class NativeModelCompositionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    key: str
    title: str
    objective: str
    model_keys: list[str] = Field(default_factory=list)
    why_it_matters: str
    native_outputs: list[str] = Field(default_factory=list)
    bos_agents: list[str] = Field(default_factory=list)


class NativeModelRecommendationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    key: str
    title: str
    fit: str
    rationale: str
    model_keys: list[str] = Field(default_factory=list)
    native_outputs: list[str] = Field(default_factory=list)


class NativeModelRolloutStepResponse(BaseModel):
    phase: str
    title: str
    objective: str


class NativeModelCatalogResponse(BaseBosModel):
    catalog_version: str
    verified_on: str
    models: list[NativeModelCapabilityResponse] = Field(default_factory=list)
    compositions: list[NativeModelCompositionResponse] = Field(default_factory=list)
    recommendations: list[NativeModelRecommendationResponse] = Field(default_factory=list)
    rollout: list[NativeModelRolloutStepResponse] = Field(default_factory=list)


class NativeModelRuntimeArtifactResponse(BaseModel):
    expected_location: str
    configured_location: str | None = None
    exists: bool
    source_reference: str | None = None
    artifact_kind: str | None = None


class NativeModelRuntimeDependencyResponse(BaseModel):
    package: str
    installed: bool


class NativeModelRuntimeEntryResponse(BaseModel):
    key: str
    ready: bool
    runtime_state: str
    modality: str
    adapter_status: str
    artifact: NativeModelRuntimeArtifactResponse
    dependencies: list[NativeModelRuntimeDependencyResponse] = Field(default_factory=list)
    expected_inputs: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class NativeModelRuntimeStatusResponse(BaseBosModel):
    enabled: bool
    cache_dir: str
    summary: dict[str, Any] = Field(default_factory=dict)
    runtimes: list[NativeModelRuntimeEntryResponse] = Field(default_factory=list)


class NativeModelInferenceRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    batch_id: int | None = None
    dry_run: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class NativeModelInferenceResponse(BaseBosModel):
    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    batch_id: int | None = None
    ready: bool
    runtime_state: str
    execution_mode: str
    payload_echo: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class NativeModelDownloadPlanResponse(BaseBosModel):
    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    supported: bool
    source_kind: str
    source_reference: str | None = None
    target_path: str
    notes: list[str] = Field(default_factory=list)


class NativeModelDownloadResponse(BaseBosModel):
    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    downloaded: bool
    runtime_state: str
    target_path: str
    source_reference: str | None = None
    detail: str
    extracted_path: str | None = None


class NativeModelRunArtifactResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    execution_mode: str
    recorded_at: str
    artifact_path: str
    payload_echo: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class NativeModelRunSummaryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    modality: str
    evidence_tier: str
    evidence_label: str
    evidence_summary: Optional[str] = None
    execution_mode: str
    recorded_at: str
    artifact_path: str
    metric_name: str | None = None
    prediction_horizon: int | None = None
    forecast_preview: list[str] = Field(default_factory=list)
    detection_count: int | None = None
    top_label: str | None = None
    top_candidates: list[str] = Field(default_factory=list)
    bbox_summary: str | None = None
    is_live: bool


class SupervisorObservationRequest(BaseModel):
    uv254: float
    od280: float
    do: float = Field(
        ...,
        alias="do",
    )
    ph: float
    elapsed_hours: float = Field(
        ...,
        ge=0,
    )
    previous_c_signal_hat: float | None = Field(None, ge=0, le=1)
    previous_elapsed_hours: float | None = Field(None, ge=0)
    previous_dc_dt_hat: float | None = None
    previous_negative_slope_streak: int = Field(default=0, ge=0)
    confidence_threshold: float = Field(default=0.8, ge=0, le=1)
    negative_slope_persistence: int = Field(default=3, ge=1)
    observability_required: bool = True


class SupervisorStateResponse(BaseBosModel):
    id: int
    signal_batch_id: int
    c_signal_hat: float
    dc_dt_hat: float | None = None
    confidence: float
    observed_at: datetime
    missing_channels: list[str] = Field(default_factory=list)
    channels_used: list[str] = Field(default_factory=list)
    information_loss: float | None = Field(None, ge=0, le=1)
    observability_score: float | None = Field(None, ge=0, le=1)
    negative_slope_streak: int | None = Field(None, ge=0)
    trigger_reason: str | None = None
    expected_handover: datetime | None = None
    mechanistic_context: dict[str, Any] | None = None


class HandoverRecommendationResponse(BaseBosModel):
    signal_batch_id: int
    recommended_handover: bool
    trigger_reason: str
    expected_freshness_window_hours: float | None = None
    c_signal_hat: float | None = Field(None, ge=0, le=1)
    dc_dt_hat: float | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    expected_handover: datetime | None = None
    confidence_threshold: float = 0.8
    negative_slope_persistence: int | None = None
    observability_required: bool = True
    missing_channels: list[str] = Field(default_factory=list)
    channels_used: list[str] = Field(default_factory=list)
    information_loss: float | None = Field(None, ge=0, le=1)
    observability_score: float | None = Field(None, ge=0, le=1)
    mechanistic_context: dict[str, Any] | None = None


class ClosedLoopSimulationRequest(BaseModel):
    batch_id: int
    num_cycles: int = Field(default=5, ge=1, le=24)
    seed: int = Field(default=7, ge=0)
    feed_amount_g: float = Field(default=25.0, gt=0, le=1000)
    task_name: str = Field(default="feed_larvae", min_length=1, max_length=100)


class ClosedLoopSimulationCycleResponse(BaseModel):
    cycle: int
    ser: dict[str, Any] = Field(default_factory=dict)
    vision: dict[str, Any] = Field(default_factory=dict)
    prediction: dict[str, Any] = Field(default_factory=dict)
    digital_twin: dict[str, Any] = Field(default_factory=dict)
    phy_execution: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)


class ClosedLoopSimulationResponse(BaseBosModel):
    mode: str
    batch: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    cycles: list[ClosedLoopSimulationCycleResponse] = Field(default_factory=list)
    disclaimer: str


class ClosedLoopSimulationTableRowResponse(BaseModel):
    batch_id: str | None = None
    species: str | None = None
    cycle: int
    ser_score: float | None = None
    ser_information_loss: float | None = None
    larvae_count: int | None = None
    larvae_density: float | None = None
    stage: str | None = None
    decomp_72h_percent: float | None = None
    instantaneous_ser_proxy: float | None = None
    growth_rate: float | None = None
    twin_biomass: float | None = None
    twin_substrate: float | None = None
    twin_temperature: float | None = None
    twin_moisture: float | None = None
    response_time_ms: float | None = None
    watchdog_triggered: bool | None = None
    watchdog_status: str | None = None
    sensor_temperature_C: float | None = None
    sensor_moisture_pct: float | None = None
    sensor_larvae_density: float | None = None
    audit_mode: str | None = None
    audit_recorded_at: str | None = None


class ClosedLoopSimulationTableResponse(BaseBosModel):
    mode: str
    batch: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[ClosedLoopSimulationTableRowResponse] = Field(default_factory=list)
    disclaimer: str
