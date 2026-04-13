# ontology_engine/engine/validation/value_domain_validator.py
"""Value domain validator for checking computed results against declared domains."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a value domain validation."""
    valid: bool = True
    violations: list[str] = field(default_factory=list)


class ValueDomainValidator:
    """Validate values against their declared value domains.

    Supports all value domain types:
    - continuous: numeric range checks
    - discrete: membership in value set
    - enum: reference to schema enum definitions
    - score_grade: score to grade mapping
    - money_range: monetary range checks
    """

    def validate(self, value: Any, domain: dict[str, Any]) -> ValidationResult:
        """Validate a value against a value domain definition.

        Args:
            value: The value to validate
            domain: Value domain dict with at least 'type' key

        Returns:
            ValidationResult with valid flag and any violation messages
        """
        result = ValidationResult()
        domain_type = domain.get("type", "continuous")

        try:
            if domain_type == "continuous":
                result = self._validate_continuous(value, domain)
            elif domain_type == "discrete":
                result = self._validate_discrete(value, domain)
            elif domain_type == "enum":
                result = self._validate_enum(value, domain)
            elif domain_type == "score_grade":
                result = self._validate_score_grade(value, domain)
            elif domain_type == "money_range":
                result = self._validate_money_range(value, domain)
            else:
                result.valid = False
                result.violations.append(f"Unknown value domain type: {domain_type}")
        except Exception as e:
            result.valid = False
            result.violations.append(f"Validation error: {e}")

        return result

    def _validate_continuous(self, value: Any, domain: dict) -> ValidationResult:
        """Validate against continuous numeric range."""
        result = ValidationResult()
        if not isinstance(value, (int, float)):
            result.valid = False
            result.violations.append(f"Expected numeric type, got {type(value).__name__}: {value}")
            return result

        min_val = domain.get("min")
        max_val = domain.get("max")

        if min_val is not None and value < min_val:
            result.valid = False
            result.violations.append(f"Value {value} below minimum {min_val}")

        if max_val is not None and value > max_val:
            result.valid = False
            result.violations.append(f"Value {value} exceeds maximum {max_val}")

        step = domain.get("step")
        if step is not None and step > 0:
            # Check if value is on step boundary (with floating point tolerance)
            if abs((value - min_val if min_val is not None else value) % step) > 1e-9:
                result.violations.append(
                    f"Value {value} not on step boundary (step={step})"
                )

        return result

    def _validate_discrete(self, value: Any, domain: dict) -> ValidationResult:
        """Validate against discrete value set."""
        result = ValidationResult()
        valid_values = domain.get("values", [])
        valid_set = {v.get("id", v) if isinstance(v, dict) else v for v in valid_values}

        if value not in valid_set:
            result.valid = False
            result.violations.append(
                f"Value '{value}' not in valid set: {sorted(str(v) for v in valid_set)}"
            )

        return result

    def _validate_enum(self, value: Any, domain: dict) -> ValidationResult:
        """Validate against enum reference."""
        result = ValidationResult()
        # Enum validation requires schema context - just check non-empty for now
        enum_ref = domain.get("enum_ref")
        if enum_ref:
            # Would look up from schema.enums in full implementation
            pass
        else:
            result.violations.append("Enum domain missing enum_ref")
        return result

    def _validate_score_grade(self, value: Any, domain: dict) -> ValidationResult:
        """Validate against score grade ranges."""
        result = ValidationResult()
        if not isinstance(value, (int, float)):
            result.valid = False
            result.violations.append(f"Score must be numeric, got {type(value).__name__}")
            return result

        min_val = domain.get("min")
        max_val = domain.get("max")

        if min_val is not None and value < min_val:
            result.valid = False
            result.violations.append(f"Score {value} below minimum {min_val}")

        if max_val is not None and value > max_val:
            result.valid = False
            result.violations.append(f"Score {value} exceeds maximum {max_val}")

        return result

    def _validate_money_range(self, value: Any, domain: dict) -> ValidationResult:
        """Validate against money range constraints."""
        result = ValidationResult()
        if not isinstance(value, (int, float)):
            result.valid = False
            result.violations.append(f"Monetary value must be numeric, got {type(value).__name__}")
            return result

        min_val = domain.get("min")
        if min_val is not None and value < min_val:
            result.valid = False
            result.violations.append(f"Amount {value} below minimum {min_val}")

        return result

    def map_to_grade(self, score: float, domain: dict) -> str:
        """Map a numeric score to a grade using score_grade domain.

        Args:
            score: The numeric score
            domain: Value domain dict with type='score_grade' and 'grades' list

        Returns:
            Grade code string (e.g., "AAA", "A", "B")
        """
        grades = domain.get("grades", [])
        default_grade = domain.get("default_grade", "UNKNOWN")

        for grade_def in grades:
            min_score = grade_def.get("min_score", 0)
            max_score = grade_def.get("max_score", 100)
            exclusive_max = grade_def.get("exclusive_max", False)
            grade_code = grade_def.get("grade", "UNKNOWN")

            if exclusive_max:
                if min_score <= score < max_score:
                    return grade_code
            else:
                if min_score <= score <= max_score:
                    return grade_code

        return default_grade
