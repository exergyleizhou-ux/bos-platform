"""
BOS Pipeline v9.0 Monte Carlo simulation router.

API endpoints for Monte Carlo, sensitivity, Bayesian A/B, and forecast workflows.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.engine.bayesian_engine import BayesianABInput, run_bayesian_ab
from app.engine.forecast import ForecastInput, run_forecast
from app.engine.monte_carlo_engine import MCInput, run_monte_carlo
from app.engine.sensitivity_engine import SensitivityInput, run_sensitivity_analysis
from app.models import Batch, Calculation, User
from app.schemas import MonteCarloRequest, MonteCarloResponse

router = APIRouter()


@router.post("/monte-carlo", response_model=MonteCarloResponse)
@router.post("/run", response_model=MonteCarloResponse)
async def run_simulation(
    body: MonteCarloRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Run Monte Carlo simulation for SER uncertainty quantification.

    Supports both the current `/monte-carlo` route and the legacy `/run` alias.
    """
    start_time = time.perf_counter()

    result = await db.execute(
        select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

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


@router.post("/sensitivity")
async def sensitivity_simulation(
    body: dict,
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Run sensitivity analysis using the current engine."""
    del current_user
    sa_input = SensitivityInput(
        method=body.get("method", "sobol"),
        n_samples=body.get("n_samples", 1024),
        parameters=body.get("parameters", {}),
        seed=body.get("seed"),
    )
    sa_result = run_sensitivity_analysis(sa_input)
    if sa_result.errors:
        raise HTTPException(status_code=422, detail={"errors": sa_result.errors})
    return {
        "method": sa_result.method,
        "parameter_ranking": sa_result.parameter_ranking,
        "first_order": sa_result.first_order,
        "total_order": sa_result.total_order,
        "mu_star": sa_result.mu_star,
        "sigma": sa_result.sigma,
        "n_samples": sa_result.n_samples,
    }


@router.post("/bayesian-ab")
async def bayesian_ab_simulation(
    body: dict,
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Run Bayesian A/B comparison using the current engine."""
    del current_user
    ab_input = BayesianABInput(
        group_a_values=body.get("group_a_values"),
        group_b_values=body.get("group_b_values"),
        group_a_successes=body.get("group_a_successes"),
        group_a_trials=body.get("group_a_trials"),
        group_b_successes=body.get("group_b_successes"),
        group_b_trials=body.get("group_b_trials"),
        model=body.get("model", "normal"),
        n_posterior_samples=body.get("n_posterior_samples", 100_000),
        rope_lower=body.get("rope_lower", -0.01),
        rope_upper=body.get("rope_upper", 0.01),
        group_a_name=body.get("group_a_name", "Control"),
        group_b_name=body.get("group_b_name", "Treatment"),
        metric_name=body.get("metric_name", "SER"),
        seed=body.get("seed"),
    )
    ab_result = run_bayesian_ab(ab_input)
    if ab_result.errors:
        raise HTTPException(status_code=422, detail={"errors": ab_result.errors})
    return {
        "decision": ab_result.recommendation,
        "confidence": ab_result.confidence,
        "prob_b_better": ab_result.prob_b_better,
        "prob_a_better": ab_result.prob_a_better,
        "prob_rope": ab_result.prob_rope,
    }


@router.post("/forecast")
async def forecast_simulation(
    body: dict,
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Run time-series forecast using the legacy-compatible wrapper."""
    del current_user
    forecast_input = ForecastInput(
        values=body.get("values", []),
        method=body.get("method", "sma"),
        horizon=body.get("horizon", 3),
        window=body.get("window", 3),
        alpha=body.get("alpha", 0.3),
        beta=body.get("beta", 0.1),
    )
    result = run_forecast(forecast_input)
    return {
        "forecast": result.forecast,
        "ci_lower": result.ci_lower,
        "ci_upper": result.ci_upper,
        "method": result.method,
        "horizon": result.horizon,
        "mape": result.mape,
        "rmse": result.rmse,
    }
