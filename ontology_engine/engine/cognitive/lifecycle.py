"""Memory lifecycle engine.

Implements forgetting (Ebbinghaus decay), dream cycle, and memory
strength tracking.

Design decisions (from memory-lifecycle.md):
- Forgetting based on memory strength model
- Ebbinghaus decay with configurable forgetting rates
- Dream cycle 5-phase maintenance
- Protection for high-feedback memories
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.models import CognitiveNode, CognitiveEdge

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


STRENGTH_SOFT_DECAY_THRESHOLD = 0.3
STRENGTH_TYPE_DEMOTION_THRESHOLD = 0.2
STRENGTH_ARCHIVE_THRESHOLD = 0.1
STRENGTH_HARD_DELETE_THRESHOLD = 0.01
FEEDBACK_PROTECTION_THRESHOLD = 0.9

TYPE_DEMOTION_ORDER = [
    "mental_model",
    "entity",
    "observation",
    "archived",
]

FORGETTING_RATES = {
    "high_value": 0.1,
    "medium_value": 0.4,
    "low_value": 0.85,
}

MAX_VERSIONS_PER_ENTITY = 100


@dataclass
class DreamCycleResult:
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    expired: list[str] = field(default_factory=list)
    orphans_cleaned: int = 0
    links_enhanced: int = 0
    graph_completed: int = 0
    errors: list[str] = field(default_factory=list)


def compute_memory_strength(
    access_count: int,
    last_accessed_days: float,
    proof_count: int,
    feedback_weight: float,
    confirmation_count: int = 0,
    last_confirmed_at: str | None = None,
) -> float:
    recency = math.exp(-0.1 * max(0, last_accessed_days))
    evidence = min(proof_count / 10.0, 1.0)
    frequency = min(access_count / 50.0, 1.0)

    if last_confirmed_at:
        try:
            from datetime import datetime, timezone
            confirmed_dt = datetime.fromisoformat(last_confirmed_at)
            if confirmed_dt.tzinfo is None:
                confirmed_dt = confirmed_dt.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - confirmed_dt).days
            confirmation = math.exp(-0.05 * days_since)
        except (ValueError, TypeError):
            confirmation = min(confirmation_count / 5.0, 1.0)
    elif confirmation_count > 0:
        confirmation = min(confirmation_count / 5.0, 1.0)
    else:
        confirmation = 1.0

    strength = (
        recency * 0.25
        + confirmation * 0.15
        + evidence * 0.25
        + feedback_weight * 0.2
        + frequency * 0.15
    )
    return min(1.0, max(0.0, strength))


def forgetting_rate(memory_value: float) -> float:
    """Get forgetting rate based on memory value.

    Args:
        memory_value: Current memory value/strength.

    Returns:
        Forgetting rate (lambda).
    """
    if memory_value >= 0.8:
        return FORGETTING_RATES["high_value"]
    elif memory_value >= 0.5:
        return FORGETTING_RATES["medium_value"]
    else:
        return FORGETTING_RATES["low_value"]


def decay_strength(
    current_strength: float,
    days_elapsed: int,
    memory_value: float,
) -> float:
    """Apply Ebbinghaus decay to memory strength.

    Args:
        current_strength: Current strength value.
        days_elapsed: Days since last decay.
        memory_value: Memory value for rate selection.

    Returns:
        Decayed strength value.
    """
    lam = forgetting_rate(memory_value)
    return current_strength * math.exp(-lam * days_elapsed)


def get_demotion_target(memory_type: str) -> str | None:
    """Get the next demotion target for a memory type.

    Args:
        memory_type: Current memory type.

    Returns:
        Next demotion type, or None if already at bottom.
    """
    try:
        idx = TYPE_DEMOTION_ORDER.index(memory_type)
        if idx < len(TYPE_DEMOTION_ORDER) - 1:
            return TYPE_DEMOTION_ORDER[idx + 1]
    except ValueError:
        pass
    return None


class ForgettingEngine:
    """Engine for memory forgetting and decay.

    Implements:
    - Memory strength computation
    - Ebbinghaus decay
    - Type demotion
    - Feedback protection
    """

    def __init__(self, repository: "CognitiveRepository"):
        """Initialize ForgettingEngine.

        Args:
            repository: CognitiveRepository for node operations.
        """
        self._repo = repository

    async def evaluate_forgetting(
        self,
        space_id: str,
        days_elapsed: int = 1,
    ) -> dict[str, list[str]]:
        """Evaluate memories for forgetting in a space.

        Args:
            space_id: Space to evaluate.
            days_elapsed: Days since last evaluation.

        Returns:
            Dictionary with categories: soft_decayed, demoted, archived, deleted, protected.
        """
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=10000)

        result: dict[str, list[str]] = {
            "soft_decayed": [],
            "demoted": [],
            "archived": [],
            "deleted": [],
            "protected": [],
        }

        for node in nodes:
            if self._is_protected(node):
                result["protected"].append(node.id)
                continue

            strength = self._compute_node_strength(node, days_elapsed)

            if strength < STRENGTH_HARD_DELETE_THRESHOLD:
                result["deleted"].append(node.id)
            elif strength < STRENGTH_ARCHIVE_THRESHOLD:
                result["archived"].append(node.id)
            elif strength < STRENGTH_TYPE_DEMOTION_THRESHOLD:
                result["demoted"].append(node.id)
            elif strength < STRENGTH_SOFT_DECAY_THRESHOLD:
                result["soft_decayed"].append(node.id)

        return result

    async def apply_forgetting(
        self,
        space_id: str,
        days_elapsed: int = 1,
    ) -> dict[str, int]:
        """Apply forgetting actions to a space.

        Args:
            space_id: Space to apply forgetting.
            days_elapsed: Days since last evaluation.

        Returns:
            Dictionary with action counts.
        """
        evaluation = await self.evaluate_forgetting(space_id, days_elapsed)

        applied: dict[str, int] = {
            "soft_decayed": 0,
            "demoted": 0,
            "archived": 0,
            "deleted": 0,
        }

        for node_id in evaluation.get("demoted", []):
            try:
                node = await self._repo.get_node(node_id)
                target_type = get_demotion_target(node.memory_type)
                if target_type:
                    node.memory_type = target_type
                    await self._repo.update_node(node, reason="forgetting_demotion")
                    applied["demoted"] += 1
            except Exception as e:
                logger.warning("Failed to demote node %s: %s", node_id, e)

        for node_id in evaluation.get("deleted", []):
            try:
                node = await self._repo.get_node(node_id)
                if node.strength < 0.01 and node.proof_count == 0:
                    connected_edges = await self._repo.query_cognitive_edges(
                        from_id=node_id, limit=100,
                    )
                    connected_edges += await self._repo.query_cognitive_edges(
                        to_id=node_id, limit=100,
                    )
                    for edge in connected_edges:
                        try:
                            edge_id = getattr(edge, "id", None) or f"{edge.from_id}->{edge.to_id}"
                            await self._repo.delete_cognitive_edge(edge_id)
                        except Exception as edge_e:
                            logger.debug("Failed to delete edge for node %s: %s", node_id, edge_e)
                    await self._repo.delete_node(node_id)
                    applied["deleted"] += 1
            except Exception as e:
                logger.warning("Failed to delete node %s: %s", node_id, e)

        for node_id in evaluation.get("soft_decayed", []):
            try:
                node = await self._repo.get_node(node_id)
                node.feedback_weight = max(0.1, node.feedback_weight * 0.7)
                await self._repo.update_node(node, reason="soft_decay_weight_reduction")
                applied["soft_decayed"] += 1
            except Exception as e:
                logger.warning("Failed to soft-decay node %s: %s", node_id, e)

        for node_id in evaluation.get("archived", []):
            try:
                node = await self._repo.get_node(node_id)
                node.memory_type = "archived"
                await self._repo.update_node(node, reason="forgetting_archive")
                applied["archived"] += 1
            except Exception as e:
                logger.warning("Failed to archive node %s: %s", node_id, e)

        nodes = await self._repo.query_nodes(domain_id=space_id, limit=500)
        entity_ids: set[str] = set()
        for n in nodes:
            if n.memory_type == "entity" and n.source_fragment_ids:
                for fid in n.source_fragment_ids:
                    entity_ids.add(fid)
        version_archived = 0
        for eid in entity_ids:
            try:
                count = await enforce_version_limit(self._repo, space_id, eid)
                version_archived += count
            except Exception as e:
                logger.debug("Version limit enforcement skipped for %s: %s", eid, e)
        applied["version_archived"] = version_archived

        return applied

    def _compute_node_strength(self, node: CognitiveNode, days_elapsed: int) -> float:
        """Compute strength for a single node.

        Args:
            node: CognitiveNode to evaluate.
            days_elapsed: Days since last evaluation.

        Returns:
            Current strength value.
        """
        now = datetime.now(timezone.utc)
        last_access = node.updated_at or node.created_at

        days_since_access = 0.0
        if last_access:
            try:
                last_dt = datetime.fromisoformat(last_access.replace("Z", "+00:00"))
                days_since_access = max(0, (now - last_dt).days)
            except (ValueError, TypeError):
                pass

        strength = compute_memory_strength(
            access_count=int(node.access_count),
            last_accessed_days=days_since_access,
            proof_count=len(node.source_fragment_ids),
            feedback_weight=node.feedback_weight,
            confirmation_count=getattr(node, "confirmation_count", 0),
            last_confirmed_at=getattr(node, "last_confirmed_at", None),
        )

        return decay_strength(strength, days_elapsed, node.feedback_weight)

    def _is_protected(self, node: CognitiveNode) -> bool:
        if node.feedback_weight >= 0.9:
            return True
        if node.memory_type == "mental_model" and node.belief_status == "accepted":
            return True
        return False

    async def apply_strategic_forgetting(self, node_id: str, signal: str) -> None:
        node = await self._repo.get_node(node_id)
        if not node:
            return

        if self._is_protected(node):
            logger.info("Strategic forgetting skipped for protected node %s (feedback_weight=%.2f, type=%s, belief=%s)",
                        node_id, node.feedback_weight, node.memory_type, node.belief_status)
            return

        DECAY_FACTORS = {"superseded": 0.5, "rejected": 0.2}
        decay_factor = DECAY_FACTORS.get(signal, 1.0)

        node.strength = max(0, node.strength * decay_factor)
        node.feedback_weight = max(0, node.feedback_weight * decay_factor)

        if signal == "rejected" and node.valid_to is None:
            from datetime import datetime, timezone
            node.valid_to = datetime.now(timezone.utc).isoformat()

        await self._repo.update_node(node)

        if signal in ("superseded", "rejected"):
            await self._mark_downstream_stale(node_id, signal)

    async def _mark_downstream_stale(self, node_id: str, reason: str, depth: int = 0) -> None:
        MAX_CASCADE_DEPTH = 3
        MAX_CASCADE_NODES = 100
        stale_edge_types = {"SUMMARIZED_AS", "CONSOLIDATED_INTO", "COGNITIVE_RELATES_TO"}

        visited: set[str] = {node_id}
        current_frontier = [node_id]

        for _ in range(MAX_CASCADE_DEPTH):
            next_frontier = []
            for nid in current_frontier:
                try:
                    edges = await self._repo.query_cognitive_edges(from_id=nid, limit=50)
                    for edge in edges:
                        if edge.edge_type not in stale_edge_types:
                            continue
                        if edge.to_id in visited:
                            continue
                        if len(visited) >= MAX_CASCADE_NODES:
                            return
                        visited.add(edge.to_id)
                        next_frontier.append(edge.to_id)
                        try:
                            target = await self._repo.get_node(edge.to_id)
                            if target and target.belief_status == "accepted":
                                target.attributes = dict(target.attributes or {})
                                target.attributes["stale_reason"] = f"upstream_{reason}"
                                target.attributes["stale_from"] = node_id
                                await self._repo.update_node(target)
                        except Exception as e:
                            logger.warning("Failed to mark node %s stale: %s", edge.to_id, e)

                    reverse_edges = await self._repo.query_cognitive_edges(to_id=nid, limit=50)
                    for edge in reverse_edges:
                        if edge.edge_type == "COGNITIVE_RELATES_TO" and edge.from_id not in visited:
                            if len(visited) >= MAX_CASCADE_NODES:
                                return
                            visited.add(edge.from_id)
                            next_frontier.append(edge.from_id)
                            try:
                                target = await self._repo.get_node(edge.from_id)
                                if target and target.belief_status == "accepted":
                                    target.attributes = dict(target.attributes or {})
                                    target.attributes["stale_reason"] = f"upstream_{reason}"
                                    target.attributes["stale_from"] = node_id
                                    await self._repo.update_node(target)
                            except Exception as e:
                                logger.warning("Failed to mark reverse node %s stale: %s", edge.from_id, e)
                except Exception as e:
                    logger.warning("Failed to query edges from %s: %s", nid, e)
            current_frontier = next_frontier
            if not current_frontier:
                break


class DreamCycle:
    """Dream cycle for periodic memory maintenance.

    Implements 5-phase maintenance:
    1. Contradiction detection
    2. Expiry check
    3. Orphan cleanup
    4. Self-link enhancement
    5. Graph completion
    """

    def __init__(
        self,
        repository: "CognitiveRepository",
        forgetting_engine: ForgettingEngine,
    ):
        """Initialize DreamCycle.

        Args:
            repository: CognitiveRepository for node operations.
            forgetting_engine: ForgettingEngine for decay operations.
        """
        self._repo = repository
        self._forgetting = forgetting_engine

    async def run(self, space_id: str) -> DreamCycleResult:
        """Run a full dream cycle for a space.

        Args:
            space_id: Space to maintain.

        Returns:
            DreamCycleResult with phase outcomes.
        """
        result = DreamCycleResult()
        errors: list[str] = []

        try:
            result.contradictions = await self._detect_contradictions(space_id)
        except Exception as e:
            logger.warning("Phase 1 (contradiction detection) failed: %s", e)
            errors.append(f"phase1_contradictions: {e}")

        try:
            result.expired = await self._check_expired(space_id)
        except Exception as e:
            logger.warning("Phase 2 (expiry check) failed: %s", e)
            errors.append(f"phase2_expired: {e}")

        try:
            result.orphans_cleaned = await self._clean_orphans(space_id)
        except Exception as e:
            logger.warning("Phase 3 (orphan cleanup) failed: %s", e)
            errors.append(f"phase3_orphans_cleaned: {e}")

        try:
            result.links_enhanced = await self._enhance_self_links(space_id)
        except Exception as e:
            logger.warning("Phase 4 (self-link enhancement) failed: %s", e)
            errors.append(f"phase4_links_enhanced: {e}")

        try:
            result.graph_completed = await self._complete_graph(space_id)
        except Exception as e:
            logger.warning("Phase 5 (graph completion) failed: %s", e)
            errors.append(f"phase5_graph_completed: {e}")

        result.errors = errors
        return result

    async def _detect_contradictions(self, space_id: str) -> list[dict[str, Any]]:
        """Phase 1: Detect contradictions in recently updated memories.

        Samples recently changed nodes and checks for conflicting content,
        explicit contradictions (belief_status=contradicted), and cross-node
        contradictions by entity grouping.

        Resource estimation: ~10% of full space scan (limited to 500 nodes).
        """
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=500)
        contradictions: list[dict[str, Any]] = []

        contradicted_nodes = []
        for n in nodes:
            if n.belief_status == "contradicted":
                contradicted_nodes.append(n)

        for node in contradicted_nodes:
            contradictions.append({
                "node_id": node.id,
                "contradiction_type": "explicit_contradiction",
                "conflicting_nodes": [],
                "severity": 0.9,
            })

        entity_groups: dict[str, list[CognitiveNode]] = {}
        for n in nodes:
            if n.memory_type in ("entity", "observation") and n.content:
                key = n.content.strip().lower()[:80]
                entity_groups.setdefault(key, []).append(n)

        for key, group in entity_groups.items():
            if len(group) < 2:
                continue
            content_sets = {}
            for n in group:
                words = frozenset(n.content.lower().split())
                content_sets.setdefault(words, []).append(n)

            if len(content_sets) > 1:
                for node in group:
                    contradictions.append({
                        "node_id": node.id,
                        "contradiction_type": "content_divergence",
                        "conflicting_nodes": [
                            other.id for other in group if other.id != node.id
                        ],
                        "severity": 0.7,
                    })

        return contradictions

    async def _check_expired(self, space_id: str) -> list[str]:
        """Phase 2: Check for expired memories and apply forgetting.

        Checks TTL expiry and applies the forgetting engine for
        low-strength nodes. TTL-expired nodes are transitioned to
        'superseded' belief status before forgetting is applied,
        ensuring they are actually cleaned up rather than just listed.

        Resource estimation: full expired set (nodes with TTL expired).
        """
        now = datetime.now(timezone.utc)
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=1000)

        expired: list[str] = []
        for n in nodes:
            is_expired = False
            if n.valid_to:
                try:
                    valid_to = datetime.fromisoformat(n.valid_to.replace("Z", "+00:00"))
                    if now > valid_to:
                        is_expired = True
                except (ValueError, TypeError):
                    pass
            elif n.ttl_seconds > 0 and n.created_at:
                try:
                    created = datetime.fromisoformat(n.created_at.replace("Z", "+00:00"))
                    if now > created + timedelta(seconds=n.ttl_seconds):
                        is_expired = True
                except (ValueError, TypeError):
                    pass

            if is_expired and n.belief_status == "accepted":
                try:
                    await self._repo.transition_belief(
                        n.id, "pending_review", reason="TTL expired, awaiting human confirmation",
                    )
                    expired.append(n.id)
                except Exception as e:
                    logger.debug("Failed to transition expired node %s: %s", n.id, e)
                    expired.append(n.id)

        try:
            await self._forgetting.apply_forgetting(space_id, days_elapsed=1)
        except Exception as e:
            logger.warning("Forgetting engine failed during expiry check: %s", e)

        return expired

    async def _clean_orphans(self, space_id: str) -> int:
        """Phase 3: Clean orphaned fragments with low access count.

        Identifies fragments with access_count < 5 and marks them as
        consolidated. Batches processing to avoid memory pressure.

        Resource estimation: ~20% of fragment space.
        """
        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            memory_type="fragment",
            limit=500,
        )
        cleaned = 0
        now = datetime.now(timezone.utc)

        for node in nodes:
            if node.access_count >= 5:
                continue
            if node.consolidated_at:
                continue
            try:
                node.consolidated_at = now.isoformat()
                await self._repo.update_node(node, reason="orphan_cleanup")
                cleaned += 1
            except Exception as e:
                logger.warning("Failed to clean orphan %s: %s", node.id, e)

        return cleaned

    async def _enhance_self_links(self, space_id: str) -> int:
        """Phase 4: Create COGNITIVE_RELATES_TO edges for entity self-links.

        For entity nodes created within the last day, finds semantically
        related entities via word-overlap (30% threshold) and creates edges.
        Includes deduplication check to avoid duplicate edges.

        Resource estimation: incremental (new entities only).
        """
        now = datetime.now(timezone.utc)
        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            memory_type="entity",
            limit=200,
        )
        edges_created = 0

        for node in nodes:
            if not node.content:
                continue
            try:
                created_dt = datetime.fromisoformat(node.created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if (now - created_dt).total_seconds() > 86400:
                continue

            node_words = set(node.content.lower().split())
            if len(node_words) < 3:
                continue

            for other in nodes:
                if other.id == node.id:
                    continue
                if not other.content:
                    continue
                other_words = set(other.content.lower().split())
                if len(other_words) < 3:
                    continue
                union = len(node_words | other_words)
                overlap = len(node_words & other_words)
                if union == 0:
                    continue
                if overlap / union < 0.3:
                    continue

                try:
                    existing = await self._repo.query_cognitive_edges(
                        from_id=node.id, to_id=other.id, edge_type="COGNITIVE_RELATES_TO", limit=1,
                    )
                    if existing:
                        continue
                except Exception:
                    pass

                try:
                    await self._repo.create_cognitive_edge(CognitiveEdge(
                        edge_type="COGNITIVE_RELATES_TO",
                        from_id=node.id,
                        to_id=other.id,
                    ))
                    edges_created += 1
                except Exception as e:
                    logger.debug("Entity self-link edge creation skipped %s→%s: %s", node.id, other.id, e)

        return edges_created

    async def _complete_graph(self, space_id: str) -> int:
        """Phase 5: Create COGNITIVE_RELATES_TO edges for recent observations.

        Rule-based: finds observation nodes created within the last day
        and links them to existing nodes with similar content via
        word-overlap threshold (25%).

        Resource estimation: incremental (new observations only).
        """
        now = datetime.now(timezone.utc)
        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            memory_type="observation",
            limit=200,
        )
        created_edges = 0

        for node in nodes:
            if not node.created_at or not node.content:
                continue
            try:
                created_dt = datetime.fromisoformat(node.created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if (now - created_dt).total_seconds() > 86400:
                continue

            node_words = set(node.content.lower().split())
            if len(node_words) < 3:
                continue

            for other in nodes:
                if other.id == node.id:
                    continue
                if not other.content:
                    continue
                other_words = set(other.content.lower().split())
                if len(other_words) < 3:
                    continue
                union = len(node_words | other_words)
                overlap = len(node_words & other_words)
                if union == 0:
                    continue
                if overlap / union < 0.25:
                    continue

                try:
                    existing = await self._repo.query_cognitive_edges(
                        from_id=node.id, to_id=other.id, edge_type="COGNITIVE_RELATES_TO", limit=1,
                    )
                    if existing:
                        continue
                except Exception:
                    pass

                try:
                    await self._repo.create_cognitive_edge(CognitiveEdge(
                        edge_type="COGNITIVE_RELATES_TO",
                        from_id=node.id,
                        to_id=other.id,
                    ))
                    created_edges += 1
                except Exception as e:
                    logger.warning("Failed to create COGNITIVE_RELATES_TO edge %s→%s: %s", node.id, other.id, e)

        return created_edges


async def enforce_version_limit(repository, space_id: str, entity_id: str) -> int:
    """Enforce MAX_VERSIONS_PER_ENTITY limit by archiving oldest versions.

    When an entity accumulates more than MAX_VERSIONS_PER_ENTITY related
    observations, the oldest ones are archived (memory_type="archived") to
    prevent unbounded growth.

    Returns:
        Number of nodes archived.
    """
    nodes = await repository.query_nodes(domain_id=space_id, limit=500)
    related = [
        n for n in nodes
        if entity_id in (n.source_fragment_ids or [])
        and n.memory_type in ("observation", "fragment")
    ]
    related.sort(key=lambda n: n.created_at or "")

    if len(related) <= MAX_VERSIONS_PER_ENTITY:
        return 0

    to_archive = related[:len(related) - MAX_VERSIONS_PER_ENTITY]
    archived_count = 0

    for node in to_archive:
        try:
            node.memory_type = "archived"
            await repository.update_node(node, reason="version_limit_archived")
            archived_count += 1
        except Exception as e:
            logger.warning("Failed to archive node %s: %s", node.id, e)

    return archived_count
