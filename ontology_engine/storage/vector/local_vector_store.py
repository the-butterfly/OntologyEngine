"""In-memory vector store using exact distance calculation.

This is a placeholder implementation for Phase 1 / early Phase 2.
Once Faiss integration is completed (Phase 2 prerequisite), this can be
replaced or wrapped by a Faiss-based backend.
"""

from __future__ import annotations

import math
from typing import Any

from ontology_engine.storage.base import (
    StorageError,
    VectorSearchResult,
    VectorStoreBackend,
)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class LocalVectorStore(VectorStoreBackend):
    """In-memory vector store using exact cosine similarity.

    Suitable for small datasets and testing.  Not recommended for production
    use with >10k vectors.
    """

    def __init__(self) -> None:
        self._dimension: int | None = None
        self._vectors: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def _ensure_initialized(self) -> None:
        if self._dimension is None:
            raise StorageError(
                "Vector store not initialized. Call initialize(dimension) first."
            )

    async def initialize(self, dimension: int) -> None:
        self._dimension = dimension
        self._vectors.clear()
        self._metadata.clear()

    async def close(self) -> None:
        self._vectors.clear()
        self._metadata.clear()
        self._dimension = None

    async def add_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        self._ensure_initialized()
        if len(ids) != len(vectors):
            raise ValueError("ids and vectors must have the same length")
        if metadata is not None and len(metadata) != len(ids):
            raise ValueError("metadata must have the same length as ids")

        for i, vid in enumerate(ids):
            vec = vectors[i]
            if len(vec) != self._dimension:
                raise ValueError(
                    f"Vector dimension mismatch for {vid}: "
                    f"expected {self._dimension}, got {len(vec)}"
                )
            self._vectors[vid] = vec
            self._metadata[vid] = metadata[i] if metadata else {}

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        self._ensure_initialized()
        if len(query_vector) != self._dimension:
            raise ValueError(
                f"Query vector dimension mismatch: "
                f"expected {self._dimension}, got {len(query_vector)}"
            )

        if not self._vectors:
            return []

        scored: list[tuple[str, float]] = []
        for vid, vec in self._vectors.items():
            md = self._metadata.get(vid, {})
            if filters:
                if not all(md.get(k) == v for k, v in filters.items()):
                    continue
            sim = _cosine_similarity(query_vector, vec)
            scored.append((vid, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        results: list[VectorSearchResult] = []
        for vid, sim in scored[:top_k]:
            results.append(
                VectorSearchResult(
                    id=vid,
                    score=sim,
                    metadata=dict(self._metadata.get(vid, {})),
                )
            )
        return results

    async def delete_vectors(self, ids: list[str]) -> None:
        self._ensure_initialized()
        for vid in ids:
            self._vectors.pop(vid, None)
            self._metadata.pop(vid, None)
