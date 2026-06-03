"""DeduplicationGate — write-time governance for the cognitive memory system.

Intercepts incoming memories before they are stored, performing three checks:
1. Fast vector deduplication (similarity > threshold → DUPLICATE)
2. Contradiction pre-detection (semantic conflict → CONTRADICTION_CANDIDATE)
3. Marginal value assessment (novelty × relevance / redundancy → DELAYED)

Design reference: docs/02-design/agent-memory/memory-lifecycle.md §0
"""

from __future__ import annotations

import enum
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class WriteDecision(enum.Enum):
    ACCEPT = "accept"
    DUPLICATE = "duplicate"
    CONTRADICTION_CANDIDATE = "contradiction_candidate"
    DELAYED = "delayed"


@dataclass
class GateResult:
    decision: WriteDecision
    reason: str = ""
    duplicate_of: str | None = None
    contradiction_with: list[str] = field(default_factory=list)
    marginal_value: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    existing_node: Any | None = None
    similarity: float | None = None


class DeduplicationGate:
    """Write-time governance gate for the cognitive memory system.

    Inserted between the API layer and the storage layer, this gate
    checks incoming memories for duplicates, contradictions, and
    marginal value before allowing them to be stored.

    Usage:
        gate = DeduplicationGate(repository=repo, vector_index=vector_index)
        result = await gate.check(content, space_id, memory_type, tags)
        if result.decision == WriteDecision.ACCEPT:
            # proceed with storage
        elif result.decision == WriteDecision.DUPLICATE:
            # update access count only
    """

    DEFAULT_SIMILARITY_THRESHOLD = 0.92
    DEFAULT_MARGINAL_VALUE_THRESHOLD = 0.15
    DEFAULT_CONTRADICTION_CANDIDATE_THRESHOLD = 0.80

    def __init__(
        self,
        repository: Any,
        vector_index: Any | None = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        marginal_value_threshold: float = DEFAULT_MARGINAL_VALUE_THRESHOLD,
        contradiction_threshold: float = DEFAULT_CONTRADICTION_CANDIDATE_THRESHOLD,
        orbit_router: Any | None = None,
    ):
        self._repo = repository
        self._vector_index = vector_index
        self._similarity_threshold = similarity_threshold
        self._marginal_value_threshold = marginal_value_threshold
        self._contradiction_threshold = contradiction_threshold
        self._orbit_router = orbit_router

    async def check(
        self,
        content: str,
        space_id: str,
        memory_type: str = "fragment",
        tags: dict[str, str | list[str]] | None = None,
        confidence: float = 1.0,
        source_pipeline: str = "",
        source_trust_tier: str = "",
    ) -> GateResult:
        dedup_result = await self._check_duplicate(content, space_id, memory_type, tags)
        if dedup_result.decision != WriteDecision.ACCEPT:
            if dedup_result.decision == WriteDecision.CONTRADICTION_CANDIDATE and self._orbit_router:
                orbit_result = self._orbit_router.route_ingest_contradiction(
                    new_source_pipeline=source_pipeline,
                    new_source_trust_tier=source_trust_tier,
                    existing_node=dedup_result.existing_node,
                    similarity=dedup_result.similarity or 0.0,
                )
                dedup_result.metadata["orbit"] = orbit_result.orbit.value
                dedup_result.metadata["orbit_action"] = orbit_result.action
                if orbit_result.orbit.value == "A":
                    dedup_result.metadata["requires_human_review"] = True
            return dedup_result

        contradiction_result = await self._check_contradiction(content, space_id, memory_type, tags)
        if contradiction_result.decision != WriteDecision.ACCEPT:
            if self._orbit_router:
                orbit_result = self._orbit_router.route_ingest_contradiction(
                    new_source_pipeline=source_pipeline,
                    new_source_trust_tier=source_trust_tier,
                    existing_node=contradiction_result.existing_node,
                    similarity=contradiction_result.similarity or 0.0,
                )
                contradiction_result.metadata["orbit"] = orbit_result.orbit.value
                contradiction_result.metadata["orbit_action"] = orbit_result.action
            return contradiction_result

        marginal_result = await self._check_marginal_value(
            content, space_id, memory_type, tags, confidence,
        )
        return marginal_result

    async def _check_duplicate(
        self,
        content: str,
        space_id: str,
        memory_type: str,
        tags: dict[str, str | list[str]] | None,
    ) -> GateResult:
        """Check 1: Fast vector deduplication.

        Uses vector similarity search to find near-duplicate content.
        If similarity > threshold, mark as DUPLICATE and return
        the existing node ID.

        Only uses true vector embeddings for deduplication.
        BM25 fallback is NOT used for dedup because its scores
        are not comparable to cosine similarity thresholds.
        """
        if not self._vector_index:
            return GateResult(decision=WriteDecision.ACCEPT, reason="no_vector_index")

        try:
            query_vector = await self._vector_index._compute_embedding(content)
            if query_vector is None:
                dedup_result = await self._check_duplicate_by_content_hash(content, space_id)
                if dedup_result is not None:
                    return dedup_result
                return GateResult(decision=WriteDecision.ACCEPT, reason="no_embedding_model")

            results = await self._vector_index._vector_search_embedding(
                query_vector, space_id, top_k=3,
            )
            for r in results:
                if r.score >= self._similarity_threshold:
                    node = await self._repo.get_node(r.doc_id)
                    if node and node.belief_status not in ("superseded", "rejected"):
                        from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
                        conflict = ReflectAgent._has_mutually_exclusive_values(content, node.content)
                        has_negation = ReflectAgent._has_negation_conflict(content, node.content)
                        if conflict or has_negation:
                            logger.info(
                                "Contradiction in high-similarity pair: score=%.3f, "
                                "conflict=%s for content='%s'",
                                r.score, conflict or "negation", content[:50],
                            )
                            return GateResult(
                                decision=WriteDecision.CONTRADICTION_CANDIDATE,
                                reason=f"value_conflict_in_duplicate: {conflict or 'negation'}",
                                contradiction_with=[r.doc_id],
                                existing_node=node,
                                similarity=r.score,
                            )

                    logger.info(
                        "Duplicate detected: score=%.3f for content='%s'",
                        r.score, content[:50],
                    )
                    return GateResult(
                        decision=WriteDecision.DUPLICATE,
                        reason=f"vector_similarity={r.score:.3f}",
                        duplicate_of=r.doc_id,
                    )
        except Exception as e:
            logger.warning("Vector dedup check failed: %s", e)

        return GateResult(decision=WriteDecision.ACCEPT, reason="no_duplicate_found")

    async def _check_duplicate_by_content_hash(
        self,
        content: str,
        space_id: str,
    ) -> GateResult | None:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        try:
            nodes = await self._repo.query_nodes(domain_id=space_id, limit=500)
            for node in nodes:
                if node.belief_status in ("superseded", "rejected"):
                    continue
                node_hash = hashlib.sha256(node.content.encode()).hexdigest()
                if node_hash == content_hash:
                    logger.info(
                        "Duplicate by content hash: content='%s'",
                        content[:50],
                    )
                    return GateResult(
                        decision=WriteDecision.DUPLICATE,
                        reason="content_hash_match",
                        duplicate_of=node.id,
                    )
        except Exception as e:
            logger.warning("Content hash dedup check failed: %s", e)
        return None

    async def _check_contradiction(
        self,
        content: str,
        space_id: str,
        memory_type: str,
        tags: dict[str, str | list[str]] | None,
    ) -> GateResult:
        """Check 2: Contradiction pre-detection.

        Searches for semantically similar content with different
        factual claims. Uses vector search to find candidates,
        then checks for value conflicts using the same patterns
        as ReflectAgent.
        """
        if not self._vector_index:
            return GateResult(decision=WriteDecision.ACCEPT, reason="no_vector_index")

        try:
            query_vector = await self._vector_index._compute_embedding(content)
            if query_vector is None:
                return GateResult(decision=WriteDecision.ACCEPT, reason="no_embedding_model")

            results = await self._vector_index._vector_search_embedding(
                query_vector, space_id, top_k=5,
            )
            candidates = [
                r for r in results
                if self._contradiction_threshold <= r.score < self._similarity_threshold
            ]

            if not candidates:
                return GateResult(decision=WriteDecision.ACCEPT, reason="no_contradiction_candidates")

            from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
            contradiction_ids = []
            for candidate in candidates:
                node = await self._repo.get_node(candidate.doc_id)
                if not node:
                    continue
                if node.belief_status in ("superseded", "rejected"):
                    continue
                conflict = ReflectAgent._has_mutually_exclusive_values(content, node.content)
                has_negation = ReflectAgent._has_negation_conflict(content, node.content)
                if conflict or has_negation:
                    contradiction_ids.append(candidate.doc_id)

            if contradiction_ids:
                logger.info(
                    "Contradiction candidate: %d conflicts for content='%s'",
                    len(contradiction_ids), content[:50],
                )
                first_node = None
                first_sim = None
                for candidate in candidates:
                    if candidate.doc_id in contradiction_ids:
                        first_node = await self._repo.get_node(candidate.doc_id)
                        first_sim = candidate.score
                        break
                return GateResult(
                    decision=WriteDecision.CONTRADICTION_CANDIDATE,
                    reason=f"conflicts_with_{len(contradiction_ids)}_nodes",
                    contradiction_with=contradiction_ids,
                    existing_node=first_node,
                    similarity=first_sim,
                )
        except Exception as e:
            logger.warning("Contradiction check failed: %s", e)

        return GateResult(decision=WriteDecision.ACCEPT, reason="no_contradiction_found")

    async def _check_marginal_value(
        self,
        content: str,
        space_id: str,
        memory_type: str,
        tags: dict[str, str | list[str]] | None,
        confidence: float,
    ) -> GateResult:
        """Check 3: Marginal value assessment.

        Computes: marginal_value = novelty × relevance / (redundancy + 0.1)
        - novelty: 1 - max_similarity (how different from existing)
        - relevance: confidence × type_weight
        - redundancy: count of similar nodes / 10

        If marginal_value < threshold, mark as DELAYED.
        """
        if not self._vector_index:
            return GateResult(
                decision=WriteDecision.ACCEPT,
                reason="no_vector_index",
                marginal_value=1.0,
            )

        try:
            query_vector = await self._vector_index._compute_embedding(content)
            if query_vector is None:
                return GateResult(
                    decision=WriteDecision.ACCEPT,
                    reason="no_embedding_model",
                    marginal_value=1.0,
                )

            results = await self._vector_index._vector_search_embedding(
                query_vector, space_id, top_k=10,
            )

            max_similarity = max((r.score for r in results), default=0.0)
            novelty = 1.0 - max_similarity

            from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS
            type_weight = BASE_TYPE_WEIGHTS.get(memory_type, 1.0)
            relevance = confidence * type_weight

            similar_count = sum(1 for r in results if r.score >= 0.7)
            redundancy = similar_count / 10.0

            marginal_value = novelty * relevance / (redundancy + 0.1)

            if marginal_value < self._marginal_value_threshold:
                logger.info(
                    "Delayed: marginal_value=%.3f < threshold=%.3f for content='%s'",
                    marginal_value, self._marginal_value_threshold, content[:50],
                )
                return GateResult(
                    decision=WriteDecision.DELAYED,
                    reason=f"marginal_value={marginal_value:.3f}",
                    marginal_value=marginal_value,
                )

            return GateResult(
                decision=WriteDecision.ACCEPT,
                reason="passed_marginal_value",
                marginal_value=marginal_value,
            )
        except Exception as e:
            logger.warning("Marginal value check failed: %s", e)
            return GateResult(
                decision=WriteDecision.ACCEPT,
                reason=f"check_error: {e}",
                marginal_value=1.0,
            )
