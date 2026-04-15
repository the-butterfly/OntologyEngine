"""Tests for ExpressionEngine sandbox enhancements."""

import pytest
from ontology_engine.engine.expression.engine import ExpressionEngine, ExpressionSyntaxError


class TestDaysSinceAndClamp:
    """Verify extended function registry."""

    def test_days_since(self):
        engine = ExpressionEngine()
        result = engine.evaluate("days_since('2024-01-01')", {})
        assert isinstance(result, int)
        assert result > 400  # should be well over a year

    def test_clamp(self):
        engine = ExpressionEngine()
        assert engine.evaluate("clamp(5, 0, 10)", {}) == 5
        assert engine.evaluate("clamp(-1, 0, 10)", {}) == 0
        assert engine.evaluate("clamp(15, 0, 10)", {}) == 10


class TestAstevalMultilineFallback:
    """Verify multi-line expressions fall back to asteval."""

    def test_multiline_if_else(self):
        engine = ExpressionEngine()
        # asteval supports nested if-else but not elif
        formula = """
score = 70
if score >= 80:
    result = 20
else:
    if score >= 60:
        result = 10
    else:
        result = 0
result
"""
        assert engine.evaluate(formula, {}) == 10

    def test_multiline_business_stability_proxy(self):
        engine = ExpressionEngine()
        context = {
            "contract_fulfillment_rate": 85,
            "core_enterprise_count": 2,
            "overdue_invoice_ratio": 3,
        }
        formula = """
score = 50
if contract_fulfillment_rate >= 80:
    score += 20
elif contract_fulfillment_rate >= 50:
    score += 10
if core_enterprise_count >= 3:
    score += 15
elif core_enterprise_count >= 1:
    score += 5
if overdue_invoice_ratio < 5:
    score += 15
elif overdue_invoice_ratio < 10:
    score += 5
min(score, 100)
"""
        assert engine.evaluate(formula, context) == 90


class TestSecurityHardening:
    """Verify dangerous operations are blocked."""

    def test_import_blocked_in_simpleeval(self):
        engine = ExpressionEngine()
        with pytest.raises(ExpressionSyntaxError):
            engine.evaluate("__import__('os').system('ls')", {})

    def test_import_blocked_in_asteval(self):
        engine = ExpressionEngine()
        with pytest.raises(ExpressionSyntaxError):
            engine.evaluate("\nimport os\nos.system('ls')\n", {})

    def test_bitwise_operators_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises(ExpressionSyntaxError):
            engine.evaluate("1 << 2", {})

    def test_mod_operator_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises(ExpressionSyntaxError):
            engine.evaluate("10 % 3", {})
