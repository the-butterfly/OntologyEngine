# ontology_engine/services/simulation_service.py
"""Simulation service for rule execution with dry-run mode."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ontology_engine.engine.rule.models import (
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
    ConditionClause,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator
from ontology_engine.engine.rule.operators import OperatorRegistry


@dataclass
class ConditionDetail:
    """Detailed condition evaluation result."""
    type: str  # expression, all_of, any_of
    expression: str | None = None
    sub_conditions: list[dict[str, Any]] = field(default_factory=list)
    result: bool = False
    explanation: str = ""


@dataclass
class StepSimulationResult:
    """Result of a single step simulation."""
    step_id: str
    step_name: str
    condition_result: bool
    condition_detail: ConditionDetail | None = None
    action_taken: str | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class SimulationResult:
    """Result of a rule group simulation."""
    rule_group_name: str
    steps: list[StepSimulationResult]
    final_output: dict[str, Any] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SimulationService:
    """Service for simulating rule execution without persisting results.

    Uses dry_run=True to execute rules in-memory without writing to storage
    or triggering alerts.
    """

    def __init__(self):
        """Initialize SimulationService."""
        self._evaluator = ExpressionEvaluator()

    async def simulate_rule_group(
        self,
        rule_group: RuleGroupDefinition,
        steps: list[RuleStep],
        entity_data: dict[str, Any],
        pre_computed: dict[str, Any] | None = None,
        step_filter: list[str] | None = None,
    ) -> SimulationResult:
        """Simulate execution of a rule group.

        Args:
            rule_group: Rule group definition
            steps: List of rule steps to execute
            entity_data: Entity data for evaluation
            pre_computed: Pre-computed metric values
            step_filter: Optional list of step IDs to execute

        Returns:
            SimulationResult with step-by-step details
        """
        pre_computed = pre_computed or {}
        context = {**entity_data, **pre_computed}
        computed: dict[str, Any] = {}
        alerts: list[dict[str, Any]] = []
        errors: list[str] = []
        step_results: list[StepSimulationResult] = []

        # Filter steps if specified
        if step_filter:
            steps = [s for s in steps if s.id in step_filter]

        for step in sorted(steps, key=lambda s: s.order):
            if not step.enabled:
                continue

            step_start = _get_time_ms()
            step_result = await self._simulate_step(step, context, computed)
            step_result.duration_ms = _get_time_ms() - step_start
            step_results.append(step_result)

            # Update context with computed values
            computed.update(step_result.output)

            # Check for errors
            if step_result.error:
                errors.append(f"Step {step.id}: {step_result.error}")

            # Add alerts
            if step_result.output.get("_alert"):
                alerts.append({
                    "level": step_result.output.get("_alert_level", "info"),
                    "type": step_result.output.get("_alert_type", "general"),
                    "message": step_result.output.get("_alert_message", ""),
                    "step_id": step.id,
                })

        # Compute final output
        final_output = dict(computed)
        final_output.update({
            k: v for k, v in context.items()
            if k not in entity_data and k not in computed
        })

        return SimulationResult(
            rule_group_name=rule_group.name,
            steps=step_results,
            final_output=final_output,
            alerts=alerts,
            errors=errors,
        )

    async def _simulate_step(
        self,
        step: RuleStep,
        context: dict[str, Any],
        computed: dict[str, Any],
    ) -> StepSimulationResult:
        """Simulate a single rule step.

        Args:
            step: Rule step to simulate
            context: Evaluation context
            computed: Previously computed values

        Returns:
            StepSimulationResult with details
        """
        try:
            # Evaluate condition
            condition_detail = self._evaluate_condition(step.when, {**context, **computed})
            condition_result = condition_detail.result

            if not condition_result:
                return StepSimulationResult(
                    step_id=step.id,
                    step_name=step.name,
                    condition_result=False,
                    condition_detail=condition_detail,
                    action_taken=None,
                    output={"skipped": "condition not met"},
                )

            # Execute then action
            if step.then:
                output, action_taken = await self._execute_action(
                    step.then, {**context, **computed}
                )
            else:
                output = {}
                action_taken = None

            return StepSimulationResult(
                step_id=step.id,
                step_name=step.name,
                condition_result=True,
                condition_detail=condition_detail,
                action_taken=action_taken,
                output=output,
            )

        except Exception as e:
            return StepSimulationResult(
                step_id=step.id,
                step_name=step.name,
                condition_result=False,
                condition_detail=None,
                action_taken=None,
                output={},
                error=str(e),
            )

    def _evaluate_condition(
        self,
        condition: ConditionClause,
        context: dict[str, Any],
    ) -> ConditionDetail:
        """Evaluate a condition with detailed breakdown.

        Args:
            condition: Condition to evaluate
            context: Evaluation context

        Returns:
            ConditionDetail with results and explanations
        """
        detail = ConditionDetail(
            type=condition.type,
            expression=condition.expression,
        )

        if condition.type == "expression" and condition.expression:
            result = self._evaluator.evaluate(condition.expression, context)
            detail.result = bool(result)
            detail.explanation = self._explain_expression(condition.expression, context, result)
            detail.sub_conditions = [{
                "expr": condition.expression,
                "result": result,
                "explain": detail.explanation,
            }]

        elif condition.type == "all_of" and condition.sub_conditions:
            sub_results = []
            all_passed = True
            for expr in condition.sub_conditions:
                result = self._evaluator.evaluate(expr, context)
                all_passed = all_passed and bool(result)
                sub_results.append({
                    "expr": expr,
                    "result": result,
                    "explain": self._explain_expression(expr, context, result),
                })
            detail.result = all_passed
            detail.sub_conditions = sub_results
            detail.explanation = f"ALL_OF: {all_passed}"

        elif condition.type == "any_of" and condition.sub_conditions:
            sub_results = []
            any_passed = False
            for expr in condition.sub_conditions:
                result = self._evaluator.evaluate(expr, context)
                any_passed = any_passed or bool(result)
                sub_results.append({
                    "expr": expr,
                    "result": result,
                    "explain": self._explain_expression(expr, context, result),
                })
            detail.result = any_passed
            detail.sub_conditions = sub_results
            detail.explanation = f"ANY_OF: {any_passed}"

        else:
            detail.result = True
            detail.explanation = "No condition (always true)"

        return detail

    def _explain_expression(
        self,
        expression: str,
        context: dict[str, Any],
        result: Any,
    ) -> str:
        """Generate human-readable explanation of expression evaluation.

        Args:
            expression: Expression string
            context: Evaluation context
            result: Result of evaluation

        Returns:
            Human-readable explanation
        """
        try:
            # Extract variable names from expression
            import re
            var_names = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_.]*)\b', expression)

            explanations = []
            for name in var_names:
                if name in context:
                    value = context[name]
                    if isinstance(value, dict) and "value" in value:
                        value = value["value"]
                    explanations.append(f"{name}={value}")

            if explanations:
                return f"{' AND '.join(explanations)} → {result}"
            return f"{expression} → {result}"
        except (ValueError, TypeError, KeyError):
            # Only catch parseable errors, re-raise unexpected ones
            return f"{expression} → {result}"

    async def _execute_action(
        self,
        action: ActionClause,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        """Execute an action using the operator registry.

        Args:
            action: Action to execute
            context: Evaluation context

        Returns:
            Tuple of (output dict, action_taken string)
        """
        operator_name = action.operator
        params = action.params

        try:
            operator = OperatorRegistry.get(operator_name)
            result = await operator.execute(
                inputs=params,
                config={},
                context=context,
            )
            return result, operator_name
        except KeyError:
            # Unknown operator, return params as output
            return params, operator_name
        except Exception as e:
            # Operator error, return error info
            return {"error": str(e)}, operator_name


def _get_time_ms() -> float:
    """Get current time in milliseconds."""
    import time
    return time.time() * 1000
