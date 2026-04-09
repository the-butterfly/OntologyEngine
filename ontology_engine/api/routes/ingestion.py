# ontology_engine/api/routes/ingestion.py
"""Ingestion endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ontology_engine.api.server import get_ingestion_service
from ontology_engine.services.ingestion_service import IngestionService
from ontology_engine.services.dto import IngestionRequest

router = APIRouter()


class EntityCreateItem(BaseModel):
    concept_type: str
    entity_id: str
    attributes: dict[str, Any] | None = None


class RelationCreateItem(BaseModel):
    relation_type: str
    from_id: str
    to_id: str
    attributes: dict[str, Any] | None = None


class IngestionRequestBody(BaseModel):
    instances_path: str | None = None
    entities: list[EntityCreateItem] | None = None
    relations: list[RelationCreateItem] | None = None


@router.post("/import")
async def import_instances(
    body: IngestionRequestBody,
    service: IngestionService = Depends(get_ingestion_service)
):
    """Import entities and relations in bulk.

    Args:
        body: Ingestion request with entities and relations

    Returns:
        IngestionResult with counts and any errors
    """
    try:
        from ontology_engine.services.dto import EntityCreateRequest as ECDTO, RelationCreateRequest as RCDTO
        request = IngestionRequest(
            instances_path=body.instances_path,
            entities=[ECDTO(
                concept_type=e.concept_type,
                entity_id=e.entity_id,
                attributes=e.attributes
            ) for e in (body.entities or [])],
            relations=[RCDTO(
                relation_type=r.relation_type,
                from_id=r.from_id,
                to_id=r.to_id,
                attributes=r.attributes
            ) for r in (body.relations or [])]
        )
        result = await service.import_instances(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/dict")
async def import_from_dict(
    data: dict[str, Any],
    service: IngestionService = Depends(get_ingestion_service)
):
    """Import from a dictionary format.

    Expected format:
    {
        "entities": [
            {"concept_type": "Supplier", "entity_id": "S001", "attributes": {...}}
        ],
        "relations": [
            {"relation_type": "has_invoice", "from_id": "S001", "to_id": "INV001", ...}
        ]
    }

    Args:
        data: Dictionary with entities and relations

    Returns:
        IngestionResult with counts
    """
    try:
        result = await service.import_from_dict(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_import(
    body: IngestionRequestBody,
    service: IngestionService = Depends(get_ingestion_service)
):
    """Validate import data without persisting.

    Args:
        body: Ingestion request to validate

    Returns:
        Validation result with valid entity IDs and any errors
    """
    try:
        from ontology_engine.services.dto import EntityCreateRequest as ECDTO, RelationCreateRequest as RCDTO
        request = IngestionRequest(
            instances_path=body.instances_path,
            entities=[ECDTO(
                concept_type=e.concept_type,
                entity_id=e.entity_id,
                attributes=e.attributes
            ) for e in (body.entities or [])],
            relations=[RCDTO(
                relation_type=r.relation_type,
                from_id=r.from_id,
                to_id=r.to_id,
                attributes=r.attributes
            ) for r in (body.relations or [])]
        )
        valid_ids, invalid_reasons = await service.validate_import(request)
        return {
            "valid_entity_ids": valid_ids,
            "invalid_reasons": invalid_reasons
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
