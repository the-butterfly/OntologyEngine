"""KGML Schema data models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


# ============== KGML Schema (Complete) ==============


class KGMLSchema(BaseModel):
    metadata: SchemaMetadata
    types: list[TypeDefinition] = Field(default_factory=list)
    enums: list[EnumDefinition] = Field(default_factory=list)
    concepts: list[ConceptDefinition] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)
    rules: RulesDefinition | None = None

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
