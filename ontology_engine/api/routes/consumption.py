# ontology_engine/api/routes/consumption.py
from __future__ import annotations

import warnings
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.api.dependencies import get_consumption_service

warnings.warn(
    "ontology_engine.api.routes.consumption is deprecated. "
    "Use ontology_engine.api.routes.views instead.",
    DeprecationWarning,
    stacklevel=2,
)

router = APIRouter(prefix="/v1", tags=["Consumption"])


class ExecuteAnalyzeRequest(BaseModel):
    entity_id: str
    dimension: str = "credit_assessment"
    include_trace: bool = True


class ExecuteSimulateRequest(BaseModel):
    entity_id: str
    dimension: str = "credit_assessment"
    overrides: dict[str, Any] | None = None
    include_trace: bool = True


@router.get("/views", response_model=dict)
async def list_views():
    service = get_consumption_service()
    views = await service.list_views()
    return success_response(data=views)


@router.get("/views/{view_id}", response_model=dict)
async def get_view(view_id: str):
    service = get_consumption_service()
    result = await service.get_view(view_id)
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    return success_response(data=result)


@router.get("/views/{view_id}/entities", response_model=dict)
async def list_view_entities(
    view_id: str,
    concept: str | None = Query(default=None),
):
    service = get_consumption_service()
    result = await service.list_view_entities(view_id, concept)
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    return success_response(data=result)


@router.get("/views/{view_id}/schema-graph", response_model=dict)
async def get_schema_graph(
    view_id: str,
    graph_type: str = Query(default="entity_relation"),
    layer_filter: str | None = Query(default=None),
):
    service = get_consumption_service()
    result = await service.get_schema_graph(view_id, graph_type, layer_filter)
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    return success_response(data=result)


@router.get("/views/{view_id}/rules/dependency-graph", response_model=dict)
async def get_rule_dependency_graph(view_id: str):
    service = get_consumption_service()
    result = await service.get_rule_dependency_graph(view_id)
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    return success_response(data=result)


@router.get("/views/{view_id}/rules/for-entity/{entity_id}", response_model=dict)
async def get_rules_for_entity(
    view_id: str,
    entity_id: str,
    dimension: str | None = Query(default=None),
):
    service = get_consumption_service()
    result = await service.get_rules_for_entity(view_id, entity_id, dimension)
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    if isinstance(result, dict) and result.get("error") == "entity_not_found":
        return error_response(code="NOT_FOUND", message=f"Entity {entity_id} not found")
    return success_response(data=result)


@router.get("/views/{view_id}/metrics/{entity_id}/snapshot", response_model=dict)
async def get_metric_snapshot(
    view_id: str,
    entity_id: str,
    dimension: str = Query(default="credit_assessment"),
):
    service = get_consumption_service()
    result = await service.get_metric_snapshot(view_id, entity_id, dimension)
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    if isinstance(result, dict) and result.get("error") == "entity_not_found":
        return error_response(code="NOT_FOUND", message=f"Entity {entity_id} not found")
    return success_response(data=result)


@router.post("/views/{view_id}/execute/analyze", response_model=dict)
async def execute_analyze(view_id: str, request: ExecuteAnalyzeRequest):
    service = get_consumption_service()
    result = await service.execute_analyze(
        view_id, request.entity_id, request.dimension, request.include_trace
    )
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    if isinstance(result, dict) and result.get("error") == "entity_not_found":
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")
    return success_response(data=result)


@router.post("/views/{view_id}/execute/simulate", response_model=dict)
async def execute_simulate(view_id: str, request: ExecuteSimulateRequest):
    service = get_consumption_service()
    result = await service.execute_simulate(
        view_id, request.entity_id, request.dimension,
        request.overrides, request.include_trace
    )
    if result is None:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found", suggestion="Use GET /v1/views to list available views")
    if isinstance(result, dict) and result.get("error") == "entity_not_found":
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")
    return success_response(data=result)
