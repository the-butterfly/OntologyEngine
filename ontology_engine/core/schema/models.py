"""KGML Schema data models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ============== Metadata ==============


class SchemaMetadata(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    schema_version: str = "3.0"
    domain: str | None = None


# ============== Types ==============


class TypeProperty(BaseModel):
    type: str
    description: str | None = None
    default: Any = None


class TypeDefinition(BaseModel):
    name: str
    description: str | None = None
    base_type: str  # "object", "string", "decimal", "integer", "float", "boolean", "date"
    properties: dict[str, TypeProperty] | None = None
    min: float | None = None
    max: float | None = None
    enum: list[str] | None = None


# ============== Enums ==============


class EnumValue(BaseModel):
    id: str
    label: str | None = None
    weight: float | None = None
    severity_score: int | None = None


class EnumDefinition(BaseModel):
    name: str
    description: str | None = None
    values: list[EnumValue] = Field(default_factory=list)


# ============== Concepts ==============


class AttributeDefinition(BaseModel):
    name: str
    type: str
    required: bool = False
    unique: bool = False
    default: Any = None
    description: str | None = None
    validation: dict | None = None
    enum: list[str] | None = None  # For enum types
    value_domain: ValueDomain | None = None


class RelationDefinition(BaseModel):
    name: str
    target: str  # Target concept name
    cardinality: str = "0..*"  # "1", "0..1", "0..*", "1..*"
    description: str | None = None
    inverse: str | None = None  # Inverse relation name


class ConceptDefinition(BaseModel):
    name: str
    description: str | None = None
    category: Literal["entity", "relation"] = "entity"
    attributes: list[AttributeDefinition] = Field(default_factory=list)
    relations: list[RelationDefinition] = Field(default_factory=list)


# ============== Rules ==============


# ============== Canonical Rule Step (L4 DAG execution) ==============


class RuleStep(BaseModel):
    """L4 Rule execution step for DAG-based rule logic (canonical grammar).

    Canonical: steps[]. Each step has id/priority/depends_on/condition/action/operator.
    """
    id: str
    name: str | None = None
    description: str | None = None
    priority: int = 100  # execution order when no depends_on
    depends_on: list[str] = Field(default_factory=list)  # step IDs this depends on
    condition: RuleWhen | None = None  # step-level precondition
    action: str | None = None  # operator name to invoke
    operator: str | None = None  # operator name (canonical alias for action)
    computation: dict | None = None  # formula to compute
    output_field: str | None = None  # which computed_metrics key this step produces
    enabled: bool = True


# ============== Rule Models (v1 + canonical v2) ==============


class RuleDimension(BaseModel):
    name: str
    description: str | None = None
    applicable_entities: list[str] = Field(default_factory=list)


class RuleWhen(BaseModel):
    expression: str | None = None
    allOf: list[dict] | None = None
    anyOf: list[dict] | None = None


class RuleThen(BaseModel):
    action: str | None = None
    output: dict | None = None
    computation: dict | None = None


class RuleDefinition(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    type: str = "constraint"  # "constraint", "inference", "alert", "decision"
    priority: int = 100
    enabled: bool = True
    scope: dict | None = None
    when: RuleWhen | None = None
    then: RuleThen | None = None
    else_: dict | None = Field(default=None, alias="else")
    # ADR-008: Forward compatibility for rule_definitions + rule_logics separation
    # When logic_ids is non-empty, executor should use external RuleLogic objects
    logic_ids: list[str] = Field(default_factory=list)


class RulesDefinition(BaseModel):
    rule_dimensions: list[RuleDimension] = Field(default_factory=list)
    ruleset: list[RuleDefinition] = Field(default_factory=list)


# ============== Metrics (Simplified) ==============


class MetricDefinition(BaseModel):
    name: str
    description: str | None = None
    type: str | None = None  # "atomic", "derived", "composite"
    scope: str | None = None  # Concept name
    formula: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    # ADR-007: L3/L4 computation boundary
    standard_formula: str | None = None  # Optional standard formula (declaration)
    overridable: bool = False  # If True, L4 can override standard_formula


# ============== V2 Models: Fact Objects (L1) ==============


class FactObjectEntity(BaseModel):
    """L1 Entity definition in v2 format."""
    id: str
    name: str | None = None
    description: str | None = None
    attributes: list[AttributeDefinition] = Field(default_factory=list)
    relations: list[RelationDefinition] = Field(default_factory=list)


class FactObjects(BaseModel):
    """L1 Fact Objects container."""
    shared_types: list[TypeDefinition] = Field(default_factory=list)
    enums: list[EnumDefinition] = Field(default_factory=list)
    entities: list[FactObjectEntity] = Field(default_factory=list)
    relations: list[RelationDefinition] = Field(default_factory=list)


# ============== Value Domain ==============


class ValueDomain(BaseModel):
    """Value domain declaration for attribute/metric values."""
    type: str = "continuous"  # continuous, discrete, enum, score_grade, money_range
    name: str | None = None
    description: str | None = None
    # continuous
    min: Any = None
    max: Any = None
    step: float | None = None
    unit: str | None = None
    # discrete / tags
    values: list[dict[str, Any]] = Field(default_factory=list)
    # enum
    enum_ref: str | None = None
    # score_grade
    grades: list[dict[str, Any]] = Field(default_factory=list)
    default_grade: str | None = None
    # money_range
    currency: str | None = None
    ranges: list[dict[str, Any]] = Field(default_factory=list)


class CategoryValueDefinition(BaseModel):
    """Category value definition."""
    id: str
    label: str
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    sort_order: int = 0
    color: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # hierarchical extension
    level: int | None = None
    parent_id: str | None = None
    children: list["CategoryValueDefinition"] = Field(default_factory=list)


class CategoryValueDomain(BaseModel):
    """Category value domain definition."""
    type: Literal["discrete", "enum", "hierarchical", "tags"] = "discrete"
    values: list[CategoryValueDefinition] = Field(default_factory=list)
    enum_ref: str | None = None


class DimensionApplicability(BaseModel):
    """Dimension applicability to object types."""
    object_type: str
    required: bool = False
    auto_categorize: bool = True
    auto_dimension: dict[str, Any] | None = None


class RuleOverride(BaseModel):
    """Rule override by category."""
    rule_id: str
    override_field: str
    override_value: Any


class RuleApplicabilityMapping(BaseModel):
    """Category value to rule applicability mapping."""
    dimension_value: str
    applicable_rule_groups: list[str] = Field(default_factory=list)
    excluded_rule_groups: list[str] = Field(default_factory=list)
    rule_overrides: list[RuleOverride] = Field(default_factory=list)


class CategorizationRuleset(BaseModel):
    """Ruleset for derived categorization."""
    id: str
    name: str | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list)


# ============== V2 Models: Categorization (L2) ==============


class CategorizationDimension(BaseModel):
    """L2 Categorization dimension (enhanced)."""
    id: str
    name: str | None = None
    description: str | None = None
    type: str = "flat"  # hierarchical, flat, derived, tags
    value_domain: CategoryValueDomain | None = None
    multi_select: bool = False
    applicable_to: list[DimensionApplicability | str] = Field(default_factory=list)
    ruleset: CategorizationRuleset | None = None
    rule_applicability: list[RuleApplicabilityMapping] = Field(default_factory=list)
    triggers: list[dict] = Field(default_factory=list)


class Categorizations(BaseModel):
    """L2 Categorizations container."""
    dimensions: list[CategorizationDimension] = Field(default_factory=list)


# ============== V2 Models: Analytical Elements (L3) ==============


class MetricSource(BaseModel):
    """Metric source definition."""
    type: str  # "fact_attribute", "graph_traversal", "external_api", "constant"
    entity: str | None = None
    attribute: str | None = None
    traversal: str | None = None
    aggregate: str | None = None
    filter: str | None = None
    provider: str | None = None


class MetricComponent(BaseModel):
    """Component for composite metrics."""
    metric: str
    weight: float = 1.0
    transform: str | None = None


class GraphAlgorithmDefinition(BaseModel):
    """Structured graph algorithm definition."""
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class MetricDefinitionV2(BaseModel):
    """L3 Metric definition in v2 format.

    Canonical field names: id, name, type (not element_type), source,
    dependencies, formula, unit, range, default, thresholds,
    overridable, components, algorithm, traversal, neighbor_filter,
    value_domain, expression_domain.
    """
    id: str
    name: str | None = None
    description: str | None = None
    # Canonical field name is 'type'; 'element_type' accepted for backward compat
    type: str = "atomic"  # "atomic", "derived", "composite", "graph"
    source: MetricSource | None = None
    dependencies: list[str] = Field(default_factory=list)
    formula: str | None = None
    unit: str | None = None
    range: tuple[float, float] | None = None
    default: Any = None
    thresholds: dict | None = None
    overridable: bool = False
    components: list[MetricComponent] | None = None
    algorithm: GraphAlgorithmDefinition | str | None = None
    traversal: dict | None = None
    neighbor_filter: str | None = None
    value_domain: ValueDomain | None = None
    expression_domain: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_element_type(cls, data):
        """Normalize 'element_type' → 'type' for backward compatibility."""
        if isinstance(data, dict):
            if "element_type" in data and "type" not in data:
                data = dict(data)
                data["type"] = data.pop("element_type")
        return data

    @model_validator(mode="before")
    @classmethod
    def _normalize_algorithm(cls, data):
        """Normalize string algorithm to GraphAlgorithmDefinition."""
        if isinstance(data, dict) and isinstance(data.get("algorithm"), str):
            data = dict(data)
            data["algorithm"] = {"name": data["algorithm"], "params": {}}
        return data

    @model_validator(mode="after")
    def _derive_composite_dependencies(self) -> "MetricDefinitionV2":
        """Auto-derive dependencies for composite metrics from components."""
        if self.type == "composite" and self.components:
            expected = [c.metric for c in self.components]
            if self.dependencies and set(self.dependencies) != set(expected):
                raise ValueError(
                    f"Metric '{self.id}' dependencies {self.dependencies} "
                    f"do not match components {expected}"
                )
            self.dependencies = expected
        return self


class IndicatorDefinition(BaseModel):
    """L3 Indicator definition.

    Canonical field name is 'type' (not element_type).
    """
    id: str
    name: str | None = None
    description: str | None = None
    type: str = "atomic"  # canonical: "atomic", "derived"
    source: MetricSource | None = None
    dependencies: list[str] = Field(default_factory=list)
    formula: str | None = None
    output_type: str = "boolean"
    overridable: bool = False
    value_domain: ValueDomain | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_element_type(cls, data):
        if isinstance(data, dict):
            if "element_type" in data and "type" not in data:
                data = dict(data)
                data["type"] = data.pop("element_type")
        return data


class ScorecardDefinition(BaseModel):
    """L3 Scorecard definition.

    Canonical field name is 'type' (not element_type).
    """
    id: str
    name: str | None = None
    description: str | None = None
    type: str = "derived"  # canonical field name
    dependencies: list[str] = Field(default_factory=list)
    formula: str | None = None
    output_type: str = "string"
    overridable: bool = False
    value_domain: ValueDomain | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_element_type(cls, data):
        if isinstance(data, dict):
            if "element_type" in data and "type" not in data:
                data = dict(data)
                data["type"] = data.pop("element_type")
        return data


class AnalyticalElements(BaseModel):
    """L3 Analytical Elements container."""
    metrics: list[MetricDefinitionV2] = Field(default_factory=list)
    indicators: list[IndicatorDefinition] = Field(default_factory=list)
    scorecards: list[ScorecardDefinition] = Field(default_factory=list)


# ============== V2 Models: Business Logic (L4) ==============


class RuleDefinitionV2(BaseModel):
    """L4 Rule definition in v2 format.

    Canonical field names: id, name, description, rule_type, priority,
    applies_to (not target_objects), inputs/outputs (not input/output_elements),
    preconditions, logic_ids, enabled.

    L4 canonical structure uses rule_definitions + rule_logics separation
    (ADR-008). rule_definitions provides applies_to + preconditions contract,
    rule_logics provides the actual execution steps (steps[] with depends_on).
    """
    id: str
    name: str | None = None
    description: str | None = None
    rule_type: str = "constraint"  # "constraint", "inference", "alert", "decision"
    priority: int = 100
    applies_to: list[str] = Field(default_factory=list)  # canonical: entity ids this applies to
    applicable_categorizations: list[str] = Field(default_factory=list)
    inputs: list[dict] = Field(default_factory=list)  # canonical field name
    outputs: list[dict] = Field(default_factory=list)  # canonical field name
    preconditions: list[dict] = Field(default_factory=list)  # canonical: rule-level preconditions
    enabled: bool = True
    logic_ids: list[str] = Field(default_factory=list)  # references to RuleLogic instances

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data):
        """Normalize legacy field names to canonical."""
        if isinstance(data, dict):
            if "target_objects" in data and "applies_to" not in data:
                data = dict(data)
                data["applies_to"] = data.pop("target_objects")
            if "input_elements" in data and "inputs" not in data:
                data = dict(data)
                data["inputs"] = data.pop("input_elements")
            if "output_elements" in data and "outputs" not in data:
                data = dict(data)
                data["outputs"] = data.pop("output_elements")
        return data


class RuleLogic(BaseModel):
    """L4 Rule logic instance.

    Canonical grammar supports two execution models:
    1. Legacy: when + then_action + else_action (simple conditional)
    2. DAG: steps[] with depends_on for complex rule chains

    When steps[] is non-empty, executor should use DAG-based execution.
    Each step has: id/priority/depends_on/condition/action/operator/computation.
    """
    id: str
    name: str | None = None
    definition_id: str
    applicable_conditions: list[dict] = Field(default_factory=list)
    # Legacy simple execution model
    when: RuleWhen | None = None
    then_action: RuleAction | None = None
    else_action: RuleAction | None = None
    # Canonical DAG execution model
    steps: list[RuleStep] = Field(default_factory=list)
    priority: int = 100
    version: int = 1
    environment: str = "default"


class RuleAction(BaseModel):
    """Rule action."""
    action_type: str | None = None
    output: dict | None = None
    computation: dict | None = None


class BusinessLogic(BaseModel):
    """L4 Business Logic container."""
    rule_definitions: list[RuleDefinitionV2] = Field(default_factory=list)
    rule_logics: list[RuleLogic] = Field(default_factory=list)


# ============== KGML Schema (Complete) ==============


class KGMLSchema(BaseModel):
    metadata: SchemaMetadata
    schema_version: str = "1.0"

    # V1 format fields
    types: list[TypeDefinition] = Field(default_factory=list)
    enums: list[EnumDefinition] = Field(default_factory=list)
    concepts: list[ConceptDefinition] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)
    rules: RulesDefinition | None = None

    # V2 format fields
    fact_objects: FactObjects | None = None
    categorizations: Categorizations | None = None
    analytical_elements: AnalyticalElements | None = None
    business_logic: BusinessLogic | None = None

    def get_concept(self, name: str) -> ConceptDefinition | None:
        return next((c for c in self.concepts if c.name == name), None)

    def get_enum(self, name: str) -> EnumDefinition | None:
        return next((e for e in self.enums if e.name == name), None)

    def get_type(self, name: str) -> TypeDefinition | None:
        return next((t for t in self.types if t.name == name), None)

    def get_rules_for_dimension(self, dimension: str) -> list[RuleDefinition]:
        if not self.rules:
            return []
        return [
            r for r in self.rules.ruleset
            if dimension in (r.scope.get("dimensions", []) if r.scope else [])
        ]

    def is_v2_format(self) -> bool:
        """Check if this schema uses v2 format."""
        return self.fact_objects is not None or self.schema_version == "2.0"

    def get_all_metrics(self) -> list[MetricDefinitionV2]:
        """Get all metrics from v2 analytical_elements or convert v1 metrics."""
        if self.analytical_elements:
            return self.analytical_elements.metrics
        # Fallback: convert v1 metrics to v2 format
        return []

    def get_all_rule_definitions(self) -> list[RuleDefinitionV2]:
        """Get all rule definitions from v2 business_logic."""
        if self.business_logic:
            return self.business_logic.rule_definitions
        return []

    def get_all_rule_logics(self) -> list[RuleLogic]:
        """Get all rule logics from v2 business_logic."""
        if self.business_logic:
            return self.business_logic.rule_logics
        return []

    def get_entity_id_field(self, concept_name: str) -> str | None:
        """Discover the ID field for a concept from schema declarations.

        Strategy:
        1. Find the unique+required attribute in the concept definition
        2. Search in fact_objects.relations (for relation objects like GuaranteeRelation)
        3. Convention fallback: {concept_lower}_id or {concept_lower}_no

        Args:
            concept_name: The concept/fact_object/relation_object name

        Returns:
            The ID field name, or None if not discoverable
        """
        concept = self.get_concept(concept_name)
        if concept:
            for attr in concept.attributes:
                if attr.unique and attr.required:
                    return attr.name
            for attr in concept.attributes:
                if attr.unique:
                    return attr.name

        if self.fact_objects and self.fact_objects.relations:
            for rel_def in self.fact_objects.relations:
                if rel_def.name == concept_name:
                    name = concept_name
                    if name.endswith("Relation"):
                        base = name[:-8].lower()
                        return f"{base}_id"
                    lower = concept_name.lower()
                    return f"{lower}_id"

        lower = concept_name.lower()
        convention_candidates = [f"{lower}_id", f"{lower}_no"]
        if concept:
            attr_names = {a.name for a in concept.attributes}
            for candidate in convention_candidates:
                if candidate in attr_names:
                    return candidate

        return None

    def get_all_concept_names(self) -> list[str]:
        """Get all concept/fact_object names from schema."""
        return [c.name for c in self.concepts]

    def get_relation_names_for_concept(self, concept_name: str) -> list[str]:
        """Get all relation names declared for a concept."""
        concept = self.get_concept(concept_name)
        if concept:
            return [r.name for r in concept.relations]
        return []

    def get_first_relation_name(self) -> str | None:
        """Get the first relation name from any concept, for default fallback."""
        for concept in self.concepts:
            if concept.relations:
                return concept.relations[0].name
        return None

    def to_space_layers_dict(self) -> dict:
        """Convert KGMLSchema to dict format compatible with SemanticSpaceLayers.

        This converts v2 structured objects to dict format for storage in
        SemanticSpace. Works with both v1 and v2 schema formats.

        Returns:
            Dict with keys: L1_fact_objects, L2_categorizations,
            L3_analytical_elements, L4_business_logic
        """
        # L1: Fact Objects
        l1_fact_objects = []
        if self.fact_objects and self.fact_objects.entities:
            for entity in self.fact_objects.entities:
                l1_fact_objects.append({
                    "id": entity.id,
                    "name": entity.name,
                    "description": entity.description,
                    "properties": [
                        {
                            "name": attr.name,
                            "type": attr.type,
                            "required": attr.required,
                            "unique": attr.unique,
                            "default": attr.default,
                            "description": attr.description,
                            "validation": attr.validation,
                            "enum": attr.enum,
                        }
                        for attr in entity.attributes
                    ],
                    "relations": [
                        {
                            "name": rel.name,
                            "target": rel.target,
                            "cardinality": rel.cardinality,
                            "description": rel.description,
                            "inverse": rel.inverse,
                        }
                        for rel in entity.relations
                    ],
                })
        elif self.concepts:
            # Fallback to v1 concepts format
            for concept in self.concepts:
                l1_fact_objects.append({
                    "id": concept.name,
                    "name": concept.name,
                    "description": concept.description,
                    "properties": [
                        {
                            "name": attr.name,
                            "type": attr.type,
                            "required": attr.required,
                            "unique": attr.unique,
                            "default": attr.default,
                            "description": attr.description,
                            "validation": attr.validation,
                            "enum": attr.enum,
                        }
                        for attr in concept.attributes
                    ],
                    "relations": [
                        {
                            "name": rel.name,
                            "target": rel.target,
                            "cardinality": rel.cardinality,
                            "description": rel.description,
                            "inverse": rel.inverse,
                        }
                        for rel in concept.relations
                    ],
                })

        # L2: Categorizations
        l2_categorizations = []
        if self.categorizations and self.categorizations.dimensions:
            for dim in self.categorizations.dimensions:
                cat_dict: dict[str, Any] = {
                    "id": dim.id,
                    "name": dim.name,
                    "description": dim.description,
                    "type": dim.type,
                    "multi_select": dim.multi_select,
                    "triggers": dim.triggers,
                }
                # Serialize applicable_to (can be str or DimensionApplicability)
                if dim.applicable_to:
                    serialized_at = []
                    for item in dim.applicable_to:
                        if isinstance(item, str):
                            serialized_at.append(item)
                        else:
                            serialized_at.append(item.model_dump())
                    cat_dict["applicable_to"] = serialized_at
                # Serialize value_domain
                if dim.value_domain:
                    cat_dict["value_domain"] = dim.value_domain.model_dump()
                # Serialize ruleset
                if dim.ruleset:
                    cat_dict["ruleset"] = dim.ruleset.model_dump()
                # Serialize rule_applicability
                if dim.rule_applicability:
                    cat_dict["rule_applicability"] = [
                        ra.model_dump() for ra in dim.rule_applicability
                    ]
                l2_categorizations.append(cat_dict)

        # L3: Analytical Elements
        l3_analytical_elements: list[dict[str, Any]] = []
        if self.analytical_elements:
            # Metrics
            for metric in self.analytical_elements.metrics:
                elem = {
                    "id": metric.id,
                    "name": metric.name,
                    "description": metric.description,
                    "type": metric.type,  # canonical field name
                    "dependencies": metric.dependencies,
                    "formula": metric.formula,
                    "unit": metric.unit,
                    "range": list(metric.range) if metric.range else None,
                    "default": metric.default,
                    "thresholds": metric.thresholds,
                    "overridable": metric.overridable,
                    "value_domain": metric.value_domain.model_dump() if metric.value_domain else None,
                    "expression_domain": metric.expression_domain,
                }
                if metric.source:
                    elem["source"] = {
                        "type": metric.source.type,
                        "entity": metric.source.entity,
                        "attribute": metric.source.attribute,
                        "traversal": metric.source.traversal,
                        "aggregate": metric.source.aggregate,
                        "filter": metric.source.filter,
                        "provider": metric.source.provider,
                    }
                if metric.components:
                    elem["components"] = [
                        {"metric": c.metric, "weight": c.weight, "transform": c.transform}
                        for c in metric.components
                    ]
                l3_analytical_elements.append(elem)
            # Indicators
            for indicator in self.analytical_elements.indicators:
                elem = {
                    "id": indicator.id,
                    "name": indicator.name,
                    "description": indicator.description,
                    "type": indicator.type,  # canonical field name
                    "output_type": indicator.output_type,
                    "overridable": indicator.overridable,
                }
                if indicator.source:
                    elem["source"] = {
                        "type": indicator.source.type,
                        "entity": indicator.source.entity,
                        "attribute": indicator.source.attribute,
                    }
                l3_analytical_elements.append(elem)
            # Scorecards
            for scorecard in self.analytical_elements.scorecards:
                l3_analytical_elements.append({
                    "id": scorecard.id,
                    "name": scorecard.name,
                    "description": scorecard.description,
                    "type": scorecard.type,  # canonical field name
                    "dependencies": scorecard.dependencies,
                    "formula": scorecard.formula,
                    "output_type": scorecard.output_type,
                    "overridable": scorecard.overridable,
                })
        elif self.metrics:
            # Fallback to v1 metrics format
            for metric_v1 in self.metrics:
                l3_analytical_elements.append({
                    "id": metric_v1.name,
                    "name": metric_v1.name,
                    "description": metric_v1.description,
                    "type": "derived" if metric_v1.formula else "atomic",
                    "formula": metric_v1.formula,
                    "dependencies": metric_v1.dependencies,
                })

        # L4: Business Logic
        l4_rule_definitions = []
        l4_rule_logics = []
        if self.business_logic:
            for rd in self.business_logic.rule_definitions:
                l4_rule_definitions.append({
                    "id": rd.id,
                    "name": rd.name,
                    "description": rd.description,
                    "rule_type": rd.rule_type,
                    "priority": rd.priority,
                    "applies_to": rd.applies_to,  # canonical field name
                    "applicable_categorizations": rd.applicable_categorizations,
                    "inputs": rd.inputs,  # canonical field name
                    "outputs": rd.outputs,  # canonical field name
                    "preconditions": rd.preconditions,  # canonical field name
                    "enabled": rd.enabled,
                    "logic_ids": rd.logic_ids,
                })
            for rl in self.business_logic.rule_logics:
                logic_dict: dict[str, Any] = {
                    "id": rl.id,
                    "name": rl.name,
                    "definition_id": rl.definition_id,
                    "applicable_conditions": rl.applicable_conditions,
                    "priority": rl.priority,
                    "version": rl.version,
                    "environment": rl.environment,
                }
                if rl.when:
                    logic_dict["when"] = {
                        "expression": rl.when.expression,
                        "allOf": rl.when.allOf,
                        "anyOf": rl.when.anyOf,
                    }
                if rl.then_action:
                    logic_dict["then_action"] = {
                        "action_type": rl.then_action.action_type,
                        "output": rl.then_action.output,
                        "computation": rl.then_action.computation,
                    }
                if rl.else_action:
                    logic_dict["else_action"] = {
                        "action_type": rl.else_action.action_type,
                        "output": rl.else_action.output,
                        "computation": rl.else_action.computation,
                    }
                # Canonical DAG steps[]
                if rl.steps:
                    logic_dict["steps"] = [
                        {
                            "id": s.id,
                            "name": s.name,
                            "description": s.description,
                            "priority": s.priority,
                            "depends_on": s.depends_on,
                            "condition": {
                                "expression": s.condition.expression if s.condition else None,
                                "allOf": s.condition.allOf if s.condition else None,
                                "anyOf": s.condition.anyOf if s.condition else None,
                            } if s.condition else None,
                            "action": s.action or s.operator,
                            "computation": s.computation,
                            "output_field": s.output_field,
                            "enabled": s.enabled,
                        }
                        for s in rl.steps
                    ]
                l4_rule_logics.append(logic_dict)

        return {
            "L1_fact_objects": l1_fact_objects,
            "L2_categorizations": l2_categorizations,
            "L3_analytical_elements": l3_analytical_elements,
            "L4_business_logic": {
                "rule_definitions": l4_rule_definitions,
                "rule_logics": l4_rule_logics,
            },
        }
