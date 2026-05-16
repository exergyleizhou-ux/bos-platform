"""
BOS Pipeline v9.0 - Feedstock reference router.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_minimum_role
from app.engine.feedstock_db import (
    CandidateReviewStatus,
    get_all_feedstock_candidates,
    get_all_feedstocks,
    get_feedstock,
    get_feedstock_candidate,
    get_feedstock_candidate_keys,
    get_feedstock_keys,
)
from app.models import User

router = APIRouter()


def _candidate_payload(candidate):
    return {
        "key": candidate.key,
        "display_name": candidate.display_name,
        "category": candidate.category,
        "risk_tier": candidate.risk_tier,
        "source_kind": candidate.source_kind,
        "source_ref": candidate.source_ref,
        "license_note": candidate.license_note,
        "ingestion_mode": candidate.ingestion_mode,
        "human_review_required": candidate.human_review_required,
        "review_status": candidate.review_status,
        "candidate_scope": candidate.candidate_scope,
        "suitability_notes": candidate.suitability_notes,
        "references": list(candidate.references),
        "aliases": list(candidate.aliases),
    }


@router.get("")
async def list_feedstocks(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    del current_user
    items = get_all_feedstocks()
    return {
        "feedstocks": [
            {
                "key": item.key,
                "display_name": item.display_name,
                "category": item.category,
                "typical_cn_min": item.typical_cn_min,
                "typical_cn_max": item.typical_cn_max,
                "moisture_risk": item.moisture_risk,
                "contamination_risk": item.contamination_risk,
                "lignocellulose_severity": item.lignocellulose_severity,
                "suitability_notes": item.suitability_notes,
                "evidence_basis": item.evidence_basis,
                "references": list(item.references),
            }
            for item in items
        ],
        "count": len(items),
    }


@router.get("/keys")
async def list_feedstock_keys(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    del current_user
    return {"keys": get_feedstock_keys()}


@router.get("/candidates")
async def list_feedstock_candidates(
    review_status: CandidateReviewStatus | None = None,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    del current_user
    candidates = get_all_feedstock_candidates(review_status=review_status)
    return {
        "candidates": [_candidate_payload(candidate) for candidate in candidates],
        "count": len(candidates),
        "validated_feedstock_keys": get_feedstock_keys(),
        "candidate_keys": get_feedstock_candidate_keys(),
    }


@router.get("/candidates/{candidate_key}")
async def get_feedstock_candidate_detail(
    candidate_key: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    del current_user
    candidate = get_feedstock_candidate(candidate_key)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown feedstock candidate: {candidate_key}. Available: {get_feedstock_candidate_keys()}",
        )
    return _candidate_payload(candidate)


@router.get("/{feedstock_key}")
async def get_feedstock_detail(
    feedstock_key: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    del current_user
    item = get_feedstock(feedstock_key)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown feedstock: {feedstock_key}. Available: {get_feedstock_keys()}",
        )
    return {
        "key": item.key,
        "display_name": item.display_name,
        "category": item.category,
        "typical_cn_min": item.typical_cn_min,
        "typical_cn_max": item.typical_cn_max,
        "moisture_risk": item.moisture_risk,
        "contamination_risk": item.contamination_risk,
        "lignocellulose_severity": item.lignocellulose_severity,
        "suitability_notes": item.suitability_notes,
        "evidence_basis": item.evidence_basis,
        "references": list(item.references),
    }
