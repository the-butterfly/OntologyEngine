"""Bundle Search four-phase algorithm.

Phase 1 — Wide Search: query all 7 ChromaDB collections in parallel.
Phase 2 — Graph Projection: project hit IDs onto KuzuDB, expand neighbors by
           node-type priority to build a coherent subgraph.
Phase 3 — Path Cost: propagate path cost through the subgraph using
           semantic distance + hop penalties + mutual-index miss penalties.
Phase 4 — Rank: sort by final_score descending and return top-k.
"""

from __future__ import annotations

import asyncio
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

# Node type priority for Phase 2 expansion: lower number = expand first
TYPE_PRIORITY: dict[str, int] = {
    "Entity": 0,
    "CategoryTag": 1,
    "MetricValue": 2,
    "KnowledgeFragment": 3,
    "RuleDefinition": 4,
}

# ── Cost constants ──────────────────────────────────────────────────────────
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

# Mutual-index edge types that indicate cross-layer hops
_CROSS_LAYER_EDGE_TYPES = frozenset(
    {"EXTRACTED_FROM", "SUPPORTED_BY", "DEFINED_IN", "TRACE_TO"}
)

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
    """Four-phase Bundle Search: wide search → graph projection → path cost → rank.

    Phase 2 change from v1:
      The old implementation simply deduped vector candidates (pure vector layer).
      The new Phase 2 projects hit IDs onto KuzuDB, fetches each node's direct
      neighbors, and expands the candidate set following TYPE_PRIORITY, so that
      Phase 3 path-cost is computed over a true subgraph rather than isolated
      vector hits.
    """

    def __init__(
        self,
        vector_store: VectorStoreBackend,
        graph_store: GraphStoreBackend,
        *,
        phase2_neighbors_per_node: int = 20,
    ) -> None:
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._phase2_neighbors_per_node = phase2_neighbors_per_node

    # ─────────────────────────── Phase 1 ────────────────────────────────────

    async def phase1_wide_search(
        self,
        query_embedding: list[float],
        top_k: int = 100,
        domain_id: str | None = None,
        is_temporal: bool = False,
    ) -> dict[str, list[BundleCandidate]]:
        """Search all 7 ChromaDB collections in parallel."""
        effective_top_k = min(top_k * 2, 300) if is_temporal else top_k

        async def _search_one(collection: str) -> tuple[str, list[BundleCandidate]]:
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
                    candidates.append(
                        BundleCandidate(
                            id=r.id,
                            node_type=metadata.get("node_type", "Entity"),
                            collection=collection,
                            raw_distance=raw_dist,
                            adjusted_score=adjusted,
                        )
                    )
                return collection, candidates
            except Exception:
                return collection, []

        pairs = await asyncio.gather(*[_search_one(c) for c in COLLECTIONS_FOR_BUNDLE])
        return dict(pairs)

    # ─────────────────────────── Phase 2 ────────────────────────────────────

    async def phase2_graph_projection(
        self,
        collection_results: dict[str, list[BundleCandidate]],
    ) -> dict[str, BundleCandidate]:
        """Project vector hits onto KuzuDB and expand neighbor subgraph.

        Algorithm:
        1. Collect all hit IDs from Phase 1, deduplicate keeping best score.
        2. Sort seeds by TYPE_PRIORITY (Entity first, KnowledgeFragment last).
        3. For each seed, query KuzuDB for direct neighbors (both directions).
        4. Add discovered neighbors to the candidate pool if not already present,
           assigning a penalty-adjusted score so they rank below direct hits.
        5. Return the merged candidate dict for Phase 3 cost propagation.
        """
        # Step 1 — best-score dedup across collections
        seed_map: dict[str, BundleCandidate] = {}
        for _coll, candidates in collection_results.items():
            for c in candidates:
                if c.id not in seed_map or c.adjusted_score > seed_map[c.id].adjusted_score:
                    seed_map[c.id] = c

        if not seed_map:
            return seed_map

        # Step 2 — sort seeds by TYPE_PRIORITY so important node types expand first
        sorted_seeds = sorted(
            seed_map.values(),
            key=lambda c: TYPE_PRIORITY.get(c.node_type, 99),
        )

        # Step 3 & 4 — expand neighbors from KuzuDB in parallel
        expanded: dict[str, BundleCandidate] = dict(seed_map)

        async def _expand_node(seed: BundleCandidate) -> list[BundleCandidate]:
            """Fetch neighbors from KuzuDB and return new BundleCandidate entries."""
            try:
                neighbors = await self._graph_store.get_neighbors(
                    node_id=seed.id,
                    direction="both",
                    limit=self._phase2_neighbors_per_node,
                )
            except Exception:
                return []

            new_candidates: list[BundleCandidate] = []
            for nb in neighbors:
                nb_id = nb.get("neighbor_id", "")
                if not nb_id or nb_id in seed_map:
                    # Already a direct hit; skip to avoid downgrading score
                    continue
                edge_type = nb.get("edge_type", "")
                # Neighbor score = seed score penalised by hop cost
                hop_penalty = (
                    CROSS_LAYER_HOP_COST
                    if edge_type in _CROSS_LAYER_EDGE_TYPES
                    else HOP_COST
                )
                nb_score = max(0.0, seed.adjusted_score - hop_penalty)
                nb_type = nb.get("node_type", "Entity")
                new_candidates.append(
                    BundleCandidate(
                        id=nb_id,
                        node_type=nb_type,
                        collection="__graph_expansion__",
                        raw_distance=seed.raw_distance + hop_penalty,
                        adjusted_score=nb_score,
                    )
                )
            return new_candidates

        results_list = await asyncio.gather(*[_expand_node(s) for s in sorted_seeds])
        for new_candidates in results_list:
            for nc in new_candidates:
                if nc.id not in expanded or nc.adjusted_score > expanded[nc.id].adjusted_score:
                    expanded[nc.id] = nc

        return expanded

    # ─────────────────────────── Phase 3 ────────────────────────────────────

    async def phase3_path_cost(
        self,
        candidates: dict[str, BundleCandidate],
        query_embedding: list[float],
    ) -> list[BundleResult]:
        """Compute path cost for every node in the projected subgraph.

        path_cost = raw_distance
                  + DIRECT_ENTITY_PENALTY (if node is a plain Entity)
                  + Σ hop/miss penalties for neighbors

        final_score = 1 / (1 + path_cost)

        Cost semantics (deliberate design choice):
        ─────────────────────────────────────────
        Both ``hop`` and ``miss`` *increase* path_cost, which in turn
        *decreases* final_score (since final_score = 1 / (1 + path_cost)).

        • ``hop``: an edge that connects to *another candidate in the set*.
          A small propagation cost (HOP_COST=0.05 for same-layer,
          CROSS_LAYER_HOP_COST=0.15 for mutual-index hops) is added to model
          the traversal cost of following that edge.  This is **not** a
          penalty for being well-connected; it is the cost of the path
          through a connected subgraph.  Nodes with many intra-set connections
          accumulate more hop cost, but also benefit from a lower raw_distance
          baseline because they are reachable from high-scoring seeds.

        • ``miss``: an edge that leads *outside* the candidate set entirely.
          This is a deliberate miss-penalty (MUTUAL_INDEX_MISS_PENALTY or
          EDGE_MISS_COST=0.9) because an out-of-set edge carries no
          supporting evidence for the query and acts as noise.

        If you prefer a reward-based model instead (where intra-set
        connections *lower* path_cost), negate the hop term:
          ``path_cost -= hop``
        The current additive model matches the original Bundle Search
        specification where graph traversal is always costly.
        """
        results: list[BundleResult] = []

        for cid, candidate in candidates.items():
            path_cost = candidate.raw_distance
            if candidate.node_type == "Entity" and candidate.collection != "__graph_expansion__":
                path_cost += DIRECT_ENTITY_PENALTY

            try:
                neighbors = await self._graph_store.get_neighbors(
                    node_id=cid,
                    direction="both",
                    limit=20,
                )
            except Exception:
                neighbors = []

            for nb in neighbors:
                nb_id = nb.get("neighbor_id", "")
                edge_type = nb.get("edge_type", "")
                if nb_id in candidates:
                    # Edge connects to another candidate — add propagation cost.
                    # See docstring above for design rationale.
                    hop = (
                        CROSS_LAYER_HOP_COST
                        if edge_type in _CROSS_LAYER_EDGE_TYPES
                        else HOP_COST
                    )
                    path_cost += hop
                else:
                    # Edge leads outside the candidate set — miss penalty.
                    miss = MUTUAL_INDEX_MISS_PENALTY.get(edge_type, EDGE_MISS_COST)
                    path_cost += miss

            final_score = 1.0 / (1.0 + path_cost)
            results.append(
                BundleResult(
                    entity_id=cid,
                    entity_type=candidate.node_type,
                    path_cost=path_cost,
                    final_score=final_score,
                )
            )

        return sorted(results, key=lambda r: r.final_score, reverse=True)

    # ─────────────────────────── Public API ─────────────────────────────────

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        domain_id: str | None = None,
        is_temporal: bool = False,
    ) -> list[BundleResult]:
        """Execute four-phase Bundle Search and return top-k results."""
        collection_results = await self.phase1_wide_search(
            query_embedding,
            top_k=100,
            domain_id=domain_id,
            is_temporal=is_temporal,
        )
        projected = await self.phase2_graph_projection(collection_results)
        scored = await self.phase3_path_cost(projected, query_embedding)
        return scored[:top_k]
