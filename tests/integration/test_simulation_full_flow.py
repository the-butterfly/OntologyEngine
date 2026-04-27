# tests/integration/test_simulation_full_flow.py
"""Integration tests for simulation full flow.

Tests:
1. Execution tree building via simulation/tree API
2. Consumption API with DependencyAnalyzer
3. Shared service usage (SimulationOrchestrator, RuleLocator)

Note: Some tests use space_supply_chain_finance which is pre-loaded in data/semantic_spaces/.
The consumption API tests use a temporary storage with a test view.
"""

import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport

from ontology_engine.api.server import create_app
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SpaceType,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    SemanticSpaceStorage,
)
from ontology_engine.services.simulation_orchestrator import SimulationOrchestrator
from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.api.routes import consumption as consumption_module


VIEW_ID = "view_test_simulation_flow"
ENTITY_ID = "SUP_SIM_FLOW_001"


def _make_test_space() -> SemanticSpace:
    """Create a test semantic space for simulation flow tests."""
    return SemanticSpace(
        metadata=SpaceMetadata(
            id=VIEW_ID,
            name="Test Simulation Flow View",
            space_type=SpaceType.CONSUMPTION,
            description="Integration test view for simulation flow",
            domain="test",
            status=SpaceStatus.ACTIVE,
        ),
        layers=SemanticSpaceLayers(
            L1_fact_objects=[
                {"id": "Supplier", "name": "Supplier", "description": "A supplier entity", "properties": [], "relations": []},
            ],
            L2_categorizations=[
                {"id": "risk_level", "name": "risk_level", "description": "Risk level categorization", "applicable_to": ["Supplier"]},
            ],
            L3_analytical_elements=[
                {"id": "credit_score", "name": "credit_score", "type": "atomic", "source": {"attribute": "credit_score"}, "dependencies": [], "overridable": True},
                {"id": "transaction_count", "name": "transaction_count", "type": "atomic", "source": {"attribute": "transaction_count"}, "dependencies": [], "overridable": True},
            ],
            L4_business_logic=L4BusinessLogic(
                rule_definitions=[
                    {
                        "id": "R001",
                        "name": "Credit Score Compute",
                        "rule_type": "inference",
                        "priority": 100,
                        "enabled": True,
                        "target_objects": ["Supplier"],
                        "inputs": [],
                        "outputs": [{"id": "credit_score", "type": "metric"}],
                        "logic_ids": ["L001"],
                    },
                    {
                        "id": "R002",
                        "name": "Risk Assessment",
                        "rule_type": "constraint",
                        "priority": 90,
                        "enabled": True,
                        "target_objects": ["Supplier"],
                        "inputs": [{"id": "credit_score", "type": "metric"}],
                        "outputs": [{"id": "risk_level_flag", "type": "flag"}],
                        "logic_ids": ["L002"],
                    },
                    {
                        "id": "R003",
                        "name": "Final Decision",
                        "rule_type": "decision",
                        "priority": 50,
                        "enabled": True,
                        "target_objects": ["Supplier"],
                        "inputs": [{"id": "credit_score", "type": "metric"}, {"id": "risk_level_flag", "type": "flag"}],
                        "outputs": [{"id": "final_decision", "type": "flag"}],
                        "logic_ids": ["L003"],
                    },
                ],
                rule_logics=[
                    {
                        "id": "L001",
                        "name": "Credit Score Logic",
                        "applicable_conditions": [],
                        "when": {"expression": "transaction_count > 0"},
                        "then_action": {"action_type": "compute", "output": {"credit_score": 750}},
                    },
                    {
                        "id": "L002",
                        "name": "Risk Assessment Logic",
                        "applicable_conditions": [],
                        "when": {"expression": "credit_score >= 700"},
                        "then_action": {"action_type": "set_flag", "output": {"risk_level_flag": "low_risk"}},
                        "else_action": {"action_type": "set_flag", "output": {"risk_level_flag": "high_risk"}},
                    },
                    {
                        "id": "L003",
                        "name": "Final Decision Logic",
                        "applicable_conditions": [],
                        "when": {"expression": "risk_level_flag == 'low_risk'"},
                        "then_action": {"action_type": "approve", "output": {"final_decision": "approved"}},
                        "else_action": {"action_type": "reject", "output": {"final_decision": "rejected"}},
                    },
                ],
            ),
        ),
        instances=SpaceInstances(
            entities=[
                {
                    "entity_id": ENTITY_ID,
                    "_fact_object": "Supplier",
                    "name": "Test Supplier",
                    "credit_score": 750,
                    "transaction_count": 10,
                },
            ],
            relations=[],
            category_tags=[],
            metric_values=[],
        ),
        versions=[],
    )


@pytest_asyncio.fixture
async def app_with_view(tmp_path):
    """Create app with test view for consumption API."""
    storage = SemanticSpaceStorage(base_path=str(tmp_path / "spaces"))
    space = _make_test_space()
    await storage.save(space)

    # Override consumption module storage
    original_get_storage = consumption_module._get_storage
    consumption_module._get_storage = lambda: storage

    application = create_app()
    yield application

    consumption_module._get_storage = original_get_storage


@pytest_asyncio.fixture
async def client(app_with_view):
    """Async HTTP client for integration testing."""
    transport = ASGITransport(app=app_with_view)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestConsumptionAPIWithDependencyAnalyzer:
    """Tests for consumption API execute/simulate with DependencyAnalyzer.

    These tests use a temporary storage with a test view and properly override
    the consumption module storage, so they pass.
    """

    @pytest.mark.asyncio
    async def test_execute_analyze_with_steps_decision_final_outputs(self, client):
        """Test execute/analyze returns steps, decision, final_outputs structure."""
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/analyze",
            json={"entity_id": ENTITY_ID, "dimension": "credit_assessment", "include_trace": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        # Verify response structure
        assert "steps" in data, "Response should contain 'steps'"
        assert "decision" in data, "Response should contain 'decision'"
        assert "final_outputs" in data, "Response should contain 'final_outputs'"
        assert len(data["steps"]) >= 3, f"Expected 3+ steps, got {len(data['steps'])}"

    @pytest.mark.asyncio
    async def test_execute_simulate_response_structure(self, client):
        """Test execute/simulate returns proper response structure."""
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/simulate",
            json={
                "entity_id": ENTITY_ID,
                "dimension": "credit_assessment",
                "overrides": {"credit_score": 800},
                "include_trace": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        # Verify response structure for simulation
        assert "steps" in data, "Simulation response should contain 'steps'"
        # Note: simulate response may not have top-level 'decision' and 'final_outputs'
        # but has nested structure with baseline_outputs, simulated_outputs, comparison
        assert "baseline_outputs" in data
        assert "simulated_outputs" in data
        assert "comparison" in data


class TestSharedServiceUsage:
    """Tests for shared service coordination (SimulationOrchestrator, RuleLocator).

    These tests use the actual SemanticSpaceStorage() which loads from data/semantic_spaces/.
    The space_supply_chain_finance.json exists there with RD006_final_decision rule.
    """

    @pytest.mark.asyncio
    async def test_simulation_orchestrator_build_execution_tree_with_real_space(self):
        """Test SimulationOrchestrator coordinates build_execution_tree correctly.

        Uses space_supply_chain_finance which exists in data/semantic_spaces/.
        """
        orchestrator = SimulationOrchestrator()
        tree = await orchestrator.build_execution_tree(
            "space_supply_chain_finance",
            "final_decision"
        )

        assert "layers" in tree
        assert "total_steps" in tree
        # The actual space_supply_chain_finance has multiple layers when building tree for final_decision
        assert len(tree["layers"]) >= 3, f"Expected 3+ layers, got {len(tree['layers'])}"
        assert tree["total_steps"] >= 4, f"Expected 4+ total_steps, got {tree['total_steps']}"

    @pytest.mark.asyncio
    async def test_rule_locator_by_output_with_real_space(self):
        """Test RuleLocator finds rules by output name.

        Uses space_supply_chain_finance which exists in data/semantic_spaces/.
        final_decision is produced by RD006_final_decision.
        """
        storage = SemanticSpaceStorage()
        locator = RuleLocator(storage)

        # final_decision is produced by RD006_final_decision
        results = await locator.locate_by_output("final_decision", "space_supply_chain_finance")
        assert len(results) >= 1, f"Expected at least 1 rule producing final_decision, got {len(results)}"
        assert any("RD006" in r["id"] for r in results), f"Expected RD006 in results, got {[r['id'] for r in results]}"

        # credit_score is produced by RD002_credit_score_compute
        results = await locator.locate_by_output("credit_score", "space_supply_chain_finance")
        assert len(results) >= 1, f"Expected at least 1 rule producing credit_score, got {len(results)}"

    @pytest.mark.asyncio
    async def test_simulation_orchestrator_locate_rules_producing_with_real_space(self):
        """Test SimulationOrchestrator can locate rules producing specific output.

        Uses space_supply_chain_finance which exists in data/semantic_spaces/.
        """
        orchestrator = SimulationOrchestrator()

        results = await orchestrator.locate_rules_producing("final_decision", "space_supply_chain_finance")
        assert len(results) >= 1, f"Expected at least 1 rule, got {len(results)}"
        assert any("RD006" in r["id"] for r in results), f"Expected RD006 in results, got {[r['id'] for r in results]}"

    @pytest.mark.asyncio
    async def test_dependency_analysis(self):
        """Test analyzing rule dependencies builds correct levels."""
        orchestrator = SimulationOrchestrator()

        rules = [
            {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
            {"id": "B", "inputs": [{"id": "x"}], "outputs": [{"id": "y"}]},
            {"id": "C", "inputs": [{"id": "y"}], "outputs": [{"id": "z"}]},
        ]

        result = await orchestrator.analyze_dependencies(rules)

        assert "graph" in result
        assert "levels" in result
        assert result["levels"]["A"] == 0
        assert result["levels"]["B"] == 1
        assert result["levels"]["C"] == 2

    @pytest.mark.asyncio
    async def test_execution_tree_layer_contains_zhonghe_credit_decision(self):
        """Test that execution tree layer 0 contains '综合授信决策' (comprehensive credit decision).

        Uses space_supply_chain_finance which exists in data/semantic_spaces/.
        RD006_final_decision is named '综合授信决策'.
        """
        orchestrator = SimulationOrchestrator()
        tree = await orchestrator.build_execution_tree(
            "space_supply_chain_finance",
            "final_decision"
        )

        # Verify layer 0 contains the comprehensive credit decision rule group
        assert len(tree["layers"]) >= 3, f"Expected 3+ layers, got {len(tree['layers'])}"
        layer_0_rule_groups = tree["layers"][0]["rule_groups"]
        assert any("综合授信决策" in rg or "综合" in rg for rg in layer_0_rule_groups), \
            f"Expected '综合授信决策' or '综合' in layer 0 rule groups, got {layer_0_rule_groups}"


class TestSimulationAutoFill:
    """Tests for simulation API auto-fill functionality.

    Verifies that when entity_id is provided, the API auto-fills current_inputs
    from the entity's attributes based on L3 analytical element source mappings.
    """

    @pytest.mark.asyncio
    async def test_simulation_tree_api_auto_fills_entity_attributes(self, tmp_path):
        """Test POST /v1/simulation/tree auto-fills current_inputs from entity.

        When entity_id is provided, the API should:
        1. Load the space
        2. Find the entity
        3. Extract L3 element values via source.attribute mapping
        4. Pre-fill current_inputs in the response
        """
        from ontology_engine.api.routes import simulation as sim_module
        from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder

        # Create test space with entities that have matching attributes
        storage = SemanticSpaceStorage(base_path=str(tmp_path / "spaces"))
        test_space = _make_test_space()
        await storage.save(test_space)

        # Override simulation module storage AND tree builder
        # (tree builder holds reference to original storage)
        original_storage = sim_module._semantic_space_storage
        original_builder = sim_module._tree_builder
        sim_module._semantic_space_storage = storage
        sim_module._tree_builder = RuleTreeBuilder(semantic_space_storage=storage)

        try:
            # Create app and client
            application = create_app()
            transport = ASGITransport(app=application)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Call with entity_id = SUP_SIM_FLOW_001
                resp = await client.post(
                    "/v1/simulation/tree",
                    json={
                        "schema_id": VIEW_ID,
                        "entity_id": ENTITY_ID,
                        "target_output": "final_decision",
                    },
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["success"] is True

                data = body["data"]
                assert "session_id" in data
                assert "execution_tree" in data

                # Verify current_inputs is auto-filled
                # The test space has L3 elements: credit_score and transaction_count
                # with source.attribute pointing to entity fields
                # credit_score is required for final_decision, transaction_count is not
                current_inputs = data.get("current_inputs", {})
                assert "credit_score" in current_inputs, f"Expected credit_score in current_inputs, got {current_inputs}"
                assert current_inputs["credit_score"] == 750, f"Expected credit_score=750, got {current_inputs['credit_score']}"
                # transaction_count is NOT auto-filled because it's not in input_requirements
                # Only inputs listed in input_requirements should be auto-filled
                assert "transaction_count" not in current_inputs, \
                    f"transaction_count should NOT be auto-filled, got {current_inputs}"
        finally:
            sim_module._semantic_space_storage = original_storage
            sim_module._tree_builder = original_builder

    @pytest.mark.asyncio
    async def test_simulation_tree_api_without_entity_id_returns_empty_inputs(self, tmp_path):
        """Test POST /v1/simulation/tree without entity_id returns empty current_inputs."""
        from ontology_engine.api.routes import simulation as sim_module

        storage = SemanticSpaceStorage(base_path=str(tmp_path / "spaces"))
        test_space = _make_test_space()
        await storage.save(test_space)

        original_storage = sim_module._semantic_space_storage
        sim_module._semantic_space_storage = storage

        try:
            application = create_app()
            transport = ASGITransport(app=application)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Call without entity_id
                resp = await client.post(
                    "/v1/simulation/tree",
                    json={
                        "schema_id": VIEW_ID,
                        "target_output": "final_decision",
                    },
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["success"] is True

                data = body["data"]
                current_inputs = data.get("current_inputs", {})
                # Without entity_id, no auto-fill should happen
                assert current_inputs == {}, f"Expected empty current_inputs, got {current_inputs}"
        finally:
            sim_module._semantic_space_storage = original_storage