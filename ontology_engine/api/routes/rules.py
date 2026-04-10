# ontology_engine/api/routes/rules.py
"""Rule management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_schema_service, get_analysis_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.schema_service import SchemaService
from ontology_engine.services.analysis_service import AnalysisService

router = APIRouter(prefix="/v1/rules", tags=["Rules"])


class RuleExecuteRequestBody(BaseModel):
    """Request body for rule execution."""
    entity_id: str
    dimension: str
    rules: list[str] | None = None
    dry_run: bool = False
    context_overrides: dict[str, Any] | None = None


@router.get("")
async def list_rules(
    dimension: str | None = None,
    schema_service: SchemaService = Depends(get_schema_service)
):
    """List all available rules.

    Args:
        dimension: Optional dimension filter

    Returns:
        List of rules
    """
    try:
        schema = await schema_service.get_schema()
        if schema is None:
            return error_response(
                code="SCHEMA_NOT_LOADED",
                message="No schema loaded"
            )

        rules = []
        if schema.rules:
            for rule in schema.rules:
                if dimension is None or rule.dimension == dimension:
                    rules.append({
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "dimension": rule.dimension,
                        "priority": getattr(rule, "priority", None),
                    })

        return success_response(data={"rules": rules})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/execute")
async def execute_rules(
    body: RuleExecuteRequestBody,
    service: AnalysisService = Depends(get_analysis_service)
):
    """Execute rules for an entity.

    Args:
        body: Rule execution request

    Returns:
        AnalysisResponse with rule execution results
    """
    try:
        result = await service.execute_analysis(
            entity_id=body.entity_id,
            dimension=body.dimension,
            context=body.context_overrides
        )
        return success_response(data=result)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
