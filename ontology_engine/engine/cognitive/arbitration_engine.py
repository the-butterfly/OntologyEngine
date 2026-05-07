"""ArbitrationEngine — evidence-weighted automatic arbitration of contradictions.

When ReflectAgent detects contradictions, this engine automatically
arbitrates based on evidence strength, source trust, and recency,
rather than requiring manual review for every conflict.

Design reference: docs/02-design/agent-memory/memory-lifecycle.md §3.2
                 docs/02-design/agent-memory/memory-api.md §4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

SOURCE_TRUST_TIERS: dict[str, float] = {
    "user_declared": 1.0,
    "court_judgment": 1.0,
    "regulatory_document": 0.95,
    "official_document": 0.9,
    "verified_source": 0.85,
    "expert_input": 0.8,
    "behavior_inferred": 0.6,
    "user_observation": 0.7,
    "environment_observed": 0.65,
    "agent_generated": 0.5,
    "inferred": 0.5,
    "unverified": 0.3,
    "unknown": 0.5,
}


@dataclass
class ArbitrationResult:
    winner_id: str | None = None
    loser_id: str | None = None
    winner_score: float = 0.0
    loser_score: float = 0.0
    action: str = "auto_supersede"
    reason: str = ""
    confidence: float = 0.0
    needs_manual_review: bool = False


class ArbitrationEngine:
    """Evidence-weighted automatic arbitration of contradictions.

    Scoring formula:
        score = proof_count × source_trust_tier × recency_factor

    Where:
    - proof_count: number of supporting evidence fragments
    - source_trust_tier: trust level of the source (0.3-1.0)
    - recency_factor: exponential decay from creation time

    If the score difference between winner and loser is below
    the uncertainty threshold, the case is flagged for manual review.
    """

    DEFAULT_UNCERTAINTY_THRESHOLD = 0.3
    DEFAULT_RECENCY_HALF_LIFE_DAYS = 90.0

    def __init__(
        self,
        repository: Any,
        uncertainty_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD,
        recency_half_life_days: float = DEFAULT_RECENCY_HALF_LIFE_DAYS,
    ):
        self._repo = repository
        self._uncertainty_threshold = uncertainty_threshold
        self._recency_half_life_days = recency_half_life_days

    async def arbitrate(
        self,
        node_ids: list[str],
        contradiction_type: str = "",
    ) -> ArbitrationResult:
        """Arbitrate between conflicting nodes.

        Args:
            node_ids: IDs of the conflicting nodes.
            contradiction_type: Type of contradiction for context.

        Returns:
            ArbitrationResult with winner/loser and action recommendation.
        """
        if len(node_ids) < 2:
            return ArbitrationResult(
                reason="insufficient_nodes",
                needs_manual_review=True,
            )

        scored_nodes = []
        for node_id in node_ids:
            try:
                node = await self._repo.get_node(node_id)
                if not node:
                    continue
                score = self._compute_arbitration_score(node)
                scored_nodes.append((node_id, score, node))
            except Exception as e:
                logger.warning("Failed to score node %s: %s", node_id, e)

        if len(scored_nodes) < 2:
            return ArbitrationResult(
                reason="insufficient_scored_nodes",
                needs_manual_review=True,
            )

        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        winner_id, winner_score, winner_node = scored_nodes[0]
        loser_id, loser_score, loser_node = scored_nodes[1]

        score_diff = winner_score - loser_score

        if score_diff < self._uncertainty_threshold:
            return ArbitrationResult(
                winner_id=winner_id,
                loser_id=loser_id,
                winner_score=winner_score,
                loser_score=loser_score,
                action="manual_review",
                reason=f"score_diff={score_diff:.3f} < threshold={self._uncertainty_threshold:.3f}",
                confidence=score_diff,
                needs_manual_review=True,
            )

        action = "auto_supersede"
        if loser_node.belief_status == "accepted" and loser_score > 0.5:
            action = "auto_downgrade"

        return ArbitrationResult(
            winner_id=winner_id,
            loser_id=loser_id,
            winner_score=winner_score,
            loser_score=loser_score,
            action=action,
            reason=f"winner_score={winner_score:.3f} > loser_score={loser_score:.3f} (diff={score_diff:.3f})",
            confidence=score_diff,
            needs_manual_review=False,
        )

    async def apply_arbitration(self, result: ArbitrationResult) -> dict[str, Any]:
        """Apply an arbitration result by updating belief statuses.

        Args:
            result: The arbitration result to apply.

        Returns:
            Dict with applied changes.
        """
        if result.needs_manual_review or not result.loser_id:
            return {"applied": False, "reason": "needs_manual_review"}

        try:
            if result.action == "auto_supersede":
                await self._repo.transition_belief(
                    result.loser_id,
                    new_belief="superseded",
                    reason=f"auto_arbitrated: {result.reason}",
                )
                return {
                    "applied": True,
                    "action": "superseded",
                    "loser_id": result.loser_id,
                    "winner_id": result.winner_id,
                }

            if result.action == "auto_downgrade":
                await self._repo.transition_belief(
                    result.loser_id,
                    new_belief="pending_review",
                    reason=f"auto_downgraded: {result.reason}",
                )
                return {
                    "applied": True,
                    "action": "downgraded",
                    "loser_id": result.loser_id,
                    "winner_id": result.winner_id,
                }
        except Exception as e:
            logger.warning("Failed to apply arbitration: %s", e)
            return {"applied": False, "reason": str(e)}

        return {"applied": False, "reason": "unknown_action"}

    def _compute_arbitration_score(self, node: Any) -> float:
        """Compute arbitration score for a node.

        score = proof_count × source_trust × recency_factor
        """
        proof_count = 1.0
        if hasattr(node, "source_fragment_ids") and isinstance(node.source_fragment_ids, list):
            proof_count = max(len(node.source_fragment_ids), 1)

        source_trust = SOURCE_TRUST_TIERS.get("unknown", 0.5)
        if hasattr(node, "extraction_hint") and node.extraction_hint:
            source_trust = SOURCE_TRUST_TIERS.get(node.extraction_hint, 0.5)

        confidence = getattr(node, "confidence", 1.0)
        feedback_weight = getattr(node, "feedback_weight", 0.5)

        recency_factor = self._compute_recency_factor(node)

        score = proof_count * source_trust * recency_factor * confidence * (0.5 + 0.5 * feedback_weight)
        return score

    def _compute_recency_factor(self, node: Any) -> float:
        """Compute recency factor using exponential decay.

        factor = 2^(-days_elapsed / half_life)
        """
        from datetime import datetime, timezone

        created_at = getattr(node, "created_at", None)
        if not created_at:
            return 0.5

        try:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            days_elapsed = max((now - created_at).total_seconds() / 86400, 0)
            return 2.0 ** (-days_elapsed / self._recency_half_life_days)
        except Exception:
            return 0.5
