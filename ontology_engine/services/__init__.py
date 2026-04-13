# ontology_engine/services/__init__.py
"""Service layer exports."""

from ontology_engine.services.schema_service import SchemaService
from ontology_engine.services.entity_service import EntityService
from ontology_engine.services.analysis_service import AnalysisService
from ontology_engine.services.query_service import QueryService
from ontology_engine.services.ingestion_service import IngestionService
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.services.incremental_update import IncrementalUpdateService, EntityDiffer
from ontology_engine.services.dataset_service import DatasetService

__all__ = [
    "SchemaService",
    "EntityService",
    "AnalysisService",
    "QueryService",
    "IngestionService",
    "VisualizationService",
    "IncrementalUpdateService",
    "EntityDiffer",
    "DatasetService",
]
