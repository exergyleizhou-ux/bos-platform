"""
BOS Pipeline v9.0 �� Dynamic Schema Validation Engine

Validates arbitrary data against dynamically-defined schemas.
Used for:
  - Custom metadata validation
  - Webhook payload validation
  - User-defined field validation
  - Import file column mapping checks

Schema definition format:
{
    "field_name": {
        "type": "float",          # float, int, str, bool, date, list, dict
        "required": true,
        "min": 0,
        "max": 100,
        "pattern": "^[A-Z]+$",   # Regex for strings
        "choices": ["a", "b"],    # Allowed values
        "default": 0.0
    }
}
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENGINE_VERSION = "9.0.0"


@dataclass
class SchemaField:
    """Definition for a single schema field."""

    name: str
    field_type: str = "str"  # float, int, str, bool, date, list, dict
    required: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    nullable: bool = True
    description: Optional[str] = None


@dataclass
class SchemaValidationIssue:
    """Single schema validation issue."""

    field: str
    code: str
    severity: str  # error, warning
    message: str


@dataclass
class SchemaValidationResult:
    """Schema validation results."""

    valid: bool = True
    issues: List[SchemaValidationIssue] = field(default_factory=list)
    validated_data: Dict[str, Any] = field(default_factory=dict)
    defaults_applied: List[str] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    engine_version: str = ENGINE_VERSION


TYPE_MAP = {
    "float": (int, float),
    "int": (int,),
    "str": (str,),
    "bool": (bool,),
    "list": (list,),
    "dict": (dict,),
    "date": (str,),  # Validated via regex
}


def validate_against_schema(
    data: Dict[str, Any],
    schema: List[SchemaField],
) -> SchemaValidationResult:
    """
    Validate data against a dynamic schema.

    Parameters
    ----------
    data : dict
        Data to validate.
    schema : list of SchemaField
        Field definitions.

    Returns
    -------
    SchemaValidationResult
        Validation result with issues and cleaned data.
    """
    result = SchemaValidationResult()
    validated: Dict[str, Any] = {}

    for field_def in schema:
        name = field_def.name
        value = data.get(name)

        # Apply default
        if value is None and field_def.default is not None:
            value = field_def.default
            result.defaults_applied.append(name)

        # Required check
        if value is None:
            if field_def.required:
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="REQUIRED_MISSING",
                    severity="error",
                    message=f"Required field '{name}' is missing",
                ))
            continue

        # Null check
        if value is None and not field_def.nullable:
            result.issues.append(SchemaValidationIssue(
                field=name,
                code="NULL_NOT_ALLOWED",
                severity="error",
                message=f"Field '{name}' cannot be null",
            ))
            continue

        # Type check
        expected_types = TYPE_MAP.get(field_def.field_type)
        if expected_types and not isinstance(value, expected_types):
            # Try coercion
            try:
                if field_def.field_type == "float":
                    value = float(value)
                elif field_def.field_type == "int":
                    value = int(value)
                elif field_def.field_type == "str":
                    value = str(value)
                elif field_def.field_type == "bool":
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes")
                    else:
                        value = bool(value)
            except (ValueError, TypeError):
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="TYPE_MISMATCH",
                    severity="error",
                    message=f"Field '{name}': expected {field_def.field_type}, got {type(value).__name__}",
                ))
                continue

        # Range checks
        if isinstance(value, (int, float)):
            if field_def.min_value is not None and value < field_def.min_value:
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="BELOW_MIN",
                    severity="error",
                    message=f"Field '{name}': value {value} below minimum {field_def.min_value}",
                ))
            if field_def.max_value is not None and value > field_def.max_value:
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="ABOVE_MAX",
                    severity="error",
                    message=f"Field '{name}': value {value} above maximum {field_def.max_value}",
                ))

        # Length checks
        if isinstance(value, (str, list)):
            if field_def.min_length is not None and len(value) < field_def.min_length:
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="TOO_SHORT",
                    severity="error",
                    message=f"Field '{name}': length {len(value)} below minimum {field_def.min_length}",
                ))
            if field_def.max_length is not None and len(value) > field_def.max_length:
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="TOO_LONG",
                    severity="error",
                    message=f"Field '{name}': length {len(value)} above maximum {field_def.max_length}",
                ))

        # Pattern check
        if isinstance(value, str) and field_def.pattern:
            if not re.match(field_def.pattern, value):
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="PATTERN_MISMATCH",
                    severity="error",
                    message=f"Field '{name}': value '{value}' doesn't match pattern '{field_def.pattern}'",
                ))

        # Choices check
        if field_def.choices is not None and value not in field_def.choices:
            result.issues.append(SchemaValidationIssue(
                field=name,
                code="INVALID_CHOICE",
                severity="error",
                message=f"Field '{name}': value '{value}' not in allowed choices: {field_def.choices}",
            ))

        # Date format check
        if field_def.field_type == "date" and isinstance(value, str):
            date_pattern = r"^\d{4}-\d{2}-\d{2}$"
            if not re.match(date_pattern, value):
                result.issues.append(SchemaValidationIssue(
                    field=name,
                    code="INVALID_DATE",
                    severity="error",
                    message=f"Field '{name}': '{value}' is not a valid date (expected YYYY-MM-DD)",
                ))

        validated[name] = value

    # Aggregate
    for issue in result.issues:
        if issue.severity == "error":
            result.error_count += 1
        else:
            result.warning_count += 1

    result.valid = result.error_count == 0
    result.validated_data = validated

    return result

