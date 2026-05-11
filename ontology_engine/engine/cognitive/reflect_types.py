"""Reflect agent types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReflectionPhase(str, Enum):
    RETRIEVAL = "retrieval"
    CONTRADICTION_DETECTION = "contradiction_detection"
    BELIEF_REVISION = "belief_revision"
    CONSOLIDATION = "consolidation"
    FORGETTING = "forgetting"
    CORRECTION_PROPAGATION = "correction_propagation"
    SCHEMA_SUGGESTION = "schema_suggestion"


class ReflectionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Insight:
    """A discovered insight from reflection.

    Attributes:
        text: Insight description.
        confidence: Confidence score (0-1).
        evidence_ids: IDs of supporting evidence.
        suggested_memory_type: Suggested memory type for storage.
    """
    text: str
    confidence: float = 0.5
    evidence_ids: list[str] = field(default_factory=list)
    suggested_memory_type: str = "observation"


@dataclass
class ContradictionReport:
    """A detected contradiction between memories.

    Attributes:
        node_ids: IDs of contradictory nodes.
        contradiction_type: Type of contradiction.
        contradiction_field: Field with contradiction.
        old_value: Old value.
        new_value: New value.
        suggested_resolution: Suggested resolution.
    """
    node_ids: list[str] = field(default_factory=list)
    contradiction_type: str = "value_conflict"
    contradiction_field: str = ""
    old_value: str = ""
    new_value: str = ""
    suggested_resolution: str = ""


@dataclass
class MentalModelUpdate:
    """A proposed update to a mental model.

    Attributes:
        model_id: ID of the mental model to update.
        update_type: Type of update (refine, extend, supersede).
        update_text: Updated text.
        evidence_ids: Supporting evidence IDs.
    """
    model_id: str
    update_type: str = "refine"
    update_text: str = ""
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ReflectResult:
    """Result of a reflection session.

    Attributes:
        insights: Discovered insights.
        contradictions: Detected contradictions.
        consolidation_requests: Space IDs needing consolidation.
        forgetting_requests: Node IDs suggested for forgetting.
        mental_model_updates: Proposed mental model updates.
        short_circuited: Whether the funnel was short-circuited.
        iterations_used: Number of iterations used during reflection.
        tokens_used: Estimated tokens used during reflection.
    """
    insights: list[Insight] = field(default_factory=list)
    contradictions: list[ContradictionReport] = field(default_factory=list)
    consolidation_requests: list[str] = field(default_factory=list)
    forgetting_requests: list[str] = field(default_factory=list)
    mental_model_updates: list[MentalModelUpdate] = field(default_factory=list)
    short_circuited: bool = False
    iterations_used: int = 1
    tokens_used: int = 0
    method: str = "rule_only"


@dataclass
class ReflectionProgress:
    """Progress tracking for an async reflection job.

    Attributes:
        reflection_id: Unique identifier for the reflection job.
        status: Current status of the reflection.
        progress: Phase-to-status mapping.
        partial_results: Partial results accumulated so far.
        error: Error message if failed.
        created_at: Creation timestamp.
        completed_at: Completion timestamp.
    """
    reflection_id: str
    status: ReflectionStatus = ReflectionStatus.PENDING
    progress: dict[str, str] = field(default_factory=dict)
    partial_results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


@dataclass
class ReflectionJob:
    """An async reflection job.

    Attributes:
        reflection_id: Unique identifier.
        query: Original query.
        space_id: Space being reflected on.
        max_iterations: Maximum reflection iterations.
        focus_types: Optional focus on specific memory types.
        skip_consolidation: Whether to skip the consolidation phase.
        skip_forgetting: Whether to skip the forgetting phase.
        cascade_depth: Maximum depth for correction propagation.
        skip_correction_propagation: Whether to skip correction propagation.
        progress: Progress tracking object.
    """
    reflection_id: str
    query: str
    space_id: str
    max_iterations: int = 10
    focus_types: list[str] | None = None
    skip_consolidation: bool = False
    skip_forgetting: bool = False
    cascade_depth: int = 3
    skip_correction_propagation: bool = False
    progress: ReflectionProgress | None = None

    @staticmethod
    def generate_id() -> str:
        return f"refl:{uuid.uuid4().hex[:12]}"


FORCED_SEARCH_SEQUENCE = ["mental_model", "entity", "observation"]
MAX_ITERATIONS = 10
MAX_CONTEXT_TOKENS = 8000
MAX_HALLUCINATION_RETRIES = 2

DIRECTIVES_RULES: list[dict[str, Any]] = [
    {
        "id": "D-REF-5.1",
        "name": "No Node Creation",
        "description": "Reflection must not create new CognitiveNodes. Report insights only.",
        "action": "create_node",
        "level": "fatal",
    },
    {
        "id": "D-REF-5.2",
        "name": "No Belief Modification",
        "description": "Reflection must not directly modify belief_status. Report contradictions instead.",
        "action": "modify_belief",
        "level": "fatal",
    },
    {
        "id": "D-REF-5.3",
        "name": "No Memory Deletion",
        "description": "Reflection must not delete any memories. Use forgetting requests instead.",
        "action": "delete_node",
        "level": "fatal",
    },
    {
        "id": "D-REF-5.4",
        "name": "Insights Require Evidence",
        "description": "Every insight must include evidence_ids from actual retrieved results.",
        "action": "insight_no_evidence",
        "level": "fatal",
    },
    {
        "id": "D-REF-5.5",
        "name": "Contradictions Require Resolution",
        "description": "Every contradiction must include a suggested_resolution.",
        "action": "contradiction_no_resolution",
        "level": "warning",
    },
    {
        "id": "D-REF-5.6",
        "name": "No External ID Reference",
        "description": "Must not reference memory IDs outside the retrieval scope.",
        "action": "external_id",
        "level": "fatal",
    },
]
