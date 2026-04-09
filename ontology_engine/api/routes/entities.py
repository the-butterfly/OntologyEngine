# ontology_engine/api/routes/entities.py
"""Entity management endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ontology_engine.api.server import get_entity_service
from ontology_engine.services.entity_service import EntityService
from ontology_engine.services.dto import (
    EntityCreateRequest,
    ConceptNotDefinedError,
)

router = APIRouter()


class EntityCreateRequestBody(BaseModel):
    concept_type: str
    entity_id: str
    attributes: dict[str, Any] | None = None


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
            concept_type=body.concept_type,
            entity_id=body.entity_id,
            attributes=body.attributes
        )
        return result
    except ConceptNotDefinedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            concept_type=b.concept_type,
            entity_id=b.entity_id,
            attributes=b.attributes
        )
        for b in bodies
    ]
    result = await service.batch_create(requests)
    return result


@router.get("/{concept}/{entity_id}")
async def get_entity(
    concept: str,
    entity_id: str,
    service: EntityService = Depends(get_entity_service)
):
    """Get entity by concept and ID.

    Args:
        concept: Concept type
        entity_id: Entity ID

    Returns:
        EntityResponse if found
    """
    result = await service.get_entity(concept, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return result


@router.get("")
async def query_entities(
    concept_type: str | None = None,
    service: EntityService = Depends(get_entity_service)
):
    """Query entities with optional concept filter.

    Args:
        concept_type: Optional concept type filter

    Returns:
        List of EntityResponse objects
    """
    results = await service.query_entities(concept_type=concept_type)
    return {"entities": results}


@router.post("/relations")
async def create_relation(
    relation_type: str,
    from_id: str,
    to_id: str,
    attributes: dict[str, Any] | None = None,
    service: EntityService = Depends(get_entity_service)
):
    """Create a relation between entities.

    Args:
        relation_type: Type of relation
        from_id: Source entity ID
        to_id: Target entity ID
        attributes: Optional relation attributes

    Returns:
        Created RelationResponse
    """
    try:
        result = await service.create_relation(
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            attributes=attributes
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/neighbors/{entity_id}")
async def get_neighbors(
    entity_id: str,
    relation_type: str | None = None,
    depth: int = 1,
    service: EntityService = Depends(get_entity_service)
):
    """Get neighboring entities.

    Args:
        entity_id: Source entity ID
        relation_type: Optional relation type filter
        depth: Traversal depth (max 2 in Phase 1)

    Returns:
        List of NeighborResponse objects
    """
    try:
        results = await service.get_neighbors(
            entity_id=entity_id,
            relation_type=relation_type,
            depth=depth
        )
        return {"neighbors": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
