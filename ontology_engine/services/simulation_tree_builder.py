# ontology_engine/services/simulation_tree_builder.py
"""Rule Tree Builder for cross-rule-group execution.

This module provides the RuleTreeBuilder class that traces dependencies
from a target output backwards through rule groups using Kahn algorithm-style
layering to build an execution tree.
"""
from __future__ import annotations

from typing import Any

from ontology_engine.engine.rule.models import RuleGroupDefinition


class RuleTreeBuilder:
    """Builds execution tree from target output, tracing dependencies.

    This builder traces backwards from a target output through rule groups,
    building layers (Kahn algorithm-style) where each layer contains rule
    groups that need to execute before the next layer can proceed.

    The execution tree structure:
        {
            "schema_id": str,
            "target_output": str,
            "layers": [
                {
                    "layer_index": int,
                    "rule_groups": [str, ...],
                    "steps": [...],
                    "output_names": [str, ...],
                },
                ...
            ],
            "total_steps": int,
            "rule_group_count": int,
        }
    """

    def __init__(self, rule_service=None):
        """Initialize RuleTreeBuilder.

        Args:
            rule_service: RuleService instance for locating rule groups.
                         If None, must be provided later or _locate_by_output
                         must be overridden.
        """
        self._rule_service = rule_service

    async def build_tree(
        self,
        schema_id: str,
        entity_id: str | None,
        target_output: str,
    ) -> dict[str, Any]:
        """Build an execution tree for the target output.

        Starting from a target output element, this method:
        1. Locates all rule groups that produce the target output
        2. Traces their input dependencies recursively
        3. Builds layers using Kahn algorithm-style approach

        Args:
            schema_id: Semantic space ID for rule group lookup
            entity_id: Entity ID to filter steps by category (optional)
            target_output: The output element name to build tree for

        Returns:
            Dict containing execution tree with layers and metadata
        """
        # 1. Trace dependencies recursively using Kahn algorithm-style layering
        # Note: The loop starts with current_outputs = {target_output} and
        # finds groups producing that output in the first iteration
        layers = []
        current_outputs = {target_output}
        visited_groups = set()

        while current_outputs:
            # Find groups producing current outputs
            next_groups = []
            for output_name in current_outputs:
                groups = await self._locate_by_output(output_name, schema_id)
                for group in groups:
                    if group.name not in visited_groups:
                        visited_groups.add(group.name)
                        next_groups.append(group)

            if not next_groups:
                break

            # 3. Filter steps by entity category
            steps = await self._filter_steps(next_groups, entity_id)

            # 4. Build layer
            layers.append({
                "layer_index": len(layers),
                "rule_groups": [g.name for g in next_groups],
                "steps": steps,
                "output_names": list(current_outputs),
            })

            # 5. Collect new input dependencies for next iteration
            current_outputs = set()
            for step in steps:
                for inp in step.get("inputs", []):
                    if inp.get("type") == "attribute":
                        current_outputs.add(inp["name"])

        return {
            "schema_id": schema_id,
            "target_output": target_output,
            "layers": layers,
            "total_steps": sum(len(layer["steps"]) for layer in layers),
            "rule_group_count": len(visited_groups),
        }

    async def _locate_by_output(
        self,
        output_name: str,
        schema_id: str,
    ) -> list[RuleGroupDefinition]:
        """Locate rule groups that produce a specific output.

        Args:
            output_name: Output element name to search for
            schema_id: Semantic space ID for rule group lookup

        Returns:
            List of RuleGroupDefinition that produce the specified output
        """
        if self._rule_service is None:
            # Return empty list if no rule service available
            return []

        result = await self._rule_service.locate_rule_groups(output_name, schema_id)
        return result

    async def _filter_steps(
        self,
        groups: list[RuleGroupDefinition],
        entity_id: str | None,
    ) -> list[dict[str, Any]]:
        """Filter steps from rule groups by entity category.

        Args:
            groups: List of rule groups to extract steps from
            entity_id: Entity ID to filter by category (optional)

        Returns:
            List of step dictionaries with metadata
        """
        # TODO: Implement actual step filtering by entity category
        # For now, return empty list as placeholder
        # Real implementation would:
        # 1. Get steps for each rule group
        # 2. Filter by applies_to.categories for the entity
        # 3. Return step metadata including inputs/outputs
        return []
