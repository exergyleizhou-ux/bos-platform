"""
BOS Pipeline v9.0 - Species Database Router

API endpoints for querying the species reference database.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import require_minimum_role
from app.models import User
from app.engine.species_db import (
    CandidateReviewStatus,
    compare_species,
    get_all_bioexecutor_candidates,
    get_all_species,
    get_bioexecutor_candidate,
    get_bioexecutor_candidate_codes,
    get_optimal_ranges,
    get_species,
    get_species_codes,
    get_species_summary,
)

router = APIRouter()


def _candidate_payload(candidate):
    return {
        "code": candidate.code,
        "scientific_name": candidate.scientific_name,
        "common_name": candidate.common_name,
        "source_kind": candidate.source_kind,
        "source_ref": candidate.source_ref,
        "license_note": candidate.license_note,
        "ingestion_mode": candidate.ingestion_mode,
        "human_review_required": candidate.human_review_required,
        "review_status": candidate.review_status,
        "candidate_scope": candidate.candidate_scope,
        "notes": candidate.notes,
        "references": list(candidate.references),
        "related_feedstocks": list(candidate.related_feedstocks),
    }


@router.get("")
async def list_species(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """List all supported species."""
    species_list = get_all_species()
    return {
        "species": [
            {
                "code": sp.code,
                "scientific_name": sp.scientific_name,
                "common_name": sp.common_name,
                "aliases": list(sp.aliases),
                "source_basis": sp.source_basis,
                "notes": sp.notes,
                "references": list(sp.references),
                "ser_typical": sp.ser_typical,
                "development_days": sp.development_days,
                "protein_content": sp.protein_content,
                "fat_content": sp.fat_content,
            }
            for sp in species_list
        ],
        "count": len(species_list),
    }


@router.get("/codes")
async def list_species_codes(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Get all supported species codes."""
    return {"codes": get_species_codes()}


@router.get("/candidates")
async def list_bioexecutor_candidates(
    review_status: CandidateReviewStatus | None = Query(
        None,
        description="Filter candidates by review status without reading validated species defaults.",
    ),
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """List review-gated external bioexecutor candidates."""
    del current_user
    candidates = get_all_bioexecutor_candidates(review_status=review_status)
    return {
        "candidates": [_candidate_payload(candidate) for candidate in candidates],
        "count": len(candidates),
        "validated_species_codes": get_species_codes(),
        "candidate_codes": get_bioexecutor_candidate_codes(),
    }


@router.get("/candidates/{candidate_code}")
async def get_bioexecutor_candidate_detail(
    candidate_code: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Get a review-gated external bioexecutor candidate."""
    del current_user
    candidate = get_bioexecutor_candidate(candidate_code)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown bioexecutor candidate: {candidate_code}. Available: {get_bioexecutor_candidate_codes()}",
        )
    return _candidate_payload(candidate)


@router.get("/{species_code}")
async def get_species_detail(
    species_code: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Get detailed parameters for a species."""
    summary = get_species_summary(species_code)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown species: {species_code}. Available: {get_species_codes()}",
        )
    return summary


@router.get("/{species_code}/ranges")
async def get_ranges(
    species_code: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Get optimal operating ranges for a species."""
    ranges = get_optimal_ranges(species_code)
    if not ranges:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown species: {species_code}")

    sp = get_species(species_code)
    return {
        "species": species_code,
        "common_name": sp.common_name if sp else None,
        "ranges": ranges,
    }


@router.post("/compare")
async def compare_species_endpoint(
    codes: List[str] = Query(..., min_length=2, max_length=10, description="Species codes to compare"),
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Compare parameters across multiple species."""
    result = compare_species(codes)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid species found in the provided codes",
        )

    return {
        "comparison": result,
        "species_count": len(result),
    }
