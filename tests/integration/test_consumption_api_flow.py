# tests/integration/test_consumption_api_flow.py
"""Consumption API integration tests.

Covers:
- GET  /v1/views
- GET  /v1/views/{view_id}
- GET  /v1/views/{view_id}/entities
- GET  /v1/views/{view_id}/schema-graph
- GET  /v1/views/{view_id}/rules/dependency-graph
- POST /v1/views/{view_id}/execute/analyze
- POST /v1/views/{view_id}/execute/simulate
- GET  /v1/views/{view_id}/rules/for-entity/{entity_id}
- GET  /v1/views/{view_id}/metrics/{entity_id}/snapshot
- Error paths: nonexistent view, nonexistent entity
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
from ontology_engine.api.routes import consumption as consumption_module


VIEW_ID = "view_test_consumption"
ENTITY_ID = "SUP_TEST_001"


def _make_test_space() -> SemanticSpace:
    return SemanticSpace(
        metadata=SpaceMetadata(
            id=VIEW_ID,
            name="Test Consumption View",
            space_type=SpaceType.CONSUMPTION,
            description="Integration test view",
            domain="test",
            status=SpaceStatus.ACTIVE,
        ),
        layers=SemanticSpaceLayers(
            L1_fact_objects=[
                {"id": "Supplier", "name": "Supplier", "description": "A supplier entity", "properties": [], "relations": []},
                {"id": "Invoice", "name": "Invoice", "description": "An invoice entity", "properties": [], "relations": []},
            ],
            L2_categorizations=[
                {"id": "risk_level", "name": "risk_level", "description": "Risk level categorization", "applicable_to": ["Supplier"]},
            ],
            L3_analytical_elements=[
                {"id": "total_invoice_amount", "name": "total_invoice_amount", "type": "atomic", "source": {"attribute": "total_invoice_amount"}, "dependencies": [], "overridable": True},
                {"id": "overdue_amount", "name": "overdue_amount", "type": "atomic", "source": {"attribute": "overdue_amount"}, "dependencies": [], "overridable": True},
            ],
            L4_business_logic=L4BusinessLogic(
                rule_definitions=[
                    {
                        "id": "R001",
                        "name": "Basic Eligibility",
                        "rule_type": "constraint",
                        "priority": 100,
                        "enabled": True,
                        "target_objects": ["Supplier"],
                        "inputs": [{"name": "total_invoice_amount", "type": "metric"}],
                        "outputs": [{"name": "eligible", "type": "flag"}],
                        "logic_ids": ["L001"],
                    },
                    {
                        "id": "R002",
                        "name": "Overdue Check",
                        "rule_type": "constraint",
                        "priority": 90,
                        "enabled": True,
                        "target_objects": ["Supplier"],
                        "inputs": [{"name": "overdue_amount", "type": "metric"}],
                        "outputs": [{"name": "decision", "type": "flag"}],
                        "logic_ids": ["L002"],
                    },
                ],
                rule_logics=[
                    {
                        "id": "L001",
                        "name": "Eligibility Logic",
                        "applicable_conditions": [],
                        "when": {"expression": "total_invoice_amount > 0"},
                        "then_action": {"action_type": "set_flag", "output": {"eligible": True}},
                    },
                    {
                        "id": "L002",
                        "name": "Overdue Logic",
                        "applicable_conditions": [],
                        "when": {"expression": "overdue_amount > 50000"},
                        "then_action": {"action_type": "reject", "output": {}},
                        "else_action": {"action_type": "approve", "output": {}},
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
                    "total_invoice_amount": 100000,
                    "overdue_amount": 30000,
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
    storage = SemanticSpaceStorage(base_path=str(tmp_path / "spaces"))
    space = _make_test_space()
    await storage.save(space)

    original_get_storage = consumption_module._get_storage
    consumption_module._get_storage = lambda: storage

    application = create_app()
    yield application

    consumption_module._get_storage = original_get_storage


@pytest_asyncio.fixture
async def client(app_with_view):
    transport = ASGITransport(app=app_with_view)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestListView:
    @pytest.mark.asyncio
    async def test_list_views(self, client):
        resp = await client.get("/v1/views")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        views = body["data"]
        assert isinstance(views, list)
        view_ids = [v["id"] for v in views]
        assert VIEW_ID in view_ids


class TestGetView:
    @pytest.mark.asyncio
    async def test_get_view_detail(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["id"] == VIEW_ID
        assert data["name"] == "Test Consumption View"
        assert data["entity_count"] == 1
        assert data["rule_definition_count"] == 2

    @pytest.mark.asyncio
    async def test_get_nonexistent_view(self, client):
        resp = await client.get("/v1/views/view_nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "NOT_FOUND" in body["error"]["code"]


class TestViewEntities:
    @pytest.mark.asyncio
    async def test_list_entities(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/entities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        entities = body["data"]
        assert len(entities) == 1
        assert entities[0]["entity_id"] == ENTITY_ID
        assert entities[0]["_fact_object"] == "Supplier"

    @pytest.mark.asyncio
    async def test_list_entities_filtered_by_concept(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/entities", params={"concept": "Supplier"})
        assert resp.status_code == 200
        entities = resp.json()["data"]
        assert len(entities) == 1

        resp2 = await client.get(f"/v1/views/{VIEW_ID}/entities", params={"concept": "Invoice"})
        assert resp2.status_code == 200
        entities2 = resp2.json()["data"]
        assert len(entities2) == 0


class TestSchemaGraph:
    @pytest.mark.asyncio
    async def test_schema_graph(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/schema-graph")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data
        node_types = {n["type"] for n in data["nodes"]}
        assert "entity" in node_types
        assert "rule" in node_types
        assert "metric" in node_types

    @pytest.mark.asyncio
    async def test_schema_graph_layer_filter(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/schema-graph", params={"layer_filter": "L1,L4"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        node_types = {n["type"] for n in data["nodes"]}
        assert "entity" in node_types
        assert "rule" in node_types
        assert "metric" not in node_types


class TestRuleDependencyGraph:
    @pytest.mark.asyncio
    async def test_dependency_graph(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/rules/dependency-graph")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert "nodes" in data
        assert "edges" in data
        assert "execution_order" in data
        assert "mutual_exclusions" in data
        assert "stats" in data
        assert data["stats"]["total_rules"] == 2
        assert len(data["nodes"]) == 2
        assert len(data["execution_order"]) == 2

    @pytest.mark.asyncio
    async def test_dependency_graph_nonexistent_view(self, client):
        resp = await client.get("/v1/views/view_nonexistent/rules/dependency-graph")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False


class TestExecuteAnalyze:
    @pytest.mark.asyncio
    async def test_execute_analyze(self, client):
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/analyze",
            json={"entity_id": ENTITY_ID, "dimension": "credit_assessment", "include_trace": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["entity_id"] == ENTITY_ID
        assert "steps" in data
        assert "execution_path" in data
        assert "skipped_rules" in data
        assert "final_outputs" in data
        assert "decision" in data
        assert "computed_metrics" in data
        assert len(data["steps"]) == 2

    @pytest.mark.asyncio
    async def test_execute_analyze_with_trace(self, client):
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/analyze",
            json={"entity_id": ENTITY_ID, "dimension": "credit_assessment", "include_trace": True},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        for step in data["steps"]:
            if step["status"] == "passed":
                assert "context_before" in step
                assert "context_after" in step

    @pytest.mark.asyncio
    async def test_execute_analyze_nonexistent_entity(self, client):
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/analyze",
            json={"entity_id": "NONEXISTENT", "dimension": "credit_assessment"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "NOT_FOUND" in body["error"]["code"]

    @pytest.mark.asyncio
    async def test_execute_analyze_nonexistent_view(self, client):
        resp = await client.post(
            "/v1/views/view_nonexistent/execute/analyze",
            json={"entity_id": ENTITY_ID, "dimension": "credit_assessment"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False


class TestExecuteSimulate:
    @pytest.mark.asyncio
    async def test_execute_simulate(self, client):
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/simulate",
            json={
                "entity_id": ENTITY_ID,
                "dimension": "credit_assessment",
                "overrides": {"overdue_amount": 80000},
                "include_trace": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["entity_id"] == ENTITY_ID
        assert data["simulation_type"] == "what_if"
        assert "baseline_outputs" in data
        assert "simulated_outputs" in data
        assert "comparison" in data
        assert "diffs" in data["comparison"]
        assert "impact_chains" in data["comparison"]

    @pytest.mark.asyncio
    async def test_simulate_with_no_overrides(self, client):
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/simulate",
            json={"entity_id": ENTITY_ID, "dimension": "credit_assessment"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["simulation_type"] == "what_if"
        assert data["comparison"]["changed_fields"] == 0

    @pytest.mark.asyncio
    async def test_simulate_nonexistent_entity(self, client):
        resp = await client.post(
            f"/v1/views/{VIEW_ID}/execute/simulate",
            json={"entity_id": "NONEXISTENT", "dimension": "credit_assessment"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False


class TestRulesForEntity:
    @pytest.mark.asyncio
    async def test_rules_for_entity(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/rules/for-entity/{ENTITY_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["entity_id"] == ENTITY_ID
        assert "applicable_rules" in data
        assert "dependency_edges" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_rules_for_nonexistent_entity(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/rules/for-entity/NONEXISTENT")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False


class TestMetricSnapshot:
    @pytest.mark.asyncio
    async def test_metric_snapshot(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/metrics/{ENTITY_ID}/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["entity_id"] == ENTITY_ID
        assert "metrics" in data
        assert "decision" in data

    @pytest.mark.asyncio
    async def test_metric_snapshot_nonexistent_entity(self, client):
        resp = await client.get(f"/v1/views/{VIEW_ID}/metrics/NONEXISTENT/snapshot")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
