"""Minimal sustainability value-proof kernel."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.external_knowledge_candidates import build_candidate_context, get_approved_factor
from app.models_bos import SustainabilityResultRecord
from app.schemas.evidence import EvidenceItemCreate, EvidencePackCreate
from app.schemas.sustainability_kernel import LCACompareRequest, SustainabilityResultResponse, TEAEstimateRequest
from app.services.evidence_service import create_evidence_pack
from app.services.external_knowledge_activation_service import get_active_external_factor


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _response(record: SustainabilityResultRecord) -> SustainabilityResultResponse:
    return SustainabilityResultResponse(
        result_id=record.result_id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        result_type=record.result_type,  # type: ignore[arg-type]
        functional_unit=record.functional_unit,
        system_boundary=record.system_boundary,
        baseline_scenario=record.baseline_scenario,
        alternative_scenario=record.alternative_scenario,
        activity_data=record.activity_data,
        emission_factors=record.emission_factors,
        cost_factors=record.cost_factors,
        result=record.result,
        uncertainty_warnings=record.uncertainty_warnings or [],
        factor_sources=(record.result or {}).get("factor_sources", {}),
        review_gate=(record.result or {}).get("review_gate", {}),
        evidence_pack_id=record.evidence_pack_id,
        created_at=record.created_at,
    )


async def _resolve_factor(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_type: str,
    key: str,
    provided: dict[str, float],
    assumed_value: float,
    warnings: list[str],
) -> tuple[float, dict]:
    if key in provided:
        return provided[key], {
            "key": key,
            "source_kind": "operator_input",
            "source_ref": "request_payload",
            "review_status": "operator_supplied",
            "human_review_required": True,
            "used_in_kernel": True,
        }
    active = await get_active_external_factor(db, tenant_id=tenant_id, candidate_type=candidate_type, candidate_key=key)
    if active is not None:
        return float(active["value"]), active
    approved = get_approved_factor(candidate_type, key)  # type: ignore[arg-type]
    if approved is not None:
        return float(approved.value), {
            **approved.to_payload(),
            "used_in_kernel": True,
        }
    warnings.append(f"{'emission' if candidate_type == 'lca_factor_candidate' else 'cost'}_factor.{key} defaulted")
    return assumed_value, {
        "key": key,
        "source_kind": "fallback_default",
        "source_ref": "sustainability_kernel_v1_assumed_default",
        "review_status": "unreviewed_default",
        "human_review_required": True,
        "used_in_kernel": True,
        "candidate_context": build_candidate_context(candidate_type, [key]),  # type: ignore[arg-type]
    }


async def compare_lca(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: LCACompareRequest,
) -> SustainabilityResultResponse:
    warnings: list[str] = []
    electricity_factor, electricity_source = await _resolve_factor(
        db,
        tenant_id=tenant_id,
        candidate_type="lca_factor_candidate",
        key="electricity_kgco2e_per_kwh",
        provided=payload.emission_factors,
        assumed_value=0.42,
        warnings=warnings,
    )
    landfill_factor, landfill_source = await _resolve_factor(
        db,
        tenant_id=tenant_id,
        candidate_type="lca_factor_candidate",
        key="landfill_kgco2e_per_tonne",
        provided=payload.emission_factors,
        assumed_value=450.0,
        warnings=warnings,
    )
    factors = {
        "electricity_kgco2e_per_kwh": electricity_factor,
        "landfill_kgco2e_per_tonne": landfill_factor,
        **payload.emission_factors,
    }
    factor_sources = {
        "electricity_kgco2e_per_kwh": electricity_source,
        "landfill_kgco2e_per_tonne": landfill_source,
    }
    substrate_tonnes = float(payload.activity_data.get("substrate_tonnes", 1.0))
    electricity_kwh = float(payload.activity_data.get("electricity_kwh", 35.0))
    baseline_kind = str(payload.baseline_scenario.get("kind", "landfill"))
    baseline_co2e = substrate_tonnes * (factors["landfill_kgco2e_per_tonne"] if baseline_kind == "landfill" else 110.0)
    alternative_co2e = electricity_kwh * factors["electricity_kgco2e_per_kwh"] + substrate_tonnes * 24.0
    result = {
        "baseline_co2e_kg": round(baseline_co2e, 4),
        "alternative_co2e_kg": round(alternative_co2e, 4),
        "co2e_abatement_kg": round(baseline_co2e - alternative_co2e, 4),
        "energy_kwh": electricity_kwh,
        "water_kg": round(float(payload.activity_data.get("water_kg", substrate_tonnes * 80.0)), 4),
        "functional_unit": payload.functional_unit,
        "factor_sources": factor_sources,
        "review_gate": {
            "external_candidates_available": True,
            "pending_candidates_not_used": True,
            "human_review_required": bool(warnings),
        },
    }
    return await _persist_result(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        result_type="lca",
        functional_unit=payload.functional_unit,
        system_boundary=payload.system_boundary,
        baseline_scenario=payload.baseline_scenario,
        alternative_scenario=payload.alternative_scenario,
        activity_data=payload.activity_data,
        emission_factors=factors,
        cost_factors=None,
        result=result,
        warnings=warnings,
    )


async def estimate_tea(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: TEAEstimateRequest,
) -> SustainabilityResultResponse:
    warnings: list[str] = []
    energy_factor, energy_source = await _resolve_factor(
        db,
        tenant_id=tenant_id,
        candidate_type="tea_factor_candidate",
        key="energy_usd_per_kwh",
        provided=payload.cost_factors,
        assumed_value=0.18,
        warnings=warnings,
    )
    labor_factor, labor_source = await _resolve_factor(
        db,
        tenant_id=tenant_id,
        candidate_type="tea_factor_candidate",
        key="labor_usd_per_hour",
        provided=payload.cost_factors,
        assumed_value=18.0,
        warnings=warnings,
    )
    biomass_factor, biomass_source = await _resolve_factor(
        db,
        tenant_id=tenant_id,
        candidate_type="tea_factor_candidate",
        key="biomass_usd_per_kg",
        provided=payload.cost_factors,
        assumed_value=2.5,
        warnings=warnings,
    )
    costs = {
        "energy_usd_per_kwh": energy_factor,
        "labor_usd_per_hour": labor_factor,
        "biomass_usd_per_kg": biomass_factor,
        **payload.cost_factors,
    }
    factor_sources = {
        "energy_usd_per_kwh": energy_source,
        "labor_usd_per_hour": labor_source,
        "biomass_usd_per_kg": biomass_source,
    }
    biomass_kg = float(payload.activity_data.get("biomass_kg", 1.0))
    energy_kwh = float(payload.activity_data.get("energy_kwh", 35.0))
    labor_hours = float(payload.activity_data.get("labor_hours", 2.0))
    revenue = biomass_kg * costs["biomass_usd_per_kg"]
    operating_cost = energy_kwh * costs["energy_usd_per_kwh"] + labor_hours * costs["labor_usd_per_hour"]
    result = {
        "revenue_usd": round(revenue, 4),
        "operating_cost_usd": round(operating_cost, 4),
        "gross_margin_usd": round(revenue - operating_cost, 4),
        "energy_kwh": energy_kwh,
        "labor_hours": labor_hours,
        "functional_unit": payload.functional_unit,
        "factor_sources": factor_sources,
        "review_gate": {
            "external_candidates_available": True,
            "pending_candidates_not_used": True,
            "human_review_required": bool(warnings),
        },
    }
    return await _persist_result(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        result_type="tea",
        functional_unit=payload.functional_unit,
        system_boundary=payload.system_boundary,
        baseline_scenario=payload.baseline_scenario,
        alternative_scenario=payload.alternative_scenario,
        activity_data=payload.activity_data,
        emission_factors=None,
        cost_factors=costs,
        result=result,
        warnings=warnings,
    )


async def _persist_result(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    result_type: str,
    functional_unit: str,
    system_boundary: dict,
    baseline_scenario: dict | None,
    alternative_scenario: dict | None,
    activity_data: dict,
    emission_factors: dict | None,
    cost_factors: dict | None,
    result: dict,
    warnings: list[str],
) -> SustainabilityResultResponse:
    result_id = _new_id("SUS")
    pack = await create_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=EvidencePackCreate(
            subject_type=f"sustainability_{result_type}",
            subject_id=result_id,
            title=f"{result_type.upper()} evidence for {functional_unit}",
            summary="Minimal sustainability kernel result with explicit defaults and uncertainty warnings.",
            verification_status="review_required" if warnings else "verified",
            human_review_required=bool(warnings),
            items=[
                EvidenceItemCreate(
                    kind=f"{result_type}_result",
                    source_kind="fallback_default" if warnings else "deterministic_model",
                    source_ref="sustainability_kernel_v1_review_gated_factor_lookup",
                    payload=result,
                    uncertainty_level="medium" if warnings else "low",
                )
            ],
        ),
    )
    record = SustainabilityResultRecord(
        result_id=result_id,
        tenant_id=tenant_id,
        user_id=user_id,
        result_type=result_type,
        functional_unit=functional_unit,
        system_boundary=jsonable_encoder(system_boundary),
        baseline_scenario=jsonable_encoder(baseline_scenario),
        alternative_scenario=jsonable_encoder(alternative_scenario),
        activity_data=jsonable_encoder(activity_data),
        emission_factors=jsonable_encoder(emission_factors),
        cost_factors=jsonable_encoder(cost_factors),
        result=jsonable_encoder(result),
        uncertainty_warnings=warnings,
        evidence_pack_id=pack.evidence_pack_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _response(record)


async def get_sustainability_result(
    db: AsyncSession,
    *,
    tenant_id: int,
    result_id: str,
) -> SustainabilityResultResponse | None:
    result = await db.execute(
        select(SustainabilityResultRecord).where(
            SustainabilityResultRecord.result_id == result_id,
            SustainabilityResultRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    return _response(record) if record else None
