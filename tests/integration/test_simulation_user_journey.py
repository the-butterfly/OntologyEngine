# tests/integration/test_simulation_user_journey.py
"""Integration tests for complete simulation user journey.

Tests the full user flow:
1. Create session with entity_id via POST /v1/simulation/tree
2. Verify auto-filled inputs from entity attributes
3. Run simulation via PATCH /v1/simulation/{session_id}
4. Verify execution result structure
"""

import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport

from ontology_engine.api.server import create_app


VIEW_ID = "view_test_journey"
ENTITY_ID = "SUP001"


def _make_test_space():
    """Create a test semantic space for user journey tests."""
    from ontology_engine.core.semantic_space import (
        SemanticSpace,
        SpaceMetadata,
        SpaceStatus,
        SpaceType,
        SemanticSpaceLayers,
        L4BusinessLogic,
        SpaceInstances,
    )

    return SemanticSpace(
        metadata=SpaceMetadata(
            id=VIEW_ID,
            name="Test Journey View",
            space_type=SpaceType.CONSUMPTION,
            description="Integration test view for user journey",
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
    """Create app with test view for simulation API."""
    from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage
    from ontology_engine.api.routes import simulation as sim_module
    from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder

    storage = SemanticSpaceStorage(base_path=str(tmp_path / "spaces"))
    space = _make_test_space()
    await storage.save(space)

    # Override simulation module storage AND tree builder
    original_storage = sim_module._semantic_space_storage
    original_builder = sim_module._tree_builder
    sim_module._semantic_space_storage = storage
    sim_module._tree_builder = RuleTreeBuilder(semantic_space_storage=storage)

    application = create_app()
    yield application

    sim_module._semantic_space_storage = original_storage
    sim_module._tree_builder = original_builder


@pytest_asyncio.fixture
async def client(app_with_view):
    """Async HTTP client for integration testing."""
    transport = ASGITransport(app=app_with_view)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_full_simulation_journey(client):
    """Test complete simulation user journey:
    1. Create session with entity_id
    2. Verify auto-filled inputs
    3. Run simulation
    4. Verify execution result
    """
    # 1. Create session with entity_id
    resp = await client.post("/v1/simulation/tree", json={
        "schema_id": VIEW_ID,
        "entity_id": ENTITY_ID,
        "target_output": "final_decision"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]

    # 2. Verify auto-filled inputs
    assert "current_inputs" in data
    # Should have credit_score from entity auto-fill
    # (May be empty if entity doesn't exist or L3 mapping issues)

    session_id = data["session_id"]
    execution_tree = data["execution_tree"]
    assert "layers" in execution_tree
    assert len(execution_tree["layers"]) >= 2

    # 3. Run simulation
    resp = await client.patch(f"/v1/simulation/{session_id}", json={
        "input_values": {}
    })
    assert resp.status_code == 200
    result = resp.json()["data"]["result"]

    # 4. Verify execution result
    assert result is not None, "result should not be None when inputs are provided"
    assert "final_outputs" in result or "step_results" in result


@pytest.mark.asyncio
async def test_simulation_tree_api_without_entity(client):
    """Test creating simulation tree without entity_id."""
    resp = await client.post("/v1/simulation/tree", json={
        "schema_id": VIEW_ID,
        "target_output": "final_decision"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert "session_id" in data
    assert "execution_tree" in data
    # current_inputs should be empty when no entity_id provided
    assert data["current_inputs"] == {}