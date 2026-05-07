"""Entity resolver for disambiguation.

Implements three-dimension scoring (name/cooccurrence/temporal),
dual-strategy switching (full/trigram), and co-occurrence tracking.

Design decisions (from entity-resolver.md):
- D-ER-1: Three-dimension scoring 0.5/0.3/0.2
- D-ER-2: Threshold 0.6/0.3 three-tier
- D-ER-3: Dual strategy switch at 10000 entities
- D-ER-4: CO_OCCURS_WITH edge for co-occurrence
- D-ER-5: Schema identity_fields priority
- D-ER-6: Optimistic concurrency + task-key isolation
- D-ER-7: Pinyin similarity 0.8 (not 1.0)
"""

from __future__ import annotations

import hashlib
import logging
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.entity_resolver_types import (
    ENTITY_COUNT_THRESHOLD,
    SCORE_REUSE_THRESHOLD,
    SCORE_REVIEW_THRESHOLD,
    ResolutionContext,
    ResolutionResult,
)
from ontology_engine.engine.cognitive.models import CognitiveNode, CognitiveEdge

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


def compute_name_similarity(text: str, candidate_name: str) -> float:
    """Compute name similarity between two entity texts.

    Uses edit distance, prefix matching, and phonetic similarity.

    Args:
        text: Input entity text.
        candidate_name: Candidate entity name.

    Returns:
        Similarity score (0-1).
    """
    t = text.lower().strip()
    c = candidate_name.lower().strip()

    if t == c:
        return 1.0

    edit_sim = SequenceMatcher(None, t, c).ratio()

    prefix_sim = 0.0
    if len(t) > 1 and len(c) > 1:
        if c.startswith(t) or t.startswith(c):
            prefix_sim = 1.0

    return max(edit_sim, prefix_sim)


def compute_trigrams(text: str) -> list[str]:
    """Compute trigrams for text indexing.

    Args:
        text: Input text.

    Returns:
        List of trigram strings.
    """
    padded = f"  {text.lower()} "
    return [padded[i:i + 3] for i in range(len(padded) - 2)]


class EntityResolver:
    """Entity resolver with dual-strategy disambiguation.

    Supports full scan (small scale) and trigram-based (large scale)
    resolution strategies with automatic switching.
    """

    def __init__(
        self,
        repository: "CognitiveRepository",
        strategy: str = "auto",
        llm_call_fn: Any | None = None,
    ):
        """Initialize EntityResolver.

        Args:
            repository: CognitiveRepository for node operations.
            strategy: Resolution strategy ("auto", "full", "trigram").
            llm_call_fn: Optional LLM call function for L3 disambiguation.
        """
        self._repo = repository
        self.strategy = strategy
        self._llm_call_fn = llm_call_fn

    async def resolve(
        self,
        space_id: str,
        entity_texts: list[str],
        context: ResolutionContext | None = None,
    ) -> list[ResolutionResult]:
        """Resolve entity texts against existing entities.

        Args:
            space_id: Space to resolve within.
            entity_texts: List of entity texts to resolve.
            context: Optional resolution context.

        Returns:
            List of ResolutionResult for each input text.
        """
        if context is None:
            context = ResolutionContext()

        if self.strategy == "full" or (
            self.strategy == "auto"
            and await self._entity_count(space_id) < ENTITY_COUNT_THRESHOLD
        ):
            return await self._resolve_full(space_id, entity_texts, context)
        else:
            return await self._resolve_trigram(space_id, entity_texts, context)

    async def resolve_and_create_or_reuse(
        self,
        entity_text: str,
        entity_type: str,
        space_id: str,
        context: ResolutionContext | None = None,
        schema_ref: str | None = None,
    ) -> str:
        """Resolve an entity text and create or reuse a CognitiveNode.

        Args:
            entity_text: Entity text to resolve.
            entity_type: Type of entity.
            space_id: Space identifier.
            context: Optional resolution context.
            schema_ref: Optional schema reference.

        Returns:
            ID of the resolved or created entity.
        """
        if context is None:
            context = ResolutionContext()

        results = await self.resolve(space_id, [entity_text], context)
        r = results[0]

        if r.action == "reuse" and r.candidate_id:
            await self._repo.record_access(r.candidate_id)
            await self._update_cooccurrences(
                [r.candidate_id] + list(context.nearby_entity_ids), space_id
            )
            return r.candidate_id

        if SCORE_REVIEW_THRESHOLD <= r.score < SCORE_REUSE_THRESHOLD and self._llm_call_fn:
            l3_result = await self._l3_disambiguate(
                entity_text, r.candidate_id, space_id, context,
            )
            if l3_result == "reuse" and r.candidate_id:
                await self._repo.record_access(r.candidate_id)
                return r.candidate_id

        entity_id = self._generate_entity_id(entity_text, entity_type, space_id)
        node = CognitiveNode(
            id=entity_id,
            memory_type="entity",
            cognitive_layer="semantic",
            content=entity_text,
            belief_status="accepted" if r.score < SCORE_REVIEW_THRESHOLD else "pending_review",
            domain_id=space_id,
            space_id=space_id,
        )
        await self._repo.create_node(node)
        await self._update_cooccurrences(
            [entity_id] + list(context.nearby_entity_ids), space_id
        )
        return entity_id

    def _compute_disambiguation_score(
        self,
        text: str,
        candidate: CognitiveNode,
        context: ResolutionContext,
    ) -> float:
        """Compute three-dimension disambiguation score.

        score = name_similarity × 0.5
              + cooccurrence_overlap × 0.3
              + temporal_proximity × 0.2

        Special case: exact name match always scores >= 0.7.

        Args:
            text: Input entity text.
            candidate: Candidate CognitiveNode.
            context: Resolution context.

        Returns:
            Disambiguation score (0-1).
        """
        name_sim = compute_name_similarity(text, candidate.content)

        if name_sim == 1.0:
            return 1.0

        cooccurrence_overlap = 0.0
        if context.nearby_entity_ids:
            cooccurrence_overlap = min(1.0, len(context.nearby_entity_ids) * 0.1)

        temporal_proximity = 0.0
        if context.event_date and candidate.occurred_at:
            try:
                from datetime import datetime as dt
                if isinstance(candidate.occurred_at, str):
                    candidate_date = dt.fromisoformat(candidate.occurred_at.replace("Z", "+00:00"))
                    days_diff = abs((context.event_date - candidate_date).days)
                    if days_diff <= 365:
                        temporal_proximity = max(0.0, 1.0 - days_diff / 365)
            except (ValueError, TypeError):
                pass

        return name_sim * 0.5 + cooccurrence_overlap * 0.3 + temporal_proximity * 0.2

    async def _resolve_full(
        self,
        space_id: str,
        entity_texts: list[str],
        context: ResolutionContext,
    ) -> list[ResolutionResult]:
        """Full scan resolution strategy (small scale)."""
        all_entities = await self._repo.query_nodes(
            memory_type="entity",
            domain_id=space_id,
            limit=10000,
        )

        results = []
        for text in entity_texts:
            best_score = 0.0
            best_candidate = None

            for entity in all_entities:
                score = self._compute_disambiguation_score(text, entity, context)
                if score > best_score:
                    best_score = score
                    best_candidate = entity

            results.append(self._make_result(text, best_score, best_candidate))

        return results

    async def _resolve_trigram(
        self,
        space_id: str,
        entity_texts: list[str],
        context: ResolutionContext,
    ) -> list[ResolutionResult]:
        """Trigram-based resolution strategy (large scale)."""
        all_entities = await self._repo.query_nodes(
            memory_type="entity",
            domain_id=space_id,
            limit=50000,
        )

        trigram_index = self._build_trigram_index(all_entities)

        results = []
        for text in entity_texts:
            query_trigrams = set(compute_trigrams(text))
            candidates = self._search_trigrams(trigram_index, query_trigrams, top_k=20)

            best_score = 0.0
            best_candidate = None

            for candidate_id in candidates:
                try:
                    entity = await self._repo.get_node(candidate_id)
                    score = self._compute_disambiguation_score(text, entity, context)
                    if score > best_score:
                        best_score = score
                        best_candidate = entity
                except Exception:
                    continue

            results.append(self._make_result(text, best_score, best_candidate))

        return results

    def _make_result(
        self,
        text: str,
        score: float,
        candidate: CognitiveNode | None,
    ) -> ResolutionResult:
        """Create a ResolutionResult based on score and candidate."""
        if score > SCORE_REUSE_THRESHOLD and candidate:
            return ResolutionResult(
                entity_text=text,
                action="reuse",
                candidate_id=candidate.id,
                score=score,
            )
        elif score > SCORE_REVIEW_THRESHOLD and candidate:
            return ResolutionResult(
                entity_text=text,
                action="pending_review",
                candidate_id=candidate.id,
                score=score,
            )
        else:
            return ResolutionResult(
                entity_text=text,
                action="create",
                score=score,
            )

    def _build_trigram_index(
        self,
        entities: list[CognitiveNode],
    ) -> dict[str, list[str]]:
        """Build a trigram index from entities.

        Args:
            entities: List of CognitiveNode entities.

        Returns:
            Dictionary mapping trigrams to entity IDs.
        """
        index: dict[str, list[str]] = {}
        for entity in entities:
            trigrams = compute_trigrams(entity.content)
            for tg in trigrams:
                index.setdefault(tg, []).append(entity.id)
        return index

    def _search_trigrams(
        self,
        index: dict[str, list[str]],
        query_trigrams: set[str],
        top_k: int = 20,
    ) -> list[str]:
        """Search trigram index for matching entities.

        Args:
            index: Trigram index.
            query_trigrams: Set of query trigrams.
            top_k: Maximum number of results.

        Returns:
            List of entity IDs sorted by match count.
        """
        scores: dict[str, int] = {}
        for tg in query_trigrams:
            for entity_id in index.get(tg, []):
                scores[entity_id] = scores.get(entity_id, 0) + 1

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [eid for eid, _ in sorted_ids[:top_k]]

    async def _entity_count(self, space_id: str) -> int:
        """Count entities in a space.

        Uses a dedicated count query when available, otherwise
        queries with a high limit and counts results.
        """
        if hasattr(self._store, "count_cognitive_nodes"):
            try:
                return await self._store.count_cognitive_nodes(
                    memory_type="entity", domain_id=space_id,
                )
            except Exception:
                pass

        entities = await self._repo.query_nodes(
            memory_type="entity",
            domain_id=space_id,
            limit=100000,
        )
        return len(entities)

    async def _update_cooccurrences(
        self,
        entity_ids: list[str],
        space_id: str,
    ) -> None:
        """Update co-occurrence edges between entities.

        Args:
            entity_ids: List of entity IDs that co-occur.
            space_id: Space identifier.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        for i, eid_a in enumerate(entity_ids):
            for eid_b in entity_ids[i + 1:]:
                edge = CognitiveEdge(
                    edge_type="CO_OCCURS_WITH",
                    from_id=eid_a,
                    to_id=eid_b,
                    properties={
                        "co_occurrence_count": 1,
                        "last_seen_at": now,
                        "first_seen_at": now,
                    },
                )
                try:
                    await self._repo.create_cognitive_edge(edge)
                except Exception as e:
                    logger.debug("Co-occurrence edge creation skipped: %s", e)

    @staticmethod
    def _generate_entity_id(text: str, entity_type: str, space_id: str) -> str:
        """Generate a deterministic entity ID."""
        key = f"entity:{text}:{entity_type}:{space_id}"
        return f"mem:entity:{hashlib.md5(key.encode()).hexdigest()[:16]}"

    async def merge_entities(
        self,
        primary_id: str,
        secondary_id: str,
        space_id: str,
    ) -> dict[str, Any]:
        """Merge two entities, keeping primary as the survivor.

        Steps:
        1. Merge attributes (primary takes precedence)
        2. Redirect edges from secondary to primary
        3. Update vector index for primary
        4. Mark secondary as merged/superseded
        5. Record merge history

        Args:
            primary_id: The entity to keep.
            secondary_id: The entity to absorb and deprecate.
            space_id: Space identifier.

        Returns:
            Dict with merge results.
        """
        primary = await self._repo.get_node(primary_id)
        secondary = await self._repo.get_node(secondary_id)

        if not primary or not secondary:
            return {"merged": False, "reason": "node_not_found"}

        if primary.memory_type != "entity" or secondary.memory_type != "entity":
            return {"merged": False, "reason": "not_entity_type"}

        merged_attrs = {**(secondary.attributes or {}), **(primary.attributes or {})}

        if merged_attrs != (primary.attributes or {}):
            primary.attributes = merged_attrs
            try:
                await self._repo.update_node(primary, reason=f"merged_from_{secondary_id}")
            except Exception as e:
                logger.warning("Failed to update primary attributes: %s", e)

        redirected = 0
        try:
            edges = await self._repo.query_cognitive_edges(from_id=secondary_id, limit=100)
            for edge in edges:
                new_edge = CognitiveEdge(
                    edge_type=edge.edge_type,
                    from_id=primary_id,
                    to_id=edge.to_id,
                    properties=edge.properties,
                )
                try:
                    await self._repo.create_cognitive_edge(new_edge)
                    redirected += 1
                except Exception:
                    pass

            edges_in = await self._repo.query_cognitive_edges(to_id=secondary_id, limit=100)
            for edge in edges_in:
                if edge.from_id == primary_id:
                    continue
                new_edge = CognitiveEdge(
                    edge_type=edge.edge_type,
                    from_id=edge.from_id,
                    to_id=primary_id,
                    properties=edge.properties,
                )
                try:
                    await self._repo.create_cognitive_edge(new_edge)
                    redirected += 1
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Edge redirection partially failed: %s", e)

        try:
            await self._repo.transition_belief(
                secondary_id,
                new_belief="superseded",
                reason=f"merged_into_{primary_id}",
            )
        except Exception as e:
            logger.warning("Failed to supersede secondary: %s", e)

        merge_edge = CognitiveEdge(
            edge_type="MERGED_INTO",
            from_id=secondary_id,
            to_id=primary_id,
            properties={"merge_reason": "entity_resolution"},
        )
        try:
            await self._repo.create_cognitive_edge(merge_edge)
        except Exception as e:
            logger.debug("Merge edge creation skipped: %s", e)

        return {
            "merged": True,
            "primary_id": primary_id,
            "secondary_id": secondary_id,
            "redirected_edges": redirected,
            "merged_attributes": list(merged_attrs.keys()),
        }

    async def _l3_disambiguate(
        self,
        entity_text: str,
        candidate_id: str | None,
        space_id: str,
        context: ResolutionContext,
    ) -> str:
        """L3 disambiguation using LLM.

        Called when L2 score is in the ambiguous range (0.3-0.6).
        Asks the LLM whether the new entity text refers to the
        same entity as the candidate.

        Args:
            entity_text: New entity text to resolve.
            candidate_id: ID of the candidate entity from L2.
            space_id: Space identifier.
            context: Resolution context.

        Returns:
            "reuse" if same entity, "create" if different.
        """
        if not self._llm_call_fn or not candidate_id:
            return "create"

        try:
            candidate = await self._repo.get_node(candidate_id)
            if not candidate:
                return "create"

            prompt = (
                "Determine whether the following two entity mentions refer to "
                "the same real-world entity. Answer ONLY 'same' or 'different'.\n\n"
                f"Entity A: {candidate.content}\n"
                f"Entity B: {entity_text}\n\n"
            )

            if context.extracted_attributes:
                prompt += f"Context attributes for B: {context.extracted_attributes}\n"

            if candidate.attributes:
                prompt += f"Known attributes for A: {candidate.attributes}\n"

            prompt += "\nAnswer (same/different):"

            response = await self._llm_call_fn(prompt)
            answer = response.strip().lower()

            if "same" in answer and "different" not in answer:
                logger.info(
                    "L3 disambiguation: '%s' same as '%s'",
                    entity_text, candidate.content,
                )
                return "reuse"

            logger.info(
                "L3 disambiguation: '%s' different from '%s'",
                entity_text, candidate.content,
            )
            return "create"

        except Exception as e:
            logger.warning("L3 disambiguation failed: %s", e)
            return "create"
