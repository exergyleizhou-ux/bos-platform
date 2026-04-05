"""
BOS Pipeline v9.0 �� Forecast Router

API endpoints for time series forecasting of batch metrics.
"""

import time
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context
from app.models import User, Batch, Calculation
from app.engine.arima_engine import ForecastInput, forecast_timeseries

router = APIRouter()


class ForecastRequest(BaseModel):
    """Forecast request."""

    values: List[float] = Field(..., min_length=3, max_length=10000)
    horizon: int = Field(default=10, ge=1, le=365)
    method: str = Field(default="ewma", pattern=r"^(sma|ewma|ar)$")
    sma_window: int = Field(default=5, ge=2, le=100)
    ewma_alpha: float = Field(default=0.3, ge=0.01, le=0.99)
    ar_order: int = Field(default=3, ge=1, le=20)
    confidence_level: float = Field(default=0.95, ge=0.80, le=0.99)
    seasonal_period: Optional[int] = Field(None, ge=2, le=365)


@router.post("/predict")
async def forecast_endpoint(
    body: ForecastRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Forecast a time series."""
    start_time = time.perf_counter()

    fc_input = ForecastInput(
        values=body.values,
        horizon=body.horizon,
        method=body.method,
        sma_window=body.sma_window,
        ewma_alpha=body.ewma_alpha,
        ar_order=body.ar_order,
        confidence_level=body.confidence_level,
        seasonal_period=body.seasonal_period,
    )

    fc_result = forecast_timeseries(fc_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if fc_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": fc_result.errors},
        )

    # Persist
    calc = Calculation(
        batch_id=None,
        calc_type="forecast",
        status="completed",
        inputs={
            "method": body.method,
            "horizon": body.horizon,
            "n_values": len(body.values),
        },
        result={
            "mae": fc_result.mae,
            "rmse": fc_result.rmse,
            "mape": fc_result.mape,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=fc_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    response = {
        "forecast": fc_result.forecast,
        "ci_lower": fc_result.ci_lower,
        "ci_upper": fc_result.ci_upper,
        "fitted": fc_result.fitted,
        "model_quality": {
            "mae": fc_result.mae,
            "rmse": fc_result.rmse,
            "mape": fc_result.mape,
        },
        "method": fc_result.method,
        "computation_time_ms": fc_result.computation_time_ms,
    }

    if fc_result.trend is not None:
        response["decomposition"] = {
            "trend": fc_result.trend,
            "seasonal": fc_result.seasonal,
            "residual": fc_result.residual_component,
        }

    return response


@router.post("/ser-forecast")
async def forecast_ser_from_batches(
    horizon: int = Query(10, ge=1, le=90),
    method: str = Query("ewma", pattern=r"^(sma|ewma|ar)$"),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Forecast SER trend from tenant's historical batch data."""
    result = await db.execute(
        select(Batch.score)
        .where(
            Batch.tenant_id == current_user.tenant_id,
            Batch.score.isnot(None),
            Batch.batch_date.isnot(None),
        )
        .order_by(Batch.batch_date.asc())
    )
    scores = [float(row[0]) for row in result.all()]

    if len(scores) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Need at least 5 historical SER values, found {len(scores)}",
        )

    fc_input = ForecastInput(
        values=scores,
        horizon=horizon,
        method=method,
    )

    fc_result = forecast_timeseries(fc_input)

    return {
        "historical_count": len(scores),
        "forecast": fc_result.forecast,
        "ci_lower": fc_result.ci_lower,
        "ci_upper": fc_result.ci_upper,
        "model_quality": {
            "mae": fc_result.mae,
            "rmse": fc_result.rmse,
        },
    }
