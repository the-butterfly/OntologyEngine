# ontology_engine/services/dag_executor.py
"""DAG Executor - Executes rule tree layer by layer using Kahn algorithm."""

from __future__ import annotations

from typing import Any

from ontology_engine.core.semantic_space import SemanticSpace


class DAGExecutor:
    """Executes rules following Kahn algorithm layer ordering.

    The execution tree has layers, each layer has steps. Steps within a layer
    can be executed in parallel (no dependencies). Steps across layers have
    dependencies enforced by the topological sort in tree building.
    """

    def __init__(self, semantic_space: SemanticSpace):
        """Initialize DAG Executor.

        Args:
            semantic_space: The semantic space containing rule definitions and logics.
        """
        self._space = semantic_space

    async def execute(
        self,
        execution_tree: dict[str, Any],
        entity_data: dict[str, Any],
        input_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute rule tree from entity data with optional overrides.

        Args:
            execution_tree: Tree with layers and steps from RuleTreeBuilder
            entity_data: Entity's current attribute values
            input_overrides: Override values for what-if analysis

        Returns:
            Execution result with final_outputs, step_results, errors
        """
        working_data = dict(entity_data)
        if input_overrides:
            working_data.update(input_overrides)

        all_step_results = []
        final_outputs = {}
        errors = []

        for layer in execution_tree.get("layers", []):
            layer_results = []
            for step in layer.get("steps", []):
                result = await self._execute_step(step, working_data)
                layer_results.append(result)

                if result.get("error"):
                    errors.append(f"{step['step_id']}: {result['error']}")
                else:
                    # Update working_data with step output for downstream steps
                    step_output = result.get("output", {})
                    working_data.update(step_output)
                    # Track final outputs
                    for k, v in step_output.items():
                        final_outputs[k] = v

            all_step_results.append({
                "layer_index": layer["layer_index"],
                "layer_name": layer.get("rule_groups", []),
                "step_results": layer_results,
            })

        return {
            "final_outputs": final_outputs,
            "step_results": all_step_results,
            "errors": errors if errors else None,
        }

    async def _execute_step(
        self,
        step: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute single rule step.

        Steps have:
        - step_id: Rule definition ID
        - condition: Contains expression string
        - action: Contains operator and params (from tree building)

        Returns result with condition_result, action_taken, output, or error.
        """
        step_id = step.get("step_id", "")
        step_name = step.get("step_name", step_id)

        # 1. Evaluate condition expression
        condition = step.get("condition", {})
        expr = condition.get("expression", "")
        condition_met = self._evaluate_expression(expr, context)

        if not condition_met:
            return {
                "step_id": step_id,
                "step_name": step_name,
                "condition_result": False,
                "action_taken": "skipped",
                "output": {},
            }

        # 2. Find matching rule definition and execute its logic
        rule_defs = self._space.layers.L4_business_logic.rule_definitions
        rule_logics = self._space.layers.L4_business_logic.rule_logics

        # Find rule definition by step_id
        rd = next((r for r in rule_defs if r.get("id") == step_id), None)
        if not rd:
            return {
                "step_id": step_id,
                "step_name": step_name,
                "error": f"Rule definition {step_id} not found",
            }

        # Get logic_ids from rule definition
        logic_ids = rd.get("logic_ids", [])

        # Execute each logic (if multiple exist)
        output = {}
        action_taken = "none"
        for logic_id in logic_ids:
            logic = next((l for l in rule_logics if l.get("id") == logic_id), None)
            if not logic:
                continue

            # Evaluate the when condition of this logic
            when = logic.get("when", {})
            when_expr = when.get("expression", "")
            logic_condition_met = self._evaluate_expression(when_expr, context)

            if logic_condition_met:
                # Execute then_action
                then_action = logic.get("then_action", {})
                action_result = self._execute_action(then_action)
                output.update(action_result.get("output", {}))
                if action_result.get("action_type"):
                    action_taken = action_result["action_type"]
            else:
                # Execute else_action if condition fails and else_action exists
                else_action = logic.get("else_action")
                if else_action:
                    action_result = self._execute_action(else_action)
                    output.update(action_result.get("output", {}))
                    if action_result.get("action_type"):
                        action_taken = action_result["action_type"]

        return {
            "step_id": step_id,
            "step_name": step_name,
            "condition_result": True,
            "action_taken": action_taken,
            "output": output,
        }

    def _execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute a rule action.

        Args:
            action: Action dict with action_type, output, formula, operator

        Returns:
            Dict with action_type and output
        """
        action_type = action.get("action_type", "")
        output = action.get("output", {})
        formula = action.get("formula")

        # Handle compute action with formula
        if action_type == "compute" and formula:
            # Formula is a string expression like "credit_score * 0.8"
            computed = self._evaluate_formula(formula, {})
            if computed is not None:
                output = {"result": computed}

        return {
            "action_type": action_type,
            "output": output,
        }

    def _evaluate_expression(self, expr: str, context: dict[str, Any]) -> bool:
        """Safely evaluate condition expression.

        Handles expressions like:
        - "credit_score >= 60"
        - "annual_revenue_value >= 0"
        - "risk_level_flag == 'low_risk'"

        Args:
            expr: Condition expression string
            context: Working data with current variable values

        Returns:
            True if condition is met or expression is empty/invalid
        """
        if not expr or expr in ("true", "True"):
            return True

        try:
            # Replace variable names with their values
            # Sort by length descending to avoid partial replacements
            sorted_keys = sorted(context.keys(), key=len, reverse=True)
            eval_expr = expr

            for key in sorted_keys:
                value = context[key]
                if isinstance(value, str):
                    # Escape string values for eval
                    eval_expr = eval_expr.replace(key, f"'{value}'")
                elif isinstance(value, (int, float)):
                    eval_expr = eval_expr.replace(key, str(value))
                elif value is None:
                    eval_expr = eval_expr.replace(key, "None")

            # Evaluate the expression safely
            result = eval(eval_expr, {"__builtins__": {}}, {})
            return bool(result)
        except Exception:
            # If evaluation fails, return True to not block execution
            # This is a safety measure - failed conditions don't prevent rules from running
            return True

    def _evaluate_formula(self, formula: str, context: dict[str, Any]) -> Any:
        """Evaluate a formula/expression.

        Handles expressions like:
        - "credit_score * 0.8"
        - "min(100, annual_revenue_value / 1000000 + 50)"
        - "registered_capital_value * 0.5"

        Args:
            formula: Formula string
            context: Working data with variable values

        Returns:
            Computed value or None if evaluation fails
        """
        if not formula:
            return None

        try:
            # Replace variable names with their values
            sorted_keys = sorted(context.keys(), key=len, reverse=True)
            eval_formula = formula

            for key in sorted_keys:
                value = context[key]
                if isinstance(value, (int, float)):
                    eval_formula = eval_formula.replace(key, str(value))

            # Only allow safe math operations
            result = eval(eval_formula, {
                "__builtins__": {},
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
            }, {})
            return result
        except Exception:
            return None