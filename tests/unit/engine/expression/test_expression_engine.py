"""Tests for ExpressionEngine L0/L1 execution model."""

import pytest
from ontology_engine.engine.expression.engine import ExpressionEngine, ExpressionSyntaxError
from ontology_engine.engine.expression.errors import (
    FormulaError,
    FormulaSecurityError,
    FormulaSyntaxError,
)


class TestDaysSinceAndClamp:

    def test_days_since(self):
        engine = ExpressionEngine()
        result = engine.evaluate("days_since('2024-01-01')", {})
        assert isinstance(result, int)
        assert result > 400

    def test_clamp(self):
        engine = ExpressionEngine()
        assert engine.evaluate("clamp(5, 0, 10)", {}) == 5
        assert engine.evaluate("clamp(-1, 0, 10)", {}) == 0
        assert engine.evaluate("clamp(15, 0, 10)", {}) == 10


class TestAstevalMultilineFallback:

    def test_multiline_if_else(self):
        engine = ExpressionEngine()
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

    def test_import_blocked_in_simpleeval(self):
        engine = ExpressionEngine()
        with pytest.raises((ExpressionSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("__import__('os').system('ls')", {})

    def test_import_blocked_in_asteval(self):
        engine = ExpressionEngine()
        with pytest.raises((ExpressionSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("\nimport os\nos.system('ls')\n", {})

    def test_bitwise_operators_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises((ExpressionSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("1 << 2", {})

    def test_mod_operator_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises((ExpressionSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("10 % 3", {})


class TestL0L1AutoSelection:

    def test_l0_simple_expression(self):
        engine = ExpressionEngine()
        assert engine._select_executor("1 + 2") == "l0"

    def test_l1_multiline(self):
        engine = ExpressionEngine()
        assert engine._select_executor("x = 1\ny = 2") == "l1"

    def test_l1_control_flow(self):
        engine = ExpressionEngine()
        assert engine._select_executor("if x > 0: pass") == "l1"

    def test_l1_list_literal(self):
        engine = ExpressionEngine()
        assert engine._select_executor("sum([1, 2, 3])") == "l1"


class TestExtendedFunctionLibrary:

    def test_string_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("upper('abc')") == "ABC"
        assert engine.evaluate("lower('ABC')") == "abc"
        assert engine.evaluate("trim('  hi  ')") == "hi"
        assert engine.evaluate("len('hello')") == 5
        assert engine.evaluate("contains('hello', 'ell')") is True
        assert engine.evaluate("starts_with('hello', 'hel')") is True
        assert engine.evaluate("ends_with('hello', 'llo')") is True

    def test_aggregate_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("sum([1, 2, 3])") == 6
        assert engine.evaluate("avg([10, 20, 30])") == 20.0
        assert engine.evaluate("count([1, None, 3])") == 2

    def test_conditional_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("coalesce(None, None, 42)") == 42
        assert engine.evaluate("if_expr(True, 1, 0)") == 1
        assert engine.evaluate("if_expr(False, 1, 0)") == 0

    def test_math_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("ceil(3.1)") == 4
        assert engine.evaluate("floor(3.9)") == 3
        assert engine.evaluate("sqrt(100)") == 10.0

    def test_date_functions(self):
        engine = ExpressionEngine()
        assert isinstance(engine.evaluate("today()"), str)
        assert isinstance(engine.evaluate("now()"), str)
        assert engine.evaluate("year('2026-04-19')") == 2026
        assert engine.evaluate("month('2026-04-19')") == 4
        assert engine.evaluate("day('2026-04-19')") == 19

    def test_function_count(self):
        engine = ExpressionEngine()
        assert len(engine.SAFE_FUNCTIONS) >= 40
