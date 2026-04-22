# ontology_engine/services/simulation_orchestrator.py
"""SimulationOrchestrator - coordinates simulation operations across management and consumption planes."""

from __future__ import annotations

from typing import Any

from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage
from ontology_engine.engine.rule.dependency_analyzer import DependencyAnalyzer
from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder


class SimulationOrchestrator:
    """Orchestrates simulation operations across management and consumption planes.

    Coordinates:
    - RuleLocator: for rule discovery
    - RuleTreeBuilder: for execution tree building
    - DependencyAnalyzer: for dependency analysis
    """

    def __init__(self, semantic_space_storage: SemanticSpaceStorage | None = None):
        """Initialize SimulationOrchestrator.

        Args:
            semantic_space_storage: Storage instance for semantic spaces.
                                   If None, creates a new SemanticSpaceStorage.
        """
        self._storage = semantic_space_storage or SemanticSpaceStorage()
        self._rule_locator = RuleLocator(self._storage)
        self._tree_builder = RuleTreeBuilder(semantic_space_storage=self._storage)
        self._dependency_analyzer = DependencyAnalyzer()

    async def build_execution_tree(
        self,
        schema_id: str,
        target_output: str,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        """Build execution tree from target output.

        Args:
            schema_id: The schema (space) ID to build tree within
            target_output: The output element name to build tree for
            entity_id: Optional entity ID to filter steps by category

        Returns:
            Dict containing execution tree with layers and metadata
        """
        return await self._tree_builder.build_tree(
            schema_id=schema_id,
            entity_id=entity_id,
            target_output=target_output,
        )

    async def locate_rules_producing(
        self,
        output_name: str,
        schema_id: str,
    ) -> list[dict]:
        """Locate rules that produce a specific output.

        Args:
            output_name: The name of the output element to search for
            schema_id: The schema (space) ID to search within

        Returns:
            List of rule definition dicts that have the specified output
        """
        return await self._rule_locator.locate_by_output(output_name, schema_id)

    async def analyze_dependencies(
        self,
        rules: list[dict],
    ) -> dict[str, Any]:
        """Analyze dependencies between rules.

        Args:
            rules: List of rule dicts with id, inputs, outputs

        Returns:
            Dict containing graph structure and execution levels
        """
        graph = self._dependency_analyzer.build(rules)
        levels = self._dependency_analyzer.compute_levels(graph)
        return {
            "graph": {
                "adjacency": graph.adjacency,
                "in_degree": graph.in_degree,
                "edges": graph.edges,
            },
            "levels": levels,
        }