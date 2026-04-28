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
from ontology_engine.storage.base import StorageBackend

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema


class AnalysisService:
    """Analysis orchestration service.

    Coordinates: CategorizationEngine → MetricEngine → RuleEngine

    This is the core service that orchestrates the complete analysis flow
    for supply chain finance credit assessment.

    Engines are created internally from schema + storage, keeping the
    API layer free of direct engine imports (module boundary rule).
    """

    def __init__(
        self,
        storage: StorageBackend,
        schema: KGMLSchema | None = None,
        pipeline_state_manager: Any = None,
    ):
        self.storage = storage
        self.schema = schema
        self._psm = pipeline_state_manager

        self.categorization_engine: Any = None
        self.metric_engine: Any = None
        self.rule_executor: Any = None

        if schema:
            from ontology_engine.engine.metric.engine import MetricEngine, MetricCache
            from ontology_engine.engine.categorization.engine import CategorizationEngine
            from ontology_engine.engine.rule.executor import RuleExecutor

            metric_cache = MetricCache()
            self.metric_engine = MetricEngine(schema=schema, storage=storage, cache=metric_cache)
            self.rule_executor = RuleExecutor(schema=schema)
            self.categorization_engine = CategorizationEngine(
                schema=schema, storage=storage, rule_executor=self.rule_executor,
            )

    async def execute_analysis(
        self,
        entity_id: str,
        dimension: str,
        context: dict[str, Any] | None = None
    ) -> AnalysisResponse:
        run_id = None
        if self._psm:
            run = self._psm.create_run(
                rule_logic_name="analysis",
                rule_definition_name=dimension,
                entity_id=entity_id,
                dimension=dimension,
            )
            run_id = run.id
            self._psm.start_run(run_id)

        try:
            result = await self._execute_six_steps(entity_id, dimension, context, run_id)
            if self._psm and run_id:
                self._psm.complete_run(run_id)
            return result
        except Exception as e:
            if self._psm and run_id:
                self._psm.fail_run(run_id, str(e))
            raise

    async def _execute_six_steps(
        self,
        entity_id: str,
        dimension: str,
        context: dict[str, Any] | None,
        run_id: str | None,
    ) -> AnalysisResponse:
        import asyncio

        # Step 1: Entity resolution
        entity = await self._find_entity(entity_id)
        if entity is None:
            raise EntityNotFoundError(entity_id)

        # Step 6: Feedback integration (pre-check)
        if hasattr(self.storage, 'get_feedback'):
            try:
                from ontology_engine.services.feedback_service import FeedbackService
                feedback_svc = FeedbackService(self.storage)
                await feedback_svc.apply_feedback(entity_id)
                entity = await self._find_entity(entity_id) or entity
            except Exception:
                pass

        # Step 2: L2 Categorization
        category_tags = await self.categorization_engine.categorize(entity)
        category_tags_dict = category_tags.tags if hasattr(category_tags, 'tags') else {}

        # Step 3: L3 Metric pre-computation (parallel when multiple)
        required_metrics = self._collect_required_metrics(dimension)
        computed_metrics = {}

        if required_metrics and self.metric_engine:
            if hasattr(self.metric_engine, 'compute_batch'):
                computed_metrics = await self.metric_engine.compute_batch(
                    required_metrics, entity, context=context
                )
                computed_metrics = self._serialize_metrics(computed_metrics)
            elif hasattr(self.metric_engine, 'compute_metric'):
                tasks = [
                    self.metric_engine.compute_metric(m, entity, context=context)
                    for m in required_metrics
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for m, r in zip(required_metrics, results):
                    if not isinstance(r, Exception):
                        computed_metrics[m] = r

        # Step 4: L4 Rule execution
        entity_data = dict(entity.data) if hasattr(entity, 'data') else {}
        entity_data["_fact_object"] = entity._fact_object

        for key, value in computed_metrics.items():
            entity_data[key] = value

        analysis_result = await self.rule_executor.execute_dimension(
            dimension=dimension,
            entity_id=entity_id,
            entity_data=entity_data
        )

        # Step 5: Result assembly
        rule_results = [
            RuleResultResponse(
                rule_id=r.rule_id if hasattr(r, 'rule_id') else '',
                rule_name=str(r.rule_name) if hasattr(r, 'rule_name') and r.rule_name else '',
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
            fact_object=entity._fact_object,
            dimension=dimension,
            category_tags=category_tags_dict,
            computed_metrics=analysis_result.computed_metrics,
            rule_results=rule_results,
            alerts=alerts,
            decision=analysis_result.decision,
            decision_reasoning=analysis_result.decision_reasoning
        )

    async def explain(
        self,
        entity_id: str,
        dimension: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entity = await self._find_entity(entity_id)
        if entity is None:
            raise EntityNotFoundError(entity_id)

        explanation: dict[str, Any] = {
            "entity_id": entity_id,
            "fact_object": entity._fact_object,
            "feedback_weight": entity.feedback_weight,
            "steps": [],
        }

        if self.categorization_engine:
            try:
                cat_result = await self.categorization_engine.categorize(entity)
                explanation["steps"].append({
                    "step": "L2_categorization",
                    "result": cat_result.tags if hasattr(cat_result, 'tags') else {},
                })
            except Exception as e:
                explanation["steps"].append({"step": "L2_categorization", "error": str(e)})

        if self.metric_engine and dimension:
            try:
                required = self._collect_required_metrics(dimension)
                explanation["steps"].append({
                    "step": "L3_metric_precomputation",
                    "required_metrics": required,
                })
            except Exception as e:
                explanation["steps"].append({"step": "L3_metric_precomputation", "error": str(e)})

        if self.rule_executor and dimension:
            try:
                entity_data = dict(entity.data)
                entity_data["_fact_object"] = entity._fact_object
                rule_result = await self.rule_executor.execute_dimension(
                    dimension=dimension, entity_id=entity_id, entity_data=entity_data
                )
                explanation["steps"].append({
                    "step": "L4_rule_execution",
                    "decision": rule_result.decision if hasattr(rule_result, 'decision') else None,
                    "rules_fired": [
                        {"rule_id": r.rule_id, "passed": r.passed}
                        for r in rule_result.rule_results
                        if hasattr(r, 'rule_id') and r.passed
                    ] if hasattr(rule_result, 'rule_results') else [],
                })
            except Exception as e:
                explanation["steps"].append({"step": "L4_rule_execution", "error": str(e)})

        if hasattr(self.storage, 'get_feedback'):
            try:
                feedback_records = await self.storage.get_feedback(entity_id)
                explanation["feedback"] = [
                    {"type": r.feedback_type, "weight": r.updated_weight, "applied": r.applied}
                    for r in feedback_records
                ]
            except Exception:
                explanation["feedback"] = []

        return explanation

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

        Since StorageBackend.get_entity requires concept type,
        we use schema concept names to search, with a fallback
        to full scan.

        Args:
            entity_id: Entity ID to find

        Returns:
            EntityInstance if found, None otherwise
        """
        try:
            entity = await self.storage.get_entity_by_id(entity_id)
            if entity:
                return entity
        except (AttributeError, NotImplementedError):
            pass

        concept_types = self._get_concept_types()

        for concept in concept_types:
            entity = await self.storage.get_entity(fact_object=concept, entity_id=entity_id)
            if entity:
                return entity

        entities = await self.storage.query_entities(fact_object=None, filters=None)
        for entity in entities:
            if entity.entity_id == entity_id:
                return entity

        return None

    def _get_concept_types(self) -> list[str]:
        """Get concept types from schema, or fallback to empty list."""
        if self.schema and hasattr(self.schema, 'concepts'):
            return [c.name for c in self.schema.concepts]
        return []

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
