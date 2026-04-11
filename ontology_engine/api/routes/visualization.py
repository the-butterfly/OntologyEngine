# ontology_engine/api/routes/visualization.py
"""Visualization API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_visualization_service
from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.visualization.simulator import (
    EntityNotFoundError,
    SchemaNotLoadedError,
    dataclasses_asdict,
)

router = APIRouter(prefix="/v1/visualize", tags=["Visualization"])


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
    """Get Schema graph data (G6 format)."""
    try:
        layers = layer_filter.split(",") if layer_filter else None
        result = await service.get_schema_graph(graph_type, layers)
        return success_response(data=dataclasses_asdict(result))
    except SchemaNotLoadedError as exc:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        return error_response(code="INTERNAL_ERROR", message=str(exc))


@router.get("/entities")
async def list_visualization_entities(
    concept: str | None = Query(default="Supplier", description="实体类型，默认 Supplier"),
    dimension: str | None = Query(default=None, description="按评估维度过滤实体"),
    service: VisualizationService = Depends(get_visualization_service),
):
    """List selectable entities for visualization pages."""
    try:
        result = await service.list_entities(concept=concept, dimension=dimension)
        return success_response(data=[dataclasses_asdict(item) for item in result])
    except SchemaNotLoadedError as exc:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        return error_response(code="INTERNAL_ERROR", message=str(exc))


@router.get("/metrics/{entity_id}")
async def get_metric_snapshot(
    entity_id: str,
    dimension: str = Query(default="credit_assessment", description="评估维度"),
    service: VisualizationService = Depends(get_visualization_service),
):
    """Get real metric snapshot for one entity."""
    try:
        result = await service.get_metric_snapshot(entity_id=entity_id, dimension=dimension)
        return success_response(data=dataclasses_asdict(result))
    except EntityNotFoundError as exc:
        return error_response(code="ENTITY_NOT_FOUND", message=str(exc))
    except SchemaNotLoadedError as exc:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        return error_response(code="SIMULATION_ERROR", message=f"{type(exc).__name__}: {str(exc)}")


@router.get("/rule-chain/{dimension}")
async def get_rule_chain_graph(
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """Get rule chain DAG graph data (X6 format)."""
    try:
        result = await service.get_rule_chain_graph(dimension)
        return success_response(data=dataclasses_asdict(result))
    except SchemaNotLoadedError as exc:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return error_response(code="INTERNAL_ERROR", message=f"{type(exc).__name__}: {str(exc)}")


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
    """Simulate rule chain execution."""
    try:
        result = await service.simulate_execution(
            entity_id=request.entity_id,
            dimension=request.dimension,
            overrides=request.overrides,
            dry_run=request.dry_run,
        )
        return success_response(data=dataclasses_asdict(result))
    except EntityNotFoundError as exc:
        return error_response(code="ENTITY_NOT_FOUND", message=str(exc))
    except SchemaNotLoadedError as exc:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return error_response(code="SIMULATION_ERROR", message=f"{type(exc).__name__}: {str(exc)}")


@router.get("/execution/{entity_id}/{dimension}")
async def get_execution_trace(
    entity_id: str,
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """Get historical execution trace."""
    try:
        steps = await service.get_execution_trace(entity_id, dimension)
        return success_response(data=[dataclasses_asdict(step) for step in steps])
    except EntityNotFoundError as exc:
        return error_response(code="ENTITY_NOT_FOUND", message=str(exc))
    except SchemaNotLoadedError as exc:
        return error_response(code="SCHEMA_NOT_LOADED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        return error_response(code="INTERNAL_ERROR", message=str(exc))
