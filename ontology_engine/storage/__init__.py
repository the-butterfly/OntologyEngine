# ontology_engine/storage/__init__.py
from ontology_engine.storage.duckdb import (
    DuckDBStorage,
    EntityInstance,
    RelationInstance,
    StorageBackend,
    StorageError,
)

__all__ = [
    "DuckDBStorage",
    "EntityInstance",
    "RelationInstance",
    "StorageBackend",
    "StorageError",
]