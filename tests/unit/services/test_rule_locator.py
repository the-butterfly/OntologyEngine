# tests/unit/services/test_rule_locator.py
"""Tests for RuleLocator service."""

import pytest
from unittest.mock import MagicMock

from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage


def _make_mock_storage():
    """Create a SemanticSpaceStorage with mocked load method."""
    storage = SemanticSpaceStorage()

    async def mock_load(space_id):
        if space_id == "space_supply_chain_finance":
            space = MagicMock()
            rule_defs = [
                {
                    "id": "RD006_final_decision",
                    "name": "综合授信决策",
                    "inputs": [{"id": "credit_score", "type": "metric"}],
                    "outputs": [{"id": "final_decision", "type": "flag"}],
                },
                {
                    "id": "RD003_risk_assessment",
                    "name": "风险评估",
                    "inputs": [{"id": "credit_score", "type": "metric"}],
                    "outputs": [{"id": "risk_flag", "type": "flag"}],
                },
            ]
            space.layers.L4_business_logic.rule_definitions = rule_defs
            return space
        return None

    storage.load = mock_load
    return storage


@pytest.fixture
def storage():
    return _make_mock_storage()


@pytest.fixture
def locator(storage):
    return RuleLocator(storage)


@pytest.mark.asyncio
async def test_locate_by_output_exact_match(locator):
    results = await locator.locate_by_output("final_decision", "space_supply_chain_finance")
    assert len(results) == 1
    assert results[0]["id"] == "RD006_final_decision"


@pytest.mark.asyncio
async def test_locate_by_output_not_found(locator):
    results = await locator.locate_by_output("nonexistent_output", "space_supply_chain_finance")
    assert results == []


@pytest.mark.asyncio
async def test_locate_by_input(locator):
    results = await locator.locate_by_input("credit_score", "space_supply_chain_finance")
    assert len(results) >= 1
    assert any(r["id"] == "RD006_final_decision" for r in results)
