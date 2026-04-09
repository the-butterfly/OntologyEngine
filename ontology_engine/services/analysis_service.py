# ontology_engine/services/analysis_service.py
"""Analysis orchestration service - core business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.services.dto import (
    AnalysisResponse,
    RuleResultResponse,
    AlertResponse,
    EntityNotFoundError,
)
from ontology_engine.storage.duckdb import DuckDBStorage

if TYPE_CHECKING:
    from ontology_engine.engine.categorization import CategorizationEngine
    from ontology_engine.engine.metric import MetricEngine
    from ontology_engine.engine.rule import RuleExecutor
    from ontology_engine.core.schema.models import KGMLSchema


class AnalysisService:
    """Analysis orchestration service.

    Coordinates: CategorizationEngine → MetricEngine → RuleEngine

    This is the core service that orchestrates the complete analysis flow
    for supply chain finance credit assessment.
    """

    def __init__(
        self,
        categorization_engine: CategorizationEngine,
        metric_engine: MetricEngine,
        rule_executor: RuleExecutor,
        storage: DuckDBStorage,
        schema: KGMLSchema | None = None,
    ):
        """Initialize AnalysisService.

        Args:
            categorization_engine: L2 categorization engine
            metric_engine: L3 metric computation engine
            rule_executor: L4 rule execution engine
            storage: DuckDBStorage for entity retrieval
            schema: Optional schema for validation
        """
        self.categorization_engine = categorization_engine
        self.metric_engine = metric_engine
        self.rule_executor = rule_executor
        self.storage = storage
        self.schema = schema

    async def execute_analysis(
        self,
        entity_id: str,
        dimension: str,
        context: dict[str, Any] | None = None
    ) -> AnalysisResponse:
        """Execute complete dimension analysis.

        Flow:
        1. Get entity from storage
        2. L2 Categorization
        3. L3 Metric computation (Decision #11: direct call)
        4. L4 Rule execution
        5. Assemble results

        Args:
            entity_id: Entity to analyze
            dimension: Dimension name (e.g., "credit_assessment")
            context: Optional analysis context/overrides

        Returns:
            AnalysisResponse with complete analysis results

        Raises:
            EntityNotFoundError: If entity not found
        """
        # 1. Get entity - we need to find it first
        entity = await self._find_entity(entity_id)
        if entity is None:
            raise EntityNotFoundError(entity_id)

        # 2. L2 Categorization
        category_tags = await self.categorization_engine.categorize(entity)
        category_tags_dict = category_tags.tags if hasattr(category_tags, 'tags') else {}

        # 3. L3 Metric computation
        # Get required metrics for this dimension from schema
        required_metrics = self._collect_required_metrics(dimension)
        computed_metrics = {}

        if required_metrics and hasattr(self.metric_engine, 'compute_batch'):
            computed_metrics = await self.metric_engine.compute_batch(
                required_metrics, entity,
                context=context
            )
            # Convert to serializable dict
            computed_metrics = self._serialize_metrics(computed_metrics)

        # 4. L4 Rule execution
        entity_data = dict(entity.data) if hasattr(entity, 'data') else {}
        entity_data["_concept"] = entity.concept

        # Add computed metrics to entity data for rule evaluation
        for key, value in computed_metrics.items():
            entity_data[key] = value

        # Execute rules
        analysis_result = await self.rule_executor.execute_dimension(
            dimension=dimension,
            entity_id=entity_id,
            entity_data=entity_data
        )

        # 5. Assemble response
        rule_results = [
            RuleResultResponse(
                rule_id=r.rule_id if hasattr(r, 'rule_id') else '',
                rule_name=r.rule_name if hasattr(r, 'rule_name') else '',
                passed=r.passed if hasattr(r, 'passed') else False,
                output=r.output if hasattr(r, 'output') else {},
                error=getattr(r, 'error', None)
            )
            for r in analysis_result.rule_results
        ]

        alerts = [
            AlertResponse(
                level=a.level if hasattr(a, 'level') else 'info',
                type=a.type if hasattr(a, 'type') else 'general',
                message=a.message if hasattr(a, 'message') else '',
                data=a.data if hasattr(a, 'data') else {}
            )
            for a in analysis_result.alerts
        ]

        return AnalysisResponse(
            entity_id=entity_id,
            concept_type=entity.concept,
            dimension=dimension,
            category_tags=category_tags_dict,
            computed_metrics=analysis_result.computed_metrics,
            rule_results=rule_results,
            alerts=alerts,
            decision=analysis_result.decision,
            decision_reasoning=analysis_result.decision_reasoning
        )

    async def execute_dry_run(
        self,
        entity_id: str,
        dimension: str,
        context: dict[str, Any] | None = None
    ) -> AnalysisResponse:
        """Execute analysis preview without persisting results.

        Args:
            entity_id: Entity to analyze
            dimension: Dimension name
            context: Optional analysis context

        Returns:
            AnalysisResponse (not persisted)
        """
        # For dry run, we just execute normally
        # In a full implementation, this would skip storage writes
        return await self.execute_analysis(entity_id, dimension, context)

    async def _find_entity(self, entity_id: str):
        """Find entity by ID.

        Since DuckDBStorage.get_entity requires concept type,
        we try common concepts.

        Args:
            entity_id: Entity ID to find

        Returns:
            EntityInstance if found, None otherwise
        """
        # Try common concept types
        concept_types = ["Supplier", "Invoice", "Contract", "Enterprise", "Company"]

        for concept in concept_types:
            entity = await self.storage.get_entity(concept, entity_id)
            if entity:
                return entity

        # Try querying all entities
        entities = await self.storage.query_entities(concept=None, filters=None)
        for entity in entities:
            if entity.entity_id == entity_id:
                return entity

        return None

    def _collect_required_metrics(self, dimension: str) -> list[str]:
        """Collect all metrics required for a dimension.

        Args:
            dimension: Dimension name

        Returns:
            List of required metric names
        """
        if not self.schema or not hasattr(self.schema, 'metrics'):
            return []

        # Return all metrics for now
        # A full implementation would extract from rule definitions
        return [m.name for m in self.schema.metrics]

    def _serialize_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Convert metric values to serializable format.

        Args:
            metrics: Raw metric values

        Returns:
            Serializable dict
        """
        result = {}
        for key, value in metrics.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result
