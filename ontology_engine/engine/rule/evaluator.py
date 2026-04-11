"""Rule-focused wrapper around the shared expression engine."""

from __future__ import annotations

from typing import Any

from ontology_engine.engine.expression import ExpressionEngine, ExpressionSyntaxError


class ExpressionEvaluator:
    """Evaluate rule conditions and formula snippets consistently."""

    def __init__(self, engine: ExpressionEngine | None = None) -> None:
        self.engine = engine or ExpressionEngine()

    def evaluate(
        self,
        condition: str | list | dict | None | object,
        context: dict[str, Any],
    ) -> Any:
        """Evaluate a condition or formula against context."""
        if condition is None:
            return True

        if hasattr(condition, "expression"):
            expression = getattr(condition, "expression")
            if expression is not None:
                return self.engine.evaluate(expression, context)
            if hasattr(condition, "allOf") and getattr(condition, "allOf"):
                return self.evaluate_allOf(getattr(condition, "allOf"), context)
            if hasattr(condition, "anyOf") and getattr(condition, "anyOf"):
                return self.evaluate_anyOf(getattr(condition, "anyOf"), context)
            return True

        if isinstance(condition, dict):
            if "allOf" in condition:
                return self.evaluate_allOf(condition["allOf"], context)
            if "anyOf" in condition:
                return self.evaluate_anyOf(condition["anyOf"], context)
            if "expression" in condition:
                return self.engine.evaluate(condition["expression"], context)

        if isinstance(condition, list):
            if all(isinstance(item, dict) for item in condition):
                return self.evaluate_allOf(condition, context)
            return [self.engine.evaluate(str(item), context) for item in condition]

        if isinstance(condition, str):
            return self.engine.evaluate(condition, context)

        return True

    def evaluate_allOf(self, conditions: list[Any], context: dict[str, Any]) -> bool:
        """Evaluate all conditions in logical conjunction."""
        for cond in conditions:
            result = self.evaluate(cond, context)
            if not result:
                return False
        return True

    def evaluate_anyOf(self, conditions: list[Any], context: dict[str, Any]) -> bool:
        """Evaluate conditions in logical disjunction."""
        for cond in conditions:
            result = self.evaluate(cond, context)
            if result:
                return True
        return False


__all__ = ["ExpressionEvaluator", "ExpressionSyntaxError"]
