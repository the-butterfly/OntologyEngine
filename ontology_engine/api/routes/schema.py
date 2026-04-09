# ontology_engine/api/routes/schema.py
"""Schema management endpoints."""

from fastapi import APIRouter, HTTPException, Depends

from ontology_engine.api.server import get_schema_service
from ontology_engine.services.schema_service import SchemaService
from ontology_engine.services.dto import SchemaValidationError

router = APIRouter()


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
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SchemaValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=404, detail="No schema loaded")
    return schema


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
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions")
async def get_schema_versions(
    service: SchemaService = Depends(get_schema_service)
):
    """Get schema version history.

    Returns:
        List of version info dicts
    """
    versions = await service.get_schema_versions()
    return {"versions": versions}


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
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
