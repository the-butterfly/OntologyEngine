"""Memory API Routes — 10 endpoints for Agent Memory System (remember, recall, reflect, approve, reflect_status, consolidate, forget, dream, stats, types, audit)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from ontology_engine.api.dependencies import get_memory_service
from ontology_engine.api.dto.responses import error_response, success_response

router = APIRouter(prefix="/v1/spaces/{space_id}/memory", tags=["memory"])


def _is_lock_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "lock" in msg or "could not set" in msg


def _handle_error(exc: Exception, code: str) -> Any:
    if _is_lock_error(exc):
        return error_response(
            code="DB_LOCK_ERROR",
            message=str(exc),
            suggestion="Another process is using the database. If using uvicorn --reload, wait a moment and retry.",
        )
    return error_response(code=code, message=str(exc))


@router.post("/remember")
async def remember(
    space_id: str,
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        content = request.get("content", "")
        tags = request.get("tags")
        memory_type = request.get("memory_type", "fragment")
        visibility = request.get("visibility")
        auto_consolidate = request.get("auto_consolidate", False)
        metadata = request.get("metadata")
        created_by = request.get("created_by")
        confidence = request.get("confidence", 1.0)
        schema_ref = request.get("schema_ref")
        supersede_target = request.get("supersede_target")
        supersede_reason = request.get("supersede_reason")
        belief_status = request.get("belief_status", "accepted")
        valid_from = request.get("valid_from")
        valid_to = request.get("valid_to")
        recorded_at = request.get("recorded_at")
        occurred_at = request.get("occurred_at")
        source_pipeline = request.get("source_pipeline")

        service = get_memory_service()
        result = await service.remember(
            content=content,
            space_id=space_id,
            tags=tags,
            memory_type=memory_type,
            visibility=visibility,
            auto_consolidate=auto_consolidate,
            metadata=metadata,
            created_by=created_by,
            confidence=confidence,
            schema_ref=schema_ref,
            supersede_target=supersede_target,
            supersede_reason=supersede_reason,
            belief_status=belief_status,
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at,
            occurred_at=occurred_at,
            source_pipeline=source_pipeline,
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
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        query = request.get("query", "")
        memory_type = request.get("memory_type")
        max_results = request.get("max_results", 10)
        include_evidence = request.get("include_evidence", True)
        evidence_depth = request.get("evidence_depth", 1)
        as_of = request.get("as_of")
        token_budget = request.get("token_budget")
        belief_status_filter = request.get("belief_status_filter")
        audit_trail = request.get("audit_trail", False)
        user_id = request.get("user_id")
        min_confidence = request.get("min_confidence", 0.5)
        disposition_override = request.get("disposition_override")
        cognitive_layer = request.get("cognitive_layer")
        include_superseded = request.get("include_superseded", False)

        service = get_memory_service()
        result = await service.recall(
            query=query,
            space_id=space_id,
            memory_type=memory_type,
            max_results=max_results,
            include_evidence=include_evidence,
            evidence_depth=evidence_depth,
            as_of=as_of,
            token_budget=token_budget,
            belief_status_filter=belief_status_filter,
            audit_trail=audit_trail,
            user_id=user_id,
            min_confidence=min_confidence,
            disposition_override=disposition_override,
            cognitive_layer=cognitive_layer,
            include_superseded=include_superseded,
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
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        query = request.get("query", "")
        max_iterations = request.get("max_iterations", 10)
        focus_types = request.get("focus_types")
        async_mode = request.get("async_mode", True)
        skip_consolidation = request.get("skip_consolidation", False)
        skip_forgetting = request.get("skip_forgetting", False)
        cascade_depth = request.get("cascade_depth", 3)
        skip_correction_propagation = request.get("skip_correction_propagation", False)

        service = get_memory_service()
        result = await service.reflect(
            query=query,
            space_id=space_id,
            max_iterations=max_iterations,
            focus_types=focus_types,
            async_mode=async_mode,
            skip_consolidation=skip_consolidation,
            skip_forgetting=skip_forgetting,
            cascade_depth=cascade_depth,
            skip_correction_propagation=skip_correction_propagation,
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
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        node_id = request.get("node_id", "")
        action = request.get("action", "approve")
        modifier_id = request.get("modifier_id", "user")
        comment = request.get("comment", "")

        service = get_memory_service()
        result = await service.approve_memory(
            node_id=node_id,
            action=action,
            modifier_id=modifier_id,
            comment=comment,
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
    request: dict[str, Any],
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
    request: dict[str, Any] = Body({}),
) -> dict[str, Any] | Any:
    try:
        service = get_memory_service()
        days_elapsed = request.get("days_elapsed", 1)
        result = await service.run_forgetting(space_id, days_elapsed=days_elapsed)
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
