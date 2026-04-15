"""Operator Registry with JSON Schema support.

This module extends the base OperatorRegistry with:
- OperatorSchema model for registration metadata
- JSON Schema generation for operator parameters
- Dynamic validation support
"""
from __future__ import annotations

from typing import Any, Literal

from ontology_engine.engine.rule.models import OperatorSchema


# JSON Schema templates for each operator type
OPERATOR_SCHEMAS: dict[str, dict[str, Any]] = {
    "SET_FLAG": {
        "type": "object",
        "properties": {
            "flag": {"type": "string", "description": "Flag name to set"},
            "value": {"type": ["boolean", "string", "number"], "description": "Value to assign"},
        },
        "required": ["flag", "value"],
    },
    "REJECT": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Rejection reason"},
        },
        "required": ["reason"],
    },
    "APPROVE": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Approval message"},
        },
    },
    "COMPUTE": {
        "type": "object",
        "properties": {
            "formula": {"type": "string", "description": "Formula expression"},
            "output_field": {"type": "string", "description": "Output field name"},
        },
        "required": ["formula", "output_field"],
    },
    "BINNING": {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input variable name"},
            "output": {"type": "string", "description": "Output variable name"},
            "inclusive_max": {"type": "boolean", "description": "Include upper bound"},
            "bins": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "range": {
                            "type": "array",
                            "items": {"type": ["number", "null"]},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "[lower, upper] tuple",
                        },
                        "label": {"type": "string", "description": "Bin label"},
                    },
                    "required": ["range", "label"],
                },
                "description": "Bin definitions",
            },
        },
        "required": ["input", "output", "bins"],
    },
    "SCORECARD": {
        "type": "object",
        "properties": {
            "output": {"type": "string", "description": "Output variable name"},
            "baseline": {"type": "number", "description": "Baseline score"},
            "post_formula": {"type": "string", "description": "Post-processing formula"},
            "variables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Variable name"},
                        "points": {
                            "type": "object",
                            "description": "Condition to points mapping",
                        },
                    },
                    "required": ["name", "points"],
                },
            },
        },
        "required": ["output", "baseline", "variables"],
    },
    "WEIGHTED_SUM": {
        "type": "object",
        "properties": {
            "output": {"type": "string", "description": "Output variable name"},
            "weights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input variable name"},
                        "weight": {"type": "number", "description": "Weight value (0-1)"},
                    },
                    "required": ["input", "weight"],
                },
                "description": "Weight configuration",
            },
            "grade_multipliers": {
                "type": "object",
                "description": "Grade to multiplier mapping (e.g., {'AAA': 1.8})",
            },
            "grade_input": {"type": "string", "description": "Grade input variable name"},
        },
        "required": ["output", "weights"],
    },
    "DECISION_TABLE": {
        "type": "object",
        "properties": {
            "conditions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "variable": {"type": "string"},
                        "format": {"type": "string"},
                    },
                    "required": ["variable"],
                },
            },
            "output": {"type": "string", "description": "Output variable name"},
            "matrix": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "when": {"type": "object", "description": "Condition mapping"},
                        "result": {"type": "string", "description": "Result value"},
                        "default": {"type": "string", "description": "Default result when no match"},
                    },
                },
            },
        },
        "required": ["conditions", "output", "matrix"],
    },
    "LLM_JUDGE": {
        "type": "object",
        "properties": {
            "output": {"type": "string", "description": "Output variable name"},
            "prompt_template": {"type": "string", "description": "Prompt template"},
            "input_mapping": {
                "type": "object",
                "description": "Input variable to template placeholder mapping",
            },
            "expected_format": {"type": "string", "description": "Expected output format"},
            "confidence_threshold": {"type": "number", "minimum": 0, "maximum": 1},
            "timeout_ms": {"type": "integer", "minimum": 1000},
            "fallback_value": {"type": "string", "description": "Fallback value on error"},
        },
        "required": ["output", "prompt_template"],
    },
    "TRIGGER_ALERT": {
        "type": "object",
        "properties": {
            "alert_level": {
                "type": "string",
                "enum": ["info", "warning", "high", "critical"],
                "description": "Alert severity level",
            },
            "alert_type": {"type": "string", "description": "Alert type identifier"},
            "message": {"type": "string", "description": "Alert message template"},
        },
        "required": ["alert_level", "alert_type", "message"],
    },
    "SWITCH": {
        "type": "object",
        "properties": {
            "variable": {"type": "string", "description": "Switch variable name"},
            "cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string", "description": "Case condition"},
                        "operator": {"type": "string", "description": "Operator to execute"},
                        "params": {"type": "object", "description": "Operator parameters"},
                    },
                    "required": ["condition", "operator"],
                },
            },
            "default": {
                "type": "object",
                "properties": {
                    "operator": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "required": ["variable", "cases"],
    },
}


def get_operator_schema(name: str) -> dict[str, Any] | None:
    """Get the JSON Schema for an operator by name.

    Args:
        name: Operator name

    Returns:
        JSON Schema dict or None if not found
    """
    return OPERATOR_SCHEMAS.get(name)


def get_all_operator_schemas() -> dict[str, dict[str, Any]]:
    """Get all registered operator schemas.

    Returns:
        Dict mapping operator names to their schemas
    """
    return dict(OPERATOR_SCHEMAS)


def validate_operator_params(name: str, params: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate operator parameters against schema.

    This is a basic validation. For full JSON Schema validation,
    use a library like jsonschema.

    Args:
        name: Operator name
        params: Parameters to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    schema = get_operator_schema(name)
    if schema is None:
        return False, [f"Unknown operator: {name}"]

    errors: list[str] = []

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in params:
            errors.append(f"Missing required field: {field}")

    # Check types
    properties = schema.get("properties", {})
    for field, value in params.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type and not _check_type(value, expected_type):
                errors.append(f"Field '{field}' has wrong type. Expected: {expected_type}")

    return len(errors) == 0, errors


def _check_type(value: Any, expected_type: str | list) -> bool:
    """Check if value matches expected type.

    Args:
        value: Value to check
        expected_type: Type name or list of type names

    Returns:
        True if type matches
    """
    if isinstance(expected_type, list):
        return any(_check_type(value, t) for t in expected_type)

    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "boolean": bool,
        "number": (int, float),
        "integer": int,
        "object": dict,
        "array": list,
        "null": type(None),
    }

    expected = type_map.get(expected_type)
    if expected is None:
        return True
    return isinstance(value, expected)


def build_operator_schemas() -> list[OperatorSchema]:
    """Build list of OperatorSchema objects for all registered operators.

    Returns:
        List of OperatorSchema objects
    """
    schemas: list[OperatorSchema] = []

    for name, schema in OPERATOR_SCHEMAS.items():
        category = _infer_category(name)
        schemas.append(OperatorSchema(
            name=name,
            display_name=_get_display_name(name),
            description=_get_description(name),
            category=category,
            param_schema=schema,
            input_types=_get_input_types(name),
            output_types=_get_output_types(name),
        ))

    return schemas


def _infer_category(operator_name: str) -> Literal[
    "binning", "scorecard", "weighted_sum", "decision_table",
    "llm_judge", "flag", "alert", "compute", "switch", "graph"
]:
    """Infer operator category from name."""
    name_lower = operator_name.lower()
    if "binning" in name_lower:
        return "binning"
    if "scorecard" in name_lower:
        return "scorecard"
    if "weighted" in name_lower:
        return "weighted_sum"
    if "decision" in name_lower:
        return "decision_table"
    if "llm" in name_lower or "judge" in name_lower:
        return "llm_judge"
    if "flag" in name_lower:
        return "flag"
    if "alert" in name_lower:
        return "alert"
    if "compute" in name_lower:
        return "compute"
    if "switch" in name_lower:
        return "switch"
    if "graph" in name_lower:
        return "graph"
    return "compute"


def _get_display_name(operator_name: str) -> str:
    """Get human-readable display name."""
    display_names = {
        "SET_FLAG": "Set Flag",
        "REJECT": "Reject",
        "APPROVE": "Approve",
        "COMPUTE": "Compute",
        "BINNING": "Binning",
        "SCORECARD": "Scorecard",
        "WEIGHTED_SUM": "Weighted Sum",
        "DECISION_TABLE": "Decision Table",
        "LLM_JUDGE": "LLM Judge",
        "TRIGGER_ALERT": "Trigger Alert",
        "SWITCH": "Switch",
    }
    return display_names.get(operator_name, operator_name)


def _get_description(operator_name: str) -> str:
    """Get operator description."""
    descriptions = {
        "SET_FLAG": "Set a boolean flag or variable to a specified value",
        "REJECT": "Reject the entity with a reason",
        "APPROVE": "Approve the entity",
        "COMPUTE": "Compute a formula and store the result",
        "BINNING": "Discretize a continuous value into bins with labels",
        "SCORECARD": "Calculate a score using variable-weighted points",
        "WEIGHTED_SUM": "Calculate weighted sum with optional grade multipliers",
        "DECISION_TABLE": "Make decision based on condition matrix",
        "LLM_JUDGE": "Use LLM for qualitative analysis with fallback",
        "TRIGGER_ALERT": "Trigger an alert with specified severity",
        "SWITCH": "Execute different operators based on variable value",
    }
    return descriptions.get(operator_name, "")


def _get_input_types(operator_name: str) -> list[str]:
    """Get supported input types for operator."""
    common = ["number", "string", "boolean", "array"]
    return common


def _get_output_types(operator_name: str) -> list[str]:
    """Get output types produced by operator."""
    name_lower = operator_name.lower()
    if "llm" in name_lower:
        return ["string", "object"]
    if "decision" in name_lower:
        return ["string", "object"]
    return ["number", "string", "boolean", "object"]
