# ontology_engine/api/routes/ingestion.py
"""Ingestion endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_ingestion_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.ingestion_service import IngestionService
from ontology_engine.services.dto import IngestionRequest

router = APIRouter(prefix="/v1/ingestion", tags=["Ingestion"])


class MissingParameterError(Exception):
    """Raised when a required query parameter is missing."""
    def __init__(self, param_name: str):
        self.param_name = param_name
        super().__init__(f"Missing required parameter: {param_name}")


class EntityCreateItem(BaseModel):
    """Entity item for ingestion."""
    fact_object: str
    entity_id: str
    attributes: dict[str, Any] | None = None


class RelationCreateItem(BaseModel):
    """Relation item for ingestion."""
    relation_name: str
    from_id: str
    to_id: str
    attributes: dict[str, Any] | None = None


class IngestionRequestBody(BaseModel):
    """Request body for ingestion."""
    instances_path: str | None = None
    entities: list[EntityCreateItem] | None = None
    relations: list[RelationCreateItem] | None = None
    space_id: str | None = None


@router.post("/import")
async def import_instances(
    body: IngestionRequestBody,
    space_id: str = Query(default=None, description="Space ID for the imported entities"),
    service: IngestionService = Depends(get_ingestion_service)
):
    """Import entities and relations in bulk.

    Args:
        body: Ingestion request with entities and relations
        space_id: Space ID for the imported entities (required)

    Returns:
        IngestionResult with counts and any errors
    """
    if not space_id:
        return error_response(
            code="MISSING_PARAMETER",
            message="space_id query parameter is required"
        )
    try:
        from ontology_engine.services.dto import EntityCreateRequest as ECDTO, RelationCreateRequest as RCDTO
        # Add space_id to each entity's attributes
        entities_with_space = []
        for e in (body.entities or []):
            attrs = dict(e.attributes) if e.attributes else {}
            attrs["_space_id"] = space_id
            entities_with_space.append(ECDTO(
                fact_object=e.fact_object,
                entity_id=e.entity_id,
                attributes=attrs
            ))
        request = IngestionRequest(
            instances_path=body.instances_path,
            entities=entities_with_space,
            relations=[RCDTO(
                relation_name=r.relation_name,
                from_id=r.from_id,
                to_id=r.to_id,
                attributes=r.attributes
            ) for r in (body.relations or [])],
            space_id=space_id
        )
        result = await service.import_instances(request)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="INGESTION_ERROR", message=str(e))


@router.post("/import/dict")
async def import_from_dict(
    data: dict[str, Any],
    space_id: str = Query(default=None, description="Space ID for the imported entities"),
    service: IngestionService = Depends(get_ingestion_service)
):
    """Import from a dictionary format.

    Expected format:
    {
        "entities": [
            {"fact_object": "Supplier", "entity_id": "S001", "attributes": {...}}
        ],
        "relations": [
            {"relation_name": "has_invoice", "from_id": "S001", "to_id": "INV001", ...}
        ]
    }

    Args:
        data: Dictionary with entities and relations
        space_id: Space ID for the imported entities (required)

    Returns:
        IngestionResult with counts
    """
    if not space_id:
        return error_response(
            code="MISSING_PARAMETER",
            message="space_id query parameter is required"
        )
    try:
        # Add space_id to each entity's attributes
        if "entities" in data:
            for e in data["entities"]:
                if isinstance(e, dict):
                    attrs = dict(e.get("attributes", {}))
                    attrs["_space_id"] = space_id
                    e["attributes"] = attrs
        result = await service.import_from_dict(data, space_id=space_id)
        return success_response(data=result)
    except Exception as e:
        return error_response(code="INGESTION_ERROR", message=str(e))


@router.post("/validate")
async def validate_import(
    body: IngestionRequestBody,
    space_id: str = Query(default=None, description="Space ID for the imported entities"),
    service: IngestionService = Depends(get_ingestion_service)
):
    """Validate import data without persisting.

    Args:
        body: Ingestion request to validate
        space_id: Space ID for the imported entities (required)

    Returns:
        Validation result with valid entity IDs and any errors
    """
    if not space_id:
        return error_response(
            code="MISSING_PARAMETER",
            message="space_id query parameter is required"
        )
    try:
        from ontology_engine.services.dto import EntityCreateRequest as ECDTO, RelationCreateRequest as RCDTO
        # Add space_id to each entity's attributes
        entities_with_space = []
        for e in (body.entities or []):
            attrs = dict(e.attributes) if e.attributes else {}
            attrs["_space_id"] = space_id
            entities_with_space.append(ECDTO(
                fact_object=e.fact_object,
                entity_id=e.entity_id,
                attributes=attrs
            ))
        request = IngestionRequest(
            instances_path=body.instances_path,
            entities=entities_with_space,
            relations=[RCDTO(
                relation_name=r.relation_name,
                from_id=r.from_id,
                to_id=r.to_id,
                attributes=r.attributes
            ) for r in (body.relations or [])],
            space_id=space_id
        )
        valid_ids, invalid_reasons = await service.validate_import(request)
        return success_response(data={
            "valid_entity_ids": valid_ids,
            "invalid_reasons": invalid_reasons
        })
    except Exception as e:
        return error_response(code="INGESTION_ERROR", message=str(e))
