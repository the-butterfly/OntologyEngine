# ontology_engine/storage/dual_write.py
"""Dual-write coordinator for DuckDB + GraphStore synchronization."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ontology_engine.storage.base import (
    EntityInstance,
    GraphStoreBackend,
    RelationInstance,
    StorageBackend,
)

logger = logging.getLogger(__name__)


class DualWriteCoordinator:
    """Coordinates writes between DuckDB (attribute storage) and GraphStore (topology).

    Write flow:
    1. Write to DuckDB first (strong consistency)
    2. Async write to GraphStore (eventual consistency, failure logged)
    3. Periodic reconciliation compares both sides

    Read flow:
    1. Attribute queries -> DuckDB only
    2. Graph queries (neighbors/paths/cycles) -> GraphStore only
    3. Hybrid queries -> GraphStore for topology + DuckDB for attributes
    """

    def __init__(
        self,
        storage: StorageBackend,
        graph_store: GraphStoreBackend | None = None,
    ):
        self.storage = storage
        self.graph = graph_store
        self._sync_failures: list[dict[str, Any]] = []

    @property
    def graph_enabled(self) -> bool:
        return self.graph is not None

    async def save_entity_with_graph(
        self,
        entity: EntityInstance,
        relations: list[RelationInstance] | None = None,
    ) -> str:
        """Save entity to DuckDB and sync to GraphStore."""
        # Step 1: Write to DuckDB (strong consistency)
        entity_id = await self.storage.save_entity(entity)

        # Step 2: Write to GraphStore (eventual consistency)
        if self.graph:
            try:
                await self.graph.upsert_node(
                    node_id=entity.entity_id,
                    labels=[entity.concept],
                    properties=entity.data,
                )
            except Exception as e:
                self._log_sync_failure("upsert_node", entity.entity_id, e)
                logger.warning(f"Graph sync failed for node {entity.entity_id}: {e}")

        # Step 3: Write relations
        if relations:
            for rel in relations:
                await self.storage.save_relation(rel)
                if self.graph:
                    try:
                        edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_type}"
                        await self.graph.upsert_edge(
                            edge_id=edge_id,
                            from_node_id=rel.from_entity_id,
                            to_node_id=rel.to_entity_id,
                            edge_type=rel.relation_type,
                            properties=rel.data or {},
                        )
                    except Exception as e:
                        self._log_sync_failure("upsert_edge", rel.relation_type, e)
                        logger.warning(f"Graph sync failed for edge: {e}")

        return entity_id

    async def get_neighbor_details(
        self,
        entity_id: str,
        relation_type: str,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Hybrid query: GraphStore for topology + DuckDB for attributes."""
        if not self.graph:
            # Fallback: use DuckDB get_neighbors
            neighbors = await self.storage.get_neighbors(entity_id, relation_type, direction)
            return [
                {
                    "entity": {"entity_id": e.entity_id, "concept": e.concept, "data": e.data},
                    "relation": {"relation_type": r.relation_type, "data": r.data},
                }
                for e, r in neighbors
            ]

        # Get topology from GraphStore
        graph_neighbors = await self.graph.get_neighbors(
            node_id=entity_id, edge_type=relation_type, direction=direction
        )

        results = []
        for gn in graph_neighbors:
            neighbor_id = gn["neighbor_id"]
            # Get full entity from DuckDB
            entity = await self.storage.get_entity(concept=None, entity_id=neighbor_id)
            if entity:
                results.append({
                    "entity": {"entity_id": entity.entity_id, "concept": entity.concept, "data": entity.data},
                    "relation": {
                        "edge_id": gn.get("edge_id"),
                        "edge_type": gn.get("edge_type"),
                        "direction": gn.get("direction"),
                    },
                })

        return results

    async def batch_sync_from_storage(self) -> dict[str, int]:
        """Full sync: load all entities/relations from DuckDB into GraphStore."""
        if not self.graph:
            return {"nodes_written": 0, "edges_written": 0, "error": "graph_store_not_configured"}

        # Load all entities from DuckDB
        all_entities = await self.storage.query_entities(concept=None)
        nodes = []
        for entity in all_entities:
            nodes.append({
                "node_id": entity.entity_id,
                "labels": [entity.concept],
                "properties": entity.data,
            })

        # Load all relations
        edges = []
        for entity in all_entities:
            relations = await self.storage.get_relations(entity.entity_id)
            for rel in relations:
                edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_type}"
                edges.append({
                    "edge_id": edge_id,
                    "from_node_id": rel.from_entity_id,
                    "to_node_id": rel.to_entity_id,
                    "edge_type": rel.relation_type,
                    "properties": rel.data or {},
                })

        result = await self.graph.batch_upsert(nodes=nodes, edges=edges)
        logger.info(f"Batch sync completed: {result}")
        return result

    def get_sync_failures(self) -> list[dict[str, Any]]:
        """Get list of sync failures for debugging."""
        return list(self._sync_failures)

    def _log_sync_failure(self, operation: str, target: str, error: Exception) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "target": target,
            "error": str(error),
        }
        self._sync_failures.append(entry)
        if len(self._sync_failures) > 1000:
            self._sync_failures = self._sync_failures[-500:]
