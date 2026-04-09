# ontology_engine/engine/metric/engine.py
"""MetricEngine - DAG-based metric computation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from datetime import date, datetime, timedelta

import simpleeval

from ontology_engine.engine.metric.dag import MetricDAG
from ontology_engine.engine.metric.errors import (
    MetricError,
    MetricNotFoundError,
    MetricNotComputableError,
)
from ontology_engine.storage.duckdb import DuckDBStorage

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import MetricDefinition, KGMLSchema
    from ontology_engine.storage.duckdb import EntityInstance, RelationInstance


class MetricCache:
    """Simple in-memory cache for computed metrics."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], Any] = {}

    def get(self, entity_id: str, metric_name: str) -> Any | None:
        """Get cached metric value."""
        return self._cache.get((entity_id, metric_name))

    def set(self, entity_id: str, metric_name: str, value: Any) -> None:
        """Set cached metric value."""
        self._cache[(entity_id, metric_name)] = value

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def clear_entity(self, entity_id: str) -> None:
        """Clear cached values for an entity."""
        keys_to_delete = [k for k in self._cache if k[0] == entity_id]
        for key in keys_to_delete:
            del self._cache[key]


class MetricEngine:
    """DAG-based metric computation engine.

    Computes four types of metrics:
    - atomic: Direct attribute extraction or aggregation from relations
    - derived: Formula-based calculation using dependencies
    - composite: Weighted aggregation of multiple components
    - graph: NetworkX-based graph algorithms
    """

    def __init__(
        self,
        schema: "KGMLSchema",
        storage: DuckDBStorage,
        cache: MetricCache | None = None,
    ):
        """Initialize MetricEngine.

        Args:
            schema: KGMLSchema with metric definitions
            storage: DuckDBStorage instance
            cache: Optional MetricCache for caching computed values
        """
        self.schema = schema
        self.storage = storage
        self.cache = cache or MetricCache()
        self._metric_defs: dict[str, "MetricDefinition"] = {
            m.name: m for m in schema.metrics
        }
        self._dag = MetricDAG(schema.metrics)

    async def compute(
        self,
        metric_name: str,
        entity: "EntityInstance",
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Compute a single metric for an entity.

        Automatically handles dependencies by recursively computing them first.

        Args:
            metric_name: Name of the metric to compute
            entity: EntityInstance to compute metric for
            context: Optional additional context for evaluation

        Returns:
            Computed metric value

        Raises:
            MetricNotFoundError: If metric definition doesn't exist
        """
        metric_def = self._metric_defs.get(metric_name)
        if not metric_def:
            raise MetricNotFoundError(f"Metric '{metric_name}' not found in schema")

        # Check cache first
        cached = self.cache.get(entity.entity_id, metric_name)
        if cached is not None:
            return cached

        # Also check storage for persisted value
        stored = await self.storage.get_metric(entity.entity_id, metric_name)
        if stored is not None:
            self.cache.set(entity.entity_id, metric_name, stored)
            return stored

        # Ensure dependencies are computed
        dep_values: dict[str, Any] = {}
        for dep in metric_def.dependencies:
            dep_values[dep] = await self.compute(dep, entity, context)

        # Compute based on metric type
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

        # Cache and persist
        self.cache.set(entity.entity_id, metric_name, value)
        await self.storage.save_metric(entity.entity_id, metric_name, value)

        return value

    async def compute_batch(
        self,
        metric_names: list[str],
        entity: "EntityInstance",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compute multiple metrics for an entity in optimal order.

        Uses DAG topological sort to compute dependencies first.

        Args:
            metric_names: List of metric names to compute
            entity: EntityInstance to compute metrics for
            context: Optional additional context for evaluation

        Returns:
            Dict mapping metric names to computed values
        """
        # Get sorted order including all dependencies
        sorted_metrics = self._dag.topological_order(metric_names)

        results: dict[str, Any] = {}
        for name in sorted_metrics:
            if name not in results:
                # Check cache
                cached = self.cache.get(entity.entity_id, name)
                if cached is not None:
                    results[name] = cached
                else:
                    results[name] = await self.compute(name, entity, context)

        return {name: results[name] for name in metric_names}

    def _collect_dependencies(self, metric_names: list[str]) -> set[str]:
        """Collect all transitive dependencies for given metrics."""
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
        """Compute atomic metric - direct extraction or simple aggregation.

        Examples:
        - total_invoice_amount_90d: aggregate from Invoice relations
        - overdue_invoice_amount: aggregate OVERDUE invoices
        """
        name = metric_def.name

        # Check if it's a pre-computed attribute on entity
        if name in entity.data:
            return entity.data[name]

        # Handle supply chain finance-specific atomic metrics
        # These aggregate from related entities
        if name == "total_invoice_amount_90d":
            return await self._aggregate_invoice_amount(entity, days=90)
        elif name == "overdue_invoice_amount":
            return await self._aggregate_overdue_invoice_amount(entity)
        elif name == "invoice_count_90d":
            return await self._count_invoices_90d(entity)
        elif name == "total_contract_amount":
            return await self._aggregate_contract_amount(entity)
        elif name == "core_enterprise_count":
            return await self._count_core_enterprises(entity)
        elif name == "guarantee_chain_depth":
            return await self._compute_guarantee_chain_depth(entity)
        elif name == "has_guarantee_circle":
            depth = await self._compute_guarantee_chain_depth(entity)
            return depth >= 3

        # Default: check entity attributes
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
        """Aggregate total invoice amount from related invoices."""
        cutoff = date.today() - timedelta(days=days)
        total = 0.0

        neighbors, _ = await self._get_neighbors_with_relations(
            entity.entity_id, "has_invoice", "outgoing"
        )

        for neighbor, _ in neighbors:
            amount = neighbor.data.get("amount", {})
            if isinstance(amount, dict):
                val = amount.get("value", 0)
            else:
                val = amount or 0

            issue_date_str = neighbor.data.get("issue_date", "")
            if issue_date_str:
                try:
                    issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                    if issue_date >= cutoff:
                        total += val
                except (ValueError, TypeError):
                    pass

        return {"value": total, "currency": "CNY"}

    async def _aggregate_overdue_invoice_amount(
        self,
        entity: "EntityInstance",
    ) -> dict[str, Any]:
        """Aggregate overdue invoice amount from related invoices."""
        total = 0.0

        neighbors, _ = await self._get_neighbors_with_relations(
            entity.entity_id, "has_invoice", "outgoing"
        )

        for neighbor, _ in neighbors:
            if neighbor.data.get("status") == "OVERDUE":
                amount = neighbor.data.get("amount", {})
                if isinstance(amount, dict):
                    val = amount.get("value", 0)
                else:
                    val = amount or 0
                total += val

        return {"value": total, "currency": "CNY"}

    async def _count_invoices_90d(
        self,
        entity: "EntityInstance",
    ) -> int:
        """Count invoices from the last 90 days."""
        cutoff = date.today() - timedelta(days=90)
        count = 0

        neighbors, _ = await self._get_neighbors_with_relations(
            entity.entity_id, "has_invoice", "outgoing"
        )

        for neighbor, _ in neighbors:
            issue_date_str = neighbor.data.get("issue_date", "")
            if issue_date_str:
                try:
                    issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                    if issue_date >= cutoff:
                        count += 1
                except (ValueError, TypeError):
                    pass

        return count

    async def _aggregate_contract_amount(
        self,
        entity: "EntityInstance",
    ) -> dict[str, Any]:
        """Aggregate total contract amount from related contracts."""
        total = 0.0

        neighbors, _ = await self._get_neighbors_with_relations(
            entity.entity_id, "has_contract", "outgoing"
        )

        for neighbor, _ in neighbors:
            amount = neighbor.data.get("contract_amount", {})
            if isinstance(amount, dict):
                val = amount.get("value", 0)
            else:
                val = amount or 0
            total += val

        return {"value": total, "currency": "CNY"}

    async def _count_core_enterprises(
        self,
        entity: "EntityInstance",
    ) -> int:
        """Count core enterprises (direct suppliers)."""
        neighbors, _ = await self._get_neighbors_with_relations(
            entity.entity_id, "supplies_to", "outgoing"
        )
        return len(neighbors)

    async def _compute_guarantee_chain_depth(
        self,
        entity: "EntityInstance",
    ) -> int:
        """Compute guarantee chain depth by traversing guaranteed_by relations."""
        depth = 0
        visited: set[str] = set()

        # Start with direct guarantors
        current_ids: list[str] = []
        initial_guarantors = entity.data.get("guaranteed_by", [])
        for g in initial_guarantors:
            gid = str(g.get("supplier_id", "")) if isinstance(g, dict) else str(g) if g else ""
            if gid:
                current_ids.append(gid)

        while current_ids and len(visited) < 10:
            depth += 1
            next_ids: list[str] = []
            for cid in current_ids:
                if cid in visited:
                    # Cycle detected - this is a guarantee circle
                    depth += 1
                    break
                visited.add(cid)

                # Get the guarantor's guarantors
                guarantor_entity = await self.storage.get_entity("Supplier", cid)
                if guarantor_entity:
                    guarantor_list = guarantor_entity.data.get("guaranteed_by", [])
                    for g in guarantor_list:
                        next_id = str(g.get("supplier_id", "")) if isinstance(g, dict) else str(g) if g else ""
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
    ) -> tuple[list[tuple["EntityInstance", "RelationInstance"]], list[Any]]:
        """Get neighboring entities and their relations."""
        return await self.storage.get_neighbors(entity_id, relation_type, direction)

    async def _compute_derived(
        self,
        metric_def: "MetricDefinition",
        entity: "EntityInstance",
        dep_values: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> Any:
        """Compute derived metric using formula evaluation."""
        if not metric_def.formula:
            raise MetricError(f"Derived metric '{metric_def.name}' missing formula")

        # Build evaluation context
        eval_context = self._build_eval_context(entity, dep_values, context)

        # Evaluate formula using simpleeval
        try:
            evaluator = simpleeval.SimpleEval()
            evaluator.names = eval_context
            result = evaluator.eval(metric_def.formula)
        except Exception as e:
            raise MetricError(f"Failed to evaluate formula '{metric_def.formula}': {e}")

        # Type adaptation
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
        """Compute composite metric using formula evaluation.

        Phase 1 uses formula-based composite metrics.
        Future versions may support component-based weighted aggregation.
        """
        if not metric_def.formula:
            raise MetricError(f"Composite metric '{metric_def.name}' missing formula")

        eval_context = self._build_eval_context(entity, dep_values, context)
        try:
            evaluator = simpleeval.SimpleEval()
            evaluator.names = eval_context
            result = evaluator.eval(metric_def.formula)
        except Exception as e:
            raise MetricError(f"Failed to evaluate formula '{metric_def.formula}': {e}")

        # Clip to output range if specified
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
        """Compute graph metric using NetworkX algorithms.

        Phase 1 uses simplified implementations without full NetworkX graph store.
        """
        algorithm = getattr(metric_def, "algorithm", None)

        if algorithm == "longest_path":
            return await self._compute_guarantee_chain_depth(entity)
        elif algorithm == "cycle_detection":
            depth = await self._compute_guarantee_chain_depth(entity)
            return depth >= 3
        elif algorithm == "page_rank":
            # Simplified: count connections as proxy
            neighbors, _ = await self._get_neighbors_with_relations(
                entity.entity_id, "guarantees_for", "outgoing"
            )
            return round(len(neighbors) / 10.0, 4)
        elif algorithm == "betweenness":
            # Simplified: use depth as proxy
            depth = await self._compute_guarantee_chain_depth(entity)
            return round(depth / 10.0, 4)

        raise MetricError(f"Unknown graph algorithm: {algorithm}")

    def _build_eval_context(
        self,
        entity: "EntityInstance",
        dep_values: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build evaluation context for formula evaluation."""
        eval_ctx: dict[str, Any] = {}

        # Entity attributes (flatten nested)
        for key, value in entity.data.items():
            if isinstance(value, dict) and "value" in value:
                eval_ctx[key] = value["value"]
            else:
                eval_ctx[key] = value

        # Add entity_id
        eval_ctx["entity_id"] = entity.entity_id

        # Dependency metric values (flatten dicts with "value" key)
        for dep_name, dep_value in dep_values.items():
            if isinstance(dep_value, dict) and "value" in dep_value:
                eval_ctx[dep_name] = dep_value["value"]
            else:
                eval_ctx[dep_name] = dep_value

        # External context (overrides)
        if context:
            eval_ctx.update(context)

        return eval_ctx

    def _to_numeric(self, value: Any) -> float:
        """Convert metric value to numeric."""
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
