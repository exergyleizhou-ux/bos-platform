"""
Backward-compatible SER calculator module used by legacy tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class SERInput:
    dm_in: float
    dm_out: float
    n_in: float = 0.0
    n_larvae: float = 0.0
    n_frass: float = 0.0


@dataclass
class NitrogenBalance:
    n_in: float
    n_larvae: float
    n_frass: float
    n_loss: float
    recovery_pct: float


@dataclass
class SERResult:
    ser_value: float
    grade: str
    passed: bool
    nitrogen_balance: NitrogenBalance | None
    computation_time_ms: float


def score_to_grade(score: float) -> str:
    if score < 0:
        raise ValueError("score must be non-negative")
    if score <= 0.08:
        return "A+"
    if score <= 0.12:
        return "A"
    if score <= 0.20:
        return "B"
    if score <= 0.30:
        return "C"
    if score <= 0.40:
        return "D"
    return "F"


def compute_nitrogen_balance(n_in: float, n_larvae: float, n_frass: float) -> NitrogenBalance:
    if n_in <= 0:
        raise ValueError("n_in must be > 0")
    if n_larvae < 0 or n_frass < 0:
        raise ValueError("n_larvae/n_frass must be >= 0")

    n_loss = max(0.0, n_in - n_larvae - n_frass)
    recovery = (n_larvae + n_frass) / n_in
    return NitrogenBalance(
        n_in=n_in,
        n_larvae=n_larvae,
        n_frass=n_frass,
        n_loss=n_loss,
        recovery_pct=recovery,
    )


def compute_ser(inp: SERInput) -> SERResult:
    started = time.perf_counter()

    if inp.dm_in <= 0:
        raise ValueError("dm_in must be > 0")
    if inp.dm_out < 0:
        raise ValueError("dm_out must be >= 0")
    if inp.dm_out > inp.dm_in:
        raise ValueError("dm_out must be <= dm_in")

    # Legacy tests expect lower values to be better.
    ser_value = (inp.dm_in - inp.dm_out) / inp.dm_in
    nitrogen_balance: NitrogenBalance | None = None

    if inp.n_in > 0:
        nitrogen_balance = compute_nitrogen_balance(inp.n_in, inp.n_larvae, inp.n_frass)
        ser_value = ser_value * (0.7 + 0.3 * nitrogen_balance.recovery_pct)

    grade = score_to_grade(ser_value)
    passed = grade in {"A+", "A", "B", "C"}
    elapsed_ms = (time.perf_counter() - started) * 1000

    return SERResult(
        ser_value=ser_value,
        grade=grade,
        passed=passed,
        nitrogen_balance=nitrogen_balance,
        computation_time_ms=elapsed_ms,
    )
