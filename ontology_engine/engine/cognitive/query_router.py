"""Query router for分层漏斗检索.

Implements query type detection, parameter mapping, funnel retrieval,
and degradation chain.

Design decisions (from query-routing.md):
- D-QR-1: Keyword matching over LLM classification
- D-QR-2: Detection priority temporal > analytical > multi-hop > factual
- D-QR-3: mixed type uses collaborative path
- D-QR-4: Funnel is main flow, query type is internal strategy
- D-QR-5: Scene-aware short-circuit
- D-QR-6: Async verification after short-circuit
- D-QR-7: DispositionProfile dynamic weights
- D-QR-8: Cold-start degradation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.query_router_types import (
    DEGRADATION_CHAINS,
    DEGRADATION_PATHS,
    MIN_RESULTS_THRESHOLD,
    PARAM_PRESETS,
    QUERY_TYPE_PATTERNS,
    RetrievalParams,
)
from ontology_engine.engine.cognitive.rrf_types import (
    COGNITIVE_LAYER_PRIORITY,
    RetrievalResult,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.models import DispositionProfile
    from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


def detect_query_type(query: str) -> str:
    """Detect query type from keyword patterns.

    Priority: temporal > decision > analytical > user_preference > multi-hop > factual > mixed

    Args:
        query: Query text.

    Returns:
        Detected query type string.
    """
    scores: dict[str, int] = {
        "factual": 0,
        "multi_hop": 0,
        "temporal": 0,
        "analytical": 0,
        "user_preference": 0,
        "decision": 0,
    }

    query_lower = query.lower()

    for qtype, patterns in QUERY_TYPE_PATTERNS.items():
        for lang, words in patterns.items():
            for word in words:
                if word in query_lower:
                    scores[qtype] += 1

    hit_types = [k for k, v in scores.items() if v > 0]

    if len(hit_types) == 0:
        return "factual"

    if "temporal" in hit_types:
        return "temporal"

    if "decision" in hit_types:
        return "decision"

    if "analytical" in hit_types:
        return "analytical"

    if "user_preference" in hit_types:
        return "user_preference"

    if len(hit_types) >= 2:
        return "mixed"

    priority_order = ["multi_hop", "factual"]
    for ptype in priority_order:
        if ptype in hit_types:
            return ptype

    return "factual"


class QueryRouter:
    """Query router with funnel retrieval and degradation.

    Implements:
    - Query type detection (D-QR-1, D-QR-2)
    - Parameter mapping (D-QR-4)
    - Funnel retrieval with short-circuit (D-QR-5)
    - Degradation chain (D-QR-8)
    - Disposition dynamic weights (D-QR-7)
    """

    def __init__(
        self,
        rrf_engine: "RRFFusionEngine",
        repository: "CognitiveRepository",
    ):
        """Initialize QueryRouter.

        Args:
            rrf_engine: RRF fusion engine for retrieval.
            repository: CognitiveRepository for node operations.
        """
        self._rrf = rrf_engine
        self._repo = repository

    async def route(
        self,
        query: str,
        space_id: str = "default",
        top_k: int = 10,
        disposition: "DispositionProfile | None" = None,
        allow_short_circuit: bool | None = None,
        strategy_adjustment: Any | None = None,
    ) -> list[RetrievalResult]:
        """Route a query through the funnel retrieval pipeline.

        Args:
            query: Query text.
            space_id: Space to search within.
            top_k: Maximum number of results.
            disposition: Optional DispositionProfile for dynamic weights.
            allow_short_circuit: Override short-circuit behavior.

        Returns:
            Ranked retrieval results.
        """
        query_type = detect_query_type(query)
        params = self._get_params(query_type, disposition, allow_short_circuit)

        if query_type == "analytical":
            logger.info("Analytical query routed to RRF: %s", query)
            disposition_weights = None
            if disposition:
                disposition_weights = await self._repo.compute_weights(disposition)
            results = await self._rrf.fuse(
                query=query,
                query_type="analytical",
                space_id=space_id,
                top_k=top_k,
                disposition_weights=disposition_weights,
                strategy_adjustment=strategy_adjustment,
            )
            return self._apply_funnel(results, params, disposition)

        disposition_weights = None
        if disposition:
            disposition_weights = await self._repo.compute_weights(disposition)

        all_results = await self._rrf.fuse(
            query=query,
            query_type=query_type,
            space_id=space_id,
            top_k=top_k,
            disposition_weights=disposition_weights,
            strategy_adjustment=strategy_adjustment,
        )

        results = self._apply_funnel(all_results, params, disposition)

        if params.allow_short_circuit and self._can_short_circuit(disposition) and results:
            import asyncio
            asyncio.create_task(self._verify_short_circuit(results, all_results))

        if len(results) < MIN_RESULTS_THRESHOLD:
            logger.info("Results below threshold (%d), triggering degradation", len(results))
            results = await self._degrade(query, query_type, space_id, top_k, disposition_weights)

        return results

    async def expand_evidence(
        self,
        node_id: str,
        space_id: str,
        depth: int = 1,
    ) -> list[RetrievalResult]:
        """Expand evidence chain for a given node.

        Args:
            node_id: Node ID to expand.
            space_id: Space identifier.
            depth: Expansion depth (1 or 2).

        Returns:
            List of supporting evidence nodes.
        """
        evidence: list[RetrievalResult] = []

        try:
            node = await self._repo.get_node(node_id)
            frag_count = len(node.source_fragment_ids) if node.source_fragment_ids else 1
            if depth >= 1 and node.source_fragment_ids:
                for idx, frag_id in enumerate(node.source_fragment_ids):
                    try:
                        frag = await self._repo.get_node(frag_id)
                        evidence.append(RetrievalResult(
                            doc_id=frag.id,
                            content=frag.content,
                            source="evidence_depth_1",
                            memory_type=frag.memory_type,
                            cognitive_layer=frag.cognitive_layer,
                            edge_type="SUPPORTS",
                            confidence=frag.confidence,
                            contribution=round(1.0 / frag_count, 3) if idx < frag_count else 0.0,
                        ))
                    except Exception:
                        continue

            if depth >= 2:
                for ev in list(evidence):
                    try:
                        ev_node = await self._repo.get_node(ev.doc_id)
                        if ev_node.source_fragment_ids:
                            for deeper_id in ev_node.source_fragment_ids:
                                try:
                                    deeper = await self._repo.get_node(deeper_id)
                                    evidence.append(RetrievalResult(
                                        doc_id=deeper.id,
                                        content=deeper.content,
                                        source="evidence_depth_2",
                                        memory_type=deeper.memory_type,
                                        cognitive_layer=deeper.cognitive_layer,
                                    ))
                                except Exception:
                                    continue
                    except Exception:
                        continue
        except Exception:
            pass

        return evidence

    def _get_params(
        self,
        query_type: str,
        disposition: "DispositionProfile | None",
        allow_short_circuit: bool | None,
    ) -> RetrievalParams:
        """Get retrieval parameters for a query type.

        Args:
            query_type: Detected query type.
            disposition: Optional DispositionProfile.
            allow_short_circuit: Override short-circuit behavior.

        Returns:
            RetrievalParams instance.
        """
        params = PARAM_PRESETS.get(query_type, PARAM_PRESETS["factual"])
        params = RetrievalParams(
            query_type=params.query_type,
            cognitive_layers=list(params.cognitive_layers),
            memory_types=list(params.memory_types),
            chroma_top_k=params.chroma_top_k,
            kuzu_max_depth=params.kuzu_max_depth,
            edge_weights=dict(params.edge_weights),
            temporal_filter=params.temporal_filter,
            cog_extracted_from_expansion=params.cog_extracted_from_expansion,
            cog_supported_by_backtrack=params.cog_supported_by_backtrack,
            bundle_search_enabled=params.bundle_search_enabled,
            rrf_weights=dict(params.rrf_weights),
            confidence_threshold=params.confidence_threshold,
            belief_status_filter=params.belief_status_filter,
            allow_short_circuit=params.allow_short_circuit,
        )

        if allow_short_circuit is not None:
            params.allow_short_circuit = allow_short_circuit

        if disposition:
            if hasattr(disposition, "thoroughness") and disposition.thoroughness > 0.8:
                params.allow_short_circuit = False
                params.confidence_threshold = 0.3

            if hasattr(disposition, "skepticism") and disposition.skepticism > 0.7:
                params.belief_status_filter = "all"

        return params

    def _apply_funnel(
        self,
        results: list[RetrievalResult],
        params: RetrievalParams,
        disposition: Any | None = None,
    ) -> list[RetrievalResult]:
        if not results:
            return results

        for r in results:
            r.metadata["funnel_priority"] = COGNITIVE_LAYER_PRIORITY.get(r.cognitive_layer, 0)

        results.sort(key=lambda r: (r.metadata.get("funnel_priority", 0), r.score), reverse=True)

        if params.allow_short_circuit and self._can_short_circuit(disposition) and results:
            top_priority = results[0].metadata.get("funnel_priority", 0)
            if top_priority >= COGNITIVE_LAYER_PRIORITY.get("semantic", 0):
                high_conf = [r for r in results if r.score >= params.confidence_threshold]
                if high_conf:
                    return high_conf

        return results

    def _can_short_circuit(self, disposition: Any | None) -> bool:
        if disposition and disposition.thoroughness > 0.7:
            return False
        if disposition and disposition.evidence_demand > 0.8:
            return False
        return True

    async def _verify_short_circuit(
        self,
        high_results: list[RetrievalResult],
        all_results: list[RetrievalResult],
    ) -> None:
        """Async verification: check if low-layer results contradict high-layer short-circuit results.

        Per RFC-023, after short-circuiting to high-layer results, we
        asynchronously check whether low-layer (procedure/perception)
        results have CONTRADICTS edges that would undermine the
        short-circuited conclusion.
        """
        low_layer = [
            r for r in all_results
            if r.cognitive_layer in ("procedure", "perception")
        ]
        for low in low_layer:
            try:
                edges = await self._repo.query_cognitive_edges(
                    from_id=low.doc_id, edge_type="CONTRADICTS", limit=5,
                )
                if edges:
                    for edge in edges:
                        contradicted_high = [
                            h for h in high_results if h.doc_id == edge.to_id
                        ]
                        if contradicted_high:
                            logger.warning(
                                "Short-circuit result %s contradicted by low-layer %s",
                                contradicted_high[0].doc_id, low.doc_id,
                            )
            except Exception:
                pass

    async def _degrade(
        self,
        query: str,
        query_type: str,
        space_id: str,
        top_k: int,
        disposition_weights: dict[str, float] | None,
    ) -> list[RetrievalResult]:
        """Apply degradation chain when results are insufficient.

        Args:
            query: Original query.
            query_type: Detected query type.
            space_id: Space identifier.
            top_k: Maximum results.
            disposition_weights: Optional disposition weights.

        Returns:
            Degraded retrieval results.
        """
        chain = DEGRADATION_CHAINS.get(query_type, DEGRADATION_CHAINS["factual"])

        for step_name in chain:
            method_name = DEGRADATION_PATHS.get(step_name)
            if not method_name:
                continue
            search_fn = getattr(self._rrf, method_name, None)
            if not search_fn:
                continue
            try:
                results = await search_fn(query, space_id, top_k)
                if results and len(results) >= MIN_RESULTS_THRESHOLD:
                    return results
            except Exception as e:
                logger.warning("Degradation step %s failed: %s", step_name, e)
                continue

        logger.info("Cold-start degradation: falling back to direct node query")
        try:
            nodes = await self._repo.query_nodes(domain_id=space_id, limit=top_k * 2)
            from ontology_engine.engine.cognitive.rrf_types import RetrievalResult
            fallback_results = [
                RetrievalResult(
                    doc_id=n.id,
                    content=n.content,
                    score=0.3,
                    memory_type=n.memory_type,
                    cognitive_layer=n.cognitive_layer,
                    occurred_at=n.occurred_at,
                    created_at=n.created_at,
                )
                for n in nodes
                if n.content and query.lower() in (n.content or "").lower()
            ][:top_k]
            if fallback_results:
                return fallback_results
        except Exception as e:
            logger.warning("Cold-start fallback failed: %s", e)

        return []
