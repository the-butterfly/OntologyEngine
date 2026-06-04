"""Memory API Routes — 10 endpoints for Agent Memory System (remember, recall, reflect, approve, reflect_status, consolidate, forget, dream, stats, types, audit)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_memory_service
from ontology_engine.api.dto.responses import error_response, success_response

router = APIRouter(prefix="/v1/spaces/{space_id}/memory", tags=["memory"])


def _is_lock_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "lock" in msg or "could not set" in msg


def _handle_error(exc: Exception, code: str) -> Any:
    if isinstance(exc, HTTPException):
        raise exc
    if _is_lock_error(exc):
        return error_response(
            code="DB_LOCK_ERROR",
            message=str(exc),
            suggestion="Another process is using the database. If using uvicorn --reload, wait a moment and retry.",
        )
    return error_response(code=code, message=str(exc))


class CorrectNodeRequest(BaseModel):
    corrected_text: str
    reason: str = ""
    user_id: str = "system"


class RememberRequest(BaseModel):
    content: str = ""
    tags: list[str] | dict[str, str | list[str]] | None = None
    memory_type: str = "fragment"
    visibility: Any = None
    auto_consolidate: bool = False
    metadata: Any = None
    created_by: Any = None
    confidence: float = 1.0
    schema_ref: Any = None
    supersede_target: Any = None
    supersede_reason: Any = None
    belief_status: str = "accepted"
    valid_from: Any = None
    valid_to: Any = None
    recorded_at: Any = None
    occurred_at: Any = None
    source_pipeline: Any = None


class RecallRequest(BaseModel):
    query: str = ""
    memory_type: Any = None
    max_results: int = 10
    include_evidence: bool = True
    evidence_depth: int = 1
    as_of: Any = None
    token_budget: Any = None
    belief_status_filter: Any = None
    audit_trail: bool = False
    user_id: Any = None
    min_confidence: float = 0.5
    disposition_override: Any = None
    cognitive_layer: Any = None
    include_superseded: bool = False


class ReflectRequest(BaseModel):
    query: str = ""
    max_iterations: int = 10
    focus_types: Any = None
    async_mode: bool = True
    skip_consolidation: bool = False
    skip_forgetting: bool = False
    cascade_depth: int = 3
    skip_correction_propagation: bool = False


class ApproveRequest(BaseModel):
    node_id: str = ""
    action: str = "approve"
    modifier_id: str = "user"
    comment: str = ""


class ConsolidateRequest(BaseModel):
    pass


class ForgetRequest(BaseModel):
    days_elapsed: int = 1


@router.post("/remember")
async def remember(
    space_id: str,
    request: RememberRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        # Convert list[str] tags to dict[str, str] format expected by MemoryAPI
        tags = request.tags
        if isinstance(tags, list):
            tags = {t: t for t in tags}
        result = await service.remember(
            content=request.content,
            space_id=space_id,
            tags=tags,
            memory_type=request.memory_type,
            visibility=request.visibility,
            auto_consolidate=request.auto_consolidate,
            metadata=request.metadata,
            created_by=request.created_by,
            confidence=request.confidence,
            schema_ref=request.schema_ref,
            supersede_target=request.supersede_target,
            supersede_reason=request.supersede_reason,
            belief_status=request.belief_status,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            recorded_at=request.recorded_at,
            occurred_at=request.occurred_at,
            source_pipeline=request.source_pipeline,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return _handle_error(e, "REMEMBER_ERROR")


@router.post("/recall")
async def recall(
    space_id: str,
    request: RecallRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.recall(
            query=request.query,
            space_id=space_id,
            memory_type=request.memory_type,
            max_results=request.max_results,
            include_evidence=request.include_evidence,
            evidence_depth=request.evidence_depth,
            as_of=request.as_of,
            token_budget=request.token_budget,
            belief_status_filter=request.belief_status_filter,
            audit_trail=request.audit_trail,
            user_id=request.user_id,
            min_confidence=request.min_confidence,
            disposition_override=request.disposition_override,
            cognitive_layer=request.cognitive_layer,
            include_superseded=request.include_superseded,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return _handle_error(e, "RECALL_ERROR")


@router.post("/reflect")
async def reflect(
    space_id: str,
    request: ReflectRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.reflect(
            query=request.query,
            space_id=space_id,
            max_iterations=request.max_iterations,
            focus_types=request.focus_types,
            async_mode=request.async_mode,
            skip_consolidation=request.skip_consolidation,
            skip_forgetting=request.skip_forgetting,
            cascade_depth=request.cascade_depth,
            skip_correction_propagation=request.skip_correction_propagation,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return _handle_error(e, "REFLECT_ERROR")


@router.post("/approve")
async def approve(
    space_id: str,
    request: ApproveRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.approve_memory(
            node_id=request.node_id,
            action=request.action,
            modifier_id=request.modifier_id,
            comment=request.comment,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return _handle_error(e, "APPROVE_ERROR")


@router.post("/consolidate")
async def consolidate(
    space_id: str,
    request: ConsolidateRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.run_consolidation(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "CONSOLIDATE_ERROR")


@router.post("/forget")
async def force_forget(
    space_id: str,
    request: ForgetRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.run_forgetting(space_id, days_elapsed=request.days_elapsed)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "FORGET_ERROR")


@router.post("/dream")
async def dream(
    space_id: str,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.dream(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "DREAM_ERROR")


@router.get("/stats")
async def stats(
    space_id: str,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.get_stats(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "STATS_ERROR")


@router.get("/types")
async def types_list(
    space_id: str,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.get_types(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "TYPES_ERROR")


@router.get("/audit")
async def audit(
    space_id: str,
    limit: int = 50,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.get_audit_trail(space_id, limit=limit)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "AUDIT_ERROR")


@router.get("/reflect-status")
async def reflect_status(
    space_id: str,
    reflection_id: str,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.get_reflection_status(reflection_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "REFLECT_STATUS_ERROR")


@router.get("/contradictions")
async def contradictions(
    space_id: str,
    limit: int = 50,
    severity: str | None = None,
) -> dict[str, Any] | Any:
    """Get contradictions for a space."""
    try:
        service = get_memory_service()
        result = await service.list_nodes(
            space_id,
            belief_status="contradicted",
            limit=limit,
        )
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "CONTRADICTIONS_ERROR")


@router.get("/corrections")
async def corrections(
    space_id: str,
    limit: int = 50,
) -> dict[str, Any] | Any:
    """Get corrections for a space."""
    try:
        service = get_memory_service()
        result = await service.list_nodes(
            space_id,
            belief_status="superseded",
            limit=limit,
        )
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "CORRECTIONS_ERROR")


@router.get("/nodes")
async def list_nodes(
    space_id: str,
    memory_type: str | None = None,
    belief_status: str | None = None,
    limit: int = 1000,
) -> dict[str, Any] | Any:
    """List cognitive nodes for a space."""
    try:
        service = get_memory_service()
        result = await service.list_nodes(
            space_id,
            memory_type=memory_type,
            belief_status=belief_status,
            limit=limit,
        )
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "LIST_NODES_ERROR")


@router.get("/edges")
async def list_edges(
    space_id: str,
    edge_type: str | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    limit: int = 500,
) -> dict[str, Any] | Any:
    """List cognitive edges for a space."""
    try:
        service = get_memory_service()
        result = await service.list_edges(
            space_id,
            edge_type=edge_type,
            from_id=from_id,
            to_id=to_id,
            limit=limit,
        )
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "LIST_EDGES_ERROR")


@router.get("/graph")
async def get_memory_graph(
    space_id: str,
    memory_type: str | None = None,
    belief_status: str | None = None,
    edge_type: str | None = None,
    node_limit: int = 500,
    edge_limit: int = 500,
) -> dict[str, Any] | Any:
    """Get complete memory graph data (nodes + edges) for visualization."""
    try:
        service = get_memory_service()
        result = await service.get_memory_graph(
            space_id,
            memory_type=memory_type,
            belief_status=belief_status,
            edge_type=edge_type,
            node_limit=node_limit,
            edge_limit=edge_limit,
        )
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return _handle_error(e, "MEMORY_GRAPH_ERROR")


@router.get("/{node_id}")
async def get_node(
    space_id: str,
    node_id: str,
) -> dict[str, Any] | Any:
    """Get a cognitive node by ID."""
    try:
        service = get_memory_service()
        result = await service.get_node(space_id, node_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        service = get_memory_service()
        if service.is_node_not_found_error(e):
            return error_response(code="NODE_NOT_FOUND", message=str(e))
        return error_response(code="GET_NODE_ERROR", message=str(e))


@router.get("/{node_id}/evidence")
async def get_evidence(
    space_id: str,
    node_id: str,
    depth: int = 1,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.get_evidence(space_id, node_id, depth=depth)
        return success_response(data=result.get("data", result), meta={"space_id": space_id})
    except Exception as e:
        service = get_memory_service()
        if service.is_node_not_found_error(e):
            return error_response(code="NODE_NOT_FOUND", message=str(e))
        return _handle_error(e, "EVIDENCE_ERROR")


@router.patch("/{node_id}/correct")
async def correct_node(
    space_id: str,
    node_id: str,
    request: CorrectNodeRequest,
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        result = await service.correct_node(
            space_id=space_id,
            node_id=node_id,
            corrected_text=request.corrected_text,
            reason=request.reason,
            user_id=request.user_id,
        )
        return success_response(data=result.get("data", result), meta={"space_id": space_id})
    except Exception as e:
        service = get_memory_service()
        if service.is_node_not_found_error(e):
            return error_response(code="NODE_NOT_FOUND", message=str(e))
        return _handle_error(e, "CORRECT_ERROR")
