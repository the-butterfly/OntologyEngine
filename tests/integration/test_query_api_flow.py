# tests/integration/test_query_api_flow.py
"""Query API integration tests.

Covers:
- POST /v1/query/search (semantic search)
- POST /v1/query/graph (graph traversal)
- POST /v1/query/hybrid (hybrid search)
- GET  /v1/query/pattern-match/{concept}
- GET  /v1/query/trace/{entity_id}
- POST /v1/query/path (path finding)
- Error paths: missing entity, invalid depth, no retrieval backend
"""

import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport

from ontology_engine.api.server import create_app
from ontology_engine.api import dependencies
from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.storage.base import EntityInstance, RelationInstance
from ontology_engine.services import QueryService, EntityService, SchemaService
from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata, ConceptDefinition


@pytest_asyncio.fixture
async def storage():
    s = SQLiteStorage(db_path=":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def seeded_storage(storage):
    entities = [
        EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={"name": "Supplier A", "status": "ACTIVE"}),
        EntityInstance(_fact_object="Supplier", entity_id="SUP_002", data={"name": "Supplier B", "status": "INACTIVE"}),
        EntityInstance(_fact_object="Invoice", entity_id="INV_001", data={"amount": 100000, "status": "PAID"}),
        EntityInstance(_fact_object="Invoice", entity_id="INV_002", data={"amount": 200000, "status": "OVERDUE"}),
    ]
    for e in entities:
        await storage.save_entity(e)

    relations = [
        RelationInstance(
            relation_name="has_invoice",
            from_entity_id="SUP_001",
            to_entity_id="INV_001",
            data={},
        ),
        RelationInstance(
            relation_name="has_invoice",
            from_entity_id="SUP_001",
            to_entity_id="INV_002",
            data={},
        ),
        RelationInstance(
            relation_name="has_invoice",
            from_entity_id="SUP_002",
            to_entity_id="INV_002",
            data={},
        ),
    ]
    for r in relations:
        await storage.save_relation(r)

    return storage


@pytest_asyncio.fixture
async def app(seeded_storage):
    application = create_app()

    schema = KGMLSchema(
        metadata=SchemaMetadata(id="test", name="test", version="1.0"),
        concepts=[
            ConceptDefinition(name="Supplier", description="A supplier"),
            ConceptDefinition(name="Invoice", description="An invoice"),
        ],
        metrics=[],
        rules=None,
    )

    services = {
        "schema": SchemaService(storage=seeded_storage),
        "entity": EntityService(storage=seeded_storage, schema=schema),
        "query": QueryService(storage=seeded_storage),
    }
    dependencies.init_dependencies(seeded_storage, services)

    yield application

    dependencies.init_dependencies(None, {})


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestPatternMatch:
    @pytest.mark.asyncio
    async def test_pattern_match_supplier(self, client):
        resp = await client.get("/v1/query/pattern-match/Supplier")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert len(results) == 2
        assert all(r["fact_object"] == "Supplier" for r in results)

    @pytest.mark.asyncio
    async def test_pattern_match_invoice(self, client):
        resp = await client.get("/v1/query/pattern-match/Invoice")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 2
        assert all(r["fact_object"] == "Invoice" for r in results)

    @pytest.mark.asyncio
    async def test_pattern_match_empty_concept(self, client):
        resp = await client.get("/v1/query/pattern-match/NonExistent")
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 0


class TestGraphTraverse:
    @pytest.mark.asyncio
    async def test_graph_traverse_outgoing(self, client):
        resp = await client.get(
            "/v1/query/traverse/SUP_001",
            params={"relation_name": "has_invoice", "direction": "outgoing", "depth": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert len(results) == 2
        neighbor_ids = {r["entity_id"] for r in results}
        assert "INV_001" in neighbor_ids
        assert "INV_002" in neighbor_ids

    @pytest.mark.asyncio
    async def test_graph_traverse_incoming(self, client):
        resp = await client.get(
            "/v1/query/traverse/INV_001",
            params={"relation_name": "has_invoice", "direction": "incoming", "depth": 1},
        )
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["entity_id"] == "SUP_001"

    @pytest.mark.asyncio
    async def test_graph_traverse_invalid_depth(self, client):
        resp = await client.get(
            "/v1/query/traverse/SUP_001",
            params={"relation_name": "has_invoice", "depth": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "INVALID_REQUEST" in body["error"]["code"]

    @pytest.mark.asyncio
    async def test_graph_traverse_nonexistent_entity(self, client):
        resp = await client.get(
            "/v1/query/traverse/NONEXISTENT",
            params={"relation_name": "has_invoice", "depth": 1},
        )
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 0


class TestPathFinding:
    @pytest.mark.asyncio
    async def test_find_path_get(self, client):
        resp = await client.get("/v1/query/path/SUP_001/INV_001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        paths = body["data"]["paths"]
        assert len(paths) >= 1
        assert paths[0][0] == "SUP_001"
        assert paths[0][-1] == "INV_001"

    @pytest.mark.asyncio
    async def test_find_path_post(self, client):
        resp = await client.post(
            "/v1/query/path",
            json={"from_entity_id": "SUP_001", "to_entity_id": "INV_002", "max_depth": 2},
        )
        assert resp.status_code == 200
        paths = resp.json()["data"]["paths"]
        assert len(paths) >= 1

    @pytest.mark.asyncio
    async def test_find_path_invalid_depth(self, client):
        resp = await client.post(
            "/v1/query/path",
            json={"from_entity_id": "SUP_001", "to_entity_id": "INV_001", "max_depth": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False


class TestSemanticSearch:
    @pytest.mark.asyncio
    async def test_search_without_retrieval_backend(self, client):
        resp = await client.post(
            "/v1/query/search",
            json={"text": "supplier", "top_k": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "QUERY_ERROR" in body["error"]["code"]

    @pytest.mark.asyncio
    async def test_search_with_fact_object_filter(self, client):
        resp = await client.post(
            "/v1/query/search",
            json={"text": "supplier", "fact_object": "Supplier", "top_k": 5},
        )
        assert resp.status_code == 200


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_hybrid_without_retrieval_backend(self, client):
        resp = await client.post(
            "/v1/query/hybrid",
            json={"query": "supplier", "fact_object": "Supplier"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert isinstance(results, list)


class TestGraphQuery:
    @pytest.mark.asyncio
    async def test_graph_query_traverse(self, client):
        resp = await client.post(
            "/v1/query/graph",
            json={
                "start": {"entity_id": "SUP_001"},
                "traverse": [{"relation_name": "has_invoice", "direction": "outgoing", "max_hops": 1}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_graph_query_missing_start(self, client):
        resp = await client.post(
            "/v1/query/graph",
            json={
                "start": {},
                "traverse": [],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "INVALID_REQUEST" in body["error"]["code"]

    @pytest.mark.asyncio
    async def test_graph_query_invalid_depth(self, client):
        resp = await client.post(
            "/v1/query/graph",
            json={
                "start": {"entity_id": "SUP_001"},
                "traverse": [{"relation_name": "has_invoice", "max_hops": 5}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False


class TestTraceRule:
    @pytest.mark.asyncio
    async def test_trace_nonexistent_entity(self, client):
        resp = await client.get("/v1/query/trace/NONEXISTENT")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        traces = body["data"]["traces"]
        assert isinstance(traces, list)
        assert len(traces) == 0
