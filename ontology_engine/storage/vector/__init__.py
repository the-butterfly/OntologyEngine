"""Vector storage backends."""

from ontology_engine.storage.vector.local_vector_store import LocalVectorStore

__all__ = ["LocalVectorStore"]

try:
    from ontology_engine.storage.vector.chroma_store import ChromaVectorStore  # noqa: F401

    __all__.append("ChromaVectorStore")
except ImportError:
    pass
