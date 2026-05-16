"""BOS Simulation Lab router."""

from __future__ import annotations

import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User
from app.schemas.simulation_lab import (
    SimulationLabAuditTraceResponse,
    SimulationLabCycleListResponse,
    SimulationLabExportResponse,
    SimulationLabRunHistoryItem,
    SimulationLabRunResponse,
    SimulationEvidenceSourcesResponse,
    SimulationPolicyCompareRequest,
    SimulationPolicyComparisonResponse,
    SimulationReplayResponse,
    SimulationRunDiffResponse,
    SimulationScenarioCreate,
    SimulationScenarioImportRequest,
    SimulationScenarioImportResponse,
    SimulationScenarioResponse,
)
from app.services.feature_flags import get_effective_flag_value
from app.services.simulation_lab_service import (
    create_scenario,
    compare_policies,
    build_release_appendix,
    export_run,
    diff_runs,
    get_audit_trace,
    get_cycles,
    get_evidence_sources,
    import_scenario_from_reference,
    list_runs,
    list_scenarios,
    render_release_appendix_markdown,
    replay_run,
    run_scenario,
)

router = APIRouter()


async def _ensure_simulation_lab_enabled(
    request: Request,
    db: AsyncSession,
    *,
    tenant_id: int,
) -> None:
    redis = getattr(request.app.state, "redis", None)
    enabled, _source = await get_effective_flag_value(
        db,
        flag_name="bos_simulation_lab",
        tenant_id=tenant_id,
        redis=redis,
    )
    if not enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bos_simulation_lab_disabled")


@router.post("/scenarios", response_model=SimulationScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_simulation_lab_scenario(
    payload: SimulationScenarioCreate,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    return await create_scenario(db, tenant_id=current_user.tenant_id, user_id=current_user.id, payload=payload)


@router.post(
    "/scenarios/import-reference",
    response_model=SimulationScenarioImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_simulation_lab_scenario_from_reference(
    payload: SimulationScenarioImportRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    imported = await import_scenario_from_reference(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        payload=payload,
    )
    if imported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference source not found")
    return imported


@router.get("/scenarios", response_model=list[SimulationScenarioResponse])
async def list_simulation_lab_scenarios(
    request: Request,
    batch_id: str | None = Query(default=None),
    species: str | None = Query(default=None),
    feedstock: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    return await list_scenarios(
        db,
        tenant_id=current_user.tenant_id,
        batch_id=batch_id,
        species=species,
        feedstock=feedstock,
        limit=limit,
    )


@router.post("/scenarios/{simulation_id}/run", response_model=SimulationLabRunResponse)
async def run_simulation_lab_scenario(
    simulation_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    run = await run_scenario(db, tenant_id=current_user.tenant_id, user_id=current_user.id, simulation_id=simulation_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return run


@router.post("/scenarios/{simulation_id}/compare", response_model=SimulationPolicyComparisonResponse)
async def compare_simulation_lab_policies(
    simulation_id: str,
    payload: SimulationPolicyCompareRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    comparison = await compare_policies(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        simulation_id=simulation_id,
        policies=payload.policies,
        baseline_policy=payload.baseline_policy,
    )
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return comparison


@router.get("/scenarios/{simulation_id}/runs", response_model=list[SimulationLabRunHistoryItem])
async def list_simulation_lab_runs(
    simulation_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    runs = await list_runs(db, tenant_id=current_user.tenant_id, simulation_id=simulation_id)
    if runs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return runs


@router.get("/scenarios/{simulation_id}/cycles", response_model=SimulationLabCycleListResponse)
async def get_simulation_lab_cycles(
    simulation_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    cycles = await get_cycles(db, tenant_id=current_user.tenant_id, simulation_id=simulation_id)
    if cycles is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return cycles


@router.get("/scenarios/{simulation_id}/audit-trace", response_model=SimulationLabAuditTraceResponse)
async def get_simulation_lab_audit_trace(
    simulation_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    audit_trace = await get_audit_trace(db, tenant_id=current_user.tenant_id, simulation_id=simulation_id)
    if audit_trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return audit_trace


@router.get("/scenarios/{simulation_id}/evidence-sources", response_model=SimulationEvidenceSourcesResponse)
async def get_simulation_lab_evidence_sources(
    simulation_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    evidence_sources = await get_evidence_sources(db, tenant_id=current_user.tenant_id, simulation_id=simulation_id)
    if evidence_sources is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return evidence_sources


@router.get("/scenarios/{simulation_id}/export", response_model=SimulationLabExportResponse)
async def export_simulation_lab_run(
    simulation_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    exported = await export_run(db, tenant_id=current_user.tenant_id, simulation_id=simulation_id)
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario not found")
    return exported


@router.get("/scenarios/{simulation_id}/release-appendix")
async def export_simulation_lab_release_appendix(
    simulation_id: str,
    request: Request,
    format: str = Query(default="json", pattern=r"^(json|md)$"),
    run_id: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    appendix = await build_release_appendix(
        db,
        tenant_id=current_user.tenant_id,
        simulation_id=simulation_id,
        run_id=run_id,
    )
    if appendix is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation scenario or run not found")
    export_date = date.today().isoformat()
    if format == "md":
        return StreamingResponse(
            io.StringIO(render_release_appendix_markdown(appendix)),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=simulation_appendix_{simulation_id}_{export_date}.md",
            },
        )
    return appendix


@router.post("/runs/{run_id}/replay", response_model=SimulationReplayResponse)
async def replay_simulation_lab_run(
    run_id: str,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    replay = await replay_run(db, tenant_id=current_user.tenant_id, user_id=current_user.id, run_id=run_id)
    if replay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")
    return replay


@router.get("/runs/{run_id}/diff", response_model=SimulationRunDiffResponse)
async def diff_simulation_lab_runs(
    run_id: str,
    request: Request,
    against_run_id: str = Query(...),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_simulation_lab_enabled(request, db, tenant_id=current_user.tenant_id)
    diff = await diff_runs(
        db,
        tenant_id=current_user.tenant_id,
        run_id=run_id,
        against_run_id=against_run_id,
    )
    if diff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")
    return diff
