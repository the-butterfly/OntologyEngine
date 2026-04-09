# tests/unit/engine/rule/operators/test_operators.py
"""Tests for rule operators."""

import pytest
from ontology_engine.engine.rule.operators import OperatorRegistry


class TestOperatorRegistry:
    """Test OperatorRegistry."""

    def test_register_and_get(self):
        """Test basic operator registration and retrieval."""
        # Operators should already be registered via import
        op = OperatorRegistry.get("set_flag")
        assert op is not None
        assert op.name == "set_flag"

    def test_get_unknown_operator(self):
        """Test error on unknown operator."""
        with pytest.raises(KeyError) as exc_info:
            OperatorRegistry.get("unknown_operator")
        assert "unknown_operator" in str(exc_info.value)

    def test_available_operators(self):
        """Test getting list of available operators."""
        operators = OperatorRegistry.available()
        assert "set_flag" in operators
        assert "approve_eligibility" in operators
        assert "reject_eligibility" in operators
        assert "compute_formula" in operators
        assert "trigger_alert" in operators
        assert "switch" in operators


class TestSetFlagOperator:
    """Test SetFlagOperator."""

    @pytest.mark.asyncio
    async def test_set_flag_default(self):
        """Test set_flag with defaults."""
        op = OperatorRegistry.get("set_flag")
        result = await op.execute({}, {}, {})
        assert result["flag"] is True
        assert result["flag_set"] is True

    @pytest.mark.asyncio
    async def test_set_flag_custom(self):
        """Test set_flag with custom values."""
        op = OperatorRegistry.get("set_flag")
        result = await op.execute(
            {"flag_name": "approved", "flag_value": False},
            {},
            {}
        )
        assert result["approved"] is False
        assert result["approved_set"] is True


class TestApproveEligibilityOperator:
    """Test approve_eligibility operator."""

    @pytest.mark.asyncio
    async def test_approve_eligibility(self):
        """Test approval sets eligible=True."""
        op = OperatorRegistry.get("approve_eligibility")
        result = await op.execute({}, {}, {})
        assert result["eligible"] is True


class TestRejectEligibilityOperator:
    """Test reject_eligibility operator."""

    @pytest.mark.asyncio
    async def test_reject_eligibility(self):
        """Test rejection sets eligible=False."""
        op = OperatorRegistry.get("reject_eligibility")
        result = await op.execute({}, {}, {})
        assert result["eligible"] is False
        assert "rejection_reason" in result

    @pytest.mark.asyncio
    async def test_reject_with_custom_reason(self):
        """Test rejection with custom reason."""
        op = OperatorRegistry.get("reject_eligibility")
        result = await op.execute(
            {"rejection_reason": "Insufficient credit history"},
            {},
            {}
        )
        assert result["rejection_reason"] == "Insufficient credit history"


class TestComputeFormulaOperator:
    """Test compute_formula operator."""

    @pytest.mark.asyncio
    async def test_compute_formula(self):
        """Test simple formula computation."""
        op = OperatorRegistry.get("compute_formula")
        context = {"a": 10, "b": 5}
        result = await op.execute(
            {"formula": "a + b", "output_key": "result"},
            {},
            context
        )
        assert result["result"] == 15

    @pytest.mark.asyncio
    async def test_compute_formula_with_division(self):
        """Test formula with division."""
        op = OperatorRegistry.get("compute_formula")
        context = {"overdue_amount": 100, "total_amount": 1000}
        result = await op.execute(
            {"formula": "overdue_amount / total_amount * 100", "output_key": "ratio"},
            {},
            context
        )
        assert result["ratio"] == 10.0

    @pytest.mark.asyncio
    async def test_compute_formula_missing_formula(self):
        """Test error on missing formula."""
        op = OperatorRegistry.get("compute_formula")
        result = await op.execute({}, {}, {})
        assert "error" in result


class TestSwitchOperator:
    """Test switch operator."""

    @pytest.mark.asyncio
    async def test_switch_match(self):
        """Test switch matches correct case."""
        op = OperatorRegistry.get("switch")
        context = {"score": 95}
        result = await op.execute(
            {
                "value": "score",
                "cases": [
                    {"condition": ">= 90", "result": "AAA"},
                    {"condition": ">= 80", "result": "AA"},
                ],
                "default": "A"
            },
            {},
            context
        )
        assert result["switch_result"] == "AAA"
        assert result["matched_case"] == ">= 90"

    @pytest.mark.asyncio
    async def test_switch_default(self):
        """Test switch falls through to default."""
        op = OperatorRegistry.get("switch")
        context = {"score": 30}
        result = await op.execute(
            {
                "value": "score",
                "cases": [
                    {"condition": ">= 90", "result": "AAA"},
                    {"condition": ">= 80", "result": "AA"},
                ],
                "default": "B"
            },
            {},
            context
        )
        assert result["switch_result"] == "B"
        assert result["matched_case"] == "default"


class TestBinningOperator:
    """Test binning operator."""

    @pytest.mark.asyncio
    async def test_binning_low(self):
        """Test binning into LOW bin."""
        op = OperatorRegistry.get("binning")
        context = {"ratio": 3}
        result = await op.execute(
            {
                "value": "ratio",
                "bins": [
                    {"min": 0, "max": 5, "label": "LOW"},
                    {"min": 5, "max": 10, "label": "MED"},
                ],
                "default": "HIGH"
            },
            {},
            context
        )
        assert result["bin"] == "LOW"

    @pytest.mark.asyncio
    async def test_binning_high(self):
        """Test binning falls through to default."""
        op = OperatorRegistry.get("binning")
        context = {"ratio": 15}
        result = await op.execute(
            {
                "value": "ratio",
                "bins": [
                    {"min": 0, "max": 5, "label": "LOW"},
                    {"min": 5, "max": 10, "label": "MED"},
                ],
                "default": "HIGH"
            },
            {},
            context
        )
        assert result["bin"] == "HIGH"


class TestTriggerAlertOperator:
    """Test trigger_alert operator."""

    @pytest.mark.asyncio
    async def test_trigger_alert(self):
        """Test alert triggering."""
        op = OperatorRegistry.get("trigger_alert")
        result = await op.execute(
            {
                "alert_level": "warning",
                "alert_type": "credit_risk",
                "message": "High risk detected"
            },
            {},
            {}
        )
        assert result["alert_triggered"] is True
        assert result["level"] == "warning"
        assert result["type"] == "credit_risk"
        assert result["message"] == "High risk detected"


class TestGraphTraversalOperator:
    """Test graph_traversal operator."""

    @pytest.mark.asyncio
    async def test_graph_traversal(self):
        """Test graph traversal returns placeholder."""
        op = OperatorRegistry.get("graph_traversal")
        context = {"entity_id": "SUP_001"}
        result = await op.execute(
            {
                "relation_type": "guarantees_for",
                "direction": "outgoing",
                "aggregation": "count"
            },
            {},
            context
        )
        assert result["relation_type"] == "guarantees_for"
        assert result["aggregation"] == "count"
        assert "note" in result
