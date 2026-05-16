"""
BOS Pipeline v9.0 — Bayesian A/B Testing Router

API endpoints for Bayesian hypothesis testing.
"""

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User, Calculation
from app.engine.bayesian_engine import BayesianABInput, run_bayesian_ab

router = APIRouter()


class BayesianABRequest(BaseModel):
    """Bayesian A/B test request."""

    # Continuous (normal model)
    group_a_values: Optional[List[float]] = None
    group_b_values: Optional[List[float]] = None

    # Binary (beta-binomial model)
    group_a_successes: Optional[int] = Field(None, ge=0)
    group_a_trials: Optional[int] = Field(None, ge=1)
    group_b_successes: Optional[int] = Field(None, ge=0)
    group_b_trials: Optional[int] = Field(None, ge=1)

    model: str = Field(default="normal", pattern=r"^(normal|beta_binomial)$")
    n_posterior_samples: int = Field(default=100_000, ge=1000, le=1_000_000)
    rope_lower: float = Field(default=-0.01)
    rope_upper: float = Field(default=0.01)
    group_a_name: str = Field(default="Control", max_length=100)
    group_b_name: str = Field(default="Treatment", max_length=100)
    metric_name: str = Field(default="SER", max_length=100)
    seed: Optional[int] = None


@router.post("/test")
async def run_bayesian_test(
    body: BayesianABRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Run a Bayesian A/B test comparing two groups."""
    start_time = time.perf_counter()

    ab_input = BayesianABInput(
        group_a_values=body.group_a_values,
        group_b_values=body.group_b_values,
        group_a_successes=body.group_a_successes,
        group_a_trials=body.group_a_trials,
        group_b_successes=body.group_b_successes,
        group_b_trials=body.group_b_trials,
        model=body.model,
        n_posterior_samples=body.n_posterior_samples,
        rope_lower=body.rope_lower,
        rope_upper=body.rope_upper,
        group_a_name=body.group_a_name,
        group_b_name=body.group_b_name,
        metric_name=body.metric_name,
        seed=body.seed,
    )

    ab_result = run_bayesian_ab(ab_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if ab_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": ab_result.errors},
        )

    # Persist
    calc = Calculation(
        batch_id=None,
        calc_type="bayesian_ab",
        status="completed",
        inputs={
            "model": body.model,
            "group_a_name": body.group_a_name,
            "group_b_name": body.group_b_name,
            "n_posterior_samples": body.n_posterior_samples,
        },
        result={
            "prob_b_better": ab_result.prob_b_better,
            "effect_mean": ab_result.effect_mean,
            "confidence": ab_result.confidence,
            "recommendation": ab_result.recommendation,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=ab_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "probabilities": {
            "b_better": ab_result.prob_b_better,
            "a_better": ab_result.prob_a_better,
            "practically_equivalent": ab_result.prob_rope,
        },
        "effect": {
            "mean": ab_result.effect_mean,
            "std": ab_result.effect_std,
            "ci_95": [ab_result.effect_ci_lower, ab_result.effect_ci_upper],
        },
        "posteriors": {
            "a": {"mean": ab_result.posterior_a_mean, "std": ab_result.posterior_a_std},
            "b": {"mean": ab_result.posterior_b_mean, "std": ab_result.posterior_b_std},
        },
        "decision": {
            "recommendation": ab_result.recommendation,
            "confidence": ab_result.confidence,
        },
        "histogram": {
            "bins": ab_result.effect_histogram_bins,
            "counts": ab_result.effect_histogram_counts,
        },
        "groups": {
            "a_name": body.group_a_name,
            "b_name": body.group_b_name,
        },
        "computation_time_ms": ab_result.computation_time_ms,
    }
