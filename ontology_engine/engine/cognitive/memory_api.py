"""Memory API - Three-operation cognitive API.

Implements the L1/L2/L3 three-layer abstraction for agent memory:
- remember: Store information (auto-extract, auto-consolidate)
- recall: Retrieve information (auto-route, auto-rank)
- reflect: Analyze information (auto-detect contradictions, trigger maintenance)

Design decisions (from memory-api.md):
- D-API-1: Three operations only (remember/recall/reflect)
- D-API-2: consolidate and forget are reflect internals
- D-API-3: memory_type is optional hint
- D-API-4: L1/L2/L3 three-layer abstraction
- D-API-5: reflect async orchestration
- D-API-6: Evidence chain expansion
- D-API-7: Visibility control (private/shared/public)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.consolidation_engine import compute_schema_alignment_score
from ontology_engine.engine.cognitive.deduplication_gate import WriteDecision
from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveErrorCode,
    CognitiveNodeNotFoundError,
    InvalidMemoryTypeError,
    InvalidVisibilityError,
)
from ontology_engine.engine.cognitive.models import (
    VALID_MEMORY_TYPES,
    VALID_VISIBILITIES,
    BeliefRevisionRule,
    CognitiveNode,
    CognitiveEdge,
    DEFAULT_BELIEF_REVISION_RULES,
    apply_dynamic_weight,
)
from ontology_engine.engine.cognitive.reflect_types import (
    ReflectionJob,
    ReflectionPhase,
    ReflectionProgress,
    ReflectionStatus,
)
from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.cognitive_vector_index import CognitiveVectorIndex
    from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine, compute_schema_alignment_score
    from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
    from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
    from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
    from ontology_engine.engine.cognitive.query_router import QueryRouter
    from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
    from ontology_engine.engine.cognitive.reflect_types import ContradictionReport
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


@dataclass
class RememberRequest:
    content: str
    space_id: str
    tags: dict[str, str | list[str]] | None = None
    memory_type: str = "fragment"
    metadata: dict[str, Any] | None = None
    visibility: str | None = None
    created_by: str | None = None
    confidence: float = 1.0
    supersede_target: str | None = None
    supersede_reason: str | None = None
    belief_status: str = "accepted"
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_at: str | None = None
    occurred_at: str | None = None
    source_pipeline: str | None = None
    schema_ref: str | None = None
    source_fragment_ids: list[str] | None = None


@dataclass
class RecallRequest:
    query: str
    space_id: str
    memory_type: str | None = None
    max_results: int = 10
    include_evidence: bool = True
    evidence_depth: int = 1
    user_id: str | None = None
    as_of: str | None = None
    allow_short_circuit: bool = True
    min_confidence: float = 0.5
    token_budget: int | None = None
    belief_status_filter: str | None = None
    reflection_id: str | None = None
    cognitive_layer: str | None = None
    expansion_rules: str | None = None
    disposition_override: dict[str, Any] | str | None = None


@dataclass
class ReflectRequest:
    query: str
    space_id: str
    max_iterations: int = 10
    focus_types: list[str] | None = None
    skip_consolidation: bool = False
    skip_forgetting: bool = False
    cascade_depth: int = 3
    skip_correction_propagation: bool = False


class ReflectionJobStore:

    def __init__(self):
        self._jobs: dict[str, ReflectionJob] = {}
        self._lock = asyncio.Lock()

    async def create_job(
        self,
        query: str,
        space_id: str,
        max_iterations: int = 10,
        focus_types: list[str] | None = None,
        skip_consolidation: bool = False,
        skip_forgetting: bool = False,
        cascade_depth: int = 3,
        skip_correction_propagation: bool = False,
    ) -> ReflectionJob:
        async with self._lock:
            reflection_id = f"refl:{uuid.uuid4().hex[:12]}"
            progress = ReflectionProgress(
                reflection_id=reflection_id,
                status=ReflectionStatus.PENDING,
                progress={phase.value: "pending" for phase in ReflectionPhase},
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            job = ReflectionJob(
                reflection_id=reflection_id,
                query=query,
                space_id=space_id,
                max_iterations=max_iterations,
                focus_types=focus_types,
                skip_consolidation=skip_consolidation,
                skip_forgetting=skip_forgetting,
                cascade_depth=cascade_depth,
                skip_correction_propagation=skip_correction_propagation,
                progress=progress,
            )
            self._jobs[reflection_id] = job
            return job

    async def get_job(self, reflection_id: str) -> ReflectionJob | None:
        async with self._lock:
            return self._jobs.get(reflection_id)

    async def update_progress(self, reflection_id: str, phase: str, phase_status: str) -> None:
        async with self._lock:
            job = self._jobs.get(reflection_id)
            if job and job.progress:
                job.progress.progress[phase] = phase_status
                if all(s == "completed" for s in job.progress.progress.values()):
                    job.progress.status = ReflectionStatus.COMPLETED
                    job.progress.completed_at = datetime.now(timezone.utc).isoformat()
                elif any(s == "in_progress" for s in job.progress.progress.values()):
                    job.progress.status = ReflectionStatus.IN_PROGRESS

    async def set_partial_results(self, reflection_id: str, key: str, results: Any) -> None:
        async with self._lock:
            job = self._jobs.get(reflection_id)
            if job and job.progress:
                job.progress.partial_results[key] = results

    async def set_error(self, reflection_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(reflection_id)
            if job and job.progress:
                job.progress.status = ReflectionStatus.FAILED
            job.progress.error = error


class MemoryAPI:

    def __init__(
        self,
        repository: "CognitiveRepository",
        consolidation_engine: "ConsolidationEngine",
        entity_resolver: "EntityResolver",
        query_router: "QueryRouter",
        reflect_agent: "ReflectAgent",
        forgetting_engine: "ForgettingEngine",
        dream_cycle: "DreamCycle",
        correction_propagation: "CorrectionPropagation | None" = None,
        vector_index: "CognitiveVectorIndex | None" = None,
        qul: Any | None = None,
        ingestion_service: Any | None = None,
    ):
        self._repo = repository
        self._consolidation = consolidation_engine
        self._resolver = entity_resolver
        self._router = query_router
        self._reflect = reflect_agent
        self._forgetting = forgetting_engine
        self._dream = dream_cycle
        self._correction_propagation = correction_propagation
        self._vector_index = vector_index
        self._qul = qul
        self._ingestion = ingestion_service
        self._job_store = ReflectionJobStore()
        self._background_tasks: set[asyncio.Task[Any]] = set()

        from ontology_engine.engine.cognitive.deduplication_gate import DeduplicationGate
        self._dedup_gate = DeduplicationGate(
            repository=repository,
            vector_index=vector_index,
        )

    async def remember(
        self,
        content: str,
        space_id: str,
        tags: dict[str, str | list[str]] | None = None,
        memory_type: str = "fragment",
        metadata: dict[str, Any] | None = None,
        visibility: str | None = None,
        created_by: str | None = None,
        confidence: float = 1.0,
        supersede_target: str | None = None,
        supersede_reason: str | None = None,
        belief_status: str = "accepted",
        valid_from: str | None = None,
        valid_to: str | None = None,
        recorded_at: str | None = None,
        occurred_at: str | None = None,
        source_pipeline: str | None = None,
        schema_ref: str | None = None,
        source_fragment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        req = RememberRequest(
            content=content,
            space_id=space_id,
            tags=tags,
            memory_type=memory_type,
            metadata=metadata,
            visibility=visibility,
            created_by=created_by,
            confidence=confidence,
            supersede_target=supersede_target,
            supersede_reason=supersede_reason,
            belief_status=belief_status,
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at,
            occurred_at=occurred_at,
            source_pipeline=source_pipeline,
            schema_ref=schema_ref,
            source_fragment_ids=source_fragment_ids,
        )
        return await self._remember(req)

    async def _remember(self, req: RememberRequest) -> dict[str, Any]:
        if not req.content or not req.content.strip():
            raise CognitiveError("Content cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if not req.space_id or not req.space_id.strip():
            raise CognitiveError("Space ID cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if req.memory_type not in VALID_MEMORY_TYPES:
            raise InvalidMemoryTypeError(req.memory_type, VALID_MEMORY_TYPES)

        if req.visibility is None:
            source = req.metadata.get("source") if req.metadata else None
            req.visibility = self._determine_visibility(req.content, req.memory_type, source)
        elif req.visibility not in VALID_VISIBILITIES:
            raise InvalidVisibilityError(req.visibility, VALID_VISIBILITIES)

        gate_result = await self._dedup_gate.check(
            content=req.content,
            space_id=req.space_id,
            memory_type=req.memory_type,
            tags=req.tags,
            confidence=req.confidence,
        )

        if gate_result.decision == WriteDecision.DUPLICATE:
            if gate_result.duplicate_of:
                try:
                    await self._repo.record_access(gate_result.duplicate_of)
                except Exception:
                    pass
            return self._make_response(
                data={
                    "memory_id": gate_result.duplicate_of,
                    "decision": "duplicate",
                    "reason": gate_result.reason,
                    "space_id": req.space_id,
                },
                space_id=req.space_id,
            )

        if gate_result.decision == WriteDecision.CONTRADICTION_CANDIDATE:
            req.belief_status = "pending_review"

        if gate_result.decision == WriteDecision.DELAYED:
            return self._make_response(
                data={
                    "memory_id": None,
                    "decision": "delayed",
                    "reason": gate_result.reason,
                    "marginal_value": gate_result.marginal_value,
                    "space_id": req.space_id,
                },
                space_id=req.space_id,
            )

        node_id = self._generate_memory_id(req.content, req.space_id, req.memory_type)

        cognitive_layer = self._infer_cognitive_layer(req.memory_type)
        initial_tags = self._infer_tags(req.memory_type)
        merged_tags = {**initial_tags, **(req.tags or {})}

        if self._ingestion is not None:
            try:
                ingest_result = await self._ingestion.ingest(
                    content=req.content,
                    space_id=req.space_id,
                    memory_type=req.memory_type,
                    tags=merged_tags,
                    metadata=req.metadata,
                    source_trust_tier="normal",
                    scope=merged_tags.get("model", "world"),
                    source_pipeline="api",
                    user_id=req.created_by or "system",
                    visibility=req.visibility,
                    confidence=req.confidence,
                    belief_status=req.belief_status,
                )
                node_id = ingest_result.get("node_id", node_id)
                return self._make_response(
                    data={
                        "memory_id": node_id,
                        "node_id": node_id,
                        "fragment_id": ingest_result.get("fragment_id"),
                        "decision": "contradiction_candidate" if req.belief_status == "pending_review" else "accepted",
                        "space_id": req.space_id,
                    },
                    space_id=req.space_id,
                )
            except Exception as e:
                logger.warning("IngestionService failed, falling back to direct create: %s", e)

        node = CognitiveNode(
            id=node_id,
            memory_type=req.memory_type,
            cognitive_layer=cognitive_layer,
            content=req.content,
            domain_id=req.space_id,
            space_id=req.space_id,
            visibility=req.visibility,
            created_by=req.created_by,
            confidence=req.confidence,
            belief_status=req.belief_status,
            occurred_at=req.occurred_at,
            schema_ref=req.schema_ref,
            valid_from=req.valid_from,
            valid_to=req.valid_to,
            recorded_at=req.recorded_at,
            tags=merged_tags,
            attributes=self._extract_attributes(req.memory_type, req.metadata),
            source_fragment_ids=req.source_fragment_ids or [],
            proof_count=len(req.source_fragment_ids) if req.source_fragment_ids else 0,
        )
        await self._repo.create_node(node)

        if self._vector_index is not None:
            try:
                await self._vector_index.index_node(
                    node_id=node.id,
                    content=node.content,
                    memory_type=node.memory_type,
                    tags=node.tags,
                    space_id=node.space_id,
                )
            except Exception as e:
                logger.debug("Vector indexing skipped for %s: %s", node.id, e)

        schema_extracted_nodes: list[str] = []
        if req.schema_ref:
            try:
                schema_node_id = self._generate_memory_id(
                    f"schema:{req.schema_ref}:{req.content[:60]}",
                    req.space_id,
                    "observation",
                )
                schema_node = CognitiveNode(
                    id=schema_node_id,
                    memory_type="observation",
                    cognitive_layer="semantic",
                    content=req.content,
                    domain_id=req.space_id,
                    space_id=req.space_id,
                    visibility=req.visibility,
                    created_by=req.created_by,
                    confidence=req.confidence,
                    schema_ref=req.schema_ref,
                    source_fragment_ids=[node_id],
                    extraction_hint="schema_guided",
                )
                await self._repo.create_node(schema_node)
                schema_extracted_nodes.append(schema_node_id)
                await self._repo.create_cognitive_edge(CognitiveEdge(
                    edge_type="CONSOLIDATED_INTO",
                    from_id=node_id,
                    to_id=schema_node_id,
                    properties={"consolidated_at": datetime.now(timezone.utc).isoformat()},
                ))
            except Exception as e:
                logger.warning("Schema-guided extraction failed: %s", e)

        extracted_entities: list[str] = []
        try:
            entity_id = await self._resolver.resolve_and_create_or_reuse(
                entity_text=req.content[:50],
                entity_type="auto_extracted",
                space_id=req.space_id,
            )
            extracted_entities.append(entity_id)
        except Exception as e:
            logger.debug("Entity extraction skipped: %s", e)

        consolidation_triggered = False
        if self._consolidation is not None:
            try:
                triggered = await self._consolidation.maybe_trigger_consolidation(
                    req.space_id, trigger="post_write"
                )
                consolidation_triggered = triggered
            except Exception as e:
                logger.warning("Consolidation post-write hook failed: %s", e)

        superseded_node_id: str | None = None
        if req.supersede_target:
            try:
                target = await self._repo.get_node(req.supersede_target)
                target.superseded_by = node_id
                target.belief_status = "superseded"
                target.confidence = 0.0
                reason = req.supersede_reason or "correction"
                await self._repo.update_node(target, reason=reason, action="superseded")
                superseded_node_id = target.id

                edge = CognitiveEdge(
                    edge_type="SUPERSEDES",
                    from_id=node_id,
                    to_id=superseded_node_id,
                )
                await self._repo.create_cognitive_edge(edge)
            except CognitiveNodeNotFoundError:
                logger.warning("Supersede target '%s' not found", req.supersede_target)
            except Exception as e:
                logger.warning("Supersede failed for '%s': %s", req.supersede_target, e)

        return self._make_response(
            data={
                "memory_id": node_id,
                "memory_type": req.memory_type,
                "visibility": req.visibility,
                "extracted_entities": extracted_entities,
                "schema_extracted_nodes": schema_extracted_nodes,
                "consolidation_triggered": consolidation_triggered,
                "superseded_node_id": superseded_node_id,
            },
            space_id=req.space_id,
        )

    async def recall(
        self,
        query: str,
        space_id: str,
        memory_type: str | None = None,
        max_results: int = 10,
        include_evidence: bool = True,
        evidence_depth: int = 1,
        user_id: str | None = None,
        as_of: str | None = None,
        allow_short_circuit: bool = True,
        min_confidence: float = 0.5,
        token_budget: int | None = None,
        belief_status_filter: str | None = None,
        reflection_id: str | None = None,
        cognitive_layer: str | None = None,
        expansion_rules: str | None = None,
        disposition_override: dict[str, Any] | str | None = None,
        include_superseded: bool = False,
        audit_trail: bool = False,
    ) -> dict[str, Any]:
        if audit_trail or include_superseded:
            nodes = await self._repo.query_nodes(domain_id=space_id, limit=max_results * 3)
            superseded_nodes = [
                n for n in nodes
                if n.belief_status in ("superseded", "rejected")
                or getattr(n, "superseded_by", None)
            ]
            return self._make_response(
                data={
                    "results": [
                        {
                            "id": n.id, "content": n.content,
                            "memory_type": n.memory_type,
                            "belief_status": n.belief_status,
                            "superseded_by": getattr(n, "superseded_by", None),
                            "updated_at": n.updated_at,
                        }
                        for n in superseded_nodes[:max_results]
                    ],
                    "total_superseded": len(superseded_nodes),
                },
                space_id=space_id,
            )

        req = RecallRequest(
            query=query,
            space_id=space_id,
            memory_type=memory_type,
            max_results=max_results,
            include_evidence=include_evidence,
            evidence_depth=evidence_depth,
            user_id=user_id,
            as_of=as_of,
            allow_short_circuit=allow_short_circuit,
            min_confidence=min_confidence,
            token_budget=token_budget,
            belief_status_filter=belief_status_filter,
            reflection_id=reflection_id,
            cognitive_layer=cognitive_layer,
            expansion_rules=expansion_rules,
            disposition_override=disposition_override,
        )
        return await self._recall(req)

    async def _recall(self, req: RecallRequest) -> dict[str, Any]:
        if req.reflection_id is not None:
            return await self._recall_reflection_progress(req.reflection_id)

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
                strength_info = self._compute_strength(n)
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
                    strength_info = self._compute_strength(node_data)
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
            for result in results:
                try:
                    evidence = await self._router.expand_evidence(
                        result["id"], req.space_id, depth=req.evidence_depth
                    )
                    if not evidence:
                        try:
                            node = await self._repo.get_node(result["id"])
                            if node.source_fragment_ids:
                                for frag_id in node.source_fragment_ids:
                                    try:
                                        frag = await self._repo.get_node(frag_id)
                                        from ontology_engine.engine.cognitive.rrf_types import RetrievalResult
                                        evidence.append(RetrievalResult(
                                            doc_id=frag.id,
                                            content=frag.content,
                                            source="evidence_depth_1",
                                            memory_type=frag.memory_type,
                                            cognitive_layer=frag.cognitive_layer,
                                            edge_type="SUPPORTS",
                                            confidence=frag.confidence,
                                            contribution=round(1.0 / len(node.source_fragment_ids), 3),
                                        ))
                                    except Exception:
                                        continue
                        except Exception:
                            pass
                    if not evidence:
                        try:
                            consolidated_edges = await self._repo.query_cognitive_edges(
                                from_id=result["id"], edge_type="CONSOLIDATED_INTO", limit=5,
                            )
                            for edge in consolidated_edges:
                                try:
                                    consolidated = await self._repo.get_node(edge.to_id)
                                    if consolidated.source_fragment_ids:
                                        for frag_id in consolidated.source_fragment_ids:
                                            try:
                                                frag = await self._repo.get_node(frag_id)
                                                from ontology_engine.engine.cognitive.rrf_types import RetrievalResult
                                                evidence.append(RetrievalResult(
                                                    doc_id=frag.id,
                                                    content=frag.content,
                                                    source="evidence_depth_1",
                                                    memory_type=frag.memory_type,
                                                    cognitive_layer=frag.cognitive_layer,
                                                    edge_type="SUPPORTS",
                                                    confidence=frag.confidence,
                                                    contribution=round(1.0 / len(consolidated.source_fragment_ids), 3),
                                                ))
                                            except Exception:
                                                continue
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            pass
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
                except Exception:
                    pass

        for result in results:
            tw = BASE_TYPE_WEIGHTS.get(result.get("memory_type", "fragment"), 1.0)
            result["type_weight"] = tw

        try:
            profile = None
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

        from ontology_engine.engine.cognitive.models import compute_temporal_weight

        recency_bias = 0.5
        if profile is not None:
            recency_bias = getattr(profile, 'recency_bias', 0.5)
        tw = compute_temporal_weight(recency_bias)

        for result in results:
            tp = self._compute_temporal_proximity(result)
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

        return self._make_response(
            data={
                "results": results,
                "total": len(results),
                "query_type": query_type,
                "total_tokens": actual_tokens,
            },
            space_id=req.space_id,
        )

    async def reflect(
        self,
        query: str,
        space_id: str,
        max_iterations: int = 10,
        focus_types: list[str] | None = None,
        async_mode: bool = True,
        skip_consolidation: bool = False,
        skip_forgetting: bool = False,
        cascade_depth: int = 3,
        skip_correction_propagation: bool = False,
    ) -> dict[str, Any]:
        req = ReflectRequest(
            query=query,
            space_id=space_id,
            max_iterations=max_iterations,
            focus_types=focus_types,
            skip_consolidation=skip_consolidation,
            skip_forgetting=skip_forgetting,
            cascade_depth=cascade_depth,
            skip_correction_propagation=skip_correction_propagation,
        )

        if not req.query or not req.query.strip():
            raise CognitiveError("Query cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if not req.space_id or not req.space_id.strip():
            raise CognitiveError("Space ID cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if async_mode:
            job = await self._job_store.create_job(
                req.query,
                req.space_id,
                req.max_iterations,
                req.focus_types,
                req.skip_consolidation,
                req.skip_forgetting,
                req.cascade_depth,
                req.skip_correction_propagation,
            )
            task = asyncio.create_task(self._run_reflect_background(job))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return self._make_response(
                data={
                    "reflection_id": job.reflection_id,
                    "status": job.progress.status.value if job.progress else "pending",
                },
                space_id=req.space_id,
            )

        return await self._execute_reflect(req)

    async def _recall_reflection_progress(self, reflection_id: str) -> dict[str, Any]:
        """Query reflection progress via recall(reflection_id=...).

        Design §11.2 - Progress query via recall instead of get_reflection_status.
        Returns progress info when in_progress, full result when completed.
        """
        job = await self._job_store.get_job(reflection_id)
        if not job:
            raise CognitiveError(
                f"Reflection job '{reflection_id}' not found",
                CognitiveErrorCode.NODE_NOT_FOUND,
            )
        progress = job.progress
        if not progress:
            return self._make_response(
                data={"reflection_id": reflection_id, "status": "unknown"},
                space_id=job.space_id,
            )

        if progress.status == ReflectionStatus.COMPLETED and "final_result" in progress.partial_results:
            return progress.partial_results["final_result"]

        return self._make_response(
            data={
                "reflection_id": reflection_id,
                "status": progress.status.value,
                "progress": progress.progress,
                "partial_results": progress.partial_results,
                "error": progress.error,
            },
            space_id=job.space_id,
        )

    async def get_reflection_status(self, reflection_id: str) -> dict[str, Any]:
        job = await self._job_store.get_job(reflection_id)
        if not job:
            raise CognitiveError(
                f"Reflection job '{reflection_id}' not found",
                CognitiveErrorCode.NODE_NOT_FOUND,
            )
        progress = job.progress
        return self._make_response(
            data={
                "reflection_id": reflection_id,
                "status": progress.status.value if progress else "unknown",
                "progress": progress.progress if progress else {},
                "partial_results": progress.partial_results if progress else {},
                "error": progress.error if progress else None,
            },
            space_id=job.space_id,
        )

    async def get_stats(self, space_id: str) -> dict[str, Any]:
        """Get memory statistics for a space."""
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=10000)
        total = len(nodes)
        by_type: dict[str, int] = {}
        by_belief: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        for n in nodes:
            by_type[n.memory_type] = by_type.get(n.memory_type, 0) + 1
            by_belief[n.belief_status] = by_belief.get(n.belief_status, 0) + 1
            by_layer[n.cognitive_layer] = by_layer.get(n.cognitive_layer, 0) + 1
        return {
            "total": total,
            "by_type": by_type,
            "by_belief": by_belief,
            "by_layer": by_layer,
            "space_id": space_id,
        }

    async def get_types(self, space_id: str) -> dict[str, Any]:
        """Get memory type distribution for a space."""
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=10000)
        by_type: dict[str, int] = {}
        for n in nodes:
            by_type[n.memory_type] = by_type.get(n.memory_type, 0) + 1
        return {"types": by_type, "space_id": space_id}

    async def get_audit_trail(self, space_id: str, limit: int = 50) -> dict[str, Any]:
        """Get audit trail for a space (superseded/rejected/pending_review nodes)."""
        superseded = await self._repo.query_nodes(
            domain_id=space_id, belief_status="superseded", limit=limit,
        )
        rejected = await self._repo.query_nodes(
            domain_id=space_id, belief_status="rejected", limit=limit,
        )
        pending = await self._repo.query_nodes(
            domain_id=space_id, belief_status="pending_review", limit=limit,
        )
        entries = []
        for n in superseded + rejected + pending:
            entries.append({
                "id": n.id,
                "memory_type": n.memory_type,
                "content": n.content[:200],
                "belief_status": n.belief_status,
                "superseded_by": n.superseded_by,
                "updated_at": n.updated_at,
            })
        return {"entries": entries[:limit], "space_id": space_id}

    async def run_consolidation(self, space_id: str) -> dict[str, Any]:
        """Manually trigger consolidation for a space."""
        result = await self._consolidation.run_consolidation_job(space_id)
        return {
            "created": result.created,
            "updated": result.updated,
            "deleted": result.deleted,
            "errors": result.errors,
            "space_id": space_id,
        }

    async def run_forgetting(self, space_id: str, days_elapsed: int = 1) -> dict[str, Any]:
        """Manually trigger forgetting for a space."""
        result = await self._forgetting.apply_forgetting(space_id, days_elapsed=days_elapsed)
        return {
            "result": result,
            "space_id": space_id,
            "days_elapsed": days_elapsed,
        }

    async def dream(self, space_id: str) -> dict[str, Any]:
        """Run a full dream cycle for a space.

        Dream cycle performs 5-phase maintenance:
        1. Contradiction detection
        2. Expiry check
        3. Orphan cleanup
        4. Self-link enhancement
        5. Graph completion

        Args:
            space_id: Space to maintain.

        Returns:
            Dict with phase outcomes.
        """
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

    async def approve_memory(
        self,
        node_id: str,
        action: str = "approve",
        modifier_id: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Approve, reject, or modify a pending_review memory (Human-in-the-loop).

        Design §13.2 - Three-zone model (track A/B/review zone) API support.

        Args:
            node_id: The node ID to act on.
            action: One of "approve", "reject", "modify".
            modifier_id: Identifier of the human modifier.
            comment: Optional comment for audit trail.
        """
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

        return self._make_response(
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
        return self._make_response(
            data={"space_id": space_id, "updated": True},
            space_id=space_id,
        )

    async def correct_memory(
        self,
        node_id: str,
        corrected_text: str,
        reason: str = "",
        user_id: str = "system",
        auto_consolidate: bool = True,
    ) -> dict[str, Any]:
        old_node = await self._repo.get_node(node_id)
        if not old_node:
            raise CognitiveNodeNotFoundError(node_id)

        effective_space_id = old_node.space_id

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
            from ontology_engine.engine.cognitive.models import CognitiveEdge
            await self._repo.create_cognitive_edge(CognitiveEdge(
                edge_type="SUPERSEDES",
                from_id=new_node_id,
                to_id=node_id,
                properties={"reason": reason or "corrected"},
            ))
        except Exception as e:
            logger.warning("Failed to create SUPERSEDES edge: %s", e)

        if hasattr(self, "_forgetting") and self._forgetting and hasattr(self._forgetting, "apply_strategic_forgetting"):
            await self._forgetting.apply_strategic_forgetting(node_id, "superseded")

        if hasattr(self, "_correction_propagation") and self._correction_propagation and hasattr(self._correction_propagation, "propagate"):
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

        if auto_consolidate:
            await self._consolidation.maybe_trigger_consolidation(
                effective_space_id, trigger="correction",
            )

        return self._make_response(
            data={"new_node_id": new_node_id, "old_node_id": node_id},
            space_id=effective_space_id,
        )

    async def _execute_reflect(
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

        arbitration_results = []
        if reflect_result.contradictions:
            from ontology_engine.engine.cognitive.arbitration_engine import ArbitrationEngine
            arb_engine = ArbitrationEngine(repository=self._repo)
            for c in reflect_result.contradictions:
                if len(c.node_ids) >= 2:
                    try:
                        arb_result = await arb_engine.arbitrate(
                            node_ids=c.node_ids,
                            contradiction_type=c.contradiction_type,
                        )
                        if not arb_result.needs_manual_review:
                            apply_result = await arb_engine.apply_arbitration(arb_result)
                            arbitration_results.append({
                                "winner_id": arb_result.winner_id,
                                "loser_id": arb_result.loser_id,
                                "action": arb_result.action,
                                "applied": apply_result.get("applied", False),
                            })
                        else:
                            arbitration_results.append({
                                "needs_manual_review": True,
                                "reason": arb_result.reason,
                            })
                    except Exception as e:
                        logger.debug("Arbitration failed for contradiction: %s", e)

        belief_revisions = []
        for c in reflect_result.contradictions:
            already_arbitrated = any(
                ar.get("loser_id") in c.node_ids and ar.get("applied")
                for ar in arbitration_results
            )
            if already_arbitrated:
                continue
            for node_id in c.node_ids:
                try:
                    revision = await self._apply_belief_revision_rules(node_id, c)
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

        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.BELIEF_REVISION.value, "completed"
            )

        consolidation_result = None
        if reflect_result.consolidation_requests and not req.skip_consolidation:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CONSOLIDATION.value, "in_progress"
                )
            try:
                total_created = 0
                total_updated = 0
                total_deleted = 0
                total_errors = 0
                for req_space in reflect_result.consolidation_requests:
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
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CONSOLIDATION.value, "completed"
                )
        elif req.skip_consolidation:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CONSOLIDATION.value, "completed"
                )

        forgetting_result = None
        if reflect_result.forgetting_requests and not req.skip_forgetting:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.FORGETTING.value, "in_progress"
                )
            try:
                applied = await self._forgetting.apply_forgetting(req.space_id)
                forgetting_result = applied
            except Exception as e:
                logger.warning("Forgetting during reflect failed: %s", e)
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.FORGETTING.value, "completed"
                )
        elif req.skip_forgetting:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.FORGETTING.value, "completed"
                )

        propagation_result = None
        if not req.skip_correction_propagation and self._correction_propagation is not None:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CORRECTION_PROPAGATION.value, "in_progress"
                )
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
        else:
            if job and job.progress:
                await self._job_store.update_progress(
                    job.reflection_id, ReflectionPhase.CORRECTION_PROPAGATION.value, "completed"
                )

        if job and job.progress:
            await self._job_store.update_progress(
                job.reflection_id, ReflectionPhase.SCHEMA_SUGGESTION.value, "completed"
            )

        return self._make_response(
            data={
                "insights": [
                    {
                        "text": i.text,
                        "type": "new_insight",
                        "memory_id": self._generate_memory_id(i.text, req.space_id, i.suggested_memory_type),
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
                    {
                        "model_id": u.model_id,
                        "action": u.update_type,
                    }
                    for u in reflect_result.mental_model_updates
                ],
                "iterations_used": reflect_result.iterations_used if hasattr(reflect_result, "iterations_used") and reflect_result.iterations_used else 1,
                "tokens_used": reflect_result.tokens_used if hasattr(reflect_result, "tokens_used") and reflect_result.tokens_used else 0,
            },
            space_id=req.space_id,
        )

    async def _run_reflect_background(self, job: ReflectionJob) -> None:
        try:
            req = ReflectRequest(
                query=job.query,
                space_id=job.space_id,
                max_iterations=job.max_iterations,
                focus_types=job.focus_types,
                skip_consolidation=job.skip_consolidation,
                skip_forgetting=job.skip_forgetting,
                cascade_depth=job.cascade_depth,
                skip_correction_propagation=job.skip_correction_propagation,
            )
            result = await self._execute_reflect(req, job)
            await self._job_store.set_partial_results(job.reflection_id, "final_result", result)
        except Exception as e:
            await self._job_store.set_error(job.reflection_id, str(e))

    def _generate_memory_id(self, content: str, space_id: str, memory_type: str) -> str:
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"mem:{memory_type}:{space_id}:{content_hash}"

    async def get_node(self, space_id: str, node_id: str) -> dict[str, Any]:
        """Get a cognitive node by ID.

        Args:
            space_id: Space ID.
            node_id: Node ID.

        Returns:
            Node data dictionary.

        Raises:
            CognitiveNodeNotFoundError: If node doesn't exist.
        """
        node = await self._repo.get_node(node_id)
        return {
            "id": node.id,
            "memory_type": node.memory_type,
            "cognitive_layer": node.cognitive_layer,
            "content": node.content,
            "belief_status": node.belief_status,
            "confidence": node.confidence,
            "visibility": node.visibility,
            "created_by": node.created_by,
            "space_id": node.space_id,
            "tags": node.tags,
            "attributes": node.attributes,
            "schema_ref": node.schema_ref,
            "occurred_at": node.occurred_at,
            "recorded_at": node.recorded_at,
            "valid_from": node.valid_from,
            "valid_to": node.valid_to,
            "superseded_by": node.superseded_by,
            "source_fragment_ids": node.source_fragment_ids,
            "confirmation_count": node.confirmation_count,
            "strength": node.strength,
            "entity_name": node.entity_name,
            "entity_type": node.entity_type,
            "version": node.version,
            "last_confirmed_at": node.last_confirmed_at,
            "consolidation_reasoning": node.consolidation_reasoning,
            "compiled_at": node.compiled_at,
            "source_trust_tier": node.source_trust_tier,
            "scope": node.scope,
            "source_pipeline": node.source_pipeline,
            "source_content_hash": node.source_content_hash,
            "access_count": node.access_count,
            "last_access_at": node.last_access_at,
            "consolidated_at": node.consolidated_at,
            "domain_id": node.domain_id,
            "feedback_weight": node.feedback_weight,
            "proof_count": node.proof_count,
            "ttl_seconds": node.ttl_seconds,
        }

    async def list_nodes(
        self,
        space_id: str,
        memory_type: str | None = None,
        belief_status: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """List cognitive nodes for a space.

        Args:
            space_id: Space ID.
            memory_type: Optional memory type filter.
            belief_status: Optional belief status filter.
            limit: Maximum number of nodes to return.

        Returns:
            Dict with nodes list and space_id.
        """
        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            memory_type=memory_type,
            belief_status=belief_status,
            limit=limit,
        )
        results = []
        for n in nodes:
            strength_info = self._compute_strength(n)
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
        return {"nodes": results, "total": len(results), "space_id": space_id}

    async def list_my_memories(
        self,
        space_id: str,
        user_id: str,
        scope_type: str | None = None,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                memory_type=memory_type,
                limit=10000,
            )
            filtered = [n for n in nodes if n.created_by == user_id]
            if scope_type:
                filtered = [n for n in filtered if getattr(n, "scope", None) == scope_type]
            filtered = filtered[:limit]
            results = []
            for n in filtered:
                strength_info = self._compute_strength(n)
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
            return self._make_response(
                data={"nodes": results, "total": len(results), "space_id": space_id},
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("list_my_memories failed: %s", e)
            return self._make_response(
                data={"nodes": [], "total": 0, "space_id": space_id},
                space_id=space_id,
            )

    async def record_commitment(
        self,
        content: str,
        space_id: str,
        deadline: str | None = None,
        task_id: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        try:
            node_id = self._generate_memory_id(content, space_id, "commitment")
            cognitive_layer = self._infer_cognitive_layer("commitment")

            attributes: dict[str, str] = {}
            if deadline:
                attributes["deadline"] = deadline
            if task_id:
                attributes["task_id"] = task_id

            node = CognitiveNode(
                id=node_id,
                memory_type="commitment",
                cognitive_layer=cognitive_layer,
                content=content,
                domain_id=space_id,
                space_id=space_id,
                visibility="shared",
                created_by=created_by,
                confidence=1.0,
                belief_status="accepted",
                tags={"model": "task"},
                attributes=attributes,
                source_fragment_ids=[],
                proof_count=1,
            )
            await self._repo.create_node(node)
            return self._make_response(
                data={
                    "memory_id": node_id,
                    "node_id": node_id,
                    "commitment_id": node_id,
                    "decision": "accepted",
                    "space_id": space_id,
                },
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("record_commitment failed: %s", e)
            return self._make_response(
                data={"memory_id": None, "error": str(e), "space_id": space_id},
                space_id=space_id,
            )

    async def check_commitments(
        self,
        space_id: str,
        status: str | None = None,
        overdue: bool = False,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                memory_type="commitment",
                limit=500,
            )
            now = datetime.now(timezone.utc)
            results = []
            for n in nodes:
                n_status = getattr(n, "belief_status", "accepted")
                if status and n_status != status:
                    continue
                n_deadline = n.attributes.get("deadline") if n.attributes else None
                is_overdue = False
                if n_deadline:
                    try:
                        dl = datetime.fromisoformat(str(n_deadline).replace("Z", "+00:00"))
                        is_overdue = dl < now
                    except (ValueError, TypeError):
                        pass
                if overdue and not is_overdue:
                    continue
                results.append({
                    "id": n.id,
                    "content": n.content,
                    "status": n_status,
                    "deadline": n_deadline,
                    "task_id": n.attributes.get("task_id") if n.attributes else None,
                    "created_by": n.created_by,
                    "is_overdue": is_overdue,
                    "created_at": n.created_at,
                })
            return self._make_response(
                data={"commitments": results, "total": len(results), "space_id": space_id},
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("check_commitments failed: %s", e)
            return self._make_response(
                data={"commitments": [], "total": 0, "space_id": space_id},
                space_id=space_id,
            )

    async def compile_entity_page(
        self,
        entity_id: str,
        space_id: str,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                limit=5000,
            )
            entity_nodes = [
                n for n in nodes
                if n.entity_name == entity_id or entity_id in n.id
            ]
            entity_node_ids = {en.id for en in entity_nodes}
            entity_names: set[str] = set()
            src_fragment_ids: set[str] = set()
            for en in entity_nodes:
                if en.entity_name:
                    entity_names.add(en.entity_name)
                for fid in (en.source_fragment_ids or []):
                    src_fragment_ids.add(fid)
            related_nodes = [
                n for n in nodes
                if n.id not in entity_node_ids and (
                    n.id in src_fragment_ids or (
                        n.entity_name and n.entity_name in entity_names
                    )
                )
            ]
            page_nodes = entity_nodes + related_nodes[:20]
            node_list = []
            for n in page_nodes:
                strength_info = self._compute_strength(n)
                node_list.append({
                    "id": n.id,
                    "memory_type": n.memory_type,
                    "text": n.content,
                    "entity_name": n.entity_name,
                    "entity_type": n.entity_type,
                    "belief_status": n.belief_status,
                    "confidence": n.confidence,
                    "strength": strength_info["value"],
                    "created_by": n.created_by,
                    "created_at": n.created_at,
                    "tags": n.tags,
                    "attributes": n.attributes,
                })
            return self._make_response(
                data={
                    "entity_id": entity_id,
                    "nodes": node_list,
                    "total_nodes": len(node_list),
                    "entity_node_count": len(entity_nodes),
                    "related_node_count": len(related_nodes[:20]),
                    "space_id": space_id,
                },
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("compile_entity_page failed: %s", e)
            return self._make_response(
                data={"entity_id": entity_id, "nodes": [], "total_nodes": 0, "space_id": space_id},
                space_id=space_id,
            )

    async def compile_topic_page(
        self,
        topic: str,
        entity_ids: list[str],
        space_id: str,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                limit=5000,
            )
            entity_set = set(entity_ids)
            topic_lower = topic.lower()
            topic_nodes: list[Any] = []
            for n in nodes:
                matches = False
                if n.entity_name and n.entity_name in entity_set:
                    matches = True
                elif topic_lower in (n.content or "").lower():
                    matches = True
                elif any(topic_lower in str(v).lower() for v in (n.tags or {}).values()):
                    matches = True
                if matches:
                    topic_nodes.append(n)

            topic_nodes = topic_nodes[:100]
            node_list = []
            for n in topic_nodes:
                strength_info = self._compute_strength(n)
                node_list.append({
                    "id": n.id,
                    "memory_type": n.memory_type,
                    "text": n.content,
                    "entity_name": n.entity_name,
                    "entity_type": n.entity_type,
                    "belief_status": n.belief_status,
                    "confidence": n.confidence,
                    "strength": strength_info["value"],
                    "created_by": n.created_by,
                    "created_at": n.created_at,
                    "tags": n.tags,
                    "attributes": n.attributes,
                })
            return self._make_response(
                data={
                    "topic": topic,
                    "entity_ids": entity_ids,
                    "nodes": node_list,
                    "total_nodes": len(node_list),
                    "space_id": space_id,
                },
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("compile_topic_page failed: %s", e)
            return self._make_response(
                data={"topic": topic, "entity_ids": entity_ids, "nodes": [], "total_nodes": 0, "space_id": space_id},
                space_id=space_id,
            )

    def _make_response(
        self,
        data: dict[str, Any] | None = None,
        space_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        import uuid
        from datetime import datetime, timezone

        return {
            "success": True,
            "data": data or {},
            "error": None,
            "meta": {
                "request_id": request_id or str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "space_id": space_id,
                "memory_version": "v2",
            },
        }

    async def _apply_belief_revision_rules(
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
                if eval(rule.condition, {"__builtins__": {}}, context):
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

    async def _compute_is_newer(self, node: "CognitiveNode", contradiction: "ContradictionReport") -> bool:
        """Determine if the current node is newer than the contradicting node."""
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

    @staticmethod
    def _infer_cognitive_layer(memory_type: str) -> str:
        layer_mapping = {
            "mental_model": "opinion",
            "opinion": "opinion",
            "observation": "opinion",
            "commitment": "opinion",
            "entity": "semantic",
            "rule": "semantic",
            "constraint": "semantic",
            "task_state": "semantic",
            "procedure": "procedure",
            "episode": "procedure",
            "self_experience": "perception",
            "fragment": "perception",
        }
        return layer_mapping.get(memory_type, "perception")

    @staticmethod
    def _infer_tags(memory_type: str) -> dict[str, str]:
        """Infer initial tags from memory type, replacing the removed model_domain."""
        domain_mapping: dict[str, str] = {
            "entity": "world", "rule": "world", "constraint": "world",
            "observation": "world", "fragment": "world",
            "mental_model": "self", "opinion": "self", "self_experience": "self",
            "commitment": "task", "task_state": "task", "procedure": "task", "episode": "task",
        }
        return {"model": domain_mapping.get(memory_type, "world")}

    @staticmethod
    def _compute_temporal_proximity(result: dict[str, Any]) -> float:
        import math
        from datetime import datetime, timezone

        timestamp = result.get("occurred_at") or result.get("created_at")
        if not timestamp:
            return 0.5
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days = max(0, (now - dt).total_seconds() / 86400.0)
            return math.exp(-0.05 * days)
        except (ValueError, TypeError):
            return 0.5

    @staticmethod
    def _extract_attributes(memory_type: str, metadata: dict[str, Any] | None) -> dict[str, str]:
        type_specific_keys: dict[str, list[str]] = {
            "observation": ["fact_type", "observed_at", "observer", "certainty"],
            "opinion": ["opinion_type", "sentiment", "holder", "topic", "confidence_basis", "review_required"],
            "mental_model": ["model_type", "scope", "abstraction_level"],
            "episode": ["event_type", "location", "participants", "duration"],
            "procedure": ["step_count", "domain", "difficulty", "prerequisites"],
            "entity": ["entity_name", "entity_type", "aliases"],
            "rule": ["rule_type", "scope", "priority"],
            "commitment": ["deadline", "status", "task_id", "fulfilled_by"],
            "constraint": ["constraint_type", "enforceable", "violation_action"],
            "self_experience": ["tool_name", "call_result", "latency_ms"],
            "task_state": ["task_id", "current_phase", "decision_log"],
        }
        if not metadata:
            return {}
        allowed = type_specific_keys.get(memory_type, [])
        return {k: str(v) for k, v in metadata.items() if k in allowed}

    @staticmethod
    def _determine_visibility(content: str, memory_type: str, source: str | None = None) -> str:
        if MemoryAPI._contains_personal_info(content):
            return "private"
        if memory_type in ("entity", "rule", "mental_model"):
            return "shared"
        if source == "user_input" and memory_type == "episode":
            return "private"
        return "shared"

    @staticmethod
    def _contains_personal_info(content: str) -> bool:
        patterns = [
            r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
            r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b(?:passport\s*(?:no|number|#)|ssn|social\s*security)\b",
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _compute_strength(node: CognitiveNode) -> dict[str, Any]:
        """Compute memory strength from node attributes.

        strength = recency * 0.25 + confirmation * 0.15 + evidence * 0.25
                   + feedback * 0.2 + frequency * 0.15

        Returns strength value and breakdown.
        """
        recency = 0.5
        last_access = node.last_access_at or node.updated_at or node.created_at
        if last_access:
            try:
                accessed = datetime.fromisoformat(str(last_access).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_hours = max(0, (now - accessed).total_seconds() / 3600)
                recency = max(0.0, 1.0 - (age_hours / (30 * 24)))
            except (ValueError, TypeError):
                pass

        evidence = min(1.0, len(node.source_fragment_ids) / 5.0) if isinstance(node.source_fragment_ids, list) and node.source_fragment_ids else 0.1

        feedback = node.feedback_weight

        frequency = min(1.0, node.access_count / 10.0) if node.access_count else 0.1

        confirmation = 0.1
        if hasattr(node, "proof_count") and node.proof_count:
            confirmation = min(1.0, node.proof_count / 5.0)

        strength = recency * 0.25 + confirmation * 0.15 + evidence * 0.25 + feedback * 0.2 + frequency * 0.15

        return {
            "value": round(strength, 3),
            "breakdown": {
                "recency": round(recency, 3),
                "confirmation": round(confirmation, 3),
                "evidence": round(evidence, 3),
                "feedback": round(feedback, 3),
                "access_frequency": round(frequency, 3),
            },
        }
