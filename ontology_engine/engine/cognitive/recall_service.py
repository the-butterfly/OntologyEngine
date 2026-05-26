from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.evidence_expander import EvidenceExpander
from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveErrorCode,
    EvidenceExpansionError,
)
from ontology_engine.engine.cognitive.memory_utils import (
    RecallRequest,
    compute_strength,
    compute_temporal_proximity,
    make_response,
)
from ontology_engine.engine.cognitive.models import apply_dynamic_weight, compute_temporal_weight
from ontology_engine.engine.cognitive.reflect_types import ReflectionStatus
from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.query_router import QueryRouter
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class RecallService:

    def __init__(
        self,
        repository: "CognitiveRepository",
        query_router: "QueryRouter",
        qul: Any | None = None,
    ):
        self._repo = repository
        self._router = query_router
        self._qul = qul

    async def recall(self, req: RecallRequest, job_store: Any | None = None) -> dict[str, Any]:
        if req.reflection_id is not None:
            return await self._recall_reflection_progress(req.reflection_id, job_store)

        if not req.query or not req.query.strip():
            raise CognitiveError("Query cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if not req.space_id or not req.space_id.strip():
            raise CognitiveError("Space ID cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        from ontology_engine.engine.cognitive.query_router import detect_query_type

        qul_constraints = None
        _qul_strategy = None
        if self._qul is not None:
            try:
                from ontology_engine.engine.cognitive.query_understanding_layer import RecallContext
                context = RecallContext(space_id=req.space_id, user_id=req.user_id or "")
                qul_constraints = await self._qul.extract_constraints(req.query, context)
                if qul_constraints:
                    _qul_strategy = self._qul.map_to_retrieval_strategy(qul_constraints)
                    query_type = self._qul.infer_query_type(qul_constraints)
                else:
                    query_type = "type_filter" if req.memory_type else detect_query_type(req.query)
            except Exception:
                query_type = "type_filter" if req.memory_type else detect_query_type(req.query)
        else:
            query_type = "type_filter" if req.memory_type else detect_query_type(req.query)

        if req.memory_type:
            belief_filter = req.belief_status_filter or "accepted"
            nodes = await self._repo.query_nodes(
                memory_type=req.memory_type,
                domain_id=req.space_id,
                limit=req.max_results,
                as_of=req.as_of,
                belief_status=belief_filter,
                cognitive_layer=req.cognitive_layer,
            )
            results = []
            for n in nodes:
                strength_info = compute_strength(n)
                results.append({
                    "id": n.id,
                    "memory_type": n.memory_type,
                    "text": n.content,
                    "cognitive_layer": n.cognitive_layer,
                    "belief_status": n.belief_status,
                    "proof_count": len(n.source_fragment_ids),
                    "visibility": n.visibility,
                    "created_by": n.created_by,
                    "confidence": n.confidence,
                    "strength": strength_info["value"],
                    "strength_breakdown": strength_info["breakdown"],
                })
        else:
            retrieval_results = await self._router.route(
                query=req.query,
                space_id=req.space_id,
                top_k=req.max_results,
                allow_short_circuit=req.allow_short_circuit,
                strategy_adjustment=_qul_strategy,
            )
            results = []
            for r in retrieval_results:
                strength_info = None
                try:
                    node_data = await self._repo.get_node(r.doc_id)
                    strength_info = compute_strength(node_data)
                    result_entry = {
                        "id": r.doc_id,
                        "memory_type": r.memory_type,
                        "text": r.content,
                        "cognitive_layer": r.cognitive_layer,
                        "belief_status": node_data.belief_status,
                        "score": r.score,
                        "source": r.source,
                        "visibility": node_data.visibility,
                        "created_by": node_data.created_by,
                        "confidence": node_data.confidence,
                        "strength": strength_info["value"],
                        "strength_breakdown": strength_info["breakdown"],
                    }
                except Exception:
                    result_entry = {
                        "id": r.doc_id,
                        "memory_type": r.memory_type,
                        "text": r.content,
                        "cognitive_layer": r.cognitive_layer,
                        "belief_status": "accepted",
                        "score": r.score,
                        "source": r.source,
                        "visibility": None,
                        "created_by": None,
                        "confidence": 1.0,
                        "strength": 0.5,
                        "strength_breakdown": {},
                    }
                results.append(result_entry)

        if req.min_confidence > 0:
            results = [r for r in results if r.get("confidence", 1.0) >= req.min_confidence]

        if req.belief_status_filter is not None:
            results = [r for r in results if r.get("belief_status") == req.belief_status_filter]

        if req.cognitive_layer is not None:
            results = [r for r in results if r.get("cognitive_layer") == req.cognitive_layer]

        if req.user_id is not None:
            filtered = []
            for r in results:
                vis = r.get("visibility")
                if vis is None:
                    continue
                if vis == "public":
                    filtered.append(r)
                elif vis == "shared":
                    filtered.append(r)
                elif vis == "private" and r.get("created_by") == req.user_id:
                    filtered.append(r)
            results = filtered

        if req.include_evidence and req.evidence_depth > 0:
            expander = EvidenceExpander(self._repo)
            for result in results:
                try:
                    evidence = await expander.expand(
                        result["id"], req.space_id, depth=req.evidence_depth,
                    )
                    if evidence:
                        result["evidence"] = [
                            {
                                "id": e.doc_id,
                                "memory_type": e.memory_type,
                                "text": e.content,
                                "edge_type": e.edge_type,
                                "confidence": e.confidence,
                                "contribution": e.contribution,
                            }
                            for e in evidence
                        ]
                except EvidenceExpansionError as exc:
                    logger.warning("Evidence expansion failed for %s: %s", result["id"], exc)

        for result in results:
            tw = BASE_TYPE_WEIGHTS.get(result.get("memory_type", "fragment"), 1.0)
            result["type_weight"] = tw

        profile = None
        try:
            scene = req.disposition_override if isinstance(req.disposition_override, str) else None
            if scene:
                try:
                    profile = await self._repo.get_profile_by_scene(scene, domain_id=req.space_id)
                except Exception:
                    pass
            if profile is None:
                try:
                    profile = await self._repo.get_profile_by_scene("default", domain_id=req.space_id)
                except Exception:
                    pass
            if profile is not None:
                for result in results:
                    mt = result.get("memory_type", "fragment")
                    raw_score = result.get("score", 0.5)
                    dynamic_score = apply_dynamic_weight(raw_score, mt, profile)
                    result["type_weight"] = round(dynamic_score / max(raw_score, 0.001), 3)
        except Exception:
            pass

        recency_bias = 0.5
        if profile is not None:
            recency_bias = getattr(profile, 'recency_bias', 0.5)
        tw = compute_temporal_weight(recency_bias)

        for result in results:
            tp = compute_temporal_proximity(result)
            result["temporal_proximity"] = round(tp, 4)
            result["rank_score"] = round(result.get("score", 0.5) * result["type_weight"] * ((1 - tw) + tw * tp), 3)

        if qul_constraints and self._qul is not None:
            try:
                results = self._qul.apply_constraint_boost(results, qul_constraints)
            except Exception:
                pass

        if req.token_budget is not None and req.token_budget > 0:
            total_tokens = 0
            trimmed_results = []
            for r in results:
                text = r.get("text", "")
                estimated = max(1, len(text) // 4)
                if total_tokens + estimated <= req.token_budget:
                    trimmed_results.append(r)
                    total_tokens += estimated
                else:
                    break
            results = trimmed_results

        actual_tokens = sum(max(1, len(r.get("text", "")) // 4) for r in results)

        return make_response(
            data={
                "results": results,
                "total": len(results),
                "query_type": query_type,
                "total_tokens": actual_tokens,
            },
            space_id=req.space_id,
        )

    async def _recall_reflection_progress(self, reflection_id: str, job_store: Any | None = None) -> dict[str, Any]:
        if job_store is None:
            raise CognitiveError(
                f"Reflection job '{reflection_id}' not found",
                CognitiveErrorCode.NODE_NOT_FOUND,
            )
        job = await job_store.get_job(reflection_id)
        if not job:
            raise CognitiveError(
                f"Reflection job '{reflection_id}' not found",
                CognitiveErrorCode.NODE_NOT_FOUND,
            )
        progress = job.progress
        if not progress:
            return make_response(
                data={"reflection_id": reflection_id, "status": "unknown"},
                space_id=job.space_id,
            )

        if progress.status == ReflectionStatus.COMPLETED and "final_result" in progress.partial_results:
            return progress.partial_results["final_result"]

        return make_response(
            data={
                "reflection_id": reflection_id,
                "status": progress.status.value,
                "progress": progress.progress,
                "partial_results": progress.partial_results,
                "error": progress.error,
            },
            space_id=job.space_id,
        )
