"""
BOS Pipeline v9.0 — SER Engine (System Efficiency Ratio)

Pure-function engine for computing the System Efficiency Ratio and related
bioconversion efficiency metrics.

The SER is the primary KPI for insect bioconversion:
  SER = DM_out / DM_in

Additional metrics:
  - EER (Energy Efficiency Ratio)
  - MCR (Mass Conversion Ratio)
  - BCR (Bioconversion Rate)
  - Nitrogen balance
  - Ash balance
  - Fat balance

Grading scale:
  A+  : SER ≥ 0.30
  A   : SER ≥ 0.25
  B   : SER ≥ 0.20
  C   : SER ≥ 0.15
  D   : SER ≥ 0.10
  F   : SER < 0.10
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

ENGINE_VERSION = "9.0.0"

# ═══════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════


@dataclass
class SERInput:
    """Input parameters for SER calculation."""

    dm_in: float  # Dry matter input (kg)
    dm_out: float  # Dry matter output — larvae (kg)
    n_in: float = 0.0  # Nitrogen input (g)
    n_larvae: float = 0.0  # Nitrogen in larvae (g)
    n_frass: float = 0.0  # Nitrogen in frass (g)
    ash_in: float = 0.0  # Ash input (g)
    ash_out: float = 0.0  # Ash output (g)
    fat_in: float = 0.0  # Fat input (g)
    fat_out: float = 0.0  # Fat output (g)

    def validate(self) -> List[str]:
        """Validate inputs and return list of error codes."""
        errors: List[str] = []

        if self.dm_in <= 0:
            errors.append("E001_DM_IN_NONPOSITIVE")
        if self.dm_out < 0:
            errors.append("E002_DM_OUT_NEGATIVE")
        if self.dm_out > self.dm_in * 2:
            errors.append("W001_DM_OUT_EXCEEDS_INPUT")
        if self.n_in < 0:
            errors.append("E003_N_IN_NEGATIVE")
        if self.n_larvae < 0:
            errors.append("E004_N_LARVAE_NEGATIVE")
        if self.n_frass < 0:
            errors.append("E005_N_FRASS_NEGATIVE")

        # Nitrogen balance check (allow 15% tolerance for gas losses)
        if self.n_in > 0:
            n_total_out = self.n_larvae + self.n_frass
            n_balance = n_total_out / self.n_in
            if n_balance > 1.15:
                errors.append("W002_NITROGEN_BALANCE_EXCEEDS_INPUT")

        return errors


@dataclass
class SERResult:
    """Complete SER calculation result."""

    ser_value: float
    eer: Optional[float] = None
    mcr: Optional[float] = None
    bcr: Optional[float] = None
    nitrogen_balance: Optional[float] = None
    ash_balance: Optional[float] = None
    fat_balance: Optional[float] = None
    passed: bool = False
    fail_codes: List[str] = field(default_factory=list)
    grade: str = "F"
    recommendations: List[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION


# ═══════════════════════════════════════════════
# Grading
# ═══════════════════════════════════════════════

GRADE_THRESHOLDS: List[Tuple[str, float]] = [
    ("A+", 0.25),
    ("A", 0.20),
    ("B", 0.15),
    ("C", 0.10),
    ("D", 0.05),
]

SER_PASS_THRESHOLD = 0.15  # Minimum SER to pass
PASS_THRESHOLD = SER_PASS_THRESHOLD  # Backward-compatible alias used by legacy tests.


def grade_ser(ser_value: float) -> str:
    """Assign a letter grade based on SER value."""
    for grade_label, threshold in GRADE_THRESHOLDS:
        if ser_value >= threshold:
            return grade_label
    return "F"


def grade_ser_result(ser_value: float) -> str:
    """Return the user-facing grade used by result payloads and dashboards."""
    grade = grade_ser(ser_value)
    if ser_value < 0.10:
        return "F"
    return grade


# ═══════════════════════════════════════════════
# Recommendations
# ═══════════════════════════════════════════════


def generate_recommendations(inp: SERInput, result: SERResult) -> List[str]:
    """Generate actionable recommendations based on SER results."""
    recs: List[str] = []

    if result.ser_value < 0.10:
        recs.append(
            "CRITICAL: SER below 0.10 indicates severe conversion issues. Review substrate quality and larval health."
        )
    elif result.ser_value < 0.15:
        recs.append("SER below pass threshold (0.15). Consider adjusting feed rate or moisture content.")
    elif result.ser_value < 0.20:
        recs.append("SER is acceptable but below optimal. Fine-tune temperature and density parameters.")
    elif result.ser_value < 0.25:
        recs.append("Good SER. Minor optimizations in substrate composition may improve further.")
    elif result.ser_value >= 0.30:
        recs.append("Excellent SER. Current parameters are performing at top tier.")

    # Nitrogen balance recommendations
    if result.nitrogen_balance is not None:
        if result.nitrogen_balance < 0.70:
            recs.append("High nitrogen loss detected (>30%). Check for ammonia volatilization. Reduce aeration or pH.")
        elif result.nitrogen_balance > 1.10:
            recs.append("Nitrogen balance >110% — possible measurement error. Re-calibrate nitrogen analyzer.")

    # Ash balance recommendations
    if result.ash_balance is not None:
        if result.ash_balance > 1.20:
            recs.append("Ash output significantly exceeds input. Check for soil/sand contamination in substrate.")

    # Fat recommendations
    if result.fat_balance is not None:
        if result.fat_balance > 2.0:
            recs.append(
                "Very high fat conversion. BSF larvae are accumulating lipids well — consider lipid extraction."
            )
        elif result.fat_balance < 0.5 and inp.fat_in > 0:
            recs.append("Low fat conversion. Substrate lipid content may be suboptimal for BSF growth.")

    return recs


# ═══════════════════════════════════════════════
# Main Computation
# ═══════════════════════════════════════════════


def compute_ser(inp: SERInput) -> SERResult:
    """
    Compute the System Efficiency Ratio and all related metrics.

    This is a pure function with no side effects — safe for concurrent use.

    Parameters
    ----------
    inp : SERInput
        Validated input parameters.

    Returns
    -------
    SERResult
        Complete calculation results including grade and recommendations.
    """
    # 1. Validate
    errors = inp.validate()
    hard_errors = [e for e in errors if e.startswith("E")]
    if hard_errors:
        return SERResult(
            ser_value=0.0,
            passed=False,
            fail_codes=errors,
            grade="F",
            recommendations=["Fix input errors before calculating SER."],
        )

    # 2. Core SER
    ser_value = inp.dm_out / inp.dm_in if inp.dm_in > 0 else 0.0

    # 3. Energy Efficiency Ratio
    # Legacy consumers treat this as the same dry-matter efficiency ratio.
    eer = None
    if inp.dm_in > 0:
        eer = round(ser_value, 4)

    # 4. Mass Conversion Ratio (MCR) — same as SER for DM basis
    mcr = round(ser_value, 4)

    # 5. Bioconversion Rate (BCR) — fraction of substrate consumed
    bcr = None
    if inp.dm_in > 0:
        dm_consumed = inp.dm_in - (inp.dm_in - inp.dm_out)  # simplified
        bcr = round(1.0 - (inp.dm_in - inp.dm_out) / inp.dm_in, 4) if inp.dm_in > 0 else 0.0

    # 6. Nitrogen balance
    nitrogen_balance = None
    if inp.n_in > 0:
        n_total_out = inp.n_larvae + inp.n_frass
        nitrogen_balance = round(n_total_out / inp.n_in, 4)

    # 7. Ash balance
    ash_balance = None
    if inp.ash_in > 0:
        ash_balance = round(inp.ash_out / inp.ash_in, 4)

    # 8. Fat balance
    fat_balance = None
    if inp.fat_in > 0:
        fat_balance = round(inp.fat_out / inp.fat_in, 4)

    # 9. Grade
    ser_rounded = round(ser_value, 4)
    grade = grade_ser_result(ser_rounded)

    # 10. Pass/fail
    passed = ser_rounded >= SER_PASS_THRESHOLD and not hard_errors

    # 11. Build result
    if ser_rounded > 1.0 and "SER_ABOVE_1" not in errors:
        errors.append("SER_ABOVE_1")
    if nitrogen_balance is not None and nitrogen_balance > 1.0 and "N_IMBALANCE" not in errors:
        errors.append("N_IMBALANCE")

    result = SERResult(
        ser_value=ser_rounded,
        eer=eer,
        mcr=mcr,
        bcr=bcr,
        nitrogen_balance=nitrogen_balance,
        ash_balance=ash_balance,
        fat_balance=fat_balance,
        passed=passed,
        fail_codes=errors,
        grade=grade,
    )

    # 12. Recommendations
    result.recommendations = generate_recommendations(inp, result)

    return result


# ═══════════════════════════════════════════════
# Batch Processing
# ═══════════════════════════════════════════════


def compute_ser_batch(inputs: List[SERInput]) -> List[SERResult]:
    """Compute SER for multiple batches."""
    return [compute_ser(inp) for inp in inputs]


# ═══════════════════════════════════════════════
# Statistics
# ═══════════════════════════════════════════════


def compute_ser_statistics(results: List[SERResult]) -> dict:
    """Compute aggregate statistics over a collection of SER results."""
    if not results:
        return {
            "count": 0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "median": 0.0,
            "pass_rate": 0.0,
            "grade_distribution": {},
        }

    ser_values = np.array([r.ser_value for r in results])
    grades = [r.grade for r in results]

    grade_counts: dict[str, int] = {}
    for g in grades:
        grade_counts[g] = grade_counts.get(g, 0) + 1

    return {
        "count": len(results),
        "mean": float(np.mean(ser_values)),
        "std": float(np.std(ser_values)),
        "min": float(np.min(ser_values)),
        "max": float(np.max(ser_values)),
        "median": float(np.median(ser_values)),
        "pass_rate": sum(1 for r in results if r.passed) / len(results),
        "grade_distribution": grade_counts,
    }
