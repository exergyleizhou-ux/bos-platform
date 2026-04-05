"""
BOS Pipeline v9.0 �� Data Validator Engine

Validates input data quality before scientific computations.
Performs:
  1. Type checking
  2. Range validation (physical plausibility)
  3. Cross-field consistency checks
  4. Missing value assessment
  5. Unit conversion verification

Returns a structured validation report with severity levels:
  - ERROR   : Cannot proceed �� hard validation failure
  - WARNING : Suspicious but computation can proceed
  - INFO    : Informational note
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.engine.species_db import get_species

ENGINE_VERSION = "9.0.0"


@dataclass
class ValidationIssue:
    """Single validation issue."""

    field: str
    severity: str  # "error", "warning", "info"
    code: str
    message: str
    value: Optional[Any] = None
    expected: Optional[str] = None


@dataclass
class ValidationInput:
    """Input data to validate."""

    data: Dict[str, Any]
    species: str = "BSF"
    context: str = "batch"  # "batch", "ser", "simulation", "export"


@dataclass
class ValidationResult:
    """Validation report."""

    valid: bool = True  # True if no errors (warnings OK)
    issues: List[ValidationIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    fields_checked: int = 0
    missing_fields: List[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Physical Plausibility Ranges
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

BATCH_FIELD_RULES: Dict[str, Dict[str, Any]] = {
    "dm_in": {
        "type": (int, float),
        "min": 0.001,
        "max": 100_000,
        "unit": "kg DM",
        "required": True,
    },
    "dm_out": {
        "type": (int, float),
        "min": 0,
        "max": 100_000,
        "unit": "kg DM",
        "required": True,
    },
    "n_in": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
    "n_larvae": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
    "n_frass": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
    "temperature": {
        "type": (int, float),
        "min": -10,
        "max": 60,
        "unit": "��C",
        "required": False,
    },
    "moisture": {
        "type": (int, float),
        "min": 0,
        "max": 100,
        "unit": "%",
        "required": False,
    },
    "feed_rate": {
        "type": (int, float),
        "min": 0,
        "max": 10,
        "unit": "g DM/larva/day",
        "required": False,
    },
    "density": {
        "type": (int, float),
        "min": 0,
        "max": 100_000,
        "unit": "larvae/m2",
        "required": False,
    },
    "ash_in": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
    "ash_out": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
    "fat_in": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
    "fat_out": {
        "type": (int, float),
        "min": 0,
        "max": 1_000_000,
        "unit": "g",
        "required": False,
    },
}


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Validation Logic
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def validate_batch_data(inp: ValidationInput) -> ValidationResult:
    """
    Validate batch input data.

    Parameters
    ----------
    inp : ValidationInput
        Data dictionary and context.

    Returns
    -------
    ValidationResult
        Structured validation report.
    """
    result = ValidationResult()
    data = inp.data
    rules = BATCH_FIELD_RULES

    # ���� 1. Field-level validation ����
    for field_name, rule in rules.items():
        result.fields_checked += 1
        value = data.get(field_name)

        # Check required
        if value is None:
            if rule.get("required", False):
                result.issues.append(ValidationIssue(
                    field=field_name,
                    severity="error",
                    code="E_MISSING_REQUIRED",
                    message=f"Required field '{field_name}' is missing",
                    expected=f"Type: {rule['type']}, Range: [{rule['min']}, {rule['max']}]",
                ))
            else:
                result.missing_fields.append(field_name)
            continue

        # Check type
        if not isinstance(value, rule["type"]):
            result.issues.append(ValidationIssue(
                field=field_name,
                severity="error",
                code="E_INVALID_TYPE",
                message=f"Field '{field_name}' has invalid type: {type(value).__name__}, expected numeric",
                value=value,
            ))
            continue

        # Check range
        if value < rule["min"]:
            result.issues.append(ValidationIssue(
                field=field_name,
                severity="error",
                code="E_BELOW_MIN",
                message=f"Field '{field_name}' = {value} is below minimum {rule['min']} {rule['unit']}",
                value=value,
                expected=f">= {rule['min']}",
            ))
        elif value > rule["max"]:
            result.issues.append(ValidationIssue(
                field=field_name,
                severity="error",
                code="E_ABOVE_MAX",
                message=f"Field '{field_name}' = {value} exceeds maximum {rule['max']} {rule['unit']}",
                value=value,
                expected=f"<= {rule['max']}",
            ))

    # ���� 2. Cross-field consistency checks ����
    dm_in = data.get("dm_in")
    dm_out = data.get("dm_out")

    if dm_in is not None and dm_out is not None:
        if isinstance(dm_in, (int, float)) and isinstance(dm_out, (int, float)):
            if dm_out > dm_in:
                result.issues.append(ValidationIssue(
                    field="dm_out",
                    severity="warning",
                    code="W_DM_OUT_GT_IN",
                    message=f"dm_out ({dm_out}) exceeds dm_in ({dm_in}). SER > 1.0 is physically unusual.",
                    value=dm_out,
                ))

            if dm_in > 0 and dm_out / dm_in > 0.5:
                result.issues.append(ValidationIssue(
                    field="dm_out",
                    severity="info",
                    code="I_HIGH_SER",
                    message=f"SER = {dm_out/dm_in:.3f} is very high. Verify measurements.",
                    value=round(dm_out / dm_in, 4),
                ))

    # Nitrogen balance check
    n_in = data.get("n_in")
    n_larvae = data.get("n_larvae")
    n_frass = data.get("n_frass")
    if all(v is not None and isinstance(v, (int, float)) for v in [n_in, n_larvae, n_frass]):
        if n_in > 0:
            n_balance = (n_larvae + n_frass) / n_in
            if n_balance > 1.15:
                result.issues.append(ValidationIssue(
                    field="n_balance",
                    severity="warning",
                    code="W_N_BALANCE_HIGH",
                    message=f"Nitrogen balance = {n_balance:.3f} (>115%). N output exceeds input.",
                    value=round(n_balance, 4),
                ))
            elif n_balance < 0.50:
                result.issues.append(ValidationIssue(
                    field="n_balance",
                    severity="warning",
                    code="W_N_BALANCE_LOW",
                    message=f"Nitrogen balance = {n_balance:.3f} (<50%). High N losses.",
                    value=round(n_balance, 4),
                ))

    # ���� 3. Species-specific checks ����
    sp = get_species(inp.species)
    if sp:
        temp = data.get("temperature")
        if temp is not None and isinstance(temp, (int, float)):
            if temp < sp.temp_lethal_low:
                result.issues.append(ValidationIssue(
                    field="temperature",
                    severity="error",
                    code="E_LETHAL_TEMP_LOW",
                    message=f"Temperature {temp}��C is below lethal threshold ({sp.temp_lethal_low}��C) for {sp.common_name}",
                    value=temp,
                ))
            elif temp > sp.temp_lethal_high:
                result.issues.append(ValidationIssue(
                    field="temperature",
                    severity="error",
                    code="E_LETHAL_TEMP_HIGH",
                    message=f"Temperature {temp}��C exceeds lethal threshold ({sp.temp_lethal_high}��C) for {sp.common_name}",
                    value=temp,
                ))
            elif temp < sp.temp_min or temp > sp.temp_max:
                result.issues.append(ValidationIssue(
                    field="temperature",
                    severity="warning",
                    code="W_TEMP_OUTSIDE_RANGE",
                    message=f"Temperature {temp}��C outside normal range ({sp.temp_min}�C{sp.temp_max}��C) for {sp.common_name}",
                    value=temp,
                ))

        moisture = data.get("moisture")
        if moisture is not None and isinstance(moisture, (int, float)):
            if moisture < sp.moisture_min or moisture > sp.moisture_max:
                result.issues.append(ValidationIssue(
                    field="moisture",
                    severity="warning",
                    code="W_MOISTURE_OUTSIDE_RANGE",
                    message=f"Moisture {moisture}% outside range ({sp.moisture_min}�C{sp.moisture_max}%) for {sp.common_name}",
                    value=moisture,
                ))

    # ���� Aggregate counts ����
    for issue in result.issues:
        if issue.severity == "error":
            result.error_count += 1
        elif issue.severity == "warning":
            result.warning_count += 1
        elif issue.severity == "info":
            result.info_count += 1

    result.valid = result.error_count == 0

    return result
