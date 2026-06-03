# ontology_engine/storage/__init__.py
from ontology_engine.storage.base import (
    AuditStorage,
    CategoryStorage,
    ChangeStorage,
    CognitiveStorageBackend,
    DatasetStorage,
    DimensionStorage,
    EntityInstance,
    EntityStorage,
    GraphQueryError,
    GraphStoreBackend,
    HybridSearchResult,
    MetricStorage,
    RelationInstance,
    RetrievalBackend,
    StorageBackend,
    StorageError,
    VectorSearchResult,
    VectorStoreBackend,
    VersionStorage,
)
from ontology_engine.storage.config import (
    StorageConfig,
    create_graph_store,
    create_meta_store,
    create_vector_store,
)
from ontology_engine.storage.sqlite import SQLiteStorage
from ontology_engine.storage.dual_write import DualWriteCoordinator
from ontology_engine.storage.graph import LadybugGraphStore, NetworkXGraphStore
from ontology_engine.storage.retrieval import DefaultRetrievalBackend
from ontology_engine.storage.vector import LocalVectorStore

__all__ = [
    "AuditStorage",
    "CategoryStorage",
    "ChangeStorage",
    "CognitiveStorageBackend",
    "DatasetStorage",
    "DefaultRetrievalBackend",
    "DimensionStorage",
    "DualWriteCoordinator",
    "EntityInstance",
    "EntityStorage",
    "GraphQueryError",
    "GraphStoreBackend",
    "HybridSearchResult",
    "LadybugGraphStore",
    "LocalVectorStore",
    "MetricStorage",
    "NetworkXGraphStore",
    "RelationInstance",
    "RetrievalBackend",
    "SQLiteStorage",
    "StorageBackend",
    "StorageConfig",
    "StorageError",
    "VectorSearchResult",
    "VectorStoreBackend",
    "VersionStorage",
    "create_graph_store",
    "create_meta_store",
    "create_vector_store",
]

try:
    from ontology_engine.storage.vector.chroma_store import ChromaVectorStore

    __all__.append("ChromaVectorStore")
except ImportError:
    ChromaVectorStore = None  # type: ignore[assignment, misc]
