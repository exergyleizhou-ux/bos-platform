"""
BOS Pipeline v9.0 �� GP Calibration Router

API endpoints for Gaussian Process model calibration.
"""

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User, Calculation
from app.engine.calibration_engine import GPInput, fit_gp

router = APIRouter()


class GPCalibrationRequest(BaseModel):
    """GP calibration request."""

    X_train: List[List[float]] = Field(..., min_length=2, description="Training features (n �� d)")
    y_train: List[float] = Field(..., min_length=2, description="Training targets")
    X_predict: Optional[List[List[float]]] = None
    kernel: str = Field(default="matern52", pattern=r"^(rbf|matern52)$")
    noise_variance: float = Field(default=0.01, ge=0)
    optimize_hyperparams: bool = True
    n_restarts: int = Field(default=5, ge=1, le=20)


@router.post("/fit")
async def fit_gp_endpoint(
    body: GPCalibrationRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Fit a Gaussian Process model to data.

    Returns predictions with uncertainty (posterior mean �� std).
    """
    start_time = time.perf_counter()

    gp_input = GPInput(
        X_train=body.X_train,
        y_train=body.y_train,
        X_predict=body.X_predict,
        kernel=body.kernel,
        noise_variance=body.noise_variance,
        optimize_hyperparams=body.optimize_hyperparams,
        n_restarts=body.n_restarts,
    )

    gp_result = fit_gp(gp_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if gp_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": gp_result.errors},
        )

    # Persist
    calc = Calculation(
        batch_id=None,
        calc_type="gp_calibration",
        status="completed",
        inputs={
            "n_train": len(body.X_train),
            "n_features": len(body.X_train[0]) if body.X_train else 0,
            "kernel": body.kernel,
        },
        result={
            "length_scale": gp_result.length_scale,
            "signal_variance": gp_result.signal_variance,
            "noise_variance": gp_result.noise_variance,
            "r_squared": gp_result.r_squared,
            "rmse": gp_result.rmse,
            "log_marginal_likelihood": gp_result.log_marginal_likelihood,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=gp_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "predictions": {
            "mean": gp_result.y_pred_mean,
            "std": gp_result.y_pred_std,
            "ci_lower": gp_result.y_pred_ci_lower,
            "ci_upper": gp_result.y_pred_ci_upper,
        },
        "hyperparameters": {
            "length_scale": gp_result.length_scale,
            "signal_variance": gp_result.signal_variance,
            "noise_variance": gp_result.noise_variance,
            "log_marginal_likelihood": gp_result.log_marginal_likelihood,
        },
        "model_quality": {
            "r_squared": gp_result.r_squared,
            "rmse": gp_result.rmse,
            "mae": gp_result.mae,
        },
        "computation_time_ms": round(duration_ms, 2),
    }
