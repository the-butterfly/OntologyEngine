# ontology_engine/storage/graph/networkx_store.py
"""NetworkX-based in-memory graph store.

This is the default graph store implementation that uses NetworkX
for graph algorithms. It operates entirely in-memory and is suitable
for small to medium graphs.

For larger graphs or production use, consider LadybugGraphStore.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

import networkx as nx

from ontology_engine.storage.base import GraphQueryError, GraphStoreBackend

logger = logging.getLogger(__name__)


class NetworkXGraphStore(GraphStoreBackend):
    """NetworkX-based in-memory graph store.

    Data model:
    - Nodes: stored as NetworkX nodes with attributes
    - Edges: stored as NetworkX directed edges with attributes
    - Labels: stored as node attribute '_labels'
    """

    def __init__(self):
        self._graph = nx.MultiDiGraph()
        self._node_properties: dict[str, dict[str, Any]] = {}
        self._edge_properties: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self, db_path: str | None = None) -> None:
        """Initialize the in-memory graph store."""
        self._graph = nx.MultiDiGraph()
        self._node_properties = {}
        self._edge_properties = {}
        self._initialized = True
        logger.info("NetworkX graph store initialized (in-memory)")

    async def close(self) -> None:
        """Clear all graph data."""
        self._graph.clear()
        self._node_properties.clear()
        self._edge_properties.clear()
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise GraphQueryError("Graph store not initialized. Call initialize() first.")

    # --- Node Management ---

    async def upsert_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> None:
        self._ensure_initialized()
        self._graph.add_node(node_id)
        self._node_properties[node_id] = {
            "_labels": labels,
            **properties,
        }

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        if node_id not in self._graph:
            return None
        return {
            "id": node_id,
            **self._node_properties.get(node_id, {}),
        }

    async def delete_node(self, node_id: str) -> None:
        self._ensure_initialized()
        self._graph.remove_node(node_id)
        self._node_properties.pop(node_id, None)

    # --- Edge Management ---

    async def upsert_edge(
        self,
        edge_id: str,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self._ensure_initialized()
        # Ensure nodes exist
        if from_node_id not in self._graph:
            self._graph.add_node(from_node_id)
            self._node_properties.setdefault(from_node_id, {"_labels": []})
        if to_node_id not in self._graph:
            self._graph.add_node(to_node_id)
            self._node_properties.setdefault(to_node_id, {"_labels": []})

        # Remove existing edge with same key if present
        if self._graph.has_edge(from_node_id, to_node_id, edge_id):
            self._graph.remove_edge(from_node_id, to_node_id, edge_id)

        edge_props = {"_edge_id": edge_id, "_type": edge_type}
        if properties:
            edge_props.update(properties)
        self._graph.add_edge(from_node_id, to_node_id, key=edge_id, **edge_props)
        self._edge_properties[edge_id] = edge_props

    async def get_edges(
        self,
        from_node_id: str | None = None,
        to_node_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        results = []
        for u, v, key, data in self._graph.edges(keys=True, data=True):
            if from_node_id and u != from_node_id:
                continue
            if to_node_id and v != to_node_id:
                continue
            if edge_type and data.get("_type") != edge_type:
                continue
            results.append({
                "edge_id": key,
                "from_node_id": u,
                "to_node_id": v,
                "edge_type": data.get("_type"),
                "properties": {k: val for k, val in data.items() if not k.startswith("_")},
            })
        return results

    async def delete_edge(self, edge_id: str) -> None:
        self._ensure_initialized()
        for u, v, key in list(self._graph.edges(keys=True)):
            if key == edge_id:
                self._graph.remove_edge(u, v, key)
                self._edge_properties.pop(edge_id, None)
                break

    # --- Graph Queries ---

    async def get_neighbors_basic(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node (generic graph parameters only).

        Pure graph-topology query — no concept or temporal filtering.
        """
        self._ensure_initialized()
        if node_id not in self._graph:
            return []

        neighbors = []
        if direction in ("outgoing", "both"):
            for _, neighbor, key, data in self._graph.out_edges(node_id, keys=True, data=True):
                if edge_type and data.get("_type") != edge_type:
                    continue
                if filter_props:
                    if not all(data.get(k) == v for k, v in filter_props.items()):
                        continue
                neighbors.append({
                    "neighbor_id": neighbor,
                    "edge_id": key,
                    "edge_type": data.get("_type"),
                    "direction": "outgoing",
                })
        if direction in ("incoming", "both"):
            for source, _, key, data in self._graph.in_edges(node_id, keys=True, data=True):
                if edge_type and data.get("_type") != edge_type:
                    continue
                if filter_props:
                    if not all(data.get(k) == v for k, v in filter_props.items()):
                        continue
                neighbors.append({
                    "neighbor_id": source,
                    "edge_id": key,
                    "edge_type": data.get("_type"),
                    "direction": "incoming",
                })

        return neighbors[:limit]

    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
        node_concept: str | None = None,
        as_of: str | None = None,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node.

        Delegates to ``get_neighbors_basic()`` for graph topology, then
        applies cognitive-layer filters (node_concept, as_of,
        include_history) in-memory.  NetworkX does not store concept or
        temporal metadata natively, so these filters are best-effort.

        Note: ``node_concept`` filtering checks node properties for a
        ``_labels`` match.  ``as_of`` / ``include_history`` are not
        supported by NetworkX — use Ladybug for temporal queries.
        """
        neighbors = await self.get_neighbors_basic(
            node_id=node_id,
            edge_type=edge_type,
            direction=direction,
            limit=limit,
            filter_props=filter_props,
        )

        # Apply node_concept filter in-memory
        if node_concept and neighbors:
            filtered = []
            for n in neighbors:
                nid = n["neighbor_id"]
                props = self._node_properties.get(nid, {})
                labels = props.get("_labels", [])
                if node_concept in labels:
                    filtered.append(n)
            neighbors = filtered

        # as_of and include_history are not supported by NetworkX
        # (no temporal metadata stored) — return as-is

        return neighbors

    async def get_k_hop_neighbors(
        self,
        node_id: str,
        k: int = 2,
        edge_type: str | None = None,
        direction: str = "both",
        limit_per_hop: int = 100,
    ) -> dict[str, float]:
        """Get all neighbors within k hops using NetworkX BFS.

        Args:
            node_id: Starting node ID.
            k: Number of hops (depth). Defaults to 2.
            edge_type: Optional edge type filter.
            direction: Traversal direction ("outgoing", "incoming", "both").
            limit_per_hop: Max neighbors per node per hop.

        Returns:
            Dict mapping neighbor_id → proximity score (1/(1+depth)).
        """
        self._ensure_initialized()
        if node_id not in self._graph:
            return {}

        visited: set[str] = {node_id}
        scores: dict[str, float] = {}
        current_level: list[str] = [node_id]

        for depth in range(k):
            next_level: list[str] = []
            for nid in current_level:
                neighbors_raw = await self.get_neighbors(
                    node_id=nid,
                    edge_type=edge_type,
                    direction=direction,
                    limit=limit_per_hop,
                )
                for n in neighbors_raw:
                    neighbor_id = n["neighbor_id"]
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_level.append(neighbor_id)
                        scores[neighbor_id] = max(
                            scores.get(neighbor_id, 0.0),
                            1.0 / (1.0 + depth),
                        )
            current_level = next_level
            if not current_level:
                break

        return scores

    async def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_depth: int = 3,
        edge_types: list[str] | None = None,
    ) -> list[list[dict]]:
        self._ensure_initialized()
        if source_id not in self._graph:
            return []

        if target_id:
            results = []
            try:
                for path in nx.all_simple_paths(self._graph, source_id, target_id, cutoff=max_depth):
                    path_list = []
                    for i, node in enumerate(path):
                        node_info = {"node_id": node, **self._node_properties.get(node, {})}
                        path_list.append(node_info)
                        if i < len(path) - 1:
                            edge_data = self._graph.get_edge_data(path[i], path[i + 1])
                            edge_key = list(edge_data.keys())[0] if edge_data else None
                            path_list.append({
                                "edge_id": edge_key,
                                "edge_type": edge_data[edge_key].get("_type") if edge_data and edge_key else None,
                            })
                    results.append(path_list)
            except nx.NetworkXNoPath:
                pass
            return results
        else:
            visited = {source_id}
            queue = deque([(source_id, [source_id])])
            results = []
            while queue and len(results) < 50:
                current, path = queue.popleft()
                if len(path) > max_depth + 1:
                    continue
                results.append([{"node_id": n, **self._node_properties.get(n, {})} for n in path])
                for neighbor in self._graph.successors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
            return results

    async def detect_cycles(
        self,
        center_id: str,
        edge_types: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[list[str]]:
        self._ensure_initialized()
        if center_id not in self._graph:
            return []

        cycles: list[list[str]] = []

        def _dfs(current: str, path: list[str], visited: set[str]) -> None:
            if len(path) > max_depth:
                return
            for neighbor in self._graph.successors(current):
                if neighbor == center_id and len(path) > 1:
                    cycles.append(path + [center_id])
                elif neighbor not in visited:
                    visited.add(neighbor)
                    _dfs(neighbor, path + [neighbor], visited)
                    visited.discard(neighbor)

        _dfs(center_id, [center_id], {center_id})
        return cycles

    async def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        raise GraphQueryError(
            "Cypher queries are not supported by NetworkX store. "
            "Use dedicated graph query methods instead."
        )

    async def compute_graph_metric(
        self,
        algorithm: str,
        node_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_initialized()
        config = config or {}

        if algorithm == "centrality":
            metric_type = config.get("metric", "betweenness")
            if metric_type == "betweenness":
                cent = nx.betweenness_centrality(self._graph)
            elif metric_type == "closeness":
                cent = nx.closeness_centrality(self._graph)
            elif metric_type == "pagerank":
                cent = nx.pagerank(self._graph)
            else:
                cent = nx.degree_centrality(self._graph)
            if node_id:
                return {"algorithm": algorithm, "metric": metric_type, "node_id": node_id, "value": cent.get(node_id, 0.0)}
            return {"algorithm": algorithm, "metric": metric_type, "values": dict(cent)}

        elif algorithm == "component":
            if self._graph.is_directed():
                components = list(nx.weakly_connected_components(self._graph))
            else:
                components = list(nx.connected_components(self._graph))
            result: dict[str, Any] = {"algorithm": algorithm, "component_count": len(components)}
            if node_id:
                for i, comp in enumerate(components):
                    if node_id in comp:
                        result["node_component"] = i
                        break
            return result

        elif algorithm == "community":
            from networkx.algorithms.community import greedy_modularity_communities
            communities = list(greedy_modularity_communities(self._graph.to_undirected()))
            result = {"algorithm": algorithm, "community_count": len(communities)}
            if node_id:
                for i, comm in enumerate(communities):
                    if node_id in comm:
                        result["node_community"] = i
                        break
            return result

        else:
            raise GraphQueryError(f"Unknown graph algorithm: {algorithm}")

    # --- Batch Operations ---

    async def batch_upsert(
        self,
        nodes: list[dict] | None = None,
        edges: list[dict] | None = None,
    ) -> dict[str, int]:
        self._ensure_initialized()
        nodes_written = 0
        edges_written = 0

        if nodes:
            for node in nodes:
                await self.upsert_node(
                    node_id=node["node_id"],
                    labels=node.get("labels", []),
                    properties=node.get("properties", {}),
                )
                nodes_written += 1

        if edges:
            for edge in edges:
                await self.upsert_edge(
                    edge_id=edge["edge_id"],
                    from_node_id=edge["from_node_id"],
                    to_node_id=edge["to_node_id"],
                    edge_type=edge["edge_type"],
                    properties=edge.get("properties"),
                )
                edges_written += 1

        return {"nodes_written": nodes_written, "edges_written": edges_written}
