"""Unified CognitiveNode storage interface and routing.

P0-1: StorageInterface abstract layer — replaces the multi-interface
CognitiveStorageBackend pattern with a single unified interface that
automatically routes by memory_type to the correct storage engine.

Boundary: engine/cognitive/ -> storage/cognitive_interface.py

DEPRECATED: Use CognitiveStorageBackend from ontology_engine.storage.base instead.
StorageInterface is kept for backward compatibility and will be removed in a future version.
CognitiveStorageBackend in base.py is the canonical interface for cognitive storage operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ontology_engine.storage.models import VALID_MEMORY_TYPES


# ============================================================================
# Search types
# ============================================================================


@dataclass
class SearchQuery:
    """Query parameters for hybrid search.

    Attributes:
        query_text: Natural language search text.
        space_id: Memory space to search within.
        top_k: Maximum number of results.
        memory_type: Optional filter by memory type.
        cognitive_layer: Optional filter by cognitive layer.
        tags_filter: Optional tag-based filtering (exact match on dict keys/values).
        belief_status: Optional filter by belief status.
        vector: Pre-computed query embedding vector.
    """

    query_text: str
    space_id: str
    top_k: int = 10
    memory_type: str | None = None
    cognitive_layer: str | None = None
    tags_filter: dict[str, Any] | None = None
    belief_status: str | None = None
    vector: list[float] | None = None


@dataclass
class SearchResult:
    """Result from a hybrid search operation.

    Attributes:
        nodes: Final fused CognitiveNode results ordered by relevance.
        scores: Per-node final relevance score (node_id → score).
        semantic_scores: Per-node semantic/vector similarity scores.
        keyword_scores: Per-node keyword/FTS/BM25 scores.
        fusion_metadata: Strategy name, RRF parameters, candidate counts, etc.
    """

    nodes: list[Any]  # list[CognitiveNode] — deferred import to avoid cycle
    scores: dict[str, float] = field(default_factory=dict)
    semantic_scores: dict[str, float] = field(default_factory=dict)
    keyword_scores: dict[str, float] = field(default_factory=dict)
    fusion_metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Storage routing
# ============================================================================


class StorageRouting:
    """Route memory_type to target storage engines.

    Each memory_type maps to one or more stores:
    - "sqlite": structured data (CognitiveNode fields)
    - "chromadb": vector embeddings (semantic search)

    Routing table from plan §P0-1:
        fragment     → chromadb only (pure vector, not stored in SQLite)
        entity       → sqlite + chromadb (structured + entity_name vector)
        relation     → sqlite + chromadb (structured + edge_text vector)
        observation  → sqlite only
        mental_model → sqlite only
        episode      → sqlite only
        procedure    → sqlite only
        rule         → sqlite only
        opinion      → sqlite only
        metrics      → sqlite only
        OE extensions (commitment, constraint, self_experience, task_state) → sqlite only
    """

    ROUTING: dict[str, list[str]] = {
        # D-S2 core 10 types
        "fragment":     ["chromadb"],
        "entity":       ["sqlite", "chromadb"],
        "relation":     ["sqlite", "chromadb"],
        "observation":  ["sqlite"],
        "mental_model": ["sqlite"],
        "episode":      ["sqlite"],
        "procedure":    ["sqlite"],
        "rule":         ["sqlite"],
        "opinion":      ["sqlite"],
        "metrics":      ["sqlite"],
        # OE extensions
        "commitment":      ["sqlite"],
        "constraint":      ["sqlite"],
        "self_experience": ["sqlite"],
        "task_state":      ["sqlite"],
    }

    @classmethod
    def get_stores(cls, memory_type: str) -> list[str]:
        """Return list of store names for the given memory_type.

        Args:
            memory_type: One of the 14 valid memory types.

        Returns:
            List of store names (e.g., ["sqlite", "chromadb"]).

        Raises:
            ValueError: If memory_type is not recognized.
        """
        stores = cls.ROUTING.get(memory_type)
        if stores is None:
            raise ValueError(f"Unknown memory_type: {memory_type!r}. Valid types: {sorted(cls.ROUTING)}")
        return stores

    @classmethod
    def supports_store(cls, memory_type: str, store: str) -> bool:
        """Check if the given memory_type routes to the specified store.

        Args:
            memory_type: Memory type to check.
            store: Store name (e.g., "sqlite", "chromadb").

        Returns:
            True if the memory_type uses the specified store.
        """
        return store in cls.get_stores(memory_type)

    @classmethod
    def all_memory_types(cls) -> list[str]:
        """Return all known memory types in sorted order."""
        return sorted(cls.ROUTING.keys())

    @classmethod
    def all_stores(cls) -> set[str]:
        """Return all unique store names used across all memory types."""
        return {store for stores in cls.ROUTING.values() for store in stores}


# ============================================================================
# Storage interface
# ============================================================================


class StorageInterface(ABC):
    """Unified CognitiveNode storage interface.

    .. deprecated::
        Use ``CognitiveStorageBackend`` from ``ontology_engine.storage.base``
        instead.  ``StorageInterface`` is kept for backward compatibility and
        will be removed in a future version.

    Replaces the current multi-interface CognitiveStorageBackend pattern.
    Exposes consistent storage operations to MemoryService and
    CognitiveRepository, internally routing by memory_type to the correct
    storage engine (SQLite for structured data, ChromaDB for vectors).

    Usage:
        interface = CognitiveStorageImpl(...)  # concrete implementation
        node_id = await interface.save_node(node)
        result = await interface.search(SearchQuery(query_text="...", space_id="default"))
    """

    @abstractmethod
    async def save_node(self, node: Any) -> str:  # Any = CognitiveNode
        """Save a CognitiveNode, returning its ID.

        Automatically routes to the correct storage engine(s) based on
        node.memory_type via StorageRouting.

        Args:
            node: CognitiveNode to persist.

        Returns:
            The node's unique identifier.
        """

    @abstractmethod
    async def get_node(self, node_id: str) -> Any | None:  # Any = CognitiveNode
        """Retrieve a CognitiveNode by ID.

        Args:
            node_id: Unique node identifier.

        Returns:
            CognitiveNode if found, None otherwise.
        """

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResult:
        """Hybrid search combining vector + keyword + metadata filtering.

        Uses RRF (Reciprocal Rank Fusion) to merge results from multiple
        retrieval paths (ChromaDB semantic search, SQLite FTS5/BM25).

        Args:
            query: SearchQuery with text, filters, and optional pre-computed vector.

        Returns:
            SearchResult with fused nodes, scores, and metadata.
        """

    @abstractmethod
    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        """Delete a CognitiveNode.

        Args:
            node_id: Unique node identifier.
            soft: If True (default), mark as superseded_by='deleted'.
                  If False, permanently remove from storage.
        """

    @abstractmethod
    async def batch_save(self, nodes: list[Any]) -> list[str]:  # Any = CognitiveNode
        """Batch save multiple CognitiveNodes.

        Args:
            nodes: List of CognitiveNodes to persist.

        Returns:
            List of node IDs in the same order as input.
        """

    @abstractmethod
    async def count(self, filter: dict[str, Any]) -> int:
        """Count nodes matching the given filter criteria.

        Args:
            filter: Dictionary of field_name → value pairs.
                    Supports: memory_type, cognitive_layer, space_id,
                    belief_status, tags (partial match).

        Returns:
            Number of matching nodes.
        """

    async def traverse(
        self,
        node_id: str,
        relation: str | None = None,
        depth: int = 2,
    ) -> list[Any]:  # Any = CognitiveNode
        """Graph traversal from a starting node.

        Delegates to the graph engine (Ladybug). Falls back to SQLite
        association queries if graph engine is unavailable.

        Args:
            node_id: Starting node ID.
            relation: Optional edge type filter (e.g., "PART_OF").
            depth: Maximum traversal depth (default: 2).

        Returns:
            List of reachable CognitiveNodes.
        """
        return []

    async def list_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[Any]:  # list[CognitiveNode]
        """List CognitiveNodes with optional filters.

        Args:
            memory_type: Filter by memory type.
            cognitive_layer: Filter by cognitive layer.
            belief_status: Filter by belief status.
            domain_id: Filter by domain ID.
            space_id: Filter by space ID.
            limit: Maximum number of results.
            as_of: Temporal query — only return nodes valid at this timestamp.

        Returns:
            List of matching CognitiveNodes.
        """
        raise NotImplementedError

    async def update_node_with_occ(
        self,
        node_id: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> Any | None:
        """Update a CognitiveNode with optimistic concurrency control.

        Args:
            node_id: Unique node identifier.
            expected_version: Expected current version for OCC check.
            updates: Dictionary of field names to new values.

        Returns:
            Updated CognitiveNode if version matched, None if conflict.
        """
        raise NotImplementedError

    async def save_disposition(self, profile_data: dict[str, Any]) -> None:
        """Create or update a DispositionProfile.

        Args:
            profile_data: Dictionary of DispositionProfile fields.
        """
        raise NotImplementedError

    async def get_disposition(
        self,
        profile_id: str | None = None,
        scene: str | None = None,
        domain_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get a DispositionProfile by ID or scene.

        Args:
            profile_id: Unique identifier for the disposition profile.
            scene: Scene/context to filter by.
            domain_id: Domain identifier to filter by.

        Returns:
            Dictionary with profile properties, or None if not found.
        """
        raise NotImplementedError

    async def compute_dynamic_weights(
        self, profile: dict[str, Any]
    ) -> dict[str, float]:
        """Compute dynamic type weights based on a DispositionProfile.

        Args:
            profile: DispositionProfile dictionary.

        Returns:
            Dictionary of memory_type -> weight.
        """
        raise NotImplementedError

    async def save_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an edge between two CognitiveNodes.

        Args:
            edge_type: Type of edge (PART_OF, SUPPORTS, CONTRADICTS, etc.).
            from_id: Source CognitiveNode ID.
            to_id: Target CognitiveNode ID.
            properties: Optional edge properties.

        Returns:
            Created edge record.
        """
        raise NotImplementedError

    async def list_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query cognitive edges with optional filters.

        Args:
            from_id: Filter by source node ID.
            to_id: Filter by target node ID.
            edge_type: Filter by edge type.
            limit: Maximum number of edges to return.

        Returns:
            List of matching edge records.
        """
        raise NotImplementedError


assert set(StorageRouting.ROUTING.keys()) == set(VALID_MEMORY_TYPES), \
    f"StorageRouting mismatch: missing={set(VALID_MEMORY_TYPES) - set(StorageRouting.ROUTING.keys())}, extra={set(StorageRouting.ROUTING.keys()) - set(VALID_MEMORY_TYPES)}"
