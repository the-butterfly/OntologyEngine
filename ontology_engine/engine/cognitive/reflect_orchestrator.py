from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.memory_utils import (
    ReflectRequest,
    generate_memory_id,
    make_response,
)
from ontology_engine.engine.cognitive.models import CognitiveEdge
from ontology_engine.engine.cognitive.reflect_types import (
    ReflectionJob,
    ReflectionPhase,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.approval_service import ApprovalService
    from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
    from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
    from ontology_engine.engine.cognitive.lifecycle import ForgettingEngine
    from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class ReflectOrchestrator:

    def __init__(
        self,
        repository: "CognitiveRepository",
        reflect_agent: "ReflectAgent",
        consolidation_engine: "ConsolidationEngine",
        forgetting_engine: "ForgettingEngine",
        approval_service: "ApprovalService",
        correction_propagation: "CorrectionPropagation | None" = None,
        job_store: Any | None = None,
    ):
        self._repo = repository
        self._reflect = reflect_agent
        self._consolidation = consolidation_engine
        self._forgetting = forgetting_engine
        self._approval = approval_service
        self._correction_propagation = correction_propagation
        self._job_store = job_store

    async def execute_reflect(
        self,
        req: ReflectRequest,
        job: ReflectionJob | None = None,
    ) -> dict[str, Any]:
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.RETRIEVAL.value, "in_progress"
            )

        reflect_result = await self._reflect.reflect(
            query=req.query,
            space_id=req.space_id,
            max_iterations=req.max_iterations,
            focus_types=req.focus_types,
        )

        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.RETRIEVAL.value, "completed"
            )
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.CONTRADICTION_DETECTION.value, "completed"
            )
            await self._job_store.set_partial_results(
                job.reflection_id,
                "insights",
                [
                    {"text": i.text, "confidence": i.confidence, "evidence_ids": i.evidence_ids}
                    for i in reflect_result.insights
                ],
            )
            await self._job_store.set_partial_results(
                job.reflection_id,
                "contradictions",
                [
                    {"node_ids": c.node_ids, "contradiction_type": c.contradiction_type}
                    for c in reflect_result.contradictions
                ],
            )

        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.BELIEF_REVISION.value, "in_progress"
            )

        arbitration_results = await self._run_arbitration(reflect_result.contradictions)

        belief_revisions = await self._run_belief_revision(
            reflect_result.contradictions, arbitration_results,
        )

        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.BELIEF_REVISION.value, "completed"
            )

        consolidation_result = await self._run_consolidation(
            reflect_result.consolidation_requests, req.skip_consolidation, job,
        )

        forgetting_result = await self._run_forgetting(
            reflect_result.forgetting_requests, req, job,
        )

        propagation_result = await self._run_correction_propagation(
            belief_revisions, req, job,
        )

        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.SCHEMA_SUGGESTION.value, "completed"
            )

        return make_response(
            data={
                "insights": [
                    {
                        "text": i.text,
                        "type": "new_insight",
                        "memory_id": generate_memory_id(i.text, req.space_id, i.suggested_memory_type),
                        "memory_type": i.suggested_memory_type,
                        "confidence": i.confidence,
                        "evidence_ids": i.evidence_ids,
                    }
                    for i in reflect_result.insights
                ],
                "contradictions": [c.to_api_dict() for c in reflect_result.contradictions],
                "consolidation": {
                    "fragments_processed": (consolidation_result.get("created", 0) + consolidation_result.get("updated", 0) + consolidation_result.get("deleted", 0) + consolidation_result.get("errors", 0)) if consolidation_result else 0,
                    "observations_created": consolidation_result.get("created", 0) if consolidation_result else 0,
                    "observations_updated": consolidation_result.get("updated", 0) if consolidation_result else 0,
                } if consolidation_result is not None else None,
                "forgetting": {
                    "memories_decayed": (forgetting_result.get("soft_decayed", 0) + forgetting_result.get("demoted", 0)) if forgetting_result else 0,
                    "memories_archived": (forgetting_result.get("archived", 0) + forgetting_result.get("deleted", 0)) if forgetting_result else 0,
                } if forgetting_result is not None else None,
                "correction_propagation": propagation_result,
                "mental_model_updates": [
                    {"model_id": u.model_id, "action": u.update_type}
                    for u in reflect_result.mental_model_updates
                ],
                "iterations_used": reflect_result.iterations_used if hasattr(reflect_result, "iterations_used") and reflect_result.iterations_used else 1,
                "tokens_used": reflect_result.tokens_used if hasattr(reflect_result, "tokens_used") and reflect_result.tokens_used else 0,
            },
            space_id=req.space_id,
        )

    async def _run_arbitration(self, contradictions: list[Any]) -> list[dict[str, Any]]:
        results = []
        if not contradictions:
            return results
        from ontology_engine.engine.cognitive.arbitration_engine import ArbitrationEngine
        arb_engine = ArbitrationEngine(repository=self._repo)
        for c in contradictions:
            if len(c.node_ids) < 2:
                continue
            try:
                arb_result = await arb_engine.arbitrate(
                    node_ids=c.node_ids,
                    contradiction_type=c.contradiction_type,
                )
                if not arb_result.needs_manual_review:
                    apply_result = await arb_engine.apply_arbitration(arb_result)
                    results.append({
                        "winner_id": arb_result.winner_id,
                        "loser_id": arb_result.loser_id,
                        "action": arb_result.action,
                        "applied": apply_result.get("applied", False),
                    })
                else:
                    results.append({
                        "needs_manual_review": True,
                        "reason": arb_result.reason,
                    })
            except Exception as e:
                logger.debug("Arbitration failed for contradiction: %s", e)
        return results

    async def _run_belief_revision(
        self,
        contradictions: list[Any],
        arbitration_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        belief_revisions = []
        for c in contradictions:
            already_arbitrated = any(
                ar.get("loser_id") in c.node_ids and ar.get("applied")
                for ar in arbitration_results
            )
            if already_arbitrated:
                continue
            for node_id in c.node_ids:
                try:
                    revision = await self._approval.apply_belief_revision_rules(node_id, c)
                    if revision:
                        belief_revisions.append(revision)
                    else:
                        await self._repo.transition_belief(
                            node_id, "pending_review",
                            reason=f"Contradiction detected: {c.contradiction_type}",
                        )
                        belief_revisions.append({"node_id": node_id, "new_status": "pending_review"})
                except Exception as e:
                    logger.debug("Belief revision skipped for %s: %s", node_id, e)

            if len(c.node_ids) >= 2:
                try:
                    edge = CognitiveEdge(
                        edge_type="CONTRADICTS",
                        from_id=c.node_ids[0],
                        to_id=c.node_ids[1],
                    )
                    await self._repo.create_cognitive_edge(edge)
                except Exception as e:
                    logger.debug("Failed to create CONTRADICTS edge: %s", e)
        return belief_revisions

    async def _run_consolidation(
        self,
        consolidation_requests: list[str],
        skip: bool,
        job: ReflectionJob | None,
    ) -> dict[str, int] | None:
        if not consolidation_requests or skip:
            if skip and job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CONSOLIDATION.value, "completed"
                )
            return None
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.CONSOLIDATION.value, "in_progress"
            )
        try:
            total_created = 0
            total_updated = 0
            total_deleted = 0
            total_errors = 0
            for req_space in consolidation_requests:
                result = await self._consolidation.run_consolidation_job(req_space)
                total_created += len(result.created)
                total_updated += len(result.updated)
                total_deleted += len(result.deleted)
                total_errors += len(result.errors)
            consolidation_result = {
                "created": total_created,
                "updated": total_updated,
                "deleted": total_deleted,
                "errors": total_errors,
            }
        except Exception as e:
            logger.warning("Consolidation during reflect failed: %s", e)
            consolidation_result = None
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.CONSOLIDATION.value, "completed"
            )
        return consolidation_result

    async def _run_forgetting(
        self,
        forgetting_requests: list[str],
        req: ReflectRequest,
        job: ReflectionJob | None,
    ) -> dict[str, Any] | None:
        if not forgetting_requests or req.skip_forgetting:
            if req.skip_forgetting and job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.FORGETTING.value, "completed"
                )
            return None
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.FORGETTING.value, "in_progress"
            )
        forgetting_result = None
        try:
            forgetting_result = await self._forgetting.apply_forgetting(req.space_id)
        except Exception as e:
            logger.warning("Forgetting during reflect failed: %s", e)
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.FORGETTING.value, "completed"
            )
        return forgetting_result

    async def _run_correction_propagation(
        self,
        belief_revisions: list[dict[str, Any]],
        req: ReflectRequest,
        job: ReflectionJob | None,
    ) -> dict[str, Any] | None:
        if req.skip_correction_propagation or self._correction_propagation is None:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CORRECTION_PROPAGATION.value, "completed"
                )
            return None
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.CORRECTION_PROPAGATION.value, "in_progress"
            )
        propagation_result = None
        try:
            for revision in belief_revisions:
                node_id = revision["node_id"]
                prop = await self._correction_propagation.propagate(
                    node_id, cascade_depth=req.cascade_depth,
                )
                if prop.propagated_count > 0:
                    propagation_result = {
                        "source_node_id": node_id,
                        "reviewed_node_ids": prop.reviewed_node_ids,
                        "propagated_count": prop.propagated_count,
                        "depth_reached": prop.depth_reached,
                    }
        except Exception as e:
            logger.warning("Correction propagation failed: %s", e)
        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.CORRECTION_PROPAGATION.value, "completed"
            )
        return propagation_result
