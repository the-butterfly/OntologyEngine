"""Dependency analysis for rule execution ordering."""
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class DependencyGraph:
    """Represents a dependency graph for rule execution.

    Attributes:
        adjacency: Maps rule_id to list of dependent rule_ids.
        in_degree: In-degree count for each rule.
        edges: List of edge dicts with source, target, via_element.
        rules: List of all rule ids in the graph.
    """

    adjacency: dict[str, list[str]] = field(default_factory=dict)
    in_degree: dict[str, int] = field(default_factory=dict)
    edges: list[dict[str, str]] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)

    def compute_levels(self) -> dict[str, int]:
        """Compute execution level for each rule using Kahn's algorithm.

        Returns:
            Dict mapping rule_id to execution level (0-indexed).
            Rules with no dependencies get level 0.
        """
        levels: dict[str, int] = {}
        # Initialize levels for rules with no dependencies (in_degree == 0)
        # Track current frontier
        frontier = [rule for rule in self.rules if self.in_degree.get(rule, 0) == 0]
        current_level = 0

        while frontier:
            next_frontier = []
            for rule in frontier:
                if rule not in levels:
                    levels[rule] = current_level
                for dependent in self.adjacency.get(rule, []):
                    # Decrease in-degree for dependent
                    new_degree = self.in_degree.get(dependent, 0) - 1
                    self.in_degree[dependent] = new_degree
                    if new_degree == 0:
                        next_frontier.append(dependent)
            frontier = next_frontier
            current_level += 1

        # Handle any remaining rules not reached (cyclic or unreachable)
        for rule in self.rules:
            if rule not in levels:
                levels[rule] = 0

        return levels


class DependencyAnalyzer:
    """Analyzes dependencies between rules for execution ordering.

    Rule A depends on Rule B if A's inputs overlap with B's outputs.
    """

    def build(self, rules: list[dict]) -> DependencyGraph:
        """Build dependency graph from rules.

        Args:
            rules: List of rule dicts with id, inputs, outputs.

        Returns:
            DependencyGraph with adjacency, in_degree, edges, and rules.
        """
        adjacency: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)
        edges: list[dict[str, str]] = []
        rule_ids: list[str] = []

        # Collect all output element ids for each rule
        output_map: dict[str, set[str]] = {}
        for rule in rules:
            rule_id = rule["id"]
            rule_ids.append(rule_id)
            outputs = rule.get("outputs", [])
            output_map[rule_id] = {elem["id"] for elem in outputs}
            # Initialize adjacency list for each rule
            if rule_id not in adjacency:
                adjacency[rule_id] = []

        # Build dependencies: rule depends on rules that produce its inputs
        for rule in rules:
            rule_id = rule["id"]
            inputs = rule.get("inputs", [])
            input_ids = {elem["id"] for elem in inputs}

            for prev_rule in rules:
                prev_rule_id = prev_rule["id"]
                if prev_rule_id == rule_id:
                    continue
                # If this rule's inputs overlap with prev_rule's outputs, depends on prev_rule
                if input_ids & output_map.get(prev_rule_id, set()):
                    adjacency[prev_rule_id].append(rule_id)
                    edges.append({
                        "source": prev_rule_id,
                        "target": rule_id,
                        "via_element": list(input_ids & output_map[prev_rule_id])[0]
                    })
                    in_degree[rule_id] += 1

        # Ensure all rules have entries in in_degree
        for rule_id in rule_ids:
            if rule_id not in in_degree:
                in_degree[rule_id] = 0

        return DependencyGraph(
            adjacency=dict(adjacency),
            in_degree=dict(in_degree),
            edges=edges,
            rules=rule_ids
        )

    def compute_levels(self, graph: DependencyGraph) -> dict[str, int]:
        """Compute execution levels for the dependency graph.

        Args:
            graph: The dependency graph.

        Returns:
            Dict mapping rule_id to execution level.
        """
        return graph.compute_levels()