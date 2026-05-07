"""Memory API Routes — endpoints for Agent Memory System.

Route ordering rule: STATIC paths must be defined BEFORE dynamic /{node_id} paths,
to prevent FastAPI from matching static segments (e.g. "my", "build") as node_ids.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from ontology_engine.api.dto.responses import error_response, success_response

router = APIRouter(prefix="/v1/spaces/{space_id}/memory", tags=["memory"])


async def _get_memory_api():
    from ontology_engine.engine.cognitive.factory import MemoryAPISingleton
    return await MemoryAPISingleton.get_or_create()


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  POST endpoints (all static)
# ═══════════════════════════════════════════════════════════════════════════════

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


@router.post("/commitments")
async def record_commitment(
    space_id: str,
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        content = request.get("content", "")
        deadline = request.get("deadline")
        task_id = request.get("task_id")
        created_by = request.get("created_by")

        api = await _get_memory_api()
        result = await api.record_commitment(
            content=content,
            space_id=space_id,
            deadline=deadline,
            task_id=task_id,
            created_by=created_by,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="COMMITMENT_ERROR", message=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  GET endpoints — STATIC paths first
# ═══════════════════════════════════════════════════════════════════════════════

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


@router.get("/my")
async def list_my(
    space_id: str,
    user_id: str = "",
    scope_type: str | None = None,
    memory_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.list_my_memories(
            space_id=space_id,
            user_id=user_id,
            scope_type=scope_type,
            memory_type=memory_type,
            limit=limit,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="LIST_MY_ERROR", message=str(e))


@router.get("/commitments")
async def check_commitments(
    space_id: str,
    status: str | None = None,
    overdue: bool = False,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.check_commitments(
            space_id=space_id,
            status=status,
            overdue=overdue,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="CHECK_COMMITMENTS_ERROR", message=str(e))


@router.get("/contradictions")
async def contradictions(
    space_id: str,
    severity: str | None = None,
    limit: int = 50,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        edges = await api._repo.query_cognitive_edges(
            edge_type="CONTRADICTS",
            limit=limit,
        )
        items = []
        for e in edges:
            item = {
                "source_id": e.from_id,
                "target_id": e.to_id,
                "edge_type": e.edge_type,
            }
            if e.properties:
                item["contradiction_type"] = e.properties.get("contradiction_type")
                item["severity"] = e.properties.get("severity")
            if e.created_at:
                item["created_at"] = e.created_at
            if severity and item.get("severity") != severity:
                continue
            items.append(item)
        return success_response(
            data=items,
            meta={"space_id": space_id, "total": len(items)}
        )
    except Exception as e:
        return error_response(code="CONTRADICTIONS_ERROR", message=str(e))


@router.get("/corrections")
async def corrections(
    space_id: str,
    limit: int = 50,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        edges = await api._repo.query_cognitive_edges(
            edge_type="SUPERSEDES",
            limit=limit,
        )
        items = []
        for e in edges:
            item = {
                "old_id": e.from_id,
                "new_id": e.to_id,
                "edge_type": e.edge_type,
            }
            if e.properties:
                item["reason"] = e.properties.get("reason")
                item["modifier_id"] = e.properties.get("modifier_id")
            if e.created_at:
                item["superseded_at"] = e.created_at
            items.append(item)
        return success_response(
            data=items,
            meta={"space_id": space_id, "total": len(items)}
        )
    except Exception as e:
        return error_response(code="CORRECTIONS_ERROR", message=str(e))


@router.put("/disposition")
async def put_disposition(
    space_id: str,
    body: dict = Body(...),
) -> dict[str, Any] | Any:
    try:
        from ontology_engine.engine.cognitive.disposition_store import get_disposition_store
        from ontology_engine.engine.cognitive.models import DispositionProfile
        store = get_disposition_store()
        existing = store.get(space_id)
        profile = DispositionProfile(
            id=existing.id,
            scene=body.get("scene", existing.scene),
            skepticism=body.get("skepticism", existing.skepticism),
            evidence_demand=body.get("evidence_demand", existing.evidence_demand),
            abstraction_preference=body.get("abstraction_preference", existing.abstraction_preference),
            thoroughness=body.get("thoroughness", existing.thoroughness),
            recency_bias=body.get("recency_bias", existing.recency_bias),
            empathy=body.get("empathy", existing.empathy),
            risk_tolerance=body.get("risk_tolerance", existing.risk_tolerance),
            space_id=space_id,
        )
        store.save(space_id, profile)
        return success_response(data=store.to_dict(space_id), meta={"space_id": space_id})
    except Exception as e:
        return error_response(code="DISPOSITION_PUT_ERROR", message=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# 3.  GET /{node_id} /evidence — DYNAMIC paths LAST
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{node_id}/evidence")
async def evidence(
    space_id: str,
    node_id: str,
    depth: int = 1,
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        node = await api._repo.get_node(node_id)
        if not node:
            return error_response(code="NOT_FOUND", message=f"Node {node_id} not found")

        fragments: list[dict[str, Any]] = []
        for fid in node.source_fragment_ids[:20]:
            try:
                frag = await api._repo.get_node(fid)
                if frag:
                    fragments.append(frag.to_dict() if hasattr(frag, "to_dict") else {"id": fid})
            except Exception:
                fragments.append({"id": fid})

        supporting_edges = await api._repo.query_cognitive_edges(
            to_id=node_id,
            edge_type="COG_SUPPORTED_BY",
            limit=20,
        )
        supporting_ids = [e.from_id for e in supporting_edges]
        supporting_nodes = []
        for sid in supporting_ids:
            try:
                sn = await api._repo.get_node(sid)
                if sn:
                    supporting_nodes.append(sn.to_dict() if hasattr(sn, "to_dict") else {"id": sid})
            except Exception:
                supporting_nodes.append({"id": sid})

        consolidated_edges = await api._repo.query_cognitive_edges(
            from_id=node_id,
            edge_type="CONSOLIDATED_INTO",
            limit=10,
        )

        return success_response(
            data={
                "node_id": node_id,
                "source_fragments": fragments,
                "supporting_nodes": supporting_nodes,
                "consolidated_into": [
                    {"target_id": e.to_id, "edge_type": e.edge_type}
                    for e in consolidated_edges
                ],
            },
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="EVIDENCE_ERROR", message=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  PATCH /{node_id}/correct — DYNAMIC path
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{node_id}/correct")
async def correct(
    space_id: str,
    node_id: str,
    request: dict[str, Any],
) -> dict[str, Any] | Any:
    try:
        corrected_text = request.get("corrected_text", "")
        reason = request.get("reason", "")
        user_id = request.get("user_id", "api_user")

        api = await _get_memory_api()
        result = await api.correct_memory(
            node_id=node_id,
            corrected_text=corrected_text,
            reason=reason,
            user_id=user_id,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="CORRECT_ERROR", message=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  DELETE /{node_id} — DYNAMIC path
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{node_id}")
async def delete(
    space_id: str,
    node_id: str,
    cascade: bool = False,
    user_id: str = "api_user",
) -> dict[str, Any] | Any:
    try:
        api = await _get_memory_api()
        result = await api.delete_memory(
            node_id=node_id,
            space_id=space_id,
            cascade=cascade,
            user_id=user_id,
        )
        return success_response(
            data=result.get("data", result),
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="DELETE_ERROR", message=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  GET /{node_id} — MOST GENERIC DYNAMIC path LAST
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{node_id}")
async def get_node(
    space_id: str,
    node_id: str,
) -> dict[str, Any] | Any:
    """Get a single memory node by ID."""
    try:
        api = await _get_memory_api()
        node = await api._repo.get_node(node_id)
        if not node:
            return error_response(code="NOT_FOUND", message=f"Node {node_id} not found")
        return success_response(
            data=node.to_dict() if hasattr(node, "to_dict") else node,
            meta={"space_id": space_id}
        )
    except Exception as e:
        return error_response(code="GET_NODE_ERROR", message=str(e))
