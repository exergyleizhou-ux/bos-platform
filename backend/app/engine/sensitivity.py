"""Backward-compatible sensitivity module used by legacy tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.ser_calculator import SERInput, compute_ser


@dataclass
class SensitivityInput:
    dm_in: float
    dm_out: float
    n_in: float = 0.0
    n_larvae: float = 0.0
    n_frass: float = 0.0
    variation_pct: float = 0.2
    n_steps: int = 10


@dataclass
class SensitivityResult:
    base_ser: float
    parameter_ranking: list[str] = field(default_factory=list)
    impact_scores: dict[str, float] = field(default_factory=dict)
    sweep_results: dict[str, list[dict[str, float]]] = field(default_factory=dict)


def _linear_space(center: float, variation_pct: float, n_steps: int) -> list[float]:
    delta = abs(center) * variation_pct
    if delta == 0:
        delta = variation_pct or 0.1
    start = center - delta
    end = center + delta
    if n_steps <= 1:
        return [center]
    step = (end - start) / (n_steps - 1)
    return [start + i * step for i in range(n_steps)]


def run_sensitivity(inp: SensitivityInput) -> SensitivityResult:
    if inp.n_steps <= 1:
        raise ValueError("n_steps must be > 1")
    if inp.dm_in <= 0:
        raise ValueError("dm_in must be > 0")

    base = compute_ser(
        SERInput(
            dm_in=inp.dm_in,
            dm_out=inp.dm_out,
            n_in=inp.n_in,
            n_larvae=inp.n_larvae,
            n_frass=inp.n_frass,
        )
    ).ser_value

    params = {
        "dm_in": inp.dm_in,
        "dm_out": inp.dm_out,
    }
    if inp.n_in > 0:
        params["n_in"] = inp.n_in
        params["n_larvae"] = inp.n_larvae
        params["n_frass"] = inp.n_frass

    impact_scores: dict[str, float] = {}
    sweep_results: dict[str, list[dict[str, float]]] = {}

    for name, center in params.items():
        points: list[dict[str, float]] = []
        ser_values: list[float] = []
        for x in _linear_space(center, inp.variation_pct, inp.n_steps):
            sample = params.copy()
            sample[name] = x
            # Guard invalid dm bounds.
            if name == "dm_out" and x > sample["dm_in"]:
                x = sample["dm_in"]
                sample[name] = x
            if name == "dm_in" and x <= 0:
                x = 1e-6
                sample[name] = x
            ser = compute_ser(
                SERInput(
                    dm_in=sample["dm_in"],
                    dm_out=sample["dm_out"],
                    n_in=sample.get("n_in", 0.0),
                    n_larvae=sample.get("n_larvae", 0.0),
                    n_frass=sample.get("n_frass", 0.0),
                )
            ).ser_value
            points.append({"x": float(x), "ser": float(ser)})
            ser_values.append(float(ser))
        sweep_results[name] = points
        impact_scores[name] = max(ser_values) - min(ser_values)

    ranking = sorted(impact_scores, key=impact_scores.get, reverse=True)
    return SensitivityResult(
        base_ser=float(base),
        parameter_ranking=ranking,
        impact_scores={k: float(v) for k, v in impact_scores.items()},
        sweep_results=sweep_results,
    )
