"""Storage abstractions shared by engine and service layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class StorageError(Exception):
    """Storage operation error."""


@dataclass
class EntityInstance:
    """Entity instance with concept and payload data."""

    concept: str
    entity_id: str
    data: dict[str, Any]


@dataclass
class RelationInstance:
    """Relation between two entities."""

    relation_type: str
    from_entity_id: str
    to_entity_id: str
    data: dict[str, Any] = field(default_factory=dict)


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
    async def get_entity(self, concept: str, entity_id: str) -> EntityInstance | None:
        """Load one entity by concept and identifier."""

    @abstractmethod
    async def query_entities(
        self,
        concept: str | None,
        filters: dict[str, Any] | None = None,
    ) -> list[EntityInstance]:
        """Query entities, optionally across all concepts."""

    @abstractmethod
    async def save_relation(self, relation: RelationInstance) -> None:
        """Persist a relation."""

    @abstractmethod
    async def get_relations(
        self,
        from_entity_id: str,
        relation_type: str | None = None,
    ) -> list[RelationInstance]:
        """Load relations from one entity."""

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str,
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
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node."""

    @abstractmethod
    async def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_depth: int = 3,
        edge_types: list[str] | None = None,
    ) -> list[list[dict]]:
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
        nodes: list[dict] | None = None,
        edges: list[dict] | None = None,
    ) -> dict[str, int]:
        """Batch write nodes and edges.

        Returns:
            {"nodes_written": N, "edges_written": M}
        """
