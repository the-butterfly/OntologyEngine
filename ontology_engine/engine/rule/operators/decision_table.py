# ontology_engine/engine/rule/operators/decision_table.py
"""Decision table operator for multi-condition combinatory decisions."""

from __future__ import annotations

from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("decision_table")
class DecisionTableOperator(Operator):
    """Multi-condition decision table operator.

    Supports:
    - Multi-column condition matching (AND semantics)
    - Wildcard "*" (matches any value)
    - List matching (value in list)
    - Row-priority matching (first match wins)

    Inputs:
        - conditions: List of condition column definitions
            - each: {name: <str>}  - field name to match
        - rules: List of decision rows
            - each: {conditions: [...], output: {...}}
        - default: Default output if no rule matches

    Example:
        action:
            operator: "decision_table"
            inputs:
                conditions:
                    - name: "credit_score_bin"
                    - name: "debt_ratio_bin"
                rules:
                    - conditions: ["LOW", "LOW"]
                      output: {decision: "APPROVE", rate: 0.04}
                    - conditions: ["HIGH", "*"]
                      output: {decision: "REJECT"}
                default: {decision: "REVIEW"}
    """

    @property
    def name(self) -> str:
        return "decision_table"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        conditions = inputs.get("conditions", [])
        rules = inputs.get("rules", [])
        default = inputs.get("default", {})

        # Build evaluation context
        eval_context = self._build_context(context)

        # Get actual values for each condition column
        actual_values: list[Any] = []
        for cond in conditions:
            cond_name = cond.get("name", "")
            actual_values.append(eval_context.get(cond_name))

        # Match rules in order (first match wins)
        for rule in rules:
            rule_conds = rule.get("conditions", [])
            if self._matches(actual_values, rule_conds):
                output = rule.get("output", {})
                output["_matched_rule"] = True
                output["_matched_conditions"] = rule_conds
                return output

        # Default
        default_out = dict(default) if default else {}
        default_out["_matched_rule"] = False
        default_out["_matched_conditions"] = None
        return default_out

    def _matches(self, actual: list[Any], pattern: list[Any]) -> bool:
        """Check if actual values match the rule pattern."""
        if len(actual) != len(pattern):
            return False
        for a, p in zip(actual, pattern):
            if p == "*":
                continue
            if isinstance(p, list) and a not in p:
                return False
            if a != p:
                return False
        return True

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result
