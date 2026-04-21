"""Bundle Search four-phase algorithm."""

from __future__ import annotations

from dataclasses import dataclass, field

from ontology_engine.storage.base import VectorStoreBackend, GraphStoreBackend


COLLECTIONS_FOR_BUNDLE = [
    "entity_name",
    "entity_summary",
    "facet_search_text",
    "edge_relationship_name",
    "edge_text",
    "knowledge_fragment",
    "rule_definition",
]

TYPE_PRIORITY: dict[str, int] = {
    "Entity": 0,
    "CategoryTag": 1,
    "MetricValue": 2,
    "KnowledgeFragment": 3,
    "RuleDefinition": 4,
}

EDGE_MISS_COST = 0.9
HOP_COST = 0.05
CROSS_LAYER_HOP_COST = 0.15
DIRECT_ENTITY_PENALTY = 0.3
MAX_RELEVANT_IDS = 300

MUTUAL_INDEX_MISS_PENALTY: dict[str, float] = {
    "EXTRACTED_FROM": 0.5,
    "SUPPORTED_BY": 0.7,
    "DEFINED_IN": 0.3,
    "TRACE_TO": 0.6,
}

COLLECTION_BASELINES: dict[str, float] = {
    "facet_search_text": 0.60,
    "edge_text": 0.56,
    "entity_name": 0.68,
    "entity_summary": 1.06,
    "knowledge_fragment": 1.06,
}


@dataclass
class BundleCandidate:
    id: str
    node_type: str
    collection: str
    raw_distance: float
    adjusted_score: float


@dataclass
class BundleResult:
    entity_id: str
    entity_type: str
    path_cost: float
    final_score: float
    path_nodes: list[str] = field(default_factory=list)
    path_edges: list[str] = field(default_factory=list)


class BundleSearchEngine:
    """Four-phase Bundle Search: wide search → dedup → path cost → rank."""

    def __init__(self, vector_store: VectorStoreBackend, graph_store: GraphStoreBackend) -> None:
        self._vector_store = vector_store
        self._graph_store = graph_store

    async def phase1_wide_search(
        self,
        query_embedding: list[float],
        top_k: int = 100,
        domain_id: str | None = None,
        is_temporal: bool = False,
    ) -> dict[str, list[BundleCandidate]]:
        effective_top_k = min(top_k * 2, 300) if is_temporal else top_k
        collection_results: dict[str, list[BundleCandidate]] = {}

        for collection in COLLECTIONS_FOR_BUNDLE:
            try:
                results = await self._vector_store.search(
                    query_embedding=query_embedding,
                    top_k=effective_top_k,
                    collection_name=collection,
                )
                baseline = COLLECTION_BASELINES.get(collection, 1.0)
                candidates: list[BundleCandidate] = []
                for r in results:
                    raw_dist = r.distance if r.distance is not None else 1.0
                    adjusted = (1.0 - raw_dist) / baseline if baseline > 0 else 0.0
                    metadata = r.metadata or {}
                    candidates.append(BundleCandidate(
                        id=r.id,
                        node_type=metadata.get("node_type", "Entity"),
                        collection=collection,
                        raw_distance=raw_dist,
                        adjusted_score=adjusted,
                    ))
                collection_results[collection] = candidates
            except Exception:
                collection_results[collection] = []

        return collection_results

    async def phase2_dedup(
        self,
        collection_results: dict[str, list[BundleCandidate]],
    ) -> dict[str, BundleCandidate]:
        best: dict[str, BundleCandidate] = {}
        for _coll, candidates in collection_results.items():
            for c in candidates:
                if c.id not in best or c.adjusted_score > best[c.id].adjusted_score:
                    best[c.id] = c
        return best

    async def phase3_path_cost(
        self,
        candidates: dict[str, BundleCandidate],
        query_embedding: list[float],
    ) -> list[BundleResult]:
        results: list[BundleResult] = []
        for cid, candidate in candidates.items():
            path_cost = candidate.raw_distance
            if candidate.node_type == "Entity":
                path_cost += DIRECT_ENTITY_PENALTY

            neighbors = await self._graph_store.get_neighbors(
                node_id=cid, direction="both", limit=20,
            )
            for nb in neighbors:
                nb_id = nb.get("neighbor_id", "")
                if nb_id in candidates:
                    path_cost += HOP_COST
                else:
                    edge_type = nb.get("edge_type", "")
                    miss = MUTUAL_INDEX_MISS_PENALTY.get(edge_type, EDGE_MISS_COST)
                    path_cost += miss

            final_score = 1.0 / (1.0 + path_cost)
            results.append(BundleResult(
                entity_id=cid,
                entity_type=candidate.node_type,
                path_cost=path_cost,
                final_score=final_score,
            ))

        return sorted(results, key=lambda r: r.final_score, reverse=True)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        domain_id: str | None = None,
        is_temporal: bool = False,
    ) -> list[BundleResult]:
        collection_results = await self.phase1_wide_search(
            query_embedding, top_k=100, domain_id=domain_id, is_temporal=is_temporal,
        )
        deduped = await self.phase2_dedup(collection_results)
        scored = await self.phase3_path_cost(deduped, query_embedding)
        return scored[:top_k]
