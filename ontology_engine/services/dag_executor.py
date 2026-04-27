# ontology_engine/services/dag_executor.py
"""DAG Executor - Executes rule tree layer by layer using Kahn algorithm."""

from __future__ import annotations

from typing import Any

from ontology_engine.core.semantic_space import SemanticSpace
from ontology_engine.engine.expression.engine import ExpressionEngine


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
        - condition: Contains expression string (for display only, not evaluated here)
        - action: Contains operator and params (from tree building)

        Returns result with condition_result, action_taken, output, or error.
        """
        import time

        step_id = step.get("step_id", "")
        step_name = step.get("step_name", step_id)
        start_time = time.time()

        # Note: Step-level condition is NOT evaluated here.
        # The actual condition evaluation comes from rule_logics.when.expression below.
        # Step.condition.expression is for display/human readable purposes only.

        # 1. Find matching rule definition and execute its logic
        rule_defs = self._space.layers.L4_business_logic.rule_definitions
        rule_logics = self._space.layers.L4_business_logic.rule_logics

        # Find rule definition by step_id
        rd = next((r for r in rule_defs if r.get("id") == step_id), None)
        if not rd:
            return {
                "step_id": step_id,
                "step_name": step_name,
                "condition_result": False,
                "action_taken": "error",
                "output": {},
                "input_values_used": {},
                "error": f"Rule definition {step_id} not found",
                "duration_ms": int((time.time() - start_time) * 1000),
            }

        # Get logic_ids from rule definition
        logic_ids = rd.get("logic_ids", [])

        # Track condition details for display
        condition_details = []
        any_condition_met = False

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

            condition_details.append({
                "logic_id": logic_id,
                "expression": when_expr,
                "result": logic_condition_met,
            })

            if logic_condition_met:
                any_condition_met = True
                # Execute then_action
                then_action = logic.get("then_action", {})
                action_result = self._execute_action(then_action, context)
                output.update(action_result.get("output", {}))
                if action_result.get("action_type"):
                    action_taken = action_result["action_type"]
            else:
                # Execute else_action if condition fails and else_action exists
                else_action = logic.get("else_action")
                if else_action:
                    action_result = self._execute_action(else_action, context)
                    output.update(action_result.get("output", {}))
                    if action_result.get("action_type"):
                        action_taken = action_result["action_type"]

        duration_ms = int((time.time() - start_time) * 1000)

        # Build condition detail for frontend
        condition_detail = None
        if condition_details:
            if len(condition_details) == 1:
                cd = condition_details[0]
                condition_detail = {
                    "type": "expression",
                    "expression": cd["expression"],
                    "result": cd["result"],
                    "explanation": f"Condition '{cd['expression']}' evaluated to {cd['result']}",
                }
            else:
                condition_detail = {
                    "type": "all_of",
                    "sub_conditions": [cd["expression"] for cd in condition_details],
                    "result": all(cd["result"] for cd in condition_details),
                    "explanation": f"All conditions evaluated: {all(cd['result'] for cd in condition_details)}",
                }

        # Collect input values used for this step
        input_values_used = {}
        for inp in step.get("inputs", []):
            inp_id = inp.get("id") if isinstance(inp, dict) else inp
            if inp_id and inp_id in context:
                input_values_used[inp_id] = context[inp_id]

        return {
            "step_id": step_id,
            "step_name": step_name,
            "condition_result": any_condition_met,
            "condition_detail": condition_detail,
            "action_taken": action_taken,
            "output": output,
            "input_values_used": input_values_used,
            "duration_ms": duration_ms,
        }

    def _execute_action(self, action: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Execute a rule action.

        Args:
            action: Action dict with action_type, output, formula, operator
            context: Working data with current variable values

        Returns:
            Dict with action_type and output
        """
        action_type = action.get("action_type", "")
        output = dict(action.get("output", {}))
        formula = action.get("formula")

        # Handle compute action with formula - evaluate formula with context
        if action_type == "compute" and formula:
            computed = self._evaluate_formula(formula, context)
            if computed is not None:
                # Assign computed value to the correct output field
                if len(output) == 1:
                    key = list(output.keys())[0]
                    output = {key: computed}
                elif len(output) > 1:
                    output = {k: computed for k in output.keys()}
                else:
                    output = {"result": computed}
        elif action_type == "compute" and output:
            # No explicit formula - check if output values contain computation formulas
            # (e.g., output like {"credit_score": "min(100, $metric:credit_score + 5)"}
            # or {"recommended_credit_limit": "base = registered_capital_value * 0.5\n..."}
            evaluated = {}
            for key, val in output.items():
                if isinstance(val, str) and self._looks_like_formula(val):
                    computed = self._evaluate_formula(val, context)
                    if computed is not None:
                        evaluated[key] = computed
                    else:
                        # Formula evaluation failed, keep original value
                        evaluated[key] = val
                else:
                    evaluated[key] = val
            output = evaluated

        return {
            "action_type": action_type,
            "output": output,
        }

    def _looks_like_formula(self, value: str) -> bool:
        """Check if a string value looks like a computation formula vs a simple value."""
        if not isinstance(value, str):
            return False
        # Simple pattern: looks like a formula if it contains operators, keywords, or newlines
        # that indicate computation logic rather than a simple literal value
        formula_indicators = ['\n', '=', 'if ', 'min(', 'max(', 'def ', 'lambda']
        return any(indicator in value for indicator in formula_indicators)

    def _evaluate_expression(self, expr: str, context: dict[str, Any]) -> bool:
        """Safely evaluate condition expression using ExpressionEngine.

        Args:
            expr: Condition expression string (e.g., "credit_score >= 700")
            context: Working data with current variable values

        Returns:
            True if condition is met or expression is empty/invalid
        """
        if not expr or expr in ("true", "True"):
            return True

        try:
            engine = ExpressionEngine()
            result = engine.evaluate(expr, context)
            return bool(result)
        except Exception:
            # If evaluation fails, return True to not block execution
            # This is a safety measure - failed conditions don't prevent rules from running
            return True

    def _evaluate_formula(self, formula: str, context: dict[str, Any]) -> Any:
        """Evaluate a formula/expression using ExpressionEngine.

        Args:
            formula: Formula string (e.g., "credit_score * 0.8")
            context: Working data with variable values

        Returns:
            Computed value or None if evaluation fails
        """
        if not formula:
            return None

        try:
            engine = ExpressionEngine()
            result = engine.evaluate(formula, context)
            return result
        except Exception:
            return None