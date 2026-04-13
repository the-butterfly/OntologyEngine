# ontology_engine/engine/rule/operators/switch.py
"""Switch operator for multi-branch selection."""

from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("switch")
class SwitchOperator(Operator):
    """Multi-branch selection based on input value.

    Similar to switch/case in programming languages.
    Evaluates conditions in order and returns the first match.

    Inputs:
        - value: The value to evaluate
        - cases: List of case definitions
            - each case: {condition: "<expression>", result: <value>}
        - default: Default result if no case matches

    Example:
        action:
            operator: "switch"
            inputs:
                value: "credit_score"
                cases:
                    - condition: ">= 90"
                      result: "AAA"
                    - condition: ">= 80"
                      result: "A"
                default: "B"
    """

    @property
    def name(self) -> str:
        return "switch"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        value_name = inputs.get("value")
        cases = inputs.get("cases", [])
        default = inputs.get("default")

        # Get the actual value from context
        eval_context = self._build_context(context)
        value = eval_context.get(value_name) if value_name else None

        # Try each case condition
        for case in cases:
            condition = case.get("condition")
            result_value = case.get("result")

            if condition and self._evaluate_condition(condition, value, eval_context):
                return {
                    "switch_result": result_value,
                    "matched_case": condition
                }

        # Default case
        return {
            "switch_result": default,
            "matched_case": "default"
        }

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result

    def _evaluate_condition(self, condition: str, value: Any, context: dict[str, Any]) -> bool:
        """Evaluate a condition like '>= 90' against a value."""
        condition = condition.strip()

        # Handle comparison operators
        operators = [">=", "<=", ">", "<", "==", "!="]
        for op in operators:
            if condition.startswith(op):
                threshold_str = condition[len(op):].strip()
                try:
                    threshold = float(threshold_str)
                    if op == ">=":
                        return value >= threshold
                    elif op == "<=":
                        return value <= threshold
                    elif op == ">":
                        return value > threshold
                    elif op == "<":
                        return value < threshold
                    elif op == "==":
                        return value == threshold
                    elif op == "!=":
                        return value != threshold
                except (ValueError, TypeError):
                    return False

        # If no operator, treat as equality check
        return str(value) == condition


@OperatorRegistry.register("binning")
class BinningOperator(Operator):
    """Discretize continuous value into bins.

    Inputs:
        - value: The value to bin
        - bins: List of bin definitions
            - each bin: {min: <num>, max: <num>, label: <str>}
        - default: Default label if value doesn't fit any bin

    Example:
        action:
            operator: "binning"
            inputs:
                value: "overdue_ratio"
                bins:
                    - min: 0
                      max: 5
                      label: "LOW"
                    - min: 5
                      max: 10
                      label: "MED"
                default: "HIGH"
    """

    @property
    def name(self) -> str:
        return "binning"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        value_name = inputs.get("value")
        bins = inputs.get("bins", [])
        default = inputs.get("default", "UNKNOWN")

        # Get the actual value from context
        eval_context = self._build_context(context)
        value = eval_context.get(value_name) if value_name else None

        try:
            value = float(value)
        except (ValueError, TypeError):
            return {"bin": default, "bin_error": "invalid_value"}

        # Check each bin (support inclusive_max)
        for bin_def in bins:
            min_val = bin_def.get("min", float("-inf"))
            max_val = bin_def.get("max", float("inf"))
            inclusive_max = bin_def.get("inclusive_max", False)
            label = bin_def.get("label", "UNKNOWN")
            bin_description = bin_def.get("description", "")

            if inclusive_max:
                if min_val <= value <= max_val:
                    return {"bin": label, "bin_value": value, "bin_description": bin_description}
            else:
                if min_val <= value < max_val:
                    return {"bin": label, "bin_value": value, "bin_description": bin_description}

        return {"bin": default, "bin_value": value, "bin_description": "default"}

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result


@OperatorRegistry.register("scorecard")
class ScorecardOperator(Operator):
    """Scorecard calculation - weighted score from multiple factors.

    Inputs:
        - factors: List of factor definitions
            - each factor: {name: <str>, weight: <num>, transform: <expression>}
        - output_key: Where to store result (default: "scorecard_score")
        - range_min: Minimum score (default: 0)
        - range_max: Maximum score (default: 100)

    Example:
        action:
            operator: "scorecard"
            inputs:
                factors:
                    - name: "payment_history"
                      weight: 0.3
                      transform: "payment_score / 10"
                    - name: "utilization"
                      weight: 0.2
                      transform: "1 - utilization_rate"
                output_key: "credit_scorecard"
    """

    @property
    def name(self) -> str:
        return "scorecard"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        factors = inputs.get("factors", [])
        output_key = inputs.get("output_key", "scorecard_score")
        range_min = inputs.get("range_min", 0)
        range_max = inputs.get("range_max", 100)

        # Build flat context for evaluation
        eval_context = self._build_context(context)

        total_score = 0.0
        total_weight = 0.0
        factor_results = []

        for factor in factors:
            factor_name = factor.get("name")
            weight = factor.get("weight", 1.0)
            transform = factor.get("transform")

            if not factor_name:
                continue

            # Get factor value
            factor_value = eval_context.get(factor_name, 0)

            # Apply transform if specified
            if transform:
                try:
                    import simpleeval
                    evaluator = simpleeval.SimpleEval()
                    evaluator.names = {**eval_context, "value": factor_value}
                    factor_value = evaluator.eval(transform)
                except Exception:
                    factor_value = 0

            # Convert to numeric
            try:
                factor_value = float(factor_value)
            except (ValueError, TypeError):
                factor_value = 0

            total_score += factor_value * weight
            total_weight += weight
            factor_results.append({
                "name": factor_name,
                "value": factor_value,
                "weight": weight
            })

        # Normalize by total weight
        if total_weight > 0:
            normalized_score = total_score / total_weight * sum(f.get("weight", 1) for f in factors)
        else:
            normalized_score = 0

        # Clip to range
        final_score = max(range_min, min(range_max, normalized_score))

        # Grade mapping support
        grade = None
        grade_mapping = inputs.get("grade_mapping", [])
        if grade_mapping:
            sorted_grades = sorted(grade_mapping, key=lambda g: g.get("min_score", 0), reverse=True)
            for gm in sorted_grades:
                if final_score >= gm.get("min_score", 0):
                    grade = gm.get("grade")
                    break

        # WOE mode support
        mode = inputs.get("mode", "simple")
        if mode == "woe":
            import math

            base_score = inputs.get("base_score", 600)
            pdo = inputs.get("pdo", 20)
            base_odds = inputs.get("base_odds", 1.0)
            woe_variables = inputs.get("woe_variables", [])
            woe_values = []
            for wv in woe_variables:
                binning_input = wv.get("binning_input", "")
                woe_bins = wv.get("bins", [])
                input_val = eval_context.get(binning_input)
                for b in woe_bins:
                    if str(b.get("bin", "")) == str(input_val) or b.get("bin") == input_val:
                        woe_values.append(b.get("woe", 0.0))
                        break
            if woe_values:
                log_odds = math.log(base_odds)
                for woe_val in woe_values:
                    log_odds += woe_val
                final_score = base_score + pdo / math.log(2) * log_odds
                final_score = max(range_min, min(range_max, final_score))

        result = {
            output_key: round(final_score, 2),
            f"{output_key}_factors": factor_results,
        }
        if grade:
            result[f"{output_key}_grade"] = grade
        if mode == "woe":
            result[f"{output_key}_mode"] = "woe"
        return result

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result
