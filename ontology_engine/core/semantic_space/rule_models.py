# ontology_engine/core/semantic_space/rule_models.py
"""Rule models for semantic space management - separates declaration from logic.

.. deprecated::
    The models in this module are being superseded by the V3 models in
    core.schema.models (RuleDefinitionDeclaration, RuleLogicDeclaration).
    They are retained for backward compatibility with existing JSON data files.
    Use to_v3_declaration() / to_v3_logic() to convert to the new models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import (
        RuleDefinitionDeclaration,
        RuleLogicDeclaration,
    )


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

    def to_v3_declaration(self) -> RuleDefinitionDeclaration:
        """Convert to V3 RuleDefinitionDeclaration model."""
        from ontology_engine.core.schema.models import (
            RuleDefinitionDeclaration,
            AppliesToDecl,
            IOElementDecl,
        )

        fact_objects = [t.concept for t in self.target_objects]
        categories = {}
        if self.applicable_scope.scope_type == "by_classification":
            path = self.applicable_scope.classification_path or ""
            for val in self.applicable_scope.classification_values:
                categories[path] = val

        return RuleDefinitionDeclaration(
            id=self.id,
            name=self.name or self.id,
            description=self.description,
            rule_type=self.rule_type,
            priority=self.priority,
            applies_to=AppliesToDecl(
                fact_objects=fact_objects,
                categories=categories,
            ),
            inputs=[
                IOElementDecl(name=i.name, type=i.element_type)
                for i in self.input_elements
            ],
            outputs=[
                IOElementDecl(name=o.name, type=o.element_type)
                for o in self.output_elements
            ],
            logic_ids=self.logic_ids,
            enabled=self.enabled,
        )


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

    def to_v3_logic(self) -> RuleLogicDeclaration:
        """Convert to V3 RuleLogicDeclaration model."""
        from ontology_engine.core.schema.models import (
            RuleLogicDeclaration,
            StepDeclaration,
            StepCondition,
            StepAction,
        )

        steps = []
        if self.when and (self.then_action or self.else_action):
            condition = None
            if self.when.expression:
                condition = StepCondition(expression=self.when.expression)
            elif self.when.allOf:
                condition = StepCondition(and_=self.when.allOf)
            elif self.when.anyOf:
                condition = StepCondition(or_=self.when.anyOf)

            then_step_action = None
            if self.then_action:
                then_step_action = StepAction(
                    type=self.then_action.action_type,
                    output=self.then_action.output,
                    formula=self.then_action.formula,
                    operator=self.then_action.operator,
                )

            else_step_action = None
            if self.else_action:
                else_step_action = StepAction(
                    type=self.else_action.action_type,
                    output=self.else_action.output,
                    formula=self.else_action.formula,
                    operator=self.else_action.operator,
                )

            steps.append(StepDeclaration(
                id=f"{self.id}_step1",
                name=self.name or self.id,
                condition=condition,
                action=then_step_action,
                else_action=else_step_action,
            ))

        return RuleLogicDeclaration(
            id=self.id,
            name=self.name or self.id,
            definition_ref=self.definition_id,
            steps=steps,
            version=self.version,
        )


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
