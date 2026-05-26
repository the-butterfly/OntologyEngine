"""Legacy storage adapter — wraps CognitiveStorageBackend as StorageInterface.

Adapts the old CognitiveStorageBackend interface to the new StorageInterface,
enabling CognitiveRepository to depend on a single storage abstraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.storage.models import CognitiveNode
from ontology_engine.storage.cognitive_interface import (
    SearchQuery,
    SearchResult,
    StorageInterface,
)

if TYPE_CHECKING:
    from ontology_engine.storage.base import CognitiveStorageBackend


class LegacyStorageAdapter(StorageInterface):
    """Adapts CognitiveStorageBackend to StorageInterface."""

    def __init__(self, backend: CognitiveStorageBackend) -> None:
        self._backend = backend

    async def save_node(self, node: CognitiveNode) -> str:
        await self._backend.save_cognitive_node(node.to_dict())
        return node.id

    async def get_node(self, node_id: str) -> CognitiveNode | None:
        data = await self._backend.get_cognitive_node(node_id)
        if data is None:
            return None
        return CognitiveNode.from_dict(data) if isinstance(data, dict) else data

    async def search(self, query: SearchQuery) -> SearchResult:
        data_list = await self._backend.list_cognitive_nodes(
            memory_type=query.memory_type,
            cognitive_layer=query.cognitive_layer,
            belief_status=query.belief_status,
            domain_id=query.space_id,
            limit=query.top_k,
        )
        nodes = [CognitiveNode.from_dict(d) for d in data_list]
        return SearchResult(nodes=nodes, scores={n.id: 1.0 for n in nodes})

    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        await self._backend.delete_cognitive_node(node_id)

    async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
        for n in nodes:
            await self._backend.save_cognitive_node(n.to_dict())
        return [n.id for n in nodes]

    async def count(self, filter: dict[str, Any]) -> int:
        data_list = await self._backend.list_cognitive_nodes(limit=999999, **filter)
        return len(data_list)

    async def list_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[CognitiveNode]:
        data_list = await self._backend.list_cognitive_nodes(
            memory_type=memory_type,
            cognitive_layer=cognitive_layer,
            belief_status=belief_status,
            domain_id=domain_id,
            space_id=space_id,
            limit=limit,
            as_of=as_of,
        )
        return [CognitiveNode.from_dict(d) for d in data_list]

    async def update_node_with_occ(
        self,
        node_id: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> Any | None:
        return await self._backend.update_cognitive_node_with_occ(
            node_id, expected_version, updates
        )

    async def save_disposition(self, profile_data: dict[str, Any]) -> None:
        await self._backend.save_disposition(profile_data)

    async def get_disposition(
        self,
        profile_id: str | None = None,
        scene: str | None = None,
        domain_id: str | None = None,
    ) -> dict[str, Any] | None:
        return await self._backend.get_disposition(
            profile_id=profile_id, scene=scene, domain_id=domain_id
        )

    async def compute_dynamic_weights(
        self, profile: dict[str, Any]
    ) -> dict[str, float]:
        return await self._backend.compute_dynamic_weights(profile)

    async def save_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._backend.save_cognitive_edge(
            edge_type=edge_type,
            from_id=from_id,
            to_id=to_id,
            properties=properties,
        )

    async def list_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._backend.list_cognitive_edges(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            limit=limit,
        )
