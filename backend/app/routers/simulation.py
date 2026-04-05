"""
BOS Pipeline v9.0 - simulation router.

This module exposes the richer v9 Monte Carlo endpoint and also keeps the
frontend-compatible aliases grouped under `/simulation/*`.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.engine.bayesian_ab import (
    BayesianABInput as LegacyBayesianABInput,
    run_bayesian_ab as run_legacy_bayesian_ab,
)
from app.engine.forecast import ForecastInput as LegacyForecastInput, run_forecast
from app.engine.monte_carlo_engine import MCInput, run_monte_carlo
from app.engine.sensitivity import (
    SensitivityInput as LegacySensitivityInput,
    run_sensitivity,
)
from app.models import Batch, Calculation, User
from app.schemas import MonteCarloRequest, MonteCarloResponse

router = APIRouter()


@router.post("/run", response_model=MonteCarloResponse)
async def run_simulation(
    body: MonteCarloRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Run Monte Carlo simulation for SER uncertainty quantification."""
    start_time = time.perf_counter()

    result = await db.execute(
        select(Batch).where(
            Batch.id == body.batch_id,
            Batch.tenant_id == current_user.tenant_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    mc_input = MCInput(
        n_samples=body.n_samples,
        dm_in_mean=body.dm_in_mean,
        dm_in_std=body.dm_in_std,
        dm_out_mean=body.dm_out_mean,
        dm_out_std=body.dm_out_std,
        seed=body.seed,
    )
    mc_result = run_monte_carlo(mc_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if mc_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": mc_result.errors},
        )

    calc = Calculation(
        batch_id=body.batch_id,
        calc_type="monte_carlo",
        status="completed",
        inputs=body.model_dump(),
        result={
            "ser_mean": mc_result.ser_mean,
            "ser_std": mc_result.ser_std,
            "ser_median": mc_result.ser_median,
            "ser_ci_lower": mc_result.ser_ci_lower,
            "ser_ci_upper": mc_result.ser_ci_upper,
            "pass_probability": mc_result.pass_probability,
            "grade_probabilities": mc_result.grade_probabilities,
        },
        ser_value=mc_result.ser_mean,
        passed=mc_result.pass_probability >= 0.5,
        mc_samples=mc_result.n_samples,
        duration_ms=round(duration_ms, 2),
        engine_version=mc_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return MonteCarloResponse(
        n_samples=mc_result.n_samples,
        ser_mean=mc_result.ser_mean,
        ser_std=mc_result.ser_std,
        ser_median=mc_result.ser_median,
        ser_ci_lower=mc_result.ser_ci_lower,
        ser_ci_upper=mc_result.ser_ci_upper,
        percentiles=mc_result.percentiles,
        pass_probability=mc_result.pass_probability,
        histogram_bins=mc_result.histogram_bins,
        histogram_counts=mc_result.histogram_counts,
        computation_time_ms=mc_result.computation_time_ms,
    )


@router.post("/quick")
async def quick_simulation(
    dm_in_mean: float,
    dm_out_mean: float,
    dm_in_std: float = 0.5,
    dm_out_std: float = 0.3,
    n_samples: int = 5000,
    current_user: User = Depends(require_minimum_role("operator")),
):
    """Quick Monte Carlo simulation without batch association."""
    del current_user
    mc_input = MCInput(
        n_samples=min(n_samples, 100_000),
        dm_in_mean=dm_in_mean,
        dm_in_std=dm_in_std,
        dm_out_mean=dm_out_mean,
        dm_out_std=dm_out_std,
    )
    mc_result = run_monte_carlo(mc_input)
    return {
        "ser_mean": mc_result.ser_mean,
        "ser_std": mc_result.ser_std,
        "ci_95": [mc_result.ser_ci_lower, mc_result.ser_ci_upper],
        "pass_probability": mc_result.pass_probability,
        "computation_time_ms": mc_result.computation_time_ms,
    }


@router.post("/monte-carlo")
async def monte_carlo_alias(
    body: MonteCarloRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Frontend/test-compatible alias for Monte Carlo simulation."""
    response = await run_simulation(body=body, current_user=current_user, db=db)
    return {
        "n_samples": response.n_samples,
        "n_simulations": response.n_samples,
        "ser_mean": response.ser_mean,
        "ser_std": response.ser_std,
        "ser_median": response.ser_median,
        "ser_p5": response.percentiles.get("p5"),
        "ser_p95": response.percentiles.get("p95"),
        "ser_ci_lower": response.ser_ci_lower,
        "ser_ci_upper": response.ser_ci_upper,
        "percentiles": response.percentiles,
        "pass_probability": response.pass_probability,
        "histogram_bins": response.histogram_bins,
        "histogram_counts": response.histogram_counts,
        "computation_time_ms": response.computation_time_ms,
    }


@router.post("/sensitivity")
async def sensitivity_alias(
    body: dict[str, Any],
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Frontend-compatible sensitivity analysis endpoint."""
    del current_user
    result = run_sensitivity(
        LegacySensitivityInput(
            dm_in=float(body.get("dm_in", 10.0)),
            dm_out=float(body.get("dm_out", 8.0)),
            n_in=float(body.get("n_in", 0.0) or 0.0),
            n_larvae=float(body.get("n_larvae", 0.0) or 0.0),
            n_frass=float(body.get("n_frass", 0.0) or 0.0),
            variation_pct=float(body.get("variation_pct", 0.2)),
            n_steps=int(body.get("n_steps", 10)),
        )
    )
    return {
        "base_ser": result.base_ser,
        "parameter_ranking": result.parameter_ranking,
        "impact_scores": result.impact_scores,
        "sweep_results": {
            key: [
                {
                    "parameter_value": point["x"],
                    "ser_value": point["ser"],
                    "variation_pct": float(body.get("variation_pct", 0.2)),
                }
                for point in points
            ]
            for key, points in result.sweep_results.items()
        },
    }


@router.post("/bayesian-ab")
async def bayesian_ab_alias(
    body: dict[str, Any],
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Frontend-compatible Bayesian A/B endpoint."""
    del current_user
    result = run_legacy_bayesian_ab(
        LegacyBayesianABInput(
            group_a=[float(item) for item in body.get("group_a", [])],
            group_b=[float(item) for item in body.get("group_b", [])],
            n_samples=int(body.get("n_samples", 10000)),
        )
    )
    effect_samples = [
        b - a for a, b in zip(result.posterior_a, result.posterior_b)
    ]
    effect_samples.sort()
    lower_idx = int(len(effect_samples) * 0.025)
    upper_idx = int(len(effect_samples) * 0.975) - 1
    return {
        "mean_a": result.mean_a,
        "mean_b": result.mean_b,
        "std_a": 0.0,
        "std_b": 0.0,
        "prob_b_better": result.prob_b_better,
        "effect_size": result.effect_size,
        "ci_effect_lower": effect_samples[max(lower_idx, 0)],
        "ci_effect_upper": effect_samples[max(upper_idx, 0)],
        "decision": result.decision,
        "confidence": result.confidence,
        "posterior_a": result.posterior_a,
        "posterior_b": result.posterior_b,
    }


@router.post("/forecast")
async def forecast_alias(
    body: dict[str, Any],
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Frontend-compatible forecast endpoint."""
    del current_user
    method = str(body.get("method", "sma"))
    if method == "ar":
        method = "ewma"
    result = run_forecast(
        LegacyForecastInput(
            values=[float(item) for item in body.get("values", [])],
            method=method,
            horizon=int(body.get("horizon", 5)),
            window=int(body.get("window", 3) or 3),
            alpha=float(body.get("alpha", 0.3) or 0.3),
            beta=float(body.get("beta", 0.1) or 0.1),
        )
    )
    return {
        "forecast": result.forecast,
        "ci_lower": result.ci_lower,
        "ci_upper": result.ci_upper,
        "method": result.method,
        "horizon": result.horizon,
        "mape": result.mape,
        "rmse": result.rmse,
    }
