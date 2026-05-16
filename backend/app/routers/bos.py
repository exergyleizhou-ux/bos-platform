"""
BOS protocol-first routers.
"""

import io
from pathlib import Path
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context
from app.engine.bos_closed_loop_simulation import (
    ClosedLoopSimulationConfig,
    build_closed_loop_table_rows,
    run_closed_loop_simulation,
)
from app.engine.bos_supervisor_engine import evaluate_bos_supervisor_state
from app.models import (
    AuditPacket,
    Batch,
    BoundaryLedger,
    ControlAPIProfile,
    ExecutorProfile,
    LocalityProfile,
    PortabilityAudit,
    ReleaseDecision,
    SignalBatch,
    User,
)
from app.schemas import (
    AuditPacketResponse,
    BatchGuidanceResponse,
    BrainRuntimeDocumentResponse,
    BrainRuntimeResponse,
    BrainRuntimeUpdateRequest,
    BoundaryLedgerResponse,
    ClosedLoopSimulationRequest,
    ClosedLoopSimulationResponse,
    ClosedLoopSimulationTableResponse,
    ControlAPIProfileCreate,
    ControlAPIProfileResponse,
    ExecutorProfileCreate,
    ExecutorProfileResponse,
    HandoverRecommendationResponse,
    LocalityProfileCreate,
    LocalityProfileResponse,
    NativeModelCatalogResponse,
    NativeModelDownloadPlanResponse,
    NativeModelDownloadResponse,
    NativeModelInferenceRequest,
    NativeModelInferenceResponse,
    NativeModelRunArtifactResponse,
    NativeModelRuntimeStatusResponse,
    PortabilityAuditCreate,
    PortabilityAuditResponse,
    PortabilityRecommendationRequest,
    PortabilityRecommendationResponse,
    ReleaseDecisionResponse,
    ReleaseEvaluationRequest,
    RecentTimeseriesRiskResponse,
    SignalBatchCreate,
    SignalBatchResponse,
    SignalCompileRequest,
    SignalCompileResponse,
    SignalRefreshResponse,
    SupervisorObservationRequest,
    SupervisorStateResponse,
    TimeseriesRiskResponse,
    VisionObservationAttachRequest,
    VisionObservationAttachResponse,
    VisionDetectionResponse,
)
from app.schemas.external_source_review import (
    LiteratureValueReleaseEvidenceLinkCreateRequest,
    LiteratureValueReleaseEvidenceLinkResponse,
)
from app.services.bos import (
    _latest_for_batch,
    compile_signal_for_batch,
    evaluate_release_for_batch,
    persist_supervisor_snapshot,
    recommend_portability,
    refresh_audit_packet_for_signal,
    refresh_signal_batch_state,
    serialize_audit_packet,
    serialize_portability_audit,
    serialize_release_decision,
)
from app.services.brain_runtime import validate_runtime_document
from app.services.bos_guidance_service import build_batch_guidance
from app.services.bos_native_models import build_native_model_catalog
from app.services.bos_native_runtime import (
    build_native_download_plan,
    build_native_runtime_status,
    download_native_model_artifact,
    list_native_inference_runs,
    run_native_inference_contract,
)
from app.services.bos_report_service import render_audit_packet_json, render_audit_packet_markdown
from app.services.feature_flags import get_effective_flag_value
from app.services.reviewed_external_candidate_service import create_literature_value_release_evidence_link
from app.services.timeseries_risk_service import (
    build_batch_timeseries_risk,
    build_recent_timeseries_risks,
)
from app.services import vision_detection_service

router = APIRouter()
RUNTIME_ROOT = Path(__file__).resolve().parents[3] / ".agents" / "runtime"
RUNTIME_DOCUMENTS = (
    ("project_brain", "Project Brain", "project-brain.md"),
    ("decision_journal", "Decision Journal", "decision-journal.md"),
    ("evolution_log", "Evolution Log", "evolution-log.md"),
    ("run_ledger", "Autonomy Run Ledger", "run-ledger.md"),
)
RUNTIME_DOCUMENT_MAP = {key: (title, filename) for key, title, filename in RUNTIME_DOCUMENTS}


@router.post("/bos/vision/detect", response_model=VisionDetectionResponse)
async def detect_bos_vision_observation(
    file: UploadFile = File(...),
    current_user: User = Depends(require_minimum_role("operator")),
):
    max_bytes = 12 * 1024 * 1024
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vision detection requires an image upload.",
        )
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty.",
        )
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded image exceeds the 12MB phase-1 limit.",
        )
    return vision_detection_service.detect_image(
        file_bytes=file_bytes,
        file_name=file.filename or "vision-upload",
        content_type=file.content_type,
        tenant_id=current_user.tenant_id,
    )


@router.get("/bos/vision/runs", response_model=list[VisionDetectionResponse])
async def list_bos_vision_observation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_minimum_role("operator")),
):
    return vision_detection_service.list_detection_runs(
        tenant_id=current_user.tenant_id,
        limit=limit,
    )


@router.post("/bos/vision/runs/{run_id}/attach", response_model=VisionObservationAttachResponse)
async def attach_bos_vision_observation_to_signal(
    run_id: str,
    body: VisionObservationAttachRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    run = vision_detection_service.get_detection_run(
        tenant_id=current_user.tenant_id,
        run_id=run_id,
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision detection run not found")

    signal_batch = await _get_signal_batch_or_404(db, body.signal_batch_id, current_user.tenant_id)
    qc_markers = dict(signal_batch.qc_markers or {})
    vision_observation = run.observation.model_dump(mode="json")
    vision_observation.update(
        {
            "run_id": run.run_id,
            "recorded_at": run.created_at.isoformat(),
            "model_name": run.model_name,
            "model_status": run.model_status,
            "fallback_used": run.fallback_used,
            "artifact_path": run.artifact_path,
            "phase": "operator_review",
            "supervisor_auto_execution": False,
        }
    )
    qc_markers["vision_observation"] = vision_observation
    signal_batch.qc_markers = qc_markers
    flag_modified(signal_batch, "qc_markers")

    audit_packet_refreshed = False
    try:
        await refresh_audit_packet_for_signal(
            db,
            signal_batch=signal_batch,
            current_user=current_user,
        )
        audit_packet_refreshed = True
    except Exception:
        audit_packet_refreshed = False

    await db.commit()
    await db.refresh(signal_batch)
    return VisionObservationAttachResponse(
        signal_batch_id=signal_batch.id,
        run_id=run.run_id,
        attached=True,
        observation=run.observation,
        audit_packet_refreshed=audit_packet_refreshed,
    )


async def _ensure_flag_enabled(
    request: Request,
    db: AsyncSession,
    *,
    tenant_id: int,
    flag_name: str,
) -> None:
    redis = getattr(request.app.state, "redis", None)
    enabled, _source = await get_effective_flag_value(
        db,
        flag_name=flag_name,
        tenant_id=tenant_id,
        redis=redis,
    )
    if not enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{flag_name}_disabled")


async def _get_batch_or_404(db: AsyncSession, batch_id: int, tenant_id: int) -> Batch:
    result = await db.execute(select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


@router.get("/bos/risk/batch/{batch_id}", response_model=TimeseriesRiskResponse)
async def get_model_backed_batch_risk(
    batch_id: int,
    horizon: int = Query(default=6, ge=1, le=24),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Return Chronos-backed BOS risk metrics for one batch with heuristic fallback."""
    batch = await _get_batch_or_404(db, batch_id, current_user.tenant_id)
    return await build_batch_timeseries_risk(
        db=db,
        batch=batch,
        tenant_id=current_user.tenant_id,
        horizon=horizon,
    )


@router.get("/bos/risk/recent", response_model=RecentTimeseriesRiskResponse)
async def get_recent_model_backed_risks(
    limit: int = Query(default=5, ge=1, le=20),
    horizon: int = Query(default=6, ge=1, le=24),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Return recent Chronos-backed BOS risk metrics for assistant and release surfaces."""
    return await build_recent_timeseries_risks(
        db=db,
        tenant_id=current_user.tenant_id,
        limit=limit,
        horizon=horizon,
    )


def _serialize_runtime_document(key: str, title: str, filename: str) -> BrainRuntimeDocumentResponse:
    path = RUNTIME_ROOT / filename
    relative_path = str(path.relative_to(Path(__file__).resolve().parents[3])).replace("\\", "/")
    if not path.exists():
        return BrainRuntimeDocumentResponse(
            key=key,
            title=title,
            relative_path=relative_path,
            content="",
            updated_at=None,
            line_count=0,
            is_missing=True,
        )

    content = path.read_text(encoding="utf-8")
    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return BrainRuntimeDocumentResponse(
        key=key,
        title=title,
        relative_path=relative_path,
        content=content,
        updated_at=updated_at,
        line_count=len(content.splitlines()),
        is_missing=False,
    )


def _resolve_runtime_document_or_404(document_key: str) -> tuple[str, str]:
    if document_key not in RUNTIME_DOCUMENT_MAP:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brain runtime document not found")
    return RUNTIME_DOCUMENT_MAP[document_key]


@router.get("/brain/runtime", response_model=BrainRuntimeResponse)
async def get_brain_runtime(
    current_user: User = Depends(require_minimum_role("operator")),
):
    del current_user
    documents = [
        _serialize_runtime_document(key=key, title=title, filename=filename)
        for key, title, filename in RUNTIME_DOCUMENTS
    ]
    available_updates = [item.updated_at for item in documents if item.updated_at is not None]
    return BrainRuntimeResponse(
        root_path=str(RUNTIME_ROOT.relative_to(Path(__file__).resolve().parents[3])).replace("\\", "/"),
        documents=documents,
        total_line_count=sum(item.line_count for item in documents),
        last_updated_at=max(available_updates) if available_updates else None,
    )


@router.put("/brain/runtime/{document_key}", response_model=BrainRuntimeDocumentResponse)
async def update_brain_runtime_document(
    document_key: str,
    body: BrainRuntimeUpdateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
):
    del current_user
    title, filename = _resolve_runtime_document_or_404(document_key)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    path = RUNTIME_ROOT / filename
    validation = validate_runtime_document(document_key, body.content)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": f"{title} must preserve the required runtime-memory structure.",
                "missing_headings": validation.missing_headings,
                "unexpected_headings": validation.unexpected_headings,
                "duplicate_headings": validation.duplicate_headings,
                "out_of_order_headings": validation.out_of_order_headings,
                "invalid_lines": validation.invalid_lines,
            },
        )
    path.write_text(validation.normalized_content, encoding="utf-8")
    return _serialize_runtime_document(document_key, title, filename)


@router.get("/guidance/batch/{batch_id}", response_model=BatchGuidanceResponse)
async def get_batch_guidance(
    batch_id: int,
    request: Request,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_flag_enabled(
        request,
        db,
        tenant_id=current_user.tenant_id,
        flag_name="bos_guidance",
    )
    batch = await _get_batch_or_404(db, batch_id, current_user.tenant_id)
    signal_batch = await _latest_for_batch(db, SignalBatch, batch_id=batch.id, tenant_id=current_user.tenant_id)
    boundary_ledger = await _latest_for_batch(db, BoundaryLedger, batch_id=batch.id, tenant_id=current_user.tenant_id)
    del boundary_ledger
    release_decision = await _latest_for_batch(db, ReleaseDecision, batch_id=batch.id, tenant_id=current_user.tenant_id)

    control_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at))
        .limit(1)
    )
    control_profile = control_result.scalar_one_or_none()

    portability_result = await db.execute(
        select(PortabilityAudit)
        .where(PortabilityAudit.tenant_id == current_user.tenant_id, PortabilityAudit.signal_batch_id == signal_batch.id if signal_batch else False)
        .order_by(desc(PortabilityAudit.created_at))
    )
    portability_audits = portability_result.scalars().all() if signal_batch else []

    locality_profile = None
    if portability_audits and portability_audits[0].locality_profile_id:
        locality_profile = await db.get(LocalityProfile, portability_audits[0].locality_profile_id)

    guidance = build_batch_guidance(
        batch=batch,
        signal_batch=signal_batch,
        control_profile=control_profile,
        locality_profile=locality_profile,
        release_decision=release_decision,
        portability_audits=portability_audits,
        native_model_stack=build_native_model_catalog(batch=batch, signal_batch=signal_batch),
    )
    return BatchGuidanceResponse(**guidance)


@router.get("/native-models", response_model=NativeModelCatalogResponse)
async def list_native_models(
    batch_id: int | None = Query(default=None),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    batch = None
    signal_batch = None
    if batch_id is not None:
        batch = await _get_batch_or_404(db, batch_id, current_user.tenant_id)
        signal_batch = await _latest_for_batch(
            db,
            SignalBatch,
            batch_id=batch.id,
            tenant_id=current_user.tenant_id,
        )

    catalog = build_native_model_catalog(batch=batch, signal_batch=signal_batch)
    return NativeModelCatalogResponse(**catalog)


@router.get("/native-models/runtime", response_model=NativeModelRuntimeStatusResponse)
async def get_native_model_runtime_status(
    current_user: User = Depends(set_tenant_context),
):
    del current_user
    return NativeModelRuntimeStatusResponse(**build_native_runtime_status())


@router.get("/native-models/download-plan", response_model=list[NativeModelDownloadPlanResponse])
async def get_native_model_download_plan(
    model_key: str | None = Query(default=None),
    current_user: User = Depends(set_tenant_context),
):
    del current_user
    return [NativeModelDownloadPlanResponse(**item) for item in build_native_download_plan(model_key=model_key)]


@router.post("/native-models/{model_key}/download", response_model=NativeModelDownloadResponse)
async def download_native_model(
    model_key: str,
    current_user: User = Depends(require_minimum_role("operator")),
):
    del current_user
    try:
        response = download_native_model_artifact(model_key=model_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return NativeModelDownloadResponse(**response)


@router.get("/native-models/runs", response_model=list[NativeModelRunArtifactResponse])
async def list_native_model_runs(
    model_key: str | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(set_tenant_context),
):
    del current_user
    return [
        NativeModelRunArtifactResponse(**item)
        for item in list_native_inference_runs(model_key=model_key, batch_id=batch_id, limit=limit)
    ]


@router.post("/native-models/infer", response_model=NativeModelInferenceResponse)
async def infer_native_model(
    body: NativeModelInferenceRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    batch = None
    if body.batch_id is not None:
        batch = await _get_batch_or_404(db, body.batch_id, current_user.tenant_id)

    try:
        response = run_native_inference_contract(
            model_key=body.model_key,
            payload=body.payload,
            batch=batch,
            dry_run=body.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if batch is not None:
        latest_signal = await _latest_for_batch(
            db,
            SignalBatch,
            batch_id=batch.id,
            tenant_id=current_user.tenant_id,
        )
        if latest_signal is not None:
            await refresh_audit_packet_for_signal(
                db,
                signal_batch=latest_signal,
                current_user=current_user,
            )
            await db.commit()

    return NativeModelInferenceResponse(**response)


async def _get_signal_batch_or_404(
    db: AsyncSession,
    signal_batch_id: int,
    tenant_id: int,
) -> SignalBatch:
    result = await db.execute(
        select(SignalBatch).where(
            SignalBatch.id == signal_batch_id,
            SignalBatch.tenant_id == tenant_id,
        )
    )
    signal_batch = result.scalar_one_or_none()
    if not signal_batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal batch not found")
    return signal_batch


async def _get_executor_profile_or_404(
    db: AsyncSession,
    executor_profile_id: int,
    tenant_id: int,
) -> ExecutorProfile:
    result = await db.execute(
        select(ExecutorProfile).where(
            ExecutorProfile.id == executor_profile_id,
            ExecutorProfile.tenant_id == tenant_id,
        )
    )
    executor_profile = result.scalar_one_or_none()
    if not executor_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Executor profile not found")
    return executor_profile


async def _get_locality_profile_or_404(
    db: AsyncSession,
    locality_profile_id: int,
    tenant_id: int,
) -> LocalityProfile:
    result = await db.execute(
        select(LocalityProfile).where(
            LocalityProfile.id == locality_profile_id,
            LocalityProfile.tenant_id == tenant_id,
        )
    )
    locality_profile = result.scalar_one_or_none()
    if not locality_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locality profile not found")
    return locality_profile


def _extract_signal_mechanistic_context(signal_batch: SignalBatch) -> dict:
    qc_markers = signal_batch.qc_markers or {}
    compile_context = qc_markers.get("compile_context") or {}
    mechanistic_context = compile_context.get("mechanistic_context")
    if isinstance(mechanistic_context, dict):
        return mechanistic_context
    return {}


@router.post("/closed-loop/simulate", response_model=ClosedLoopSimulationResponse)
async def simulate_closed_loop(
    body: ClosedLoopSimulationRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    batch = await _get_batch_or_404(db, body.batch_id, current_user.tenant_id)
    signal_batch = await _latest_for_batch(
        db,
        SignalBatch,
        batch_id=batch.id,
        tenant_id=current_user.tenant_id,
    )
    mechanistic_context = _extract_signal_mechanistic_context(signal_batch) if signal_batch else {}
    result = run_closed_loop_simulation(
        batch_code=batch.batch_id,
        species=batch.species,
        substrate=batch.substrate,
        dm_in=batch.dm_in,
        dm_out=batch.dm_out,
        temperature=batch.temperature,
        moisture=batch.moisture,
        density=batch.density,
        mechanistic_context=mechanistic_context,
        config=ClosedLoopSimulationConfig(
            num_cycles=body.num_cycles,
            seed=body.seed,
            feed_amount_g=body.feed_amount_g,
            task_name=body.task_name,
        ),
    )
    return ClosedLoopSimulationResponse.model_validate(result)


@router.post("/closed-loop/simulate/table", response_model=ClosedLoopSimulationTableResponse)
async def simulate_closed_loop_table(
    body: ClosedLoopSimulationRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    batch = await _get_batch_or_404(db, body.batch_id, current_user.tenant_id)
    signal_batch = await _latest_for_batch(
        db,
        SignalBatch,
        batch_id=batch.id,
        tenant_id=current_user.tenant_id,
    )
    mechanistic_context = _extract_signal_mechanistic_context(signal_batch) if signal_batch else {}
    simulation = run_closed_loop_simulation(
        batch_code=batch.batch_id,
        species=batch.species,
        substrate=batch.substrate,
        dm_in=batch.dm_in,
        dm_out=batch.dm_out,
        temperature=batch.temperature,
        moisture=batch.moisture,
        density=batch.density,
        mechanistic_context=mechanistic_context,
        config=ClosedLoopSimulationConfig(
            num_cycles=body.num_cycles,
            seed=body.seed,
            feed_amount_g=body.feed_amount_g,
            task_name=body.task_name,
        ),
    )
    return ClosedLoopSimulationTableResponse.model_validate(
        {
            "mode": simulation["mode"],
            "batch": simulation["batch"],
            "configuration": simulation["configuration"],
            "summary": simulation["summary"],
            "rows": build_closed_loop_table_rows(simulation),
            "disclaimer": simulation["disclaimer"],
        }
    )


@router.get("/signals", response_model=list[SignalBatchResponse])
async def list_signal_batches(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(SignalBatch)
        .where(SignalBatch.tenant_id == current_user.tenant_id)
        .order_by(desc(SignalBatch.created_at))
    )
    return [SignalBatchResponse.model_validate(item) for item in result.scalars().all()]


@router.post(
    "/signals",
    response_model=SignalBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_signal_batch(
    body: SignalBatchCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _get_batch_or_404(db, body.batch_id, current_user.tenant_id)
    persisted_payload = body.model_dump(
        exclude={
            "source_mode",
            "compiler_version",
            "compiled_from_batch_version",
            "compile_context",
            "freshness_score",
            "stability_score",
            "release_readiness_score",
        }
    )
    signal_batch = SignalBatch(
        **persisted_payload,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(signal_batch)
    await db.commit()
    await db.refresh(signal_batch)
    return SignalBatchResponse.model_validate(signal_batch)


@router.post("/signals/compile", response_model=SignalCompileResponse, status_code=status.HTTP_201_CREATED)
async def compile_signal(
    body: SignalCompileRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_flag_enabled(
        request,
        db,
        tenant_id=current_user.tenant_id,
        flag_name="bos_signal_compile",
    )
    batch = await _get_batch_or_404(db, body.batch_id, current_user.tenant_id)
    control_profile = None
    locality_profile = None
    if body.control_profile_id is not None:
        control_profile = await db.get(ControlAPIProfile, body.control_profile_id)
    if body.locality_profile_id is not None:
        locality_profile = await _get_locality_profile_or_404(db, body.locality_profile_id, current_user.tenant_id)

    signal_batch, compile_context = await compile_signal_for_batch(
        db,
        batch=batch,
        current_user=current_user,
        control_profile=control_profile,
        locality_profile=locality_profile,
        signal_api_version="SIG-1.0",
        compiler_version=body.compiler_version,
        notes=body.notes,
        dose_window_min=body.dose_window_min,
        dose_window_max=body.dose_window_max,
        stability_window_hours=body.stability_window_hours,
        kernel_residence_time_hours=body.kernel_residence_time_hours,
        apply_locality_shifts=body.apply_locality_shifts,
    )
    signal_batch.qc_markers = {
        **(signal_batch.qc_markers or {}),
        "compile_context": compile_context,
    }
    await db.commit()
    await db.refresh(signal_batch)
    payload = SignalCompileResponse.model_validate(signal_batch).model_dump()
    payload["compile_status"] = "compiled"
    payload["source_mode"] = "compiled"
    return SignalCompileResponse(**payload)


@router.post("/signals/{signal_batch_id}/refresh", response_model=SignalRefreshResponse)
async def refresh_signal(
    signal_batch_id: int,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_flag_enabled(
        request,
        db,
        tenant_id=current_user.tenant_id,
        flag_name="bos_signal_compile",
    )
    signal_batch = await _get_signal_batch_or_404(db, signal_batch_id, current_user.tenant_id)
    batch = await _get_batch_or_404(db, signal_batch.batch_id, current_user.tenant_id)
    refreshed = await refresh_signal_batch_state(db, signal_batch=signal_batch, batch=batch)
    await db.commit()
    await db.refresh(signal_batch)
    return SignalRefreshResponse(**refreshed)


@router.post("/signals/{signal_batch_id}/supervisor", response_model=SupervisorStateResponse)
async def evaluate_signal_supervisor(
    signal_batch_id: int,
    body: SupervisorObservationRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    signal_batch = await _get_signal_batch_or_404(db, signal_batch_id, current_user.tenant_id)
    decision = evaluate_bos_supervisor_state(
        uv254=body.uv254,
        od280=body.od280,
        do_value=body.do,
        ph=body.ph,
        elapsed_hours=body.elapsed_hours,
        previous_c_signal_hat=body.previous_c_signal_hat,
        previous_elapsed_hours=body.previous_elapsed_hours,
        previous_dc_dt_hat=body.previous_dc_dt_hat,
        previous_negative_slope_streak=body.previous_negative_slope_streak,
        confidence_threshold=body.confidence_threshold,
        negative_slope_persistence=body.negative_slope_persistence,
        observability_required=body.observability_required,
    )
    snapshot = persist_supervisor_snapshot(
        signal_batch,
        observation=body.model_dump(by_alias=True),
        decision={
            "c_signal_hat": decision.c_signal_hat,
            "dc_dt_hat": decision.dc_dt_hat,
            "confidence": decision.confidence,
            "missing_channels": decision.missing_channels,
            "channels_used": decision.channels_used,
            "information_loss": decision.information_loss,
            "observability_score": decision.observability_score,
            "negative_slope_streak": decision.negative_slope_streak,
            "trigger_reason": decision.trigger_reason,
            "recommended_handover": decision.recommended_handover,
            "expected_freshness_window_hours": decision.expected_freshness_window_hours,
        },
        mode="supervisor",
    )
    await refresh_audit_packet_for_signal(
        db,
        signal_batch=signal_batch,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(signal_batch)
    now = datetime.now(UTC)
    expected_handover = now + timedelta(hours=decision.expected_freshness_window_hours or 0.0)
    return SupervisorStateResponse(
        id=signal_batch.id,
        signal_batch_id=signal_batch.id,
        c_signal_hat=decision.c_signal_hat,
        dc_dt_hat=decision.dc_dt_hat,
        confidence=decision.confidence,
        observed_at=decision.computed_at,
        missing_channels=decision.missing_channels,
        channels_used=decision.channels_used,
        information_loss=decision.information_loss,
        observability_score=decision.observability_score,
        negative_slope_streak=decision.negative_slope_streak,
        trigger_reason=decision.trigger_reason,
        expected_handover=expected_handover,
        mechanistic_context={
            **_extract_signal_mechanistic_context(signal_batch),
            "supervisor_snapshot": snapshot,
        },
    )


@router.post(
    "/signals/{signal_batch_id}/handover-recommendation",
    response_model=HandoverRecommendationResponse,
)
async def get_handover_recommendation(
    signal_batch_id: int,
    body: SupervisorObservationRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    signal_batch = await _get_signal_batch_or_404(db, signal_batch_id, current_user.tenant_id)
    decision = evaluate_bos_supervisor_state(
        uv254=body.uv254,
        od280=body.od280,
        do_value=body.do,
        ph=body.ph,
        elapsed_hours=body.elapsed_hours,
        previous_c_signal_hat=body.previous_c_signal_hat,
        previous_elapsed_hours=body.previous_elapsed_hours,
        previous_dc_dt_hat=body.previous_dc_dt_hat,
        previous_negative_slope_streak=body.previous_negative_slope_streak,
        confidence_threshold=body.confidence_threshold,
        negative_slope_persistence=body.negative_slope_persistence,
        observability_required=body.observability_required,
    )
    snapshot = persist_supervisor_snapshot(
        signal_batch,
        observation=body.model_dump(by_alias=True),
        decision={
            "c_signal_hat": decision.c_signal_hat,
            "dc_dt_hat": decision.dc_dt_hat,
            "confidence": decision.confidence,
            "missing_channels": decision.missing_channels,
            "channels_used": decision.channels_used,
            "information_loss": decision.information_loss,
            "observability_score": decision.observability_score,
            "negative_slope_streak": decision.negative_slope_streak,
            "trigger_reason": decision.trigger_reason,
            "recommended_handover": decision.recommended_handover,
            "expected_freshness_window_hours": decision.expected_freshness_window_hours,
        },
        mode="handover",
    )
    await refresh_audit_packet_for_signal(
        db,
        signal_batch=signal_batch,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(signal_batch)
    expected_window = decision.expected_freshness_window_hours
    if signal_batch.stability_window_hours is not None and expected_window is not None:
        expected_window = round(min(signal_batch.stability_window_hours, expected_window), 2)
    expected_handover = datetime.now(UTC) + timedelta(hours=expected_window or 0.0)
    return HandoverRecommendationResponse(
        signal_batch_id=signal_batch.id,
        recommended_handover=decision.recommended_handover,
        trigger_reason=decision.trigger_reason or "monitor_signal",
        expected_freshness_window_hours=expected_window,
        c_signal_hat=decision.c_signal_hat,
        dc_dt_hat=decision.dc_dt_hat,
        confidence=decision.confidence,
        expected_handover=expected_handover,
        confidence_threshold=body.confidence_threshold,
        negative_slope_persistence=body.negative_slope_persistence,
        observability_required=body.observability_required,
        missing_channels=decision.missing_channels,
        channels_used=decision.channels_used,
        information_loss=decision.information_loss,
        observability_score=decision.observability_score,
        mechanistic_context={
            **_extract_signal_mechanistic_context(signal_batch),
            "supervisor_snapshot": snapshot,
        },
    )


@router.get("/control-profiles", response_model=list[ControlAPIProfileResponse])
async def list_control_profiles(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id)
        .order_by(desc(ControlAPIProfile.updated_at))
    )
    return [ControlAPIProfileResponse.model_validate(item) for item in result.scalars().all()]


@router.post(
    "/control-profiles",
    response_model=ControlAPIProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_control_profile(
    body: ControlAPIProfileCreate,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    profile = ControlAPIProfile(
        **body.model_dump(),
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return ControlAPIProfileResponse.model_validate(profile)


@router.get("/locality-profiles", response_model=list[LocalityProfileResponse])
async def list_locality_profiles(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(LocalityProfile)
        .where(LocalityProfile.tenant_id == current_user.tenant_id)
        .order_by(desc(LocalityProfile.updated_at))
    )
    return [LocalityProfileResponse.model_validate(item) for item in result.scalars().all()]


@router.post(
    "/locality-profiles",
    response_model=LocalityProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_locality_profile(
    body: LocalityProfileCreate,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    locality = LocalityProfile(
        **body.model_dump(),
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(locality)
    await db.commit()
    await db.refresh(locality)
    return LocalityProfileResponse.model_validate(locality)


@router.get("/executor-profiles", response_model=list[ExecutorProfileResponse])
async def list_executor_profiles(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(ExecutorProfile)
        .where(ExecutorProfile.tenant_id == current_user.tenant_id)
        .order_by(desc(ExecutorProfile.updated_at))
    )
    return [ExecutorProfileResponse.model_validate(item) for item in result.scalars().all()]


@router.post(
    "/executor-profiles",
    response_model=ExecutorProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_executor_profile(
    body: ExecutorProfileCreate,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    if body.locality_profile_id is not None:
        await _get_locality_profile_or_404(db, body.locality_profile_id, current_user.tenant_id)

    executor = ExecutorProfile(
        **body.model_dump(),
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(executor)
    await db.commit()
    await db.refresh(executor)
    return ExecutorProfileResponse.model_validate(executor)


@router.post("/release-decisions/evaluate", response_model=ReleaseDecisionResponse)
async def evaluate_release(
    body: ReleaseEvaluationRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    batch = await _get_batch_or_404(db, body.batch_id, current_user.tenant_id)
    (
        _signal,
        _control,
        _boundary,
        release_decision,
        _packet,
    ) = await evaluate_release_for_batch(
        db,
        batch=batch,
        current_user=current_user,
        control_profile_id=body.control_profile_id,
        signal_batch_id=body.signal_batch_id,
        locality_profile_id=body.locality_profile_id,
        persist=body.persist,
    )
    return serialize_release_decision(release_decision)


@router.get("/release-decisions", response_model=list[ReleaseDecisionResponse])
async def list_release_decisions(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(ReleaseDecision)
        .where(ReleaseDecision.tenant_id == current_user.tenant_id)
        .order_by(desc(ReleaseDecision.created_at))
    )
    return [serialize_release_decision(item) for item in result.scalars().all()]


@router.get("/release-decisions/batch/{batch_id}", response_model=ReleaseDecisionResponse)
async def get_release_decision_for_batch(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(ReleaseDecision)
        .where(
            ReleaseDecision.batch_id == batch_id,
            ReleaseDecision.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(ReleaseDecision.created_at))
        .limit(1)
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release decision not found")
    return serialize_release_decision(decision)


@router.post(
    "/release-decisions/{release_decision_id}/literature-evidence-links",
    response_model=LiteratureValueReleaseEvidenceLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_literature_evidence_link_for_release_decision(
    release_decision_id: int,
    payload: LiteratureValueReleaseEvidenceLinkCreateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        link = await create_literature_value_release_evidence_link(
            db,
            tenant_id=current_user.tenant_id,
            release_decision_id=release_decision_id,
            linked_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_release_evidence_link_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release decision not found")
    return link


@router.get("/boundary-ledgers/batch/{batch_id}", response_model=BoundaryLedgerResponse)
async def get_boundary_ledger_for_batch(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(BoundaryLedger)
        .where(
            BoundaryLedger.batch_id == batch_id,
            BoundaryLedger.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(BoundaryLedger.created_at))
        .limit(1)
    )
    ledger = result.scalar_one_or_none()
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boundary ledger not found")
    return BoundaryLedgerResponse.model_validate(ledger)


@router.post(
    "/portability-audits",
    response_model=PortabilityAuditResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_portability_audit(
    body: PortabilityAuditCreate,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    signal_batch = await _get_signal_batch_or_404(db, body.signal_batch_id, current_user.tenant_id)
    executor_profile = await _get_executor_profile_or_404(db, body.executor_profile_id, current_user.tenant_id)
    locality_profile = None
    if body.locality_profile_id is not None:
        locality_profile = await _get_locality_profile_or_404(db, body.locality_profile_id, current_user.tenant_id)

    control_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at))
        .limit(1)
    )
    control_profile = control_result.scalar_one_or_none()

    persisted_payload = body.model_dump(exclude={"override_outcome"})
    audit = PortabilityAudit(
        **persisted_payload,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(audit)
    await db.flush()
    recommendation = recommend_portability(
        signal_batch=signal_batch,
        executor_profile=executor_profile,
        locality_profile=locality_profile,
        control_profile=control_profile,
    )
    await refresh_audit_packet_for_signal(
        db,
        signal_batch=signal_batch,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(audit)
    return serialize_portability_audit(audit, recommendation)


@router.get("/portability-audits", response_model=list[PortabilityAuditResponse])
async def list_all_portability_audits(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(PortabilityAudit)
        .where(PortabilityAudit.tenant_id == current_user.tenant_id)
        .order_by(desc(PortabilityAudit.created_at))
    )
    audits = result.scalars().all()
    control_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at))
        .limit(1)
    )
    control_profile = control_result.scalar_one_or_none()

    signal_ids = {audit.signal_batch_id for audit in audits}
    executor_ids = {audit.executor_profile_id for audit in audits}
    locality_ids = {audit.locality_profile_id for audit in audits if audit.locality_profile_id is not None}

    signals = {
        item.id: item
        for item in (
            await db.execute(select(SignalBatch).where(SignalBatch.id.in_(signal_ids)))
        ).scalars().all()
    } if signal_ids else {}
    executors = {
        item.id: item
        for item in (
            await db.execute(select(ExecutorProfile).where(ExecutorProfile.id.in_(executor_ids)))
        ).scalars().all()
    } if executor_ids else {}
    localities = {
        item.id: item
        for item in (
            await db.execute(select(LocalityProfile).where(LocalityProfile.id.in_(locality_ids)))
        ).scalars().all()
    } if locality_ids else {}

    return [
        serialize_portability_audit(
            audit,
            recommend_portability(
                signal_batch=signals[audit.signal_batch_id],
                executor_profile=executors[audit.executor_profile_id],
                locality_profile=localities.get(audit.locality_profile_id) if audit.locality_profile_id else None,
                control_profile=control_profile,
            ) if audit.signal_batch_id in signals and audit.executor_profile_id in executors else None,
        )
        for audit in audits
    ]


@router.get("/portability-audits/signal/{signal_batch_id}", response_model=list[PortabilityAuditResponse])
async def list_portability_audits(
    signal_batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(PortabilityAudit)
        .where(
            PortabilityAudit.signal_batch_id == signal_batch_id,
            PortabilityAudit.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(PortabilityAudit.created_at))
    )
    audits = result.scalars().all()
    control_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at))
        .limit(1)
    )
    control_profile = control_result.scalar_one_or_none()
    signal_batch = await _get_signal_batch_or_404(db, signal_batch_id, current_user.tenant_id)
    executor_ids = {audit.executor_profile_id for audit in audits}
    locality_ids = {audit.locality_profile_id for audit in audits if audit.locality_profile_id is not None}
    executors = {
        item.id: item
        for item in (
            await db.execute(select(ExecutorProfile).where(ExecutorProfile.id.in_(executor_ids)))
        ).scalars().all()
    } if executor_ids else {}
    localities = {
        item.id: item
        for item in (
            await db.execute(select(LocalityProfile).where(LocalityProfile.id.in_(locality_ids)))
        ).scalars().all()
    } if locality_ids else {}
    return [
        serialize_portability_audit(
            audit,
            recommend_portability(
                signal_batch=signal_batch,
                executor_profile=executors[audit.executor_profile_id],
                locality_profile=localities.get(audit.locality_profile_id) if audit.locality_profile_id else None,
                control_profile=control_profile,
            ) if audit.executor_profile_id in executors else None,
        )
        for audit in audits
    ]


@router.post(
    "/portability-audits/recommendation",
    response_model=PortabilityRecommendationResponse,
)
async def get_portability_recommendation(
    body: PortabilityRecommendationRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    signal_batch = await _get_signal_batch_or_404(db, body.signal_batch_id, current_user.tenant_id)
    executor_profile = await _get_executor_profile_or_404(db, body.executor_profile_id, current_user.tenant_id)
    locality_profile = None
    if body.locality_profile_id is not None:
        locality_profile = await _get_locality_profile_or_404(db, body.locality_profile_id, current_user.tenant_id)

    control_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at))
        .limit(1)
    )
    control_profile = control_result.scalar_one_or_none()

    return recommend_portability(
        signal_batch=signal_batch,
        executor_profile=executor_profile,
        locality_profile=locality_profile,
        control_profile=control_profile,
    )


@router.get("/audit-packets", response_model=list[AuditPacketResponse])
async def list_audit_packets(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(AuditPacket)
        .where(AuditPacket.tenant_id == current_user.tenant_id)
        .order_by(desc(AuditPacket.created_at), desc(AuditPacket.id))
    )
    return [serialize_audit_packet(item) for item in result.scalars().all()]


@router.get("/audit-packets/batch/{batch_id}", response_model=AuditPacketResponse)
async def get_audit_packet_for_batch(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(AuditPacket)
        .where(
            AuditPacket.batch_id == batch_id,
            AuditPacket.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(AuditPacket.created_at), desc(AuditPacket.id))
        .limit(1)
    )
    packet = result.scalar_one_or_none()
    if not packet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit packet not found")
    return serialize_audit_packet(packet)


@router.get("/audit-packets/batch/{batch_id}/export")
async def export_audit_packet_for_batch(
    batch_id: int,
    format: str = Query("md", pattern=r"^(md|json)$"),
    request: Request = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_flag_enabled(
        request,
        db,
        tenant_id=current_user.tenant_id,
        flag_name="bos_audit_export",
    )

    result = await db.execute(
        select(AuditPacket)
        .where(
            AuditPacket.batch_id == batch_id,
            AuditPacket.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(AuditPacket.created_at), desc(AuditPacket.id))
        .limit(1)
    )
    packet = result.scalar_one_or_none()
    if packet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit packet not found")

    serialized = serialize_audit_packet(packet)
    export_date = date.today().isoformat()

    if format == "json":
        payload = render_audit_packet_json(serialized)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_packet_{batch_id}_{export_date}.json",
            },
        )

    payload = render_audit_packet_markdown(serialized)
    return StreamingResponse(
        io.StringIO(payload),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=audit_packet_{batch_id}_{export_date}.md",
        },
    )
