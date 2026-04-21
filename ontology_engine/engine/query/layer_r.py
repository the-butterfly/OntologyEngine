"""Layer-R vector retrieval over knowledge fragments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ontology_engine.storage.base import VectorStoreBackend


@dataclass
class LinkedEntity:
    entity_id: str
    entity_name: str
    fact_object: str
    confidence: float
    edge_text: str


@dataclass
class FragmentResult:
    fragment_id: str
    text: str
    score: float
    dataset_id: str
    document_id: str
    chunk_index: int
    offset_start: int
    offset_end: int
    extraction_status: str
    content_hash: str
    linked_entities: list[LinkedEntity] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class LayerRRetriever:
    """Layer-R: Vector retrieval over knowledge_fragment collection."""

    DEFAULT_LAMBDA = 0.7

    def __init__(self, vector_store: VectorStoreBackend, lambda_score: float = DEFAULT_LAMBDA) -> None:
        self._vector_store = vector_store
        self._lambda = lambda_score

    async def search_knowledge_fragments(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> list[FragmentResult]:
        results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            collection_name="knowledge_fragment",
            filter_metadata=where,
        )

        fragments: list[FragmentResult] = []
        for r in results:
            metadata = r.metadata or {}
            feedback_weight = metadata.get("feedback_weight", 0.5)
            semantic_score = 1.0 - r.distance if r.distance is not None else 0.0
            final_score = self._lambda * semantic_score + (1 - self._lambda) * feedback_weight

            fragments.append(FragmentResult(
                fragment_id=r.id,
                text=r.document,
                score=final_score,
                dataset_id=metadata.get("dataset_id", ""),
                document_id=metadata.get("document_id", ""),
                chunk_index=metadata.get("chunk_index", 0),
                offset_start=metadata.get("offset_start", 0),
                offset_end=metadata.get("offset_end", 0),
                extraction_status=metadata.get("extraction_status", "pending"),
                content_hash=metadata.get("content_hash", ""),
                metadata=metadata,
            ))

        return sorted(fragments, key=lambda f: f.score, reverse=True)
