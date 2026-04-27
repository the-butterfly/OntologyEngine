# ontology_engine/engine/metric/engine.py
"""MetricEngine - DAG-based metric computation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.engine.expression import ExpressionEngine
from ontology_engine.engine.metric.dag import MetricDAG
from ontology_engine.engine.metric.errors import (
    MetricError,
    MetricNotComputableError,
    MetricNotFoundError,
)
from ontology_engine.engine.metric.graph_operators import GraphOperatorRegistry
from ontology_engine.storage.base import StorageBackend

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema, MetricDefinition
    from ontology_engine.storage.base import EntityInstance, RelationInstance


class MetricCache:
    """Simple in-memory cache for computed metrics."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], Any] = {}

    def get(self, entity_id: str, metric_name: str) -> Any | None:
        return self._cache.get((entity_id, metric_name))

    def set(self, entity_id: str, metric_name: str, value: Any) -> None:
        self._cache[(entity_id, metric_name)] = value

    def clear(self) -> None:
        self._cache.clear()

    def clear_entity(self, entity_id: str) -> None:
        keys_to_delete = [key for key in self._cache if key[0] == entity_id]
        for key in keys_to_delete:
            del self._cache[key]


class MetricEngine:
    """DAG-based metric computation engine.

    Uses schema declarations to drive metric computation:
    - atomic metrics with graph_traversal source: aggregate over related entities
    - derived/composite metrics: evaluate formula
    - graph metrics: delegate to GraphOperatorRegistry
    """

    def __init__(
        self,
        schema: "KGMLSchema",
        storage: StorageBackend,
        cache: MetricCache | None = None,
    ):
        self.schema = schema
        self.storage = storage
        self.cache = cache or MetricCache()
        self.expression_engine = ExpressionEngine()
        self._metric_defs: dict[str, "MetricDefinition"] = {
            metric.name: metric for metric in schema.metrics
        }
        self._v2_metric_defs: dict[str, Any] = {}
        if schema.analytical_elements:
            for m in schema.analytical_elements.metrics:
                self._v2_metric_defs[m.id] = m
        self._dag = MetricDAG(schema.metrics)

    def _find_metric_def(self, metric_name: str) -> Any | None:
        """Find metric definition from v2 or v1 schema."""
        v2_def = self._v2_metric_defs.get(metric_name)
        if v2_def:
            return v2_def
        return self._metric_defs.get(metric_name)

    async def compute(
        self,
        metric_name: str,
        entity: "EntityInstance",
        context: dict[str, Any] | None = None,
    ) -> Any:
        metric_def = self._find_metric_def(metric_name)

        if metric_def is None and metric_name not in self._metric_defs:
            raise MetricNotFoundError(f"Metric '{metric_name}' not found in schema")

        cached = self.cache.get(entity.entity_id, metric_name)
        if cached is not None:
            return cached

        stored = await self.storage.get_metric(entity.entity_id, metric_name)
        if stored is not None:
            self.cache.set(entity.entity_id, metric_name, stored)
            return stored

        if metric_def is None:
            raise MetricNotFoundError(f"Metric '{metric_name}' not found in schema")

        dep_values: dict[str, Any] = {}
        for dep in metric_def.dependencies:
            dep_values[dep] = await self.compute(dep, entity, context)

        metric_type = getattr(metric_def, 'type', None) or 'atomic'

        if metric_type == "atomic":
            value = await self._compute_atomic(metric_def, entity)
        elif metric_type == "derived":
            value = await self._compute_derived(metric_def, entity, dep_values, context)
        elif metric_type == "composite":
            value = await self._compute_composite(metric_def, entity, dep_values, context)
        elif metric_type == "graph":
            value = await self._compute_graph(metric_def, entity, dep_values)
        else:
            raise MetricError(f"Unknown metric type: {metric_type}")

        self.cache.set(entity.entity_id, metric_name, value)
        await self.storage.save_metric(entity.entity_id, metric_name, value)
        return value

    async def compute_batch(
        self,
        metric_names: list[str],
        entity: "EntityInstance",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sorted_metrics = self._dag.topological_order(metric_names)

        results: dict[str, Any] = {}
        for name in sorted_metrics:
            if name in results:
                continue
            cached = self.cache.get(entity.entity_id, name)
            if cached is not None:
                results[name] = cached
            else:
                results[name] = await self.compute(name, entity, context)

        return {name: results[name] for name in metric_names}

    def _collect_dependencies(self, metric_names: list[str]) -> set[str]:
        required: set[str] = set()
        for name in metric_names:
            if name in self._metric_defs:
                required.add(name)
                required.update(self._dag.get_all_dependencies(name))
        return required

    async def _compute_atomic(
        self,
        metric_def: Any,
        entity: "EntityInstance",
    ) -> Any:
        name = getattr(metric_def, 'id', None) or getattr(metric_def, 'name', '')

        if name in entity.data:
            return entity.data[name]

        source = getattr(metric_def, 'source', None)
        if source and getattr(source, 'type', None) == "graph_traversal":
            return await self._compute_from_graph_traversal(metric_def, entity)

        if source and getattr(source, 'type', None) == "fact_attribute":
            attr = getattr(source, 'attribute', None) or name
            return entity.data.get(attr)

        if source and getattr(source, 'traversal', None):
            return await self._compute_from_graph_traversal(metric_def, entity)

        return await self._compute_atomic_by_convention(metric_def, entity)

    async def _compute_from_graph_traversal(
        self,
        metric_def: Any,
        entity: "EntityInstance",
    ) -> Any:
        """Compute an atomic metric from graph traversal source declaration."""
        source = metric_def.source
        traversal_str = getattr(source, 'traversal', None)
        aggregate = getattr(source, 'aggregate', 'SUM')
        filter_expr = getattr(source, 'filter', None)

        if not traversal_str:
            return None

        rel_name, target_concept = self._parse_traversal(traversal_str)
        if not rel_name:
            return None

        try:
            neighbors = await self._get_neighbors_with_relations(
                entity.entity_id,
                rel_name,
                "outgoing",
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

        agg_fn = aggregate.split("(")[0].strip().upper()
        result = self._apply_aggregate(agg_fn, values)

        if filter_expr and result is not None:
            pass

        return result

    async def _compute_atomic_by_convention(
        self,
        metric_def: Any,
        entity: "EntityInstance",
    ) -> Any:
        """Compute an atomic metric using convention-based relation discovery.

        For v1 schemas without MetricSource, infer the relation and attribute
        from the metric name and schema concept relations.
        """
        name = getattr(metric_def, 'id', None) or getattr(metric_def, 'name', '')
        concept = entity._fact_object

        rel_name, attr_name, agg_fn = self._infer_aggregation_from_metric_name(name, concept)
        if not rel_name:
            raise MetricNotComputableError(
                f"Atomic metric '{name}' cannot be computed for entity {entity.entity_id}"
            )

        try:
            neighbors = await self._get_neighbors_with_relations(
                entity.entity_id,
                rel_name,
                "outgoing",
            )
        except Exception:
            neighbors = []

        if not neighbors:
            return self._default_value_for_metric(name)

        if name == "guarantee_chain_depth":
            return await self._compute_guarantee_chain_depth(entity)
        if name == "has_guarantee_circle":
            depth = await self._compute_guarantee_chain_depth(entity)
            return depth >= 3

        values = []
        for neighbor, _ in neighbors:
            val = self._get_nested_value(neighbor.data, attr_name)
            if val is not None:
                if isinstance(val, dict) and "value" in val:
                    values.append(val["value"])
                else:
                    values.append(val)

        if not values:
            return self._default_value_for_metric(name)

        if agg_fn == "COUNT":
            return len(neighbors)

        return self._apply_aggregate(agg_fn, values)

    def _infer_aggregation_from_metric_name(
        self, metric_name: str, concept: str
    ) -> tuple[str | None, str | None, str]:
        """Infer relation name, attribute name, and aggregation function from metric name.

        Uses schema declarations to find the relation, then infers aggregation
        from the metric name pattern.
        """
        concept_def = self.schema.get_concept(concept)
        if not concept_def or not concept_def.relations:
            return None, None, "SUM"

        name_lower = metric_name.lower()

        if "invoice" in name_lower and "amount" in name_lower and "overdue" in name_lower:
            rel = self._find_relation_by_target_keyword(concept_def.relations, "invoice")
            if rel:
                return rel.name, "amount", "SUM"
        if "invoice" in name_lower and "amount" in name_lower:
            rel = self._find_relation_by_target_keyword(concept_def.relations, "invoice")
            if rel:
                return rel.name, "amount", "SUM"
        if "invoice" in name_lower and "count" in name_lower:
            rel = self._find_relation_by_target_keyword(concept_def.relations, "invoice")
            if rel:
                return rel.name, "amount", "COUNT"
        if "contract" in name_lower and "amount" in name_lower:
            rel = self._find_relation_by_target_keyword(concept_def.relations, "contract")
            if rel:
                return rel.name, "contract_amount", "SUM"
        if "core_enterprise" in name_lower and "count" in name_lower:
            rel = self._find_relation_by_target_keyword(concept_def.relations, "enterprise")
            if rel:
                return rel.name, None, "COUNT"

        return None, None, "SUM"

    def _find_relation_by_target_keyword(
        self, relations: list, keyword: str
    ) -> Any | None:
        """Find a relation whose target concept name contains the keyword."""
        for rel in relations:
            if keyword.lower() in rel.target.lower():
                return rel
        return None

    def _default_value_for_metric(self, name: str) -> Any:
        """Return a sensible default for a metric that can't be computed."""
        if "amount" in name.lower():
            return {"value": 0, "currency": "CNY"}
        if "count" in name.lower() or "depth" in name.lower():
            return 0
        if "ratio" in name.lower() or "rate" in name.lower():
            return 0
        if "score" in name.lower():
            return 0
        return 0

    def _parse_traversal(self, traversal: str) -> tuple[str | None, str | None]:
        """Parse traversal string like 'Store --has_sales--> MonthlySales'."""
        import re
        m = re.search(r'--(\w+)-->\s*(\w+)', traversal)
        if m:
            return m.group(1), m.group(2)
        return None, None

    def _extract_aggregate_attr(self, aggregate: str) -> str | None:
        """Extract attribute name from aggregate like 'SUM(MonthlySales.net_revenue.value)'."""
        import re
        m = re.search(r'\((\w[\w.]*)\)', aggregate)
        if m:
            return m.group(1)
        return None

    def _get_nested_value(self, data: dict, path: str | None) -> Any:
        """Get nested value from dict using dot-separated path."""
        if not path:
            return None
        parts = path.split(".")
        value: Any = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _apply_aggregate(self, agg_fn: str, values: list) -> Any:
        """Apply aggregation function to a list of values."""
        if agg_fn == "SUM":
            return sum(values)
        elif agg_fn == "COUNT":
            return len(values)
        elif agg_fn == "AVG":
            return sum(values) / len(values) if values else 0
        elif agg_fn == "MIN":
            return min(values) if values else 0
        elif agg_fn == "MAX":
            return max(values) if values else 0
        return sum(values)

    async def _compute_guarantee_chain_depth(self, entity: "EntityInstance") -> int:
        """Compute guarantee chain depth using schema-driven traversal.

        Uses schema relation declarations to find the guarantee relation
        and ID field, instead of hardcoding 'Supplier'/'guaranteed_by'/'supplier_id'.
        """
        depth = 0
        visited: set[str] = set()
        current_ids: list[str] = []

        concept = entity._fact_object
        concept_def = self.schema.get_concept(concept)

        guarantee_rel_name = "guaranteed_by"
        guarantee_id_field = "supplier_id"
        guarantee_concept = concept

        if concept_def:
            for rel in concept_def.relations:
                target_lower = rel.target.lower()
                if "guarantee" in target_lower or "guarantor" in target_lower:
                    guarantee_rel_name = rel.name
                    guarantee_concept = rel.target
                    id_field = self.schema.get_entity_id_field(rel.target)
                    if id_field:
                        guarantee_id_field = id_field
                    break

        initial_guarantors = entity.data.get(guarantee_rel_name, [])
        for guarantor in initial_guarantors:
            guarantor_id = (
                str(guarantor.get(guarantee_id_field, ""))
                if isinstance(guarantor, dict)
                else str(guarantor) if guarantor else ""
            )
            if guarantor_id:
                current_ids.append(guarantor_id)

        while current_ids and len(visited) < 10:
            depth += 1
            next_ids: list[str] = []
            for current_id in current_ids:
                if current_id in visited:
                    depth += 1
                    break
                visited.add(current_id)

                guarantor_entity = await self.storage.get_entity(guarantee_concept, current_id)
                if guarantor_entity is None:
                    continue
                guarantor_list = guarantor_entity.data.get(guarantee_rel_name, [])
                for guarantor in guarantor_list:
                    next_id = (
                        str(guarantor.get(guarantee_id_field, ""))
                        if isinstance(guarantor, dict)
                        else str(guarantor) if guarantor else ""
                    )
                    if next_id and next_id not in visited:
                        next_ids.append(next_id)

            current_ids = next_ids
            if not current_ids:
                break

        return depth

    async def _get_neighbors_with_relations(
        self,
        entity_id: str,
        relation_type: str,
        direction: str = "outgoing",
    ) -> list[tuple["EntityInstance", "RelationInstance"]]:
        return await self.storage.get_neighbors(entity_id, relation_type, direction)

    async def _compute_derived(
        self,
        metric_def: "MetricDefinition",
        entity: "EntityInstance",
        dep_values: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> Any:
        if not metric_def.formula:
            raise MetricError(f"Derived metric '{metric_def.name}' missing formula")

        eval_context = self._build_eval_context(entity, dep_values, context)
        try:
            result = self.expression_engine.evaluate(metric_def.formula, eval_context)
        except Exception as exc:
            raise MetricError(
                f"Failed to evaluate formula '{metric_def.formula}': {exc}"
            ) from exc

        if metric_def.type == "Percentage" and isinstance(result, (int, float)):
            result = round(result, 2)
        elif metric_def.type == "Money" and isinstance(result, (int, float)):
            result = {"value": result, "currency": "CNY"}
        return result

    async def _compute_composite(
        self,
        metric_def: "MetricDefinition",
        entity: "EntityInstance",
        dep_values: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> Any:
        if not metric_def.formula:
            raise MetricError(f"Composite metric '{metric_def.name}' missing formula")

        eval_context = self._build_eval_context(entity, dep_values, context)
        try:
            result = self.expression_engine.evaluate(metric_def.formula, eval_context)
        except Exception as exc:
            raise MetricError(
                f"Failed to evaluate formula '{metric_def.formula}': {exc}"
            ) from exc

        if hasattr(metric_def, "output_range") and metric_def.output_range:
            output_range = metric_def.output_range
            if isinstance(output_range, (list, tuple)) and len(output_range) == 2:
                result = max(output_range[0], min(output_range[1], result))

        return round(result, 2) if isinstance(result, (int, float)) else result

    async def _compute_graph(
        self,
        metric_def: "MetricDefinition",
        entity: "EntityInstance",
        dep_values: dict[str, Any],
    ) -> Any:
        algorithm = getattr(metric_def, "algorithm", None)

        if algorithm is None:
            raise MetricError(f"Graph metric '{metric_def.name}' missing algorithm")

        algorithm_name: str
        algorithm_params: dict[str, Any]
        if isinstance(algorithm, str):
            algorithm_name = algorithm
            algorithm_params = {}
        else:
            algorithm_name = getattr(algorithm, "name", None) or ""
            algorithm_params = getattr(algorithm, "params", {}) or {}

        if not algorithm_name:
            raise MetricError(f"Graph metric '{metric_def.name}' has invalid algorithm")

        traversal = getattr(metric_def, "traversal", None)

        return await GraphOperatorRegistry.execute(
            algorithm_name,
            entity,
            self.storage,
            algorithm_params,
            traversal,
            dep_values,
        )

    def _build_eval_context(
        self,
        entity: "EntityInstance",
        dep_values: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        eval_ctx: dict[str, Any] = {}

        for key, value in entity.data.items():
            if isinstance(value, dict) and "value" in value:
                eval_ctx[key] = value["value"]
            else:
                eval_ctx[key] = value

        eval_ctx["entity_id"] = entity.entity_id

        for dep_name, dep_value in dep_values.items():
            if isinstance(dep_value, dict) and "value" in dep_value:
                eval_ctx[dep_name] = dep_value["value"]
            else:
                eval_ctx[dep_name] = dep_value

        if context:
            eval_ctx.update(context)
        return eval_ctx

    def _to_numeric(self, value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict) and "value" in value:
            return float(value["value"])
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0
