# ontology_engine/api/routes/rules.py
"""Rule management endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ontology_engine.api.dependencies import (
    get_schema_service,
    get_analysis_service,
    get_rule_service,
    get_dag_service,
    get_simulation_service,
)
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.schema_service import SchemaService
from ontology_engine.services.analysis_service import AnalysisService
from ontology_engine.services.rule_service import RuleService, RuleServiceError
from ontology_engine.services.dag_service import DAGService
from ontology_engine.services.simulation_service import SimulationService
from ontology_engine.engine.rule.operators import build_operator_schemas

router = APIRouter(prefix="/v1", tags=["Rules"])


# =============================================================================
# Existing Endpoints (Legacy)
# =============================================================================


class RuleExecuteRequestBody(BaseModel):
    """Request body for rule execution."""
    entity_id: str
    dimension: str
    rules: list[str] | None = None
    dry_run: bool = False
    context_overrides: dict[str, Any] | None = None


@router.get("/rules")
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


@router.post("/rules/execute")
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


# =============================================================================
# Rule Groups CRUD (Phase 2)
# =============================================================================


class RuleGroupCreateRequest(BaseModel):
    """Request body for creating a rule group."""
    name: str
    description: str = ""
    type: str = "decision"
    priority: int = 100
    applies_to: dict[str, Any] | None = None
    preconditions: list[dict[str, Any]] | None = None
    inputs: list[dict[str, Any]] | None = None
    outputs: list[dict[str, Any]] | None = None
    enabled: bool = True


class RuleGroupUpdateRequest(BaseModel):
    """Request body for updating a rule group."""
    description: str | None = None
    type: str | None = None
    priority: int | None = None
    applies_to: dict[str, Any] | None = None
    preconditions: list[dict[str, Any]] | None = None
    inputs: list[dict[str, Any]] | None = None
    outputs: list[dict[str, Any]] | None = None
    enabled: bool | None = None


@router.post("/rule-groups")
async def create_rule_group(
    body: RuleGroupCreateRequest,
    service: RuleService = Depends(get_rule_service)
):
    """Create a new rule group."""
    try:
        data = body.model_dump()
        rule_group = await service.create_rule_group(data)
        return success_response(data={"rule_group": rule_group.to_dict()})
    except RuleServiceError as e:
        return error_response(code="VALIDATION_ERROR", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/rule-groups")
async def list_rule_groups(
    enabled: bool | None = None,
    service: RuleService = Depends(get_rule_service)
):
    """List all rule groups."""
    try:
        rule_groups = await service.list_rule_groups(enabled=enabled)
        return success_response(data={
            "rule_groups": [rg.to_dict() for rg in rule_groups]
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/rule-groups/{name}")
async def get_rule_group(
    name: str,
    service: RuleService = Depends(get_rule_service)
):
    """Get a rule group by name."""
    try:
        rule_group = await service.get_rule_group(name)
        if rule_group is None:
            return error_response(code="NOT_FOUND", message=f"Rule group '{name}' not found")
        return success_response(data={"rule_group": rule_group.to_dict()})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.put("/rule-groups/{name}")
async def update_rule_group(
    name: str,
    body: RuleGroupUpdateRequest,
    service: RuleService = Depends(get_rule_service)
):
    """Update a rule group."""
    try:
        data = body.model_dump(exclude_unset=True)
        rule_group = await service.update_rule_group(name, data)
        if rule_group is None:
            return error_response(code="NOT_FOUND", message=f"Rule group '{name}' not found")
        return success_response(data={"rule_group": rule_group.to_dict()})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.delete("/rule-groups/{name}")
async def delete_rule_group(
    name: str,
    service: RuleService = Depends(get_rule_service)
):
    """Delete a rule group and its steps."""
    try:
        deleted = await service.delete_rule_group(name)
        if not deleted:
            return error_response(code="NOT_FOUND", message=f"Rule group '{name}' not found")
        return success_response(data={"deleted": True})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# =============================================================================
# Rule Steps CRUD
# =============================================================================


class RuleStepCreateRequest(BaseModel):
    """Request body for creating a rule step."""
    id: str
    name: str
    step_order: int = 0
    when: dict[str, Any]
    then: dict[str, Any]
    else_: dict[str, Any] | None = None
    enabled: bool = True
    description: str = ""
    tags: list[str] | None = None


class RuleStepUpdateRequest(BaseModel):
    """Request body for updating a rule step."""
    name: str | None = None
    step_order: int | None = None
    when: dict[str, Any] | None = None
    then: dict[str, Any] | None = None
    else_: dict[str, Any] | None = None
    enabled: bool | None = None
    description: str | None = None
    tags: list[str] | None = None


@router.post("/rule-groups/{name}/steps")
async def create_rule_step(
    name: str,
    body: RuleStepCreateRequest,
    service: RuleService = Depends(get_rule_service)
):
    """Create a new rule step."""
    try:
        data = body.model_dump()
        step = await service.create_rule_step(name, data)
        return success_response(data={"step": step.to_dict()})
    except RuleServiceError as e:
        return error_response(code="VALIDATION_ERROR", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/rule-groups/{name}/steps")
async def list_rule_steps(
    name: str,
    service: RuleService = Depends(get_rule_service)
):
    """List all rule steps for a rule group."""
    try:
        steps = await service.list_rule_steps(name)
        return success_response(data={
            "steps": [s.to_dict() for s in steps]
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.put("/rule-groups/{name}/steps/{step_id}")
async def update_rule_step(
    name: str,
    step_id: str,
    body: RuleStepUpdateRequest,
    service: RuleService = Depends(get_rule_service)
):
    """Update a rule step."""
    try:
        data = body.model_dump(exclude_unset=True)
        step = await service.update_rule_step(name, step_id, data)
        if step is None:
            return error_response(code="NOT_FOUND", message=f"Step '{step_id}' not found")
        return success_response(data={"step": step.to_dict()})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.delete("/rule-groups/{name}/steps/{step_id}")
async def delete_rule_step(
    name: str,
    step_id: str,
    service: RuleService = Depends(get_rule_service)
):
    """Delete a rule step."""
    try:
        deleted = await service.delete_rule_step(name, step_id)
        if not deleted:
            return error_response(code="NOT_FOUND", message=f"Step '{step_id}' not found")
        return success_response(data={"deleted": True})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/rule-groups/{name}/reorder")
async def reorder_rule_steps(
    name: str,
    step_ids: list[str],
    service: RuleService = Depends(get_rule_service)
):
    """Reorder rule steps."""
    try:
        await service.reorder_rule_steps(name, step_ids)
        return success_response(data={"reordered": True})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# =============================================================================
# Simulation
# =============================================================================


class SimulateRequest(BaseModel):
    """Request body for rule simulation."""
    entity_data: dict[str, Any]
    pre_computed: dict[str, Any] | None = None
    step_filter: list[str] | None = None


@router.post("/rule-groups/{name}/simulate")
async def simulate_rule_group(
    name: str,
    body: SimulateRequest,
    rule_service: RuleService = Depends(get_rule_service),
    simulation_service: SimulationService = Depends(get_simulation_service),
):
    """Simulate rule group execution."""
    try:
        # Get rule group and steps in parallel
        rule_group, steps = await asyncio.gather(
            rule_service.get_rule_group(name),
            rule_service.list_rule_steps(name),
        )
        if rule_group is None:
            return error_response(code="NOT_FOUND", message=f"Rule group '{name}' not found")

        # Run simulation
        result = await simulation_service.simulate_rule_group(
            rule_group=rule_group,
            steps=steps,
            entity_data=body.entity_data,
            pre_computed=body.pre_computed,
            step_filter=body.step_filter,
        )

        return success_response(data={
            "rule_group_name": result.rule_group_name,
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_name": s.step_name,
                    "condition_result": s.condition_result,
                    "condition_detail": {
                        "type": s.condition_detail.type if s.condition_detail else None,
                        "expression": s.condition_detail.expression if s.condition_detail else None,
                        "sub_conditions": s.condition_detail.sub_conditions if s.condition_detail else [],
                        "result": s.condition_detail.result if s.condition_detail else False,
                        "explain": s.condition_detail.explanation if s.condition_detail else "",
                    } if s.condition_detail else None,
                    "action_taken": s.action_taken,
                    "output": s.output,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                }
                for s in result.steps
            ],
            "final_output": result.final_output,
            "alerts": result.alerts,
            "errors": result.errors,
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# =============================================================================
# YAML Import/Export
# =============================================================================


class ImportYamlRequest(BaseModel):
    """Request body for YAML import."""
    yaml_content: str


@router.post("/rule-groups/import")
async def import_rule_group(
    body: ImportYamlRequest,
    service: RuleService = Depends(get_rule_service)
):
    """Import a rule group from YAML."""
    try:
        rule_group = await service.import_from_yaml(body.yaml_content)
        return success_response(data={"rule_group": rule_group.to_dict()})
    except RuleServiceError as e:
        return error_response(code="VALIDATION_ERROR", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/rule-groups/validate-yaml")
async def validate_yaml(
    body: ImportYamlRequest,
    service: RuleService = Depends(get_rule_service)
):
    """Validate YAML without importing."""
    try:
        is_valid, errors = await service.validate_yaml(body.yaml_content)
        return success_response(data={
            "valid": is_valid,
            "errors": errors,
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/rule-groups/{name}/export")
async def export_rule_group(
    name: str,
    service: RuleService = Depends(get_rule_service)
):
    """Export a rule group to YAML."""
    try:
        yaml_content = await service.export_rule_group_to_yaml(name)
        return success_response(data={
            "name": name,
            "yaml_content": yaml_content,
        })
    except RuleServiceError as e:
        return error_response(code="NOT_FOUND", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# =============================================================================
# Operators
# =============================================================================


@router.get("/operators")
async def list_operators():
    """List all available operators with their schemas."""
    try:
        schemas = build_operator_schemas()
        return success_response(data={
            "operators": [s.to_dict() for s in schemas]
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/operators/{name}/schema")
async def get_operator_schema(name: str):
    """Get the JSON Schema for an operator."""
    from ontology_engine.engine.rule.operators.registry import get_operator_schema
    schema = get_operator_schema(name)
    if schema is None:
        return error_response(code="NOT_FOUND", message=f"Operator '{name}' not found")
    return success_response(data={"schema": schema})


# =============================================================================
# DAG Endpoints
# =============================================================================


@router.get("/dag/full")
async def get_full_dag(
    target: str | None = None,
    depth: int = Query(default=10, ge=1, le=50),
    dag_service: DAGService = Depends(get_dag_service),
):
    """Get full computation DAG."""
    try:
        graph_data = dag_service.to_graph_data(
            graph_type="full_computation",
            target=target,
            depth=depth,
        )
        return success_response(data=graph_data)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/dag/path")
async def get_dag_path(
    from_node: str = Query(alias="from"),
    to_node: str = Query(alias="to"),
    dag_service: DAGService = Depends(get_dag_service),
):
    """Find path from source to target in DAG."""
    try:
        path = dag_service.find_path(from_node, to_node)
        if path is None:
            return error_response(code="NOT_FOUND", message=f"No path found from '{from_node}' to '{to_node}'")
        return success_response(data={"path": path})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/metrics/{name}/dag")
async def get_metric_dag(
    name: str,
    depth: int = Query(default=5, ge=1, le=20),
    dag_service: DAGService = Depends(get_dag_service),
):
    """Get DAG for a specific metric."""
    try:
        graph_data = dag_service.to_graph_data(
            graph_type="metric_dependency",
            target=name,
            depth=depth,
        )
        return success_response(data=graph_data)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
