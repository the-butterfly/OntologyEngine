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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "version": self.version,
            "entity_count": self.entity_count,
            "metric_count": self.metric_count,
            "rule_count": self.rule_count,
            "warnings": self.warnings,
        }


class EntityResponse:
    """Entity response."""

    def __init__(
        self,
        entity_id: str,
        fact_object: str,
        attributes: dict[str, Any]
    ):
        self.entity_id = entity_id
        self._fact_object = fact_object
        self.attributes = attributes

    @property
    def fact_object(self) -> str:
        return self._fact_object

    @property
    def concept_type(self) -> str:
        return self._fact_object

    @classmethod
    def from_domain(cls, entity: Any) -> "EntityResponse":
        """Create from domain entity."""
        fo = (
            entity._fact_object
            if hasattr(entity, "_fact_object")
            else entity.concept
            if hasattr(entity, "concept")
            else entity.get("_fact_object", entity.get("concept", ""))
        )
        return cls(
            entity_id=entity.entity_id if hasattr(entity, "entity_id") else entity.get("entity_id", ""),
            fact_object=fo,
            attributes=entity.data if hasattr(entity, "data") else entity.get("data", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "fact_object": self._fact_object,
            "concept_type": self._fact_object,
            "attributes": self.attributes,
        }


class RelationResponse:
    """Relation response."""

    def __init__(
        self,
        relation_name: str,
        from_id: str,
        to_id: str,
        attributes: dict[str, Any] | None = None
    ):
        self._relation_name = relation_name
        self.from_id = from_id
        self.to_id = to_id
        self.attributes = attributes if attributes else {}

    @property
    def relation_name(self) -> str:
        return self._relation_name

    @property
    def relation_type(self) -> str:
        return self._relation_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_name": self._relation_name,
            "relation_type": self._relation_name,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "attributes": self.attributes,
        }


class NeighborResponse:
    """Neighbor entity response."""

    def __init__(
        self,
        entity: EntityResponse,
        relation: RelationResponse
    ):
        self.entity = entity
        self.relation = relation

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity.to_dict(),
            "relation": self.relation.to_dict(),
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "output": self.output,
            "error": self.error,
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "type": self.type,
            "message": self.message,
            "data": self.data,
        }


class AnalysisResponse:
    """Analysis execution response."""

    def __init__(
        self,
        entity_id: str,
        fact_object: str,
        dimension: str,
        category_tags: dict[str, str],
        computed_metrics: dict[str, Any],
        rule_results: list[RuleResultResponse],
        alerts: list[AlertResponse],
        decision: str | None,
        decision_reasoning: str | None
    ):
        self.entity_id = entity_id
        self._fact_object = fact_object
        self.dimension = dimension
        self.category_tags = category_tags
        self.computed_metrics = computed_metrics
        self.rule_results = rule_results
        self.alerts = alerts
        self.decision = decision
        self.decision_reasoning = decision_reasoning

    @property
    def fact_object(self) -> str:
        return self._fact_object

    @property
    def concept_type(self) -> str:
        return self._fact_object

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "fact_object": self._fact_object,
            "concept_type": self._fact_object,
            "dimension": self.dimension,
            "category_tags": self.category_tags,
            "computed_metrics": self.computed_metrics,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "alerts": [a.to_dict() for a in self.alerts],
            "decision": self.decision,
            "decision_reasoning": self.decision_reasoning,
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_count": self.success_count,
            "error_count": self.error_count,
            "entities": [e.to_dict() for e in self.entities],
            "errors": self.errors,
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_count": self.entity_count,
            "relation_count": self.relation_count,
            "error_count": self.error_count,
            "errors": self.errors,
        }


class SearchResultResponse:
    """Search result response."""

    def __init__(
        self,
        entity_id: str,
        fact_object: str,
        score: float,
        attributes: dict[str, Any]
    ):
        self.entity_id = entity_id
        self._fact_object = fact_object
        self.score = score
        self.attributes = attributes

    @property
    def fact_object(self) -> str:
        return self._fact_object

    @property
    def concept_type(self) -> str:
        return self._fact_object

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "fact_object": self._fact_object,
            "concept_type": self._fact_object,
            "score": self.score,
            "attributes": self.attributes,
        }
