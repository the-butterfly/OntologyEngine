# ontology_engine/api/routes/schema.py
"""Schema management endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ontology_engine.api.dependencies import get_schema_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.schema_service import SchemaService
from ontology_engine.services.dto import SchemaValidationError

router = APIRouter(prefix="/v1/schema", tags=["Schema"])


@router.post("/load")
async def load_schema(
    schema_path: str,
    service: SchemaService = Depends(get_schema_service)
):
    """Load schema from file.

    Args:
        schema_path: Path to schema YAML file

    Returns:
        SchemaInfo with loaded schema details
    """
    try:
        result = await service.load_schema(schema_path)
        response = success_response(data=result)
        return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/management/{space_id} instead."})
    except FileNotFoundError:
        return error_response(
            code="NOT_FOUND",
            message=f"Schema file not found: {schema_path}"
        )
    except SchemaValidationError as e:
        return error_response(code="VALIDATION_ERROR", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/")
async def get_schema(
    service: SchemaService = Depends(get_schema_service)
):
    """Get current active schema.

    Returns:
        Current KGMLSchema or None
    """
    schema = await service.get_schema()
    if schema is None:
        return error_response(
            code="SCHEMA_NOT_LOADED",
            message="No schema loaded"
        )
    response = success_response(data=schema)
    return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/management/{space_id} instead."})


@router.post("/reload")
async def reload_schema(
    schema_path: str,
    service: SchemaService = Depends(get_schema_service)
):
    """Hot-reload schema from file.

    Args:
        schema_path: Path to schema YAML file

    Returns:
        SchemaInfo with reloaded schema details
    """
    try:
        result = await service.reload_schema(schema_path)
        response = success_response(data=result)
        return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/management/{space_id} instead."})
    except FileNotFoundError:
        return error_response(
            code="NOT_FOUND",
            message=f"Schema file not found: {schema_path}"
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/versions")
async def get_schema_versions(
    service: SchemaService = Depends(get_schema_service)
):
    """Get schema version history.

    Returns:
        List of version info dicts
    """
    versions = await service.get_schema_versions()
    response = success_response(data={"versions": versions})
    return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/management/{space_id} instead."})


@router.post("/rollback/{target_version}")
async def rollback_schema(
    target_version: int,
    service: SchemaService = Depends(get_schema_service)
):
    """Rollback to specific schema version.

    Args:
        target_version: Version number to rollback to

    Returns:
        SchemaInfo (Note: full rollback not implemented in Phase 1)
    """
    try:
        result = await service.rollback_schema(target_version)
        response = success_response(data=result)
        return JSONResponse(content=response, headers={"X-Deprecation-Warning": "Deprecated. Use /v1/management/{space_id} instead."})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
