# ontology_engine/storage/vector/chroma_store.py
"""ChromaDB-based vector store with 7 collections and dual embedding strategy.

Implements the VectorStoreBackend interface with persistent storage,
metadata filtering, and multi-collection parallel search.

Requires ``chromadb`` Python binding (``pip install ontology-engine[chroma]``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ontology_engine.storage.base import (
    StorageError,
    VectorSearchResult,
    VectorStoreBackend,
)

logger = logging.getLogger(__name__)

COLLECTION_NAMES = [
    "entity_name",
    "entity_summary",
    "facet_search_text",
    "edge_relationship_name",
    "edge_text",
    "knowledge_fragment",
    "rule_definition",
]

DEFAULT_COLLECTION = "entity_name"


class ChromaVectorStore(VectorStoreBackend):
    """ChromaDB vector store with 7 collections and dual embedding strategy.

    Collections:
        entity_name: EntityInstance.name vectors
        entity_summary: Entity summary text vectors
        facet_search_text: CategoryTag + MetricValue combo text vectors
        edge_relationship_name: EdgeInstance.relation_name vectors
        edge_text: EdgeInstance.edge_text vectors (incl. mutual-index edges)
        knowledge_fragment: KnowledgeFragment.text vectors
        rule_definition: Rule condition + action text vectors

    Embedding strategy:
        Primary: OpenAI text-embedding-3-small (1536d) if API key available
        Fallback: sentence-transformers/all-MiniLM-L6-v2 (384d)
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        openai_api_key: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self._persist_dir = persist_dir or os.path.join(
            os.path.expanduser("~/.ontology_engine/data"), "vectors"
        )
        self._openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self._embedding_model = embedding_model
        self._client: Any = None
        self._embedding_fn: Any = None
        self._dimension: int | None = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._initialized = False

    def _resolve_embedding_function(self) -> tuple[Any, int]:
        import chromadb

        model = self._embedding_model
        if model is None and self._openai_api_key:
            model = "text-embedding-3-small"
        elif model is None:
            model = "all-MiniLM-L6-v2"

        if model == "text-embedding-3-small":
            fn = chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
                api_key=self._openai_api_key,
                model_name="text-embedding-3-small",
            )
            return fn, 1536
        else:
            fn = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
            )
            return fn, 384

    async def initialize(self, dimension: int = 0) -> None:
        if self._initialized:
            return
        try:
            import chromadb
        except ImportError as exc:
            raise StorageError(
                "chromadb is not installed. Install with: pip install ontology-engine[chroma]"
            ) from exc

        self._embedding_fn, resolved_dim = self._resolve_embedding_function()
        self._dimension = dimension if dimension > 0 else resolved_dim

        os.makedirs(self._persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_dir)

        await self._ensure_collections()
        self._initialized = True
        logger.info(
            "ChromaDB vector store initialized at %s (dim=%d)",
            self._persist_dir,
            self._dimension,
        )

    async def _ensure_collections(self) -> None:
        for name in COLLECTION_NAMES:
            await asyncio.to_thread(
                self._client.get_or_create_collection,
                name=name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedding_fn,
            )

    def _ensure_initialized(self) -> None:
        if not self._initialized or self._client is None:
            raise StorageError(
                "ChromaVectorStore not initialized. Call initialize() first."
            )

    async def close(self) -> None:
        self._client = None
        self._embedding_fn = None
        self._initialized = False
        self._executor.shutdown(wait=False)

    async def add_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        self._ensure_initialized()
        collection_name = DEFAULT_COLLECTION
        if metadata:
            for m in metadata:
                if "_collection" in m:
                    collection_name = m.pop("_collection")
                    break

        documents: list[str] = []
        if metadata:
            documents = [m.pop("_document", "") for m in metadata]

        metadatas = metadata or [{} for _ in ids]

        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        await asyncio.to_thread(
            collection.upsert,
            ids=ids,
            embeddings=vectors if vectors else None,
            documents=documents if documents else None,
            metadatas=metadatas,
        )

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        self._ensure_initialized()
        collection_name = DEFAULT_COLLECTION
        where = None
        if filters:
            collection_name = filters.pop("_collection", collection_name)
            where = filters if filters else None

        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        result = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        results: list[VectorSearchResult] = []
        if result and result.get("ids") and result["ids"][0]:
            ids = result["ids"][0]
            distances = result["distances"][0] if result.get("distances") else [0.0] * len(ids)
            metadatas = result["metadatas"][0] if result.get("metadatas") else [{}] * len(ids)
            for i, vid in enumerate(ids):
                distance = distances[i] if i < len(distances) else 0.0
                score = 1.0 - distance
                results.append(
                    VectorSearchResult(
                        id=vid,
                        score=score,
                        metadata=metadatas[i] if i < len(metadatas) else {},
                    )
                )
        return results

    async def delete_vectors(self, ids: list[str]) -> None:
        self._ensure_initialized()
        collection_name = DEFAULT_COLLECTION
        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        await asyncio.to_thread(collection.delete, ids=ids)

    async def sync_entity(self, entity_id: str, entity_data: dict[str, Any], **kwargs: Any) -> None:
        """Sync entity data to vector collections.

        Handles KnowledgeFragment entities specially (single collection),
        and regular entities with dual collection upsert (entity_name +
        entity_summary).

        Args:
            entity_id: Unique entity identifier.
            entity_data: Dict with keys: _fact_object, name, summary,
                         domain_id, feedback_weight, etc.
        """
        self._ensure_initialized()

        fact_object = entity_data.get("_fact_object", "")

        # KnowledgeFragment: single collection upsert
        if fact_object == "KnowledgeFragment":
            text = entity_data.get("text", "")
            if not text:
                return
            metadata_base = {
                "_fact_object": fact_object,
                "entity_id": entity_id,
                "dataset_id": entity_data.get("dataset_id", ""),
                "document_id": entity_data.get("document_id", ""),
                "extraction_status": entity_data.get("extraction_status", "pending"),
            }
            await self.upsert_to_collection(
                collection_name="knowledge_fragment",
                ids=[entity_id],
                documents=[text],
                metadatas=[metadata_base],
            )
            return

        # Regular entity: dual collection upsert
        name = entity_data.get("name", entity_id)
        summary = entity_data.get("summary", "")
        if not summary:
            attr_parts = [
                f"{k}={v}"
                for k, v in sorted(entity_data.items())
                if k not in ("name", "_fact_object", "entity_id")
            ]
            summary = f"{name}: " + "; ".join(attr_parts) if attr_parts else name

        metadata_base = {
            "_fact_object": fact_object,
            "entity_id": entity_id,
        }

        await self.upsert_to_collection(
            collection_name="entity_name",
            ids=[entity_id],
            documents=[name],
            metadatas=[{**metadata_base, "domain_id": entity_data.get("domain_id", "")}],
        )
        await self.upsert_to_collection(
            collection_name="entity_summary",
            ids=[f"{entity_id}:summary"],
            documents=[summary],
            metadatas=[{
                **metadata_base,
                "entity_id": entity_id,
                "feedback_weight": entity_data.get("feedback_weight", 0.5),
            }],
        )

    async def sync_relation(self, relation_id: str, relation_data: dict[str, Any], **kwargs: Any) -> None:
        """Sync relation data to vector collections.

        Writes to edge_relationship_name and edge_text collections.
        Categorizes mutual-index edges (EXTRACTED_FROM, SUPPORTED_BY,
        DEFINED_IN, TRACE_TO).

        Args:
            relation_id: Unique relation identifier.
            relation_data: Dict with keys: relation_name, from_id, to_id,
                           confidence, edge_text, edge_type, etc.
        """
        self._ensure_initialized()

        relation_name = relation_data.get("relation_name", "")
        edge_text = relation_data.get("edge_text", relation_name)

        metadata_base = {
            "edge_id": relation_id,
            "from_id": relation_data.get("from_id", ""),
            "to_id": relation_data.get("to_id", ""),
            "relation_name": relation_name,
            "confidence": relation_data.get("confidence", 1.0),
        }

        if relation_name in ("EXTRACTED_FROM", "SUPPORTED_BY", "DEFINED_IN", "TRACE_TO"):
            metadata_base["edge_category"] = "mutual_index"

        await self.upsert_to_collection(
            collection_name="edge_relationship_name",
            ids=[f"{relation_id}:rel"],
            documents=[relation_name],
            metadatas=[{**metadata_base, "edge_type": "business"}],
        )
        if edge_text:
            await self.upsert_to_collection(
                collection_name="edge_text",
                ids=[f"{relation_id}:text"],
                documents=[edge_text],
                metadatas=[{**metadata_base, "edge_type": relation_data.get("edge_type", "business")}],
            )

    async def upsert_to_collection(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        self._ensure_initialized()
        if collection_name not in COLLECTION_NAMES:
            raise StorageError(f"Unknown collection: {collection_name}")

        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        kwargs: dict[str, Any] = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        if embeddings:
            kwargs["embeddings"] = embeddings
        await asyncio.to_thread(collection.upsert, **kwargs)

    async def search_collection(
        self,
        collection_name: str,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_initialized()
        if collection_name not in COLLECTION_NAMES:
            raise StorageError(f"Unknown collection: {collection_name}")

        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        kwargs: dict[str, Any] = {"n_results": n_results, "include": ["metadatas", "distances", "documents"]}
        if query_texts:
            kwargs["query_texts"] = query_texts
        if query_embeddings:
            kwargs["query_embeddings"] = query_embeddings
        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document

        return await asyncio.to_thread(collection.query, **kwargs)

    async def multi_collection_search(
        self,
        collection_names: list[str],
        query_embedding: list[float],
        n_results_per_collection: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, list[VectorSearchResult]]:
        self._ensure_initialized()
        results: dict[str, list[VectorSearchResult]] = {}
        for name in collection_names:
            if name not in COLLECTION_NAMES:
                continue
            raw = await self.search_collection(
                collection_name=name,
                query_embeddings=[query_embedding],
                n_results=n_results_per_collection,
                where=where,
            )
            collection_results: list[VectorSearchResult] = []
            if raw and raw.get("ids") and raw["ids"][0]:
                ids = raw["ids"][0]
                distances = raw["distances"][0] if raw.get("distances") else [0.0] * len(ids)
                metadatas = raw["metadatas"][0] if raw.get("metadatas") else [{}] * len(ids)
                for i, vid in enumerate(ids):
                    distance = distances[i] if i < len(distances) else 0.0
                    collection_results.append(
                        VectorSearchResult(
                            id=vid,
                            score=1.0 - distance,
                            metadata=metadatas[i] if i < len(metadatas) else {},
                        )
                    )
            results[name] = collection_results
        return results

    async def delete_from_collection(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> None:
        self._ensure_initialized()
        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        kwargs: dict[str, Any] = {}
        if ids:
            kwargs["ids"] = ids
        if where:
            kwargs["where"] = where
        await asyncio.to_thread(collection.delete, **kwargs)

    async def get_from_collection(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_initialized()
        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        kwargs: dict[str, Any] = {"include": ["metadatas", "documents"]}
        if ids:
            kwargs["ids"] = ids
        if where:
            kwargs["where"] = where
        if limit:
            kwargs["limit"] = limit
        return await asyncio.to_thread(collection.get, **kwargs)

    async def count_collection(self, collection_name: str) -> int:
        self._ensure_initialized()
        collection = self._client.get_collection(
            name=collection_name, embedding_function=self._embedding_fn
        )
        return await asyncio.to_thread(collection.count)

    async def list_collections(self) -> list[str]:
        self._ensure_initialized()
        existing = await asyncio.to_thread(self._client.list_collections)
        return [c.name if hasattr(c, "name") else str(c) for c in existing]

    async def create_collection(
        self, name: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self._ensure_initialized()
        meta = {"hnsw:space": "cosine"}
        if metadata:
            meta.update(metadata)
        await asyncio.to_thread(
            self._client.get_or_create_collection,
            name=name,
            metadata=meta,
            embedding_function=self._embedding_fn,
        )

    async def delete_collection(self, name: str) -> None:
        self._ensure_initialized()
        await asyncio.to_thread(self._client.delete_collection, name=name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._embedding_fn is None:
            raise StorageError("Embedding function not initialized")
        return self._embedding_fn(texts)
