from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Any

from ontology_engine.storage.base import CognitiveStorageBackend
from ontology_engine.storage.cognitive_interface import SearchQuery, StorageInterface

if TYPE_CHECKING:
    from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore

logger = logging.getLogger(__name__)


class CognitiveStore(CognitiveStorageBackend):
    """Cognitive storage backend backed by LadybugGraphStore.

    .. deprecated::
        Use ``LadybugGraphStore`` directly — it now implements
        ``CognitiveStorageBackend`` natively.  This class is kept for
        backward compatibility and will be removed in a future version.

    Delegates all cognitive-specific persistence operations to the
    underlying LadybugGraphStore, which now directly implements the
    CognitiveStorageBackend interface.
    """

    def __init__(
        self,
        graph_store: LadybugGraphStore,
        storage: StorageInterface | None = None,
    ) -> None:
        warnings.warn(
            "CognitiveStore is deprecated. LadybugGraphStore now implements "
            "CognitiveStorageBackend directly. Use the graph_store instance "
            "as a CognitiveStorageBackend instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._store = graph_store
        self._storage = storage

    async def initialize(self, db_path: str | None = None) -> None:
        await self._store.initialize(db_path)

    async def close(self) -> None:
        await self._store.close()

    async def save_cognitive_node(self, node_data: dict[str, Any]) -> None:
        await self._store.save_cognitive_node(node_data)

    async def get_cognitive_node(self, node_id: str) -> dict[str, Any] | None:
        return await self._store.get_cognitive_node(node_id)

    async def list_cognitive_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._store.list_cognitive_nodes(
            memory_type=memory_type,
            cognitive_layer=cognitive_layer,
            belief_status=belief_status,
            domain_id=domain_id,
            space_id=space_id,
            limit=limit,
            as_of=as_of,
        )

    async def delete_cognitive_node(self, node_id: str) -> None:
        await self._store.delete_cognitive_node(node_id)

    async def update_cognitive_node_belief(
        self,
        node_id: str,
        new_belief: str,
        reason: str | None = None,
    ) -> None:
        await self._store.update_cognitive_node_belief(node_id, new_belief, reason)

    async def update_cognitive_node_with_occ(
        self,
        node_id: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await self._store.update_cognitive_node_with_occ(
            node_id=node_id,
            expected_version=expected_version,
            updates=updates,
        )

    async def save_cognitive_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._store.save_cognitive_edge(
            edge_type=edge_type,
            from_id=from_id,
            to_id=to_id,
            properties=properties,
        )

    async def list_cognitive_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._store.list_cognitive_edges(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            limit=limit,
        )

    async def save_disposition(self, profile_data: dict[str, Any]) -> None:
        await self._store.save_disposition(profile_data)

    async def get_disposition(
        self,
        profile_id: str | None = None,
        scene: str | None = None,
        domain_id: str | None = None,
    ) -> dict[str, Any] | None:
        return await self._store.get_disposition(
            profile_id=profile_id,
            scene=scene,
            domain_id=domain_id,
        )

    async def compute_dynamic_weights(
        self, profile: dict[str, Any]
    ) -> dict[str, float]:
        return await self._store.compute_dynamic_weights(profile)

    async def save_activity_log(
        self, node_id: str, entry: dict[str, Any]
    ) -> None:
        await self._store.save_activity_log(node_id, entry)

    async def get_activity_log(
        self, node_id: str
    ) -> list[dict[str, Any]]:
        return await self._store.get_activity_log(node_id)

    async def search_cognitive(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._storage is None:
            return await self._store.search_cognitive(
                query=query,
                space_id=space_id,
                top_k=top_k,
                memory_type=memory_type,
            )

        search_query = SearchQuery(
            query_text=query,
            space_id=space_id,
            top_k=top_k,
            memory_type=memory_type,
        )
        search_result = await self._storage.search(search_query)
        results = []
        for node in search_result.nodes:
            row = node.to_dict() if hasattr(node, "to_dict") else dict(node)
            row["score"] = search_result.scores.get(node.id, 0.0)
            if search_result.semantic_scores:
                row["semantic_score"] = search_result.semantic_scores.get(node.id, 0.0)
            if search_result.keyword_scores:
                row["keyword_score"] = search_result.keyword_scores.get(node.id, 0.0)
            if search_result.fusion_metadata:
                row["fusion_metadata"] = search_result.fusion_metadata
            results.append(row)
        return results
