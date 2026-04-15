# ontology_engine/engine/metric/engine.py
"""MetricEngine - DAG-based metric computation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
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
    """DAG-based metric computation engine."""

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
        self._dag = MetricDAG(schema.metrics)

    async def compute(
        self,
        metric_name: str,
        entity: "EntityInstance",
        context: dict[str, Any] | None = None,
    ) -> Any:
        metric_def = self._metric_defs.get(metric_name)
        if not metric_def:
            raise MetricNotFoundError(f"Metric '{metric_name}' not found in schema")

        cached = self.cache.get(entity.entity_id, metric_name)
        if cached is not None:
            return cached

        stored = await self.storage.get_metric(entity.entity_id, metric_name)
        if stored is not None:
            self.cache.set(entity.entity_id, metric_name, stored)
            return stored

        dep_values: dict[str, Any] = {}
        for dep in metric_def.dependencies:
            dep_values[dep] = await self.compute(dep, entity, context)

        if metric_def.type == "atomic":
            value = await self._compute_atomic(metric_def, entity)
        elif metric_def.type == "derived":
            value = await self._compute_derived(metric_def, entity, dep_values, context)
        elif metric_def.type == "composite":
            value = await self._compute_composite(metric_def, entity, dep_values, context)
        elif metric_def.type == "graph":
            value = await self._compute_graph(metric_def, entity, dep_values)
        else:
            raise MetricError(f"Unknown metric type: {metric_def.type}")

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
        metric_def: "MetricDefinition",
        entity: "EntityInstance",
    ) -> Any:
        name = metric_def.name

        if name in entity.data:
            return entity.data[name]

        if name == "total_invoice_amount_90d":
            return await self._aggregate_invoice_amount(entity, days=90)
        if name == "overdue_invoice_amount":
            return await self._aggregate_overdue_invoice_amount(entity)
        if name == "invoice_count_90d":
            return await self._count_invoices_90d(entity)
        if name == "total_contract_amount":
            return await self._aggregate_contract_amount(entity)
        if name == "core_enterprise_count":
            return await self._count_core_enterprises(entity)
        if name == "guarantee_chain_depth":
            return await self._compute_guarantee_chain_depth(entity)
        if name == "has_guarantee_circle":
            depth = await self._compute_guarantee_chain_depth(entity)
            return depth >= 3

        if name in entity.data:
            return entity.data[name]

        raise MetricNotComputableError(
            f"Atomic metric '{name}' cannot be computed for entity {entity.entity_id}"
        )

    async def _aggregate_invoice_amount(
        self,
        entity: "EntityInstance",
        days: int = 90,
    ) -> dict[str, Any]:
        cutoff = date.today() - timedelta(days=days)
        total = 0.0
        neighbors = await self._get_neighbors_with_relations(
            entity.entity_id,
            "has_invoice",
            "outgoing",
        )

        for neighbor, _ in neighbors:
            amount = neighbor.data.get("amount", {})
            value = amount.get("value", 0) if isinstance(amount, dict) else amount or 0
            issue_date_str = neighbor.data.get("issue_date", "")
            if not issue_date_str:
                continue
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if issue_date >= cutoff:
                total += value

        return {"value": total, "currency": "CNY"}

    async def _aggregate_overdue_invoice_amount(
        self,
        entity: "EntityInstance",
    ) -> dict[str, Any]:
        total = 0.0
        neighbors = await self._get_neighbors_with_relations(
            entity.entity_id,
            "has_invoice",
            "outgoing",
        )

        for neighbor, _ in neighbors:
            if neighbor.data.get("status") != "OVERDUE":
                continue
            amount = neighbor.data.get("amount", {})
            value = amount.get("value", 0) if isinstance(amount, dict) else amount or 0
            total += value

        return {"value": total, "currency": "CNY"}

    async def _count_invoices_90d(self, entity: "EntityInstance") -> int:
        cutoff = date.today() - timedelta(days=90)
        count = 0
        neighbors = await self._get_neighbors_with_relations(
            entity.entity_id,
            "has_invoice",
            "outgoing",
        )

        for neighbor, _ in neighbors:
            issue_date_str = neighbor.data.get("issue_date", "")
            if not issue_date_str:
                continue
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if issue_date >= cutoff:
                count += 1

        return count

    async def _aggregate_contract_amount(
        self,
        entity: "EntityInstance",
    ) -> dict[str, Any]:
        total = 0.0
        neighbors = await self._get_neighbors_with_relations(
            entity.entity_id,
            "has_contract",
            "outgoing",
        )

        for neighbor, _ in neighbors:
            amount = neighbor.data.get("contract_amount", {})
            value = amount.get("value", 0) if isinstance(amount, dict) else amount or 0
            total += value

        return {"value": total, "currency": "CNY"}

    async def _count_core_enterprises(self, entity: "EntityInstance") -> int:
        neighbors = await self._get_neighbors_with_relations(
            entity.entity_id,
            "supplies_to",
            "outgoing",
        )
        return len(neighbors)

    async def _compute_guarantee_chain_depth(self, entity: "EntityInstance") -> int:
        depth = 0
        visited: set[str] = set()
        current_ids: list[str] = []
        initial_guarantors = entity.data.get("guaranteed_by", [])
        for guarantor in initial_guarantors:
            guarantor_id = (
                str(guarantor.get("supplier_id", ""))
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

                guarantor_entity = await self.storage.get_entity("Supplier", current_id)
                if guarantor_entity is None:
                    continue
                guarantor_list = guarantor_entity.data.get("guaranteed_by", [])
                for guarantor in guarantor_list:
                    next_id = (
                        str(guarantor.get("supplier_id", ""))
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

        # Handle both legacy string algorithms and structured GraphAlgorithmDefinition
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
