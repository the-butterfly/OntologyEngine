from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.consolidation_engine import compute_schema_alignment_score
from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveErrorCode,
)
from ontology_engine.engine.cognitive.memory_utils import make_response
from ontology_engine.engine.cognitive.models import (
    BeliefRevisionRule,
    DEFAULT_BELIEF_REVISION_RULES,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.reflect_types import ContradictionReport
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class ApprovalService:

    def __init__(self, repository: "CognitiveRepository"):
        self._repo = repository

    async def approve_memory(
        self,
        node_id: str,
        action: str = "approve",
        modifier_id: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        node = await self._repo.get_node(node_id)

        if node.belief_status != "pending_review":
            raise CognitiveError(
                f"Node '{node_id}' is in '{node.belief_status}' state, "
                f"not 'pending_review'. Only pending_review nodes can be approved.",
                CognitiveErrorCode.INVALID_BELIEF_TRANSITION,
            )

        if node.feedback_weight > 0.8 and action in ("reject", "modify"):
            raise CognitiveError(
                f"Feedback protection rule (BR_R005) blocks {action}: "
                f"node '{node_id}' has feedback_weight={node.feedback_weight}",
                CognitiveErrorCode.PROTECTED_MEMORY,
            )

        target_status = {
            "approve": "accepted",
            "reject": "rejected",
            "modify": "accepted",
        }.get(action)

        if target_status is None:
            raise CognitiveError(
                f"Invalid approval action: '{action}'. Use 'approve', 'reject', or 'modify'.",
                CognitiveErrorCode.INVALID_MEMORY_TYPE,
            )

        reason = comment or f"Memory {action}d by {modifier_id or 'system'}"
        await self._repo.transition_belief(node_id, target_status, reason=reason)

        if action == "approve":
            node = await self._repo.get_node(node_id)
            node.confidence = 1.0
            await self._repo.update_node(node, reason=reason, action=f"approval_{action}")
        elif action == "reject":
            node = await self._repo.get_node(node_id)
            node.confidence = 0.0
            await self._repo.update_node(node, reason=reason, action=f"approval_{action}")

        return make_response(
            data={
                "node_id": node_id,
                "action": action,
                "new_belief_status": node.belief_status,
                "new_confidence": node.confidence,
                "modified_by": modifier_id,
            },
            space_id=node.space_id,
        )

    async def update_disposition(
        self,
        space_id: str,
        disposition: Any,
    ) -> dict[str, Any]:
        if hasattr(self, "_disposition_store") and self._disposition_store:
            await self._disposition_store.save(space_id, disposition)
        return make_response(
            data={"space_id": space_id, "updated": True},
            space_id=space_id,
        )

    async def apply_belief_revision_rules(
        self,
        node_id: str,
        contradiction: "ContradictionReport",
        rules: list[BeliefRevisionRule] | None = None,
    ) -> dict[str, Any] | None:
        active_rules = rules or DEFAULT_BELIEF_REVISION_RULES
        active_rules = [r for r in active_rules if r.enabled]
        active_rules.sort(key=lambda r: r.priority, reverse=True)

        try:
            node = await self._repo.get_node(node_id)
        except Exception:
            return None

        context = {
            "source": node.extraction_hint or "unknown",
            "confidence": node.confidence,
            "feedback_weight": node.feedback_weight,
            "evidence_count": len(node.source_fragment_ids) if isinstance(node.source_fragment_ids, list) else 0,
            "is_newer": await self._compute_is_newer(node, contradiction),
            "schema_alignment": compute_schema_alignment_score(node) if node.memory_type in ("observation", "entity") else 0.5,
            "conflicting_domains": contradiction.contradiction_type == "belief_conflict",
            "belief_status": node.belief_status,
        }

        for rule in active_rules:
            if rule.track not in ("any", "A", "B"):
                continue
            rule_source = context.get("source", "unknown")
            if rule.track == "A" and rule_source not in ("user_correction", "征信报告", "法院判决", "监管文件"):
                continue
            if rule.track == "B" and rule_source in ("user_correction", "征信报告", "法院判决", "监管文件"):
                continue
            try:
                from ontology_engine.engine.cognitive.rule_eval import safe_eval
                if safe_eval(rule.condition, context):
                    action = rule.action
                    if action.get("block_revision"):
                        return {"node_id": node_id, "new_status": "blocked", "rule": rule.rule_id}

                    new_status = action.get("set_belief")
                    new_confidence = action.get("set_confidence")

                    if new_status and new_status != node.belief_status:
                        await self._repo.transition_belief(
                            node_id, new_status,
                            reason=f"Rule {rule.rule_id} ({rule.name})",
                        )
                    if new_confidence is not None:
                        node.confidence = new_confidence
                        await self._repo.update_node(node, reason=f"Rule {rule.rule_id} confidence update")

                    return {
                        "node_id": node_id,
                        "new_status": new_status or node.belief_status,
                        "rule": rule.rule_id,
                        "confidence": new_confidence,
                    }
            except Exception:
                continue

        return None

    async def _compute_is_newer(self, node: Any, contradiction: "ContradictionReport") -> bool:
        if not hasattr(contradiction, "node_ids") or not contradiction.node_ids:
            return False
        try:
            other_id = contradiction.node_ids[0] if contradiction.node_ids[0] != node.id else contradiction.node_ids[-1]
            if other_id == node.id:
                return False
            if not node.created_at:
                return False
            other_node = await self._repo.get_node(other_id)
            if other_node and other_node.created_at:
                return node.created_at > other_node.created_at
            return True
        except Exception:
            return False
