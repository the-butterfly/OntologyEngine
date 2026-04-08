from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from ontology_engine.core.schema.models import (
    KGMLSchema,
    SchemaMetadata,
    TypeDefinition,
    TypeProperty,
    EnumDefinition,
    EnumValue,
    ConceptDefinition,
    AttributeDefinition,
    RelationDefinition,
    RuleDefinition,
    RulesDefinition,
    RuleDimension,
    MetricDefinition,
    RuleWhen,
    RuleThen,
)


class SchemaValidationError(Exception):
    """Schema validation error"""
    pass


class SchemaLoader:
    """KGML Schema loader from YAML files."""

    def load(self, path: str | Path) -> KGMLSchema:
        """Load KGML schema from YAML file.

        Args:
            path: Path to schema.yaml file

        Returns:
            KGMLSchema object

        Raises:
            FileNotFoundError: If schema file doesn't exist
            SchemaValidationError: If schema is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not raw:
            raise SchemaValidationError("Schema file is empty")

        return self._parse(raw)

    def _parse(self, raw: dict[str, Any]) -> KGMLSchema:
        """Parse raw YAML dict into KGMLSchema."""
        return KGMLSchema(
            metadata=self._parse_metadata(raw.get("metadata", {})),
            types=self._parse_types(raw.get("types", [])),
            enums=self._parse_enums(raw.get("enums", [])),
            concepts=self._parse_concepts(raw.get("concepts", [])),
            metrics=self._parse_metrics(raw.get("metrics", [])),
            rules=self._parse_rules(raw.get("rules")),
        )

    def _parse_metadata(self, raw: dict) -> SchemaMetadata:
        """Parse metadata section."""
        return SchemaMetadata(
            id=raw.get("id", ""),
            name=raw.get("name"),
            description=raw.get("description"),
            version=raw.get("version", "1.0.0"),
            schema_version=raw.get("schema_version", "3.0"),
            domain=raw.get("domain"),
        )

    def _parse_types(self, raw: list) -> list[TypeDefinition]:
        """Parse types section."""
        types = []
        for t in raw:
            props = {}
            for name, prop in t.get("properties", {}).items():
                props[name] = TypeProperty(
                    type=prop.get("type", "string"),
                    description=prop.get("description"),
                    default=prop.get("default"),
                )
            types.append(TypeDefinition(
                name=t["name"],
                description=t.get("description"),
                base_type=t.get("base_type", "object"),
                properties=props or None,
                min=t.get("min"),
                max=t.get("max"),
                enum=t.get("enum"),
            ))
        return types

    def _parse_enums(self, raw: list) -> list[EnumDefinition]:
        """Parse enums section."""
        enums = []
        for e in raw:
            values = [EnumValue(
                id=v["id"],
                label=v.get("label"),
                weight=v.get("weight"),
                severity_score=v.get("severity_score"),
            ) for v in e.get("values", [])]
            enums.append(EnumDefinition(
                name=e["name"],
                description=e.get("description"),
                values=values,
            ))
        return enums

    def _parse_concepts(self, raw: list) -> list[ConceptDefinition]:
        """Parse concepts section."""
        concepts = []
        for c in raw:
            attributes = [
                AttributeDefinition(
                    name=a["name"],
                    type=a["type"],
                    required=a.get("required", False),
                    unique=a.get("unique", False),
                    default=a.get("default"),
                    description=a.get("description"),
                    validation=a.get("validation"),
                    enum=a.get("enum"),
                )
                for a in c.get("attributes", [])
            ]

            relations = [
                RelationDefinition(
                    name=r["name"],
                    target=r["target"],
                    cardinality=r.get("cardinality", "0..*"),
                    description=r.get("description"),
                    inverse=r.get("inverse"),
                )
                for r in c.get("relations", [])
            ]

            concepts.append(ConceptDefinition(
                name=c["name"],
                description=c.get("description"),
                category=c.get("category", "entity"),
                attributes=attributes,
                relations=relations,
            ))
        return concepts

    def _parse_metrics(self, raw: list) -> list[MetricDefinition]:
        """Parse metrics section."""
        metrics = []
        for m in raw:
            metrics.append(MetricDefinition(
                name=m["name"],
                description=m.get("description"),
                type=m.get("type") or m.get("metric_type"),
                scope=m.get("scope"),
                formula=m.get("formula"),
                dependencies=m.get("dependencies", []),
            ))
        return metrics

    def _parse_rules(self, raw: dict | None) -> RulesDefinition | None:
        """Parse rules section."""
        if not raw:
            return None

        dimensions = [
            RuleDimension(
                name=d["name"],
                description=d.get("description"),
                applicable_entities=d.get("applicable_entities", []),
            )
            for d in raw.get("rule_dimensions", {}).get("dimensions", [])
        ]

        rules = []
        for r in raw.get("ruleset", []):
            when_raw = r.get("when", {})
            when = None
            if when_raw:
                when = RuleWhen(
                    expression=when_raw.get("expression"),
                    allOf=when_raw.get("allOf"),
                    anyOf=when_raw.get("anyOf"),
                )

            then_raw = r.get("then", {})
            then = None
            if then_raw:
                then = RuleThen(
                    action=then_raw.get("action"),
                    output=then_raw.get("output"),
                    computation=then_raw.get("computation"),
                )

            rules.append(RuleDefinition(
                id=r["id"],
                name=r.get("name"),
                description=r.get("description"),
                type=r.get("type", "constraint"),
                priority=r.get("priority", 100),
                enabled=r.get("enabled", True),
                scope=r.get("scope"),
                when=when,
                then=then,
                **{"else": r.get("else")},
            ))

        return RulesDefinition(
            rule_dimensions=dimensions,
            ruleset=rules,
        )

    def validate(self, schema: KGMLSchema) -> list[str]:
        """Validate schema and return list of warnings/errors.

        Returns:
            List of validation messages (empty if valid)
        """
        issues = []

        # Check for duplicate concept names
        names = [c.name for c in schema.concepts]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            issues.append(f"Duplicate concept names: {duplicates}")

        # Check for duplicate enum names
        enum_names = [e.name for e in schema.enums]
        if len(enum_names) != len(set(enum_names)):
            duplicates = [n for n in enum_names if enum_names.count(n) > 1]
            issues.append(f"Duplicate enum names: {duplicates}")

        # Check concept relations reference valid concepts
        concept_names = {c.name for c in schema.concepts}
        for c in schema.concepts:
            for r in c.relations:
                if r.target not in concept_names:
                    issues.append(f"Concept '{c.name}' references unknown concept '{r.target}'")

        # Check attribute types reference valid types or enums
        type_names = {t.name for t in schema.types}
        enum_names_set = {e.name for e in schema.enums}
        builtin_types = {"string", "integer", "decimal", "float", "boolean", "date", "object"}
        for c in schema.concepts:
            for a in c.attributes:
                if a.type not in builtin_types and a.type not in type_names and a.type not in enum_names_set:
                    issues.append(f"Concept '{c.name}' attribute '{a.name}' has unknown type '{a.type}'")

        return issues
