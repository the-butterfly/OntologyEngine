# ontology_engine/storage/__init__.py
from ontology_engine.storage.base import (
    EntityInstance,
    RelationInstance,
    StorageBackend,
    StorageError,
)
from ontology_engine.storage.duckdb import DuckDBStorage

__all__ = [
    "DuckDBStorage",
    "EntityInstance",
    "RelationInstance",
    "StorageBackend",
    "StorageError",
]