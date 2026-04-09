# ontology_engine/engine/metric/dag.py
"""Metric dependency DAG management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from ontology_engine.engine.metric.errors import MetricDAGError

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import MetricDefinition


class MetricDAG:
    """Directed acyclic graph for metric dependencies.

    Builds a dependency graph from metric definitions and provides
    topological ordering for computation.
    """

    def __init__(self, metrics: list["MetricDefinition"]):
        """Initialize DAG with metric definitions.

        Args:
            metrics: List of MetricDefinition objects from schema

        Raises:
            MetricDAGError: If circular dependencies are detected
        """
        self.metrics: dict[str, "MetricDefinition"] = {m.name: m for m in metrics}
        self.graph: nx.DiGraph = self._build()
        self._validate()

    def _build(self) -> nx.DiGraph:
        """Build the dependency graph.

        Edges go from dependency to dependent (i.e., if A depends on B,
        there's an edge B -> A, meaning B must be computed before A).
        """
        G = nx.DiGraph()

        for metric in self.metrics.values():
            G.add_node(metric.name, metric=metric)
            for dep in metric.dependencies:
                if dep in self.metrics:
                    G.add_edge(dep, metric.name)

        return G

    def _validate(self) -> None:
        """Validate that the graph is acyclic.

        Raises:
            MetricDAGError: If circular dependencies exist
        """
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise MetricDAGError(f"Metric dependencies contain cycles: {cycles}")

    def topological_order(
        self,
        target_metrics: list[str] | None = None
    ) -> list[str]:
        """Get topological order for metric computation.

        Args:
            target_metrics: Optional list of target metrics. If provided,
                           only returns metrics needed for these targets.

        Returns:
            List of metric names in computation order
        """
        if target_metrics is None:
            return list(nx.topological_sort(self.graph))

        # Collect all required metrics (targets + their transitive deps)
        required: set[str] = set()
        for target in target_metrics:
            if target not in self.metrics:
                continue
            required.add(target)
            if target in self.graph:
                required.update(nx.ancestors(self.graph, target))

        # Filter and sort
        subgraph = self.graph.subgraph(required & set(self.graph.nodes))
        return list(nx.topological_sort(subgraph))

    def get_dependencies(self, metric_name: str) -> set[str]:
        """Get direct dependencies for a metric.

        Args:
            metric_name: Name of the metric

        Returns:
            Set of metric names this metric directly depends on
        """
        if metric_name not in self.graph:
            return set()
        return set(self.graph.predecessors(metric_name))

    def get_all_dependencies(self, metric_name: str) -> set[str]:
        """Get all transitive dependencies for a metric.

        Args:
            metric_name: Name of the metric

        Returns:
            Set of all metric names this metric depends on
        """
        if metric_name not in self.graph:
            return set()
        return nx.ancestors(self.graph, metric_name)

    def get_dependents(self, metric_name: str) -> set[str]:
        """Get metrics that directly depend on this one.

        Args:
            metric_name: Name of the metric

        Returns:
            Set of metric names that depend on this one
        """
        if metric_name not in self.graph:
            return set()
        return set(self.graph.successors(metric_name))
