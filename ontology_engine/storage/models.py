"""Storage-layer data models shared across the storage stack.

Moved from engine/cognitive/models.py to eliminate the storage → engine
reverse dependency.  The engine layer re-exports these symbols so that
existing callers remain unchanged.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

from ontology_engine.storage.migrations import apply_cognitive_node_migrations

VALID_MEMORY_TYPES = {"entity", "observation", "episode", "fragment", "mental_model", "opinion", "procedure", "rule", "commitment", "constraint", "self_experience", "task_state", "relation", "metrics"}
VALID_COGNITIVE_LAYERS = {"opinion", "semantic", "procedure", "perception"}
VALID_BELIEF_STATUSES = {"accepted", "contradicted", "superseded", "pending_review", "rejected"}
VALID_VISIBILITIES = {"private", "shared", "public"}
HISTORY_MAX_ENTRIES = 20

BELIEF_TRANSITIONS = {
    "accepted": {"contradicted", "superseded", "pending_review", "rejected"},
    "contradicted": {"accepted", "pending_review", "rejected"},
    "superseded": {"accepted", "rejected", "pending_review"},
    "pending_review": {"accepted", "contradicted", "superseded", "rejected"},
    "rejected": {"accepted", "pending_review"},
}


@dataclass
class CognitiveNode:
    """Represents a memory node in the cognitive layer.

    Attributes:
        id: Unique identifier (e.g., "mem:<type>:<hash>").
        memory_type: Type of memory (entity, observation, etc.).
        cognitive_layer: Cognitive layer (opinion, semantic, procedure, perception).
        content: The memory content text.
        content_vector: Embedding vector for semantic search.
        source_fragment_ids: Source fragment IDs supporting this memory.
        belief_status: Current belief state.
        ttl_seconds: Time-to-live (0 = permanent).
        occurred_at: When the memory event occurred.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        history: List of history entries.
        access_count: Number of times accessed.
        last_access_at: Last access timestamp.
        consolidated_at: When consolidated (None if not consolidated).
        domain_id: Domain identifier.
        space_id: Space identifier.
        extraction_hint: Hint for extraction pipeline.
        visibility: Visibility level (private, shared, public).
        created_by: Creator identifier.
        feedback_weight: Weight from user/system feedback (0-1).
        confidence: Confidence score (0-1).
    """
    id: str
    memory_type: str
    cognitive_layer: str
    content: str
    content_vector: list[float] | None = None
    source_fragment_ids: list[str] = field(default_factory=list)
    belief_status: str = "accepted"
    ttl_seconds: int = 0
    occurred_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    access_count: int = 0
    last_access_at: str | None = None
    consolidated_at: str | None = None
    domain_id: str | None = None
    space_id: str = "default"
    extraction_hint: str | None = None
    visibility: str = "shared"
    created_by: str | None = None
    feedback_weight: float = 0.5
    confidence: float = 1.0
    schema_ref: str | None = None
    superseded_by: str | None = None
    proof_count: int = 1
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_at: str | None = None
    tags: dict[str, str | list[str]] = field(default_factory=dict)
    attributes: dict[str, str] = field(default_factory=dict)
    confirmation_count: int = 0
    strength: float = 1.0
    entity_name: str | None = None
    entity_type: str | None = None
    version: int = 1
    last_confirmed_at: str | None = None
    consolidation_reasoning: str | None = None
    compiled_at: str | None = None
    source_trust_tier: str | None = None
    scope: str | None = None
    source_pipeline: str | None = None
    source_content_hash: str | None = None

    def __post_init__(self) -> None:
        if self.memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(
                f"Invalid memory_type: {self.memory_type!r}, "
                f"must be one of {VALID_MEMORY_TYPES}"
            )
        if self.cognitive_layer not in VALID_COGNITIVE_LAYERS:
            raise ValueError(
                f"Invalid cognitive_layer: {self.cognitive_layer!r}, "
                f"must be one of {VALID_COGNITIVE_LAYERS}"
            )
        if self.belief_status not in VALID_BELIEF_STATUSES:
            raise ValueError(
                f"Invalid belief_status: {self.belief_status!r}, "
                f"must be one of {VALID_BELIEF_STATUSES}"
            )
        if self.visibility not in VALID_VISIBILITIES:
            raise ValueError(
                f"Invalid visibility: {self.visibility!r}, "
                f"must be one of {VALID_VISIBILITIES}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0, 1.0], got {self.confidence}"
            )
        if not 0.0 <= self.feedback_weight <= 1.0:
            raise ValueError(
                f"feedback_weight must be in [0, 1.0], got {self.feedback_weight}"
            )
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(
                f"strength must be in [0, 1.0], got {self.strength}"
            )
        if self.version < 1:
            raise ValueError(
                f"version must be >= 1, got {self.version}"
            )
        if self.source_trust_tier is not None and self.source_trust_tier not in {"high", "normal", "low"}:
            raise ValueError(
                f"Invalid source_trust_tier: {self.source_trust_tier!r}, "
                f"must be one of {{'high', 'normal', 'low'}}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveNode":
        """Create a CognitiveNode from a dictionary.

        Applies registered migrations (see ``storage/migrations.py``)
        then filters to known dataclass fields.
        """
        data = apply_cognitive_node_migrations(data)
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary using dataclasses.asdict."""
        return dataclasses.asdict(self)

    def can_transition_to(self, new_status: str) -> bool:
        """Check if a belief status transition is valid."""
        allowed = BELIEF_TRANSITIONS.get(self.belief_status, set())
        return new_status in allowed


@dataclass
class CognitiveEdge:
    """Represents an edge between two cognitive nodes.

    Attributes:
        edge_type: Type of edge (PART_OF, SUPPORTS, CONTRADICTS, etc.).
        from_id: Source node ID.
        to_id: Target node ID.
        properties: Edge-specific properties.
        created_at: Creation timestamp.
    """
    edge_type: str
    from_id: str
    to_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveEdge":
        return cls(
            edge_type=data.get("edge_type", ""),
            from_id=data.get("from_id", ""),
            to_id=data.get("to_id", ""),
            properties=data.get("properties", {}),
            created_at=data.get("created_at"),
        )
