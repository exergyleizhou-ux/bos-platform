"""
BOS Pipeline v9.0 — PID Controller Engine

Implements a discrete PID controller for regulating bioconversion
process parameters (temperature, moisture, feed rate).

Features:
  - Anti-windup (integrator clamping)
  - Derivative filtering (low-pass)
  - Setpoint ramping
  - Output saturation
  - Cascade control support

Tuning rules available:
  - Ziegler-Nichols (step response)
  - Cohen-Coon
  - Manual specification
"""

from dataclasses import dataclass, field

ENGINE_VERSION = "9.0.0"


@dataclass
class PIDParams:
    """PID controller parameters."""

    Kp: float = 1.0  # Proportional gain
    Ki: float = 0.1  # Integral gain
    Kd: float = 0.01  # Derivative gain
    setpoint: float = 28.0  # Target value
    output_min: float = 0.0  # Minimum output
    output_max: float = 100.0  # Maximum output
    integral_min: float = -50.0  # Anti-windup lower bound
    integral_max: float = 50.0  # Anti-windup upper bound
    derivative_filter: float = 0.1  # Low-pass filter coefficient (0=no filter, 1=full filter)
    deadband: float = 0.0  # Error deadband (ignore errors smaller than this)
    setpoint_ramp_rate: float | None = None  # Max setpoint change per step


@dataclass
class PIDState:
    """Internal state of the PID controller."""

    integral: float = 0.0
    previous_error: float = 0.0
    previous_derivative: float = 0.0
    current_setpoint: float = 28.0  # Ramped setpoint
    step_count: int = 0


@dataclass
class PIDStepResult:
    """Result of a single PID control step."""

    output: float = 0.0  # Control output
    error: float = 0.0  # Current error (setpoint - measured)
    p_term: float = 0.0  # Proportional component
    i_term: float = 0.0  # Integral component
    d_term: float = 0.0  # Derivative component
    setpoint: float = 0.0  # Current (possibly ramped) setpoint
    saturated: bool = False  # Whether output is at limits
    state: PIDState | None = None


def pid_step(
    measured: float,
    params: PIDParams,
    state: PIDState,
    dt: float = 1.0,
) -> PIDStepResult:
    """
    Execute one PID control step.

    Parameters
    ----------
    measured : current process value
    params : PID parameters
    state : PID internal state (modified in-place)
    dt : time step (hours or seconds, be consistent)

    Returns
    -------
    PIDStepResult with control output.
    """
    # Setpoint ramping
    if params.setpoint_ramp_rate is not None:
        diff = params.setpoint - state.current_setpoint
        max_change = params.setpoint_ramp_rate * dt
        if abs(diff) > max_change:
            state.current_setpoint += max_change * (1 if diff > 0 else -1)
        else:
            state.current_setpoint = params.setpoint
    else:
        state.current_setpoint = params.setpoint

    # Error calculation
    error = state.current_setpoint - measured

    # Deadband
    if abs(error) < params.deadband:
        error = 0.0

    # Proportional
    p_term = params.Kp * error

    # Integral with anti-windup
    state.integral += error * dt
    state.integral = max(params.integral_min, min(params.integral_max, state.integral))
    i_term = params.Ki * state.integral

    # Derivative with filtering
    raw_derivative = (error - state.previous_error) / dt if dt > 0 else 0.0

    filtered_derivative = (
        params.derivative_filter * state.previous_derivative + (1 - params.derivative_filter) * raw_derivative
    )
    d_term = params.Kd * filtered_derivative

    # Total output
    output = p_term + i_term + d_term

    # Saturation
    saturated = False
    if output > params.output_max:
        output = params.output_max
        saturated = True
        # Anti-windup: don't integrate when saturated
        state.integral -= error * dt
    elif output < params.output_min:
        output = params.output_min
        saturated = True
        state.integral -= error * dt

    # Update state
    state.previous_error = error
    state.previous_derivative = filtered_derivative
    state.step_count += 1

    return PIDStepResult(
        output=round(output, 6),
        error=round(error, 6),
        p_term=round(p_term, 6),
        i_term=round(i_term, 6),
        d_term=round(d_term, 6),
        setpoint=round(state.current_setpoint, 6),
        saturated=saturated,
        state=state,
    )


# ═══════════════════════════════════════════════
# Tuning Methods
# ═══════════════════════════════════════════════


def ziegler_nichols_tuning(
    K_u: float,
    T_u: float,
    controller_type: str = "PID",
) -> PIDParams:
    """
    Ziegler-Nichols tuning from ultimate gain (K_u) and period (T_u).

    Parameters
    ----------
    K_u : Ultimate gain (gain at which system oscillates)
    T_u : Ultimate period (period of oscillation in seconds)
    controller_type : "P", "PI", or "PID"

    Returns
    -------
    PIDParams with tuned gains.
    """
    if controller_type == "P":
        Kp = 0.5 * K_u
        Ki = 0.0
        Kd = 0.0
    elif controller_type == "PI":
        Kp = 0.45 * K_u
        Ki = 1.2 * Kp / T_u
        Kd = 0.0
    else:  # PID
        Kp = 0.6 * K_u
        Ki = 2.0 * Kp / T_u
        Kd = Kp * T_u / 8.0

    return PIDParams(Kp=round(Kp, 6), Ki=round(Ki, 6), Kd=round(Kd, 6))


def cohen_coon_tuning(
    K_process: float,
    tau: float,
    theta: float,
    controller_type: str = "PID",
) -> PIDParams:
    """
    Cohen-Coon tuning from process step response parameters.

    Parameters
    ----------
    K_process : Process gain
    tau : Process time constant
    theta : Process dead time
    controller_type : "P", "PI", or "PID"

    Returns
    -------
    PIDParams with tuned gains.
    """
    r = theta / tau  # Delay ratio

    if controller_type == "P":
        Kp = (1 / K_process) * (tau / theta) * (1 + r / 3)
        Ki, Kd = 0.0, 0.0
    elif controller_type == "PI":
        Kp = (1 / K_process) * (tau / theta) * (0.9 + r / 12)
        Ti = theta * (30 + 3 * r) / (9 + 20 * r)
        Ki = Kp / Ti
        Kd = 0.0
    else:  # PID
        Kp = (1 / K_process) * (tau / theta) * (4 / 3 + r / 4)
        Ti = theta * (32 + 6 * r) / (13 + 8 * r)
        Td = theta * 4 / (11 + 2 * r)
        Ki = Kp / Ti
        Kd = Kp * Td

    return PIDParams(Kp=round(Kp, 6), Ki=round(Ki, 6), Kd=round(Kd, 6))


# ═══════════════════════════════════════════════
# Multi-loop Control Simulation
# ═══════════════════════════════════════════════


@dataclass
class MultiLoopConfig:
    """Configuration for multi-loop PID control."""

    temperature_params: PIDParams = field(
        default_factory=lambda: PIDParams(Kp=2.0, Ki=0.1, Kd=0.05, setpoint=28.0, output_min=0, output_max=100)
    )
    moisture_params: PIDParams = field(
        default_factory=lambda: PIDParams(Kp=1.5, Ki=0.08, Kd=0.02, setpoint=70.0, output_min=0, output_max=100)
    )
    feed_rate_params: PIDParams = field(
        default_factory=lambda: PIDParams(Kp=0.5, Ki=0.05, Kd=0.01, setpoint=0.15, output_min=0, output_max=0.5)
    )


def simulate_multi_loop(
    measurements: list[dict[str, float]],
    config: MultiLoopConfig,
    dt: float = 1.0,
) -> list[dict[str, PIDStepResult]]:
    """
    Simulate multi-loop PID control over a sequence of measurements.

    Parameters
    ----------
    measurements : List of dicts with keys "temperature", "moisture", "feed_rate"
    config : PID parameters for each loop
    dt : time step

    Returns
    -------
    List of dicts mapping loop name to PIDStepResult.
    """
    temp_state = PIDState(current_setpoint=config.temperature_params.setpoint)
    moist_state = PIDState(current_setpoint=config.moisture_params.setpoint)
    feed_state = PIDState(current_setpoint=config.feed_rate_params.setpoint)

    results = []
    for m in measurements:
        step_results = {}

        if "temperature" in m:
            step_results["temperature"] = pid_step(m["temperature"], config.temperature_params, temp_state, dt)
        if "moisture" in m:
            step_results["moisture"] = pid_step(m["moisture"], config.moisture_params, moist_state, dt)
        if "feed_rate" in m:
            step_results["feed_rate"] = pid_step(m["feed_rate"], config.feed_rate_params, feed_state, dt)

        results.append(step_results)

    return results
