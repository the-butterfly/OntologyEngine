"""ChromaDB adapter for CognitiveNode vector data.

P0-3: Implements the vector portion of StorageInterface for ChromaDB,
handling memory_types that route to "chromadb" per StorageRouting:
fragment (pure vector), entity (entity_name vector), relation (edge_text vector).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from ontology_engine.storage.models import CognitiveNode
from ontology_engine.storage.cognitive_interface import (
    SearchQuery,
    SearchResult,
    StorageInterface,
)

logger = logging.getLogger(__name__)

VECTOR_MEMORY_TYPES = {"fragment", "entity", "relation"}


class ChromaDBAdapter(StorageInterface):
    """ChromaDB storage adapter for vectorized CognitiveNode data.

    Handles memory_types routed to "chromadb" per StorageRouting:
    - fragment: pure vector storage (not stored in SQLite)
    - entity: entity_name vector index
    - relation: edge_text vector index
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str = "cognitive_nodes",
    ) -> None:
        self._persist_dir = persist_dir or os.path.join(
            os.path.expanduser("~/.ontology_engine/data"), "chroma_cognitive"
        )
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None
        self._lock: asyncio.Lock | None = None

    async def initialize(self) -> None:
        if self._client is not None:
            return
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is not installed. Install with: pip install ontology-engine[chroma]"
            ) from exc

        self._lock = asyncio.Lock()
        os.makedirs(self._persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = await asyncio.to_thread(
            self._client.get_or_create_collection,
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDBAdapter initialized at %s (collection=%s)",
            self._persist_dir,
            self._collection_name,
        )

    async def close(self) -> None:
        self._client = None
        self._collection = None

    def _ensure_initialized(self) -> None:
        if self._client is None:
            raise RuntimeError("ChromaDBAdapter not initialized. Call initialize() first.")

    def _node_to_doc(self, node: CognitiveNode) -> str:
        return node.content

    _CHROMADB_MISSING_FIELDS = frozenset({
        "content_vector", "ttl_seconds", "occurred_at", "updated_at",
        "history", "access_count", "last_access_at", "consolidated_at",
        "domain_id", "extraction_hint", "visibility", "created_by",
        "schema_ref", "superseded_by", "proof_count",
        "valid_from", "valid_to", "recorded_at", "version",
        "last_confirmed_at", "consolidation_reasoning", "compiled_at",
        "source_trust_tier", "source_pipeline", "source_content_hash",
        "attributes",
    })

    def _node_to_metadata(self, node: CognitiveNode) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "memory_type": node.memory_type,
            "cognitive_layer": node.cognitive_layer,
            "space_id": node.space_id,
            "belief_status": node.belief_status,
            "confidence": node.confidence,
            "created_at": node.created_at or "",
            "strength": node.strength,
            "feedback_weight": node.feedback_weight,
            "confirmation_count": node.confirmation_count,
        }
        if node.entity_name:
            meta["entity_name"] = node.entity_name
        if node.entity_type:
            meta["entity_type"] = node.entity_type
        if node.source_fragment_ids:
            meta["source_fragment_ids"] = json.dumps(node.source_fragment_ids)
        if node.scope:
            meta["scope"] = node.scope
        if node.tags:
            for k, v in node.tags.items():
                if isinstance(v, str):
                    meta[f"tag_{k}"] = v
        return meta

    def _metadata_to_node(self, meta: dict[str, Any], doc: str, node_id: str) -> CognitiveNode:
        tags: dict[str, Any] = {}
        for k, v in meta.items():
            if k.startswith("tag_"):
                tags[k[4:]] = v
        source_fragment_ids: list[str] = []
        sfi = meta.get("source_fragment_ids")
        if isinstance(sfi, str):
            try:
                source_fragment_ids = json.loads(sfi)
            except (json.JSONDecodeError, TypeError):
                source_fragment_ids = []
        return CognitiveNode(
            id=node_id,
            memory_type=meta.get("memory_type", "fragment"),
            cognitive_layer=meta.get("cognitive_layer", "semantic"),
            content=doc,
            entity_name=meta.get("entity_name"),
            entity_type=meta.get("entity_type"),
            space_id=meta.get("space_id", "default"),
            belief_status=meta.get("belief_status", "accepted"),
            confidence=meta.get("confidence", 1.0),
            created_at=meta.get("created_at"),
            tags=tags,
            strength=meta.get("strength", 1.0),
            feedback_weight=meta.get("feedback_weight", 0.5),
            confirmation_count=meta.get("confirmation_count", 0),
            source_fragment_ids=source_fragment_ids,
            scope=meta.get("scope"),
        )

    async def save_node(self, node: CognitiveNode) -> str:
        self._ensure_initialized()
        assert self._collection is not None
        await asyncio.to_thread(
            self._collection.upsert,
            ids=[node.id],
            documents=[self._node_to_doc(node)],
            metadatas=[self._node_to_metadata(node)],
        )
        return node.id

    async def get_node(self, node_id: str) -> CognitiveNode | None:
        self._ensure_initialized()
        assert self._collection is not None
        result = await asyncio.to_thread(
            self._collection.get,
            ids=[node_id],
            include=["metadatas", "documents"],
        )
        if not result.get("ids") or not result["ids"]:
            return None
        meta = result["metadatas"][0] if result.get("metadatas") else {}
        doc = result["documents"][0] if result.get("documents") else ""
        return self._metadata_to_node(meta, doc, node_id)

    async def search(self, query: SearchQuery) -> SearchResult:
        self._ensure_initialized()
        assert self._collection is not None

        where: dict[str, Any] = {"space_id": query.space_id}
        if query.memory_type:
            where["memory_type"] = query.memory_type
        if query.cognitive_layer:
            where["cognitive_layer"] = query.cognitive_layer
        if query.belief_status:
            where["belief_status"] = query.belief_status

        result = await asyncio.to_thread(
            self._collection.query,
            query_texts=[query.query_text],
            n_results=query.top_k,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

        nodes: list[CognitiveNode] = []
        scores: dict[str, float] = {}
        semantic_scores: dict[str, float] = {}

        if result.get("ids") and result["ids"][0]:
            ids = result["ids"][0]
            distances = result.get("distances", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            documents = result.get("documents", [[]])[0]

            for i, nid in enumerate(ids):
                dist = distances[i] if i < len(distances) else 1.0
                score = 1.0 - dist
                meta = metadatas[i] if i < len(metadatas) else {}
                doc = documents[i] if i < len(documents) else ""
                node = self._metadata_to_node(meta, doc, nid)
                nodes.append(node)
                scores[nid] = score
                semantic_scores[nid] = score

        return SearchResult(
            nodes=nodes,
            scores=scores,
            semantic_scores=semantic_scores,
        )

    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        self._ensure_initialized()
        assert self._collection is not None
        await asyncio.to_thread(self._collection.delete, ids=[node_id])

    async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
        self._ensure_initialized()
        assert self._collection is not None
        if not nodes:
            return []
        await asyncio.to_thread(
            self._collection.upsert,
            ids=[n.id for n in nodes],
            documents=[self._node_to_doc(n) for n in nodes],
            metadatas=[self._node_to_metadata(n) for n in nodes],
        )
        return [n.id for n in nodes]

    async def count(self, filter: dict[str, Any]) -> int:
        self._ensure_initialized()
        assert self._collection is not None
        where = filter if filter and len(filter) > 0 else None
        if where:
            result = await asyncio.to_thread(self._collection.get, where=where)
            return len(result.get("ids", []))
        return await asyncio.to_thread(self._collection.count)
