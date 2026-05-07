"""Consolidation engine types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Fragment:
    """Represents an unconsolidated knowledge fragment.

    Attributes:
        id: Fragment ID.
        content: Fragment text content.
        tags: Tags for grouping and isolation.
        space_id: Space identifier.
        version: Version number for OCC.
        created_at: Creation timestamp.
    """
    id: str
    content: str
    tags: list[str] = field(default_factory=list)
    space_id: str = "default"
    version: int = 0
    created_at: str | None = None


@dataclass
class CreateAction:
    """Consolidation action: create a new CognitiveNode.

    Attributes:
        text: Content for the new node.
        memory_type: Target memory type (observation, entity).
        cognitive_layer: Target cognitive layer.
        tags: Tags for the new node.
        source_fragments: Source fragments that support this creation.
        confidence: Confidence score (0-1).
    """
    text: str
    memory_type: str = "observation"
    cognitive_layer: str = "semantic"
    tags: list[str] = field(default_factory=list)
    source_fragments: list[Fragment] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class UpdateAction:
    """Consolidation action: update an existing CognitiveNode.

    Attributes:
        target_id: ID of the node to update.
        updated_text: New content text.
        updated_tags: New tags.
        new_source_fragments: Additional source fragments.
        confidence: Updated confidence score.
    """
    target_id: str
    updated_text: str
    updated_tags: list[str] = field(default_factory=list)
    new_source_fragments: list[Fragment] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class DeleteAction:
    """Consolidation action: supersede an existing CognitiveNode.

    Attributes:
        target_id: ID of the node to supersede.
        replacement_id: ID of the replacement node (if any).
        reason: Reason for superseding.
    """
    target_id: str
    replacement_id: str | None = None
    reason: str = "superseded_by_consolidation"


@dataclass
class UpgradeAction:
    """Consolidation action: upgrade an observation to entity type.

    Attributes:
        target_id: ID of the observation node to upgrade.
        entity_name: Name for the new entity.
        entity_type: Type of the entity (person, org, concept, etc.).
        attributes: Additional entity attributes.
        reason: Reason for the upgrade.
    """
    target_id: str
    entity_name: str = ""
    entity_type: str = "concept"
    attributes: dict[str, str] = field(default_factory=dict)
    reason: str = "schema_pattern_match"


@dataclass
class ConsolidationResult:
    """Result of a consolidation batch.

    Attributes:
        created: List of CreateAction results (node IDs).
        updated: List of UpdateAction results (node IDs).
        deleted: List of DeleteAction results (node IDs).
        errors: List of errors encountered.
    """
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    upgraded: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def merge(self, other: "ConsolidationResult") -> "ConsolidationResult":
        """Merge two consolidation results."""
        return ConsolidationResult(
            created=self.created + other.created,
            updated=self.updated + other.updated,
            deleted=self.deleted + other.deleted,
            upgraded=self.upgraded + other.upgraded,
            errors=self.errors + other.errors,
        )


CONSOLIDATION_THRESHOLD = 5
HISTORY_MAX_ENTRIES = 20
SCHEMA_ALIGNMENT_THRESHOLD = 0.7
