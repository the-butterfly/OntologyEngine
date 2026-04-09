# ontology_engine/services/dto/errors.py
"""Service layer errors."""


class ServiceError(Exception):
    """Base service error."""
    pass


class SchemaValidationError(ServiceError):
    """Schema validation failed."""
    pass


class ConceptNotDefinedError(ServiceError):
    """Concept type not defined in schema."""
    pass


class EntityNotFoundError(ServiceError):
    """Entity not found."""
    pass


class AnalysisError(ServiceError):
    """Analysis execution failed."""
    pass


class IngestionError(ServiceError):
    """Data ingestion failed."""
    def __init__(self, type: str, id: str, error: str):
        self.type = type
        self.id = id
        self.error = error
        super().__init__(f"{type} {id}: {error}")


class QueryError(ServiceError):
    """Query execution failed."""
    pass
