"""Tests for ExpressionEvaluator."""

from __future__ import annotations

import pytest

from ontology_engine.core.schema.models import RuleWhen
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator


class TestExpressionEvaluator:
    """Verify expression evaluation semantics for rules and formulas."""

    @pytest.fixture
    def evaluator(self) -> ExpressionEvaluator:
        return ExpressionEvaluator()

    def test_evaluate_simple_condition(self, evaluator: ExpressionEvaluator) -> None:
        context = {"status": "ACTIVE", "amount": 120}
        assert evaluator.evaluate("status == 'ACTIVE' AND amount >= 100", context) is True

    def test_evaluate_all_of(self, evaluator: ExpressionEvaluator) -> None:
        context = {"status": "ACTIVE", "eligible": True}
        condition = {"allOf": [{"expression": "status == 'ACTIVE'"}, {"expression": "eligible == true"}]}
        assert evaluator.evaluate(condition, context) is True

    def test_evaluate_any_of(self, evaluator: ExpressionEvaluator) -> None:
        context = {"status": "SUSPENDED", "risk_level": "LOW"}
        condition = RuleWhen(anyOf=[{"expression": "status == 'ACTIVE'"}, {"expression": "risk_level == 'LOW'"}])
        assert evaluator.evaluate(condition, context) is True

    def test_evaluate_is_null(self, evaluator: ExpressionEvaluator) -> None:
        context = {"due_date": None}
        assert evaluator.evaluate("due_date IS NULL", context) is True
        assert evaluator.evaluate("due_date IS NOT NULL", context) is False

    def test_evaluate_nested_path(self, evaluator: ExpressionEvaluator) -> None:
        context = {"supplier": {"status": "ACTIVE", "registered_capital": {"value": 500}}}
        assert evaluator.evaluate("supplier.status == 'ACTIVE'", context) is True
        assert evaluator.evaluate("supplier.registered_capital.value >= 500", context) is True

    def test_evaluate_missing_field_is_none(self, evaluator: ExpressionEvaluator) -> None:
        context = {"status": "ACTIVE"}
        assert evaluator.evaluate("missing_field IS NULL", context) is True
        assert evaluator.evaluate("missing_field == 1", context) is False

    def test_evaluate_today_and_days_between(self, evaluator: ExpressionEvaluator) -> None:
        context = {"issue_date": "2026-04-01"}
        assert evaluator.evaluate("days_between(issue_date, '2026-04-11') == 10", context) is True

    def test_formula_result_not_forced_to_bool(self, evaluator: ExpressionEvaluator) -> None:
        context = {"invoice_amount": 100, "contract_amount": 4}
        assert evaluator.evaluate("invoice_amount / contract_amount", context) == 25
