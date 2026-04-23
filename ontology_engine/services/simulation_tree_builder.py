# ontology_engine/services/simulation_tree_builder.py
"""Rule Tree Builder for cross-rule-group execution.

This module provides the RuleTreeBuilder class that traces dependencies
from a target output backwards through rule groups using Kahn algorithm-style
layering to build an execution tree.
"""
from __future__ import annotations

from typing import Any, Literal

from ontology_engine.services.rule_locator import RuleLocator


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
                    "input_requirements": [...],
                },
                ...
            ],
            "total_steps": int,
            "rule_group_count": int,
        }
    """

    def __init__(self, rule_service=None, semantic_space_storage=None, rule_locator=None):
        """Initialize RuleTreeBuilder.

        Args:
            rule_service: RuleService instance for locating rule groups (legacy).
                         If None and semantic_space_storage is provided, will use RuleLocator.
            semantic_space_storage: Storage instance for accessing SemanticSpace L4 layer.
                                   Ignored if rule_locator is provided.
            rule_locator: Optional RuleLocator instance for dependency injection.
                         If provided, used directly instead of creating one internally.
        """
        self._rule_service = rule_service
        self._semantic_space_storage = semantic_space_storage
        if rule_locator:
            self._rule_locator = rule_locator
        elif semantic_space_storage:
            self._rule_locator = RuleLocator(semantic_space_storage)
        else:
            self._rule_locator = None

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
        layers = []
        current_outputs = {target_output}
        visited_groups = set()

        while current_outputs:
            next_groups = []
            for output_name in current_outputs:
                groups = await self._locate_by_output(output_name, schema_id)
                for group in groups:
                    group_id = group.get("id", group.get("name", ""))
                    if group_id not in visited_groups:
                        visited_groups.add(group_id)
                        next_groups.append(group)

            if not next_groups:
                break

            steps = await self._filter_steps(next_groups, entity_id)

            layer = {
                "layer_index": len(layers),
                "rule_groups": [g.get("name", g.get("id", "")) for g in next_groups],
                "steps": steps,
                "output_names": list(current_outputs),
                "input_requirements": _compute_input_requirements(next_groups),
            }
            layers.append(layer)

            # Trace all non-attribute inputs as they may be produced by rules or user-provided metrics
            # Use input ID (not name) for producer lookup since rules use IDs
            next_layer_inputs = set()
            for step in steps:
                for inp in step.get("inputs", []):
                    if inp.get("type") != "attribute":
                        next_layer_inputs.add(inp.get("id"))

            # Filter to only those that have L4 producers (skip pure user-provided metrics)
            current_outputs = set()
            for inp_id in next_layer_inputs:
                producer = await self._locate_by_output(inp_id, schema_id)
                if producer:
                    current_outputs.add(inp_id)

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
    ) -> list[dict]:
        """Locate rule groups that produce a specific output.

        Args:
            output_name: Output element name to search for
            schema_id: Semantic space ID for rule group lookup

        Returns:
            List of rule definition dicts that produce the specified output
        """
        if self._rule_locator:
            return await self._rule_locator.locate_by_output(output_name, schema_id)

        if self._rule_service is None:
            return []

        result = await self._rule_service.locate_rule_groups(output_name, schema_id)
        return result

    async def _filter_steps(
        self,
        groups: list[dict],
        entity_id: str | None,
    ) -> list[dict[str, Any]]:
        """Extract step information from rule groups.

        Args:
            groups: List of rule group dicts to extract steps from
            entity_id: Entity ID to filter by category (optional)

        Returns:
            List of step dictionaries with metadata
        """
        steps = []
        for group in groups:
            group_id = group.get("id", "")
            group_name = group.get("name") or group_id
            rule_type = group.get("rule_type", "constraint")
            priority = group.get("priority", 100)
            logic_ids = group.get("logic_ids", [])

            # Build step from rule definition
            step = {
                "step_id": group_id,
                "step_name": group_name,
                "rule_group_name": group_name,
                "rule_group_type": rule_type,
                "condition": {
                    "type": "expression",
                    "expression": _build_expression_from_inputs(group.get("inputs", [])),
                },
                "action": {
                    "operator": _get_operator_for_rule_type(rule_type),
                    "params": _build_action_params(group.get("outputs", [])),
                },
                "output_names": [_get_output_id(o) for o in group.get("outputs", [])],
                "depends_on": [],  # Derived from logic_ids if needed
                "priority": priority,
                "inputs": group.get("inputs", []),
            }
            steps.append(step)

        return steps


def _get_output_id(output: Any) -> str:
    """Get output ID from output dict or string."""
    if isinstance(output, dict):
        return output.get("id", "")
    return str(output)


def _compute_input_requirements(groups: list[dict]) -> list[dict]:
    """Compute input_requirements from rule groups for a layer."""
    requirements = []
    seen = set()

    for group in groups:
        for inp in group.get("inputs", []):
            name = inp.get("id") if isinstance(inp, dict) else inp
            if name and name not in seen:
                seen.add(name)
                inp_type = "attribute"
                if isinstance(inp, dict):
                    inp_type = inp.get("type", "attribute")
                requirements.append({
                    "name": name,
                    "type": inp_type,
                    "required": True,
                })

    return requirements


def _build_expression_from_inputs(inputs: list) -> str:
    """Build a simple expression string from inputs for display."""
    if not inputs:
        return "true"

    conditions = []
    for inp in inputs:
        name = inp.get("id") if isinstance(inp, dict) else inp
        inp_type = inp.get("type", "attribute") if isinstance(inp, dict) else "attribute"
        if inp_type == "attribute":
            conditions.append(f"{name} is not null")
        elif inp_type == "metric":
            conditions.append(f"{name} >= 0")
    return " AND ".join(conditions) if conditions else "true"


def _get_operator_for_rule_type(rule_type: str) -> str:
    """Get the operator name for a rule type."""
    operators = {
        "constraint": "SET_FLAG",
        "inference": "COMPUTE",
        "alert": "ALERT",
        "decision": "DECISION",
    }
    return operators.get(rule_type, "EXECUTE")


def _build_action_params(outputs: list) -> dict:
    """Build action params from outputs."""
    params = {}
    for out in outputs:
        name = out.get("id") if isinstance(out, dict) else out
        params[name] = None
    return params
