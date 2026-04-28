from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ontology_engine.api.dependencies import (
    get_entity_service,
    get_schema_service,
)
from ontology_engine.api.dto.responses import error_response, success_response

router = APIRouter(prefix="/v1/spaces/{space_id}/ontology", tags=["ontology"])


@router.get("/schema")
async def get_schema(
    space_id: str,
    schema_service=Depends(get_schema_service),
):
    try:
        schema = await schema_service.get_schema()
        return success_response(data=schema)
    except Exception as e:
        return error_response(code="SCHEMA_ERROR", message=str(e))


@router.put("/schema")
async def update_schema(
    space_id: str,
    request: dict[str, Any],
    schema_service=Depends(get_schema_service),
):
    try:
        schema_data = request.get("schema")
        if not schema_data:
            return error_response(code="BAD_REQUEST", message="schema data is required")
        result = await schema_service.load_schema_from_data(schema_data)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="SCHEMA_UPDATE_ERROR", message=str(e))


@router.get("/entities")
async def list_entities(
    space_id: str,
    fact_object: str | None = None,
    entity_service=Depends(get_entity_service),
):
    try:
        entities = await entity_service.query_entities(fact_object)
        return success_response(data=[
            {"entity_id": e.entity_id, "fact_object": e.fact_object, "data": e.attributes}
            for e in entities
        ])
    except Exception as e:
        return error_response(code="ENTITY_ERROR", message=str(e))


@router.post("/entities")
async def create_entity(
    space_id: str,
    request: dict[str, Any],
    entity_service=Depends(get_entity_service),
):
    try:
        fact_object = request.get("_fact_object", request.get("concept_type"))
        entity_id = request.get("entity_id")
        data = request.get("attributes", request.get("data", {}))
        if not fact_object or not entity_id:
            return error_response(code="BAD_REQUEST", message="_fact_object and entity_id are required")
        result = await entity_service.create_entity(fact_object, entity_id, data)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="ENTITY_CREATE_ERROR", message=str(e))


@router.get("/entities/{entity_id}")
async def get_entity(
    space_id: str,
    entity_id: str,
    fact_object: str | None = None,
    entity_service=Depends(get_entity_service),
):
    try:
        if fact_object:
            entity = await entity_service.get_entity(fact_object, entity_id)
        else:
            entity = await entity_service.get_entity_by_id(entity_id)
        if entity is None:
            return error_response(code="NOT_FOUND", message=f"Entity {entity_id} not found")
        return success_response(data={
            "entity_id": entity.entity_id,
            "fact_object": entity.fact_object,
            "data": entity.attributes,
        })
    except Exception as e:
        return error_response(code="ENTITY_ERROR", message=str(e))


@router.get("/relations")
async def list_relations(
    space_id: str,
    from_entity_id: str | None = None,
    relation_name: str | None = None,
    entity_service=Depends(get_entity_service),
):
    try:
        if from_entity_id:
            neighbors = await entity_service.get_neighbors(from_entity_id, relation_name)
            results = []
            for n in neighbors:
                results.append({
                    "relation_name": n.relation.relation_name,
                    "from_entity_id": from_entity_id,
                    "to_entity_id": n.entity.entity_id,
                    "data": n.relation.attributes if hasattr(n.relation, 'attributes') else {},
                })
            return success_response(data=results)
        else:
            return success_response(data=[])
    except Exception as e:
        return error_response(code="RELATION_ERROR", message=str(e))


@router.post("/relations")
async def create_relation(
    space_id: str,
    request: dict[str, Any],
    entity_service=Depends(get_entity_service),
):
    try:
        relation_name = request.get("relation_name", request.get("relation_type"))
        from_entity_id = request.get("from_entity_id")
        to_entity_id = request.get("to_entity_id")
        data = request.get("data", {})
        if not relation_name or not from_entity_id or not to_entity_id:
            return error_response(code="BAD_REQUEST", message="relation_name, from_entity_id, and to_entity_id are required")
        result = await entity_service.create_relation(relation_name, from_entity_id, to_entity_id, data)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="RELATION_CREATE_ERROR", message=str(e))


@router.get("/metrics")
async def list_metrics(
    space_id: str,
    entity_id: str | None = None,
    entity_service=Depends(get_entity_service),
):
    try:
        if entity_id:
            entity = await entity_service.get_entity_by_id(entity_id)
            if entity:
                metrics = {}
                if hasattr(entity, 'attributes') and entity.attributes:
                    metrics = entity.attributes.get("metrics", {})
                return success_response(data={"entity_id": entity_id, "metrics": metrics})
            return error_response(code="NOT_FOUND", message=f"Entity {entity_id} not found")
        return success_response(data=[])
    except Exception as e:
        return error_response(code="METRIC_ERROR", message=str(e))
