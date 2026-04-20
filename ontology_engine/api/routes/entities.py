# ontology_engine/api/routes/entities.py
"""Entity management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_entity_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.entity_service import EntityService
from ontology_engine.services.dto import (
    EntityCreateRequest,
    ConceptNotDefinedError,
)

router = APIRouter(prefix="/v1/entities", tags=["Entities"])


class EntityCreateRequestBody(BaseModel):
    """Request body for entity creation."""
    fact_object: str
    entity_id: str
    attributes: dict[str, Any] | None = None


class EntityQueryRequestBody(BaseModel):
    """Request body for entity query."""
    fact_object: str | None = None
    filter: dict[str, Any] | None = None
    limit: int = 100
    offset: int = 0


@router.post("")
async def create_entity(
    body: EntityCreateRequestBody,
    service: EntityService = Depends(get_entity_service)
):
    """Create a new entity.

    Args:
        body: Entity creation request

    Returns:
        Created EntityResponse
    """
    try:
        result = await service.create_entity(
            fact_object=body.fact_object,
            entity_id=body.entity_id,
            attributes=body.attributes
        )
        response = success_response(data=result)
        return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/spaces/{space_id}/instances/entities instead."})
    except ConceptNotDefinedError as e:
        return error_response(code="CONCEPT_NOT_FOUND", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/batch")
async def batch_create_entities(
    bodies: list[EntityCreateRequestBody],
    service: EntityService = Depends(get_entity_service)
):
    """Batch create entities.

    Args:
        bodies: List of entity creation requests

    Returns:
        BatchOperationResult
    """
    requests = [
        EntityCreateRequest(
            fact_object=b.fact_object,
            entity_id=b.entity_id,
            attributes=b.attributes
        )
        for b in bodies
    ]
    result = await service.batch_create(requests)
    response = success_response(data=result)
    return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/spaces/{space_id}/instances/entities instead."})


@router.get("/{entity_id}")
async def get_entity(
    entity_id: str,
    fact_object: str | None = None,
    service: EntityService = Depends(get_entity_service)
):
    """Get entity by ID.

    Args:
        entity_id: Entity ID
        fact_object: Fact object type (optional, helps narrow down)

    Returns:
        EntityResponse if found
    """
    if fact_object is None:
        return error_response(
            code="FACT_OBJECT_REQUIRED",
            message="Query parameter 'fact_object' is required"
        )
    result = await service.get_entity(fact_object, entity_id)
    if result is None:
        return error_response(
            code="ENTITY_NOT_FOUND",
            message=f"Entity {entity_id} not found",
            details={"entity_id": entity_id}
        )
    response = success_response(data=result)
    return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/spaces/{space_id}/instances/entities instead."})


@router.post("/query")
async def query_entities(
    body: EntityQueryRequestBody,
    service: EntityService = Depends(get_entity_service)
):
    """Query entities with optional concept filter.

    Args:
        body: Query request with concept_type and filters

    Returns:
        List of EntityResponse objects
    """
    results = await service.query_entities(
        fact_object=body.fact_object,
        filters=body.filter
    )
    response = success_response(data={"entities": results})
    return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/spaces/{space_id}/instances/entities instead."})


@router.get("/{entity_id}/neighbors")
async def get_neighbors(
    entity_id: str,
    relation_name: str | None = None,
    depth: int = 1,
    service: EntityService = Depends(get_entity_service)
):
    """Get neighboring entities.

    Args:
        entity_id: Source entity ID
        relation_name: Optional relation name filter
        depth: Traversal depth (max 2 in Phase 1)

    Returns:
        List of NeighborResponse objects
    """
    try:
        results = await service.get_neighbors(
            entity_id=entity_id,
            relation_name=relation_name,
            depth=depth
        )
        response = success_response(data={"neighbors": results})
        return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/spaces/{space_id}/instances/entities instead."})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
