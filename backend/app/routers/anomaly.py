"""
BOS Pipeline v9.0 �� Anomaly Detection Router

API endpoints for multivariate anomaly detection on batches.
"""

import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context
from app.models import User, Batch, Calculation
from app.engine.anomaly_engine import AnomalyInput, detect_anomalies

router = APIRouter()


class AnomalyRequest(BaseModel):
    """Anomaly detection request."""

    data: List[Dict[str, float]] = Field(..., min_length=3)
    features: Optional[List[str]] = None
    method: str = Field(default="isolation_forest", pattern=r"^(isolation_forest|zscore|iqr|mahalanobis)$")
    contamination: float = Field(default=0.05, ge=0.01, le=0.50)
    threshold: float = Field(default=3.0, gt=0)
    n_trees: int = Field(default=100, ge=10, le=500)
    seed: Optional[int] = None


@router.post("/detect")
async def detect_anomalies_endpoint(
    body: AnomalyRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Detect anomalous batches using multivariate methods."""
    start_time = time.perf_counter()

    anomaly_input = AnomalyInput(
        data=body.data,
        features=body.features,
        method=body.method,
        contamination=body.contamination,
        threshold=body.threshold,
        n_trees=body.n_trees,
        seed=body.seed,
    )

    anomaly_result = detect_anomalies(anomaly_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if anomaly_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": anomaly_result.errors},
        )

    # Persist
    calc = Calculation(
        batch_id=None,
        calc_type="anomaly_detection",
        status="completed",
        inputs={
            "n_samples": len(body.data),
            "method": body.method,
            "features": body.features,
        },
        result={
            "anomaly_count": anomaly_result.anomaly_count,
            "anomaly_rate": anomaly_result.anomaly_rate,
            "anomaly_indices": anomaly_result.anomaly_indices,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=anomaly_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "method": anomaly_result.method,
        "anomaly_count": anomaly_result.anomaly_count,
        "anomaly_rate": anomaly_result.anomaly_rate,
        "anomaly_indices": anomaly_result.anomaly_indices,
        "scores": anomaly_result.scores,
        "labels": anomaly_result.labels,
        "feature_contributions": anomaly_result.feature_contributions,
        "threshold_used": anomaly_result.threshold_used,
        "computation_time_ms": anomaly_result.computation_time_ms,
    }


@router.post("/detect-batches")
async def detect_anomalous_batches(
    method: str = Query("isolation_forest", pattern=r"^(isolation_forest|zscore|iqr|mahalanobis)$"),
    features: str = Query("dm_in,dm_out,temperature,moisture", description="Comma-separated feature names"),
    contamination: float = Query(0.05, ge=0.01, le=0.50),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Detect anomalous batches from the tenant's batch data.
    Automatically extracts features from stored batches.
    """
    # Fetch batches
    result = await db.execute(
        select(Batch).where(Batch.tenant_id == current_user.tenant_id, Batch.status != "archived")
    )
    batches = result.scalars().all()

    if len(batches) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 5 non-archived batches for anomaly detection",
        )

    feature_list = [f.strip() for f in features.split(",")]

    data = []
    batch_ids = []
    for b in batches:
        row = {}
        for f in feature_list:
            val = getattr(b, f, None)
            if val is not None and isinstance(val, (int, float)):
                row[f] = float(val)
            else:
                row[f] = 0.0
        data.append(row)
        batch_ids.append(b.id)

    anomaly_input = AnomalyInput(
        data=data,
        features=feature_list,
        method=method,
        contamination=contamination,
    )

    anomaly_result = detect_anomalies(anomaly_input)

    anomalous_batches = [
        {"batch_id": batch_ids[i], "score": anomaly_result.scores[i]}
        for i in anomaly_result.anomaly_indices
    ]

    return {
        "total_batches": len(batches),
        "anomaly_count": anomaly_result.anomaly_count,
        "anomaly_rate": anomaly_result.anomaly_rate,
        "anomalous_batches": anomalous_batches,
        "method": method,
        "features_used": feature_list,
    }
