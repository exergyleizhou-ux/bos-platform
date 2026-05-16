"""
BOS Pipeline v9.0 — Digital Twin Engine

Manages the state-space model of a bioconversion process.
The digital twin maintains a virtual replica of the physical batch,
updated via:
  1. Sensor data ingestion (push)
  2. Physics-based prediction (step forward)
  3. State estimation (Extended Kalman Filter correction)

State vector x = [biomass, substrate, temperature, moisture, nitrogen]?
Input vector u = [feed_rate, ventilation, heating]?
Observation vector z = [weight, temperature_sensor, moisture_sensor]?

The dynamics follow simplified Monod kinetics:
  dB/dt = μ_max * S/(K_s + S) * B - k_death * B
  dS/dt = -1/Y * μ_max * S/(K_s + S) * B + feed_rate
  dT/dt = (T_env - T)/τ_T + Q_met/(m*c_p) + Q_heat
  dM/dt = (M_env - M)/τ_M - evap_rate * ventilation
  dN/dt = -k_n * μ_max * S/(K_s + S) * B
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"

# State indices
IDX_BIOMASS = 0
IDX_SUBSTRATE = 1
IDX_TEMPERATURE = 2
IDX_MOISTURE = 3
IDX_NITROGEN = 4
STATE_DIM = 5

# Input indices
IDX_FEED_RATE = 0
IDX_VENTILATION = 1
IDX_HEATING = 2
INPUT_DIM = 3

# Observation indices
IDX_OBS_WEIGHT = 0
IDX_OBS_TEMP = 1
IDX_OBS_MOIST = 2
OBS_DIM = 3


@dataclass
class TwinParameters:
    """Kinetic and physical parameters for the twin."""

    mu_max: float = 0.025  # Max specific growth rate (1/h)
    K_s: float = 5.0  # Half-saturation constant (kg DM)
    Y: float = 0.22  # Yield coefficient (kg biomass / kg substrate)
    k_death: float = 0.001  # Death rate (1/h)
    k_n: float = 0.02  # Nitrogen uptake coefficient
    tau_T: float = 10.0  # Thermal time constant (h)
    tau_M: float = 20.0  # Moisture time constant (h)
    T_env: float = 25.0  # Ambient temperature (°C)
    M_env: float = 60.0  # Ambient moisture (%)
    c_p: float = 3.5  # Specific heat capacity (kJ/(kg·°C))
    Q_met_coeff: float = 0.1  # Metabolic heat per unit growth (kJ/h per kg/h)
    evap_rate: float = 0.5  # Evaporation coefficient (% per unit ventilation per hour)
    Q_heat_coeff: float = 2.0  # Heating power coefficient (°C/h per unit heating)


@dataclass
class TwinState:
    """Current state of the digital twin."""

    biomass: float = 0.5  # kg DM
    substrate: float = 10.0  # kg DM
    temperature: float = 28.0  # °C
    moisture: float = 70.0  # %
    nitrogen: float = 50.0  # g
    covariance: Optional[List[List[float]]] = None  # P matrix (STATE_DIM × STATE_DIM)
    timestamp_hours: float = 0.0

    @property
    def time(self) -> float:
        """Legacy alias expected by older tests."""
        return self.timestamp_hours

    def to_vector(self) -> NDArray:
        return np.array([self.biomass, self.substrate, self.temperature, self.moisture, self.nitrogen])

    @staticmethod
    def from_vector(x: NDArray, cov: Optional[NDArray] = None, t: float = 0.0) -> "TwinState":
        return TwinState(
            biomass=float(x[IDX_BIOMASS]),
            substrate=float(x[IDX_SUBSTRATE]),
            temperature=float(x[IDX_TEMPERATURE]),
            moisture=float(x[IDX_MOISTURE]),
            nitrogen=float(x[IDX_NITROGEN]),
            covariance=cov.tolist() if cov is not None else None,
            timestamp_hours=t,
        )


@dataclass
class TwinStepResult:
    """Result of a single twin step (predict or update)."""

    state: TwinState
    predicted: bool = False
    updated: bool = False
    innovation: Optional[List[float]] = None  # z - H*x (for update step)
    growth_rate: float = 0.0  # Current growth rate (kg/h)
    ser_instantaneous: float = 0.0  # Instantaneous SER


# ═══════════════════════════════════════════════
# Dynamics
# ═══════════════════════════════════════════════


def _dynamics(x: NDArray, u: NDArray, params: TwinParameters, dt: float) -> NDArray:
    """
    Compute state derivative and advance by dt (Euler integration).

    Parameters
    ----------
    x : state vector [biomass, substrate, temp, moisture, nitrogen]
    u : input vector [feed_rate, ventilation, heating]
    params : kinetic parameters
    dt : time step in hours

    Returns
    -------
    x_next : updated state vector
    """
    B, S, T, M, N = x
    feed_rate, ventilation, heating = u

    # Monod growth
    mu = params.mu_max * max(S, 0) / (params.K_s + max(S, 1e-10))

    # Temperature effect (simplified Arrhenius-like)
    temp_factor = np.exp(-0.1 * (T - 28.0) ** 2 / 50.0)  # Optimal at 28°C
    mu_eff = mu * temp_factor

    growth = mu_eff * max(B, 0)
    death = params.k_death * max(B, 0)

    # State derivatives
    dB = growth - death
    dS = -growth / max(params.Y, 0.01) + feed_rate
    dT = (params.T_env - T) / params.tau_T + params.Q_met_coeff * growth + params.Q_heat_coeff * heating
    dM = (params.M_env - M) / params.tau_M - params.evap_rate * ventilation
    dN = -params.k_n * growth

    # Euler step
    x_next = x + np.array([dB, dS, dT, dM, dN]) * dt

    # Physical constraints
    x_next[IDX_BIOMASS] = max(x_next[IDX_BIOMASS], 0)
    x_next[IDX_SUBSTRATE] = max(x_next[IDX_SUBSTRATE], 0)
    x_next[IDX_TEMPERATURE] = np.clip(x_next[IDX_TEMPERATURE], 0, 60)
    x_next[IDX_MOISTURE] = np.clip(x_next[IDX_MOISTURE], 0, 100)
    x_next[IDX_NITROGEN] = max(x_next[IDX_NITROGEN], 0)

    return x_next


def _jacobian(x: NDArray, u: NDArray, params: TwinParameters, dt: float) -> NDArray:
    """Compute state transition Jacobian F = ?f/?x (for EKF)."""
    B, S, T, M, N = x
    F = np.eye(STATE_DIM)

    mu = params.mu_max * max(S, 0) / (params.K_s + max(S, 1e-10))
    temp_factor = np.exp(-0.1 * (T - 28.0) ** 2 / 50.0)
    mu_eff = mu * temp_factor

    dmu_dS = params.mu_max * params.K_s / (params.K_s + max(S, 1e-10)) ** 2 * temp_factor
    dmu_dT = mu * temp_factor * (-0.1 * 2 * (T - 28.0) / 50.0)

    # dB/dB, dB/dS, dB/dT
    F[0, 0] += (mu_eff - params.k_death) * dt
    F[0, 1] += dmu_dS * max(B, 0) * dt
    F[0, 2] += dmu_dT * max(B, 0) * dt

    # dS/dB, dS/dS
    F[1, 0] += -mu_eff / max(params.Y, 0.01) * dt
    F[1, 1] += -dmu_dS * max(B, 0) / max(params.Y, 0.01) * dt

    # dT/dT
    F[2, 2] += -dt / params.tau_T

    # dM/dM
    F[3, 3] += -dt / params.tau_M

    # dN/dB, dN/dS
    F[4, 0] += -params.k_n * mu_eff * dt
    F[4, 1] += -params.k_n * dmu_dS * max(B, 0) * dt

    return F


# ═══════════════════════════════════════════════
# Predict & Update Steps
# ═══════════════════════════════════════════════


def predict_step(
    state: TwinState,
    inputs: Dict[str, float],
    params: TwinParameters,
    dt: float = 1.0,
) -> TwinStepResult:
    """
    Advance the digital twin forward by dt hours (prediction step).

    Parameters
    ----------
    state : current twin state
    inputs : {"feed_rate": ..., "ventilation": ..., "heating": ...}
    params : model parameters
    dt : time step in hours
    """
    x = state.to_vector()
    u = np.array(
        [
            inputs.get("feed_rate", 0.0),
            inputs.get("ventilation", 0.0),
            inputs.get("heating", 0.0),
        ]
    )

    # Process noise
    Q = np.diag([1e-4, 1e-3, 0.01, 0.1, 0.01])

    # Predict state
    x_next = _dynamics(x, u, params, dt)

    # Predict covariance
    F = _jacobian(x, u, params, dt)
    if state.covariance is not None:
        P = np.array(state.covariance)
    else:
        P = np.eye(STATE_DIM) * 0.1
    P_next = F @ P @ F.T + Q

    # Growth rate
    S = max(x[IDX_SUBSTRATE], 0)
    mu = params.mu_max * S / (params.K_s + S)
    growth_rate = mu * max(x[IDX_BIOMASS], 0)

    # Instantaneous SER
    ser_inst = x_next[IDX_BIOMASS] / max(state.substrate - x_next[IDX_SUBSTRATE] + 1e-10, 1e-10)

    new_state = TwinState.from_vector(x_next, P_next, state.timestamp_hours + dt)

    return TwinStepResult(
        state=new_state,
        predicted=True,
        growth_rate=round(float(growth_rate), 6),
        ser_instantaneous=round(float(ser_inst), 6),
    )


def update_step(
    state: TwinState,
    observations: Dict[str, float],
    params: TwinParameters,
) -> TwinStepResult:
    """
    Correct the digital twin state with sensor observations (EKF update).

    Parameters
    ----------
    state : current (predicted) twin state
    observations : {"weight": ..., "temperature": ..., "moisture": ...}
    params : model parameters
    """
    x = state.to_vector()

    if state.covariance is not None:
        P = np.array(state.covariance)
    else:
        P = np.eye(STATE_DIM) * 0.1

    # Observation model: z = H * x + noise
    # weight ≈ biomass + substrate
    # temperature = temperature
    # moisture = moisture
    H = np.zeros((OBS_DIM, STATE_DIM))
    H[IDX_OBS_WEIGHT, IDX_BIOMASS] = 1.0
    H[IDX_OBS_WEIGHT, IDX_SUBSTRATE] = 1.0
    H[IDX_OBS_TEMP, IDX_TEMPERATURE] = 1.0
    H[IDX_OBS_MOIST, IDX_MOISTURE] = 1.0

    # Observation noise
    R = np.diag([0.5, 0.5, 2.0])  # weight ±0.5kg, temp ±0.5°C, moisture ±2%

    # Build observation vector
    z = np.array(
        [
            observations.get("weight", x[IDX_BIOMASS] + x[IDX_SUBSTRATE]),
            observations.get("temperature", x[IDX_TEMPERATURE]),
            observations.get("moisture", x[IDX_MOISTURE]),
        ]
    )

    # Innovation
    y_innov = z - H @ x

    # Innovation covariance
    S_cov = H @ P @ H.T + R

    # Kalman gain
    try:
        K = P @ H.T @ np.linalg.inv(S_cov)
    except np.linalg.LinAlgError:
        K = P @ H.T @ np.linalg.pinv(S_cov)

    # Update state
    x_updated = x + K @ y_innov

    # Update covariance
    I = np.eye(STATE_DIM)
    P_updated = (I - K @ H) @ P

    # Physical constraints
    x_updated[IDX_BIOMASS] = max(x_updated[IDX_BIOMASS], 0)
    x_updated[IDX_SUBSTRATE] = max(x_updated[IDX_SUBSTRATE], 0)
    x_updated[IDX_TEMPERATURE] = np.clip(x_updated[IDX_TEMPERATURE], 0, 60)
    x_updated[IDX_MOISTURE] = np.clip(x_updated[IDX_MOISTURE], 0, 100)
    x_updated[IDX_NITROGEN] = max(x_updated[IDX_NITROGEN], 0)

    new_state = TwinState.from_vector(x_updated, P_updated, state.timestamp_hours)

    return TwinStepResult(
        state=new_state,
        updated=True,
        innovation=[round(float(v), 6) for v in y_innov],
    )


# ═══════════════════════════════════════════════
# Trajectory Simulation
# ═══════════════════════════════════════════════


def simulate_trajectory(
    initial_state: TwinState,
    inputs_schedule: List[Dict[str, float]],
    params: TwinParameters,
    dt: float = 1.0,
    total_hours: Optional[int] = None,
) -> List[TwinStepResult]:
    """
    Simulate a full trajectory over multiple time steps.

    Parameters
    ----------
    initial_state : starting state
    inputs_schedule : list of input dicts (one per step, or single repeated)
    params : model parameters
    dt : time step (hours)
    total_hours : override number of steps

    Returns
    -------
    List of TwinStepResult for each time step.
    """
    n_steps = total_hours or len(inputs_schedule)

    trajectory: List[TwinStepResult] = []
    current_state = initial_state

    for i in range(n_steps):
        inputs = inputs_schedule[min(i, len(inputs_schedule) - 1)]
        step_result = predict_step(current_state, inputs, params, dt)
        trajectory.append(step_result)
        current_state = step_result.state

    return trajectory


# Backward-compatible API expected by legacy tests.
TwinConfig = TwinParameters


def step_twin(state: TwinState, config: TwinConfig, dt: float = 1.0) -> TwinState:
    """Advance the twin by one step using zero control inputs."""
    result = predict_step(
        state,
        {"feed_rate": 0.0, "ventilation": 0.0, "heating": 0.0},
        config,
        dt,
    )
    return result.state


def run_twin_simulation(
    initial_state: TwinState,
    config: TwinConfig,
    n_steps: int = 100,
    dt: float = 1.0,
) -> List[TwinState]:
    """Run a simplified legacy trajectory simulation returning states only."""
    schedule = [{"feed_rate": 0.0, "ventilation": 0.0, "heating": 0.0}] * max(n_steps, 1)
    states = [initial_state]
    for step in simulate_trajectory(initial_state, schedule, config, dt=dt, total_hours=n_steps):
        states.append(step.state)
    return states
