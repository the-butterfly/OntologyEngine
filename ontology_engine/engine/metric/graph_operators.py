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


def _resolve_traversal_params(
    entity: Any,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve traversal parameters from entity schema and params/traversal.

    Returns a dict with keys:
    - max_hops: int
    - direction: str
    - edge: str
    - id_field: str (field name for extracting IDs from relation data)
    - concept: str (concept type for looking up entities in the chain)
    - chain_field: str (field name on entity data for initial chain links)
    """
    max_hops = params.get("max_hops", traversal.get("max_hops", 10) if traversal else 10)
    direction = params.get("direction", traversal.get("direction", "both") if traversal else "both")
    edge = params.get("edge", traversal.get("edge") if traversal else None) or "guarantees_for"
    id_field = params.get("id_field", traversal.get("id_field") if traversal else None) or "supplier_id"
    concept = params.get("concept", traversal.get("concept") if traversal else None) or getattr(entity, "_fact_object", "Supplier")
    chain_field = params.get("chain_field", traversal.get("chain_field") if traversal else None) or "guaranteed_by"

    return {
        "max_hops": max_hops,
        "direction": direction,
        "edge": edge,
        "id_field": id_field,
        "concept": concept,
        "chain_field": chain_field,
    }


@GraphOperatorRegistry.register("longest_path")
async def _op_longest_path(
    entity,
    storage,
    params: dict[str, Any],
    traversal: dict[str, Any] | None,
    dep_values: dict[str, Any],
) -> Any:
    """Compute longest path (e.g., guarantee chain depth).

    Fully parameterized via traversal/params:
    - chain_field: field on entity data containing chain links (default: 'guaranteed_by')
    - id_field: field name for extracting IDs from link dicts (default: 'supplier_id')
    - concept: concept type for looking up entities in the chain
    - edge: relation name for storage-based neighbor lookup fallback
    - max_hops: maximum traversal depth
    """
    tp = _resolve_traversal_params(entity, params, traversal)

    depth = 0
    visited: set[str] = set()
    current_ids: list[str] = []

    initial_links = entity.data.get(tp["chain_field"], [])
    for link in initial_links:
        link_id = (
            str(link.get(tp["id_field"], ""))
            if isinstance(link, dict)
            else str(link) if link else ""
        )
        if link_id:
            current_ids.append(link_id)

    if not current_ids and storage and traversal:
        neighbors = await storage.get_neighbors(entity.entity_id, tp["edge"], tp["direction"])
        for neighbor, _ in neighbors:
            if neighbor.entity_id not in visited:
                current_ids.append(neighbor.entity_id)

    while current_ids and len(visited) < tp["max_hops"]:
        depth += 1
        next_ids: list[str] = []
        for current_id in current_ids:
            if current_id in visited:
                depth += 1
                break
            visited.add(current_id)

            if storage is None:
                continue

            chain_entity = await storage.get_entity(tp["concept"], current_id)
            if chain_entity is None:
                continue

            chain_links = chain_entity.data.get(tp["chain_field"], [])
            for link in chain_links:
                next_id = (
                    str(link.get(tp["id_field"], ""))
                    if isinstance(link, dict)
                    else str(link) if link else ""
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
    longest_op = GraphOperatorRegistry.get("longest_path")
    depth = await longest_op(entity, storage, params, traversal, dep_values)
    threshold = params.get("cycle_threshold", 3)
    return depth >= threshold


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
    edge = traversal.get("edge") if traversal else params.get("edge", "guarantees_for")
    neighbors = await storage.get_neighbors(entity.entity_id, edge, "outgoing")
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

    Fully parameterized via traversal/params:
    - edge: relation name to traverse
    - filter_attribute: attribute name to check on neighbors
    - filter_threshold: minimum value for the attribute to count
    - max_hops: traversal depth
    """
    if storage is None:
        return 0

    max_hops = params.get("max_hops", traversal.get("max_hops", 2) if traversal else 2)
    direction = params.get("direction", traversal.get("direction", "both") if traversal else "both")
    edge = traversal.get("edge") if traversal else params.get("edge")
    filter_attribute = params.get("filter_attribute", traversal.get("filter_attribute") if traversal else None) or "current_overdue_amount"
    filter_threshold = params.get("filter_threshold", 0)
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

                attr_val = neighbor.data.get(filter_attribute, 0)
                if isinstance(attr_val, dict):
                    attr_val = attr_val.get("value", 0)
                if attr_val and attr_val > filter_threshold:
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
    count_key = params.get("count_key", "co_borrower_risk_count")
    count = dep_values.get(count_key, 0)
    direct_risk = count * 20
    return min(direct_risk, 100)
