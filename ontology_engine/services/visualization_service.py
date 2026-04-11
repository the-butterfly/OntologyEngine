"""Visualization service - orchestrates visualization module components."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.visualization.builders import RuleChainGraphBuilder, SchemaGraphBuilder
from ontology_engine.visualization.models import (
    ExecutionStepSnapshot,
    MetricSnapshot,
    RuleChainGraphData,
    SchemaGraphData,
    SimulationResult,
    VisualizationEntityOption,
)
from ontology_engine.visualization.simulator import (
    EntityNotFoundError,
    RuleChainSimulator,
    SchemaNotLoadedError,
)

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema
    from ontology_engine.services.analysis_service import AnalysisService
    from ontology_engine.services.schema_service import SchemaService
    from ontology_engine.storage.base import EntityInstance, StorageBackend


class VisualizationService:
    """Visualization data service - converts KGML Schema to graph data models."""

    def __init__(
        self,
        schema_service: SchemaService,
        analysis_service: AnalysisService,
        storage: StorageBackend,
        schema: KGMLSchema | None = None,
    ) -> None:
        self.schema_service = schema_service
        self.analysis_service = analysis_service
        self.storage = storage
        self._schema = schema

    def _get_schema(self) -> KGMLSchema:
        if self._schema:
            return self._schema
        schema = self.schema_service.get_schema()
        if not schema:
            raise SchemaNotLoadedError("Schema not loaded")
        return schema

    async def get_schema_graph(
        self,
        graph_type: str = "entity_relation",
        layer_filter: list[str] | None = None,
    ) -> SchemaGraphData:
        schema = self._get_schema()
        builder = SchemaGraphBuilder(schema)
        return builder.build(graph_type, layer_filter)

    async def get_rule_chain_graph(self, dimension: str) -> RuleChainGraphData:
        schema = self._get_schema()
        builder = RuleChainGraphBuilder(schema)
        return builder.build(dimension)

    async def list_entities(
        self,
        concept: str | None = "Supplier",
        dimension: str | None = None,
    ) -> list[VisualizationEntityOption]:
        entities = await self.storage.query_entities(concept=concept, filters=None)
        options: list[VisualizationEntityOption] = []
        for entity in entities:
            active_dimensions = self._extract_active_dimensions(entity)
            if dimension and active_dimensions and dimension not in active_dimensions:
                continue
            options.append(
                VisualizationEntityOption(
                    entity_id=entity.entity_id,
                    concept_type=entity.concept,
                    label=self._build_entity_label(entity),
                    active_dimensions=active_dimensions,
                )
            )
        return sorted(options, key=lambda item: (item.label, item.entity_id))

    async def get_metric_snapshot(
        self,
        entity_id: str,
        dimension: str = "credit_assessment",
    ) -> MetricSnapshot:
        simulation = await self.simulate_execution(entity_id=entity_id, dimension=dimension, dry_run=True)
        final_context = simulation.final_context or {}
        metrics = final_context.get("computed_metrics", {}) if isinstance(final_context, dict) else {}
        return MetricSnapshot(
            entity_id=entity_id,
            dimension=dimension,
            metrics=dict(metrics),
            outputs=dict(simulation.final_outputs),
            decision=simulation.decision,
            decision_reasoning=simulation.decision_reasoning,
        )

    async def simulate_execution(
        self,
        entity_id: str,
        dimension: str,
        overrides: dict[str, Any] | None = None,
        dry_run: bool = True,
    ) -> SimulationResult:
        schema = self._get_schema()
        simulator = RuleChainSimulator(
            rule_executor=self.analysis_service.rule_executor,
            storage=self.storage,
            schema=schema,
            metric_engine=self.analysis_service.metric_engine,
        )
        return await simulator.simulate(entity_id, dimension, overrides, dry_run)

    async def get_execution_trace(
        self,
        entity_id: str,
        dimension: str,
    ) -> list[ExecutionStepSnapshot]:
        result = await self.simulate_execution(entity_id, dimension, dry_run=True)
        return list(result.steps)

    @staticmethod
    def _extract_active_dimensions(entity: "EntityInstance") -> list[str]:
        value = entity.data.get("active_dimensions", [])
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    @staticmethod
    def _build_entity_label(entity: "EntityInstance") -> str:
        label = (
            entity.data.get("company_name")
            or entity.data.get("name")
            or entity.data.get("supplier_name")
            or entity.data.get("enterprise_name")
            or entity.data.get("invoice_no")
            or entity.data.get("contract_no")
            or entity.entity_id
        )
        if label == entity.entity_id:
            return entity.entity_id
        return f"{label} ({entity.entity_id})"
