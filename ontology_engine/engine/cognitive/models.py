"""Cognitive engine data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_MEMORY_TYPES = {"entity", "observation", "episode", "fragment", "mental_model", "opinion", "procedure", "rule", "commitment", "constraint", "self_experience", "task_state"}
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveNode":
        """Create a CognitiveNode from a dictionary.

        Handles backward compatibility:
        - tags as ``list[str]`` (old format) → converted to ``dict``
        - ``model_domain`` (removed field) → converted to ``tags["model"]``
        """
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}

        # Backward compat: migrate list[str] tags → dict
        tags = filtered.get("tags")
        if isinstance(tags, list):
            migrated: dict[str, str | list[str]] = {}
            for t in tags:
                if ":" in t:
                    k, v = t.split(":", 1)
                    migrated[k] = v
                else:
                    migrated.setdefault("_legacy", []).append(t)  # type: ignore[union-attr]
            filtered["tags"] = migrated

        # Backward compat: migrate model_domain → tags["model"]
        model_domain = data.get("model_domain")
        if model_domain and "model" not in (filtered.get("tags") or {}):
            tags = filtered.setdefault("tags", {})
            assert isinstance(tags, dict)
            tags["model"] = model_domain

        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "memory_type": self.memory_type,
            "cognitive_layer": self.cognitive_layer,
            "content": self.content,
            "content_vector": self.content_vector,
            "source_fragment_ids": self.source_fragment_ids,
            "belief_status": self.belief_status,
            "ttl_seconds": self.ttl_seconds,
            "occurred_at": self.occurred_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "history": self.history,
            "access_count": self.access_count,
            "last_access_at": self.last_access_at,
            "consolidated_at": self.consolidated_at,
            "domain_id": self.domain_id,
            "space_id": self.space_id,
            "extraction_hint": self.extraction_hint,
            "visibility": self.visibility,
            "created_by": self.created_by,
            "feedback_weight": self.feedback_weight,
            "confidence": self.confidence,
            "schema_ref": self.schema_ref,
            "superseded_by": self.superseded_by,
            "proof_count": self.proof_count,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "recorded_at": self.recorded_at,
            "tags": self.tags,
            "attributes": self.attributes,
            "confirmation_count": self.confirmation_count,
            "strength": self.strength,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "version": self.version,
            "last_confirmed_at": self.last_confirmed_at,
            "consolidation_reasoning": self.consolidation_reasoning,
            "compiled_at": self.compiled_at,
            "source_trust_tier": self.source_trust_tier,
            "scope": self.scope,
            "source_pipeline": self.source_pipeline,
            "source_content_hash": self.source_content_hash,
        }

    def can_transition_to(self, new_status: str) -> bool:
        """Check if a belief status transition is valid."""
        allowed = BELIEF_TRANSITIONS.get(self.belief_status, set())
        return new_status in allowed


VALID_TRUST_TIERS = {"high", "normal", "low"}


def validate_node_fields(node: CognitiveNode) -> None:
    if node.source_trust_tier is not None and node.source_trust_tier not in VALID_TRUST_TIERS:
        raise ValueError(f"Invalid source_trust_tier: {node.source_trust_tier}, must be one of {VALID_TRUST_TIERS}")
    if node.strength < 0 or node.strength > 1.0:
        raise ValueError(f"strength must be in [0, 1.0], got {node.strength}")
    if node.version < 1:
        raise ValueError(f"version must be >= 1, got {node.version}")


@dataclass
class DispositionProfile:
    """7-dimension agent disposition profile (memory-hierarchy.md §4.3).

    Attributes:
        id: Unique identifier.
        scene: Scene/context this profile applies to.
        skepticism: Sensitivity to contradictory information (0.3-0.9).
        evidence_demand: Evidence requirement level (0.3-0.9).
        abstraction_preference: Preference for high-level summaries vs raw fragments (0.2-0.8).
        thoroughness: Retrieval thoroughness, affects funnel depth and result count (0.2-0.8).
        recency_bias: Preference for recent vs historically stable information (0.2-0.8).
        empathy: Empathy level, affects agent interaction style (0.2-0.8).
        risk_tolerance: Risk tolerance, affects decision style and confidence filtering (0.2-0.8).
        domain_id: Domain identifier.
        space_id: Space identifier.
    """
    id: str
    scene: str
    skepticism: float = 0.5
    evidence_demand: float = 0.5
    abstraction_preference: float = 0.5
    thoroughness: float = 0.5
    recency_bias: float = 0.5
    empathy: float = 0.5
    risk_tolerance: float = 0.5
    domain_id: str | None = None
    space_id: str = "default"

    _SAFETY_BOUNDS: dict[str, tuple[float, float]] = field(default_factory=lambda: {
        "skepticism": (0.3, 0.9),
        "evidence_demand": (0.3, 1.0),
        "abstraction_preference": (0.2, 0.8),
        "thoroughness": (0.2, 0.8),
        "recency_bias": (0.2, 0.9),
        "empathy": (0.2, 0.8),
        "risk_tolerance": (0.2, 0.8),
    }, init=False, repr=False)

    def __post_init__(self):
        for dim, (lo, hi) in self._SAFETY_BOUNDS.items():
            val = getattr(self, dim)
            if val < lo or val > hi:
                raise ValueError(f"{dim}={val} out of safety bounds [{lo}, {hi}]")

    @classmethod
    def finance(cls, profile_id: str, space_id: str = "default") -> "DispositionProfile":
        return cls(id=profile_id, scene="finance", skepticism=0.7, evidence_demand=0.8, space_id=space_id)

    @classmethod
    def customer_service(cls, profile_id: str, space_id: str = "default") -> "DispositionProfile":
        return cls(id=profile_id, scene="customer_service", empathy=0.8, space_id=space_id)

    @classmethod
    def audit(cls, profile_id: str, space_id: str = "default") -> "DispositionProfile":
        return cls(id=profile_id, scene="audit", evidence_demand=1.0, skepticism=0.9, thoroughness=0.8,
                   abstraction_preference=0.2, recency_bias=0.3, space_id=space_id)

    @classmethod
    def quick_answer(cls, profile_id: str, space_id: str = "default") -> "DispositionProfile":
        return cls(id=profile_id, scene="quick_answer", abstraction_preference=0.8, thoroughness=0.3, space_id=space_id)

    @classmethod
    def realtime_monitor(cls, profile_id: str, space_id: str = "default") -> "DispositionProfile":
        return cls(id=profile_id, scene="realtime_monitor", recency_bias=0.9, evidence_demand=0.7, space_id=space_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispositionProfile":
        """Create a DispositionProfile from a dictionary (tolerates old field names)."""
        mapped = dict(data)
        for old, new in {"literalism": "evidence_demand", "detail_preference": "thoroughness",
                         "memory_horizon": "recency_bias", "optimism": "risk_tolerance"}.items():
            if old in mapped and new not in mapped:
                mapped[new] = mapped.pop(old)
        return cls(**{k: v for k, v in mapped.items() if k in cls.__dataclass_fields__ and k != "_SAFETY_BOUNDS"})

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id, "scene": self.scene,
            "skepticism": self.skepticism, "evidence_demand": self.evidence_demand,
            "abstraction_preference": self.abstraction_preference, "thoroughness": self.thoroughness,
            "recency_bias": self.recency_bias, "empathy": self.empathy,
            "risk_tolerance": self.risk_tolerance,
            "domain_id": self.domain_id, "space_id": self.space_id,
        }

    def override_for_scene(self, scene: str) -> "DispositionProfile":
        """Apply scene forced overrides (memory-hierarchy.md §4.3)."""
        overrides: dict[str, dict[str, float]] = {
            "audit": {"evidence_demand": 1.0, "skepticism": 0.9, "thoroughness": 0.8},
            "quick_answer": {"abstraction_preference": 0.8, "thoroughness": 0.3},
            "realtime_monitor": {"recency_bias": 0.9, "evidence_demand": 0.7},
        }
        if scene in overrides:
            for dim, val in overrides[scene].items():
                setattr(self, dim, val)
            self.scene = scene
        return self


def apply_dynamic_weight(rrf_score: float, memory_type: str, disposition: DispositionProfile, node_strength: float = 1.0) -> float:
    weight = 1.0

    val = disposition.abstraction_preference
    if val > 0.7:
        if memory_type in ("mental_model", "opinion"):
            weight *= 1.0 + (val - 0.5)
        elif memory_type == "fragment":
            weight *= 0.5 + (1.0 - val)

    val = disposition.thoroughness
    if val > 0.7 and memory_type in ("fragment", "observation"):
        weight *= 1.0 + (val - 0.5) * 0.5

    val = disposition.evidence_demand
    if val > 0.7:
        if memory_type in ("entity", "rule"):
            weight *= 1.0 + (val - 0.5) * 0.3
        elif memory_type == "fragment":
            weight *= 0.7

    if disposition.skepticism > 0.7:
        if memory_type == "mental_model":
            weight *= 0.7
        elif memory_type == "entity":
            weight *= 1.2

    val = disposition.empathy
    if val > 0.7:
        if memory_type == "observation":
            weight *= 1.0 + (val - 0.5) * 0.3
        elif memory_type == "self_experience":
            weight *= 1.0 + (val - 0.5) * 0.2

    if disposition.risk_tolerance < 0.3:
        if memory_type in ("mental_model", "opinion"):
            weight *= 0.8

    if node_strength < 0.5:
        weight *= node_strength

    return rrf_score * weight


def compute_temporal_weight(recency_bias: float) -> float:
    if recency_bias > 0.7:
        return 0.3 + (recency_bias - 0.7) * 1.0
    elif recency_bias < 0.3:
        return 0.1
    else:
        return 0.3


class MemoryHeat:
    """Memory heat classification (memory-lifecycle.md §7.1)."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"

    @staticmethod
    def classify(feedback_weight: float, last_accessed_at: str | None) -> str:
        """Classify memory heat level based on feedback_weight and access recency.

        Returns:
            One of 'hot', 'warm', 'cold'.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        days_since_access = 999
        if last_accessed_at:
            try:
                last = datetime.fromisoformat(last_accessed_at.replace("Z", "+00:00"))
                days_since_access = (now - last).days
            except (ValueError, TypeError):
                days_since_access = 999

        if feedback_weight >= 0.8 and days_since_access < 7:
            return MemoryHeat.HOT
        if feedback_weight >= 0.5 or days_since_access < 30:
            return MemoryHeat.WARM
        return MemoryHeat.COLD


@dataclass
class BeliefRevisionRule:
    """A rule for belief revision (memory-lifecycle.md §10).

    Attributes:
        rule_id: Unique identifier.
        name: Human-readable name.
        condition: Python expression as string (evaluated in context).
        action: Action to take (set_belief, set_confidence, flag_review).
        priority: Priority (higher = evaluated first).
        track: Track (A=accepted, B=review, or "any").
        enabled: Whether the rule is active.
    """
    rule_id: str
    name: str
    condition: str
    action: dict[str, Any]
    priority: int = 0
    track: str = "any"
    enabled: bool = True


DEFAULT_BELIEF_REVISION_RULES: list[BeliefRevisionRule] = [
    BeliefRevisionRule(
        rule_id="BR_R001", name="User Correction Priority",
        condition="source == 'user_correction'",
        action={"set_belief": "accepted", "set_confidence": 1.0},
        priority=100, track="any",
    ),
    BeliefRevisionRule(
        rule_id="BR_R002", name="Authoritative Source Priority",
        condition="source in ('征信报告', '法院判决', '监管文件')",
        action={"set_belief": "accepted", "set_confidence": 0.95},
        priority=90, track="A",
    ),
    BeliefRevisionRule(
        rule_id="BR_R003", name="High Confidence Override",
        condition="confidence >= 0.9 and evidence_count >= 3",
        action={"set_belief": "accepted"},
        priority=80, track="B",
    ),
    BeliefRevisionRule(
        rule_id="BR_R004", name="Temporal Update",
        condition="is_newer and confidence >= 0.7",
        action={"set_belief": "accepted", "supersede_old": True},
        priority=70, track="any",
    ),
    BeliefRevisionRule(
        rule_id="BR_R005", name="Feedback Protection",
        condition="feedback_weight > 0.8",
        action={"block_revision": True},
        priority=60, track="A",
    ),
    BeliefRevisionRule(
        rule_id="BR_R006", name="Schema Violation",
        condition="schema_alignment < 0.3",
        action={"set_belief": "pending_review", "set_confidence": 0.3},
        priority=50, track="any",
    ),
    BeliefRevisionRule(
        rule_id="BR_R007", name="Cross-Domain Conflict",
        condition="conflicting_domains and confidence < 0.6",
        action={"set_belief": "pending_review"},
        priority=40, track="any",
    ),
]


def detect_rule_conflicts(rules: list[BeliefRevisionRule]) -> list[dict[str, Any]]:
    """Detect conflicts between belief revision rules.

    Two rules conflict if they have the same priority but different actions
    for the same track.

    Returns:
        List of conflict descriptions.
    """
    conflicts: list[dict[str, Any]] = []
    by_priority: dict[int, list[BeliefRevisionRule]] = {}
    for r in rules:
        by_priority.setdefault(r.priority, []).append(r)

    for pri, group in by_priority.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ri = group[i]
                rj = group[j]
                if ri.track == rj.track or ri.track == "any" or rj.track == "any":
                    if ri.action != rj.action:
                        conflicts.append({
                            "type": "action_mismatch",
                            "rule_a": ri.rule_id,
                            "rule_b": rj.rule_id,
                            "priority": pri,
                            "detail": f"{ri.name} vs {rj.name} at priority {pri}",
                        })
    return conflicts


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


def append_history_entry(node: CognitiveNode, entry: dict[str, Any]) -> None:
    history = list(node.history) if node.history else []
    history.append(entry)
    if len(history) > HISTORY_MAX_ENTRIES:
        compressed = {"type": "compressed", "original_count": len(history) - 1, "oldest": history[0]}
        history = [compressed] + history[-(HISTORY_MAX_ENTRIES - 1):]
    node.history = history
