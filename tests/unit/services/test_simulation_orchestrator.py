# tests/unit/services/test_simulation_orchestrator.py
"""Tests for SimulationOrchestrator service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.services.simulation_orchestrator import SimulationOrchestrator
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage


def _make_mock_storage():
    """Create a SemanticSpaceStorage with mocked load method."""
    storage = SemanticSpaceStorage()

    async def mock_load(space_id):
        if space_id == "space_supply_chain_finance":
            space = MagicMock()
            rule_defs = [
                {"id": "RD001", "name": "Registered Capital", "inputs": [], "outputs": [{"id": "registered_capital"}]},
                {"id": "RD002", "name": "Credit Score", "inputs": [{"id": "registered_capital"}], "outputs": [{"id": "credit_score"}]},
                {"id": "RD003", "name": "Risk Assessment", "inputs": [{"id": "credit_score"}], "outputs": [{"id": "risk_flag"}]},
                {"id": "RD006_final_decision", "name": "Final Decision", "inputs": [{"id": "credit_score"}, {"id": "risk_flag"}], "outputs": [{"id": "final_decision"}]},
            ]
            space.layers.L4_business_logic.rule_definitions = rule_defs
            return space
        return None

    storage.load = mock_load
    return storage


@pytest.fixture
def orchestrator():
    return SimulationOrchestrator(semantic_space_storage=_make_mock_storage())


@pytest.mark.asyncio
async def test_build_execution_tree():
    orchestrator = SimulationOrchestrator(semantic_space_storage=_make_mock_storage())
    tree = await orchestrator.build_execution_tree(
        "space_supply_chain_finance",
        "final_decision"
    )
    assert len(tree["layers"]) >= 3
    assert tree["total_steps"] >= 4


@pytest.mark.asyncio
async def test_locate_rules_producing():
    orchestrator = SimulationOrchestrator(semantic_space_storage=_make_mock_storage())
    results = await orchestrator.locate_rules_producing("final_decision", "space_supply_chain_finance")
    assert len(results) == 1
    assert results[0]["id"] == "RD006_final_decision"


@pytest.mark.asyncio
async def test_analyze_dependencies():
    orchestrator = SimulationOrchestrator()
    rules = [
        {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
        {"id": "B", "inputs": [{"id": "x"}], "outputs": [{"id": "y"}]},
    ]
    result = await orchestrator.analyze_dependencies(rules)
    assert "graph" in result
    assert "levels" in result
    assert result["levels"]["A"] == 0
    assert result["levels"]["B"] == 1
