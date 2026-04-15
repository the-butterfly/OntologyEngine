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
    # V2 models
    FactObjects,
    FactObjectEntity,
    Categorizations,
    CategorizationDimension,
    AnalyticalElements,
    MetricDefinitionV2,
    IndicatorDefinition,
    ScorecardDefinition,
    BusinessLogic,
    RuleDefinitionV2,
    RuleLogic,
    RuleAction,
    RuleStep,
    MetricSource,
    MetricComponent,
    # Enhanced models
    CategoryValueDefinition,
    CategoryValueDomain,
    DimensionApplicability,
    RuleOverride,
    RuleApplicabilityMapping,
    CategorizationRuleset,
    ValueDomain,
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
        """Parse raw YAML dict into KGMLSchema.

        Supports both v1 format (concepts, metrics, rules) and
        v2 format (fact_objects, categorizations, analytical_elements, business_logic).
        """
        # Check schema version to determine format
        schema_version = raw.get("schema_version", "1.0")

        # Parse v2 format
        if schema_version == "2.0" or "fact_objects" in raw or "business_logic" in raw:
            return self._parse_v2(raw)

        # Parse v1 format (legacy)
        return KGMLSchema(
            metadata=self._parse_metadata(raw.get("metadata", {})),
            types=self._parse_types(raw.get("types", [])),
            enums=self._parse_enums(raw.get("enums", [])),
            concepts=self._parse_concepts(raw.get("concepts", [])),
            metrics=self._parse_metrics(raw.get("metrics", [])),
            rules=self._parse_rules(raw.get("rules")),
        )

    def _parse_v2(self, raw: dict[str, Any]) -> KGMLSchema:
        """Parse v2 format schema."""
        # Parse L1: Fact Objects
        fact_objects_raw = raw.get("fact_objects", {})
        fact_objects = self._parse_fact_objects(fact_objects_raw)

        # Parse L2: Categorizations
        categorizations_raw = raw.get("categorizations", [])
        categorizations = self._parse_categorizations(categorizations_raw)

        # Parse L3: Analytical Elements
        analytical_elements_raw = raw.get("analytical_elements", {})
        analytical_elements = self._parse_analytical_elements(analytical_elements_raw)

        # Parse L4: Business Logic
        business_logic_raw = raw.get("business_logic", {})
        business_logic = self._parse_business_logic(business_logic_raw)

        return KGMLSchema(
            metadata=self._parse_metadata(raw.get("metadata", raw.get("semantic_space", {}))),
            schema_version="2.0",
            # V1 fields derived from v2
            types=fact_objects.shared_types if fact_objects else [],
            enums=fact_objects.enums if fact_objects else [],
            concepts=self._entities_to_concepts(fact_objects.entities) if fact_objects else [],
            # V2 fields
            fact_objects=fact_objects,
            categorizations=categorizations,
            analytical_elements=analytical_elements,
            business_logic=business_logic,
        )

    def _parse_fact_objects(self, raw: dict) -> FactObjects | None:
        """Parse fact_objects section (L1)."""
        if not raw:
            return None

        # Parse shared types
        shared_types = self._parse_types(raw.get("shared_types", []))

        # Parse enums
        enums = self._parse_enums(raw.get("enums", []))

        # Parse entities
        entities = []
        for e in raw.get("entities", []):
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
                    value_domain=ValueDomain(**a["value_domain"]) if a.get("value_domain") else None,
                )
                for a in e.get("attributes", [])
            ]

            relations = [
                RelationDefinition(
                    name=r["name"],
                    target=r["target"],
                    cardinality=r.get("cardinality", "0..*"),
                    description=r.get("description"),
                    inverse=r.get("inverse"),
                )
                for r in e.get("relations", [])
            ]

            entities.append(FactObjectEntity(
                id=e["id"],
                name=e.get("name"),
                description=e.get("description"),
                attributes=attributes,
                relations=relations,
            ))

        # Parse relations (as FactObjectEntity with from/to)
        relations = []
        for r in raw.get("relations", []):
            # Convert relation to FactObjectEntity format for storage
            # but keep the from/to structure available
            rel = RelationDefinition(
                name=r.get("id", r.get("name", "")),
                target=r.get("to", r.get("target", "")),
                cardinality=r.get("cardinality", "0..*"),
                description=r.get("description"),
                inverse=r.get("inverse"),
            )
            relations.append(rel)

        return FactObjects(
            shared_types=shared_types,
            enums=enums,
            entities=entities,
            relations=relations,
        )

    def _parse_categorizations(self, raw: list) -> Categorizations | None:
        """Parse categorizations section (L2).

        Supports both simple format (backward compat) and enhanced format
        with value_domain, multi_select, ruleset, rule_applicability.
        """
        if not raw:
            return None

        dimensions = []
        for d in raw:
            # Parse value_domain if present
            value_domain = None
            if "value_domain" in d and d["value_domain"]:
                vd_raw = d["value_domain"]
                vd_type = vd_raw.get("type", "discrete")
                values = []
                for v in vd_raw.get("values", []):
                    children = []
                    for child in v.get("children", []):
                        children.append(CategoryValueDefinition(
                            id=child.get("id", ""),
                            label=child.get("label", ""),
                            description=child.get("description"),
                            synonyms=child.get("synonyms", []),
                            sort_order=child.get("sort_order", 0),
                            color=child.get("color"),
                            metadata=child.get("metadata", {}),
                            level=child.get("level"),
                            parent_id=child.get("parent_id"),
                        ))
                    values.append(CategoryValueDefinition(
                        id=v.get("id", ""),
                        label=v.get("label", ""),
                        description=v.get("description"),
                        synonyms=v.get("synonyms", []),
                        sort_order=v.get("sort_order", 0),
                        color=v.get("color"),
                        metadata=v.get("metadata", {}),
                        level=v.get("level"),
                        parent_id=v.get("parent_id"),
                        children=children,
                    ))
                value_domain = CategoryValueDomain(
                    type=vd_type,
                    values=values,
                    enum_ref=vd_raw.get("enum_ref"),
                )

            # Parse applicable_to (can be string list or object list)
            applicable_to_raw = d.get("applicable_to", [])
            applicable_to: list[DimensionApplicability | str] = []
            for item in applicable_to_raw:
                if isinstance(item, str):
                    applicable_to.append(item)
                elif isinstance(item, dict):
                    applicable_to.append(DimensionApplicability(
                        object_type=item.get("object_type", ""),
                        required=item.get("required", False),
                        auto_categorize=item.get("auto_categorize", True),
                        auto_dimension=item.get("auto_dimension"),
                    ))

            # Parse ruleset if present
            ruleset = None
            if "ruleset" in d and d["ruleset"]:
                rs_raw = d["ruleset"]
                ruleset = CategorizationRuleset(
                    id=rs_raw.get("id", ""),
                    name=rs_raw.get("name"),
                    rules=rs_raw.get("rules", []),
                )

            # Parse rule_applicability if present
            rule_applicability = []
            for ra in d.get("rule_applicability", []):
                overrides = []
                for ro in ra.get("rule_overrides", []):
                    overrides.append(RuleOverride(
                        rule_id=ro.get("rule_id", ""),
                        override_field=ro.get("override_field", ""),
                        override_value=ro.get("override_value"),
                    ))
                rule_applicability.append(RuleApplicabilityMapping(
                    dimension_value=ra.get("dimension_value", ""),
                    applicable_rule_groups=ra.get("applicable_rule_groups", []),
                    excluded_rule_groups=ra.get("excluded_rule_groups", []),
                    rule_overrides=overrides,
                ))

            dimensions.append(CategorizationDimension(
                id=d["id"],
                name=d.get("name"),
                description=d.get("description"),
                type=d.get("type", "flat"),
                value_domain=value_domain,
                multi_select=d.get("multi_select", False),
                applicable_to=applicable_to if applicable_to else d.get("applicable_to", []),
                ruleset=ruleset,
                rule_applicability=rule_applicability,
                triggers=d.get("triggers", []),
            ))

        return Categorizations(dimensions=dimensions)

    def _parse_analytical_elements(self, raw: dict) -> AnalyticalElements | None:
        """Parse analytical_elements section (L3)."""
        if not raw:
            return None

        # Parse metrics
        metrics = []
        for m in raw.get("metrics", []):
            source = None
            if "source" in m:
                src = m["source"]
                source = MetricSource(
                    type=src.get("type", ""),
                    entity=src.get("entity"),
                    attribute=src.get("attribute"),
                    traversal=src.get("traversal"),
                    aggregate=src.get("aggregate"),
                    filter=src.get("filter"),
                    provider=src.get("provider"),
                )

            components = None
            if "components" in m:
                components = [
                    MetricComponent(
                        metric=c["metric"],
                        weight=c.get("weight", 1.0),
                        transform=c.get("transform"),
                    )
                    for c in m["components"]
                ]

            metrics.append(MetricDefinitionV2(
                id=m["id"],
                name=m.get("name"),
                description=m.get("description"),
                type=m.get("type", m.get("element_type", "atomic")),
                source=source,
                dependencies=m.get("dependencies", []),
                formula=m.get("formula"),
                unit=m.get("unit"),
                range=m.get("range"),
                default=m.get("default"),
                thresholds=m.get("thresholds"),
                overridable=m.get("overridable", False),
                components=components,
                algorithm=m.get("algorithm"),
                traversal=m.get("traversal"),
                neighbor_filter=m.get("neighbor_filter"),
                value_domain=ValueDomain(**m["value_domain"]) if m.get("value_domain") else None,
                expression_domain=m.get("expression_domain", []),
            ))

        # Parse indicators
        indicators = []
        for i in raw.get("indicators", []):
            source = None
            if "source" in i:
                src = i["source"]
                source = MetricSource(
                    type=src.get("type", ""),
                    entity=src.get("entity"),
                    attribute=src.get("attribute"),
                )

            indicators.append(IndicatorDefinition(
                id=i["id"],
                name=i.get("name"),
                description=i.get("description"),
                type=i.get("element_type", "atomic"),
                source=source,
                dependencies=i.get("dependencies", []),
                formula=i.get("formula"),
                output_type=i.get("output_type", "boolean"),
                overridable=i.get("overridable", False),
                value_domain=ValueDomain(**i["value_domain"]) if i.get("value_domain") else None,
            ))

        # Parse scorecards
        scorecards = []
        for s in raw.get("scorecards", []):
            scorecards.append(ScorecardDefinition(
                id=s["id"],
                name=s.get("name"),
                description=s.get("description"),
                type=s.get("element_type", "derived"),
                dependencies=s.get("dependencies", []),
                formula=s.get("formula"),
                output_type=s.get("output_type", "string"),
                overridable=s.get("overridable", False),
                value_domain=ValueDomain(**s["value_domain"]) if s.get("value_domain") else None,
            ))

        return AnalyticalElements(
            metrics=metrics,
            indicators=indicators,
            scorecards=scorecards,
        )

    def _parse_business_logic(self, raw: dict) -> BusinessLogic | None:
        """Parse business_logic section (L4).

        Canonical field names: applies_to (not target_objects),
        inputs/outputs (not input_elements/output_elements),
        preconditions, steps[] with depends_on.
        Supports both canonical and legacy field names via model validators.
        """
        if not raw:
            return None

        # Parse rule definitions
        rule_definitions = []
        for rd in raw.get("rule_definitions", []):
            rule_definitions.append(RuleDefinitionV2(
                id=rd["id"],
                name=rd.get("name"),
                description=rd.get("description"),
                rule_type=rd.get("rule_type", "constraint"),
                priority=rd.get("priority", 100),
                applies_to=rd.get("applies_to", []),
                applicable_categorizations=rd.get("applicable_categorizations", []),
                inputs=rd.get("inputs", []),
                outputs=rd.get("outputs", []),
                preconditions=rd.get("preconditions", []),
                enabled=rd.get("enabled", True),
                logic_ids=rd.get("logic_ids", []),
            ))

        # Parse rule logics
        rule_logics = []
        for rl in raw.get("rule_logics", []):
            when = None
            if "when" in rl:
                when_raw = rl["when"]
                when = RuleWhen(
                    expression=when_raw.get("expression"),
                    allOf=when_raw.get("allOf"),
                    anyOf=when_raw.get("anyOf"),
                )

            then_action = None
            if "then_action" in rl:
                ta = rl["then_action"]
                then_action = RuleAction(
                    action_type=ta.get("action_type"),
                    output=ta.get("output"),
                    computation=ta.get("computation"),
                )

            else_action = None
            if "else_action" in rl:
                ea = rl["else_action"]
                else_action = RuleAction(
                    action_type=ea.get("action_type"),
                    output=ea.get("output"),
                    computation=ea.get("computation"),
                )

            # Parse canonical DAG steps[]
            steps = []
            for s in rl.get("steps", []):
                condition = None
                if "condition" in s and s["condition"]:
                    cond_raw = s["condition"]
                    condition = RuleWhen(
                        expression=cond_raw.get("expression"),
                        allOf=cond_raw.get("allOf"),
                        anyOf=cond_raw.get("anyOf"),
                    )
                steps.append(RuleStep(
                    id=s["id"],
                    name=s.get("name"),
                    description=s.get("description"),
                    priority=s.get("priority", 100),
                    depends_on=s.get("depends_on", []),
                    condition=condition,
                    action=s.get("action"),
                    operator=s.get("operator"),
                    computation=s.get("computation"),
                    output_field=s.get("output_field"),
                    enabled=s.get("enabled", True),
                ))

            rule_logics.append(RuleLogic(
                id=rl["id"],
                name=rl.get("name"),
                definition_id=rl["definition_id"],
                applicable_conditions=rl.get("applicable_conditions", []),
                when=when,
                then_action=then_action,
                else_action=else_action,
                steps=steps,
                priority=rl.get("priority", 100),
                version=rl.get("version", 1),
                environment=rl.get("environment", "default"),
            ))

        return BusinessLogic(
            rule_definitions=rule_definitions,
            rule_logics=rule_logics,
        )

    def _entities_to_concepts(self, entities: list[FactObjectEntity]) -> list[ConceptDefinition]:
        """Convert FactObjectEntity list to ConceptDefinition list for v1 compatibility."""
        concepts = []
        for e in entities:
            concepts.append(ConceptDefinition(
                name=e.id,
                description=e.description,
                category="entity",
                attributes=e.attributes,
                relations=e.relations,
            ))
        return concepts

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
                    value_domain=ValueDomain(**a["value_domain"]) if a.get("value_domain") else None,
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
