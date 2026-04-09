# ontology_engine/services/dto/__init__.py
"""DTO models for service layer."""

from ontology_engine.services.dto.errors import (
    ServiceError,
    SchemaValidationError,
    ConceptNotDefinedError,
    EntityNotFoundError,
    AnalysisError,
    IngestionError,
    QueryError,
)

from ontology_engine.services.dto.requests import (
    EntityCreateRequest,
    RelationCreateRequest,
    AnalysisRequest,
    QueryRequest,
    IngestionRequest,
)

from ontology_engine.services.dto.responses import (
    SchemaInfo,
    EntityResponse,
    RelationResponse,
    NeighborResponse,
    RuleResultResponse,
    AlertResponse,
    AnalysisResponse,
    BatchOperationResult,
    IngestionResult,
    SearchResultResponse,
)

__all__ = [
    # Errors
    "ServiceError",
    "SchemaValidationError",
    "ConceptNotDefinedError",
    "EntityNotFoundError",
    "AnalysisError",
    "IngestionError",
    "QueryError",
    # Requests
    "EntityCreateRequest",
    "RelationCreateRequest",
    "AnalysisRequest",
    "QueryRequest",
    "IngestionRequest",
    # Responses
    "SchemaInfo",
    "EntityResponse",
    "RelationResponse",
    "NeighborResponse",
    "RuleResultResponse",
    "AlertResponse",
    "AnalysisResponse",
    "BatchOperationResult",
    "IngestionResult",
    "SearchResultResponse",
]
