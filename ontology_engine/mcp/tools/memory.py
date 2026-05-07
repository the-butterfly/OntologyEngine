"""Memory MCP tools — oe_remember, oe_recall, oe_reflect, etc."""

from typing import Any

from ontology_engine.mcp import mcp_response


async def _get_memory_api():
    from ontology_engine.engine.cognitive.factory import MemoryAPISingleton
    return await MemoryAPISingleton.get_or_create()


async def oe_remember(
    content: str,
    space_id: str,
    tags: list[str] | None = None,
    memory_type: str = "fragment",
    metadata: dict[str, Any] | None = None,
    auto_consolidate: bool = False,
    visibility: str | None = None,
    created_by: str | None = None,
    confidence: float = 1.0,
    supersede_target: str | None = None,
    supersede_reason: str | None = None,
    schema_ref: str | None = None,
    belief_status: str = "accepted",
    valid_from: str | None = None,
    valid_to: str | None = None,
    occurred_at: str | None = None,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.remember(
            content=content,
            space_id=space_id,
            tags=tags,
            memory_type=memory_type,
            metadata=metadata,
            auto_consolidate=auto_consolidate,
            visibility=visibility,
            created_by=created_by,
            confidence=confidence,
            supersede_target=supersede_target,
            supersede_reason=supersede_reason,
            schema_ref=schema_ref,
            belief_status=belief_status,
            valid_from=valid_from,
            valid_to=valid_to,
            occurred_at=occurred_at,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "REMEMBER_ERROR", "message": str(e)},
        )


async def oe_recall(
    query: str,
    space_id: str,
    memory_type: str | None = None,
    max_results: int = 10,
    include_evidence: bool = True,
    evidence_depth: int = 1,
    as_of: str | None = None,
    token_budget: int | None = None,
    disposition_override: str | None = None,
    belief_status_filter: str | None = None,
    min_confidence: float = 0.5,
    cognitive_layer: str | None = None,
    include_superseded: bool = False,
    audit_trail: bool = False,
) -> dict:
    try:
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
            disposition_override=disposition_override,
            belief_status_filter=belief_status_filter,
            min_confidence=min_confidence,
            cognitive_layer=cognitive_layer,
            include_superseded=include_superseded,
            audit_trail=audit_trail,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "RECALL_ERROR", "message": str(e)},
        )


async def oe_reflect(
    query: str,
    space_id: str,
    max_iterations: int = 10,
    focus_types: list[str] | None = None,
    async_mode: bool = True,
    skip_consolidation: bool = False,
    skip_forgetting: bool = False,
    cascade_depth: int = 3,
    skip_correction_propagation: bool = False,
) -> dict:
    try:
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
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "REFLECT_ERROR", "message": str(e)},
        )


async def oe_approve_memory(
    node_id: str,
    action: str = "approve",
    modifier_id: str = "user",
    comment: str = "",
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.approve_memory(
            node_id=node_id,
            action=action,
            modifier_id=modifier_id,
            comment=comment,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "APPROVE_ERROR", "message": str(e)},
        )


async def oe_consolidate(
    space_id: str,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.run_consolidation(space_id)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "CONSOLIDATE_ERROR", "message": str(e)},
        )


async def oe_forget(
    space_id: str,
    days_elapsed: int = 1,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.run_forgetting(space_id, days_elapsed=days_elapsed)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "FORGET_ERROR", "message": str(e)},
        )


async def oe_memory_stats(
    space_id: str,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.get_stats(space_id)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "STATS_ERROR", "message": str(e)},
        )


async def oe_get_reflection_status(
    reflection_id: str,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.get_reflection_status(reflection_id)
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "REFLECTION_STATUS_ERROR", "message": str(e)},
        )


async def oe_memory_types(
    space_id: str,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.get_types(space_id)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "TYPES_ERROR", "message": str(e)},
        )


async def oe_audit_trail(
    space_id: str,
    limit: int = 50,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.get_audit_trail(space_id, limit=limit)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "AUDIT_ERROR", "message": str(e)},
        )


async def oe_correct_memory(
    node_id: str,
    corrected_text: str,
    reason: str = "",
    user_id: str = "mcp_user",
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.correct_memory(
            node_id=node_id,
            corrected_text=corrected_text,
            reason=reason,
            user_id=user_id,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "CORRECT_ERROR", "message": str(e)},
        )


async def oe_delete_memory(
    node_id: str,
    space_id: str,
    cascade: bool = False,
    user_id: str = "mcp_user",
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.delete_memory(
            node_id=node_id,
            space_id=space_id,
            cascade=cascade,
            user_id=user_id,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "DELETE_ERROR", "message": str(e)},
        )


async def oe_list_my_memories(
    space_id: str,
    user_id: str,
    scope_type: str | None = None,
    memory_type: str | None = None,
    limit: int = 50,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.list_my_memories(
            space_id=space_id,
            user_id=user_id,
            scope_type=scope_type,
            memory_type=memory_type,
            limit=limit,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "LIST_MY_ERROR", "message": str(e)},
        )


async def oe_record_commitment(
    content: str,
    space_id: str,
    deadline: str | None = None,
    task_id: str | None = None,
    created_by: str | None = None,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.record_commitment(
            content=content,
            space_id=space_id,
            deadline=deadline,
            task_id=task_id,
            created_by=created_by,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "COMMITMENT_ERROR", "message": str(e)},
        )


async def oe_check_commitments(
    space_id: str,
    status: str | None = None,
    overdue: bool = False,
) -> dict:
    try:
        api = await _get_memory_api()
        result = await api.check_commitments(
            space_id=space_id,
            status=status,
            overdue=overdue,
        )
        return mcp_response(
            success=True,
            data=result.get("data", result),
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "CHECK_COMMITMENTS_ERROR", "message": str(e)},
        )
