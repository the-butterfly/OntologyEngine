# ontology_engine/storage/dual_write.py
"""Three-engine write coordinator for MetaStore + GraphStore + VectorStore synchronization.

Write flow:
1. Write to MetaStore (SQLite) first (strong consistency)
2. Async write to GraphStore (Ladybug) (eventual consistency, failure logged)
3. Async write to VectorStore (ChromaDB) (eventual consistency, failure logged)
4. Compensating transaction on failure

Read flow:
1. Attribute queries -> MetaStore only
2. Graph queries (neighbors/paths/cycles) -> GraphStore only
3. Semantic queries -> VectorStore only
4. Hybrid queries -> GraphStore for topology + MetaStore for attributes
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ontology_engine.storage.base import (
    CompensationStore,
    EntityInstance,
    GraphStoreBackend,
    RelationInstance,
    StorageBackend,
    VectorStoreBackend,
)

logger = logging.getLogger(__name__)


class DualWriteCoordinator:
    """Coordinates writes across MetaStore + GraphStore + VectorStore.

    Three-engine write flow:
    1. Write to MetaStore (strong consistency) - always succeeds or raises
    2. Write to GraphStore (eventual consistency) - failures logged
    3. Write to VectorStore (eventual consistency) - failures logged
    4. On GraphStore/VectorStore failure: write compensation record

    Compensating transaction strategy:
    - If GraphStore write fails: compensation record -> async retry
    - If VectorStore write fails: compensation record -> async retry
    - If a CompensationStore is provided, records are persisted there;
      otherwise they are kept in-memory (``_compensation_log``).
    """

    def __init__(
        self,
        storage: StorageBackend,
        graph_store: GraphStoreBackend | None = None,
        vector_store: VectorStoreBackend | None = None,
        compensation_store: CompensationStore | None = None,
    ):
        self.storage = storage
        self.graph = graph_store
        self.vector = vector_store
        self._compensation_store = compensation_store
        self._sync_failures: list[dict[str, Any]] = []
        self._compensation_log: list[dict[str, Any]] = []

    @property
    def graph_enabled(self) -> bool:
        return self.graph is not None

    @property
    def vector_enabled(self) -> bool:
        return self.vector is not None

    async def save_entity_with_graph(
        self,
        entity: EntityInstance,
        relations: list[RelationInstance] | None = None,
        space_id: str = "default",
    ) -> str:
        """Save entity to MetaStore and sync to GraphStore + VectorStore.

        Args:
            entity: Entity to save.
            relations: Optional relations to create.
            space_id: Space identifier for graph store isolation.

        Returns:
            The saved entity ID.
        """
        # Step 1: Write to MetaStore (strong consistency)
        entity_id = await self.storage.save_entity(entity)

        # Step 2: Write to GraphStore (eventual consistency)
        if self.graph:
            try:
                node_props = {**entity.data, "space_id": space_id}
                await self.graph.upsert_node(
                    node_id=entity_id,
                    labels=[entity._fact_object],
                    properties=node_props,
                )
            except Exception as e:
                self._log_sync_failure("upsert_node", entity_id, e)
                logger.warning(f"Graph sync failed for node {entity_id}: {e}")
                await self._write_compensation("entity", entity_id, "graph_upsert")

        # Step 3: Write to VectorStore (eventual consistency)
        if self.vector:
            try:
                await self.vector.sync_entity(entity_id, self._entity_to_vector_data(entity))
            except Exception as e:
                self._log_sync_failure("vector_upsert", entity_id, e)
                logger.warning(f"Vector sync failed for entity {entity_id}: {e}")

        if relations:
            for rel in relations:
                await self.storage.save_relation(rel)
                if self.graph:
                    try:
                        edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_name}"
                        await self.graph.upsert_edge(
                            edge_id=edge_id,
                            from_node_id=rel.from_entity_id,
                            to_node_id=rel.to_entity_id,
                            edge_type=rel.relation_name,
                            properties=rel.data or {},
                        )
                    except Exception as e:
                        self._log_sync_failure("upsert_edge", f"{rel.from_entity_id}:{rel.to_entity_id}", e)
                        logger.warning(f"Graph sync failed for edge: {e}")

                if self.vector:
                    try:
                        await self.vector.sync_relation(
                            self._relation_edge_id(rel),
                            self._relation_to_vector_data(rel),
                        )
                    except Exception as e:
                        self._log_sync_failure("vector_edge_upsert", f"{rel.from_entity_id}:{rel.to_entity_id}", e)
                        logger.warning(f"Vector sync failed for edge: {e}")

        return entity_id

    async def write_entity(
        self,
        entity: EntityInstance,
        space_id: str = "default",
    ) -> str:
        entity_id = await self.storage.save_entity(entity)

        if self.graph:
            try:
                node_props = {**entity.data, "space_id": space_id}
                await self.graph.upsert_node(
                    node_id=entity_id,
                    labels=[entity._fact_object],
                    properties=node_props,
                )
            except Exception as e:
                self._log_sync_failure("upsert_node", entity_id, e)
                logger.warning(f"Graph sync failed for node {entity_id}: {e}")
                await self._write_compensation("entity", entity_id, "graph_upsert")

        if self.vector:
            try:
                await self.vector.sync_entity(entity_id, self._entity_to_vector_data(entity))
            except Exception as e:
                self._log_sync_failure("vector_upsert", entity_id, e)
                logger.warning(f"Vector sync failed for entity {entity_id}: {e}")
                await self._write_compensation("entity", entity_id, "vector_upsert")

        return entity_id

    async def write_relation(
        self,
        relation: RelationInstance,
        space_id: str = "default",
    ) -> None:
        await self.storage.save_relation(relation)

        if self.graph:
            try:
                edge_id = relation.id or f"{relation.from_entity_id}:{relation.to_entity_id}:{relation.relation_name}"
                await self.graph.upsert_edge(
                    edge_id=edge_id,
                    from_node_id=relation.from_entity_id,
                    to_node_id=relation.to_entity_id,
                    edge_type=relation.relation_name,
                    properties=relation.data or {},
                )
            except Exception as e:
                self._log_sync_failure("upsert_edge", f"{relation.from_entity_id}:{relation.to_entity_id}", e)
                logger.warning(f"Graph sync failed for edge: {e}")
                await self._write_compensation("relation", f"{relation.from_entity_id}:{relation.to_entity_id}:{relation.relation_name}", "graph_upsert")

        if self.vector:
            try:
                await self.vector.sync_relation(
                    self._relation_edge_id(relation),
                    self._relation_to_vector_data(relation),
                )
            except Exception as e:
                self._log_sync_failure("vector_edge_upsert", f"{relation.from_entity_id}:{relation.to_entity_id}", e)
                logger.warning(f"Vector sync failed for edge: {e}")
                await self._write_compensation("relation", f"{relation.from_entity_id}:{relation.to_entity_id}:{relation.relation_name}", "vector_upsert")

    async def delete_entity(self, entity_id: str) -> None:
        if self.graph:
            try:
                await self.graph.delete_node(node_id=entity_id)
            except Exception as e:
                self._log_sync_failure("delete_node", entity_id, e)
                logger.warning(f"Graph delete failed for node {entity_id}: {e}")

        if self.vector:
            try:
                await self.vector.delete_vectors([entity_id])
                await self.vector.delete_vectors([f"{entity_id}:summary"])
            except Exception as e:
                self._log_sync_failure("vector_delete", entity_id, e)
                logger.warning(f"Vector delete failed for entity {entity_id}: {e}")

    async def sync_to_graph(
        self,
        entity_id: str,
        entity: EntityInstance | None = None,
        space_id: str = "default",
    ) -> None:
        if not self.graph:
            return

        if entity is None:
            entity = await self.storage.get_entity_by_id(entity_id=entity_id)
        if entity is None:
            logger.warning(f"Entity {entity_id} not found for graph sync")
            return

        try:
            node_props = {**entity.data, "space_id": space_id}
            await self.graph.upsert_node(
                node_id=entity_id,
                labels=[entity._fact_object],
                properties=node_props,
            )
        except Exception as e:
            self._log_sync_failure("sync_to_graph", entity_id, e)
            logger.warning(f"Graph sync failed for node {entity_id}: {e}")
            await self._write_compensation("entity", entity_id, "graph_upsert")

    # --- Data conversion helpers ---

    @staticmethod
    def _entity_to_vector_data(entity: EntityInstance) -> dict[str, Any]:
        """Convert EntityInstance to dict for VectorStoreBackend.sync_entity()."""
        data: dict[str, Any] = {
            "_fact_object": entity._fact_object,
            "entity_id": entity.entity_id,
            **entity.data,
        }
        return data

    @staticmethod
    def _relation_edge_id(rel: RelationInstance) -> str:
        """Build the canonical edge ID for a relation."""
        return f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_name}"

    @staticmethod
    def _relation_to_vector_data(rel: RelationInstance) -> dict[str, Any]:
        """Convert RelationInstance to dict for VectorStoreBackend.sync_relation()."""
        return {
            "relation_name": rel.relation_name,
            "from_id": rel.from_entity_id,
            "to_id": rel.to_entity_id,
            "confidence": rel.data.get("confidence", 1.0),
            "edge_text": rel.data.get("edge_text", rel.relation_name),
            "edge_type": rel.data.get("edge_type", "business"),
        }

    # --- Hybrid query ---

    async def get_neighbor_details(
        self,
        entity_id: str,
        relation_name: str,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Hybrid query: GraphStore for topology + MetaStore for attributes."""
        if not self.graph:
            neighbors = await self.storage.get_neighbors(entity_id, relation_name, direction)
            return [
                {
                    "entity": {"entity_id": e.entity_id, "fact_object": e._fact_object, "data": e.data},
                    "relation": {"relation_name": r.relation_name, "data": r.data},
                }
                for e, r in neighbors
            ]

        graph_neighbors = await self.graph.get_neighbors(
            node_id=entity_id, edge_type=relation_name, direction=direction
        )

        results = []
        for gn in graph_neighbors:
            neighbor_id = gn["neighbor_id"]
            entity = await self.storage.get_entity_by_id(entity_id=neighbor_id)
            if entity:
                results.append({
                    "entity": {"entity_id": entity.entity_id, "fact_object": entity._fact_object, "data": entity.data},
                    "relation": {
                        "edge_id": gn.get("edge_id"),
                        "edge_type": gn.get("edge_type"),
                        "direction": gn.get("direction"),
                    },
                })

        return results

    # --- Batch sync ---

    async def batch_sync_from_storage(self) -> dict[str, int]:
        """Full sync: load all entities/relations from MetaStore into GraphStore + VectorStore."""
        nodes_written = 0
        edges_written = 0
        vectors_written = 0

        if self.graph:
            all_entities = await self.storage.query_entities(fact_object=None)
            nodes = []
            for entity in all_entities:
                nodes.append({
                    "node_id": entity.entity_id,
                    "labels": [entity._fact_object],
                    "properties": entity.data,
                })

            edges = []
            for entity in all_entities:
                relations = await self.storage.get_relations(entity.entity_id)
                for rel in relations:
                    edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_name}"
                    edges.append({
                        "edge_id": edge_id,
                        "from_node_id": rel.from_entity_id,
                        "to_node_id": rel.to_entity_id,
                        "edge_type": rel.relation_name,
                        "properties": rel.data or {},
                    })

            result = await self.graph.batch_upsert(nodes=nodes, edges=edges)
            nodes_written = result.get("nodes_written", 0)
            edges_written = result.get("edges_written", 0)
            logger.info(f"Graph batch sync: {result}")

        if self.vector:
            all_entities = await self.storage.query_entities(fact_object=None)
            for entity in all_entities:
                try:
                    await self.vector.sync_entity(entity.entity_id, self._entity_to_vector_data(entity))
                    vectors_written += 1
                except Exception as e:
                    self._log_sync_failure("vector_batch_sync", entity.entity_id, e)
            logger.info(f"Vector batch sync: {vectors_written} entities")

        return {
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "vectors_written": vectors_written,
        }

    # --- Compensation ---

    async def _write_compensation(
        self,
        target_type: str,
        target_id: str,
        operation: str,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "target_type": target_type,
            "target_id": target_id,
            "operation": operation,
            "status": "pending",
            "retry_count": 0,
        }
        if self._compensation_store is not None:
            await self._compensation_store.save_compensation(entry)
        else:
            self._compensation_log.append(entry)
        logger.info(f"Compensation record written: {target_type} {target_id} {operation}")

    async def recover_pending_compensations(self) -> int:
        """Recover pending compensation records by retrying the failed operations.

        Returns:
            Number of successfully recovered operations.
        """
        if self._compensation_store is None:
            return 0

        pending = await self._compensation_store.get_pending_compensations()
        executed = 0

        for entry in pending:
            target_type = entry.get("target_type", "")
            target_id = entry.get("target_id", "")
            operation = entry.get("operation", "")

            try:
                if operation == "graph_upsert" and target_type == "entity":
                    entity = await self.storage.get_entity_by_id(entity_id=target_id)
                    if entity and self.graph:
                        await self.graph.upsert_node(
                            node_id=target_id,
                            labels=[entity._fact_object],
                            properties=entity.data,
                        )
                        executed += 1

                elif operation == "vector_upsert" and target_type == "entity":
                    entity = await self.storage.get_entity_by_id(entity_id=target_id)
                    if entity and self.vector:
                        await self.vector.sync_entity(target_id, self._entity_to_vector_data(entity))
                        executed += 1

                elif operation == "graph_upsert" and target_type == "relation":
                    relations = await self.storage.get_relations(target_id.split(":")[0])
                    for rel in relations:
                        edge_id = self._relation_edge_id(rel)
                        if edge_id == target_id and self.graph:
                            await self.graph.upsert_edge(
                                edge_id=edge_id,
                                from_node_id=rel.from_entity_id,
                                to_node_id=rel.to_entity_id,
                                edge_type=rel.relation_name,
                                properties=rel.data or {},
                            )
                            executed += 1
                            break

                elif operation == "delete_node":
                    if self.graph:
                        await self.graph.delete_node(node_id=target_id)
                        executed += 1

                elif operation == "vector_delete":
                    if self.vector:
                        await self.vector.delete_vectors([target_id])
                        executed += 1

                elif operation == "delete_relation_graph":
                    if self.graph:
                        await self.graph.delete_edge(edge_id=target_id)
                        executed += 1

                elif operation == "update_relation_graph":
                    parts = target_id.split(":")
                    if len(parts) >= 2 and self.graph:
                        relations = await self.storage.get_relations(parts[0])
                        for rel in relations:
                            edge_id = self._relation_edge_id(rel)
                            if edge_id == target_id:
                                await self.graph.upsert_edge(
                                    edge_id=edge_id,
                                    from_node_id=rel.from_entity_id,
                                    to_node_id=rel.to_entity_id,
                                    edge_type=rel.relation_name,
                                    properties=rel.data or {},
                                )
                                executed += 1
                                break

                await self._compensation_store.mark_compensation_done(target_id, operation)

            except Exception as e:
                logger.warning(f"Recovery failed for {target_id} {operation}: {e}")
                await self._compensation_store.increment_retry_count(target_id, operation)

        return executed

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
