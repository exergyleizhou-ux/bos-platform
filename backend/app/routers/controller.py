"""
BOS Pipeline v9.0 — PID Controller Router

API endpoints for PID control simulation and tuning.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import require_minimum_role
from app.models import User
from app.engine.controller_engine import (
    PIDParams,
    PIDState,
    pid_step,
    ziegler_nichols_tuning,
    cohen_coon_tuning,
    MultiLoopConfig,
    simulate_multi_loop,
)

router = APIRouter()


class PIDTuneRequest(BaseModel):
    """PID tuning request."""

    method: str = Field(default="ziegler_nichols", pattern=r"^(ziegler_nichols|cohen_coon|manual)$")
    controller_type: str = Field(default="PID", pattern=r"^(P|PI|PID)$")

    # Ziegler-Nichols
    K_u: Optional[float] = Field(None, gt=0, description="Ultimate gain")
    T_u: Optional[float] = Field(None, gt=0, description="Ultimate period (s)")

    # Cohen-Coon
    K_process: Optional[float] = Field(None, gt=0, description="Process gain")
    tau: Optional[float] = Field(None, gt=0, description="Process time constant")
    theta: Optional[float] = Field(None, gt=0, description="Process dead time")

    # Manual
    Kp: Optional[float] = None
    Ki: Optional[float] = None
    Kd: Optional[float] = None


@router.post("/tune")
async def tune_pid(
    body: PIDTuneRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
):
    """Calculate PID parameters using tuning rules."""
    if body.method == "ziegler_nichols":
        if not body.K_u or not body.T_u:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ziegler-Nichols requires K_u and T_u",
            )
        params = ziegler_nichols_tuning(body.K_u, body.T_u, body.controller_type)

    elif body.method == "cohen_coon":
        if not body.K_process or not body.tau or not body.theta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cohen-Coon requires K_process, tau, and theta",
            )
        params = cohen_coon_tuning(body.K_process, body.tau, body.theta, body.controller_type)

    elif body.method == "manual":
        params = PIDParams(
            Kp=body.Kp or 1.0,
            Ki=body.Ki or 0.0,
            Kd=body.Kd or 0.0,
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown method")

    return {
        "method": body.method,
        "controller_type": body.controller_type,
        "parameters": {
            "Kp": params.Kp,
            "Ki": params.Ki,
            "Kd": params.Kd,
        },
    }


class PIDSimulateRequest(BaseModel):
    """PID simulation request."""

    measurements: List[Dict[str, float]] = Field(..., min_length=1, max_length=10000)
    temperature_setpoint: float = Field(default=28.0)
    moisture_setpoint: float = Field(default=70.0)
    dt: float = Field(default=1.0, gt=0)
    Kp_temp: float = Field(default=2.0)
    Ki_temp: float = Field(default=0.1)
    Kd_temp: float = Field(default=0.05)
    Kp_moist: float = Field(default=1.5)
    Ki_moist: float = Field(default=0.08)
    Kd_moist: float = Field(default=0.02)


@router.post("/simulate")
async def simulate_pid(
    body: PIDSimulateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
):
    """Simulate multi-loop PID control over a measurement sequence."""
    config = MultiLoopConfig(
        temperature_params=PIDParams(
            Kp=body.Kp_temp, Ki=body.Ki_temp, Kd=body.Kd_temp,
            setpoint=body.temperature_setpoint, output_min=0, output_max=100,
        ),
        moisture_params=PIDParams(
            Kp=body.Kp_moist, Ki=body.Ki_moist, Kd=body.Kd_moist,
            setpoint=body.moisture_setpoint, output_min=0, output_max=100,
        ),
    )

    results = simulate_multi_loop(body.measurements, config, body.dt)

    response_data = []
    for i, step_results in enumerate(results):
        step = {"step": i}
        for loop_name, pid_result in step_results.items():
            step[f"{loop_name}_output"] = pid_result.output
            step[f"{loop_name}_error"] = pid_result.error
            step[f"{loop_name}_p"] = pid_result.p_term
            step[f"{loop_name}_i"] = pid_result.i_term
            step[f"{loop_name}_d"] = pid_result.d_term
            step[f"{loop_name}_saturated"] = pid_result.saturated
        response_data.append(step)

    return {
        "n_steps": len(results),
        "setpoints": {
            "temperature": body.temperature_setpoint,
            "moisture": body.moisture_setpoint,
        },
        "results": response_data,
    }
