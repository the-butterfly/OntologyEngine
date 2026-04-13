# ontology_engine/storage/__init__.py
from ontology_engine.storage.base import (
    EntityInstance,
    GraphQueryError,
    GraphStoreBackend,
    RelationInstance,
    StorageBackend,
    StorageError,
)
from ontology_engine.storage.duckdb import DuckDBStorage
from ontology_engine.storage.dual_write import DualWriteCoordinator

__all__ = [
    "DuckDBStorage",
    "DualWriteCoordinator",
    "EntityInstance",
    "GraphQueryError",
    "GraphStoreBackend",
    "RelationInstance",
    "StorageBackend",
    "StorageError",
]