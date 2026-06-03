"""Storage abstractions shared by engine and service layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class StorageError(Exception):
    """Storage operation error."""


@dataclass
class EntityInstance:
    """Entity instance with fact object type and payload data.

    Aligned with docs/02-design/schema/instance-layer.md EntityInstance.
    """

    _fact_object: str
    entity_id: str
    data: dict[str, Any]
    layer: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = 1.0
    source_pipeline: str | None = None
    source_content_hash: str | None = None
    feedback_weight: float = 0.5
    domain_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def concept(self) -> str:
        """Backward-compatible alias for _fact_object."""
        return self._fact_object


@dataclass
class RelationInstance:
    """Relation between two entities.

    Aligned with docs/02-design/schema/instance-layer.md EdgeInstance.
    """

    relation_name: str
    from_entity_id: str
    to_entity_id: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    edge_text: str | None = None
    weight: float = 1.0
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = 1.0
    source_pipeline: str | None = None
    source_content_hash: str | None = None

    @property
    def relation_type(self) -> str:
        """Backward-compatible alias for relation_name."""
        return self.relation_name


@dataclass
class MetricValue:
    """Computed metric value for an entity.

    Aligned with docs/02-design/schema/instance-layer.md MetricValue.
    """

    entity_id: str
    metric_name: str
    value: Any
    computed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    computed_by: str | None = None
    computation_snapshot: dict[str, Any] | None = None


@dataclass
class KnowledgeFragment:
    """Layer-R storage unit for raw text chunks.

    Aligned with docs/02-design/schema/instance-layer.md KnowledgeFragment.
    """

    id: str | None = None
    dataset_id: str | None = None
    document_id: str | None = None
    chunk_index: int | None = None
    offset_start: int | None = None
    offset_end: int | None = None
    text: str = ""
    vector_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_status: str = "pending"
    content_hash: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class FeedbackRecord:
    """User feedback on entity/metric results.

    Supports confirm, override, and dispute feedback types.
    """

    record_id: str
    entity_id: str
    metric_name: str | None = None
    feedback_type: str = "confirm"
    value: float = 1.0
    previous_weight: float = 1.0
    updated_weight: float = 1.0
    source: str = "user"
    text_feedback: str | None = None
    applied: bool = False
    created_at: datetime | None = None


@dataclass
class CategoryTag:
    """Category assignment tag for an entity.

    Maps an entity to a dimension value, recording how and when
    the assignment was made.
    """

    entity_id: str
    dimension_name: str
    value_code: str
    assigned_at: datetime | None = None
    assigned_by: str = "rule"
    confidence: float = 1.0


class EntityStorage(ABC):
    """Internal mixin — entity and relation CRUD operations.

    Not intended to be used directly. Use ``CoreStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def save_entity(self, entity: EntityInstance) -> str: ...

    @abstractmethod
    async def get_entity(self, fact_object: str, entity_id: str) -> EntityInstance | None: ...

    @abstractmethod
    async def get_entity_by_id(self, entity_id: str) -> EntityInstance | None: ...

    @abstractmethod
    async def query_entities(
        self,
        fact_object: str | None,
        filters: dict[str, Any] | None = None,
    ) -> list[EntityInstance]: ...

    @abstractmethod
    async def delete_entity(self, fact_object: str, entity_id: str) -> bool: ...

    @abstractmethod
    async def save_relation(self, relation: RelationInstance) -> None: ...

    @abstractmethod
    async def get_relations(
        self,
        from_entity_id: str,
        relation_name: str | None = None,
    ) -> list[RelationInstance]: ...

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        relation_name: str,
        direction: str = "outgoing",
        as_of: str | None = None,
        include_history: bool = False,
    ) -> list[tuple[EntityInstance, RelationInstance]]: ...


class MetricStorage(ABC):
    """Internal mixin — metric read/write operations.

    Not intended to be used directly. Use ``CoreStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def save_metric(self, entity_id: str, metric_name: str, value: Any) -> None: ...

    @abstractmethod
    async def get_metric(self, entity_id: str, metric_name: str) -> Any | None: ...


class CategoryStorage(ABC):
    """Internal mixin — category tag operations.

    Not intended to be used directly. Use ``CoreStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def save_category_tag(self, tag: CategoryTag) -> None: ...

    @abstractmethod
    async def get_category_tags(
        self, entity_id: str, dimension_name: str | None = None
    ) -> list[CategoryTag]: ...

    @abstractmethod
    async def delete_category_tag(
        self, entity_id: str, dimension_name: str, value_code: str
    ) -> bool: ...

    @abstractmethod
    async def save_category_tags(self, entity_id: str, tags: dict[str, str]) -> None: ...

    @abstractmethod
    async def get_category_tags_dict(self, entity_id: str) -> dict[str, str] | None: ...


class DatasetStorage(ABC):
    """Internal mixin — dataset and snapshot operations.

    Not intended to be used directly. Use ``AdminStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def create_dataset(
        self,
        dataset_id: str,
        name: str,
        scope: dict[str, Any] | None = None,
        source_type: str = "manual",
        description: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list_datasets(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update_dataset(
        self,
        dataset_id: str,
        name: str | None = None,
        description: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> bool: ...

    @abstractmethod
    async def delete_dataset(self, dataset_id: str) -> bool: ...

    @abstractmethod
    async def add_entity_to_dataset(
        self,
        entity_id: str,
        dataset_id: str,
        fact_object: str,
        is_primary: bool = False,
        source_line: int | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_dataset_entities(
        self,
        dataset_id: str,
        fact_object: str | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def remove_entity_from_dataset(self, entity_id: str, dataset_id: str) -> None: ...

    @abstractmethod
    async def create_snapshot(
        self,
        snapshot_id: str,
        dataset_id: str,
        entity_count: int | None = None,
        relation_count: int | None = None,
        description: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_snapshots(self, dataset_id: str) -> list[dict[str, Any]]: ...


class VersionStorage(ABC):
    """Internal mixin — entity versioning and temporal queries.

    Not intended to be used directly. Use ``AdminStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def save_entity_version(
        self,
        entity_id: str,
        fact_object: str,
        version: int,
        data: dict[str, Any],
        updated_by: str = "system",
    ) -> None: ...

    @abstractmethod
    async def get_entity_version(
        self,
        entity_id: str,
        version: int | None = None,
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list_entity_versions(self, entity_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete_entity_version(self, entity_id: str, version: int) -> None: ...

    @abstractmethod
    async def get_entity_at(
        self,
        entity_id: str,
        as_of: Any,
    ) -> EntityInstance | None: ...

    @abstractmethod
    async def get_entity_history(
        self,
        entity_id: str,
    ) -> list[EntityInstance]: ...


class AuditStorage(ABC):
    """Internal mixin — audit, feedback, and knowledge fragment operations.

    Not intended to be used directly. Use ``AdminStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def log_rule_execution(self, entity_id: str, rule_id: str, result: str) -> None: ...

    @abstractmethod
    async def get_rule_execution_log(
        self,
        entity_id: str,
        rule_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def save_feedback(self, feedback: FeedbackRecord) -> None: ...

    @abstractmethod
    async def get_feedback(
        self,
        entity_id: str,
        metric_name: str | None = None,
    ) -> list[FeedbackRecord]: ...

    @abstractmethod
    async def save_knowledge_fragment(self, fragment: KnowledgeFragment) -> str: ...

    @abstractmethod
    async def get_knowledge_fragment(self, fragment_id: str) -> KnowledgeFragment | None: ...

    @abstractmethod
    async def list_knowledge_fragments(
        self,
        dataset_id: str | None = None,
        extraction_status: str | None = None,
    ) -> list[KnowledgeFragment]: ...


class DimensionStorage(ABC):
    """Internal mixin — dimension applicability and category rule mapping.

    Not intended to be used directly. Use ``AdminStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def save_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str,
        required: bool = False,
        auto_categorize: bool = True,
        source_attribute: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete_dimension_applicability(self, dimension_id: str, object_type: str) -> None: ...

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
    ) -> None: ...

    @abstractmethod
    async def get_category_rule_mappings(
        self,
        dimension_id: str | None = None,
        dimension_value: str | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete_category_rule_mapping(
        self,
        dimension_id: str,
        dimension_value: str,
        rule_group_id: str,
    ) -> None: ...


class ChangeStorage(ABC):
    """Internal mixin — change batch and entity change tracking.

    Not intended to be used directly. Use ``AdminStorage`` or
    ``StorageBackend`` instead.
    """

    @abstractmethod
    async def create_change_batch(
        self,
        batch_id: str,
        dataset_id: str | None = None,
        entity_count: int | None = None,
    ) -> None: ...

    @abstractmethod
    async def update_change_batch(
        self,
        batch_id: str,
        status: str | None = None,
        created_count: int | None = None,
        updated_count: int | None = None,
        deleted_count: int | None = None,
        unchanged_count: int | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_change_batch(self, batch_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list_change_batches(
        self,
        dataset_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

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
    ) -> None: ...

    @abstractmethod
    async def get_entity_changes(self, batch_id: str) -> list[dict[str, Any]]: ...


class CoreStorage(EntityStorage, MetricStorage, CategoryStorage, ABC):
    """Core data operations — entity, metric, and category storage.

    Groups the most frequently used storage operations for data access
    layers that only need to read/write entities, metrics, and categories
    without depending on administrative concerns.

    Someone who only needs core data ops can depend on ``CoreStorage``
    instead of the full ``StorageBackend``, following the Interface
    Segregation Principle.
    """


class AdminStorage(DatasetStorage, VersionStorage, AuditStorage, DimensionStorage, ChangeStorage, ABC):
    """Administrative operations — dataset, version, audit, dimension, and change management.

    Groups storage operations that support governance, traceability, and
    lifecycle management.  These are typically used by admin/pipeline
    layers rather than by core data-access code.

    Future implementations can choose to implement only ``CoreStorage``
    for lightweight deployments and add ``AdminStorage`` as needed.
    """


class StorageBackend(
    CoreStorage,
    AdminStorage,
    ABC,
):
    """Abstract storage contract for analysis and visualization layers.

    Inherits from ``CoreStorage`` and ``AdminStorage``, which in turn
    compose the 7 internal mixin ABCs (EntityStorage, MetricStorage,
    CategoryStorage, DatasetStorage, VersionStorage, AuditStorage,
    DimensionStorage, ChangeStorage).
    """

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


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
    async def get_neighbors_basic(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node (generic graph parameters only).

        This is the pure graph-topology query without any domain-specific
        filtering.  Implementations should only consider graph structure
        (edge type, direction, property filters).

        Args:
            node_id: The node to find neighbors for.
            edge_type: Optional edge type filter.
            direction: "outgoing", "incoming", or "both".
            limit: Maximum number of results.
            filter_props: Optional edge property exact-match filters.

        Returns:
            List of neighbor dicts with at least: neighbor_id, edge_id,
            edge_type, direction.
        """

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
        node_concept: str | None = None,
        as_of: str | None = None,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node with optional cognitive filtering.

        By default, this method delegates to ``get_neighbors_basic()`` and
        then applies cognitive-layer filters (node_concept, as_of,
        include_history) on top.  Subclasses that can push these filters
        down to the storage layer (e.g. Ladybug) should override this
        method directly for better performance.

        Args:
            node_concept: Optional concept filter applied at the storage layer
                         (e.g. ladybug WHERE n.concept = ...). Ignored if not supported.
            as_of: Optional point-in-time timestamp for temporal filtering.
            include_history: If true, include all historical versions.
        """

    async def get_k_hop_neighbors(
        self,
        node_id: str,
        k: int = 2,
        edge_type: str | None = None,
        direction: str = "both",
        limit_per_hop: int = 100,
    ) -> dict[str, float]:
        """Get all neighbors within k hops of the given node.

        Default implementation uses BFS with ``get_neighbors()`` calls.
        Subclasses may override for more efficient native traversal.

        Args:
            node_id: Starting node ID.
            k: Number of hops (depth). Defaults to 2.
            edge_type: Optional edge type filter.
            direction: Traversal direction ("outgoing", "incoming", "both").
            limit_per_hop: Max neighbors per node per hop.

        Returns:
            Dict mapping neighbor_id → proximity score (1/(1+depth)).
            The seed node itself is NOT included.
        """
        visited: set[str] = {node_id}
        scores: dict[str, float] = {}
        queue = [node_id]
        depth = 0
        while queue and depth < k:
            next_queue: list[str] = []
            for nid in queue:
                neighbors = await self.get_neighbors(
                    node_id=nid,
                    edge_type=edge_type,
                    direction=direction,
                    limit=limit_per_hop,
                )
                for n in neighbors:
                    neighbor_id = n["neighbor_id"]
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_queue.append(neighbor_id)
                        scores[neighbor_id] = max(
                            scores.get(neighbor_id, 0.0),
                            1.0 / (1.0 + depth),
                        )
            queue = next_queue
            depth += 1
        return scores

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

    async def sync_entity(self, entity_id: str, entity_data: dict[str, Any], **kwargs: Any) -> None:
        """Sync an entity to the vector index.

        Default implementation: upsert with generic content and metadata.
        Subclasses (e.g. ChromaVectorStore) can override for custom
        collection routing and metadata mapping.

        Args:
            entity_id: Unique entity identifier.
            entity_data: Entity fields (name, summary, _fact_object, etc.).
            **kwargs: Subclass-specific parameters.
        """
        content = entity_data.get("content", entity_data.get("name", ""))
        metadata = entity_data.get("metadata", {})
        if content:
            await self.add_vectors(
                ids=[entity_id],
                vectors=[kwargs.get("vector", [])],
                metadata=[metadata] if metadata else None,
            )

    async def sync_relation(self, relation_id: str, relation_data: dict[str, Any], **kwargs: Any) -> None:
        """Sync a relation to the vector index.

        Default implementation: upsert with generic content and metadata.
        Subclasses (e.g. ChromaVectorStore) can override for custom
        collection routing and edge categorization.

        Args:
            relation_id: Unique relation identifier.
            relation_data: Relation fields (relation_name, edge_text, etc.).
            **kwargs: Subclass-specific parameters.
        """
        content = relation_data.get("content", relation_data.get("relation_name", ""))
        metadata = relation_data.get("metadata", {})
        if content:
            await self.add_vectors(
                ids=[relation_id],
                vectors=[kwargs.get("vector", [])],
                metadata=[metadata] if metadata else None,
            )


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


# ============================================================================
# Cognitive Storage
# ============================================================================

class CognitiveStorageBackend(ABC):
    """Abstract interface for cognitive memory storage.

    Provides domain-specific storage operations for CognitiveNode,
    CognitiveEdge, DispositionProfile, and activity log management.
    Orthogonal to StorageBackend/GraphStoreBackend/VectorStoreBackend:
    this backend encapsulates all cognitive-specific persistence concerns
    so that the engine/cognitive layer never depends on a concrete
    storage implementation directly.
    """

    @abstractmethod
    async def initialize(self, db_path: str | None = None) -> None:
        """Initialize cognitive storage resources.

        Args:
            db_path: Database file path. None means default location.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release cognitive storage resources."""

    # --- CognitiveNode Operations ---

    @abstractmethod
    async def save_cognitive_node(self, node_data: dict[str, Any]) -> None:
        """Create or update a CognitiveNode.

        Args:
            node_data: Dictionary of CognitiveNode fields.
        """

    @abstractmethod
    async def get_cognitive_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a CognitiveNode by ID.

        Args:
            node_id: Unique identifier for the cognitive node.

        Returns:
            Dictionary with node properties, or None if not found.
        """

    @abstractmethod
    async def list_cognitive_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query CognitiveNodes with filters.

        Args:
            memory_type: Filter by memory type.
            cognitive_layer: Filter by cognitive layer.
            belief_status: Filter by belief status.
            domain_id: Filter by domain ID.
            space_id: Filter by space ID.
            limit: Maximum number of results.
            as_of: Temporal query — only return nodes valid at this timestamp.

        Returns:
            List of matching CognitiveNode records.
        """

    @abstractmethod
    async def delete_cognitive_node(self, node_id: str) -> None:
        """Delete a CognitiveNode by ID.

        Args:
            node_id: Unique identifier for the cognitive node.
        """

    @abstractmethod
    async def update_cognitive_node_belief(
        self,
        node_id: str,
        new_belief: str,
        reason: str | None = None,
    ) -> None:
        """Update the belief status of a CognitiveNode.

        Args:
            node_id: Unique identifier for the cognitive node.
            new_belief: New belief status.
            reason: Optional reason for the belief change.
        """

    @abstractmethod
    async def update_cognitive_node_with_occ(
        self,
        node_id: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a CognitiveNode with optimistic concurrency control.

        Args:
            node_id: Unique identifier for the cognitive node.
            expected_version: Expected current version for OCC check.
            updates: Dictionary of field names to new values.

        Returns:
            Updated node data if version matched, None if conflict.
        """

    # --- CognitiveEdge Operations ---

    @abstractmethod
    async def save_cognitive_edge(
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

    @abstractmethod
    async def list_cognitive_edges(
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

    # --- DispositionProfile Operations ---

    @abstractmethod
    async def save_disposition(self, profile_data: dict[str, Any]) -> None:
        """Create or update a DispositionProfile.

        Args:
            profile_data: Dictionary of DispositionProfile fields.
        """

    @abstractmethod
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

    @abstractmethod
    async def compute_dynamic_weights(
        self, profile: dict[str, Any]
    ) -> dict[str, float]:
        """Compute dynamic type weights based on a DispositionProfile.

        Args:
            profile: DispositionProfile dictionary.

        Returns:
            Dictionary of memory_type -> weight.
        """

    # --- Activity Log Operations ---

    @abstractmethod
    async def save_activity_log(
        self, node_id: str, entry: dict[str, Any]
    ) -> None:
        """Append a history entry to a CognitiveNode.

        Args:
            node_id: Unique identifier for the cognitive node.
            entry: History entry to append.
        """

    @abstractmethod
    async def get_activity_log(
        self, node_id: str
    ) -> list[dict[str, Any]]:
        """Get history entries for a CognitiveNode.

        Args:
            node_id: Unique identifier for the cognitive node.

        Returns:
            List of history entries.
        """

    # --- Hybrid Search ---

    @abstractmethod
    async def search_cognitive(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid vector+graph search for cognitive nodes.

        Args:
            query: Search query text.
            space_id: Space to search within.
            top_k: Maximum number of results.
            memory_type: Optional memory type filter.

        Returns:
            List of matching node records with relevance scores.
        """


# ============================================================================
# Compensation Store
# ============================================================================

class CompensationStore(ABC):
    """Abstract interface for compensation log persistence.

    Used by ``DualWriteCoordinator`` to persist compensation records
    when graph or vector writes fail, enabling recovery on restart.
    """

    @abstractmethod
    async def save_compensation(self, entry: dict[str, Any]) -> None:
        """Persist a compensation entry.

        Args:
            entry: Dict with keys: operation, target_type, target_id,
                   timestamp, status, retry_count, details (optional).
        """

    @abstractmethod
    async def get_pending_compensations(self) -> list[dict[str, Any]]:
        """Return all pending compensation entries ordered by timestamp."""

    @abstractmethod
    async def mark_compensation_done(self, target_id: str, operation: str) -> None:
        """Mark a compensation entry as completed.

        Args:
            target_id: The target identifier of the compensation.
            operation: The operation that was compensated.
        """

    @abstractmethod
    async def increment_retry_count(self, target_id: str, operation: str) -> None:
        """Increment the retry count for a pending compensation.

        Args:
            target_id: The target identifier of the compensation.
            operation: The operation that was compensated.
        """