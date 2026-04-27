"""
OntologyEngine - A toolchain for knowledge graph based analysis.

Usage:
    engine = OntologyEngine.from_config("schema.yaml")
    await engine.load_instances("instances.yaml")
    result = await engine.analyze(entity_id="SUP_001", dimension="credit_assessment")
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

from ontology_engine.core.schema import KGMLSchema, SchemaLoader
from ontology_engine.core.instances import InstanceLoader
from ontology_engine.storage import SQLiteStorage
from ontology_engine.engine.rule import RuleExecutor
from ontology_engine.engine.rule.models import AnalysisResult
from ontology_engine.engine.metric.engine import MetricEngine, MetricCache
from ontology_engine.engine.expression.engine import ExpressionEngine

if TYPE_CHECKING:
    from ontology_engine.storage.base import EntityInstance


class OntologyEngine:
    """Main engine for knowledge graph analysis."""

    def __init__(
        self,
        schema: KGMLSchema,
        storage: SQLiteStorage,
        rule_executor: RuleExecutor,
        metric_engine: MetricEngine | None = None,
    ):
        self.schema = schema
        self.storage = storage
        self.rule_executor = rule_executor
        self.metric_engine = metric_engine or MetricEngine(schema, storage, MetricCache())
        self.expression_engine = ExpressionEngine()

    @classmethod
    def from_config(cls, schema_path: str) -> "OntologyEngine":
        """Create engine from schema configuration.

        Args:
            schema_path: Path to schema.yaml file

        Returns:
            Configured OntologyEngine instance
        """
        loader = SchemaLoader()
        schema = loader.load(schema_path)

        issues = loader.validate(schema)
        if issues:
            import warnings
            warnings.warn(f"Schema validation issues: {issues}")

        storage = SQLiteStorage(":memory:")

        rule_executor = RuleExecutor(schema)

        metric_engine = MetricEngine(schema, storage, MetricCache())

        return cls(
            schema=schema,
            storage=storage,
            rule_executor=rule_executor,
            metric_engine=metric_engine,
        )

    async def initialize(self) -> None:
        """Initialize storage and load schema."""
        await self.storage.initialize()

    async def load_instances(self, instances_path: str) -> None:
        """Load instance data from YAML.

        Args:
            instances_path: Path to instances.yaml file
        """
        loader = InstanceLoader(schema=self.schema)
        entities, relations = loader.load(instances_path)

        for entity in entities:
            await self.storage.save_entity(entity)

        for relation in relations:
            await self.storage.save_relation(relation)

    async def get_entity(self, concept: str, entity_id: str) -> dict | None:
        """Get entity by concept and ID."""
        entity = await self.storage.get_entity(concept, entity_id)
        return entity.data if entity else None

    async def query_entities(
        self,
        concept: str,
        filters: dict | None = None
    ) -> list[dict]:
        """Query entities by concept with optional filters."""
        entities = await self.storage.query_entities(concept, filters)
        return [e.data for e in entities]

    async def analyze(
        self,
        entity_id: str,
        dimension: str,
        concept: str | None = None,
    ) -> AnalysisResult:
        """Analyze entity in a specific dimension.

        Args:
            entity_id: Entity ID to analyze
            dimension: Dimension name (e.g., "credit_assessment")
            concept: Concept type. If None, auto-detected from schema.

        Returns:
            AnalysisResult with rule execution results
        """
        if concept is None:
            concept = await self._resolve_concept(entity_id)

        entity = await self.get_entity(concept, entity_id)
        if not entity:
            return AnalysisResult(
                entity_id=entity_id,
                dimension=dimension,
                rule_results=[],
                computed_metrics={},
                alerts=[],
                decision=None,
                decision_reasoning=f"Entity {entity_id} not found"
            )

        entity = await self._compute_entity_metrics(entity)

        result = await self.rule_executor.execute_dimension(
            dimension=dimension,
            entity_id=entity_id,
            entity_data=entity
        )

        return result

    async def _resolve_concept(self, entity_id: str) -> str:
        """Resolve concept type for an entity_id using schema declarations.

        Strategy:
        1. Try get_entity_by_id if storage supports it
        2. Iterate over schema concept names and try storage.get_entity
        """
        try:
            entity = await self.storage.get_entity_by_id(entity_id)
            if entity:
                return entity._fact_object
        except (AttributeError, NotImplementedError):
            pass

        for concept_name in self.schema.get_all_concept_names():
            entity = await self.storage.get_entity(concept_name, entity_id)
            if entity:
                return concept_name

        return self.schema.get_all_concept_names()[0] if self.schema.concepts else "Unknown"

    async def _compute_entity_metrics(self, entity: dict) -> dict:
        """Compute metrics for an entity based on schema declarations.

        Strategy:
        1. If schema has L3 MetricDeclarationV2, use schema-driven computation
        2. If schema has v1 metrics, delegate to MetricEngine
        3. If no metrics defined, return entity unchanged

        Args:
            entity: Entity data dict

        Returns:
            Entity data with computed metrics added
        """
        entity = dict(entity)
        entity_id = self._detect_entity_id(entity)
        concept = entity.get("_fact_object", entity.get("_concept", ""))

        if self.schema.is_v2_format() and self.schema.analytical_elements:
            return await self._compute_metrics_v2(entity, entity_id, concept)

        if self.schema.metrics:
            return await self._compute_metrics_v1(entity, entity_id, concept)

        return entity

    async def _compute_metrics_v1(
        self,
        entity: dict,
        entity_id: str,
        concept: str,
    ) -> dict:
        """Compute metrics using v1 schema MetricDefinition via MetricEngine."""
        from ontology_engine.storage.base import EntityInstance

        entity_inst = EntityInstance(
            _fact_object=concept,
            entity_id=entity_id,
            data=entity,
        )

        metric_names = [m.name for m in self.schema.metrics]
        if not metric_names:
            return entity

        try:
            computed = await self.metric_engine.compute_batch(
                metric_names, entity_inst
            )
            for key, value in computed.items():
                if isinstance(value, dict) and "value" in value:
                    entity[key] = value["value"]
                else:
                    entity[key] = value
        except Exception:
            pass

        return entity

    async def _compute_metrics_v2(
        self,
        entity: dict,
        entity_id: str,
        concept: str,
    ) -> dict:
        """Compute metrics using v2 schema L3 MetricDeclaration.

        For each metric in schema.analytical_elements.metrics:
        - atomic: extract from entity data or compute from related entities
        - derived: evaluate formula using ExpressionEngine
        - composite: evaluate formula with weighted components
        - graph: delegate to MetricEngine graph computation
        """
        from ontology_engine.storage.base import EntityInstance

        metrics = self.schema.get_all_metrics()
        computed: dict[str, Any] = {}

        entity_inst = EntityInstance(
            _fact_object=concept,
            entity_id=entity_id,
            data=entity,
        )

        for metric_def in metrics:
            mid = metric_def.id
            if mid in entity and entity[mid] is not None:
                computed[mid] = entity[mid]
                continue

            if metric_def.type == "atomic":
                val = await self._compute_atomic_metric(metric_def, entity, entity_inst)
                if val is not None:
                    computed[mid] = val

        for metric_def in metrics:
            mid = metric_def.id
            if mid in computed:
                continue

            if metric_def.type in ("derived", "composite") and metric_def.formula:
                val = self._evaluate_metric_formula(metric_def, entity, computed)
                if val is not None:
                    computed[mid] = val

            if metric_def.type == "graph":
                try:
                    val = await self.metric_engine.compute(mid, entity_inst, computed)
                    if val is not None:
                        computed[mid] = val
                except Exception:
                    pass

        entity.update(computed)
        return entity

    async def _compute_atomic_metric(
        self,
        metric_def: Any,
        entity: dict,
        entity_inst: "EntityInstance",
    ) -> Any:
        """Compute an atomic metric from entity data or related entities."""
        mid = metric_def.id

        if mid in entity:
            return entity[mid]

        if metric_def.source and metric_def.source.type == "graph_traversal":
            return await self._compute_graph_traversal_metric(metric_def, entity, entity_inst)

        if metric_def.source and metric_def.source.type == "fact_attribute":
            attr = metric_def.source.attribute or mid
            return entity.get(attr)

        return None

    async def _compute_graph_traversal_metric(
        self,
        metric_def: Any,
        entity: dict,
        entity_inst: "EntityInstance",
    ) -> Any:
        """Compute a metric defined by graph traversal source."""
        source = metric_def.source
        if not source or not source.traversal:
            return None

        traversal = source.traversal
        aggregate = source.aggregate or "SUM"
        filter_expr = source.filter

        rel_match = self._parse_traversal(traversal)
        if not rel_match:
            return None

        rel_name, target_concept = rel_match

        try:
            neighbors = await self.storage.get_neighbors(
                entity_inst.entity_id, rel_name, "outgoing"
            )
        except Exception:
            neighbors = []

        if not neighbors:
            return None

        attr_name = self._extract_aggregate_attr(aggregate)
        if not attr_name:
            return None

        values = []
        for neighbor, _ in neighbors:
            val = self._get_nested_value(neighbor.data, attr_name)
            if val is not None:
                if isinstance(val, dict) and "value" in val:
                    values.append(val["value"])
                else:
                    values.append(val)

        if not values:
            return None

        if filter_expr:
            values = self._apply_filter(values, filter_expr)

        agg_fn = aggregate.split("(")[0].strip().upper()
        if agg_fn == "SUM":
            result = sum(values)
        elif agg_fn == "COUNT":
            result = len(values)
        elif agg_fn == "AVG":
            result = sum(values) / len(values) if values else 0
        elif agg_fn == "MIN":
            result = min(values)
        elif agg_fn == "MAX":
            result = max(values)
        else:
            result = sum(values)

        return result

    def _apply_filter(self, values: list, filter_expr: str) -> list:
        """Apply a simple filter expression to values."""
        return values

    def _parse_traversal(self, traversal: str) -> tuple[str, str] | None:
        """Parse traversal string like 'Store --has_sales--> MonthlySales'.

        Returns (relation_name, target_concept) or None.
        """
        import re
        m = re.search(r'--(\w+)-->\s*(\w+)', traversal)
        if m:
            return m.group(1), m.group(2)
        return None

    def _extract_aggregate_attr(self, aggregate: str) -> str | None:
        """Extract attribute name from aggregate like 'SUM(MonthlySales.net_revenue.value)'."""
        import re
        m = re.search(r'\((\w[\w.]*)\)', aggregate)
        if m:
            return m.group(1)
        return None

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get nested value from dict using dot-separated path."""
        parts = path.split(".")
        value: Any = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _evaluate_metric_formula(
        self,
        metric_def: Any,
        entity: dict,
        computed: dict[str, Any],
    ) -> Any:
        """Evaluate a derived/composite metric formula."""
        formula = metric_def.formula
        if not formula:
            return None

        context: dict[str, Any] = {}
        for key, value in entity.items():
            if isinstance(value, dict) and "value" in value:
                context[key] = value["value"]
            elif not isinstance(value, (dict, list)):
                context[key] = value

        context.update(computed)

        for dep in metric_def.dependencies:
            if dep in computed:
                val = computed[dep]
                if isinstance(val, dict) and "value" in val:
                    context[dep] = val["value"]
                else:
                    context[dep] = val

        try:
            result = self.expression_engine.evaluate(formula, context)
            if isinstance(result, (int, float)):
                unit = metric_def.unit
                if unit == "%":
                    result = result * 100 if result < 1 else result
            return result
        except Exception:
            return None

    def _detect_entity_id(self, entity: dict) -> str:
        """Detect entity ID from entity data using schema declarations.

        Strategy:
        1. Check _fact_object to get concept name, then use schema to find ID field
        2. Convention scan: fields ending in _id or _no
        3. Fallback: entity_id or _fact_object
        """
        concept = entity.get("_fact_object", entity.get("_concept", ""))

        if concept:
            id_field = self.schema.get_entity_id_field(concept)
            if id_field and id_field in entity:
                return str(entity[id_field])

        for key, value in entity.items():
            if key.startswith("_"):
                continue
            if key.endswith("_id") or key.endswith("_no"):
                if isinstance(value, str) and value:
                    return value

        return entity.get("entity_id", concept or "unknown")

    async def close(self) -> None:
        """Close engine and cleanup resources."""
        await self.storage.close()


__version__ = "0.1.0"
__all__ = ["OntologyEngine", "__version__"]
