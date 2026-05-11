"""Memory API Routes — 9 endpoints for Agent Memory System (remember, recall, reflect, approve, reflect_status, consolidate, forget, stats, types, audit)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from ontology_engine.api.dto.responses import error_response, success_response

router = APIRouter(prefix="/v1/spaces/{space_id}/memory", tags=["memory"])


async def _get_memory_api():
    from ontology_engine.engine.cognitive.factory import MemoryAPISingleton
    return await MemoryAPISingleton.get_or_create()


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

        api = await _get_memory_api()
        result = await api.remember(
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
        return error_response(code="REMEMBER_ERROR", message=str(e))


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

        api = await _get_memory_api()
        result = await api.recall(
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
        return error_response(code="RECALL_ERROR", message=str(e))


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

        api = await _get_memory_api()
        result = await api.reflect(
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
        return error_response(code="REFLECT_ERROR", message=str(e))


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

        api = await _get_memory_api()
        result = await api.approve_memory(
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
        return error_response(code="APPROVE_ERROR", message=str(e))


@router.post("/consolidate")
async def consolidate(
    space_id: str,
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.run_consolidation(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="CONSOLIDATE_ERROR", message=str(e))


@router.post("/forget")
async def force_forget(
    space_id: str,
    request: dict[str, Any] = Body({}),
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        days_elapsed = request.get("days_elapsed", 1)
        result = await api.run_forgetting(space_id, days_elapsed=days_elapsed)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="FORGET_ERROR", message=str(e))


@router.get("/stats")
async def stats(
    space_id: str,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.get_stats(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="STATS_ERROR", message=str(e))


@router.get("/types")
async def types_list(
    space_id: str,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.get_types(space_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="TYPES_ERROR", message=str(e))


@router.get("/audit")
async def audit(
    space_id: str,
    limit: int = 50,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.get_audit_trail(space_id, limit=limit)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="AUDIT_ERROR", message=str(e))


@router.get("/nodes")
async def list_nodes(
    space_id: str,
    memory_type: str | None = None,
    belief_status: str | None = None,
    limit: int = 1000,
) -> dict[str, Any] | Any:
    """List cognitive nodes for a space."""
    try:
        api = await _get_memory_api()
        result = await api.list_nodes(
            space_id,
            memory_type=memory_type,
            belief_status=belief_status,
            limit=limit,
        )
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="LIST_NODES_ERROR", message=str(e))


@router.get("/{node_id}")
async def get_node(
    space_id: str,
    node_id: str,
) -> dict[str, Any] | Any:
    """Get a cognitive node by ID."""
    try:
        api = await _get_memory_api()
        result = await api.get_node(space_id, node_id)
        return success_response(data=result, meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="NODE_NOT_FOUND", message=str(e))
