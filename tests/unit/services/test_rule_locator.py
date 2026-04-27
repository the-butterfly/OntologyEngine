# tests/unit/services/test_rule_locator.py
"""Tests for RuleLocator service."""

import pytest
from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage


@pytest.fixture
def storage():
    return SemanticSpaceStorage()


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