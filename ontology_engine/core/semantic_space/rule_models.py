# ontology_engine/core/semantic_space/rule_models.py
"""Rule models for semantic space management - separates declaration from logic."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class TargetObject(BaseModel):
    """Defines what objects a rule operates on."""
    concept: str  # e.g., "Supplier", "Invoice"
    filters: dict[str, Any] | None = None  # e.g., {"status": "ACTIVE"}


class InputElement(BaseModel):
    """Defines an input element (metric, attribute, relation)."""
    name: str  # e.g., "credit_score", "registered_capital"
    element_type: Literal["metric", "attribute", "relation", "computed"]
    source: str | None = None  # For metrics: which metric definition
    path: str | None = None  # e.g., "registered_capital.value"
    required: bool = True


class OutputElement(BaseModel):
    """Defines an output element."""
    name: str  # e.g., "eligible", "credit_limit"
    element_type: str  # e.g., "boolean", "Money", "RiskScore"
    destination: Literal["entity_attribute", "computed_metric", "alert"] = "computed_metric"


class ApplicableScope(BaseModel):
    """
    Rule applicable scope.

    Defines whether a rule applies globally to all entities,
    or only to entities matching specific classifications.
    """
    scope_type: Literal["global", "by_classification"] = "global"
    # For by_classification: e.g., "industry_type/TECHNOLOGY"
    classification_path: str | None = None
    # Classification values: e.g., ["TECHNOLOGY", "MANUFACTURING"]
    classification_values: list[str] = Field(default_factory=list)


class RuleDefinition(BaseModel):
    """
    Rule declaration - WHAT the rule operates on.

    Defines:
    - Target objects (WHAT entities to operate on)
    - Input elements (WHAT data it reads)
    - Output elements (WHAT data it produces)
    - Applicable scope (GLOBAL or BY classification)
    - Backward compatibility: may contain inline when/then (v1 format)

    Does NOT define HOW the logic is implemented - that's in RuleLogic.
    """
    id: str  # e.g., "R001_basic_eligibility"
    name: str | None = None
    description: str | None = None

    # Rule type classification
    rule_type: Literal["constraint", "inference", "alert", "decision"] = "constraint"
    priority: int = 100

    # Applicable scope
    applicable_scope: ApplicableScope = Field(default_factory=lambda: ApplicableScope())

    # Target objects - WHAT entities this rule operates on
    target_objects: list[TargetObject] = Field(default_factory=list)

    # Input elements - WHAT data this rule reads
    input_elements: list[InputElement] = Field(default_factory=list)

    # Output elements - WHAT data this rule produces
    output_elements: list[OutputElement] = Field(default_factory=list)

    # Enabled state
    enabled: bool = True

    # External logic references (new format)
    # Points to RuleLogic.id values
    logic_ids: list[str] = Field(default_factory=list)

    # --- Backward compatibility (v1 inline format) ---
    # When logic_ids is empty, these fields provide the default logic
    when: RuleWhen | None = None
    then_action: RuleAction | None = None
    else_action: RuleAction | None = None


class ApplicableCondition(BaseModel):
    """
    Logic applicable condition - specifies when this logic variant applies.

    A RuleLogic can have multiple ApplicableConditions,
    each with different classification requirements.
    """
    # Classification requirements (e.g., {"industry_type": "TECHNOLOGY"})
    # Empty/None means no classification requirement (matches all)
    classification: dict[str, str] | None = None
    # Match type: "exact" (default), "in" (value in list), "all" (all must match)
    match_type: Literal["exact", "in", "all"] = "exact"


class RuleWhen(BaseModel):
    """Trigger condition for a rule."""
    expression: str | None = None  # e.g., "status == 'ACTIVE'"
    allOf: list[dict] | None = None  # AND logic
    anyOf: list[dict] | None = None  # OR logic


class RuleAction(BaseModel):
    """Rule action to execute when condition is met."""
    action_type: str  # "set_flag", "compute", "reject", "approve", "alert"
    output: dict | None = None  # e.g., {"eligible": true}
    formula: str | None = None  # e.g., "credit_score * 0.8"
    operator: str | None = None  # e.g., "SWITCH", "SCORECARD"


class RuleLogic(BaseModel):
    """
    Rule logic implementation - HOW the rule is actually executed.

    Contains:
    - The actual when condition (expression or allOf/anyOf)
    - The then/else actions
    - Applicable conditions (which classification scenarios this logic applies to)
    - Operator bindings for complex computations

    One RuleDefinition can have multiple RuleLogics for different scenarios.
    """
    id: str  # e.g., "R001_logic_v1", "R001_logic_by_industry"
    name: str | None = None

    # Link to declaration
    definition_id: str  # References RuleDefinition.id

    # Applicable conditions - which scenarios this logic applies to
    applicable_conditions: list[ApplicableCondition] = Field(default_factory=list)

    # Trigger condition (when)
    when: RuleWhen | None = None

    # Execution action (then)
    then_action: RuleAction | None = None

    # Else action (optional)
    else_action: RuleAction | None = None

    # Version for tracking
    version: int = 1

    # Environment (for multi-environment support)
    environment: str = "default"


# Re-export
__all__ = [
    "TargetObject",
    "InputElement",
    "OutputElement",
    "ApplicableScope",
    "RuleDefinition",
    "ApplicableCondition",
    "RuleWhen",
    "RuleAction",
    "RuleLogic",
]
