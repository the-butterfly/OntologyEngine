"""Storage abstractions shared by engine and service layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class StorageError(Exception):
    """Storage operation error."""


@dataclass
class EntityInstance:
    """Entity instance with fact object type and payload data."""

    _fact_object: str
    entity_id: str
    data: dict[str, Any]

    @property
    def concept(self) -> str:
        """Backward-compatible alias for _fact_object."""
        return self._fact_object


@dataclass
class RelationInstance:
    """Relation between two entities."""

    relation_name: str
    from_entity_id: str
    to_entity_id: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def relation_type(self) -> str:
        """Backward-compatible alias for relation_name."""
        return self.relation_name


class StorageBackend(ABC):
    """Abstract storage contract for analysis and visualization layers."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize storage resources."""

    @abstractmethod
    async def close(self) -> None:
        """Release storage resources."""

    @abstractmethod
    async def save_entity(self, entity: EntityInstance) -> str:
        """Persist an entity and return its identifier."""

    @abstractmethod
    async def get_entity(self, fact_object: str, entity_id: str) -> EntityInstance | None:
        """Load one entity by fact object type and identifier."""

    @abstractmethod
    async def get_entity_by_id(self, entity_id: str) -> EntityInstance | None:
        """Load one entity by identifier only (across all fact object types)."""

    @abstractmethod
    async def query_entities(
        self,
        fact_object: str | None,
        filters: dict[str, Any] | None = None,
    ) -> list[EntityInstance]:
        """Query entities, optionally across all fact object types."""

    @abstractmethod
    async def save_relation(self, relation: RelationInstance) -> None:
        """Persist a relation."""

    @abstractmethod
    async def get_relations(
        self,
        from_entity_id: str,
        relation_name: str | None = None,
    ) -> list[RelationInstance]:
        """Load relations from one entity."""

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        relation_name: str,
        direction: str = "outgoing",
    ) -> list[tuple[EntityInstance, RelationInstance]]:
        """Traverse one hop of graph neighbors."""

    @abstractmethod
    async def save_metric(self, entity_id: str, metric_name: str, value: Any) -> None:
        """Persist computed metric values."""

    @abstractmethod
    async def get_metric(self, entity_id: str, metric_name: str) -> Any | None:
        """Load one computed metric value."""

    @abstractmethod
    async def save_category_tags(self, entity_id: str, tags: dict[str, str]) -> None:
        """Persist categorization tags."""

    @abstractmethod
    async def get_category_tags(self, entity_id: str) -> dict[str, str] | None:
        """Load categorization tags for one entity."""

    @abstractmethod
    async def log_rule_execution(self, entity_id: str, rule_id: str, result: str) -> None:
        """Persist rule execution audit records."""

    @abstractmethod
    async def get_rule_execution_log(
        self,
        entity_id: str,
        rule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query rule execution audit records for an entity."""

    # -------------------------------------------------------------------------
    # Phase 1 Enhancement: Dataset Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_dataset(
        self,
        dataset_id: str,
        name: str,
        scope: dict[str, Any] | None = None,
        source_type: str = "manual",
        description: str | None = None,
    ) -> None:
        """Create a new dataset."""

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Get a dataset by ID."""

    @abstractmethod
    async def list_datasets(self) -> list[dict[str, Any]]:
        """List all datasets."""

    @abstractmethod
    async def update_dataset(
        self,
        dataset_id: str,
        name: str | None = None,
        description: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> bool:
        """Update a dataset."""

    @abstractmethod
    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and its memberships."""

    @abstractmethod
    async def add_entity_to_dataset(
        self,
        entity_id: str,
        dataset_id: str,
        fact_object: str,
        is_primary: bool = False,
        source_line: int | None = None,
    ) -> None:
        """Add an entity to a dataset."""

    @abstractmethod
    async def get_dataset_entities(
        self,
        dataset_id: str,
        fact_object: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get entities in a dataset."""

    @abstractmethod
    async def remove_entity_from_dataset(self, entity_id: str, dataset_id: str) -> None:
        """Remove an entity from a dataset."""

    @abstractmethod
    async def create_snapshot(
        self,
        snapshot_id: str,
        dataset_id: str,
        entity_count: int | None = None,
        relation_count: int | None = None,
        description: str | None = None,
    ) -> None:
        """Create a dataset snapshot."""

    @abstractmethod
    async def get_snapshots(self, dataset_id: str) -> list[dict[str, Any]]:
        """Get snapshots for a dataset."""

    # -------------------------------------------------------------------------
    # Phase 1 Enhancement: Dimension Applicability & Category Rule Mapping
    # -------------------------------------------------------------------------

    @abstractmethod
    async def save_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str,
        required: bool = False,
        auto_categorize: bool = True,
        source_attribute: str | None = None,
    ) -> None:
        """Save dimension applicability mapping."""

    @abstractmethod
    async def get_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get dimension applicability entries."""

    @abstractmethod
    async def delete_dimension_applicability(self, dimension_id: str, object_type: str) -> None:
        """Delete a dimension applicability entry."""

    @abstractmethod
    async def save_category_rule_mapping(
        self,
        dimension_id: str,
        dimension_value: str,
        rule_group_id: str,
        mapping_type: str = "applicable",
        override_rule_id: str | None = None,
        override_field: str | None = None,
        override_value: Any = None,
    ) -> None:
        """Save a category-to-rule mapping."""

    @abstractmethod
    async def get_category_rule_mappings(
        self,
        dimension_id: str | None = None,
        dimension_value: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get category rule mappings."""

    @abstractmethod
    async def delete_category_rule_mapping(
        self,
        dimension_id: str,
        dimension_value: str,
        rule_group_id: str,
    ) -> None:
        """Delete a category rule mapping."""

    # -------------------------------------------------------------------------
    # Phase 1 Enhancement: Incremental Update
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_change_batch(
        self,
        batch_id: str,
        dataset_id: str | None = None,
        entity_count: int | None = None,
    ) -> None:
        """Create a new change batch."""

    @abstractmethod
    async def update_change_batch(
        self,
        batch_id: str,
        status: str | None = None,
        created_count: int | None = None,
        updated_count: int | None = None,
        deleted_count: int | None = None,
        unchanged_count: int | None = None,
    ) -> None:
        """Update a change batch."""

    @abstractmethod
    async def get_change_batch(self, batch_id: str) -> dict[str, Any] | None:
        """Get a change batch by ID."""

    @abstractmethod
    async def list_change_batches(
        self,
        dataset_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List change batches."""

    @abstractmethod
    async def save_entity_changes(
        self,
        batch_id: str,
        entity_id: str,
        fact_object: str,
        change_type: str,
        field_changes: list[dict[str, Any]] | None = None,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
    ) -> None:
        """Save entity changes for a batch."""

    @abstractmethod
    async def get_entity_changes(self, batch_id: str) -> list[dict[str, Any]]:
        """Get entity changes for a batch."""

    @abstractmethod
    async def save_entity_version(
        self,
        entity_id: str,
        fact_object: str,
        version: int,
        data: dict[str, Any],
        updated_by: str = "system",
    ) -> None:
        """Save an entity version snapshot."""

    @abstractmethod
    async def get_entity_version(
        self,
        entity_id: str,
        version: int | None = None,
    ) -> dict[str, Any] | None:
        """Get entity version(s)."""

    @abstractmethod
    async def list_entity_versions(self, entity_id: str) -> list[dict[str, Any]]:
        """List all versions for an entity."""

    @abstractmethod
    async def delete_entity_version(self, entity_id: str, version: int) -> None:
        """Delete a specific entity version."""

    @abstractmethod
    async def get_entity_at(
        self,
        entity_id: str,
        as_of: Any,
    ) -> EntityInstance | None:
        """Get entity state at a specific point in time.

        Args:
            entity_id: Entity identifier
            as_of: Timestamp for point-in-time query

        Returns:
            EntityInstance if found at that time, None otherwise
        """

    @abstractmethod
    async def get_entity_history(
        self,
        entity_id: str,
    ) -> list[EntityInstance]:
        """Get all historical versions of an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            List of EntityInstance objects ordered by valid_from
        """


class GraphQueryError(StorageError):
    """Graph query execution error."""
    pass


class GraphStoreBackend(ABC):
    """Abstract interface for graph-native storage.

    Provides graph topology storage and query capabilities.
    Orthogonal to StorageBackend: StorageBackend handles entity/relation
    attribute storage, GraphStoreBackend handles graph topology queries.
    """

    @abstractmethod
    async def initialize(self, db_path: str | None = None) -> None:
        """Initialize graph storage.

        Args:
            db_path: Graph database file path. None means in-memory.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""

    # --- Node Management ---
    @abstractmethod
    async def upsert_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> None:
        """Create or update a node."""

    @abstractmethod
    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a single node by ID."""

    @abstractmethod
    async def delete_node(self, node_id: str) -> None:
        """Delete a node and all its edges."""

    # --- Edge Management ---
    @abstractmethod
    async def upsert_edge(
        self,
        edge_id: str,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create or update an edge."""

    @abstractmethod
    async def get_edges(
        self,
        from_node_id: str | None = None,
        to_node_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query edges."""

    @abstractmethod
    async def delete_edge(self, edge_id: str) -> None:
        """Delete an edge."""

    # --- Graph Queries ---
    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
        node_concept: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node.

        Args:
            node_concept: Optional concept filter applied at the storage layer
                         (e.g. kuzu WHERE n.concept = ...). Ignored if not supported.
        """

    @abstractmethod
    async def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_depth: int = 3,
        edge_types: list[str] | None = None,
    ) -> list[list[dict[str, Any]]]:
        """Find paths between nodes."""

    @abstractmethod
    async def detect_cycles(
        self,
        center_id: str,
        edge_types: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[list[str]]:
        """Detect cycles starting from a node."""

    @abstractmethod
    async def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query (advanced interface)."""

    # --- Graph Algorithms ---
    @abstractmethod
    async def compute_graph_metric(
        self,
        algorithm: str,
        node_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a graph algorithm (centrality, community, etc.)."""

    # --- Batch Operations ---
    @abstractmethod
    async def batch_upsert(
        self,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Batch write nodes and edges.

        Returns:
            {"nodes_written": N, "edges_written": M}
        """


# ============================================================================
# Vector Storage
# ============================================================================

@dataclass
class VectorSearchResult:
    """Result from a vector search operation."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """Result from a hybrid search operation with observability into intermediate scores.

    Attributes:
        results: Final fused results ordered by relevance.
        semantic_scores: Per-entity cosine similarity scores from vector search.
        graph_scores: Per-entity graph proximity scores from BFS expansion.
        path_match_scores: Per-entity path pattern match scores (0/1 for unweighted,
                          normalized weight for weighted edges, max across multiple paths).
        fusion_metadata: Strategy name, weights used, candidate counts, etc.
    """

    results: list[VectorSearchResult]
    semantic_scores: dict[str, float] = field(default_factory=dict)
    graph_scores: dict[str, float] = field(default_factory=dict)
    path_match_scores: dict[str, float] = field(default_factory=dict)
    fusion_metadata: dict[str, Any] = field(default_factory=dict)


class VectorStoreBackend(ABC):
    """Abstract interface for vector storage and ANN search.

    Target implementation uses Faiss for approximate nearest neighbor search
    with sentence-transformers embeddings. See ``LocalVectorStore`` for a
    placeholder in-memory implementation that can be used until Faiss is
    integrated (Phase 2 prerequisite).
    """

    @abstractmethod
    async def initialize(self, dimension: int) -> None:
        """Initialize vector storage.

        Args:
            dimension: Dimensionality of embedding vectors.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""

    @abstractmethod
    async def add_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add or update vectors.

        Args:
            ids: Unique identifiers for the vectors.
            vectors: Embedding vectors (each length == dimension).
            metadata: Optional metadata dict per vector.
        """

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search for nearest neighbors.

        Args:
            query_vector: Query embedding vector.
            top_k: Maximum number of results.
            filters: Optional metadata filter (exact match).

        Returns:
            List of search results ordered by relevance (higher score = better).
        """

    @abstractmethod
    async def delete_vectors(self, ids: list[str]) -> None:
        """Remove vectors by identifier."""


# ============================================================================
# Unified Retrieval (Repository) Layer
# ============================================================================

class RetrievalBackend(ABC):
    """Unified retrieval facade that coordinates storage backends.

    Phase 2 design goal: MetaStore (entity/attribute) + GraphStore (topology)
    + VectorStore (semantics) work together through a single repository
    interface.  This is the abstraction referenced in
    ``docs/05-schema-v2/query-engine-target.md`` as the "统一 Repository 接口".
    """

    @abstractmethod
    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
        fact_object: str | None = None,
    ) -> list[VectorSearchResult]:
        """Pure vector/semantic search.

        Args:
            query_text: Raw text query.
            top_k: Maximum number of results.
            fact_object: Optional fact object type filter.

        Returns:
            Vector search results.
        """

    @abstractmethod
    async def hybrid_search(
        self,
        query_text: str | None = None,
        query_vector: list[float] | None = None,
        graph_seed_id: str | None = None,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        graph_weight: float = 0.4,
        fusion_strategy: str = "independent_then_fuse",
        path_pattern: list[tuple[str, str]] | None = None,
        path_weight: float = 0.2,
    ) -> HybridSearchResult:
        """Hybrid retrieval combining semantic, graph, and optional path signals.

        Args:
            query_text: Optional raw text query (used to derive embedding).
            query_vector: Optional pre-computed query embedding.
            graph_seed_id: Optional seed entity for graph expansion.
            top_k: Maximum number of results.
            semantic_weight: Weight for vector scores.
            graph_weight: Weight for graph proximity scores.
            fusion_strategy: One of ``filter_then_fuse``, ``independent_then_fuse``,
                            ``fuse_then_filter``.
            path_pattern: Optional sequence of (relation_type, target_concept) tuples.
            path_weight: Weight for path match scores.

        Returns:
            HybridSearchResult with fused results and intermediate scores.
        """

    @abstractmethod
    async def graph_pattern_match(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Graph DSL pattern match (e.g. Company -(guarantees)-> Company).

        Args:
            start_concept: Starting node concept type.
            path_pattern: Sequence of (relation_type, target_concept) tuples.
            start_filters: Optional attribute filters on the start node.
            limit: Maximum result count.

        Returns:
            Matched paths with node details.
        """