"""Entity resolver types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ResolutionContext:
    """Context for entity resolution.

    Attributes:
        nearby_entity_ids: IDs of entities mentioned nearby.
        event_date: Date of the event being processed.
        extracted_attributes: Key-value attributes extracted from text.
    """
    nearby_entity_ids: set[str] = field(default_factory=set)
    event_date: datetime | None = None
    extracted_attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class ResolutionResult:
    """Result of resolving a single entity text.

    Attributes:
        entity_text: Original entity text.
        action: "reuse", "create", or "pending_review".
        candidate_id: ID of the matched entity (if reuse).
        score: Disambiguation score (0-1).
    """
    entity_text: str
    action: str = "create"
    candidate_id: str | None = None
    score: float = 0.0


ENTITY_COUNT_THRESHOLD = 10000
SCORE_REUSE_THRESHOLD = 0.6
SCORE_REVIEW_THRESHOLD = 0.3
