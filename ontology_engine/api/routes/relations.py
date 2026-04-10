# ontology_engine/api/routes/relations.py
"""Relation management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_entity_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.entity_service import EntityService

router = APIRouter(prefix="/v1/relations", tags=["Relations"])


class RelationCreateRequestBody(BaseModel):
    """Request body for relation creation."""
    relation_type: str
    from_id: str
    to_id: str
    attributes: dict[str, Any] | None = None


@router.post("")
async def create_relation(
    body: RelationCreateRequestBody,
    service: EntityService = Depends(get_entity_service)
):
    """Create a relation between entities.

    Args:
        body: Relation creation request

    Returns:
        Created RelationResponse
    """
    try:
        result = await service.create_relation(
            relation_type=body.relation_type,
            from_id=body.from_id,
            to_id=body.to_id,
            attributes=body.attributes
        )
        return success_response(data=result)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
