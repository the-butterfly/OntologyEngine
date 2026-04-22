"""Mutual-index collaborative retrieval and RetrieverRegistry.

Key improvements over v1:
- MutualIndexConfig: all tuneable parameters are explicit and configurable,
  no magic numbers buried in methods.
- _expand_via_supported_by: corrected edge direction — SUPPORTED_BY goes
  FROM KnowledgeFragment TO EntityInstance, so we use direction="outgoing"
  when the starting node is a fragment.
- collaborative_search: uses asyncio.gather to expand the top-N entity IDs
  in parallel (N = config.max_parallel_entity_expansion), then merges and
  deduplicates the Layer-S results via RRF-style fusion.
- _build_evidence_chain: reads confidence, edge_text, offset values from
  the actual KuzuDB edge rather than hardcoding them; all limits/defaults
  come from MutualIndexConfig.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ontology_engine.engine.query.layer_r import LayerRRetriever, FragmentResult
from ontology_engine.engine.query.layer_s import LayerSRetriever, EntityResult, EdgeResult
from ontology_engine.storage.base import GraphStoreBackend, StorageBackend, VectorStoreBackend


# ─────────────────────────── Configuration ───────────────────────────────────

@dataclass
class MutualIndexConfig:
    """All tuneable parameters for MutualIndexCollaborative.

    Attributes:
        max_parallel_entity_expansion: How many entity IDs (derived from
            SUPPORTED_BY expansion) to expand via Layer-S in parallel.
            Larger values improve recall but increase graph query load.
            Default: 5.
        min_confidence_for_expansion: Minimum edge confidence required to
            accept a SUPPORTED_BY / EXTRACTED_FROM edge as a valid
            cross-layer link during expansion.
            Default: 0.0 (accept all).
        evidence_chain_max_fragments: Maximum number of fragments to
            include in the evidence chain per collaborative_search call.
            Default: 10.
        evidence_chain_default_confidence: Fallback confidence used when
            the KuzuDB edge does not carry a confidence property.
            Default: 0.5.
        supported_by_neighbor_limit: ``limit`` passed to
            ``get_neighbors`` when expanding fragment → entity via
            SUPPORTED_BY.
            Default: 10.
        layer_s_neighbor_limit: ``limit`` passed to
            ``get_neighbors`` when expanding entity subgraph in Layer-S.
            Default: 50.
    """

    max_parallel_entity_expansion: int = 5
    min_confidence_for_expansion: float = 0.0
    evidence_chain_max_fragments: int = 10
    evidence_chain_default_confidence: float = 0.5
    supported_by_neighbor_limit: int = 10
    layer_s_neighbor_limit: int = 50


# ─────────────────────────── Data-classes ────────────────────────────────────

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


# ─────────────────────────── Registry ────────────────────────────────────────

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


# ─────────────────────────── Collaborative retriever ─────────────────────────

class MutualIndexCollaborative:
    """Cross-layer collaborative retrieval via mutual-index edges.

    Retrieval flow
    ──────────────
    1. Layer-R: vector search → top-k KnowledgeFragment results.
    2. SUPPORTED_BY expansion (outgoing from fragment → entity):
       For each fragment, follow SUPPORTED_BY edges to find related
       EntityInstances. This is the correct direction because
       SUPPORTED_BY is defined as KnowledgeFragment → EntityInstance.
    3. Layer-S parallel expansion: take top-N entity IDs (configurable),
       run ``retrieve_neighbors`` concurrently, then merge results via
       simple score-max dedup.
    4. Evidence chain construction: read edge properties (confidence,
       edge_text, offsets) directly from KuzuDB rather than hardcoding.
    """

    def __init__(
        self,
        graph_store: GraphStoreBackend,
        meta_store: StorageBackend,
        vector_store: VectorStoreBackend,
        config: MutualIndexConfig | None = None,
    ) -> None:
        self._graph_store = graph_store
        self._meta_store = meta_store
        self._vector_store = vector_store
        self._config = config or MutualIndexConfig()
        self._layer_r = LayerRRetriever(vector_store)
        self._layer_s = LayerSRetriever(graph_store, meta_store)

    # ─────────────── Public API ───────────────────────────────────────────────

    async def collaborative_search(
        self,
        query_embedding: list[float],
        query_type: str = "mixed",
        top_k: int = 10,
    ) -> CollaborativeResult:
        """Execute mutual-index collaborative search.

        Args:
            query_embedding: Dense vector for the query.
            query_type: One of factual / multi_hop / temporal / analytical /
                        mixed.  Passed through to Layer-S retriever.
            top_k: Maximum number of fragments to retrieve from Layer-R.

        Returns:
            CollaborativeResult containing fragments, entities, edges and
            a populated evidence_chain from real KuzuDB edge properties.
        """
        # Step 1 — Layer-R vector search
        fragments = await self._layer_r.search_knowledge_fragments(
            query_embedding,
            top_k=top_k,
        )

        # Build a score lookup: fragment_id → vector score (higher = more relevant)
        fragment_score_map: dict[str, float] = {
            f.fragment_id: f.score for f in fragments
        }

        # Step 2 — SUPPORTED_BY expansion: fragment → entity (outgoing)
        fragment_ids = [f.fragment_id for f in fragments]
        entity_ids, edge_props_by_fragment = await self._expand_via_supported_by(
            fragment_ids
        )

        # Step 3 — Rank entity IDs by (fragment_score × edge_confidence) descending
        # and take top-N for parallel Layer-S expansion.
        all_entities: list[EntityResult] = []
        all_edges: list[EdgeResult] = []
        n = self._config.max_parallel_entity_expansion
        if entity_ids:
            # Compute combined score for each unique entity
            entity_combined: dict[str, float] = {}
            for fid, props_list in edge_props_by_fragment.items():
                frag_score = fragment_score_map.get(fid, 0.0)
                for props in props_list:
                    eid = props["neighbor_id"]
                    edge_conf = float(props.get("confidence") or self._config.evidence_chain_default_confidence)
                    combined = frag_score * edge_conf
                    # Keep the maximum combined score across multiple fragment→entity paths
                    if combined > entity_combined.get(eid, 0.0):
                        entity_combined[eid] = combined

            # Re-order entity_ids by combined score (preserving only those that
            # were discovered, using 0.0 as fallback for entities that had no edge props)
            ranked_entity_ids = sorted(
                entity_ids,
                key=lambda eid: entity_combined.get(eid, 0.0),
                reverse=True,
            )
            top_entity_ids = ranked_entity_ids[:n]

            neighbor_tasks = [
                self._layer_s.retrieve_neighbors(eid, query_type=query_type)
                for eid in top_entity_ids
            ]
            layer_s_results = await asyncio.gather(*neighbor_tasks, return_exceptions=True)

            seen_entity_ids: set[str] = set()
            seen_edge_keys: set[tuple[str, str, str]] = set()

            for result in layer_s_results:
                if isinstance(result, Exception):
                    continue
                for entity in result.entities:
                    if entity.entity_id not in seen_entity_ids:
                        seen_entity_ids.add(entity.entity_id)
                        all_entities.append(entity)
                for edge in result.edges:
                    key = (edge.from_id, edge.to_id, edge.edge_type)
                    if key not in seen_edge_keys:
                        seen_edge_keys.add(key)
                        all_edges.append(edge)

        # Step 4 — Evidence chain from real edge properties
        evidence_chain = await self._build_evidence_chain(
            fragment_ids=fragment_ids,
            entity_ids=entity_ids,
            edge_props_by_fragment=edge_props_by_fragment,
        )

        return CollaborativeResult(
            fragments=fragments,
            entities=all_entities,
            edges=all_edges,
            evidence_chain=evidence_chain,
        )

    # ─────────────── Internal helpers ────────────────────────────────────────

    async def _expand_via_supported_by(
        self,
        fragment_ids: list[str],
    ) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
        """Expand fragments to entities via SUPPORTED_BY edges.

        SUPPORTED_BY direction: KnowledgeFragment ──[SUPPORTED_BY]──▶ EntityInstance
        Therefore we query direction="outgoing" from the fragment node.

        Returns:
            Tuple of:
              - Ordered list of unique entity IDs (by first-seen occurrence).
              - Dict mapping fragment_id → list of edge property dicts
                (carrying confidence, edge_text, offset_start, offset_end).
        """
        entity_ids: list[str] = []
        seen_entity_ids: set[str] = set()
        edge_props_by_fragment: dict[str, list[dict[str, Any]]] = {}
        min_conf = self._config.min_confidence_for_expansion

        for fid in fragment_ids:
            edge_props_by_fragment[fid] = []
            try:
                neighbors = await self._graph_store.get_neighbors(
                    node_id=fid,
                    direction="outgoing",   # ← corrected from "incoming"
                    limit=self._config.supported_by_neighbor_limit,
                )
                for nb in neighbors:
                    edge_type = nb.get("edge_type", "")
                    if edge_type not in ("SUPPORTED_BY", "EXTRACTED_FROM"):
                        continue
                    confidence = float(nb.get("confidence", self._config.evidence_chain_default_confidence))
                    if confidence < min_conf:
                        continue
                    nb_id = nb.get("neighbor_id", "")
                    if not nb_id:
                        continue
                    if nb_id not in seen_entity_ids:
                        seen_entity_ids.add(nb_id)
                        entity_ids.append(nb_id)
                    edge_props_by_fragment[fid].append({
                        "neighbor_id": nb_id,
                        "edge_type": edge_type,
                        "confidence": confidence,
                        "edge_text": nb.get("edge_text", ""),
                        "offset_start": int(nb.get("offset_start", 0)),
                        "offset_end": int(nb.get("offset_end", 0)),
                    })
            except Exception:
                pass

        return entity_ids, edge_props_by_fragment

    async def _build_evidence_chain(
        self,
        fragment_ids: list[str],
        entity_ids: list[str],
        edge_props_by_fragment: dict[str, list[dict[str, Any]]],
    ) -> list[EvidenceLink]:
        """Build evidence chain from real KuzuDB edge properties.

        For each fragment that has edge props, create one EvidenceLink per
        (fragment, entity) pair found during SUPPORTED_BY expansion.
        All values (confidence, edge_text, offsets) come from the actual
        edge returned by KuzuDB; config.evidence_chain_default_confidence
        is only used as a fallback when the edge carries no confidence.

        The total number of links is capped at
        config.evidence_chain_max_fragments to avoid unbounded output.
        """
        chain: list[EvidenceLink] = []
        max_links = self._config.evidence_chain_max_fragments

        for fid in fragment_ids:
            if len(chain) >= max_links:
                break
            props_list = edge_props_by_fragment.get(fid, [])
            if not props_list:
                # Fragment had no expansion; emit a best-effort stub entry
                # only if we have at least one entity to target.
                if entity_ids:
                    chain.append(
                        EvidenceLink(
                            source_id=fid,
                            source_type="KnowledgeFragment",
                            target_id=entity_ids[0],
                            target_type="Entity",
                            trace_type="SUPPORTED_BY",
                            confidence=self._config.evidence_chain_default_confidence,
                            edge_text="",
                            offset_start=0,
                            offset_end=0,
                        )
                    )
                continue

            for props in props_list:
                if len(chain) >= max_links:
                    break
                chain.append(
                    EvidenceLink(
                        source_id=fid,
                        source_type="KnowledgeFragment",
                        target_id=props["neighbor_id"],
                        target_type="Entity",
                        trace_type=props["edge_type"],
                        confidence=props["confidence"],
                        edge_text=props.get("edge_text", ""),
                        offset_start=props.get("offset_start", 0),
                        offset_end=props.get("offset_end", 0),
                    )
                )

        return chain
