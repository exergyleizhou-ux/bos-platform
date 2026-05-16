"""
BOS Pipeline v9.0 sensitivity analysis router.
"""

import time
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.engine.sensitivity_engine import SensitivityInput, run_sensitivity_analysis
from app.models import Calculation, User

router = APIRouter()


class SensitivityRequest(BaseModel):
    """Sensitivity analysis request."""

    method: str = Field(default="sobol", pattern=r"^(sobol|morris|oat)$")
    n_samples: int = Field(default=1024, ge=64, le=100000)
    parameters: Dict[str, List[float]] = Field(
        default_factory=lambda: {
            "dm_in": [5.0, 20.0],
            "dm_out": [1.0, 6.0],
            "n_in": [20.0, 80.0],
            "n_larvae": [10.0, 50.0],
            "n_frass": [5.0, 30.0],
        },
        description="Parameter name -> [min, max] bounds",
    )
    seed: Optional[int] = None


@router.post("/analyze")
async def analyze_sensitivity(
    body: SensitivityRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Run global sensitivity analysis on SER.

    Identifies which input parameters have the greatest influence on output.
    """
    start_time = time.perf_counter()

    param_bounds: Dict[str, Tuple[float, float]] = {}
    for name, bounds in body.parameters.items():
        if len(bounds) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parameter '{name}' must have [min, max] bounds",
            )
        param_bounds[name] = (bounds[0], bounds[1])

    sa_input = SensitivityInput(
        method=body.method,
        n_samples=body.n_samples,
        parameters=param_bounds,
        seed=body.seed,
    )

    sa_result = run_sensitivity_analysis(sa_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if sa_result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": sa_result.errors},
        )

    calc = Calculation(
        batch_id=None,
        calc_type="sensitivity",
        status="completed",
        inputs=body.model_dump(),
        result={
            "method": sa_result.method,
            "first_order": sa_result.first_order,
            "total_order": sa_result.total_order,
            "mu_star": sa_result.mu_star,
            "sigma": sa_result.sigma,
            "parameter_ranking": sa_result.parameter_ranking,
            "n_model_evaluations": sa_result.n_model_evaluations,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=sa_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    response: Dict = {
        "method": sa_result.method,
        "parameter_ranking": sa_result.parameter_ranking,
        "n_samples": sa_result.n_samples,
        "n_model_evaluations": sa_result.n_model_evaluations,
        "computation_time_ms": sa_result.computation_time_ms,
    }

    if sa_result.first_order:
        response["first_order_indices"] = sa_result.first_order
    if sa_result.total_order:
        response["total_order_indices"] = sa_result.total_order
    if sa_result.mu_star:
        response["morris_mu_star"] = sa_result.mu_star
        response["morris_sigma"] = sa_result.sigma

    return response
