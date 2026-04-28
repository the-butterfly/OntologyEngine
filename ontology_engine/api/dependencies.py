# ontology_engine/api/dependencies.py
"""FastAPI dependencies - separated to avoid circular imports."""

from typing import Any

from fastapi import HTTPException

from ontology_engine.services import (
    SchemaService,
    EntityService,
    AnalysisService,
    QueryService,
    IngestionService,
    DatasetService,
    IncrementalUpdateService,
)
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.services.rule_service import RuleService
from ontology_engine.services.dag_service import DAGService
from ontology_engine.services.simulation_service import SimulationService

# Global storage and services (initialized on startup)
_storage: Any = None
_services: dict[str, Any] | None = None


def init_dependencies(storage: Any, services: dict[str, Any]) -> None:
    """Initialize dependencies with storage and services."""
    global _storage, _services
    _storage = storage
    _services = services


def get_storage() -> Any:
    """Get storage instance."""
    if _storage is None:
        raise HTTPException(status_code=500, detail="Storage not initialized")
    return _storage


def get_schema_service() -> SchemaService:
    """Get schema service."""
    if _services is None or "schema" not in _services:
        raise HTTPException(status_code=500, detail="Schema service not initialized")
    return _services["schema"]


def get_entity_service() -> EntityService:
    """Get entity service."""
    if _services is None or "entity" not in _services:
        raise HTTPException(status_code=500, detail="Entity service not initialized")
    return _services["entity"]


def get_analysis_service() -> AnalysisService:
    """Get analysis service."""
    if _services is None or "analysis" not in _services:
        raise HTTPException(status_code=500, detail="Analysis service not initialized")
    return _services["analysis"]


def get_query_service() -> QueryService:
    """Get query service."""
    if _services is None or "query" not in _services:
        raise HTTPException(status_code=500, detail="Query service not initialized")
    return _services["query"]


def get_ingestion_service() -> IngestionService:
    """Get ingestion service."""
    if _services is None or "ingestion" not in _services:
        raise HTTPException(status_code=500, detail="Ingestion service not initialized")
    return _services["ingestion"]


def get_visualization_service() -> VisualizationService:
    """Get visualization service."""
    if _services is None or "visualization" not in _services:
        raise HTTPException(status_code=500, detail="Visualization service not initialized")
    return _services["visualization"]


def get_dataset_service() -> DatasetService:
    """Get dataset service."""
    if _services is None or "dataset" not in _services:
        raise HTTPException(status_code=500, detail="Dataset service not initialized")
    return _services["dataset"]


def get_incremental_update_service() -> IncrementalUpdateService:
    """Get incremental update service."""
    if _services is None or "incremental" not in _services:
        raise HTTPException(status_code=500, detail="Incremental update service not initialized")
    return _services["incremental"]


def get_rule_service() -> RuleService:
    """Get rule service."""
    if _services is None or "rule" not in _services:
        raise HTTPException(status_code=500, detail="Rule service not initialized")
    return _services["rule"]


def get_dag_service() -> DAGService:
    """Get DAG service."""
    if _services is None or "dag" not in _services:
        raise HTTPException(status_code=500, detail="DAG service not initialized")
    return _services["dag"]


def get_simulation_service() -> SimulationService:
    """Get simulation service."""
    if _services is None or "simulation" not in _services:
        raise HTTPException(status_code=500, detail="Simulation service not initialized")
    return _services["simulation"]


def get_feedback_service():
    from ontology_engine.services.feedback_service import FeedbackService

    if _storage is None:
        raise HTTPException(status_code=500, detail="Storage not initialized")
    return FeedbackService(_storage)