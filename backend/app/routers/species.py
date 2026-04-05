"""
BOS Pipeline v9.0 �� Species Database Router

API endpoints for querying the species reference database.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import require_minimum_role
from app.models import User
from app.engine.species_db import (
    get_species,
    get_all_species,
    get_species_codes,
    get_optimal_ranges,
    compare_species,
    get_species_summary,
)

router = APIRouter()


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
