from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ontology_engine.api.dependencies import (
    get_analysis_service,
    get_entity_service,
    get_feedback_service,
    get_ingestion_service,
    get_query_service,
)
from ontology_engine.api.dto.responses import error_response, success_response

router = APIRouter(prefix="/v1/spaces/{space_id}/actions", tags=["actions"])


@router.post("/ingest")
async def ingest(
    space_id: str,
    request: dict[str, Any],
    ingestion_service=Depends(get_ingestion_service),
):
    try:
        data = request.get("data", {})
        format_type = request.get("format", "yaml")
        result = await ingestion_service.ingest_structured(space_id, data, format_type)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="INGEST_ERROR", message=str(e))


@router.post("/analyze")
async def analyze(
    space_id: str,
    request: dict[str, Any],
    analysis_service=Depends(get_analysis_service),
):
    try:
        entity_id = request.get("entity_id")
        dimension = request.get("dimension")
        context = request.get("context")
        if not entity_id or not dimension:
            return error_response(code="BAD_REQUEST", message="entity_id and dimension are required")
        result = await analysis_service.execute_analysis(entity_id, dimension, context)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="ANALYSIS_ERROR", message=str(e))


@router.post("/query")
async def query(
    space_id: str,
    request: dict[str, Any],
    query_service=Depends(get_query_service),
):
    try:
        query_text = request.get("query_text", "")
        top_k = request.get("top_k", 10)
        filters = request.get("filters")
        fusion_strategy = request.get("fusion_strategy", "independent_then_fuse")
        if filters:
            result = await query_service.query_hybrid(query_text, filters, fusion_strategy)
        else:
            result = await query_service.query_raw(query_text, top_k)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/feedback")
async def feedback(
    space_id: str,
    request: dict[str, Any],
    feedback_svc=Depends(get_feedback_service),
):
    try:
        entity_id = request.get("entity_id")
        feedback_type = request.get("feedback_type", "confirm")
        value = request.get("value", 1.0)
        metric_name = request.get("metric_name")
        text_feedback = request.get("text_feedback")

        record = await feedback_svc.submit_feedback(
            entity_id=entity_id,
            feedback_type=feedback_type,
            value=value,
            metric_name=metric_name,
            text_feedback=text_feedback,
        )
        await feedback_svc.apply_feedback(entity_id, metric_name)
        return success_response(data={
            "record_id": record.record_id,
            "entity_id": record.entity_id,
            "feedback_type": record.feedback_type,
            "updated_weight": record.updated_weight,
        })
    except Exception as e:
        return error_response(code="FEEDBACK_ERROR", message=str(e))


@router.post("/export")
async def export_data(
    space_id: str,
    request: dict[str, Any],
    entity_service=Depends(get_entity_service),
):
    try:
        fact_object = request.get("fact_object")
        format_type = request.get("format", "json")
        entities = await entity_service.query_entities(fact_object)
        return success_response(data={
            "space_id": space_id,
            "entities": [{"entity_id": e.entity_id, "fact_object": e.fact_object, "data": e.attributes} for e in entities],
            "count": len(entities),
            "format": format_type,
        })
    except Exception as e:
        return error_response(code="EXPORT_ERROR", message=str(e))
