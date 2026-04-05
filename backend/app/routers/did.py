"""
BOS Pipeline v9.0 �� Difference-in-Differences Router

API endpoints for causal inference via DiD analysis.
"""

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User, Calculation
from app.engine.did_engine import DiDInput, compute_did

router = APIRouter()


class DiDRequest(BaseModel):
    """DiD analysis request."""

    treatment_pre: List[float] = Field(..., min_length=2, description="Treatment group, before intervention")
    treatment_post: List[float] = Field(..., min_length=2, description="Treatment group, after intervention")
    control_pre: List[float] = Field(..., min_length=2, description="Control group, before intervention")
    control_post: List[float] = Field(..., min_length=2, description="Control group, after intervention")
    outcome_name: str = Field(default="SER", max_length=100)
    treatment_name: str = Field(default="Process Change", max_length=255)
    confidence_level: float = Field(default=0.95, ge=0.80, le=0.99)


@router.post("/analyze")
async def analyze_did(
    body: DiDRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Perform Difference-in-Differences analysis.

    Estimates the causal effect of a process change on the outcome,
    controlling for temporal trends using a control group.
    """
    start_time = time.perf_counter()

    did_input = DiDInput(
        treatment_pre=body.treatment_pre,
        treatment_post=body.treatment_post,
        control_pre=body.control_pre,
        control_post=body.control_post,
        outcome_name=body.outcome_name,
        treatment_name=body.treatment_name,
        confidence_level=body.confidence_level,
    )

    did_result = compute_did(did_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if did_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": did_result.errors},
        )

    # Persist
    calc = Calculation(
        batch_id=None,
        calc_type="did",
        status="completed",
        inputs=body.model_dump(),
        result={
            "att": did_result.att,
            "se": did_result.se,
            "t_stat": did_result.t_stat,
            "p_value": did_result.p_value,
            "ci_lower": did_result.ci_lower,
            "ci_upper": did_result.ci_upper,
            "significant": did_result.significant,
            "cohens_d": did_result.cohens_d,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=did_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "treatment_effect": {
            "att": did_result.att,
            "se": did_result.se,
            "t_stat": did_result.t_stat,
            "p_value": did_result.p_value,
            "ci": [did_result.ci_lower, did_result.ci_upper],
            "significant": did_result.significant,
            "cohens_d": did_result.cohens_d,
        },
        "group_means": {
            "treatment_pre": did_result.treat_pre_mean,
            "treatment_post": did_result.treat_post_mean,
            "control_pre": did_result.control_pre_mean,
            "control_post": did_result.control_post_mean,
        },
        "changes": {
            "treatment": did_result.treat_change,
            "control": did_result.control_change,
        },
        "parallel_trends": {
            "plausible": did_result.parallel_trends_plausible,
            "message": did_result.parallel_trends_message,
        },
        "sample_sizes": {
            "treatment": did_result.n_treatment,
            "control": did_result.n_control,
        },
        "outcome_name": did_result.outcome_name,
        "treatment_name": did_result.treatment_name,
        "confidence_level": did_result.confidence_level,
        "computation_time_ms": round(duration_ms, 2),
    }
