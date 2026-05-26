"""Composite cognitive storage with RRF hybrid search.

P0-4: Wraps SQLiteAdapter + ChromaDBAdapter, routing by memory_type
via StorageRouting and fusing search results with RRF.
"""

from __future__ import annotations

import logging
from typing import Any

from ontology_engine.storage.models import CognitiveNode
from ontology_engine.storage.cognitive_interface import (
    SearchQuery,
    SearchResult,
    StorageInterface,
    StorageRouting,
)

logger = logging.getLogger(__name__)

_RRF_K = 60


class CognitiveStorage(StorageInterface):
    """Composite storage that routes to SQLite and ChromaDB adapters.

    Implements StorageInterface by delegating to the appropriate adapter
    based on memory_type routing, and fusing search results with RRF.
    """

    def __init__(
        self,
        sqlite_adapter: StorageInterface,
        chromadb_adapter: StorageInterface | None = None,
    ) -> None:
        self._sqlite = sqlite_adapter
        self._chromadb = chromadb_adapter

    async def save_node(self, node: CognitiveNode) -> str:
        stores = StorageRouting.get_stores(node.memory_type)
        node_id = node.id
        if "sqlite" in stores:
            node_id = await self._sqlite.save_node(node)
        if "chromadb" in stores and self._chromadb is not None:
            node_id = await self._chromadb.save_node(node)
        return node_id

    async def get_node(self, node_id: str) -> CognitiveNode | None:
        result = await self._sqlite.get_node(node_id)
        if result is not None:
            return result
        if self._chromadb is not None:
            chroma_node = await self._chromadb.get_node(node_id)
            if chroma_node is not None:
                return await self._supplement_from_sqlite(chroma_node)
        return None

    async def _supplement_from_sqlite(self, node: CognitiveNode) -> CognitiveNode:
        sqlite_node = await self._sqlite.get_node(node.id)
        if sqlite_node is not None:
            return sqlite_node
        return node

    async def search(self, query: SearchQuery) -> SearchResult:
        sqlite_result: SearchResult | None = None
        chroma_result: SearchResult | None = None

        if query.memory_type is None or StorageRouting.supports_store(query.memory_type, "sqlite"):
            sqlite_result = await self._sqlite.search(query)

        if self._chromadb is not None:
            if query.memory_type is None or StorageRouting.supports_store(query.memory_type, "chromadb"):
                chroma_result = await self._chromadb.search(query)

        if sqlite_result and chroma_result:
            return _rrf_fuse(sqlite_result, chroma_result, query.top_k)
        if sqlite_result:
            return sqlite_result
        if chroma_result:
            return chroma_result
        return SearchResult(nodes=[])

    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        await self._sqlite.delete_node(node_id, soft=soft)
        if self._chromadb is not None:
            try:
                await self._chromadb.delete_node(node_id, soft=False)
            except Exception:
                pass

    async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
        sqlite_nodes = []
        chroma_nodes = []
        for n in nodes:
            stores = StorageRouting.get_stores(n.memory_type)
            if "sqlite" in stores:
                sqlite_nodes.append(n)
            if "chromadb" in stores and self._chromadb is not None:
                chroma_nodes.append(n)

        sqlite_ids: list[str] = []
        if sqlite_nodes:
            sqlite_ids = await self._sqlite.batch_save(sqlite_nodes)
        if chroma_nodes:
            await self._chromadb.batch_save(chroma_nodes)

        id_map: dict[str, str] = {}
        for n, sid in zip(sqlite_nodes, sqlite_ids):
            id_map[n.id] = sid
        for n in chroma_nodes:
            if n.id not in id_map:
                id_map[n.id] = n.id
        for n in nodes:
            if n.id not in id_map:
                id_map[n.id] = n.id

        return [id_map[n.id] for n in nodes]

    async def count(self, filter: dict[str, Any]) -> int:
        return await self._sqlite.count(filter)

    async def traverse(
        self,
        node_id: str,
        relation: str | None = None,
        depth: int = 2,
    ) -> list[CognitiveNode]:
        return await self._sqlite.traverse(node_id, relation, depth)


def _rrf_fuse(
    sqlite_result: SearchResult,
    chroma_result: SearchResult,
    top_k: int,
) -> SearchResult:
    """Fuse SQLite (keyword) and ChromaDB (semantic) results with RRF.

    Uses standard RRF formula: score = sum(1 / (k + rank)) with k=60.
    """
    doc_scores: dict[str, float] = {}
    doc_nodes: dict[str, Any] = {}
    semantic_scores: dict[str, float] = {}
    keyword_scores: dict[str, float] = {}

    for rank, node in enumerate(chroma_result.nodes, start=1):
        score = 1.0 / (_RRF_K + rank)
        doc_scores[node.id] = doc_scores.get(node.id, 0.0) + score
        doc_nodes[node.id] = node
        semantic_scores[node.id] = chroma_result.scores.get(node.id, score)

    for rank, node in enumerate(sqlite_result.nodes, start=1):
        score = 1.0 / (_RRF_K + rank)
        doc_scores[node.id] = doc_scores.get(node.id, 0.0) + score
        if node.id not in doc_nodes:
            doc_nodes[node.id] = node
        keyword_scores[node.id] = sqlite_result.scores.get(node.id, score)

    sorted_ids = sorted(doc_scores, key=lambda k: doc_scores[k], reverse=True)
    fused_nodes = [doc_nodes[nid] for nid in sorted_ids[:top_k]]
    fused_scores = {nid: doc_scores[nid] for nid in sorted_ids[:top_k]}

    return SearchResult(
        nodes=fused_nodes,
        scores=fused_scores,
        semantic_scores=semantic_scores,
        keyword_scores=keyword_scores,
        fusion_metadata={"strategy": "rrf", "k": _RRF_K},
    )
