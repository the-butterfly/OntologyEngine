# ontology_engine/api/routes/analysis.py
"""Analysis endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_analysis_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.analysis_service import AnalysisService
from ontology_engine.services.dto import (
    EntityNotFoundError,
    AnalysisError,
)

router = APIRouter(prefix="/v1/analysis", tags=["Analysis"])


class AnalysisRequestBody(BaseModel):
    """Request body for analysis."""
    entity_id: str
    dimension: str
    context: dict[str, Any] | None = None


@router.post("/execute")
async def execute_analysis(
    body: AnalysisRequestBody,
    service: AnalysisService = Depends(get_analysis_service)
):
    """Execute complete dimension analysis.

    Args:
        body: Analysis request with entity_id and dimension

    Returns:
        AnalysisResponse with complete analysis results
    """
    try:
        result = await service.execute_analysis(
            entity_id=body.entity_id,
            dimension=body.dimension,
            context=body.context
        )
        return success_response(data=result)
    except EntityNotFoundError as e:
        return error_response(
            code="ENTITY_NOT_FOUND",
            message=str(e)
        )
    except AnalysisError as e:
        return error_response(code="ANALYSIS_ERROR", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/dry-run")
async def execute_dry_run(
    body: AnalysisRequestBody,
    service: AnalysisService = Depends(get_analysis_service)
):
    """Execute analysis preview without persisting results.

    Args:
        body: Analysis request

    Returns:
        AnalysisResponse (not persisted)
    """
    try:
        result = await service.execute_dry_run(
            entity_id=body.entity_id,
            dimension=body.dimension,
            context=body.context
        )
        return success_response(data=result)
    except EntityNotFoundError as e:
        return error_response(
            code="ENTITY_NOT_FOUND",
            message=str(e)
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
