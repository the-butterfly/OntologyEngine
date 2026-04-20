"""DAG Builder for rule step topological sorting using Kahn's algorithm."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ontology_engine.engine.rule.models import RuleStep


@dataclass
class DAGNode:
    """Node in the DAG representing a rule step."""

    step_id: str
    step: RuleStep
    in_degree: int = 0
    dependents: list[str] = field(default_factory=list)  # steps that depend on this node


@dataclass
class DAGLayer:
    """A layer of nodes that can be executed in parallel."""

    index: int
    nodes: list[DAGNode]


@dataclass
class ExecutionDAG:
    """The complete execution DAG with topological layers."""

    layers: list[DAGLayer]
    step_map: dict[str, DAGNode]
    has_cycle: bool = False


class CycleError(Exception):
    """Raised when a cycle is detected in the DAG."""

    def __init__(self, message: str, cycle_path: list[str] | None = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []


class DAGBuilder:
    """Builds an execution DAG from rule steps using Kahn's algorithm.

    Kahn's algorithm performs topological sorting by repeatedly removing
    nodes with zero in-degree (no dependencies) and updating dependent nodes.

    The algorithm produces layers where nodes in the same layer can be
    executed in parallel (they have no dependency on each other).
    """

    def build(self, steps: list[RuleStep]) -> ExecutionDAG:
        """Build an execution DAG from the given rule steps.

        Args:
            steps: List of RuleStep instances with depends_on declarations.

        Returns:
            ExecutionDAG containing layers and step_map.

        Raises:
            CycleError: If a circular dependency is detected.
            KeyError: If a step depends on a non-existent step.
        """
        if not steps:
            return ExecutionDAG(layers=[], step_map={}, has_cycle=False)

        # Step 1: Create DAGNode for each step
        step_map: dict[str, DAGNode] = {}
        for step in steps:
            step_map[step.id] = DAGNode(
                step_id=step.id,
                step=step,
                in_degree=0,
                dependents=[],
            )

        # Step 2: Build edges from depends_on declarations
        for step in steps:
            node = step_map[step.id]
            for dep in step.depends_on:
                # Parse dependency: "step_id" or "rule_group/step_id"
                dep_step_id = self._parse_dependency(dep, step.rule_group)

                if dep_step_id not in step_map:
                    raise KeyError(
                        f"Step '{step.id}' depends on non-existent step '{dep_step_id}'"
                    )

                # Edge: dep -> node (dep must execute before node)
                dep_node = step_map[dep_step_id]
                dep_node.dependents.append(node.step_id)
                node.in_degree += 1

        # Step 3: Initialize queue with nodes that have in_degree == 0
        queue: deque[DAGNode] = deque()
        for node in step_map.values():
            if node.in_degree == 0:
                queue.append(node)

        # Step 4: Kahn's algorithm - BFS topological sort
        layers: list[DAGLayer] = []
        processed_count = 0

        while queue:
            # All nodes in current queue are in the same layer (can execute in parallel)
            current_layer_nodes: list[DAGNode] = []
            layer_size = len(queue)

            for _ in range(layer_size):
                node = queue.popleft()
                current_layer_nodes.append(node)
                processed_count += 1

                # Reduce in_degree of all dependent nodes
                for dependent_id in node.dependents:
                    dependent_node = step_map[dependent_id]
                    dependent_node.in_degree -= 1
                    if dependent_node.in_degree == 0:
                        queue.append(dependent_node)

            # Record this layer
            if current_layer_nodes:
                layers.append(
                    DAGLayer(index=len(layers), nodes=current_layer_nodes)
                )

        # Step 5: Cycle detection
        has_cycle = processed_count < len(steps)
        if has_cycle:
            # Find nodes involved in cycle for error reporting
            cycle_nodes = [
                node.step_id for node in step_map.values() if node.in_degree > 0
            ]
            raise CycleError(
                f"Circular dependency detected involving: {cycle_nodes}",
                cycle_path=cycle_nodes,
            )

        return ExecutionDAG(layers=layers, step_map=step_map, has_cycle=False)

    def _parse_dependency(
        self, depends_on: str, current_rule_group: str
    ) -> str:
        """Parse a depends_on declaration to extract the step_id.

        Args:
            depends_on: Dependency string, either "step_id" or "rule_group/step_id".
            current_rule_group: The rule_group of the step declaring the dependency.

        Returns:
            The step_id extracted from the dependency.
        """
        if "/" in depends_on:
            # Format: "rule_group/step_id"
            parts = depends_on.split("/", 1)
            return parts[1]
        else:
            # Same rule group: just "step_id"
            return depends_on
