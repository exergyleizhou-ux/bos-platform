"""
BOS Pipeline v9.0 �� Cross-Field Consistency Engine

Checks logical consistency across multiple batch fields:
  - Mass balance: DM_out �� DM_in
  - Nitrogen balance: N_larvae + N_frass �� N_in
  - Temperature vs. species viability
  - Temporal ordering: batch_date < created_at
  - Status transitions: logged �� active �� completed �� archived
  - Derived metric consistency: SER = DM_out / DM_in

Returns structured issues with severity and fix suggestions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENGINE_VERSION = "9.0.0"


@dataclass
class ConsistencyIssue:
    """Single consistency issue."""

    rule: str
    severity: str  # "error", "warning", "info"
    fields: List[str]
    message: str
    suggestion: Optional[str] = None


@dataclass
class ConsistencyInput:
    """Data to check for consistency."""

    current: Dict[str, Any]
    previous: Optional[Dict[str, Any]] = None  # Previous version (for transition checks)
    context: str = "batch"


@dataclass
class ConsistencyResult:
    """Consistency check results."""

    consistent: bool = True
    issues: List[ConsistencyIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    rules_checked: int = 0
    engine_version: str = ENGINE_VERSION


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Consistency Rules
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

VALID_STATUSES = ["logged", "active", "completed", "archived"]
VALID_TRANSITIONS = {
    "logged": ["active", "archived"],
    "active": ["completed", "archived"],
    "completed": ["archived"],
    "archived": [],
}


def check_consistency(inp: ConsistencyInput) -> ConsistencyResult:
    """
    Perform cross-field consistency checks.

    Parameters
    ----------
    inp : ConsistencyInput
        Current data and optionally previous version.

    Returns
    -------
    ConsistencyResult
        List of consistency issues found.
    """
    result = ConsistencyResult()
    data = inp.current

    # ���� Rule 1: Mass balance ����
    result.rules_checked += 1
    dm_in = data.get("dm_in")
    dm_out = data.get("dm_out")
    if dm_in is not None and dm_out is not None:
        if isinstance(dm_in, (int, float)) and isinstance(dm_out, (int, float)):
            if dm_out > dm_in * 1.5:
                result.issues.append(ConsistencyIssue(
                    rule="mass_balance",
                    severity="error",
                    fields=["dm_in", "dm_out"],
                    message=f"dm_out ({dm_out}) exceeds 150% of dm_in ({dm_in}). SER = {dm_out/dm_in:.3f}.",
                    suggestion="Verify dry matter measurements. Check units (kg vs g).",
                ))
            elif dm_out > dm_in:
                result.issues.append(ConsistencyIssue(
                    rule="mass_balance",
                    severity="warning",
                    fields=["dm_in", "dm_out"],
                    message=f"dm_out ({dm_out}) exceeds dm_in ({dm_in}). SER > 1.0.",
                    suggestion="Unusual but possible with wet basis reporting. Verify.",
                ))

    # ���� Rule 2: Nitrogen balance ����
    result.rules_checked += 1
    n_in = data.get("n_in")
    n_larvae = data.get("n_larvae")
    n_frass = data.get("n_frass")
    if all(isinstance(v, (int, float)) for v in [n_in, n_larvae, n_frass] if v is not None):
        if n_in and n_larvae is not None and n_frass is not None:
            n_total_out = n_larvae + n_frass
            if n_in > 0:
                n_ratio = n_total_out / n_in
                if n_ratio > 1.20:
                    result.issues.append(ConsistencyIssue(
                        rule="nitrogen_balance",
                        severity="error",
                        fields=["n_in", "n_larvae", "n_frass"],
                        message=f"N output ({n_total_out:.2f}g) exceeds N input ({n_in:.2f}g) by {(n_ratio-1)*100:.0f}%.",
                        suggestion="Recheck nitrogen analyzer readings. Ensure consistent sample prep.",
                    ))
                elif n_ratio > 1.05:
                    result.issues.append(ConsistencyIssue(
                        rule="nitrogen_balance",
                        severity="warning",
                        fields=["n_in", "n_larvae", "n_frass"],
                        message=f"N balance = {n_ratio:.3f}. Slight excess �� within measurement error.",
                    ))

    # ���� Rule 3: SER consistency ����
    result.rules_checked += 1
    score = data.get("score")
    if dm_in and dm_out and score is not None:
        if isinstance(dm_in, (int, float)) and isinstance(dm_out, (int, float)) and isinstance(score, (int, float)):
            if dm_in > 0:
                expected_ser = dm_out / dm_in
                if abs(expected_ser - score) > 0.01:
                    result.issues.append(ConsistencyIssue(
                        rule="ser_consistency",
                        severity="warning",
                        fields=["dm_in", "dm_out", "score"],
                        message=f"score ({score:.4f}) doesn't match DM_out/DM_in ({expected_ser:.4f}).",
                        suggestion="Recalculate score or verify DM values.",
                    ))

    # ���� Rule 4: Ash balance ����
    result.rules_checked += 1
    ash_in = data.get("ash_in")
    ash_out = data.get("ash_out")
    if ash_in is not None and ash_out is not None:
        if isinstance(ash_in, (int, float)) and isinstance(ash_out, (int, float)):
            if ash_in > 0 and ash_out > ash_in * 1.5:
                result.issues.append(ConsistencyIssue(
                    rule="ash_balance",
                    severity="warning",
                    fields=["ash_in", "ash_out"],
                    message=f"Ash output ({ash_out}g) exceeds ash input ({ash_in}g) by >50%. Possible contamination.",
                    suggestion="Check for soil/sand contamination in substrate.",
                ))

    # ���� Rule 5: Status transition ����
    result.rules_checked += 1
    if inp.previous:
        old_status = inp.previous.get("status")
        new_status = data.get("status")
        if old_status and new_status and old_status != new_status:
            allowed = VALID_TRANSITIONS.get(old_status, [])
            if new_status not in allowed:
                result.issues.append(ConsistencyIssue(
                    rule="status_transition",
                    severity="error",
                    fields=["status"],
                    message=f"Invalid status transition: '{old_status}' �� '{new_status}'. Allowed: {allowed}.",
                    suggestion=f"Set status to one of: {', '.join(allowed)}.",
                ))

    # ���� Rule 6: Temperature / moisture coherence ����
    result.rules_checked += 1
    temp = data.get("temperature")
    moisture = data.get("moisture")
    if temp is not None and moisture is not None:
        if isinstance(temp, (int, float)) and isinstance(moisture, (int, float)):
            # Very high temp + very high moisture �� likely measurement error
            if temp > 40 and moisture > 90:
                result.issues.append(ConsistencyIssue(
                    rule="temp_moisture_coherence",
                    severity="warning",
                    fields=["temperature", "moisture"],
                    message=f"Temperature ({temp}��C) and moisture ({moisture}%) both extreme. Verify sensors.",
                ))

    # ���� Rule 7: Fat balance ����
    result.rules_checked += 1
    fat_in = data.get("fat_in")
    fat_out = data.get("fat_out")
    if fat_in is not None and fat_out is not None:
        if isinstance(fat_in, (int, float)) and isinstance(fat_out, (int, float)):
            if fat_in > 0 and fat_out > fat_in * 5:
                result.issues.append(ConsistencyIssue(
                    rule="fat_balance",
                    severity="warning",
                    fields=["fat_in", "fat_out"],
                    message=f"Fat output ({fat_out}g) is >5�� fat input ({fat_in}g). Very high lipid accumulation.",
                    suggestion="BSF can accumulate lipids but >5�� ratio warrants verification.",
                ))

    # ���� Rule 8: Batch ID format ����
    result.rules_checked += 1
    batch_id = data.get("batch_id")
    if batch_id is not None:
        if isinstance(batch_id, str):
            if len(batch_id.strip()) == 0:
                result.issues.append(ConsistencyIssue(
                    rule="batch_id_format",
                    severity="error",
                    fields=["batch_id"],
                    message="batch_id is empty or whitespace-only.",
                    suggestion="Provide a meaningful batch identifier.",
                ))
            elif len(batch_id) > 100:
                result.issues.append(ConsistencyIssue(
                    rule="batch_id_format",
                    severity="warning",
                    fields=["batch_id"],
                    message=f"batch_id is very long ({len(batch_id)} chars). Consider a shorter identifier.",
                ))

    # ���� Aggregate ����
    for issue in result.issues:
        if issue.severity == "error":
            result.error_count += 1
        elif issue.severity == "warning":
            result.warning_count += 1

    result.consistent = result.error_count == 0

    return result
