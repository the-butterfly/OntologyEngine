# ontology_engine/services/dto/responses.py
"""Response DTOs for service layer."""

from __future__ import annotations

from typing import Any


class SchemaInfo:
    """Schema information response."""

    def __init__(
        self,
        schema_id: str,
        version: str,
        entity_count: int = 0,
        metric_count: int = 0,
        rule_count: int = 0,
        warnings: list[str] | None = None
    ):
        self.schema_id = schema_id
        self.version = version
        self.entity_count = entity_count
        self.metric_count = metric_count
        self.rule_count = rule_count
        self.warnings = warnings if warnings else []


class EntityResponse:
    """Entity response."""

    def __init__(
        self,
        entity_id: str,
        concept_type: str,
        attributes: dict[str, Any]
    ):
        self.entity_id = entity_id
        self.concept_type = concept_type
        self.attributes = attributes

    @classmethod
    def from_domain(cls, entity: Any) -> "EntityResponse":
        """Create from domain entity."""
        return cls(
            entity_id=entity.entity_id if hasattr(entity, 'entity_id') else entity.get('entity_id', ''),
            concept_type=entity.concept if hasattr(entity, 'concept') else entity.get('_concept', ''),
            attributes=entity.data if hasattr(entity, 'data') else entity.get('data', {})
        )


class RelationResponse:
    """Relation response."""

    def __init__(
        self,
        relation_type: str,
        from_id: str,
        to_id: str,
        attributes: dict[str, Any] | None = None
    ):
        self.relation_type = relation_type
        self.from_id = from_id
        self.to_id = to_id
        self.attributes = attributes if attributes else {}


class NeighborResponse:
    """Neighbor entity response."""

    def __init__(
        self,
        entity: EntityResponse,
        relation: RelationResponse
    ):
        self.entity = entity
        self.relation = relation


class RuleResultResponse:
    """Rule execution result."""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        passed: bool,
        output: dict[str, Any] | None = None,
        error: str | None = None
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.passed = passed
        self.output = output if output else {}
        self.error = error


class AlertResponse:
    """Alert response."""

    def __init__(
        self,
        level: str,
        type: str,
        message: str,
        data: dict[str, Any] | None = None
    ):
        self.level = level
        self.type = type
        self.message = message
        self.data = data if data else {}


class AnalysisResponse:
    """Analysis execution response."""

    def __init__(
        self,
        entity_id: str,
        concept_type: str,
        dimension: str,
        category_tags: dict[str, str],
        computed_metrics: dict[str, Any],
        rule_results: list[RuleResultResponse],
        alerts: list[AlertResponse],
        decision: str | None,
        decision_reasoning: str | None
    ):
        self.entity_id = entity_id
        self.concept_type = concept_type
        self.dimension = dimension
        self.category_tags = category_tags
        self.computed_metrics = computed_metrics
        self.rule_results = rule_results
        self.alerts = alerts
        self.decision = decision
        self.decision_reasoning = decision_reasoning


class BatchOperationResult:
    """Batch operation result."""

    def __init__(
        self,
        success_count: int,
        error_count: int,
        entities: list[EntityResponse] | None = None,
        errors: list[dict] | None = None
    ):
        self.success_count = success_count
        self.error_count = error_count
        self.entities = entities if entities else []
        self.errors = errors if errors else []


class IngestionResult:
    """Ingestion operation result."""

    def __init__(
        self,
        entity_count: int,
        relation_count: int,
        error_count: int,
        errors: list[dict] | None = None
    ):
        self.entity_count = entity_count
        self.relation_count = relation_count
        self.error_count = error_count
        self.errors = errors if errors else []


class SearchResultResponse:
    """Search result response."""

    def __init__(
        self,
        entity_id: str,
        concept_type: str,
        score: float,
        attributes: dict[str, Any]
    ):
        self.entity_id = entity_id
        self.concept_type = concept_type
        self.score = score
        self.attributes = attributes
