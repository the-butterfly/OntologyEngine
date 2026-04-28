from __future__ import annotations

from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("graph_traversal")
class GraphTraversalOperator(Operator):
    name = "graph_traversal"

    async def execute(self, inputs: dict[str, Any], config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        params = {**config, **inputs}
        entity_id = params.get("entity_id", context.get("entity_id", ""))
        traversal_type = params.get("traversal_type", "bfs")
        edge_types = params.get("edge_types", [])
        max_depth = params.get("max_depth", 1)
        direction = params.get("direction", "outgoing")
        aggregation = params.get("aggregation", "count")
        target_field = params.get("target_field")
        output_key = params.get("output_key", "graph_aggregation")

        graph_store = context.get("graph_store")
        if graph_store is None:
            return {output_key: {"error": "graph_store not available in context"}}

        if not entity_id:
            return {output_key: {"error": "entity_id is required"}}

        try:
            visited: set[str] = set()
            all_nodes: list[dict[str, Any]] = []

            if traversal_type == "bfs":
                all_nodes = await self._bfs_traverse(
                    graph_store, entity_id, edge_types, max_depth, direction, visited
                )
            else:
                all_nodes = await self._dfs_traverse(
                    graph_store, entity_id, edge_types, max_depth, direction, visited
                )

            result = self._aggregate(all_nodes, aggregation, target_field)
            return {output_key: result}

        except Exception as e:
            return {output_key: {"error": str(e)}}

    async def _bfs_traverse(
        self,
        graph_store: Any,
        start_id: str,
        edge_types: list[str],
        max_depth: int,
        direction: str,
        visited: set[str],
    ) -> list[dict[str, Any]]:
        import asyncio

        nodes: list[dict[str, Any]] = []
        current_level = [start_id]
        visited.add(start_id)

        for depth in range(max_depth):
            next_level: list[str] = []
            tasks = [
                self._get_neighbors(graph_store, nid, edge_types, direction)
                for nid in current_level
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for nid, neighbors in zip(current_level, results):
                if isinstance(neighbors, Exception):
                    continue
                for neighbor in neighbors:
                    neighbor_id = neighbor.get("neighbor_id", neighbor.get("node_id", ""))
                    if neighbor_id and neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_level.append(neighbor_id)
                        node_data = await self._get_node_data(graph_store, neighbor_id)
                        nodes.append(node_data)

            current_level = next_level
            if not current_level:
                break

        return nodes

    async def _dfs_traverse(
        self,
        graph_store: Any,
        start_id: str,
        edge_types: list[str],
        max_depth: int,
        direction: str,
        visited: set[str],
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        stack: list[tuple[str, int]] = [(start_id, 0)]
        visited.add(start_id)

        while stack:
            node_id, depth = stack.pop()
            if depth >= max_depth:
                continue

            neighbors = await self._get_neighbors(graph_store, node_id, edge_types, direction)
            for neighbor in neighbors:
                neighbor_id = neighbor.get("neighbor_id", neighbor.get("node_id", ""))
                if neighbor_id and neighbor_id not in visited:
                    visited.add(neighbor_id)
                    stack.append((neighbor_id, depth + 1))
                    node_data = await self._get_node_data(graph_store, neighbor_id)
                    nodes.append(node_data)

        return nodes

    async def _get_neighbors(
        self,
        graph_store: Any,
        node_id: str,
        edge_types: list[str],
        direction: str,
    ) -> list[dict[str, Any]]:
        if edge_types:
            all_neighbors: list[dict[str, Any]] = []
            for et in edge_types:
                try:
                    neighbors = await graph_store.get_neighbors(
                        node_id, edge_type=et, direction=direction, limit=500
                    )
                    all_neighbors.extend(neighbors)
                except Exception:
                    continue
            return all_neighbors
        return await graph_store.get_neighbors(node_id, direction=direction, limit=500)

    async def _get_node_data(self, graph_store: Any, node_id: str) -> dict[str, Any]:
        try:
            node = await graph_store.get_node(node_id)
            if node:
                return {"id": node_id, "data": node}
        except Exception:
            pass
        return {"id": node_id, "data": {}}

    def _aggregate(
        self,
        nodes: list[dict[str, Any]],
        aggregation: str,
        target_field: str | None,
    ) -> dict[str, Any]:
        count = len(nodes)

        if aggregation == "count":
            return {"count": count}

        if aggregation == "collect":
            return {"count": count, "nodes": [n.get("id", "") for n in nodes]}

        if not target_field:
            return {"count": count, "error": "target_field required for numeric aggregation"}

        values = self._extract_field_values(nodes, target_field)
        if not values:
            return {"count": count, "value": None}

        if aggregation in ("sum",):
            return {"count": count, "value": sum(values)}
        if aggregation in ("average", "avg"):
            return {"count": count, "value": sum(values) / len(values)}
        if aggregation == "min":
            return {"count": count, "value": min(values)}
        if aggregation == "max":
            return {"count": count, "value": max(values)}

        return {"count": count}

    def _extract_field_values(self, nodes: list[dict[str, Any]], field: str) -> list[float]:
        values: list[float] = []
        for node in nodes:
            data = node.get("data", {})
            val = data.get(field)
            if val is None:
                props = data.get("properties", {})
                val = props.get(field) if isinstance(props, dict) else None
            if val is not None:
                try:
                    values.append(float(val))
                except (TypeError, ValueError):
                    continue
        return values



