# ontology_engine/engine/rule/operators/weighted_sum.py
"""Weighted Sum operator for composite metric calculation."""

from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("weighted_sum")
class WeightedSumOperator(Operator):
    """Calculate weighted sum with optional grade multipliers.

    Computes a weighted sum of input variables with optional grade-based
    multiplier adjustment.

    Args:
        inputs: Dict with:
            - weights: List of {input: str, weight: float}
            - grade_multipliers: Optional dict of grade -> multiplier
            - grade_input: Optional input variable for grade lookup
        config: Operator configuration (unused)
        context: Execution context with entity data and computed metrics

    Returns:
        Dict with the calculated weighted sum as {output_name: result}

    Example:
        params:
            output: credit_score
            weights:
                - input: business_stability
                  weight: 0.30
                - input: tax_compliance
                  weight: 0.25
            grade_multipliers:
                AAA: 1.8
                AA: 1.5
            grade_input: credit_grade
    """

    @property
    def name(self) -> str:
        return "weighted_sum"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        weights = inputs.get("weights", [])
        grade_multipliers = inputs.get("grade_multipliers", {})
        grade_input = inputs.get("grade_input")
        output_name = inputs.get("output", "weighted_sum_result")

        # Build evaluation context from entity data and computed metrics
        eval_context = self._build_context(context)

        # Calculate weighted sum
        total = 0.0
        for item in weights:
            input_name = item.get("input")
            weight = item.get("weight", 0.0)

            # Get value from context
            value = self._get_value(input_name, eval_context)
            if value is not None:
                try:
                    total += float(value) * weight
                except (ValueError, TypeError):
                    pass

        # Apply grade multiplier if specified
        if grade_multipliers and grade_input:
            grade = self._get_value(grade_input, eval_context)
            if grade and str(grade) in grade_multipliers:
                multiplier = grade_multipliers[str(grade)]
                total = total * multiplier

        return {
            output_name: round(total, 4),
            f"{output_name}_raw": round(total, 4),
        }

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Build evaluation context from various sources."""
        eval_context: dict[str, Any] = {}

        # Entity data
        if "entity_data" in context:
            eval_context.update(context["entity_data"])

        # Computed metrics
        if "computed_metrics" in context:
            eval_context.update(context["computed_metrics"])

        # Direct context values
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool, list, dict)):
                eval_context[key] = value

        return eval_context

    def _get_value(self, name: str, context: dict[str, Any]) -> Any:
        """Get a value from context, supporting nested access."""
        if name is None:
            return None

        # Direct access
        if name in context:
            return context[name]

        # Nested access (e.g., "registered_capital.value")
        parts = name.split(".")
        value: Any = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
