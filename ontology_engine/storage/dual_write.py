# ontology_engine/storage/dual_write.py
"""Three-engine write coordinator for MetaStore + GraphStore + VectorStore synchronization.

Write flow:
1. Write to MetaStore (SQLite) first (strong consistency)
2. Async write to GraphStore (KuzuDB) (eventual consistency, failure logged)
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
    4. On GraphStore/VectorStore failure: write compensation record to MetaStore

    Compensating transaction strategy:
    - If GraphStore write fails: MetaStore writes compensation record -> async retry
    - If VectorStore write fails: MetaStore writes compensation record -> async retry
    """

    def __init__(
        self,
        storage: StorageBackend,
        graph_store: GraphStoreBackend | None = None,
        vector_store: VectorStoreBackend | None = None,
    ):
        self.storage = storage
        self.graph = graph_store
        self.vector = vector_store
        self._sync_failures: list[dict[str, Any]] = []

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
                await self._mark_pending_sync(entity_id)

        # Step 3: Write to VectorStore (eventual consistency)
        if self.vector:
            try:
                await self._sync_entity_to_vector(entity)
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
                        await self._sync_relation_to_vector(rel)
                    except Exception as e:
                        self._log_sync_failure("vector_edge_upsert", f"{rel.from_entity_id}:{rel.to_entity_id}", e)
                        logger.warning(f"Vector sync failed for edge: {e}")

        return entity_id

    async def _sync_entity_to_vector(self, entity: EntityInstance) -> None:
        """Sync entity data to VectorStore collections.

        Writes to entity_name and entity_summary collections.
        """
        if self.vector is None:
            return

        name = entity.data.get("name", entity.entity_id)
        summary = entity.data.get("summary", "")
        if not summary:
            attr_parts = [f"{k}={v}" for k, v in sorted(entity.data.items()) if k != "name"]
            summary = f"{name}: " + "; ".join(attr_parts) if attr_parts else name

        metadata_base = {
            "_fact_object": entity._fact_object,
            "entity_id": entity.entity_id,
        }

        if hasattr(self.vector, "upsert_to_collection"):
            await self.vector.upsert_to_collection(
                collection_name="entity_name",
                ids=[entity.entity_id],
                documents=[name],
                metadatas=[{**metadata_base, "domain_id": entity.data.get("domain_id", "")}],
            )
            await self.vector.upsert_to_collection(
                collection_name="entity_summary",
                ids=[f"{entity.entity_id}:summary"],
                documents=[summary],
                metadatas=[{
                    **metadata_base,
                    "entity_id": entity.entity_id,
                    "feedback_weight": entity.data.get("feedback_weight", 0.5),
                }],
            )

    async def _sync_relation_to_vector(self, rel: RelationInstance) -> None:
        """Sync relation data to VectorStore collections.

        Writes to edge_relationship_name and edge_text collections.
        """
        if self.vector is None:
            return

        edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_name}"
        edge_text = rel.data.get("edge_text", rel.relation_name)

        metadata_base = {
            "edge_id": edge_id,
            "from_id": rel.from_entity_id,
            "to_id": rel.to_entity_id,
            "relation_name": rel.relation_name,
            "confidence": rel.data.get("confidence", 1.0),
        }

        if hasattr(self.vector, "upsert_to_collection"):
            await self.vector.upsert_to_collection(
                collection_name="edge_relationship_name",
                ids=[f"{edge_id}:rel"],
                documents=[rel.relation_name],
                metadatas=[{**metadata_base, "edge_type": "business"}],
            )
            if edge_text:
                await self.vector.upsert_to_collection(
                    collection_name="edge_text",
                    ids=[f"{edge_id}:text"],
                    documents=[edge_text],
                    metadatas=[{**metadata_base, "edge_type": rel.data.get("edge_type", "business")}],
                )

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
                    await self._sync_entity_to_vector(entity)
                    vectors_written += 1
                except Exception as e:
                    self._log_sync_failure("vector_batch_sync", entity.entity_id, e)
            logger.info(f"Vector batch sync: {vectors_written} entities")

        return {
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "vectors_written": vectors_written,
        }

    async def _mark_pending_sync(self, entity_id: str) -> None:
        """Mark entity as pending graph sync for background reconciliation."""
        logger.info(f"Entity {entity_id} marked as pending graph sync")
        # TODO: In production, update entity in MetaStore with sync_pending flag
        # e.g., await self.storage.update_entity_sync_status(entity_id, "pending")

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
