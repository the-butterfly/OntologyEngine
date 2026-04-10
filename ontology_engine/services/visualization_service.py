"""Visualization service - orchestrates visualization module components."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.visualization.builders import (
    RuleChainGraphBuilder,
    SchemaGraphBuilder,
)
from ontology_engine.visualization.models import (
    ExecutionStepSnapshot,
    RuleChainGraphData,
    SchemaGraphData,
    SimulationResult,
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
    from ontology_engine.storage.duckdb import DuckDBStorage


class VisualizationService:
    """Visualization data service - converts KGML Schema to graph data models."""

    def __init__(
        self,
        schema_service: SchemaService,
        analysis_service: AnalysisService,
        storage: DuckDBStorage,
        schema: KGMLSchema | None = None,
    ) -> None:
        self.schema_service = schema_service
        self.analysis_service = analysis_service
        self.storage = storage
        self._schema = schema

    def _get_schema(self) -> KGMLSchema:
        """Get current schema, raising error if not loaded."""
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
        """Generate Schema graph data (G6 format).

        Args:
            graph_type: View type - entity_relation, metric_dependency, full, rule_overview
            layer_filter: Optional layer filter - list of "L1", "L3", "L4"

        Returns:
            SchemaGraphData with nodes, edges, layout config, and metadata
        """
        schema = self._get_schema()
        builder = SchemaGraphBuilder(schema)
        return builder.build(graph_type, layer_filter)

    async def get_rule_chain_graph(
        self,
        dimension: str,
    ) -> RuleChainGraphData:
        """Generate rule chain DAG graph data (X6 format).

        Args:
            dimension: Rule dimension name (e.g., "credit_assessment")

        Returns:
            RuleChainGraphData with rule nodes, dependency edges, and dimension info
        """
        schema = self._get_schema()
        builder = RuleChainGraphBuilder(schema)
        return builder.build(dimension)

    async def simulate_execution(
        self,
        entity_id: str,
        dimension: str,
        overrides: dict[str, Any] | None = None,
        dry_run: bool = True,
    ) -> SimulationResult:
        """Simulate rule chain execution with step-by-step snapshots.

        Args:
            entity_id: Entity ID to simulate
            dimension: Rule dimension name
            overrides: Optional variable overrides for What-if analysis
            dry_run: If True, don't write to storage

        Returns:
            SimulationResult with execution snapshots, decision, and optional comparison
        """
        schema = self._get_schema()

        # Build simulator reusing analysis service's engines
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
        """Get execution trace for an entity.

        Phase 1: Simplified - execute a dry_run.
        Phase 2: Read from rule_execution_log storage.

        Args:
            entity_id: Entity ID
            dimension: Rule dimension

        Returns:
            List of ExecutionStepSnapshot for each rule step
        """
        result = await self.simulate_execution(entity_id, dimension, dry_run=True)
        return list(result.steps)
