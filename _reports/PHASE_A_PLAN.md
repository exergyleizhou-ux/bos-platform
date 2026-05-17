# BOS Platform Phase A — Plan

> Status: **Draft for user review.** No implementation has started.
> Awaiting decisions on D1–D5 (Section 4) before any code change.
> Generated 2026-05-16. Builds on Phase 0 architecture gap report
> and the 22-commit Phase 0.5 reorganization.

---

## 1. Phase A objective (200 words max)

**In scope**:
- Stabilize **five core compute APIs** under `/api/v1/{group}/{action}` as
  the contract surface for BOS Core: `ser/compute`, `sfi/check`,
  `relay/simulate`, `mc/propagate`, `twin/run`. Pydantic schemas frozen,
  OpenAPI documented.
- Stand up `backend/agent/` as an **independent LangGraph process** on
  port 8001. The agent owns its own FastAPI app, never imports
  `backend.app.*`, and only consumes BOS Core via HTTP.
- Wire 5 LangGraph nodes (`router / ser / sfi / relay / cyber_lab`) plus
  one `render` node into a `StateGraph`, each node calling Core via
  `httpx`-backed `@tool` functions.
- Minimal V2 frontend (`/bos/v2`) able to stream Agent responses end to
  end. V1 surface untouched.

**Out of scope** (deferred to Phase B–G):
- Phase B (Causal): DoWhy / EconML / mediation / DML
- Phase C (Bayesian + Conformal): PyMC ≥ 5 / mapie
- Phase D (NN / Transformer): real Chronos / SER Surrogate
- Phase E (Optimal control): CVXPY / BoTorch / MPC / HJB
- Phase F (Information theory): channel capacity / Shannon / Landauer
- Phase G (Embodied / PhyAgentOS A2A wiring)

**Done = passes Section 7 acceptance criteria.**

---

## 2. Five core APIs — detailed spec

> All paths live under the existing `/api/v1` mount in `backend/app/main.py`.
> Schema files land in `backend/app/schemas/` alongside the Phase 0.5
> baseline schemas. Engines referenced are the Phase 0.5 core layout
> (`backend/app/engine/core/*`).

### 2.1 `POST /api/v1/ser/compute`

- **Paper map**: System Efficiency Ratio, Eq. 1–3 (SER definition);
  Eq. 7 (Monte Carlo uncertainty propagation).
- **Engines**: `engine/core/ser_engine.py` (deterministic SER) +
  `engine/core/monte_carlo_engine.py` (MC propagation).
- **Existing endpoint relation**: `/api/v1/ser/compute` already exists
  (`backend/app/routers/ser.py:26`). Phase A **freezes** the schema;
  no breaking URL change.

**Request schema (`SerComputeRequest`)** — strict per **D2 = (a)**:
```python
class SerComputeRequest(BaseModel):
    # Mass balance inputs (kg of dry matter). Eq.1 requires positive masses.
    dm_in: float = Field(
        ..., gt=0, le=1e6,
        description="Input dry matter [kg]. Eq.1 numerator denominator.",
        examples=[120.0],
    )
    dm_out: float = Field(
        ..., gt=0, le=1e6,
        description="Recovered dry matter [kg]. Must be ≤ dm_in (validator).",
        examples=[36.0],
    )
    # Nitrogen recovery. Eq.2 ratio bounded by mass-conservation.
    n_in: float = Field(
        ..., ge=0, le=1e5,
        description="Input N [kg].",
        examples=[2.8],
    )
    n_rec: float = Field(
        ..., ge=0, le=1e5,
        description="Recovered N [kg]. Must be ≤ n_in (validator).",
        examples=[0.91],
    )
    # Deconstruction / growth coefficients. Eq.3 normalized to [0, 1].
    d_prime: float = Field(
        ..., ge=0.0, le=1.0,
        description="Normalized deconstruction rate D' ∈ [0,1] (paper Eq.3).",
        examples=[0.72],
    )
    g_prime: float = Field(
        ..., ge=0.0, le=1.0,
        description="Normalized growth rate G' ∈ [0,1] (paper Eq.3).",
        examples=[0.65],
    )
    # Species + feedstock for sanity bounds (must exist in core data tables).
    species_code: str = Field(
        ..., min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$",
        description="Code from engine/core/species_db.",
        examples=["BSF_LARVA"],
    )
    feedstock_code: Optional[str] = Field(
        default=None, max_length=64, pattern=r"^[A-Z0-9_\-]+$",
        description="Optional feedstock code from engine/core/feedstock_db.",
        examples=["FOOD_WASTE_MIXED"],
    )
    # Optional MC config (omit → deterministic only). Eq.7 MC propagation.
    monte_carlo: Optional[MonteCarloConfig] = Field(
        default=None,
        description="Omit for deterministic-only result.",
    )

    @model_validator(mode="after")
    def _check_mass_conservation(self) -> "SerComputeRequest":
        if self.dm_out > self.dm_in:
            raise ValueError("dm_out cannot exceed dm_in (mass conservation).")
        if self.n_rec > self.n_in:
            raise ValueError("n_rec cannot exceed n_in (N conservation).")
        return self


class MonteCarloConfig(BaseModel):
    n_samples: int = Field(
        ge=100, le=100_000, default=10_000,
        description="Number of MC samples. Eq.7 estimator variance scales 1/√N.",
    )
    seed: Optional[int] = Field(
        default=None, ge=0, le=2**32 - 1,
        description="PRNG seed for reproducibility.",
    )
    distributions: dict[str, DistSpec] = Field(
        ...,
        description="Per-field uncertainty spec, keys must match request fields.",
    )
```

**Response schema (`SerComputeResponse`)** — strict:
```python
class SerComputeResponse(BaseModel):
    ser_point: float = Field(
        ..., ge=0.0, le=1.0,
        description="Deterministic SER ∈ [0,1] (Eq.1).",
    )
    ser_ci_lower: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="MC lower 95% CI bound; None if MC not run.",
    )
    ser_ci_upper: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="MC upper 95% CI bound; None if MC not run.",
    )
    ser_std: Optional[float] = Field(default=None, ge=0.0)
    delta_ser: Optional[float] = Field(
        default=None, ge=-1.0, le=1.0,
        description="SER delta vs baseline; positive = improvement.",
    )
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    monte_carlo: Optional[McSummary] = None
    evidence_level: Literal["validated", "supported", "planned"]
```

### 2.2 `POST /api/v1/sfi/check`

- **Paper map**: Signal/Flight Integrity, Eq. 5–6 (operating envelope
  + risk conditions).
- **Engines**: `engine/core/flight_envelope.py` (existing zone classifier)
  + **new** `engine/core/sfi_engine.py` (composite SFI score).
- **Existing endpoint relation**: `/api/v1/flight-envelope/check` already
  exists (`routers/flight.py:37`). Phase A **adds** `/api/v1/sfi/check`
  as the V5 contract path; flight-envelope keeps working in parallel.
  See decision **D1**.

**Request schema (`SfiCheckRequest`)** — strict:
```python
class SfiCheckRequest(BaseModel):
    species_code: str = Field(
        ..., min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$",
        examples=["BSF_LARVA"],
    )
    measurements: SfiMeasurements = Field(
        ...,
        description="Current sensor snapshot (temperature, moisture, density,"
                    " pH, ammonia, dissolved_O2, ...).",
    )
    setpoint_profile: Optional[SetpointProfile] = Field(default=None)
    horizon_hours: int = Field(
        default=24, ge=1, le=168,
        description="Forward-projection horizon for envelope breach check.",
    )
    # k_decay is paper-estimated-from-literature, so the API surface accepts
    # an uncertainty band rather than a point. Eq.6 maps decay → risk.
    k_decay_band: Optional[KDecayBand] = Field(
        default=None,
        description="Uncertainty band for k_decay (literature prior).",
    )


class SfiMeasurements(BaseModel):
    temperature_c: float = Field(..., ge=-10.0, le=80.0, description="°C")
    moisture_pct: float = Field(..., ge=0.0, le=100.0)
    density_kg_m3: float = Field(..., gt=0.0, le=2000.0)
    ph: float = Field(..., ge=0.0, le=14.0)
    ammonia_ppm: float = Field(..., ge=0.0, le=10_000.0)
    oxygen_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class KDecayBand(BaseModel):
    """Literature-derived k_decay (not directly measured). Eq.6 input.

    Provide either a point + 1σ, or explicit lo/hi quantiles. The SFI
    engine treats this as a prior and propagates it through Eq.6.
    """
    mode: Literal["point_sigma", "quantile"]
    point: Optional[float] = Field(default=None, gt=0.0)
    sigma: Optional[float] = Field(default=None, ge=0.0)
    lo: Optional[float] = Field(default=None, gt=0.0)
    hi: Optional[float] = Field(default=None, gt=0.0)
```

**Response (`SfiCheckResponse`)** — strict:
```python
class SfiCheckResponse(BaseModel):
    sfi_pass: bool
    zone: Literal["safe", "caution", "danger", "out_of_envelope"]
    composite_score: float = Field(..., ge=0.0, le=1.0)
    per_axis: dict[str, AxisStatus] = Field(
        ...,
        description="Per-measurement axis verdict; keys are the field names in"
                    " SfiMeasurements.",
    )
    forecast_breach: Optional[ForecastBreach] = Field(
        default=None,
        description="Earliest predicted envelope breach within horizon, if any.",
    )
    recommended_actions: list[Action] = Field(
        ..., max_length=20,
        description="Ordered remediation hints; empty when sfi_pass=True.",
    )
    evidence_level: Literal["validated", "supported", "planned"]
```

### 2.3 `POST /api/v1/relay/simulate`

- **Paper map**: Three-stage relay simulation M1 (deconstruction) →
  M2 (assimilation) → M3 (stabilization).
- **Engines**: `engine/core/digital_twin_engine.py` (state-space step) +
  `engine/core/kinetics_engine.py` (Monod / Logistic kinetics with Hill
  saturation) + `engine/core/mass_balance.py` (boundary balancing
  between stages).
- **Existing endpoint relation**: closest is
  `/api/v1/bos/closed-loop/simulate` (`routers/bos.py:573`). Phase A
  adds `/api/v1/relay/simulate` as the new clean contract; behavior may
  refactor to wrap the existing closed-loop simulation. See **D1**.

**Request (`RelaySimulateRequest`)** — strict:
```python
class RelaySimulateRequest(BaseModel):
    initial_state: TwinState = Field(
        ...,
        description="Initial biomass / substrate / T / M / N state.",
    )
    relay_config: RelayConfig = Field(
        ...,
        description="Stage timing + decay parameters (Eq.4–6).",
    )
    horizon_steps: int = Field(
        ..., ge=1, le=10_000,
        description="Number of dt-sized steps to simulate.",
    )
    dt_hours: float = Field(
        ..., gt=0.0, le=24.0,
        description="Integration step size [hours]. Stable for ≤ 1/k_decay.",
    )
    monte_carlo: Optional[MonteCarloConfig] = Field(default=None)
    control_profile: Optional[ControlProfile] = Field(default=None)


class RelayConfig(BaseModel):
    tau_m2: float = Field(
        ..., gt=0.0, le=10_000.0,
        description="M2-stage assimilation time constant [hours] (Eq.4).",
    )
    k_decay: float = Field(
        ..., gt=0.0, le=10.0,
        description="First-order decay rate [1/h] (Eq.5–6).",
    )
    s0: float = Field(
        ..., gt=0.0, le=1e6,
        description="Initial substrate pool [kg] (Eq.4 IC).",
    )
    s_min: float = Field(
        ..., ge=0.0,
        description="Minimum substrate threshold before relay-to-M3.",
    )
    tau_max: float = Field(
        ..., gt=0.0, le=1e5,
        description="Hard cap on total relay duration [hours] (safety).",
    )

    @model_validator(mode="after")
    def _check_thresholds(self) -> "RelayConfig":
        if self.s_min >= self.s0:
            raise ValueError("s_min must be strictly less than s0.")
        return self
```

**Response (`RelaySimulateResponse`)** — strict:
```python
class RelaySimulateResponse(BaseModel):
    trajectory: list[TwinSnapshot] = Field(
        ..., min_length=1, max_length=10_000,
    )
    boundary_ledger: BoundaryLedger = Field(
        ...,
        description="Mass/N balance per stage; sums must match within ε.",
    )
    relay_health: RelayHealth
    final_ser: float = Field(..., ge=0.0, le=1.0)
    final_ser_ci: Optional[tuple[float, float]] = Field(
        default=None,
        description="MC 95% CI on final SER if monte_carlo was requested.",
    )
    warnings: list[Warning] = Field(default_factory=list, max_length=50)
    evidence_level: Literal["validated", "supported", "planned"]
```

### 2.4 `POST /api/v1/mc/propagate`

- **Paper map**: Generic Monte Carlo uncertainty propagation, Eq. 7
  (re-used as a standalone tool).
- **Engines**: `engine/core/monte_carlo_engine.py`.
- **Existing endpoint relation**: `/api/v1/simulation/run` and
  `/api/v1/simulation/monte-carlo` already exist
  (`routers/simulation.py`). Phase A adds the V5-named `/api/v1/mc/propagate`
  as a generic wrapper that any other API can call internally. See **D1**.

**Request (`McPropagateRequest`)** — strict (with one intentional escape
hatch for user-defined target configurations):
```python
class McPropagateRequest(BaseModel):
    inputs: dict[str, McInput] = Field(
        ..., min_length=1, max_length=64,
        description="Per-variable distribution spec; keys are the names of"
                    " the target function's inputs.",
    )
    target_func: Literal[
        "ser", "sfi_score", "relay_final_state", "custom"
    ] = Field(..., description="Which downstream compute to propagate through.")
    # Intentional loose-typed: each target_func has its own config schema.
    # Validation is delegated to the engine on a per-target basis.
    target_func_config: dict[str, Any] = Field(
        ...,
        description="Target-specific config (e.g. baseline params, custom"
                    " function URL). See engine/core/monte_carlo_engine for"
                    " per-target schemas.",
    )
    n_samples: int = Field(ge=100, le=200_000, default=10_000)
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    return_samples: bool = Field(
        default=False,
        description="If true, response includes raw sample array (large).",
    )
    compute_sobol: bool = Field(
        default=False,
        description="If true, compute Sobol' first-order + total indices.",
    )
```

**Response (`McPropagateResponse`)** — strict:
```python
class McPropagateResponse(BaseModel):
    target_mean: float
    target_std: float = Field(..., ge=0.0)
    ci_lower: float
    ci_upper: float
    samples: Optional[list[float]] = Field(
        default=None,
        description="Returned only when return_samples=True.",
    )
    sobol_indices: Optional[SobolIndices] = Field(
        default=None,
        description="Returned only when compute_sobol=True.",
    )
    diagnostics: McDiagnostics
    evidence_level: Literal["validated", "supported", "planned"]

    @model_validator(mode="after")
    def _check_ci_order(self) -> "McPropagateResponse":
        if self.ci_lower > self.ci_upper:
            raise ValueError("ci_lower must be ≤ ci_upper.")
        return self
```

### 2.5 `POST /api/v1/twin/run`

- **Paper map**: Digital twin step-forward execution; basis for closed-loop
  control in Phase E.
- **Engines**: `engine/core/digital_twin_engine.py` (with EKF correction)
  + `engine/core/controller_engine.py` (PID step if requested).
- **Existing endpoint relation**: `/api/v1/twin/{id}/predict`,
  `/api/v1/twin/{id}/update`, `/api/v1/twin/{id}/simulate` already exist
  (`routers/twin.py`). Phase A adds `/api/v1/twin/run` as a stateless
  variant that doesn't require a persisted twin record. See **D1**.

**Request (`TwinRunRequest`)** — strict:
```python
class TwinRunRequest(BaseModel):
    initial_state: TwinState = Field(
        ...,
        description="Biomass / substrate / temperature / moisture / N at t0.",
    )
    config: TwinConfig
    inputs: list[TwinInputStep] = Field(
        ..., min_length=1, max_length=10_000,
        description="Per-step control vector (feed_rate, ventilation, heating).",
    )
    observations: Optional[list[TwinObservation]] = Field(
        default=None,
        description="Optional measurements for EKF correction. Same length"
                    " as inputs when provided.",
    )
    enable_ekf: bool = Field(
        default=True,
        description="Run Extended Kalman Filter when observations present.",
    )

    @model_validator(mode="after")
    def _check_obs_length(self) -> "TwinRunRequest":
        if self.observations and len(self.observations) != len(self.inputs):
            raise ValueError(
                "observations length must match inputs length when provided."
            )
        return self


class TwinState(BaseModel):
    biomass_kg: float = Field(..., ge=0.0, le=1e6)
    substrate_kg: float = Field(..., ge=0.0, le=1e6)
    temperature_c: float = Field(..., ge=-10.0, le=80.0)
    moisture_pct: float = Field(..., ge=0.0, le=100.0)
    nitrogen_kg: float = Field(..., ge=0.0, le=1e5)


class TwinInputStep(BaseModel):
    feed_rate_kg_h: float = Field(..., ge=0.0, le=1e4)
    ventilation_m3_h: float = Field(..., ge=0.0, le=1e5)
    heating_kw: float = Field(..., ge=0.0, le=1e3)
```

**Response (`TwinRunResponse`)** — strict:
```python
class TwinRunResponse(BaseModel):
    trajectory: list[TwinSnapshot] = Field(..., min_length=1, max_length=10_000)
    estimated_states: list[TwinState] = Field(..., min_length=1, max_length=10_000)
    innovation_stats: InnovationStats
    final_state: TwinState
    evidence_level: Literal["validated", "supported", "planned"]
```

---

## 3. LangGraph Agent skeleton spec

### 3.1 `BOSState` TypedDict

```python
class BOSState(TypedDict, total=False):
    # ---- conversation ----
    messages: Annotated[list[BaseMessage], add_messages]
    intent: Literal[
        "ser", "sfi", "relay", "cyber_lab", "render", "noop", "smalltalk"
    ]

    # ---- problem framing ----
    substrate_type: Optional[str]
    species_code: Optional[str]

    # ---- mass / nitrogen ----
    dm_in: Optional[float]
    dm_out: Optional[float]
    n_in: Optional[float]
    n_rec: Optional[float]

    # ---- rate coefficients ----
    d_prime: Optional[float]
    g_prime: Optional[float]

    # ---- SER outcomes ----
    ser: Optional[float]
    ser_ci: Optional[tuple[float, float]]
    delta_ser: Optional[float]

    # ---- relay config ----
    tau_m2: Optional[float]
    k_decay: Optional[float]
    s0: Optional[float]
    s_min: Optional[float]
    tau_max: Optional[float]

    # ---- gating ----
    sfi_pass: Optional[bool]
    sfi_zone: Optional[str]

    # ---- simulation results ----
    simulation_result: Optional[dict[str, Any]]    # raw response
    cyber_experiment: Optional[dict[str, Any]]     # composed multi-API

    # ---- rendering ----
    charts: Optional[list[ChartSpec]]
    report: Optional[str]                          # markdown summary

    # ---- audit ----
    tool_calls: list[ToolCallRecord]
    evidence_level: Literal["validated", "supported", "planned"]
```

### 3.2 Six nodes

| Node | Calls | Purpose |
|---|---|---|
| `router_node` | (LLM only, no HTTP to Core) | Intent classification → set `state["intent"]`; uses the LLM provider configured in §3.5 |
| `ser_node` | `POST /api/v1/ser/compute` | Compute SER + MC band |
| `sfi_node` | `POST /api/v1/sfi/check` | Verify operating envelope |
| `relay_node` | `POST /api/v1/relay/simulate` | Run M1→M2→M3 |
| `cyber_lab_node` | sequence of Core calls (parallel where independent) | "Cyber wet-lab" — composes multiple Core APIs for what-if exploration |
| `render_node` | (no HTTP) | Format final markdown + chart specs for the client |

#### `cyber_lab_node` typical flows

**Flow A — "Compare two relay strategies"** (parallel where safe):

1. `sfi_check(current_state)` — gate the experiment; abort if unsafe.
2. **In parallel** (`asyncio.gather`):
   - `relay_simulate(scenario_A)`
   - `relay_simulate(scenario_B)`
3. **In parallel**:
   - `ser_compute(A.final_state)`
   - `ser_compute(B.final_state)`
4. Compare SER + MC bands; emit recommendation into `state["report"]`.

**Flow B — "What-if parameter sensitivity"**:

1. `ser_compute(baseline)` — establish reference.
2. `mc_propagate(target_func="ser", inputs={d_prime: perturb_band, ...})`
   — single MC call propagates the full perturbation.
3. **For each tail-quantile point** sampled by the MC call, fan out
   `sfi_check(perturbed_state)` in parallel via `asyncio.gather`.
4. Aggregate joint SER × SFI distribution; produce uncertainty contour.

Partial-failure policy:
- If a parallel branch fails, `cyber_lab_node` records the failure in
  `state["tool_calls"]` with `evidence_level="planned"` and continues
  with the surviving branches. Only the gating step (#1 in Flow A) is
  a hard-stop.

### 3.3 Tool definitions (async)

All Phase A tools are `async def` and share a single `httpx.AsyncClient`
so the event loop can fan out `cyber_lab_node` calls in parallel via
`asyncio.gather` (see §3.2 flows + decision **D4**).

```python
import os
import httpx
from langchain_core.tools import tool

CORE_URL = os.environ["BOS_CORE_URL"]  # e.g. http://localhost:8000/api/v1
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

# Shared client (created once per process; closed at shutdown).
_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
    return _client

@tool
async def ser_compute(req: SerComputeRequest) -> SerComputeResponse:
    """Compute SER + Monte Carlo CI via BOS Core."""
    r = await _get_client().post(
        f"{CORE_URL}/ser/compute",
        json=req.model_dump(),
    )
    r.raise_for_status()
    return SerComputeResponse.model_validate(r.json())

# Identical shape for sfi_check / relay_simulate / mc_propagate / twin_run.
# All node functions are `async def node_fn(state: BOSState) -> BOSState`
# so they can `await` tool calls and use `asyncio.gather` for fan-out.
```

Server-side: `agent/server.py` wires `lifespan` to call
`await _client.aclose()` on shutdown so the AsyncClient is cleanly
released.

### 3.4 Constraints

1. **`backend/agent/` MUST NOT contain `from app.*` at any depth.**
   A unit test in Phase A will fail the build if such import appears.
2. Agent talks to Core only over HTTP. **Schema strategy**: Agent
   maintains hand-authored Pydantic mirrors in `agent/schemas/*.py`.
   Every Core-side schema change in Phase A **must** be propagated to
   the agent mirror in the same commit, and every mirror file must
   carry a `SCHEMA_VERSION = "A.<n>"` constant matching the Core file's
   constant. A `tests/architecture/test_schema_parity.py` reads both
   sides via reflection and fails on drift. (Future phases may swap to
   `openapi-python-client` codegen or a shared wheel; out of scope
   for Phase A.)
3. Agent persists `BOSState` per **D3**. Default = in-memory through the
   `get_checkpointer()` factory in §3.6.
4. Agent process binds port 8001. Single Docker container, isolated
   from Core's 8000.

### 3.5 LLM provider configuration

The `router_node` (and any future LLM-bearing node) reads from a small
provider module so the agent never inherits Core's LLM routing:

```python
# agent/llm.py
import os
from typing import Protocol

class ChatModel(Protocol):
    async def acomplete(self, messages: list[dict]) -> str: ...

def get_chat_model() -> ChatModel:
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"),
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.environ.get("LLM_MODEL", "gpt-4o"))
    if provider in ("qwen", "deepseek"):
        # Use OpenAI-compatible base URL.
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.environ["LLM_MODEL"],
            api_key=os.environ[f"{provider.upper()}_API_KEY"],
            base_url=os.environ[f"{provider.upper()}_BASE_URL"],
        )
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r}")
```

Defaults:
- `LLM_PROVIDER=anthropic`
- `LLM_MODEL=claude-sonnet-4-5`
- `ANTHROPIC_API_KEY=<required>`

This module **must not** import from `backend/app/*`. A grep test
enforces it (see §7 acceptance criterion #3).

### 3.6 Checkpointer abstraction

Decision **D3 = (a) in-memory** for Phase A, but the abstraction is
designed so Phase B+ can swap to Redis or Postgres without touching
any node code:

```python
# agent/persistence.py
import os
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

def get_checkpointer() -> BaseCheckpointSaver:
    """Factory: returns a LangGraph checkpoint saver.

    Phase A: InMemorySaver (decision D3 = a).
    Phase B+: read STATE_BACKEND env (redis|postgres|memory) and dispatch.
              This signature does not need to change.
    """
    backend = os.environ.get("STATE_BACKEND", "memory")
    if backend == "memory":
        return InMemorySaver()
    raise NotImplementedError(
        f"STATE_BACKEND={backend!r} is reserved for a future phase."
    )
```

The graph in `agent/graph.py` calls `graph.compile(checkpointer=get_checkpointer())`.
Phase B can extend this factory with no graph or node changes.

---

## 4. Key decisions (D1 – D5)

> **All five must be answered before Phase A starts.**

### D1 — Relation of `/api/v1/*` V5 contracts to existing endpoints

**Decided: (a) Coexist + explicit sunset timeline.**

Both old and new URLs live. New URLs use the frozen Phase A schema; old
URLs keep V9 schema. To avoid permanent double-maintenance, a sunset
schedule is part of the decision:

| Date offset | Old endpoint state |
|---|---|
| Phase A release (T0) | Both URLs work. New URL is canonical. |
| T0 + 6 months | Old URL responses include `Deprecation` + `Sunset` HTTP headers + a `X-BOS-Migrate-To` header pointing to the V5 path. OpenAPI `deprecated=True`. Log every hit with the caller `User-Agent` so we can audit who still uses them. |
| T0 + 12 months | Old URL handlers removed. Final commit cites this section. |

The other two options were considered:
- **(b) Redirect** — risk: frontend `fetch` callers that don't follow
  redirects break.
- **(c) Replace immediately** — cleanest history; highest blast radius;
  needs a frontend audit pass that isn't in Phase A scope.

### D2 — Pydantic schema strictness

**Decided: (a) Strict.** Every field carries `Field(..., ge/le/gt/lt,
description, examples)` and every constraint that exists in the paper
(e.g. `0 ≤ D′ ≤ 1`, `k_decay > 0`, `dm_out ≤ dm_in`) is enforced at the
schema layer. See the §2.1–§2.5 schema bodies for concrete examples.

The single intentional escape hatch is `McPropagateRequest.target_func_config:
dict[str, Any]` — because each user-selectable target function has its
own config shape, validation is delegated to the engine on a per-target
basis.

Rejected:
- **(b) Medium** — would silently accept inputs that the paper forbids;
  failures surface at engine runtime rather than at API boundary; debug
  cost is high.
- **(c) Loose** — worst OpenAPI; hardest to evolve safely.

### D3 — LangGraph state persistence

**Decided: (a) In-memory for Phase A + `get_checkpointer()` factory
abstraction (§3.6).** Every chat is fresh in Phase A; sufficient for
the end-to-end demo. The factory hides the choice, so Phase B can swap
to Redis or Postgres by extending the factory and toggling
`STATE_BACKEND=redis` without touching any node code.

The other options were considered:
- **(b) Redis** — would let users resume across operator sessions and
  store posteriors that Phase B (Bayesian) wants to reuse. Not in Phase
  A scope; the factory makes the future swap cheap.
- **(c) PostgreSQL** — long-term audit; heaviest; pairs with the existing
  `brain_runtime` document layer. Same path: extend the factory later.

### D4 — Agent ↔ Core wire protocol

**Decided: (a) HTTP REST + Pydantic, with mandatory async-from-day-1.**

All Phase A tool functions are `async def`, use a shared
`httpx.AsyncClient` (see §3.3), and every node function is
`async def node_fn(state: BOSState) -> BOSState` so the event loop can
fan out parallel Core calls in `cyber_lab_node` via `asyncio.gather`.
Synchronous `httpx.post(...)` is **forbidden** in `backend/agent/*`;
a lint check enforces it.

Rationale: a synchronous `cyber_lab` Flow A (§3.2) serially calls 5
Core endpoints (~5× latency). Async + `asyncio.gather` brings parallel
branches close to single-call latency.

Streaming via SSE (option c) is deferred. If `relay/simulate` runtimes
become uncomfortable in practice, we add SSE in a follow-up batch
without changing the REST contract.

Rejected:
- **(b) gRPC + protobuf** — best perf, hardest tooling. Premature.
- **(c) HTTP + SSE only** — useful for >5 s endpoints but adds streaming
  complexity to every tool. Picked up later if measurements demand it.

### D5 — Implementation order of the five APIs

**Decided: SER → SFI → Relay → MC → Twin.**

- SER is the most stable and best-tested engine; warm-up.
- SFI builds on the existing `flight_envelope` and is small.
- Relay involves multi-engine orchestration (twin + kinetics + mass
  balance) — middle complexity.
- MC: generic wrapper. **While implementing SER**, the `MonteCarloConfig`
  schema and the call into `monte_carlo_engine` must be extracted
  through a single internal interface (e.g. `engine.core.monte_carlo_engine
  .propagate(target_fn, dists, n, seed)`). When A4 builds the MC API, it
  re-uses the same interface — `/api/v1/mc/propagate` is then a thin
  wrapper, not a re-implementation.
- Twin is the most complex (EKF + control input). Doing it last lets the
  prior four de-risk the schema patterns.

---

## 5. Phase A batches (work breakdown)

> 6 batches; ≈ 2–3 days each; total ~ 2 person-weeks. Each batch ends
> with the same "stop-and-report" cadence used in Phase 0.5.

### Batch A1 — Core API standardization (5 endpoints)

- Freeze Pydantic schemas in `backend/app/schemas/{ser,sfi,relay,mc,twin}.py`.
- Implement / refactor handlers in `backend/app/routers/{ser,sfi,relay,mc,twin}.py`
  (sfi/relay/mc are new files; ser/twin reuse existing files with
  added handlers).
- Each handler is thin: validate → call `engine/core/*` → wrap response.
- Verification: `pytest tests/unit/test_phase_a_schemas.py` + smoke
  curl per endpoint.

### Batch A2 — OpenAPI freeze + contract tests

- Generate `_reports/phase_a_openapi_snapshot.json` from running app.
- Write `tests/contract/test_phase_a_openapi.py` to assert critical
  fields exist and types match.
- Update frontend `api/` clients (Phase 0.5 already has stubs for some).
- Add deprecation banners on superseded endpoints if **D1** = (b)/(c).

### Batch A3 — `backend/agent/` skeleton → implementation

- Phase 0.5 already created `backend/agent/__init__.py`, `graph.py`,
  `state.py`, `server.py`, `main.py`, `nodes/`, `tools/`.
- Install: `pip install -r backend/agent/requirements.txt` (langgraph,
  langchain-core, httpx, fastapi, uvicorn).
- Implement `state.py::BOSState`, `tools/*` (5 HTTP tools + 1 LLM tool
  for `router_node`), `nodes/*` (6 node functions), `graph.py`
  StateGraph wiring.

### Batch A4 — Agent ↔ Core HTTP integration

- `BOS_CORE_URL=http://localhost:8000/api/v1` env wiring.
- End-to-end "smoke": agent receives "compute SER for batch X" → calls
  `ser/compute` → response back to chat.
- Test in `backend/agent/tests/test_smoke.py` (new dir).

### Batch A5 — End-to-end demo + integration tests

- Docker compose two services: `bos-core` (port 8000) + `bos-agent`
  (port 8001). Compose file in `docker-compose.phase-a.yml`.
- Integration test driving both: `tests/e2e/test_phase_a_e2e.py`
  uses httpx to hit agent, asserts SER value matches Core's direct
  output within 1e-6.

### Batch A6 — Frontend V2 wiring

- Replace V2 stub at `frontend/src/pages/BOSAssistantV2Page.tsx`
  with a chat surface that posts to `http://localhost:8001/agent/chat`
  (or via Vite proxy).
- Stream agent thoughts via SSE if **D4** = (c); otherwise show
  step-by-step tool calls.
- V1 untouched.

**Effort estimate**: ~80–120 person-hours total
(A1: 16h, A2: 8h, A3: 24h, A4: 8h, A5: 16h, A6: 16h, plus ~16h slack
for review cycles and fixes).

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Existing `/api/v1/ser`, `/api/v1/simulation`, `/api/v1/flight-envelope` are already called by frontend | High | Before A1, `grep -r "fetch.*api/v1" frontend/src` produces a call-site inventory. Decision **D1** governs whether to keep both URLs. |
| LangGraph learning curve | Medium | A3 estimate already includes ~1 day for first-pass mistakes. Lean on official `create_react_agent` + custom node where needed. |
| Pydantic v1↔v2 confusion | Low | Project is on Pydantic 2.6.1 (verified Phase 0). All new schemas use v2 idioms (`Field(...)` + `BaseModel.model_validate`). |
| Agent process deployment complexity (two services) | Medium | Phase A5 ships a `docker-compose.phase-a.yml` so local dev is one `docker-compose up`. Production rollout deferred. |
| OpenBLAS / Torch memory pressure (already observed) | Medium | Agent process is small; doesn't load Torch. Core unchanged. The OOM problem is contained to Batch 8 (npm build) and not gating Phase A. |
| `frontend/remotion-runtime/` re-creates 8 705 files on `npm install` | Low | Already gitignored. |
| YOLO weights / native models gated behind optional requirements | Low | Phase A doesn't depend on them. |

---

## 7. Acceptance criteria

Phase A is **DONE** when **all** of the following pass:

| # | Check | Command |
|---|---|---|
| 1 | BOS Core boots | `uvicorn app.main:app --port 8000` returns 200 on `/api/v1/health/live` |
| 2 | BOS Agent boots | `python -m agent.main --port 8001` returns 200 on `/agent/health` |
| 3 | Agent does NOT import `app.*` | `pytest tests/architecture/test_agent_isolation.py` — greps `backend/agent/**` for `from app.` and fails on any match |
| 4 | Direct Core call returns SER | `curl -X POST localhost:8000/api/v1/ser/compute -d '{...}'` returns `{"ser_point": <float>, ...}` |
| 5 | End-to-end agent chat | `curl -X POST localhost:8001/agent/chat -d '{"message": "帮我算 SER for batch 42"}'` returns markdown with the SER number |
| 6 | V1 frontend still works | Navigate to `/bos` in dev server → `BOSAssistantV1Page` renders (no console error) |
| 7 | V2 frontend wired | Navigate to `/bos/v2` → page posts to agent → chat appears |
| 8 | OpenAPI snapshot stable | `pytest tests/contract/test_phase_a_openapi.py` green |
| 9 | Phase 0.5 backend invariants hold | All four Phase 0.5 verification imports still pass (see Phase 0.5 closing report) |

---

## 8. Next steps

1. **User reads this plan**, answers D1–D5.
2. **Claude Code starts Batch A1** with the decisions in hand.
3. After each batch: short report + `⏸ wait for "continue"`. Same
   cadence as Phase 0.5.
4. If at any point a decision turns out to be wrong, surface it
   immediately; do not silently re-route.

### What this plan does NOT decide

- Phase B–G timing (left for after Phase A demo lands).
- Whether `routers/code.py` (deferred in Phase 0.5) gets touched —
  it remains untouched in Phase A.
- Production deployment topology (single host vs cluster) — Phase A
  ships a local `docker-compose` only.
- Authentication on `/agent/*` — Phase A uses same JWT scheme as
  Core's `/api/v1/*` (defer hardened auth to a later phase).

---

**END OF PLAN — awaiting D1–D5 answers.**
