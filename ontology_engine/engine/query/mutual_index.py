"""Mutual-index collaborative retrieval and RetrieverRegistry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ontology_engine.engine.query.layer_r import LayerRRetriever, FragmentResult
from ontology_engine.engine.query.layer_s import LayerSRetriever, EntityResult, EdgeResult
from ontology_engine.storage.base import GraphStoreBackend, StorageBackend, VectorStoreBackend


@dataclass
class EvidenceLink:
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    trace_type: str
    confidence: float
    edge_text: str
    offset_start: int
    offset_end: int


@dataclass
class CollaborativeResult:
    fragments: list[FragmentResult] = field(default_factory=list)
    entities: list[EntityResult] = field(default_factory=list)
    edges: list[EdgeResult] = field(default_factory=list)
    evidence_chain: list[EvidenceLink] = field(default_factory=list)
    execution_snapshot: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieverMeta:
    name: str
    description: str
    applicable_scenarios: list[str]
    retriever_cls: type


class RetrieverRegistry:
    _retrievers: dict[str, RetrieverMeta] = {}

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        applicable_scenarios: list[str],
        retriever_cls: type,
    ) -> None:
        cls._retrievers[name] = RetrieverMeta(
            name=name,
            description=description,
            applicable_scenarios=applicable_scenarios,
            retriever_cls=retriever_cls,
        )

    @classmethod
    def get(cls, name: str) -> RetrieverMeta | None:
        return cls._retrievers.get(name)

    @classmethod
    def list_retrievers(cls) -> list[RetrieverMeta]:
        return list(cls._retrievers.values())


RetrieverRegistry.register(
    "layer_r_vector",
    "Layer-R vector retrieval over knowledge fragments",
    ["factual", "fragment_search"],
    LayerRRetriever,
)
RetrieverRegistry.register(
    "layer_s_graph",
    "Layer-S graph traversal retrieval",
    ["multi_hop", "graph_traverse"],
    LayerSRetriever,
)


class MutualIndexCollaborative:
    """Cross-layer collaborative retrieval via mutual-index edges."""

    def __init__(
        self,
        graph_store: GraphStoreBackend,
        meta_store: StorageBackend,
        vector_store: VectorStoreBackend,
    ) -> None:
        self._graph_store = graph_store
        self._meta_store = meta_store
        self._vector_store = vector_store
        self._layer_r = LayerRRetriever(vector_store)
        self._layer_s = LayerSRetriever(graph_store, meta_store)

    async def collaborative_search(
        self,
        query_embedding: list[float],
        query_type: str = "mixed",
        top_k: int = 10,
    ) -> CollaborativeResult:
        fragments = await self._layer_r.search_knowledge_fragments(
            query_embedding, top_k=top_k,
        )

        fragment_ids = [f.fragment_id for f in fragments]
        entity_ids_from_r = await self._expand_via_supported_by(fragment_ids)

        entity_ids = list(set(entity_ids_from_r))
        structured = await self._layer_s.retrieve_neighbors(
            entity_ids[0] if entity_ids else "",
            query_type=query_type,
        ) if entity_ids else None

        evidence_chain = await self._build_evidence_chain(fragment_ids, entity_ids)

        return CollaborativeResult(
            fragments=fragments,
            entities=structured.entities if structured else [],
            edges=structured.edges if structured else [],
            evidence_chain=evidence_chain,
        )

    async def _expand_via_supported_by(self, fragment_ids: list[str]) -> list[str]:
        entity_ids: list[str] = []
        for fid in fragment_ids:
            try:
                neighbors = await self._graph_store.get_neighbors(
                    node_id=fid, direction="incoming", limit=10,
                )
                for nb in neighbors:
                    if nb.get("edge_type") in ("SUPPORTED_BY", "EXTRACTED_FROM"):
                        entity_ids.append(nb.get("neighbor_id", ""))
            except Exception:
                pass
        return entity_ids

    async def _build_evidence_chain(
        self,
        fragment_ids: list[str],
        entity_ids: list[str],
    ) -> list[EvidenceLink]:
        chain: list[EvidenceLink] = []
        for fid in fragment_ids[:5]:
            chain.append(EvidenceLink(
                source_id=fid,
                source_type="KnowledgeFragment",
                target_id=entity_ids[0] if entity_ids else "",
                target_type="Entity",
                trace_type="SUPPORTED_BY",
                confidence=0.7,
                edge_text="",
                offset_start=0,
                offset_end=0,
            ))
        return chain
