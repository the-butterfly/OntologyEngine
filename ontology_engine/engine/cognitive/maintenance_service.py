from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.errors import CognitiveNodeNotFoundError
from ontology_engine.engine.cognitive.memory_utils import make_response
from ontology_engine.engine.cognitive.models import CognitiveEdge, CognitiveNode

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
    from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
    from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class MaintenanceService:

    def __init__(
        self,
        repository: "CognitiveRepository",
        consolidation_engine: "ConsolidationEngine",
        forgetting_engine: "ForgettingEngine",
        dream_cycle: "DreamCycle",
        correction_propagation: "CorrectionPropagation | None" = None,
    ):
        self._repo = repository
        self._consolidation = consolidation_engine
        self._forgetting = forgetting_engine
        self._dream = dream_cycle
        self._correction_propagation = correction_propagation

    async def run_consolidation(self, space_id: str) -> dict[str, Any]:
        result = await self._consolidation.run_consolidation_job(space_id)
        return {
            "created": result.created,
            "updated": result.updated,
            "deleted": result.deleted,
            "errors": result.errors,
            "space_id": space_id,
        }

    async def run_forgetting(self, space_id: str, days_elapsed: int = 1) -> dict[str, Any]:
        result = await self._forgetting.apply_forgetting(space_id, days_elapsed=days_elapsed)
        return {
            "result": result,
            "space_id": space_id,
            "days_elapsed": days_elapsed,
        }

    async def dream(self, space_id: str) -> dict[str, Any]:
        result = await self._dream.run(space_id)
        return {
            "contradictions": len(result.contradictions),
            "expired": len(result.expired),
            "orphans_cleaned": result.orphans_cleaned,
            "links_enhanced": result.links_enhanced,
            "graph_completed": result.graph_completed,
            "errors": result.errors,
            "space_id": space_id,
            "phases_completed": 5 - len(result.errors),
            "skipped": False,
            "contradictions_found": len(result.contradictions),
        }

    async def run_dream_cycle(self, space_id: str) -> dict[str, Any]:
        return await self.dream(space_id)

    async def correct_memory(
        self,
        node_id: str,
        space_id: str,
        corrected_text: str,
        reason: str = "",
        user_id: str = "system",
    ) -> dict[str, Any]:
        old_node = await self._repo.get_node(node_id)
        if not old_node:
            raise CognitiveNodeNotFoundError(node_id)

        effective_space_id = space_id

        new_node_id = f"mem:{old_node.memory_type}:{effective_space_id}:{uuid.uuid4().hex[:12]}"
        new_attributes = dict(old_node.attributes or {})
        new_attributes["corrected_from"] = node_id

        new_node = CognitiveNode(
            id=new_node_id,
            memory_type=old_node.memory_type,
            cognitive_layer=old_node.cognitive_layer,
            content=corrected_text,
            domain_id=old_node.domain_id,
            space_id=effective_space_id,
            visibility=old_node.visibility,
            created_by=user_id,
            confidence=old_node.confidence,
            belief_status=old_node.belief_status,
            occurred_at=old_node.occurred_at,
            schema_ref=old_node.schema_ref,
            tags=old_node.tags,
            attributes=new_attributes,
            confirmation_count=old_node.confirmation_count,
            feedback_weight=old_node.feedback_weight,
            valid_from=old_node.valid_from,
            valid_to=old_node.valid_to,
            recorded_at=old_node.recorded_at,
            strength=old_node.strength,
            entity_name=old_node.entity_name,
            entity_type=old_node.entity_type,
            version=old_node.version + 1,
            source_trust_tier=old_node.source_trust_tier,
            scope=old_node.scope,
            source_pipeline=old_node.source_pipeline,
            source_content_hash=old_node.source_content_hash,
        )

        await self._repo.create_node(new_node)

        await self._repo.transition_belief(node_id, "superseded", reason=reason or "corrected")

        old_node_updated = await self._repo.get_node(node_id)
        if old_node_updated:
            old_node_updated.superseded_by = new_node_id
            await self._repo.update_node(old_node_updated)

        try:
            await self._repo.create_cognitive_edge(CognitiveEdge(
                edge_type="SUPERSEDES",
                from_id=new_node_id,
                to_id=node_id,
                properties={"reason": reason or "corrected"},
            ))
        except Exception as e:
            logger.warning("Failed to create SUPERSEDES edge: %s", e)

        if hasattr(self._forgetting, "apply_strategic_forgetting"):
            await self._forgetting.apply_strategic_forgetting(node_id, "superseded")

        if self._correction_propagation is not None and hasattr(self._correction_propagation, "propagate"):
            try:
                await self._correction_propagation.propagate(
                    source_node_id=node_id, signal="superseded",
                )
            except TypeError:
                await self._correction_propagation.propagate(
                    source_node_id=node_id,
                )

        logger.info(
            "Memory corrected: old=%s new=%s space=%s reason=%s",
            node_id, new_node_id, effective_space_id, reason,
        )

        await self._consolidation.maybe_trigger_consolidation(
            effective_space_id, trigger="correction",
        )

        return make_response(
            data={"new_node_id": new_node_id, "old_node_id": node_id},
            space_id=effective_space_id,
        )

    async def delete_memory(
        self,
        node_id: str,
        space_id: str,
        cascade: bool = False,
        user_id: str = "system",
    ) -> dict[str, Any]:
        await self._repo.delete_node(node_id, soft=not cascade)
        return make_response(
            data={"memory_id": node_id, "deleted": True, "cascade": cascade},
            space_id=space_id,
        )
