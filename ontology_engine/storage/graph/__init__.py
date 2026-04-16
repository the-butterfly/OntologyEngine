# ontology_engine/storage/graph/__init__.py
"""Graph storage backends."""

from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore
from ontology_engine.storage.graph.networkx_store import NetworkXGraphStore

__all__ = ["KuzuGraphStore", "NetworkXGraphStore"]
