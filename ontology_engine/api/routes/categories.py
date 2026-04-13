# ontology_engine/api/routes/categories.py
"""Category management API routes (Phase 1 Enhancement)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ontology_engine.api.dependencies import get_storage
from ontology_engine.api.dto.responses import success_response, error_response

router = APIRouter(prefix="/v1/categories", tags=["Categories"])


# --- Dimension Applicability ---

@router.post("/dimensions/applicability")
async def save_dimension_applicability(request: dict[str, Any]) -> dict[str, Any]:
    """Save a dimension applicability mapping."""
    storage = get_storage()
    dimension_id = request.get("dimension_id")
    object_type = request.get("object_type")
    if not dimension_id or not object_type:
        return error_response(
            code="INVALID_REQUEST",
            message="dimension_id and object_type are required",
        )

    try:
        await storage.save_dimension_applicability(
            dimension_id=dimension_id,
            object_type=object_type,
            required=request.get("required", False),
            auto_categorize=request.get("auto_categorize", True),
            source_attribute=request.get("source_attribute"),
        )
        return success_response(
            data={"dimension_id": dimension_id, "object_type": object_type}
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/dimensions/{dimension_id}/applicability")
async def get_dimension_applicability(
    dimension_id: str,
    object_type: str | None = None,
) -> dict[str, Any]:
    """Get dimension applicability entries."""
    storage = get_storage()
    try:
        entries = await storage.get_dimension_applicability(dimension_id, object_type)
        return success_response(data=entries)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.delete("/dimensions/{dimension_id}/applicability/{object_type}")
async def delete_dimension_applicability(
    dimension_id: str, object_type: str
) -> dict[str, Any]:
    """Delete a dimension applicability entry."""
    storage = get_storage()
    try:
        await storage.delete_dimension_applicability(dimension_id, object_type)
        return success_response(data={"deleted": True})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# --- Category Rule Mapping ---

@router.post("/rule-mappings")
async def save_category_rule_mapping(request: dict[str, Any]) -> dict[str, Any]:
    """Save a category-to-rule mapping."""
    storage = get_storage()
    dimension_id = request.get("dimension_id")
    dimension_value = request.get("dimension_value")
    rule_group_id = request.get("rule_group_id")
    if not dimension_id or not dimension_value or not rule_group_id:
        return error_response(
            code="INVALID_REQUEST",
            message="dimension_id, dimension_value, and rule_group_id are required",
        )

    try:
        await storage.save_category_rule_mapping(
            dimension_id=dimension_id,
            dimension_value=dimension_value,
            rule_group_id=rule_group_id,
            mapping_type=request.get("mapping_type", "applicable"),
            override_rule_id=request.get("override_rule_id"),
            override_field=request.get("override_field"),
            override_value=request.get("override_value"),
        )
        return success_response(data={"saved": True})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/rule-mappings")
async def get_category_rule_mappings(
    dimension_id: str | None = None,
    dimension_value: str | None = None,
) -> dict[str, Any]:
    """Get category rule mappings."""
    storage = get_storage()
    try:
        mappings = await storage.get_category_rule_mappings(dimension_id, dimension_value)
        return success_response(data=mappings, meta={"total": len(mappings)})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.delete(
    "/rule-mappings/{dimension_id}/{dimension_value}/{rule_group_id}",
)
async def delete_category_rule_mapping(
    dimension_id: str,
    dimension_value: str,
    rule_group_id: str,
) -> dict[str, Any]:
    """Delete a category rule mapping."""
    storage = get_storage()
    try:
        await storage.delete_category_rule_mapping(
            dimension_id, dimension_value, rule_group_id
        )
        return success_response(data={"deleted": True})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# --- Entity Versions ---

@router.get("/entities/{entity_id}/versions")
async def list_entity_versions(entity_id: str) -> dict[str, Any]:
    """List all versions for an entity."""
    storage = get_storage()
    try:
        versions = await storage.list_entity_versions(entity_id)
        return success_response(data=versions, meta={"total": len(versions)})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/entities/{entity_id}/versions/{version}")
async def get_entity_version(entity_id: str, version: int) -> dict[str, Any]:
    """Get a specific entity version."""
    storage = get_storage()
    try:
        v = await storage.get_entity_version(entity_id, version)
        if not v:
            return error_response(
                code="NOT_FOUND",
                message="Entity version not found",
            )
        return success_response(data=v)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
