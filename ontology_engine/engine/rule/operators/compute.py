# ontology_engine/engine/rule/operators/compute.py
"""ComputeFormula operator."""

from typing import Any
import simpleeval

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("compute_formula")
class ComputeFormulaOperator(Operator):
    """Compute a formula and store the result.

    Inputs:
        - formula: The formula expression to evaluate
        - output_key: Where to store the result (default: "computed_value")
        - source_vars: Optional list of variable names to extract from context

    Example:
        action:
            operator: "compute_formula"
            inputs:
                formula: "credit_score * 1.2"
                output_key: "adjusted_score"
    """

    @property
    def name(self) -> str:
        return "compute_formula"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        formula = inputs.get("formula")
        if not formula:
            return {"error": "compute_formula requires 'formula' input"}

        output_key = inputs.get("output_key", "computed_value")

        try:
            # Build evaluation context from flat context
            eval_context = self._build_context(context)

            evaluator = simpleeval.SimpleEval()
            evaluator.names = eval_context
            result = evaluator.eval(formula)

            return {
                output_key: result,
                f"{output_key}_computed": True
            }
        except Exception as e:
            return {
                output_key: None,
                f"{output_key}_error": str(e)
            }

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Build a flat context dictionary for formula evaluation.

        Handles nested dicts by extracting 'value' key.
        """
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result


@OperatorRegistry.register("calculate_credit_score")
class CalculateCreditScoreOperator(Operator):
    """Calculate credit score based on metrics.

    This operator is kept for backward compatibility with legacy action names.
    """

    @property
    def name(self) -> str:
        return "calculate_credit_score"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        # Credit score calculation constants
        CREDIT_SCORE_BASE = 50
        CREDIT_SCORE_OVERDUE_RATIO_LOW = 5
        CREDIT_SCORE_OVERDUE_RATIO_MED = 10
        CREDIT_SCORE_BONUS_LOW = 15
        CREDIT_SCORE_BONUS_MED = 5
        CREDIT_SCORE_CRITICAL_PENALTY = 30
        CREDIT_SCORE_MAX = 100
        CREDIT_SCORE_MIN = 0

        # Build flat context
        eval_context = self._build_context(context)

        score = CREDIT_SCORE_BASE

        # Check for overdue invoices
        overdue_ratio = eval_context.get("overdue_invoice_ratio", 0)
        if overdue_ratio < CREDIT_SCORE_OVERDUE_RATIO_LOW:
            score += CREDIT_SCORE_BONUS_LOW
        elif overdue_ratio < CREDIT_SCORE_OVERDUE_RATIO_MED:
            score += CREDIT_SCORE_BONUS_MED

        # Check for critical alerts
        alerts = context.get("alerts", [])
        if any(a.get("level") == "critical" for a in alerts):
            score = max(CREDIT_SCORE_MIN, score - CREDIT_SCORE_CRITICAL_PENALTY)

        score = min(CREDIT_SCORE_MAX, max(CREDIT_SCORE_MIN, score))

        # Determine grade
        grade = self._get_credit_grade(score)

        return {
            "credit_score": score,
            "credit_grade": grade,
        }

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result

    def _get_credit_grade(self, score: int) -> str:
        thresholds = [
            (90, "AAA"),
            (85, "AA"),
            (80, "A"),
            (70, "BBB"),
            (60, "BB"),
            (50, "B"),
            (40, "CCC"),
            (30, "CC"),
            (20, "C"),
        ]
        for threshold, grade in thresholds:
            if score >= threshold:
                return grade
        return "D"


@OperatorRegistry.register("calculate_credit_limit")
class CalculateCreditLimitOperator(Operator):
    """Calculate credit limit based on score and grade.

    This operator is kept for backward compatibility with legacy action names.
    """

    @property
    def name(self) -> str:
        return "calculate_credit_limit"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        CREDIT_LIMIT_BASE_RATIO = 0.5
        GUARANTEE_CHAIN_PENALTY_RATE = 0.1

        multipliers = {
            "AAA": 2.0,
            "AA": 1.8,
            "A": 1.5,
            "BBB": 1.2,
            "BB": 1.0,
            "B": 0.8,
            "D": 0.5,
        }

        # Build flat context
        eval_context = self._build_context(context)

        credit_grade = eval_context.get("credit_grade", "B")
        registered_capital = eval_context.get("registered_capital", 0)
        guarantee_chain_depth = eval_context.get("guarantee_chain_depth", 0)

        base = registered_capital * CREDIT_LIMIT_BASE_RATIO
        multiplier = multipliers.get(credit_grade, 0.5)

        if guarantee_chain_depth > 0:
            multiplier = multiplier * (1 - guarantee_chain_depth * GUARANTEE_CHAIN_PENALTY_RATE)

        credit_limit = base * multiplier

        return {
            "credit_limit": credit_limit,
            "credit_grade": credit_grade,
        }

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result


@OperatorRegistry.register("determine_interest_rate")
class DetermineInterestRateOperator(Operator):
    """Determine interest rate based on credit score.

    This operator is kept for backward compatibility with legacy action names.
    """

    @property
    def name(self) -> str:
        return "determine_interest_rate"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        BASE_INTEREST_RATE = 0.05

        # Build flat context
        eval_context = self._build_context(context)

        credit_score = eval_context.get("credit_score", 50)
        risk_premium = (100 - credit_score) / 100 * BASE_INTEREST_RATE
        rate = (BASE_INTEREST_RATE + risk_premium) * 100

        return {
            "interest_rate": rate,
        }

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result
