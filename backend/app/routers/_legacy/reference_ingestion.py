"""
Staged reference-ingestion routes.
"""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.deps import require_minimum_role
from app.schemas.reference_ingestion import (
    ReferenceIngestionHealthResponse,
    ReferenceIngestionListResponse,
    ReferenceIngestionMode,
    ReferenceIngestionPromoteRequest,
    ReferenceIngestionPromoteResponse,
    ReferenceIngestionStagedItem,
)
from app.services.reference_ingestion_service import reference_ingestion_service

router = APIRouter()


def _parse_units_json(units_json: str | None) -> dict[str, str]:
    if not units_json:
        return {}
    try:
        payload = json.loads(units_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="units_json must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="units_json must be a JSON object")
    return {str(key): str(value) for key, value in payload.items()}


@router.get("/health", response_model=ReferenceIngestionHealthResponse)
async def reference_ingestion_health(
    current_user=Depends(require_minimum_role("operator")),
):
    return reference_ingestion_service.get_health(current_user.tenant_id)


@router.post(
    "/parse",
    response_model=ReferenceIngestionStagedItem,
    status_code=status.HTTP_201_CREATED,
)
async def parse_reference_document(
    file: UploadFile = File(...),
    source_title: str | None = Form(None),
    source_type: str = Form("pdf"),
    source_owner: str | None = Form(None),
    license_note: str | None = Form(None),
    region: str | None = Form(None),
    units_json: str | None = Form(None),
    ingestion_mode: ReferenceIngestionMode = Form("manual_review_first"),
    human_review_required: bool = Form(True),
    current_user=Depends(require_minimum_role("operator")),
):
    filename = file.filename or "source.pdf"
    if source_type == "pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are supported in phase 1")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    return reference_ingestion_service.parse_document(
        tenant_id=current_user.tenant_id,
        filename=filename,
        content=content,
        source_title=source_title,
        source_type=source_type,
        source_owner=source_owner,
        license_note=license_note,
        region=region,
        units=_parse_units_json(units_json),
        ingestion_mode=ingestion_mode,
        human_review_required=human_review_required,
    )


@router.get("/staged", response_model=ReferenceIngestionListResponse)
async def list_staged_reference_documents(
    current_user=Depends(require_minimum_role("operator")),
):
    items = reference_ingestion_service.list_staged_items(current_user.tenant_id)
    return ReferenceIngestionListResponse(items=items, count=len(items))


@router.get("/staged/{item_id}", response_model=ReferenceIngestionStagedItem)
async def get_staged_reference_document(
    item_id: str,
    current_user=Depends(require_minimum_role("operator")),
):
    item = reference_ingestion_service.get_staged_item(current_user.tenant_id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staged reference document not found")
    return item


@router.post(
    "/staged/{item_id}/promote",
    response_model=ReferenceIngestionPromoteResponse,
)
async def promote_staged_reference_document(
    item_id: str,
    body: ReferenceIngestionPromoteRequest,
    current_user=Depends(require_minimum_role("operator")),
):
    if body.target_type != "campaign":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only campaign promotion is supported in phase 1")

    try:
        promoted = reference_ingestion_service.promote_to_campaign(
            tenant_id=current_user.tenant_id,
            item_id=item_id,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if promoted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staged reference document not found")

    staged_item, campaign = promoted
    return ReferenceIngestionPromoteResponse(staged_item=staged_item, campaign=campaign)
