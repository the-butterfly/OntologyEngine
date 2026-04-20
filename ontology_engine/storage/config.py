# ontology_engine/storage/config.py
"""Storage configuration model and factory functions.

Provides StorageConfig for unified storage layer configuration,
and factory functions for creating storage instances without
direct dependency on concrete implementations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ontology_engine.storage.base import GraphStoreBackend, StorageBackend, VectorStoreBackend


@dataclass
class StorageConfig:
    """Unified storage configuration.

    Supports local/cloud mode switching and per-engine configuration.
    Environment variables override defaults with OE_STORAGE_ prefix.

    Attributes:
        mode: "local" or "cloud".
        graph_backend: Graph engine name ("kuzu" or "networkx").
        vector_backend: Vector engine name ("chroma" or "local").
        meta_backend: Meta engine name ("sqlite").
        data_dir: Base data directory.
        kuzu_db_path: KuzuDB database file path.
        chroma_persist_dir: ChromaDB persistence directory.
        chroma_embedding_model: Embedding model name.
        chroma_embedding_dimension: Embedding vector dimension.
        sqlite_db_path: SQLite database file path.
        openai_api_key: OpenAI API key for embeddings.
        learning_rate: Feedback weight learning rate.
        semantic_weight: Default semantic search weight.
    """

    mode: str = "local"

    graph_backend: str = "kuzu"
    vector_backend: str = "local"
    meta_backend: str = "sqlite"

    data_dir: str = os.path.join(os.path.expanduser("~/.ontology_engine"), "data")

    kuzu_db_path: str = ""
    chroma_persist_dir: str = ""
    chroma_embedding_model: str = ""
    chroma_embedding_dimension: int = 1536

    sqlite_db_path: str = ""

    openai_api_key: str | None = None

    learning_rate: float = 0.1
    semantic_weight: float = 0.7

    def __post_init__(self) -> None:
        if not self.kuzu_db_path:
            self.kuzu_db_path = os.path.join(self.data_dir, "ontology.kuzu")
        if not self.chroma_persist_dir:
            self.chroma_persist_dir = os.path.join(self.data_dir, "vectors")
        if not self.sqlite_db_path:
            self.sqlite_db_path = os.path.join(self.data_dir, "meta.db")
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")

    @classmethod
    def from_env(cls) -> StorageConfig:
        """Create config from environment variables."""
        return cls(
            mode=os.environ.get("OE_STORAGE_MODE", "local"),
            graph_backend=os.environ.get("OE_STORAGE_GRAPH_BACKEND", "kuzu"),
            vector_backend=os.environ.get("OE_STORAGE_VECTOR_BACKEND", "local"),
            meta_backend=os.environ.get("OE_STORAGE_META_BACKEND", "sqlite"),
            data_dir=os.environ.get(
                "OE_STORAGE_DATA_DIR",
                os.path.join(os.path.expanduser("~/.ontology_engine"), "data"),
            ),
            openai_api_key=os.environ.get("OE_STORAGE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            learning_rate=float(os.environ.get("OE_STORAGE_LEARNING_RATE", "0.1")),
            semantic_weight=float(os.environ.get("OE_STORAGE_SEMANTIC_WEIGHT", "0.7")),
        )


def create_meta_store(config: StorageConfig | None = None) -> StorageBackend:
    """Create a MetaStore (StorageBackend) instance.

    Args:
        config: Storage configuration. Uses defaults if None.

    Returns:
        StorageBackend instance.
    """
    from ontology_engine.storage.sqlite.store import SQLiteStorage

    cfg = config or StorageConfig()
    if cfg.meta_backend == "sqlite":
        return SQLiteStorage(db_path=cfg.sqlite_db_path)
    raise ValueError(f"Unsupported meta backend: {cfg.meta_backend}")


def create_graph_store(config: StorageConfig | None = None) -> GraphStoreBackend:
    """Create a GraphStore instance.

    Args:
        config: Storage configuration. Uses defaults if None.

    Returns:
        GraphStoreBackend instance.
    """
    from ontology_engine.storage.graph.networkx_store import NetworkXGraphStore

    cfg = config or StorageConfig()
    if cfg.graph_backend == "kuzu":
        from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore

        return KuzuGraphStore()
    elif cfg.graph_backend == "networkx":
        return NetworkXGraphStore()
    raise ValueError(f"Unsupported graph backend: {cfg.graph_backend}")


def create_vector_store(config: StorageConfig | None = None) -> VectorStoreBackend:
    """Create a VectorStore instance.

    Args:
        config: Storage configuration. Uses defaults if None.

    Returns:
        VectorStoreBackend instance.
    """
    from ontology_engine.storage.vector.local_vector_store import LocalVectorStore

    cfg = config or StorageConfig()
    if cfg.vector_backend == "chroma":
        try:
            from ontology_engine.storage.vector.chroma_store import ChromaVectorStore

            return ChromaVectorStore(
                persist_dir=cfg.chroma_persist_dir,
                openai_api_key=cfg.openai_api_key,
                embedding_model=cfg.chroma_embedding_model or None,
            )
        except ImportError:
            pass
    elif cfg.vector_backend == "local":
        return LocalVectorStore()
    return LocalVectorStore()
