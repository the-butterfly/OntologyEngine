# ontology_engine/api/routes/categories.py
"""Category management API routes (Phase 1 Enhancement)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ontology_engine.api.dependencies import get_storage

router = APIRouter(prefix="/v1/categories", tags=["Categories"])


# --- Dimension Applicability ---

@router.post("/dimensions/applicability", response_model=dict)
async def save_dimension_applicability(request: dict[str, Any]):
    """Save a dimension applicability mapping."""
    storage = get_storage()
    dimension_id = request.get("dimension_id")
    object_type = request.get("object_type")
    if not dimension_id or not object_type:
        raise HTTPException(status_code=400, detail="dimension_id and object_type are required")

    await storage.save_dimension_applicability(
        dimension_id=dimension_id,
        object_type=object_type,
        required=request.get("required", False),
        auto_categorize=request.get("auto_categorize", True),
        source_attribute=request.get("source_attribute"),
    )
    return {"status": "ok", "dimension_id": dimension_id, "object_type": object_type}


@router.get("/dimensions/{dimension_id}/applicability", response_model=dict)
async def get_dimension_applicability(
    dimension_id: str,
    object_type: str | None = None,
):
    """Get dimension applicability entries."""
    storage = get_storage()
    entries = await storage.get_dimension_applicability(dimension_id, object_type)
    return {"status": "ok", "dimension_id": dimension_id, "data": entries}


@router.delete("/dimensions/{dimension_id}/applicability/{object_type}", response_model=dict)
async def delete_dimension_applicability(dimension_id: str, object_type: str):
    """Delete a dimension applicability entry."""
    storage = get_storage()
    await storage.delete_dimension_applicability(dimension_id, object_type)
    return {"status": "ok", "deleted": True}


# --- Category Rule Mapping ---

@router.post("/rule-mappings", response_model=dict)
async def save_category_rule_mapping(request: dict[str, Any]):
    """Save a category-to-rule mapping."""
    storage = get_storage()
    dimension_id = request.get("dimension_id")
    dimension_value = request.get("dimension_value")
    rule_group_id = request.get("rule_group_id")
    if not dimension_id or not dimension_value or not rule_group_id:
        raise HTTPException(
            status_code=400,
            detail="dimension_id, dimension_value, and rule_group_id are required",
        )

    await storage.save_category_rule_mapping(
        dimension_id=dimension_id,
        dimension_value=dimension_value,
        rule_group_id=rule_group_id,
        mapping_type=request.get("mapping_type", "applicable"),
        override_rule_id=request.get("override_rule_id"),
        override_field=request.get("override_field"),
        override_value=request.get("override_value"),
    )
    return {"status": "ok"}


@router.get("/rule-mappings", response_model=dict)
async def get_category_rule_mappings(
    dimension_id: str | None = None,
    dimension_value: str | None = None,
):
    """Get category rule mappings."""
    storage = get_storage()
    mappings = await storage.get_category_rule_mappings(dimension_id, dimension_value)
    return {"status": "ok", "data": mappings, "total": len(mappings)}


@router.delete(
    "/rule-mappings/{dimension_id}/{dimension_value}/{rule_group_id}",
    response_model=dict,
)
async def delete_category_rule_mapping(
    dimension_id: str,
    dimension_value: str,
    rule_group_id: str,
):
    """Delete a category rule mapping."""
    storage = get_storage()
    await storage.delete_category_rule_mapping(dimension_id, dimension_value, rule_group_id)
    return {"status": "ok", "deleted": True}


# --- Entity Versions ---

@router.get("/entities/{entity_id}/versions", response_model=dict)
async def list_entity_versions(entity_id: str):
    """List all versions for an entity."""
    storage = get_storage()
    versions = await storage.list_entity_versions(entity_id)
    return {"status": "ok", "data": versions, "total": len(versions)}


@router.get("/entities/{entity_id}/versions/{version}", response_model=dict)
async def get_entity_version(entity_id: str, version: int):
    """Get a specific entity version."""
    storage = get_storage()
    v = await storage.get_entity_version(entity_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="Entity version not found")
    return {"status": "ok", "data": v}
