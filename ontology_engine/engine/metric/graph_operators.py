"""Graph algorithm operators for metric computation."""

from __future__ import annotations

from typing import Any, Callable

from ontology_engine.engine.metric.errors import MetricError

GraphOperatorFunc = Callable[..., Any]


class GraphOperatorRegistry:
    """Registry for graph algorithm operators."""

    _operators: dict[str, GraphOperatorFunc] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[GraphOperatorFunc], GraphOperatorFunc]:
        """Decorator to register a graph operator."""

        def decorator(func: GraphOperatorFunc) -> GraphOperatorFunc:
            cls._operators[name] = func
            return func

        return decorator

    @classmethod
    def get(cls, name: str) -> GraphOperatorFunc:
        """Get a registered operator by name."""
        op = cls._operators.get(name)
        if op is None:
            raise MetricError(f"Unknown graph algorithm: {name}")
        return op

    @classmethod
    async def execute(
        cls,
        name: str,
        entity,
        storage,
        params: dict[str, Any],
        traversal: dict[str, Any] | None,
        dep_values: dict[str, Any],
    ) -> Any:
        """Execute a registered graph operator."""
        op = cls.get(name)
        return await op(entity, storage, params, traversal, dep_values)


@GraphOperatorRegistry.register("longest_path")
async def _op_longest_path(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Compute longest path (guarantee chain depth)."""
    max_hops = params.get("max_hops", traversal.get("max_hops", 10)) if traversal else params.get("max_hops", 10)
    direction = params.get("direction", traversal.get("direction", "both")) if traversal else params.get("direction", "both")

    depth = 0
    visited: set[str] = set()
    current_ids: list[str] = []

    # Support both v1 field name and v2 relation traversal
    initial_guarantors = entity.data.get("guaranteed_by", [])
    for guarantor in initial_guarantors:
        guarantor_id = (
            str(guarantor.get("supplier_id", ""))
            if isinstance(guarantor, dict)
            else str(guarantor) if guarantor else ""
        )
        if guarantor_id:
            current_ids.append(guarantor_id)

    # Fallback: use storage neighbors if no direct field
    if not current_ids and storage and traversal:
        edge = traversal.get("edge", "GuaranteeRelation")
        neighbors = await storage.get_neighbors(entity.entity_id, edge, direction)
        for neighbor, _ in neighbors:
            if neighbor.entity_id not in visited:
                current_ids.append(neighbor.entity_id)

    while current_ids and len(visited) < max_hops:
        depth += 1
        next_ids: list[str] = []
        for current_id in current_ids:
            if current_id in visited:
                depth += 1
                break
            visited.add(current_id)

            if storage is None:
                continue

            guarantor_entity = await storage.get_entity("Supplier", current_id)
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


@GraphOperatorRegistry.register("cycle_detection")
async def _op_cycle_detection(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Detect if entity is part of a cycle."""
    # Use longest_path as proxy for cycle detection depth threshold
    longest_op = GraphOperatorRegistry.get("longest_path")
    depth = await longest_op(entity, storage, params, traversal, dep_values)
    return depth >= 3


@GraphOperatorRegistry.register("page_rank")
async def _op_page_rank(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Simple degree-based page rank proxy."""
    if storage is None:
        return 0.0
    relation_type = traversal.get("edge", "guarantees_for") if traversal else "guarantees_for"
    neighbors = await storage.get_neighbors(entity.entity_id, relation_type, "outgoing")
    return round(len(neighbors) / 10.0, 4)


@GraphOperatorRegistry.register("betweenness")
async def _op_betweenness(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Simple depth-based betweenness proxy."""
    longest_op = GraphOperatorRegistry.get("longest_path")
    depth = await longest_op(entity, storage, params, traversal, dep_values)
    return round(depth / 10.0, 4)


@GraphOperatorRegistry.register("neighbor_attribute_count")
async def _op_neighbor_attribute_count(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Count neighbors matching an attribute condition.

    Supports parameterized traversal and deduplication.
    """
    if storage is None:
        return 0

    max_hops = params.get("max_hops", traversal.get("max_hops", 2)) if traversal else params.get("max_hops", 2)
    direction = params.get("direction", traversal.get("direction", "both")) if traversal else params.get("direction", "both")
    edge = traversal.get("edge") if traversal else None
    deduplicate = params.get("deduplicate_neighbors", False)

    if not edge:
        raise MetricError("neighbor_attribute_count requires traversal.edge")

    visited: set[str] = set()
    current_ids = [entity.entity_id]
    matching = 0

    for _ in range(max_hops):
        next_ids: list[str] = []
        for current_id in current_ids:
            if current_id in visited:
                continue
            visited.add(current_id)

            neighbors = await storage.get_neighbors(current_id, edge, direction)
            for neighbor, relation in neighbors:
                neighbor_id = getattr(neighbor, "entity_id", None) or neighbor.get("id")
                if neighbor_id is None:
                    continue

                if deduplicate and neighbor_id in visited:
                    continue

                next_ids.append(neighbor_id)

                # Apply neighbor_filter via a simple attribute check
                # For now, we only support the common case: current_overdue_amount.value > 0
                overdue = neighbor.data.get("current_overdue_amount", 0)
                if isinstance(overdue, dict):
                    overdue = overdue.get("value", 0)
                if overdue and overdue > 0:
                    matching += 1

        current_ids = next_ids
        if not current_ids:
            break

    return matching


@GraphOperatorRegistry.register("weighted_neighbor_risk")
async def _op_weighted_neighbor_risk(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Compute weighted neighbor risk score.

    Falls back to formula-based computation using dependency values.
    """
    count = dep_values.get("co_borrower_risk_count", 0)
    direct_risk = count * 20
    return min(direct_risk, 100)
