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
