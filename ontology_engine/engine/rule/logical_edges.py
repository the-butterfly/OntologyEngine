from __future__ import annotations

from enum import Enum
from typing import Any

from ontology_engine.storage.base import GraphStoreBackend


class LogicalEdgeType(str, Enum):
    CAUSAL = "causal"
    ENABLEMENT = "enablement"
    CORRELATION = "correlation"


CAUSAL_RELATIONS = {"LEADS_TO", "BECAUSE_OF"}
ENABLEMENT_RELATIONS = {"ENABLES", "PREVENTS"}
CORRELATION_RELATIONS = {"same_entity_as"}

EDGE_TYPE_MAP: dict[str, LogicalEdgeType] = {}
for _r in CAUSAL_RELATIONS:
    EDGE_TYPE_MAP[_r] = LogicalEdgeType.CAUSAL
for _r in ENABLEMENT_RELATIONS:
    EDGE_TYPE_MAP[_r] = LogicalEdgeType.ENABLEMENT
for _r in CORRELATION_RELATIONS:
    EDGE_TYPE_MAP[_r] = LogicalEdgeType.CORRELATION


class LogicalEdgeEngine:
    def __init__(self, graph_store: GraphStoreBackend | None = None):
        self._graph = graph_store

    @staticmethod
    def classify(relation_name: str) -> LogicalEdgeType | None:
        return EDGE_TYPE_MAP.get(relation_name)

    async def get_logical_edges(
        self,
        entity_id: str,
        edge_type: LogicalEdgeType | None = None,
        direction: str = "both",
        max_depth: int = 1,
    ) -> list[dict[str, Any]]:
        if not self._graph:
            return []
        edges: list[dict[str, Any]] = []
        visited: set[str] = {entity_id}
        frontier: list[str] = [entity_id]
        for depth in range(max_depth):
            next_frontier: list[str] = []
            for nid in frontier:
                neighbors = await self._graph.get_neighbors(
                    nid, direction=direction, limit=500
                )
                for n in neighbors:
                    rel_name = n.get("edge_type", n.get("relation_name", ""))
                    classified = self.classify(rel_name)
                    if classified is None:
                        continue
                    if edge_type is not None and classified != edge_type:
                        continue
                    target_id = n.get("neighbor_id", n.get("node_id", ""))
                    edges.append({
                        "from_entity_id": nid,
                        "to_entity_id": target_id,
                        "relation_name": rel_name,
                        "logical_type": classified.value,
                        "direction": n.get("direction", "outgoing"),
                        "data": n.get("properties", {}),
                        "depth": depth + 1,
                    })
                    if target_id not in visited:
                        visited.add(target_id)
                        next_frontier.append(target_id)
            frontier = next_frontier
        return edges

    async def trace_causal_chain(
        self,
        entity_id: str,
        direction: str = "forward",
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        return await self.get_logical_edges(
            entity_id,
            LogicalEdgeType.CAUSAL,
            direction="outgoing" if direction == "forward" else "incoming",
            max_depth=max_depth,
        )

    async def find_enablement(
        self,
        entity_id: str,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        return await self.get_logical_edges(
            entity_id, LogicalEdgeType.ENABLEMENT, direction="both", max_depth=max_depth
        )

    async def find_correlations(self, entity_id: str) -> list[dict[str, Any]]:
        return await self.get_logical_edges(
            entity_id, LogicalEdgeType.CORRELATION, direction="both", max_depth=1
        )
