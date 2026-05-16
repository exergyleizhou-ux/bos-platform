"""Persistence-backed orchestration service for BOS Simulation Lab."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from statistics import mean
import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.bos_simulation_lab import SimulationLabConfig, run_simulation_lab
from app.engine.manuscript_reference_db import get_campaign
from app.models_bos import (
    LiteratureExtractionCandidateRecord,
    SimulationAuditEventRecord,
    SimulationCycleRecord,
    SimulationRunRecord,
    SimulationScenarioRecord,
)
from app.schemas.evidence import EvidenceItemCreate, EvidencePackCreate, SimulationEvidenceSource
from app.schemas.simulation_lab import (
    SimulationLabAuditTraceResponse,
    SimulationLabCycleListResponse,
    SimulationLabCycleResponse,
    SimulationLabExportResponse,
    SimulationLabRunHistoryItem,
    SimulationLabRunResponse,
    SimulationLabSummaryResponse,
    SimulationPolicy,
    SimulationPolicyComparisonMetrics,
    SimulationPolicyComparisonResponse,
    SimulationPolicyComparisonRun,
    SimulationEvidenceSourcesResponse,
    SimulationReleaseAppendixAuditHash,
    SimulationReleaseAppendixResponse,
    SimulationReplayResponse,
    SimulationRunDiffResponse,
    SimulationScenarioCreate,
    SimulationScenarioImportMetadata,
    SimulationScenarioImportRequest,
    SimulationScenarioImportResponse,
    SimulationScenarioResponse,
)
from app.services.evidence_service import create_evidence_pack, create_input_snapshot, stable_payload_hash
from app.services.chronos_risk_service import forecast_with_chronos_or_fallback
from app.services.reference_ingestion_service import reference_ingestion_service

SIMULATION_ENGINE_VERSION = "simulation_lab_v2_8"
SIMULATION_MODEL_VERSION = "simulation_lab_deterministic_proxy_v2_8"


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def reset_simulation_lab_store() -> None:
    """Retained for v1 tests; v2 state is stored in the test database."""


def _new_simulation_id() -> str:
    return f"SIM-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source(
    field: str,
    source_kind: str,
    *,
    source_ref: str | None = None,
    confidence: float = 1.0,
    fallback_used: bool = False,
    notes: str | None = None,
) -> dict:
    return SimulationEvidenceSource(
        field=field,
        source_kind=source_kind,  # type: ignore[arg-type]
        source_ref=source_ref,
        confidence=confidence,
        fallback_used=fallback_used,
        notes=notes,
    ).model_dump()


def _operator_scenario_sources() -> list[dict]:
    return [
        _source("species", "operator_input"),
        _source("feedstock", "operator_input"),
        _source("scenario", "operator_input"),
        _source("initial_state", "operator_input"),
        _source("cycles", "operator_input"),
        _source("seed", "operator_input"),
        _source("policy", "operator_input"),
    ]


LABSIM_STANDARD_REFS = "GB 19489-2008; GB 4284-2018; GB 15618-2018"


def _labsim_profile(*, species: str, feedstock: str) -> dict:
    species_key = species.lower()
    feedstock_key = feedstock.lower()
    if "sludge" in feedstock_key:
        return {
            "profile_id": "bsf_sludge_heavy_metal_redline",
            "route": "restricted sludge heavy-metal research lane",
            "containment": "restricted hazardous sample bench",
            "review_status": "human_review_required",
            "product_use_lock": "research_simulation_only",
            "heavy_metal_gate": "redline",
            "max_heavy_metal_risk": 0.82,
            "standard_refs": LABSIM_STANDARD_REFS,
        }
    if "grub" in species_key or "manure" in feedstock_key:
        return {
            "profile_id": "grub_manure_humus_lane",
            "route": "grub manure and humus degradation lane",
            "containment": "biosafety and odor-control bench",
            "review_status": "review_required",
            "product_use_lock": "no_feed_or_fertilizer_release_without_reviewed_assay",
            "heavy_metal_gate": "review",
            "max_heavy_metal_risk": 0.42,
            "standard_refs": LABSIM_STANDARD_REFS,
        }
    if "mealworm" in species_key or "straw" in feedstock_key:
        return {
            "profile_id": "mealworm_straw_distillers_lane",
            "route": "mealworm straw and distillers grain calibration lane",
            "containment": "dry substrate insect culture bench",
            "review_status": "calibration_required",
            "product_use_lock": "feed_pathway_locked_until_source_and_assay_review",
            "heavy_metal_gate": "screened",
            "max_heavy_metal_risk": 0.20,
            "standard_refs": LABSIM_STANDARD_REFS,
        }
    if any(marker in feedstock_key for marker in ("distillers", "brewery", "beer_lees")):
        return {
            "profile_id": "bsf_distillers_grain_lane",
            "route": "BSF distillers grain high-moisture lane",
            "containment": "high-throughput larval tray bay",
            "review_status": "pilot_ready_after_assay_review",
            "product_use_lock": "scale_up_requires_moisture_and_ammonia_evidence",
            "heavy_metal_gate": "screened",
            "max_heavy_metal_risk": 0.17,
            "standard_refs": LABSIM_STANDARD_REFS,
        }
    return {
        "profile_id": "generic_insect_biowaste_lab_lane",
        "route": "generic insect biowaste simulation lane",
        "containment": "standard virtual lab bench",
        "review_status": "review_required",
        "product_use_lock": "output_requires_human_review_before_release_use",
        "heavy_metal_gate": "unknown_requires_screening",
        "max_heavy_metal_risk": 0.50,
        "standard_refs": LABSIM_STANDARD_REFS,
    }


def _labsim_scenario_sources(*, species: str, feedstock: str) -> list[dict]:
    profile = _labsim_profile(species=species, feedstock=feedstock)
    return [
        _source(
            "lab_profile",
            "deterministic_model",
            source_ref=profile["profile_id"],
            confidence=0.86,
            notes=profile["route"],
        ),
        _source(
            "heavy_metal_gate",
            "official_standard",
            source_ref=profile["standard_refs"],
            confidence=0.82,
            fallback_used=profile["heavy_metal_gate"].startswith("unknown"),
            notes=f"{profile['heavy_metal_gate']} max_risk={profile['max_heavy_metal_risk']}",
        ),
        _source(
            "product_use_lock",
            "official_standard",
            source_ref=profile["standard_refs"],
            confidence=0.82,
            notes=profile["product_use_lock"],
        ),
        _source(
            "containment",
            "official_standard",
            source_ref="GB 19489-2008",
            confidence=0.82,
            notes=profile["containment"],
        ),
    ]


def _valid_assay_measurements(payload: dict | None) -> dict[str, float] | None:
    if not payload:
        return None
    allowed = {"biomass", "substrate", "moisture", "heavy_metal_index"}
    result: dict[str, float] = {}
    for key, value in payload.items():
        if key in allowed and value is not None:
            result[key] = float(value)
    return result or None


def _labsim_assay_source(
    measurements: dict[str, float],
    *,
    source_kind: str = "manuscript_campaign",
    source_ref: str = "operator_entered_lab_assay_measurements",
    confidence: float = 0.88,
    notes: str = "review-gated measured assay values supplied with the virtual scenario",
    measurement_mode: str = "operator_entered",
    review_status: str = "review_required",
) -> dict:
    source = _source(
        "lab_assay_measurements",
        source_kind,
        source_ref=source_ref,
        confidence=confidence,
        notes=notes,
    )
    source["payload"] = measurements
    source["measurement_mode"] = measurement_mode
    source["review_status"] = review_status
    return source


def _scenario_lab_assay_source(record: SimulationScenarioRecord) -> dict | None:
    for source in record.evidence_sources or []:
        if source.get("field") == "lab_assay_measurements":
            measurements = _valid_assay_measurements(source.get("payload"))
            if measurements:
                return source
    return None


def _scenario_lab_assay_measurements(record: SimulationScenarioRecord) -> dict[str, float] | None:
    source = _scenario_lab_assay_source(record)
    if source is None:
        return None
    return _valid_assay_measurements(source.get("payload"))


def _lab_assay_measurement_mode(source: dict | None) -> str:
    if source is None:
        return "profile_anchor"
    mode = str(source.get("measurement_mode") or "")
    if mode in {"operator_entered", "reference_imported"}:
        return mode
    if source.get("source_ref") == "operator_entered_lab_assay_measurements":
        return "operator_entered"
    return "reference_imported"


def _lab_assay_source_review_status(source: dict | None, lab_profile: dict) -> str:
    if source is None:
        return str(lab_profile["review_status"])
    return str(source.get("review_status") or lab_profile["review_status"])


def _lab_assay_source_ref(source: dict | None, lab_profile: dict) -> str:
    if source is None:
        return f"labsim_assay_anchor:{lab_profile['profile_id']}"
    return str(source.get("source_ref") or "reference_imported_lab_assay_measurements")


def _lab_assay_source_kind(source: dict | None) -> str:
    if source is None:
        return "manuscript_campaign"
    return str(source.get("source_kind") or "imported_reference")


def _metric_payload_candidates(payload: dict) -> list[dict]:
    candidates: list[dict] = [payload]
    for container_key in (
        "lab_assay_measurements",
        "assay_measurements",
        "measured_assays",
        "measurement_values",
        "runtime_payload",
        "candidate_payload",
    ):
        nested = payload.get(container_key)
        if isinstance(nested, dict):
            candidates.append(nested)
    return candidates


def _numeric_metric_value(payload: dict, aliases: tuple[str, ...]) -> float | None:
    for candidate in _metric_payload_candidates(payload):
        for alias in aliases:
            value = candidate.get(alias)
            if isinstance(value, list) and value:
                value = value[-1]
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
    return None


def _reference_metric_from_candidate(payload: dict) -> tuple[str, float] | None:
    metric_key = str(payload.get("metric_key") or "").lower()
    raw_value = payload.get("raw_value")
    if raw_value is None:
        return None
    aliases = {
        "biomass": ("biomass", "larval_biomass", "larvae_biomass", "biomass_kg"),
        "substrate": ("substrate", "residual_substrate", "substrate_remaining", "substrate_g"),
        "moisture": ("moisture", "moisture_pct", "moisture_percent"),
        "heavy_metal_index": ("heavy_metal_index", "heavy_metals", "heavy_metal_risk", "risk_index"),
    }
    for target, keys in aliases.items():
        if any(key in metric_key for key in keys):
            try:
                return target, float(raw_value)
            except (TypeError, ValueError):
                return None
    return None


def _labsim_assay_targets(profile_id: str, measurements: dict[str, float] | None = None) -> dict[str, float]:
    targets = {
        "bsf_sludge_heavy_metal_redline": {
            "biomass": 0.72,
            "substrate": 3.85,
            "moisture": 74.0,
            "heavy_metal_index": 0.82,
        },
        "grub_manure_humus_lane": {
            "biomass": 0.86,
            "substrate": 4.1,
            "moisture": 70.5,
            "heavy_metal_index": 0.42,
        },
        "mealworm_straw_distillers_lane": {
            "biomass": 0.66,
            "substrate": 3.9,
            "moisture": 57.0,
            "heavy_metal_index": 0.20,
        },
        "bsf_distillers_grain_lane": {
            "biomass": 1.08,
            "substrate": 4.6,
            "moisture": 68.5,
            "heavy_metal_index": 0.17,
        },
    }
    default_targets = targets.get(
        profile_id,
        {
            "biomass": 0.75,
            "substrate": 4.2,
            "moisture": 68.0,
            "heavy_metal_index": 0.50,
        },
    )
    if not measurements:
        return default_targets
    merged = dict(default_targets)
    merged.update(measurements)
    return merged


def _labsim_assay_comparison(
    *,
    cycle_payload: dict,
    lab_profile: dict,
    measurements: dict[str, float] | None = None,
    measurement_source: dict | None = None,
) -> dict:
    if measurements and measurement_source is None:
        measurement_source = _labsim_assay_source(measurements)
    targets = _labsim_assay_targets(str(lab_profile["profile_id"]), measurements)
    state_after = cycle_payload.get("state_after") or {}
    predicted = {
        "biomass": round(float(state_after.get("biomass", 0.0)), 4),
        "substrate": round(float(state_after.get("substrate", 0.0)), 4),
        "moisture": round(float(state_after.get("moisture", 0.0)), 4),
        "heavy_metal_index": round(float(lab_profile["max_heavy_metal_risk"]), 4),
    }
    residuals = {
        key: round(predicted[key] - targets[key], 4)
        for key in targets
    }
    tolerance = {
        "biomass": 0.35,
        "substrate": 1.25,
        "moisture": 6.0,
        "heavy_metal_index": 0.05,
    }
    out_of_band = [
        key
        for key, residual in residuals.items()
        if abs(residual) > tolerance[key]
    ]
    comparison = {
        "source_kind": _lab_assay_source_kind(measurement_source),
        "source_ref": _lab_assay_source_ref(measurement_source, lab_profile),
        "review_status": _lab_assay_source_review_status(measurement_source, lab_profile),
        "measurement_mode": _lab_assay_measurement_mode(measurement_source),
        "predicted": predicted,
        "measured_anchor": targets,
        "residuals": residuals,
        "out_of_band": out_of_band,
        "calibration_status": "review_required" if out_of_band or lab_profile["review_status"] == "human_review_required" else "within_screening_band",
    }
    if measurement_source is not None:
        for key in (
            "human_review_required",
            "numeric_values_included",
            "release_evidence_allowed",
            "runtime_activation_enabled",
            "validated_default_write_enabled",
            "promotion_enabled",
        ):
            if key in measurement_source:
                comparison[key] = measurement_source[key]
    return comparison


def _reference_review_status(payload: dict, source_type: str) -> str:
    if payload.get("campaign_type") == "literature_extraction_candidate" and payload.get("review_status"):
        return str(payload["review_status"])
    if payload.get("human_review_required") is True:
        return "human_review_required"
    staging_meta = payload.get("staging_meta")
    if isinstance(staging_meta, dict) and staging_meta.get("human_review_required") is True:
        return "human_review_required"
    if payload.get("review_status"):
        return str(payload["review_status"])
    if payload.get("status") in {"staged", "pending_review"}:
        return "pending_review"
    if source_type in {"staged_reference", "promoted_campaign"}:
        return "pending_review"
    return "review_required"


def _reference_human_review_required(payload: dict, review_status: str) -> bool:
    if payload.get("human_review_required") is True:
        return True
    staging_meta = payload.get("staging_meta")
    if isinstance(staging_meta, dict) and staging_meta.get("human_review_required") is True:
        return True
    return review_status in {"pending_review", "review_required", "human_review_required"}


def _reference_lab_assay_measurements(payload: dict) -> dict[str, float] | None:
    if payload.get("numeric_values_included") is False:
        return None
    observed_outputs = dict(payload.get("observed_outputs") or {})
    key_parameters = dict(payload.get("key_parameters") or {})
    search_payloads = [observed_outputs, key_parameters, payload]
    measurements: dict[str, float] = {}
    alias_map: dict[str, tuple[str, ...]] = {
        "biomass": (
            "lab_assay_biomass",
            "measured_biomass",
            "final_biomass",
            "biomass",
            "biomass_kg",
            "larval_biomass",
            "larvae_biomass",
        ),
        "substrate": (
            "lab_assay_substrate",
            "measured_substrate",
            "final_substrate",
            "residual_substrate",
            "substrate_remaining",
            "substrate",
            "substrate_g",
        ),
        "moisture": (
            "lab_assay_moisture",
            "measured_moisture",
            "final_moisture",
            "moisture_pct",
            "moisture_percent",
            "moisture",
        ),
        "heavy_metal_index": (
            "lab_assay_heavy_metal_index",
            "measured_heavy_metal_index",
            "heavy_metal_index",
            "heavy_metals_index",
            "heavy_metal_risk",
            "risk_index",
        ),
    }
    for field, aliases in alias_map.items():
        for candidate in search_payloads:
            value = _numeric_metric_value(candidate, aliases)
            if value is not None:
                measurements[field] = value
                break

    candidate_metric = _reference_metric_from_candidate(payload)
    if candidate_metric is not None:
        field, value = candidate_metric
        measurements.setdefault(field, value)

    if "moisture" in measurements:
        measurements["moisture"] = max(0.0, min(100.0, measurements["moisture"]))
    if "heavy_metal_index" in measurements:
        value = measurements["heavy_metal_index"]
        measurements["heavy_metal_index"] = max(0.0, min(1.0, value / 100.0 if value > 1.0 else value))
    return _valid_assay_measurements(measurements)


def _reference_lab_assay_field_sources(payload: dict) -> dict[str, str]:
    measurements = _reference_lab_assay_measurements(payload)
    if not measurements:
        return {}
    return {
        f"lab_assay_measurements.{field}": "reference.lab_assay_measurements"
        for field in measurements
    }


def _reference_lab_assay_source(
    *,
    measurements: dict[str, float],
    metadata: SimulationScenarioImportMetadata,
    payload: dict,
) -> dict:
    source = _labsim_assay_source(
        measurements,
        source_kind=metadata.reference_source,
        source_ref=metadata.reference_id,
        confidence=metadata.extraction_confidence,
        notes="review-gated measured assay values imported from reference/candidate evidence",
        measurement_mode="reference_imported",
        review_status=_reference_review_status(payload, metadata.reference_source),
    )
    source["human_review_required"] = metadata.human_review_required
    source["numeric_values_included"] = metadata.numeric_values_included
    source["release_evidence_allowed"] = metadata.release_evidence_allowed
    source["runtime_activation_enabled"] = metadata.runtime_activation_enabled
    source["validated_default_write_enabled"] = metadata.validated_default_write_enabled
    source["promotion_enabled"] = metadata.promotion_enabled
    return source


def _reference_scenario_sources(metadata: SimulationScenarioImportMetadata) -> list[dict]:
    sources: list[dict] = []
    source_ref = metadata.reference_id
    for field, source in metadata.field_sources.items():
        fallback = source.startswith("fallback.")
        kind = "fallback_default" if fallback else metadata.reference_source
        sources.append(
            _source(
                field,
                kind,
                source_ref=source_ref,
                confidence=metadata.extraction_confidence if not fallback else 0.55,
                fallback_used=fallback,
                notes=source,
            )
        )
    sources.extend(
        [
            _source("scenario", metadata.reference_source, source_ref=source_ref, confidence=metadata.extraction_confidence),
            _source("cycles", "operator_input"),
            _source("seed", "operator_input"),
            _source("policy", "operator_input"),
        ]
    )
    return sources


def _confidence_band_payload(lower: float, median: float, upper: float) -> dict[str, float]:
    return {
        "lower": round(_clamp(lower), 4),
        "median": round(_clamp(median), 4),
        "upper": round(_clamp(upper), 4),
    }


def _apply_chronos_risk_contract(result: dict) -> dict:
    """Enrich deterministic simulation risk with Chronos when available."""
    cycles = result.get("cycles") or []
    history: list[float] = []
    for cycle in cycles:
        risk_prediction = dict(cycle["risk_prediction"])
        deterministic_score = float(risk_prediction["future_risk_score"])
        history.append(deterministic_score)
        try:
            forecast = forecast_with_chronos_or_fallback(
                sensor_history=history,
                horizon=6,
                metric_name="simulation_lab_cycle_risk",
                batch=None,
            )
        except Exception as exc:
            risk_prediction.update(
                {
                    "source": "deterministic_proxy",
                    "execution_mode": "fallback",
                    "confidence_band": _confidence_band_payload(
                        deterministic_score - 0.05,
                        deterministic_score,
                        deterministic_score + 0.05,
                    ),
                    "chronos_warning": f"Chronos adapter failed; deterministic proxy preserved: {exc}",
                }
            )
            cycle["risk_prediction"] = risk_prediction
            continue

        if forecast.fallback_used:
            risk_prediction.update(
                {
                    "source": "deterministic_proxy",
                    "execution_mode": "fallback",
                    "confidence_band": _confidence_band_payload(
                        deterministic_score - 0.05,
                        deterministic_score,
                        deterministic_score + 0.05,
                    ),
                    "model_name": "simulation_lab_deterministic_proxy",
                    "chronos_execution_mode": forecast.execution_mode,
                }
            )
            if forecast.warnings:
                risk_prediction["chronos_warning"] = forecast.warnings[0]
        else:
            projected = mean(forecast.forecast) if forecast.forecast else deterministic_score
            projected_score = _clamp(projected)
            lower, upper = forecast.confidence_band
            risk_prediction.update(
                {
                    "source": "chronos",
                    "execution_mode": forecast.execution_mode,
                    "model_name": forecast.model_name,
                    "future_risk_score": round(projected_score, 4),
                    "release_warning_score": round(
                        _clamp(float(risk_prediction["release_warning_score"]) + (projected_score - deterministic_score) * 0.35),
                        4,
                    ),
                    "confidence_band": _confidence_band_payload(lower, projected_score, upper),
                    "deterministic_fallback": {
                        "future_risk_score": deterministic_score,
                        "release_warning_score": risk_prediction["release_warning_score"],
                    },
                }
            )
        cycle["risk_prediction"] = risk_prediction
    if cycles:
        risks = [float(cycle["risk_prediction"]["future_risk_score"]) for cycle in cycles]
        result["summary"]["starting_risk"] = round(risks[0], 4)
        result["summary"]["ending_risk"] = round(risks[-1], 4)
        result["summary"]["risk_delta"] = round(risks[-1] - risks[0], 4)
    return result


def _scenario_response(record: SimulationScenarioRecord) -> SimulationScenarioResponse:
    return SimulationScenarioResponse(
        simulation_id=record.simulation_id,
        batch_id=record.batch_id,
        tenant_id=record.tenant_id,
        species=record.species,
        feedstock=record.feedstock,
        scenario=record.scenario,
        initial_state=record.initial_state,
        cycles=record.cycles,
        seed=record.seed,
        policy=record.policy,
        lab_assay_measurements=_scenario_lab_assay_measurements(record),
        evidence_sources=record.evidence_sources or [],
        status=record.status,
        created_at=record.created_at,
    )


async def _literature_candidate_payload_from_source(
    db: AsyncSession,
    *,
    tenant_id: int,
    reference_id: str,
) -> tuple[str, dict] | None:
    record = await db.scalar(
        select(LiteratureExtractionCandidateRecord)
        .where(
            LiteratureExtractionCandidateRecord.tenant_id == tenant_id,
            LiteratureExtractionCandidateRecord.candidate_id == reference_id,
        )
        .limit(1)
    )
    if record is None:
        return None
    numeric_values_included = bool(record.numeric_values_included)
    return (
        str(record.source_kind),
        {
            "title": record.title,
            "species_chain": [record.species],
            "feedstocks": [record.feedstock],
            "campaign_type": "literature_extraction_candidate",
            "evidence_level": "candidate_raw_value_pending_review",
            "summary": record.extraction_note,
            "source_anchor": record.table_or_section_ref,
            "source_ref": record.source_ref,
            "source_id": record.source_id,
            "metric_key": record.metric_key,
            "metric_label": record.metric_label,
            "raw_value": record.raw_value if numeric_values_included else None,
            "unit": record.unit,
            "condition_context": record.condition_context,
            "experiment_context": record.experiment_context,
            "license_note": record.license_note,
            "source_kind": record.source_kind,
            "review_status": record.review_status,
            "human_review_required": record.human_review_required,
            "numeric_values_included": numeric_values_included,
            "release_evidence_allowed": record.release_evidence_allowed,
            "runtime_activation_enabled": record.runtime_activation_enabled,
            "validated_default_write_enabled": record.validated_default_write_enabled,
            "promotion_enabled": record.promotion_enabled,
            "guardrails": list(record.guardrails or []),
            "observed_outputs": {record.metric_key: record.raw_value} if numeric_values_included else {},
            "key_parameters": {},
        },
    )


async def _reference_payload_from_source(
    db: AsyncSession,
    *,
    tenant_id: int,
    reference_id: str,
) -> tuple[str, dict] | None:
    staged = reference_ingestion_service.get_staged_item(tenant_id, reference_id)
    if staged is not None:
        return (
            "staged_reference",
            {
                "title": staged.source_title,
                "species_chain": staged.species_chain,
                "feedstocks": staged.feedstocks,
                "key_parameters": staged.key_parameters,
                "observed_outputs": staged.observed_outputs,
                "summary": staged.summary,
                "source_anchor": staged.source_anchor,
                "source_owner": staged.source_owner,
                "license_note": staged.license_note,
                "ingestion_mode": staged.ingestion_mode,
                "human_review_required": staged.human_review_required,
                "review_status": staged.status,
            },
        )

    promoted = reference_ingestion_service.get_promoted_campaign(tenant_id, reference_id)
    if promoted is not None:
        return "promoted_campaign", promoted

    manuscript = get_campaign(reference_id)
    if manuscript is not None:
        return "manuscript_campaign", manuscript
    literature_candidate = await _literature_candidate_payload_from_source(
        db,
        tenant_id=tenant_id,
        reference_id=reference_id,
    )
    if literature_candidate is not None:
        return literature_candidate
    return None


def _scenario_from_reference_payload(
    *,
    reference_id: str,
    source_type: str,
    payload: dict,
    request: SimulationScenarioImportRequest,
) -> tuple[SimulationScenarioCreate, SimulationScenarioImportMetadata]:
    fallbacks: list[str] = []
    field_sources: dict[str, str] = {}
    species_chain = list(payload.get("species_chain") or [])
    feedstocks = list(payload.get("feedstocks") or [])
    key_parameters = dict(payload.get("key_parameters") or {})
    observed_outputs = dict(payload.get("observed_outputs") or {})
    lab_assay_measurements = _reference_lab_assay_measurements(payload)

    species = species_chain[-1] if species_chain else "BSF"
    field_sources["species"] = "reference.species_chain" if species_chain else "fallback.default_bsf"
    if not species_chain:
        fallbacks.append("species defaulted to BSF")

    feedstock = feedstocks[0] if feedstocks else "mixed_food_waste"
    field_sources["feedstock"] = "reference.feedstocks" if feedstocks else "fallback.mixed_food_waste"
    if not feedstocks:
        fallbacks.append("feedstock defaulted to mixed_food_waste")

    temperature = float(key_parameters.get("kernel_temperature_c") or key_parameters.get("washing_temperature_c") or 28.0)
    moisture = float(
        key_parameters.get("kernel_target_moisture_pct")
        or (key_parameters.get("initial_moisture_pct_range") or [70.0])[-1]
        or 70.0
    )
    if "kernel_temperature_c" in key_parameters or "washing_temperature_c" in key_parameters:
        field_sources["initial_state.temperature"] = "reference.key_parameters"
    else:
        field_sources["initial_state.temperature"] = "fallback.default_temperature"
        fallbacks.append("temperature defaulted to 28C")
    if "kernel_target_moisture_pct" in key_parameters or "initial_moisture_pct_range" in key_parameters:
        field_sources["initial_state.moisture"] = "reference.key_parameters"
    else:
        field_sources["initial_state.moisture"] = "fallback.default_moisture"
        fallbacks.append("moisture defaulted to 70%")

    scenario = "moisture_drift"
    if "moisture_gradient_pct" in key_parameters or moisture > 76 or moisture < 62:
        scenario = "moisture_drift"
    elif "risk" in str(payload.get("campaign_type", "")).lower():
        scenario = "temperature_spike"
    elif "best_single_stage_ser" in observed_outputs:
        scenario = "underfeeding"

    extraction_confidence = round(
        min(1.0, 0.45 + 0.12 * bool(species_chain) + 0.12 * bool(feedstocks) + 0.08 * bool(key_parameters) + 0.08 * bool(observed_outputs)),
        3,
    )
    field_sources.update(_reference_lab_assay_field_sources(payload))
    create_payload = SimulationScenarioCreate(
        species=species,
        feedstock=feedstock,
        scenario=scenario,
        cycles=request.cycles,
        seed=request.seed,
        policy=request.policy,
        initial_state={
            "biomass": 0.5,
            "substrate": float(key_parameters.get("total_substrate_g") or key_parameters.get("dry_mass_per_compartment_g") or 10.0),
            "temperature": temperature,
            "moisture": max(0.0, min(100.0, moisture)),
            "nitrogen": 50.0,
        },
        lab_assay_measurements=lab_assay_measurements,
    )
    review_status = _reference_review_status(payload, source_type)
    metadata = SimulationScenarioImportMetadata(
        reference_id=reference_id,
        reference_source=source_type,
        source_title=str(payload.get("title") or request.scenario_name or reference_id),
        review_status=review_status,
        human_review_required=_reference_human_review_required(payload, review_status),
        numeric_values_included=payload.get("numeric_values_included") is not False,
        release_evidence_allowed=bool(payload.get("release_evidence_allowed") is True),
        runtime_activation_enabled=bool(payload.get("runtime_activation_enabled") is True),
        validated_default_write_enabled=bool(payload.get("validated_default_write_enabled") is True),
        promotion_enabled=bool(payload.get("promotion_enabled") is True),
        extraction_confidence=extraction_confidence,
        field_sources=field_sources,
        fallbacks=fallbacks,
        environmental_drift_assumptions={
            "scenario": scenario,
            "source_anchor": payload.get("source_anchor"),
            "summary": payload.get("summary"),
        },
        expected_risk_constraints={
            "hardware_execution": False,
            "release_decision_impact": "appendix_only",
            "visual_observation_source": "synthetic_visual_mock",
        },
    )
    return create_payload, metadata


def _cycle_response(record: SimulationCycleRecord) -> SimulationLabCycleResponse:
    return SimulationLabCycleResponse(
        cycle=record.cycle_index,
        timestamp=record.timestamp,
        state_before=record.state_before,
        sensor_observation=record.sensor_observation,
        supervisor_decision=record.supervisor_decision,
        risk_prediction=record.risk_prediction,
        visual_observation=record.visual_observation,
        evidence_sources=record.evidence_sources or [],
        agent_action=record.agent_action,
        actuator_result=record.actuator_result,
        state_after=record.state_after,
        audit_event={},
    )


def _summary_response(summary: dict) -> SimulationLabSummaryResponse:
    return SimulationLabSummaryResponse(**summary)


def _run_history_item(record: SimulationRunRecord) -> SimulationLabRunHistoryItem:
    summary = record.summary
    return SimulationLabRunHistoryItem(
        run_id=record.run_id,
        simulation_id=record.simulation_id,
        tenant_id=record.tenant_id,
        policy=record.policy,
        status=record.status,
        engine_version=record.engine_version,
        model_version=record.model_version,
        input_snapshot_id=record.input_snapshot_id,
        input_snapshot_hash=record.input_snapshot_hash,
        replay_of_run_id=record.replay_of_run_id,
        evidence_pack_id=record.evidence_pack_id,
        cycle_count=summary["cycle_count"],
        starting_risk=summary["starting_risk"],
        ending_risk=summary["ending_risk"],
        risk_delta=summary["risk_delta"],
        action_count=summary["action_count"],
        audit_event_count=summary["audit_event_count"],
        final_state=summary["final_state"],
        started_at=record.started_at,
        completed_at=record.completed_at,
        created_at=record.created_at,
    )


async def create_scenario(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: SimulationScenarioCreate,
    evidence_sources: list[dict] | None = None,
) -> SimulationScenarioResponse:
    simulation_id = _new_simulation_id()
    batch_suffix = simulation_id.rsplit("-", 1)[-1]
    scenario_sources = list(evidence_sources or _operator_scenario_sources())
    scenario_sources.extend(_labsim_scenario_sources(species=payload.species, feedstock=payload.feedstock))
    assay_measurements = _valid_assay_measurements(
        payload.lab_assay_measurements.model_dump(exclude_none=True)
        if payload.lab_assay_measurements
        else None
    )
    if assay_measurements and not any(source.get("field") == "lab_assay_measurements" for source in scenario_sources):
        scenario_sources.append(_labsim_assay_source(assay_measurements))
    scenario = SimulationScenarioRecord(
        simulation_id=simulation_id,
        batch_id=f"VIRTUAL-{payload.species.upper()}-{batch_suffix}",
        tenant_id=tenant_id,
        user_id=user_id,
        species=payload.species,
        feedstock=payload.feedstock,
        scenario=payload.scenario,
        initial_state=jsonable_encoder(payload.initial_state),
        cycles=payload.cycles,
        seed=payload.seed,
        policy=payload.policy,
        evidence_sources=scenario_sources,
        status="created",
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return _scenario_response(scenario)


async def import_scenario_from_reference(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: SimulationScenarioImportRequest,
) -> SimulationScenarioImportResponse | None:
    source = await _reference_payload_from_source(db, tenant_id=tenant_id, reference_id=payload.reference_id)
    if source is None:
        return None
    source_type, reference_payload = source
    create_payload, metadata = _scenario_from_reference_payload(
        reference_id=payload.reference_id,
        source_type=source_type,
        payload=reference_payload,
        request=payload,
    )
    scenario_sources = _reference_scenario_sources(metadata)
    assay_measurements = _valid_assay_measurements(
        create_payload.lab_assay_measurements.model_dump(exclude_none=True)
        if create_payload.lab_assay_measurements
        else None
    )
    if assay_measurements:
        scenario_sources.append(
            _reference_lab_assay_source(
                measurements=assay_measurements,
                metadata=metadata,
                payload=reference_payload,
            )
        )
    scenario = await create_scenario(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=create_payload,
        evidence_sources=scenario_sources,
    )
    return SimulationScenarioImportResponse(scenario=scenario, import_metadata=metadata)


async def list_scenarios(
    db: AsyncSession,
    *,
    tenant_id: int,
    batch_id: str | None = None,
    species: str | None = None,
    feedstock: str | None = None,
    limit: int = 50,
) -> list[SimulationScenarioResponse]:
    query = select(SimulationScenarioRecord).where(SimulationScenarioRecord.tenant_id == tenant_id)
    if batch_id:
        query = query.where(SimulationScenarioRecord.batch_id == batch_id)
    if species:
        query = query.where(SimulationScenarioRecord.species == species)
    if feedstock:
        query = query.where(SimulationScenarioRecord.feedstock == feedstock)
    result = await db.execute(query.order_by(desc(SimulationScenarioRecord.created_at)).limit(limit))
    return [_scenario_response(item) for item in result.scalars().all()]


async def get_scenario(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationScenarioResponse | None:
    record = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    return _scenario_response(record) if record else None


async def _get_scenario_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationScenarioRecord | None:
    result = await db.execute(
        select(SimulationScenarioRecord).where(
            SimulationScenarioRecord.simulation_id == simulation_id,
            SimulationScenarioRecord.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def _latest_run_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationRunRecord | None:
    result = await db.execute(
        select(SimulationRunRecord)
        .where(
            SimulationRunRecord.simulation_id == simulation_id,
            SimulationRunRecord.tenant_id == tenant_id,
        )
        .order_by(desc(SimulationRunRecord.created_at), desc(SimulationRunRecord.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _run_record_by_public_id(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
    run_id: str,
) -> SimulationRunRecord | None:
    result = await db.execute(
        select(SimulationRunRecord).where(
            SimulationRunRecord.run_id == run_id,
            SimulationRunRecord.simulation_id == simulation_id,
            SimulationRunRecord.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def _run_record_by_public_id_any_simulation(
    db: AsyncSession,
    *,
    tenant_id: int,
    run_id: str,
) -> SimulationRunRecord | None:
    result = await db.execute(
        select(SimulationRunRecord).where(
            SimulationRunRecord.run_id == run_id,
            SimulationRunRecord.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def _run_records_for_simulation(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> list[SimulationRunRecord]:
    result = await db.execute(
        select(SimulationRunRecord)
        .where(
            SimulationRunRecord.simulation_id == simulation_id,
            SimulationRunRecord.tenant_id == tenant_id,
        )
        .order_by(desc(SimulationRunRecord.created_at), desc(SimulationRunRecord.id))
    )
    return list(result.scalars().all())


async def _cycle_records(
    db: AsyncSession,
    *,
    run: SimulationRunRecord,
) -> list[SimulationCycleRecord]:
    result = await db.execute(
        select(SimulationCycleRecord)
        .where(
            SimulationCycleRecord.run_id == run.id,
            SimulationCycleRecord.tenant_id == run.tenant_id,
        )
        .order_by(SimulationCycleRecord.cycle_index)
    )
    return list(result.scalars().all())


async def _audit_payloads(
    db: AsyncSession,
    *,
    run: SimulationRunRecord,
) -> list[dict]:
    result = await db.execute(
        select(SimulationAuditEventRecord)
        .where(
            SimulationAuditEventRecord.run_id == run.id,
            SimulationAuditEventRecord.tenant_id == run.tenant_id,
        )
        .order_by(SimulationAuditEventRecord.cycle_index, SimulationAuditEventRecord.id)
    )
    return [item.event_payload for item in result.scalars().all()]


async def _audit_hashes(
    db: AsyncSession,
    *,
    run: SimulationRunRecord,
) -> list[SimulationReleaseAppendixAuditHash]:
    result = await db.execute(
        select(SimulationAuditEventRecord)
        .where(
            SimulationAuditEventRecord.run_id == run.id,
            SimulationAuditEventRecord.tenant_id == run.tenant_id,
        )
        .order_by(SimulationAuditEventRecord.cycle_index, SimulationAuditEventRecord.id)
    )
    return [
        SimulationReleaseAppendixAuditHash(
            cycle=item.cycle_index,
            event_type=item.event_type,
            payload_hash=item.payload_hash,
            recorded_at=item.recorded_at,
        )
        for item in result.scalars().all()
    ]


async def _persist_simulation_result(
    db: AsyncSession,
    *,
    scenario: SimulationScenarioRecord,
    tenant_id: int,
    user_id: int,
    policy: SimulationPolicy,
    replay_of_run_id: str | None = None,
) -> tuple[SimulationRunRecord, SimulationLabSummaryResponse, list[SimulationLabCycleResponse]]:
    lab_profile = _labsim_profile(species=scenario.species, feedstock=scenario.feedstock)
    assay_source = _scenario_lab_assay_source(scenario)
    assay_measurements = _scenario_lab_assay_measurements(scenario)
    result = _apply_chronos_risk_contract(run_simulation_lab(
        SimulationLabConfig(
            simulation_id=scenario.simulation_id,
            batch_id=scenario.batch_id,
            species=scenario.species,
            feedstock=scenario.feedstock,
            scenario=scenario.scenario,
            initial_state=scenario.initial_state,
            cycles=scenario.cycles,
            seed=scenario.seed,
            policy=policy,
        )
    ))
    now = datetime.now(UTC)
    summary = jsonable_encoder(result["summary"])
    snapshot = await create_input_snapshot(
        db,
        tenant_id=tenant_id,
        subject_type="simulation_run",
        subject_id=scenario.simulation_id,
        payload={
            "simulation_id": scenario.simulation_id,
            "batch_id": scenario.batch_id,
            "species": scenario.species,
            "feedstock": scenario.feedstock,
            "scenario": scenario.scenario,
            "initial_state": scenario.initial_state,
            "cycles": scenario.cycles,
            "seed": scenario.seed,
            "policy": policy,
            "engine_version": SIMULATION_ENGINE_VERSION,
            "lab_profile": lab_profile,
            "lab_assay_measurements": assay_measurements,
        },
    )
    run_record = SimulationRunRecord(
        run_id=f"RUN-{scenario.simulation_id}-{uuid.uuid4().hex[:6].upper()}",
        scenario_id=scenario.id,
        simulation_id=scenario.simulation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        policy=policy,
        status="completed",
        summary=summary,
        engine_version=SIMULATION_ENGINE_VERSION,
        model_version=SIMULATION_MODEL_VERSION,
        input_snapshot_id=snapshot.input_snapshot_id,
        input_snapshot_hash=snapshot.payload_hash,
        replay_of_run_id=replay_of_run_id,
        started_at=now,
        completed_at=now,
    )
    db.add(run_record)
    await db.flush()

    cycle_responses: list[SimulationLabCycleResponse] = []
    for cycle in result["cycles"]:
        cycle_payload = jsonable_encoder(cycle)
        audit_payload = cycle_payload["audit_event"]
        risk_payload = cycle_payload["risk_prediction"]
        risk_payload["lab_governance"] = {
            "profile_id": lab_profile["profile_id"],
            "heavy_metal_gate": lab_profile["heavy_metal_gate"],
            "product_use_lock": lab_profile["product_use_lock"],
            "review_status": lab_profile["review_status"],
        }
        assay_comparison = _labsim_assay_comparison(
            cycle_payload=cycle_payload,
            lab_profile=lab_profile,
            measurements=assay_measurements,
            measurement_source=assay_source,
        )
        risk_payload["lab_assay_comparison"] = assay_comparison
        audit_payload["lab_governance"] = lab_profile
        audit_payload["lab_assay_comparison"] = assay_comparison
        if "lab_governance_gate" not in audit_payload.get("evidence_chain", []):
            audit_payload.setdefault("evidence_chain", []).append("lab_governance_gate")
        if "lab_assay_calibration" not in audit_payload.get("evidence_chain", []):
            audit_payload.setdefault("evidence_chain", []).append("lab_assay_calibration")
        cycle_sources = _cycle_evidence_sources(cycle_payload)
        cycle_payload["evidence_sources"] = cycle_sources
        audit_payload["evidence_sources"] = cycle_sources
        cycle_record = SimulationCycleRecord(
            run_id=run_record.id,
            simulation_id=scenario.simulation_id,
            tenant_id=tenant_id,
            cycle_index=cycle_payload["cycle"],
            timestamp=cycle["timestamp"],
            state_before=cycle_payload["state_before"],
            sensor_observation=cycle_payload["sensor_observation"],
            supervisor_decision=cycle_payload["supervisor_decision"],
            risk_prediction=cycle_payload["risk_prediction"],
            visual_observation=cycle_payload.get("visual_observation"),
            evidence_sources=cycle_sources,
            agent_action=cycle_payload["agent_action"],
            actuator_result=cycle_payload["actuator_result"],
            state_after=cycle_payload["state_after"],
        )
        db.add(cycle_record)
        await db.flush()
        db.add(
            SimulationAuditEventRecord(
                run_id=run_record.id,
                cycle_id=cycle_record.id,
                simulation_id=scenario.simulation_id,
                tenant_id=tenant_id,
                cycle_index=cycle_payload["cycle"],
                event_type=audit_payload.get("event_type", "simulation_lab_cycle"),
                evidence_chain=audit_payload.get("evidence_chain"),
                event_payload=audit_payload,
                payload_hash=_payload_hash(audit_payload),
                recorded_at=cycle["timestamp"],
            )
        )
        cycle_responses.append(SimulationLabCycleResponse(**cycle_payload))

    evidence_pack = await _create_simulation_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scenario=scenario,
        run_record=run_record,
        summary=summary,
        cycle_responses=cycle_responses,
        snapshot_id=snapshot.input_snapshot_id,
    )
    run_record.evidence_pack_id = evidence_pack.evidence_pack_id
    await db.flush()

    return run_record, _summary_response(summary), cycle_responses


def _cycle_evidence_sources(cycle_payload: dict) -> list[dict]:
    risk = cycle_payload.get("risk_prediction") or {}
    risk_source = risk.get("source")
    if risk_source == "chronos":
        risk_kind = "chronos_model"
        fallback = False
        confidence = 0.82
    elif risk.get("chronos_warning") or risk.get("execution_mode") == "fallback":
        risk_kind = "fallback_default"
        fallback = True
        confidence = 0.62
    else:
        risk_kind = "deterministic_model"
        fallback = False
        confidence = 0.74
    sources = [
        _source("sensor_observation", "synthetic", source_ref=cycle_payload.get("sensor_observation", {}).get("simulation_id")),
        _source("visual_observation", "synthetic", source_ref=cycle_payload.get("visual_observation", {}).get("frame_id")),
        _source("risk_prediction", risk_kind, source_ref=risk.get("model_name"), confidence=confidence, fallback_used=fallback),
        _source("agent_action", "deterministic_model", source_ref=cycle_payload.get("agent_action", {}).get("policy")),
        _source("actuator_result", "synthetic", notes="virtual actuator dry-run; no hardware execution"),
    ]
    lab_governance = (cycle_payload.get("audit_event") or {}).get("lab_governance") or risk.get("lab_governance")
    if lab_governance:
        sources.extend(
            [
                _source(
                    "lab_governance",
                    "official_standard",
                    source_ref=lab_governance.get("standard_refs", LABSIM_STANDARD_REFS),
                    confidence=0.82,
                    notes=lab_governance.get("review_status"),
                ),
                _source(
                    "cycle_heavy_metal_gate",
                    "official_standard",
                    source_ref=lab_governance.get("standard_refs", LABSIM_STANDARD_REFS),
                    confidence=0.82,
                    fallback_used=str(lab_governance.get("heavy_metal_gate", "")).startswith("unknown"),
                    notes=lab_governance.get("heavy_metal_gate"),
                ),
            ]
        )
    assay_comparison = (cycle_payload.get("audit_event") or {}).get("lab_assay_comparison") or risk.get("lab_assay_comparison")
    if assay_comparison:
        sources.append(
            _source(
                "lab_assay_comparison",
                "manuscript_campaign",
                source_ref=assay_comparison.get("source_ref"),
                confidence=0.78,
                fallback_used=bool(assay_comparison.get("out_of_band")),
                notes=assay_comparison.get("calibration_status"),
            )
        )
    return sources


async def _create_simulation_evidence_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    scenario: SimulationScenarioRecord,
    run_record: SimulationRunRecord,
    summary: dict,
    cycle_responses: list[SimulationLabCycleResponse],
    snapshot_id: str,
):
    missing_source = any(source.get("fallback_used") for source in (scenario.evidence_sources or []))
    fallback_risk = any(
        source.source_kind == "fallback_default"
        for cycle in cycle_responses
        for source in cycle.evidence_sources
    )
    items = [
        EvidenceItemCreate(
            kind="input_snapshot",
            source_kind="operator_input",
            source_ref=snapshot_id,
            payload={"input_snapshot_id": snapshot_id, "hash": run_record.input_snapshot_hash},
        ),
        EvidenceItemCreate(
            kind="simulation_summary",
            source_kind="deterministic_model",
            source_ref=SIMULATION_ENGINE_VERSION,
            payload=summary,
            uncertainty_level="medium" if fallback_risk else "low",
        ),
    ]
    for source in scenario.evidence_sources or []:
        items.append(
            EvidenceItemCreate(
                kind="scenario_source",
                source_kind=source["source_kind"],
                source_ref=source.get("source_ref"),
                payload=source,
                confidence=source.get("confidence", 1.0),
                uncertainty_level="medium" if source.get("fallback_used") else "low",
            )
        )
    return await create_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=EvidencePackCreate(
            subject_type="simulation_run",
            subject_id=run_record.run_id,
            title=f"Simulation evidence for {scenario.simulation_id}",
            summary=f"Virtual run completed with ending risk {summary['ending_risk']}.",
            verification_status="review_required" if fallback_risk or missing_source else "verified",
            human_review_required=bool(fallback_risk or missing_source or summary["ending_risk"] >= 0.68),
            items=items,
        ),
    )


async def run_scenario(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    simulation_id: str,
) -> SimulationLabRunResponse | None:
    scenario = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if scenario is None:
        return None

    _run_record, summary, cycle_responses = await _persist_simulation_result(
        db,
        scenario=scenario,
        tenant_id=tenant_id,
        user_id=user_id,
        policy=scenario.policy,
    )
    scenario.status = "completed"
    await db.commit()
    await db.refresh(scenario)
    return SimulationLabRunResponse(
        scenario=_scenario_response(scenario),
        summary=summary,
        cycles=cycle_responses,
    )


def _ordered_unique_policies(
    policies: list[SimulationPolicy],
    baseline_policy: SimulationPolicy,
) -> list[SimulationPolicy]:
    ordered: list[SimulationPolicy] = []
    for policy in [baseline_policy, *policies]:
        if policy not in ordered:
            ordered.append(policy)
    return ordered


def _comparison_metrics(
    *,
    initial_state: dict,
    summary: SimulationLabSummaryResponse,
    cycles: list[SimulationLabCycleResponse],
) -> SimulationPolicyComparisonMetrics:
    human_review_count = sum(
        1 for cycle in cycles if cycle.agent_action.get("recommended_action") == "request_human_review"
    )
    energy_kwh = 0.0
    water_kg = 0.0
    labor_hours = 0.0
    nh3_values: list[float] = []
    moisture_values: list[float] = []
    missing_evidence = ["assay.release_quality", "emission_factor.site_specific", "cost_factor.site_specific"]
    for cycle in cycles:
        action = cycle.agent_action.get("recommended_action")
        intensity = float(cycle.agent_action.get("intensity") or 0)
        duration_hours = float(cycle.agent_action.get("duration_minutes") or 0) / 60
        if action == "aerate":
            energy_kwh += 0.42 * intensity * duration_hours
        elif action == "cool":
            energy_kwh += 0.68 * intensity * duration_hours
        elif action == "request_human_review":
            labor_hours += 0.25
        labor_hours += 0.03
        moisture = float(cycle.sensor_observation.get("moisture") or 70.0)
        nh3 = float(cycle.sensor_observation.get("nh3") or 0.0)
        moisture_values.append(moisture)
        nh3_values.append(nh3)
        if moisture < 62:
            water_kg += (62 - moisture) * 0.018
    biomass_gain = round(float(summary.final_state["biomass"]) - float(initial_state["biomass"]), 4)
    substrate_use = round(float(initial_state["substrate"]) - float(summary.final_state["substrate"]), 4)
    audit_completeness = round(summary.audit_event_count / max(summary.cycle_count, 1), 4)
    mortality_risk = round(_clamp(summary.ending_risk * 0.62 + human_review_count * 0.03), 4)
    moisture_risk = round(_clamp(max((abs(value - 68.0) / 35.0 for value in moisture_values), default=0.0)), 4)
    nh3_risk = round(_clamp(max(((value - 3.0) / 6.0 for value in nh3_values), default=0.0)), 4)
    co2e = round(energy_kwh * 0.42, 4)
    gross_margin = round(biomass_gain * 2.5 - energy_kwh * 0.18 - labor_hours * 18.0, 4)
    human_review_required = human_review_count > 0 or summary.ending_risk >= 0.68 or bool(missing_evidence)
    if summary.ending_risk >= 0.78:
        release_readiness = "blocked"
    elif human_review_required:
        release_readiness = "review_required"
    else:
        release_readiness = "ready"
    return SimulationPolicyComparisonMetrics(
        risk_delta=summary.risk_delta,
        biomass_gain=biomass_gain,
        substrate_use=substrate_use,
        intervention_count=summary.action_count,
        human_review_count=human_review_count,
        audit_completeness=audit_completeness,
        conversion_rate_estimate=round(_clamp(biomass_gain / max(substrate_use, 0.001)), 4),
        mortality_risk=mortality_risk,
        moisture_risk=moisture_risk,
        nh3_risk=nh3_risk,
        energy_kwh_estimate=round(energy_kwh, 4),
        water_kg_estimate=round(water_kg, 4),
        co2e_estimate=co2e,
        labor_hour_estimate=round(labor_hours, 4),
        gross_margin_estimate=gross_margin,
        release_readiness=release_readiness,
        missing_evidence=missing_evidence,
        human_review_required=human_review_required,
    )


def _comparison_winners(
    runs: list[SimulationPolicyComparisonRun],
) -> dict[str, SimulationPolicy | None]:
    if not runs:
        return {
            "lowest_risk": None,
            "highest_biomass_gain": None,
            "fewest_interventions": None,
        }
    return {
        "lowest_risk": min(runs, key=lambda item: item.summary.ending_risk).policy,
        "highest_biomass_gain": max(runs, key=lambda item: item.metrics.biomass_gain).policy,
        "fewest_interventions": min(runs, key=lambda item: item.metrics.intervention_count).policy,
    }


async def compare_policies(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    simulation_id: str,
    policies: list[SimulationPolicy],
    baseline_policy: SimulationPolicy,
) -> SimulationPolicyComparisonResponse | None:
    scenario = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if scenario is None:
        return None

    comparison_runs: list[SimulationPolicyComparisonRun] = []
    for policy in _ordered_unique_policies(policies, baseline_policy):
        run_record, summary, cycles = await _persist_simulation_result(
            db,
            scenario=scenario,
            tenant_id=tenant_id,
            user_id=user_id,
            policy=policy,
        )
        comparison_runs.append(
            SimulationPolicyComparisonRun(
                policy=policy,
                run_id=run_record.run_id,
                summary=summary,
                metrics=_comparison_metrics(
                    initial_state=scenario.initial_state,
                    summary=summary,
                    cycles=cycles,
                ),
            )
        )

    scenario.status = "compared"
    await db.commit()
    await db.refresh(scenario)
    return SimulationPolicyComparisonResponse(
        simulation_id=simulation_id,
        baseline_policy=baseline_policy,
        runs=comparison_runs,
        winner=_comparison_winners(comparison_runs),
    )


async def list_runs(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> list[SimulationLabRunHistoryItem] | None:
    if await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id) is None:
        return None
    result = await db.execute(
        select(SimulationRunRecord)
        .where(
            SimulationRunRecord.simulation_id == simulation_id,
            SimulationRunRecord.tenant_id == tenant_id,
        )
        .order_by(desc(SimulationRunRecord.created_at), desc(SimulationRunRecord.id))
    )
    return [_run_history_item(item) for item in result.scalars().all()]


async def get_cycles(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationLabCycleListResponse | None:
    if await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id) is None:
        return None
    run = await _latest_run_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if run is None:
        return SimulationLabCycleListResponse(simulation_id=simulation_id, cycles=[])
    audits = await _audit_payloads(db, run=run)
    audit_by_cycle = {payload.get("cycle"): payload for payload in audits}
    cycles = [
        _cycle_response(record).model_copy(update={"audit_event": audit_by_cycle.get(record.cycle_index, {})})
        for record in await _cycle_records(db, run=run)
    ]
    return SimulationLabCycleListResponse(simulation_id=simulation_id, cycles=cycles)


async def get_audit_trace(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationLabAuditTraceResponse | None:
    if await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id) is None:
        return None
    run = await _latest_run_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if run is None:
        return SimulationLabAuditTraceResponse(simulation_id=simulation_id, audit_trace=[])
    return SimulationLabAuditTraceResponse(
        simulation_id=simulation_id,
        audit_trace=await _audit_payloads(db, run=run),
    )


async def export_run(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationLabExportResponse | None:
    scenario = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if scenario is None:
        return None
    run = await _latest_run_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    cycles_response = await get_cycles(db, tenant_id=tenant_id, simulation_id=simulation_id)
    audit_trace = await get_audit_trace(db, tenant_id=tenant_id, simulation_id=simulation_id)
    return SimulationLabExportResponse(
        simulation_id=simulation_id,
        exported_at=datetime.now(UTC),
        scenario=_scenario_response(scenario),
        summary=_summary_response(run.summary) if run else None,
        cycles=cycles_response.cycles if cycles_response else [],
        audit_trace=audit_trace.audit_trace if audit_trace else [],
        evidence_sources=scenario.evidence_sources or [],
        evidence_pack_id=run.evidence_pack_id if run else None,
        input_snapshot_id=run.input_snapshot_id if run else None,
        disclaimer=(
            "Simulation Lab v2.1 persists virtual closed-loop scenario, run, cycle, and audit data. "
            "LabSim insect bioconversion profiles are review-gated evidence with heavy-metal and product-use locks. "
            "It does not execute hardware actions, mutate production batches, or make release decisions."
        ),
    )


async def _comparison_run_from_record(
    db: AsyncSession,
    *,
    scenario: SimulationScenarioRecord,
    run: SimulationRunRecord,
) -> SimulationPolicyComparisonRun:
    cycles = [
        _cycle_response(record).model_copy(update={"audit_event": {}})
        for record in await _cycle_records(db, run=run)
    ]
    summary = _summary_response(run.summary)
    return SimulationPolicyComparisonRun(
        policy=run.policy,
        run_id=run.run_id,
        summary=summary,
        metrics=_comparison_metrics(
            initial_state=scenario.initial_state,
            summary=summary,
            cycles=cycles,
        ),
    )


async def build_release_appendix(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
    run_id: str | None = None,
) -> SimulationReleaseAppendixResponse | None:
    scenario = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if scenario is None:
        return None
    selected_run = (
        await _run_record_by_public_id(db, tenant_id=tenant_id, simulation_id=simulation_id, run_id=run_id)
        if run_id
        else await _latest_run_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    )
    if run_id and selected_run is None:
        return None

    all_runs = await _run_records_for_simulation(db, tenant_id=tenant_id, simulation_id=simulation_id)
    comparison_runs = [
        await _comparison_run_from_record(db, scenario=scenario, run=run)
        for run in all_runs
    ] if len(all_runs) > 1 else []
    return SimulationReleaseAppendixResponse(
        simulation_id=simulation_id,
        generated_at=datetime.now(UTC),
        scenario=_scenario_response(scenario),
        selected_run=_run_history_item(selected_run) if selected_run else None,
        comparison_runs=comparison_runs,
        audit_trace_hashes=await _audit_hashes(db, run=selected_run) if selected_run else [],
        evidence_pack_id=selected_run.evidence_pack_id if selected_run else None,
        input_snapshot_id=selected_run.input_snapshot_id if selected_run else None,
        disclaimer=(
            "Simulation appendix is release-review evidence only. It does not change release decisions, "
            "execute hardware actions, or mutate production batches. LabSim heavy-metal and product-use locks "
            "must remain human-reviewed before any release use."
        ),
    )


def render_release_appendix_markdown(appendix: SimulationReleaseAppendixResponse) -> str:
    scenario = appendix.scenario
    lab_profile = _labsim_profile(species=scenario.species, feedstock=scenario.feedstock)
    assay_source = next(
        (
            source.model_dump() if hasattr(source, "model_dump") else source
            for source in scenario.evidence_sources
            if (
                getattr(source, "field", None) == "lab_assay_measurements"
                or (isinstance(source, dict) and source.get("field") == "lab_assay_measurements")
            )
        ),
        None,
    )
    lines = [
        f"# Simulation Release Appendix: {appendix.simulation_id}",
        "",
        f"- Generated at: {appendix.generated_at.isoformat()}",
        f"- Species: {scenario.species}",
        f"- Feedstock: {scenario.feedstock}",
        f"- Scenario: {scenario.scenario}",
        f"- Default policy: {scenario.policy}",
        f"- Cycles: {scenario.cycles}",
        f"- Seed: {scenario.seed}",
        "",
        "## LabSim Governance",
        "",
        f"- Lab profile: {lab_profile['profile_id']}",
        f"- Route: {lab_profile['route']}",
        f"- Containment: {lab_profile['containment']}",
        f"- Heavy-metal gate: {lab_profile['heavy_metal_gate']}",
        f"- Product-use lock: {lab_profile['product_use_lock']}",
        f"- Review status: {lab_profile['review_status']}",
        f"- Standard references: {lab_profile['standard_refs']}",
        "",
        "## Lab Assay Calibration Anchors",
        "",
    ]
    targets = _labsim_assay_targets(
        str(lab_profile["profile_id"]),
        scenario.lab_assay_measurements.model_dump(exclude_none=True)
        if scenario.lab_assay_measurements
        else None,
    )
    lines.append(f"- Measurement source: {_lab_assay_measurement_mode(assay_source)}")
    lines.append(f"- Source kind: {_lab_assay_source_kind(assay_source)}")
    lines.append(f"- Source ref: {_lab_assay_source_ref(assay_source, lab_profile)}")
    lines.append(f"- Review status: {_lab_assay_source_review_status(assay_source, lab_profile)}")
    if assay_source is not None and "numeric_values_included" in assay_source:
        lines.append(f"- Human review required: {str(bool(assay_source.get('human_review_required'))).lower()}")
        lines.append(f"- Numeric values included: {str(bool(assay_source.get('numeric_values_included'))).lower()}")
        lines.append(f"- Release evidence allowed: {str(bool(assay_source.get('release_evidence_allowed'))).lower()}")
        lines.append(f"- Runtime activation enabled: {str(bool(assay_source.get('runtime_activation_enabled'))).lower()}")
        lines.append(
            f"- Validated default write enabled: {str(bool(assay_source.get('validated_default_write_enabled'))).lower()}"
        )
    for field, value in targets.items():
        lines.append(f"- {field}: measured anchor {value}")
    lines.extend(
        [
            "- Calibration status: review_required when prediction residuals exceed screening bands or route is human-review locked.",
            "",
        ]
    )
    lines.extend([
        "## Selected Run",
    ])
    if appendix.selected_run:
        run = appendix.selected_run
        lines.extend(
            [
                f"- Run ID: {run.run_id}",
                f"- Policy: {run.policy}",
                f"- Risk delta: {run.risk_delta}",
                f"- Starting risk: {run.starting_risk}",
                f"- Ending risk: {run.ending_risk}",
                f"- Audit events: {run.audit_event_count}",
            ]
        )
    else:
        lines.append("- No simulation run has been completed yet.")

    if appendix.comparison_runs:
        lines.extend(["", "## Policy Comparison", "", "| Policy | Risk delta | Biomass gain | Substrate use | Interventions | Human reviews | Audit completeness |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for item in appendix.comparison_runs:
            lines.append(
                "| "
                f"{item.policy} | {item.metrics.risk_delta} | {item.metrics.biomass_gain} | "
                f"{item.metrics.substrate_use} | {item.metrics.intervention_count} | "
                f"{item.metrics.human_review_count} | {item.metrics.audit_completeness} |"
            )

    lines.extend(["", "## Audit Trace Hashes"])
    if appendix.audit_trace_hashes:
        for item in appendix.audit_trace_hashes:
            lines.append(f"- Cycle {item.cycle}: {item.event_type} `{item.payload_hash}`")
    else:
        lines.append("- No audit trace hashes are available.")

    lines.extend(["", "## Disclaimer", "", appendix.disclaimer, ""])
    return "\n".join(lines)


async def get_evidence_sources(
    db: AsyncSession,
    *,
    tenant_id: int,
    simulation_id: str,
) -> SimulationEvidenceSourcesResponse | None:
    scenario = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    if scenario is None:
        return None
    run = await _latest_run_record(db, tenant_id=tenant_id, simulation_id=simulation_id)
    cycle_sources: list[dict] = []
    latest_run_sources: list[SimulationEvidenceSource] = []
    if run:
        latest_run_sources = [
            SimulationEvidenceSource(**_source("input_snapshot", "operator_input", source_ref=run.input_snapshot_id)),
            SimulationEvidenceSource(**_source("engine_version", "deterministic_model", source_ref=run.engine_version)),
        ]
        cycle_records = await _cycle_records(db, run=run)
        if cycle_records:
            latest_run_sources.extend(
                SimulationEvidenceSource(**source)
                for source in (cycle_records[-1].evidence_sources or [])
            )
        for record in cycle_records:
            cycle_sources.append({"cycle": record.cycle_index, "evidence_sources": record.evidence_sources or []})
    return SimulationEvidenceSourcesResponse(
        simulation_id=simulation_id,
        scenario_sources=scenario.evidence_sources or [],
        latest_run_sources=latest_run_sources,
        cycle_sources=cycle_sources,
    )


def _core_projection(cycles: list[SimulationCycleRecord]) -> list[dict]:
    return [
        {
            "cycle": cycle.cycle_index,
            "action": cycle.agent_action.get("recommended_action"),
            "intensity": cycle.agent_action.get("intensity"),
            "state_after": cycle.state_after,
            "deterministic_risk": cycle.risk_prediction.get("deterministic_fallback", {}).get(
                "future_risk_score",
                cycle.risk_prediction.get("future_risk_score"),
            ),
        }
        for cycle in cycles
    ]


async def replay_run(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    run_id: str,
) -> SimulationReplayResponse | None:
    source_run = await _run_record_by_public_id_any_simulation(db, tenant_id=tenant_id, run_id=run_id)
    if source_run is None:
        return None
    scenario = await _get_scenario_record(db, tenant_id=tenant_id, simulation_id=source_run.simulation_id)
    if scenario is None:
        return None
    replay_record, _summary, _cycles = await _persist_simulation_result(
        db,
        scenario=scenario,
        tenant_id=tenant_id,
        user_id=user_id,
        policy=source_run.policy,
        replay_of_run_id=source_run.run_id,
    )
    await db.commit()
    source_cycles = await _cycle_records(db, run=source_run)
    replay_cycles = await _cycle_records(db, run=replay_record)
    match = _core_projection(source_cycles) == _core_projection(replay_cycles)
    warnings = []
    if source_run.input_snapshot_hash != replay_record.input_snapshot_hash:
        warnings.append("input_snapshot_hash_mismatch")
    return SimulationReplayResponse(
        source_run_id=source_run.run_id,
        replay_run=_run_history_item(replay_record),
        deterministic_core_match=match,
        warnings=warnings,
    )


async def diff_runs(
    db: AsyncSession,
    *,
    tenant_id: int,
    run_id: str,
    against_run_id: str,
) -> SimulationRunDiffResponse | None:
    run = await _run_record_by_public_id_any_simulation(db, tenant_id=tenant_id, run_id=run_id)
    against = await _run_record_by_public_id_any_simulation(db, tenant_id=tenant_id, run_id=against_run_id)
    if run is None or against is None:
        return None
    left = _core_projection(await _cycle_records(db, run=run))
    right = _core_projection(await _cycle_records(db, run=against))
    differences = [
        {"cycle": item.get("cycle"), "run": item, "against": right[index] if index < len(right) else None}
        for index, item in enumerate(left)
        if index >= len(right) or item != right[index]
    ]
    return SimulationRunDiffResponse(
        run_id=run_id,
        against_run_id=against_run_id,
        deterministic_core_match=not differences,
        differences=differences,
    )
