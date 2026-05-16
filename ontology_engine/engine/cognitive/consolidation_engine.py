"""Consolidation engine.

Converts fragment memories into persistent knowledge (observation/entity/mental_model),
maintains evidence chains and change history.

Design decisions (from consolidation-engine.md):
- D-CON-1: OCC via version field (KuzuDB has no row-level locks)
- D-CON-2: source_fragment_ids as strong-typed field (fast traceability)
- D-CON-3: history inline storage (avoids SUPERSEDES edge traversal)
- D-CON-4: Tags strict grouping isolation (prevents cross-tenant leaks)
- D-CON-5: Adaptive batch halving retry (LLM context window limits)
- D-CON-6: Consolidation vs compilation separation
- D-CON-7: Schema alignment score 0.7 threshold
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.consolidation_types import (
    CONSOLIDATION_THRESHOLD,
    CreateAction,
    ConsolidationResult,
    DeleteAction,
    Fragment,
    UpdateAction,
    UpgradeAction,
)
from ontology_engine.engine.cognitive.models import CognitiveNode, CognitiveEdge, append_history_entry

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA_ALIGNMENT_THRESHOLD = 0.7


def compute_schema_alignment_score(node: CognitiveNode) -> float:
    """Compute how well a node aligns with its target schema.

    Based on memory-lifecycle.md §8.3 / consolidation-engine.md §Schema对齐评分.
    Condensed checks since full schema engine is out of scope:
    - Has source_fragment_ids: +0.3
    - Has evidence chain (history entries): +0.2
    - Content is non-trivial (>20 chars): +0.2
    - Has at least 1 tag: +0.1
    - cognitive_layer matches memory_type expectation: +0.2

    Returns:
        Score between 0.0 and 1.0.
    """
    score = 0.0

    if node.source_fragment_ids:
        score += 0.3
    if node.history:
        score += 0.2
    if node.content and len(node.content) > 20:
        score += 0.2
    if node.content and len(node.content) > 50:
        score += 0.1

    expected_layer = {
        "mental_model": "opinion",
        "entity": "semantic",
        "observation": "semantic",
        "fragment": "perception",
    }.get(node.memory_type, "perception")
    if node.cognitive_layer == expected_layer:
        score += 0.2

    return min(score, 1.0)


def maybe_upgrade_to_entity(node: CognitiveNode) -> str | None:
    """Check if a node should be upgraded to entity type.

    Returns:
        New memory_type if upgrade is needed, None otherwise.
    """
    alignment = compute_schema_alignment_score(node)
    if alignment >= SCHEMA_ALIGNMENT_THRESHOLD and node.memory_type == "observation":
        if len(node.source_fragment_ids) >= 5:
            return "entity"
    if alignment >= SCHEMA_ALIGNMENT_THRESHOLD and node.memory_type == "fragment":
        if len(node.content.split()) > 100:
            return "observation"
    return None


def _generate_uuid5(text: str, tags: dict[str, str | list[str]] | None = None) -> str:
    """Generate a deterministic ID from text and tags using SHA-1."""
    tag_str = json.dumps(tags or {}, sort_keys=True)
    key = f"{text}:{tag_str}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _tags_fingerprint(tags: dict[str, str | list[str]] | None) -> str:
    """Stable string key for tag-based grouping and dedup."""
    if not tags:
        return ""
    return json.dumps(tags, sort_keys=True)


def group_by_tags(fragments: list[Fragment]) -> dict[str, list[Fragment]]:
    """Group fragments by their tags for isolation.

    Different tag groups never share the same LLM call.
    Tags dicts are compared by JSON fingerprint.
    """
    tag_groups: dict[str, list[Fragment]] = {}
    for f in fragments:
        tag_key = _tags_fingerprint(f.tags)
        tag_groups.setdefault(tag_key, []).append(f)
    return tag_groups


class ConsolidationEngine:
    """Engine for consolidating fragment memories into persistent knowledge.

    Implements the three-action model (Create/Update/Delete) with:
    - Tags isolation (D-CON-4)
    - Adaptive batch halving (D-CON-5)
    - Optimistic concurrency control (D-CON-1)
    - Evidence chain maintenance (D-CON-2, D-CON-3)
    """

    def __init__(
        self,
        repository: "CognitiveRepository",
        llm_consolidate_fn: Any | None = None,
    ):
        """Initialize ConsolidationEngine.

        Args:
            repository: CognitiveRepository for node operations.
            llm_consolidate_fn: Async function that takes (fragments, existing_nodes)
                and returns a list of actions. If None, uses rule-based consolidation.
        """
        self._repo = repository
        self._llm_consolidate = llm_consolidate_fn

    async def maybe_trigger_consolidation(
        self,
        space_id: str,
        trigger: str = "write_async",
    ) -> bool:
        """Check if consolidation should be triggered and enqueue if so.

        Args:
            space_id: Space to check.
            trigger: Trigger type (write_async, scheduled, manual, reflect).

        Returns:
            True if a consolidation job was enqueued.
        """
        if trigger == "write_async":
            pending = await self._count_unconsolidated(space_id)
            if pending < CONSOLIDATION_THRESHOLD:
                return False

        logger.info("Triggering consolidation for space=%s trigger=%s", space_id, trigger)
        await self.run_consolidation_job(space_id)
        return True

    async def run_consolidation_job(
        self,
        space_id: str,
        batch_size: int = 50,
    ) -> ConsolidationResult:
        """Run a consolidation job for a space.

        Args:
            space_id: Space to consolidate.
            batch_size: Maximum number of fragments to process.

        Returns:
            ConsolidationResult with created/updated/deleted counts.
        """
        unconsolidated = await self._fetch_unconsolidated_fragments(space_id, batch_size)
        if not unconsolidated:
            return ConsolidationResult()

        tag_groups = group_by_tags(unconsolidated)
        total_result = ConsolidationResult()

        for tag_key, fragments in tag_groups.items():
            try:
                existing = await self._find_related_observations(space_id, tag_key)
                result = await self._consolidate_batch_with_llm(fragments, existing)
                action_result = await self._execute_consolidation_actions(list(result), space_id)
                total_result = total_result.merge(action_result)
            except Exception as e:
                logger.error("Consolidation failed for tags=%s: %s", tag_key, e)
                total_result.errors.append({
                    "tags": tag_key or "(empty)",
                    "error": str(e),
                    "fragment_count": len(fragments),
                })

        if total_result.created or total_result.updated:
            try:
                refresh_result = await self.trigger_mental_model_refresh(space_id)
                logger.info(
                    "Mental model refresh: marked_stale=%d",
                    len(refresh_result.get("marked_stale", [])),
                )
            except Exception as e:
                logger.warning("Mental model refresh after consolidation failed: %s", e)

        return total_result

    async def execute_create(
        self,
        action: CreateAction,
        space_id: str,
    ) -> str:
        """Execute a Create action.

        Args:
            action: CreateAction to execute.
            space_id: Space identifier.

        Returns:
            ID of the created node.
        """
        node_id = f"mem:{action.memory_type}:{_generate_uuid5(action.text, action.tags)}"
        source_ids = [f.id for f in action.source_fragments]

        history_entry = {
            "change_reason": "consolidation",
            "changed_at": _now_iso(),
            "changed_by": "consolidation_engine",
            "new_source_fragment_ids": source_ids,
        }

        node = CognitiveNode(
            id=node_id,
            memory_type=action.memory_type,
            cognitive_layer=action.cognitive_layer,
            content=action.text,
            source_fragment_ids=source_ids,
            history=[history_entry],
            domain_id=space_id,
            space_id=space_id,
            belief_status="accepted",
            consolidated_at=datetime.now(timezone.utc).isoformat(),
            tags=action.tags or {},
            proof_count=len(source_ids),
            confidence=action.confidence or 0.7,
            consolidation_reasoning=f"Consolidated from {len(source_ids)} fragments via {action.memory_type} consolidation",
        )

        await self._repo.create_node(node)

        for frag_id in source_ids:
            edge_type = "CONSOLIDATED_INTO"
            if action.memory_type == "mental_model":
                edge_type = "SUMMARIZED_AS"
            elif action.memory_type == "procedure":
                edge_type = "LEARNED_INTO"
            edge = CognitiveEdge(
                edge_type=edge_type,
                from_id=frag_id,
                to_id=node_id,
            )
            await self._repo.create_cognitive_edge(edge)
            try:
                frag_node = await self._repo.get_node(frag_id)
                frag_node.consolidated_at = _now_iso()
                await self._repo.update_node(frag_node, reason="consolidated")
            except Exception as e:
                logger.debug("Failed to set consolidated_at on %s: %s", frag_id, e)

            cog_edge = CognitiveEdge(
                edge_type="COG_SUPPORTED_BY",
                from_id=frag_id,
                to_id=node_id,
            )
            try:
                await self._repo.create_cognitive_edge(cog_edge)
            except Exception as e:
                logger.debug("COG_SUPPORTED_BY edge creation failed for %s→%s: %s", frag_id, node_id, e)

        logger.info("Created node %s from %d fragments", node_id, len(source_ids))

        upgrade_type = maybe_upgrade_to_entity(node)
        if upgrade_type and upgrade_type == "entity":
            upgrade_action = UpgradeAction(
                target_id=node_id,
                entity_name=action.text[:50],
                entity_type="concept",
                reason="auto_upgrade_after_consolidation",
            )
            await self.execute_upgrade(upgrade_action, space_id)

        return node_id

    async def execute_update(
        self,
        action: UpdateAction,
        space_id: str,
    ) -> str:
        """Execute an Update action.

        Args:
            action: UpdateAction to execute.
            space_id: Space identifier.

        Returns:
            ID of the updated node.
        """
        existing = await self._repo.get_node(action.target_id)

        new_source_ids = [f.id for f in action.new_source_fragments]
        merged_source_ids = list(set(existing.source_fragment_ids + new_source_ids))

        history_entry = {
            "previous_text": existing.content,
            "previous_belief_status": existing.belief_status,
            "changed_at": _now_iso(),
            "change_reason": "consolidation",
            "changed_by": "consolidation_engine",
            "new_source_fragment_ids": new_source_ids,
        }

        append_history_entry(existing, history_entry)

        existing.content = action.updated_text
        existing.source_fragment_ids = merged_source_ids
        existing.proof_count = getattr(existing, "proof_count", 0) + len(new_source_ids)
        existing.consolidation_reasoning = f"Updated with {len(new_source_ids)} new fragments via consolidation"
        if action.confidence:
            existing.confidence = max(existing.confidence, action.confidence)
        if action.updated_tags:
            existing_tags = getattr(existing, "tags", None) or {}
            existing.tags = {**existing_tags, **action.updated_tags}

        await self._repo.update_node(existing, reason="consolidation_update")

        for frag_id in new_source_ids:
            edge = CognitiveEdge(
                edge_type="CONSOLIDATED_INTO",
                from_id=frag_id,
                to_id=action.target_id,
            )
            await self._repo.create_cognitive_edge(edge)
            try:
                frag_node = await self._repo.get_node(frag_id)
                frag_node.consolidated_at = _now_iso()
                await self._repo.update_node(frag_node, reason="consolidated")
            except Exception as e:
                logger.debug("Failed to set consolidated_at on %s: %s", frag_id, e)

        logger.info("Updated node %s with %d new fragments", action.target_id, len(new_source_ids))
        return action.target_id

    async def execute_delete(
        self,
        action: DeleteAction,
        space_id: str,
    ) -> str:
        """Execute a Delete (supersede) action.

        Args:
            action: DeleteAction to execute.
            space_id: Space identifier.

        Returns:
            ID of the superseded node.
        """
        existing = await self._repo.get_node(action.target_id)

        history_entry = {
            "previous_text": existing.content,
            "previous_belief_status": existing.belief_status,
            "changed_at": _now_iso(),
            "change_reason": "consolidation",
            "changed_by": "consolidation_engine",
            "superseded_by": action.replacement_id,
        }

        append_history_entry(existing, history_entry)

        existing.superseded_by = action.replacement_id
        await self._repo.update_node(existing, reason="consolidation_supersede")
        await self._repo.transition_belief(
            action.target_id,
            "superseded",
            reason=action.reason,
        )

        logger.info("Superseded node %s (replacement=%s)", action.target_id, action.replacement_id)
        return action.target_id

    async def execute_upgrade(
        self,
        action: UpgradeAction,
        space_id: str,
    ) -> str:
        """Execute an Upgrade action: observation → entity.

        Args:
            action: UpgradeAction to execute.
            space_id: Space identifier.

        Returns:
            ID of the upgraded node.
        """
        existing = await self._repo.get_node(action.target_id)

        history_entry = {
            "previous_type": existing.memory_type,
            "previous_layer": existing.cognitive_layer,
            "changed_at": _now_iso(),
            "change_reason": action.reason,
            "changed_by": "consolidation_engine",
        }
        append_history_entry(existing, history_entry)

        existing.memory_type = "entity"
        existing.cognitive_layer = "semantic"
        existing.attributes = {
            **(existing.attributes or {}),
            "entity_name": action.entity_name or existing.content[:50],
            "entity_type": action.entity_type,
            **action.attributes,
        }

        await self._repo.update_node(existing, reason="consolidation_upgrade")

        logger.info(
            "Upgraded node %s from observation to entity (name=%s)",
            action.target_id,
            action.entity_name,
        )
        return action.target_id

    async def _consolidate_batch_with_llm(
        self,
        fragments: list[Fragment],
        existing: list[CognitiveNode],
        max_retries: int = 3,
    ) -> list[CreateAction | UpdateAction | DeleteAction]:
        """Consolidate a batch of fragments using LLM or rule-based fallback.

        Implements adaptive batch halving (D-CON-5).
        """
        if self._llm_consolidate is not None:
            batch = fragments
            for attempt in range(max_retries):
                try:
                    return await self._llm_consolidate(batch, existing)
                except Exception as e:
                    if len(batch) <= 1:
                        raise
                    logger.warning(
                        "LLM consolidation failed (attempt %d/%d), halving batch: %s",
                        attempt + 1, max_retries, e,
                    )
                    mid = len(batch) // 2
                    left = await self._consolidate_batch_with_llm(batch[:mid], existing, max_retries - 1)
                    right = await self._consolidate_batch_with_llm(batch[mid:], existing, max_retries - 1)
                    return left + right

        return self._rule_based_consolidation(fragments, existing)

    def _rule_based_consolidation(
        self,
        fragments: list[Fragment],
        existing: list[CognitiveNode],
    ) -> list[CreateAction | UpdateAction | DeleteAction]:
        """Rule-based consolidation fallback when no LLM is available.

        Simple strategy: create one observation per fragment group.
        """
        actions: list[CreateAction | UpdateAction | DeleteAction] = []

        if not fragments:
            return actions

        combined_text = " ".join(f.content for f in fragments)
        combined_tags: dict[str, str | list[str]] = {}
        for f in fragments:
            if f.tags:
                combined_tags.update(f.tags)

        if existing:
            for node in existing:
                actions.append(UpdateAction(
                    target_id=node.id,
                    updated_text=f"{node.content} {combined_text}".strip(),
                    updated_tags={**(node.to_dict().get("tags", {}) or {}), **combined_tags},
                    new_source_fragments=fragments,
                    confidence=0.6,
                ))
        else:
            actions.append(CreateAction(
                text=combined_text,
                memory_type="observation",
                cognitive_layer="semantic",
                tags=combined_tags,
                source_fragments=fragments,
                confidence=0.5,
            ))

        return actions

    async def _execute_consolidation_actions(
        self,
        actions: list[CreateAction | UpdateAction | DeleteAction | UpgradeAction],
        space_id: str,
    ) -> ConsolidationResult:
        """Execute a list of consolidation actions."""
        result = ConsolidationResult()

        for action in actions:
            try:
                if isinstance(action, CreateAction):
                    node_id = await self.execute_create(action, space_id)
                    result.created.append(node_id)
                elif isinstance(action, UpdateAction):
                    node_id = await self.execute_update(action, space_id)
                    result.updated.append(node_id)
                elif isinstance(action, DeleteAction):
                    node_id = await self.execute_delete(action, space_id)
                    result.deleted.append(node_id)
                elif isinstance(action, UpgradeAction):
                    node_id = await self.execute_upgrade(action, space_id)
                    result.upgraded.append(node_id)
            except Exception as e:
                logger.error("Failed to execute action %s: %s", type(action).__name__, e)
                result.errors.append({
                    "action_type": type(action).__name__,
                    "error": str(e),
                })

        return result

    async def _count_unconsolidated(self, space_id: str) -> int:
        """Count unconsolidated fragments in a space."""
        nodes = await self._repo.query_nodes(
            memory_type="fragment",
            domain_id=space_id,
            limit=1000,
        )
        return len([n for n in nodes if n.consolidated_at is None])

    async def _fetch_unconsolidated_fragments(
        self,
        space_id: str,
        batch_size: int,
    ) -> list[Fragment]:
        """Fetch unconsolidated fragments and mark them as consolidating (OCC)."""
        nodes = await self._repo.query_nodes(
            memory_type="fragment",
            domain_id=space_id,
            limit=batch_size,
        )
        fragments: list[Fragment] = []
        for n in nodes:
            if n.consolidated_at is not None:
                continue
            if getattr(n, "extraction_hint", None) == "consolidating":
                continue
            try:
                n.extraction_hint = "consolidating"
                await self._repo.update_node(n, reason="occ_lock")
                fragments.append(Fragment(
                    id=n.id,
                    content=n.content,
                    space_id=n.space_id,
                    created_at=n.created_at,
                    tags=getattr(n, "tags", None) or {},
                ))
            except Exception as e:
                logger.debug("OCC lock failed for %s: %s", n.id, e)
        return fragments

    async def _find_related_observations(
        self,
        space_id: str,
        tag_fingerprint: str,
    ) -> list[CognitiveNode]:
        """Find existing observations related to the given tag fingerprint (D-CON-4).

        Matches by checking if the fragment's tag fingerprint equals the node's tag fingerprint.
        """
        nodes = await self._repo.query_nodes(
            memory_type="observation",
            domain_id=space_id,
            limit=200,
        )
        if not tag_fingerprint:
            return nodes
        return [n for n in nodes if _tags_fingerprint(n.tags) == tag_fingerprint]

    async def trigger_mental_model_refresh(self, space_id: str) -> dict[str, Any]:
        """Check for stale mental models and mark them for review.

        A mental model is stale when its supporting entities have been
        updated more recently than the model itself. Marks stale models
        with belief_status="pending_review".

        Args:
            space_id: Space to check.

        Returns:
            Dict with marked_stale, updated, already_fresh counts.
        """
        models = await self._repo.query_nodes(
            memory_type="mental_model",
            domain_id=space_id,
            limit=100,
        )

        marked_stale: list[str] = []
        updated: list[str] = []
        already_fresh = 0

        for model in models:
            is_stale = False
            try:
                model_updated = model.updated_at
                if model_updated:
                    model_dt = datetime.fromisoformat(model_updated.replace("Z", "+00:00"))
                else:
                    model_dt = datetime.min.replace(tzinfo=timezone.utc)

                if model.source_fragment_ids:
                    for frag_id in model.source_fragment_ids[:20]:
                        try:
                            frag_node = await self._repo.get_node(frag_id)
                        except Exception:
                            continue
                        frag_updated = frag_node.updated_at
                        if frag_updated:
                            try:
                                frag_dt = datetime.fromisoformat(
                                    frag_updated.replace("Z", "+00:00")
                                )
                                if frag_dt > model_dt:
                                    is_stale = True
                                    break
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                logger.debug("Error checking staleness of %s: %s", model.id, e)

            if is_stale:
                try:
                    await self._repo.transition_belief(
                        model.id,
                        "pending_review",
                        reason="supporting_entity_updated",
                    )
                    marked_stale.append(model.id)
                except Exception as e:
                    logger.warning(
                        "Failed to mark mental model %s as stale: %s", model.id, e
                    )
            else:
                already_fresh += 1

        return {
            "marked_stale": marked_stale,
            "updated": updated,
            "already_fresh": already_fresh,
        }

    async def trigger_mental_model_refreshes(
        self,
        space_id: str,
        consolidated_tags: dict[str, str | list[str]] | None = None,
    ) -> dict[str, Any]:
        """Bulk refresh of mental models, optionally filtered by tags.

        Args:
            space_id: Space to refresh.
            consolidated_tags: Optional tag filter for targeted refresh.

        Returns:
            Same as trigger_mental_model_refresh.
        """
        if consolidated_tags is None:
            return await self.trigger_mental_model_refresh(space_id)

        models = await self._repo.query_nodes(
            memory_type="mental_model",
            domain_id=space_id,
            limit=100,
        )

        marked_stale: list[str] = []
        already_fresh = 0
        tag_fp = _tags_fingerprint(consolidated_tags)

        for model in models:
            model_fp = _tags_fingerprint(getattr(model, "tags", None))
            if model_fp != tag_fp:
                already_fresh += 1
                continue

            try:
                await self._repo.transition_belief(
                    model.id,
                    "pending_review",
                    reason="tag_related_consolidation",
                )
                marked_stale.append(model.id)
            except Exception as e:
                logger.warning(
                    "Failed to mark mental model %s as stale: %s", model.id, e
                )

        return {
            "marked_stale": marked_stale,
            "updated": [],
            "already_fresh": already_fresh,
        }
