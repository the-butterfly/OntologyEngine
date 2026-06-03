from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

AUTHORITATIVE_SOURCES = frozenset({
    "user_declared", "court_judgment", "regulatory_document",
    "official_document", "verified_source", "expert_input",
})

AGENT_SOURCES = frozenset({
    "agent_generated", "inferred", "behavior_inferred", "unverified",
})


class Orbit(str, Enum):
    A = "A"
    B = "B"


class PromotionStatus(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    PROMOTED = "promoted"


@dataclass
class OrbitRoutingResult:
    orbit: Orbit
    reason: str = ""
    auto_resolvable: bool = False
    requires_human_review: bool = False
    promotion_eligible: bool = False


@dataclass
class PromotionCandidate:
    node_id: str
    current_orbit: Orbit
    confidence: float
    schema_alignment: float
    evidence_count: int
    status: PromotionStatus = PromotionStatus.ELIGIBLE


@dataclass
class IngestContradictionResult:
    has_contradiction: bool = False
    orbit: Orbit = Orbit.B
    action: str = ""
    existing_node_id: str | None = None
    new_node_id: str | None = None
    reason: str = ""


class OrbitRouter:
    def __init__(
        self,
        repository: Any | None = None,
        promotion_confidence_threshold: float = 0.9,
        promotion_alignment_threshold: float = 0.9,
        promotion_min_evidence: int = 3,
    ):
        self._repo = repository
        self._prom_conf = promotion_confidence_threshold
        self._prom_align = promotion_alignment_threshold
        self._prom_evidence = promotion_min_evidence

    def route(self, source_pipeline: str, source_trust_tier: str = "", tags: dict | None = None) -> OrbitRoutingResult:
        if source_pipeline in AUTHORITATIVE_SOURCES or source_trust_tier in ("high",):
            return OrbitRoutingResult(
                orbit=Orbit.A,
                reason=f"authoritative_source:{source_pipeline}",
                auto_resolvable=False,
                requires_human_review=True,
            )
        if source_pipeline in AGENT_SOURCES or source_trust_tier in ("low",):
            return OrbitRoutingResult(
                orbit=Orbit.B,
                reason=f"agent_source:{source_pipeline}",
                auto_resolvable=True,
                requires_human_review=False,
            )
        tags = tags or {}
        model = tags.get("model", "") if isinstance(tags, dict) else ""
        if model == "self":
            return OrbitRoutingResult(
                orbit=Orbit.B,
                reason="self_domain_memory",
                auto_resolvable=True,
                requires_human_review=False,
            )
        return OrbitRoutingResult(
            orbit=Orbit.A,
            reason="default_enterprise_governance",
            auto_resolvable=False,
            requires_human_review=True,
        )

    def check_promotion_eligibility(
        self,
        node_id: str,
        confidence: float,
        schema_alignment: float,
        evidence_count: int,
    ) -> PromotionCandidate:
        eligible = (
            confidence >= self._prom_conf
            and schema_alignment >= self._prom_align
            and evidence_count >= self._prom_evidence
        )
        return PromotionCandidate(
            node_id=node_id,
            current_orbit=Orbit.B,
            confidence=confidence,
            schema_alignment=schema_alignment,
            evidence_count=evidence_count,
            status=PromotionStatus.ELIGIBLE if eligible else PromotionStatus.NOT_ELIGIBLE,
        )

    async def route_ingest_contradiction(
        self,
        new_source_pipeline: str,
        new_source_trust_tier: str,
        existing_node: Any,
        similarity: float,
    ) -> IngestContradictionResult:
        routing = self.route(new_source_pipeline, new_source_trust_tier)
        if similarity < 0.80:
            return IngestContradictionResult(
                has_contradiction=False,
                orbit=routing.orbit,
                action="accept_both",
                reason=f"low_similarity:{similarity:.2f}",
            )
        if routing.orbit == Orbit.B and routing.auto_resolvable:
            return IngestContradictionResult(
                has_contradiction=True,
                orbit=Orbit.B,
                action="auto_supersede_if_higher_confidence",
                existing_node_id=getattr(existing_node, "id", None),
                reason=f"orbit_b_auto:{similarity:.2f}",
            )
        return IngestContradictionResult(
            has_contradiction=True,
            orbit=Orbit.A,
            action="pending_review",
            existing_node_id=getattr(existing_node, "id", None),
            reason=f"orbit_a_requires_review:{similarity:.2f}",
        )
