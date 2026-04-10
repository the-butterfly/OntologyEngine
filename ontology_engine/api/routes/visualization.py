# ontology_engine/api/routes/visualization.py
"""Visualization API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_visualization_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.visualization.simulator import (
    EntityNotFoundError,
    SchemaNotLoadedError,
    dataclasses_asdict,
)

router = APIRouter(prefix="/v1/visualize", tags=["Visualization"])


# ========== Schema Visualization ==========


@router.get("/schema/graph")
async def get_schema_graph(
    graph_type: str = Query(
        default="entity_relation",
        description="图类型: entity_relation | metric_dependency | full | rule_overview",
    ),
    layer_filter: str | None = Query(
        default=None,
        description="层过滤(逗号分隔): L1,L3,L4",
    ),
    service: VisualizationService = Depends(get_visualization_service),
):
    """Get Schema graph data (G6 format).

    Returns nodes + edges structured data for frontend rendering.
    """
    try:
        layers = layer_filter.split(",") if layer_filter else None
        result = await service.get_schema_graph(graph_type, layers)
        return success_response(data=dataclasses_asdict(result))
    except SchemaNotLoadedError as e:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


# ========== Rule Chain Visualization ==========


@router.get("/rule-chain/{dimension}")
async def get_rule_chain_graph(
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """Get rule chain DAG graph data (X6 format).

    Includes rule nodes, dependency edges, and priority information.
    """
    try:
        result = await service.get_rule_chain_graph(dimension)
        return success_response(data=dataclasses_asdict(result))
    except SchemaNotLoadedError as e:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(code="INTERNAL_ERROR", message=f"{type(e).__name__}: {str(e)}")


# ========== Simulation ==========


class SimulationRequest(BaseModel):
    """Request body for simulation execution."""

    entity_id: str
    dimension: str
    overrides: dict[str, Any] | None = None
    dry_run: bool = True


@router.post("/simulate")
async def simulate_execution(
    request: SimulationRequest,
    service: VisualizationService = Depends(get_visualization_service),
):
    """Simulate rule chain execution.

    Returns step-by-step ExecutionStepSnapshot, supporting:
    - dry_run: execute without writing to storage
    - overrides: What-if variable overrides
    """
    try:
        result = await service.simulate_execution(
            entity_id=request.entity_id,
            dimension=request.dimension,
            overrides=request.overrides,
            dry_run=request.dry_run,
        )
        return success_response(data=dataclasses_asdict(result))
    except EntityNotFoundError as e:
        return error_response(code="ENTITY_NOT_FOUND", message=str(e))
    except SchemaNotLoadedError as e:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(code="SIMULATION_ERROR", message=f"{type(e).__name__}: {str(e)}")


# ========== Execution Trace ==========


@router.get("/execution/{entity_id}/{dimension}")
async def get_execution_trace(
    entity_id: str,
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """Get historical execution trace.

    Returns ExecutionStepSnapshot sequence for step-by-step replay.
    """
    try:
        steps = await service.get_execution_trace(entity_id, dimension)
        return success_response(data=[dataclasses_asdict(s) for s in steps])
    except EntityNotFoundError as e:
        return error_response(code="ENTITY_NOT_FOUND", message=str(e))
    except SchemaNotLoadedError as e:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(e))
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))
