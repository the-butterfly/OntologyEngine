# tests/unit/services/test_simulation_orchestrator.py
"""Tests for SimulationOrchestrator service."""

import pytest
from ontology_engine.services.simulation_orchestrator import SimulationOrchestrator


@pytest.fixture
def orchestrator():
    return SimulationOrchestrator()


@pytest.mark.asyncio
async def test_build_execution_tree():
    orchestrator = SimulationOrchestrator()
    tree = await orchestrator.build_execution_tree(
        "space_supply_chain_finance",
        "final_decision"
    )
    assert len(tree["layers"]) >= 3
    assert tree["total_steps"] >= 4


@pytest.mark.asyncio
async def test_locate_rules_producing():
    orchestrator = SimulationOrchestrator()
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