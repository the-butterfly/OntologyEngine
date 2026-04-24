"""Unit tests for MCP dataset and query tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.mcp import init_mcp_dependencies


class FakeDatasetService:
    def __init__(self):
        self._datasets = {}
        self._next_id = 1

    async def create_dataset(self, name, scope, source_type="manual", description=None):
        ds_id = f"ds_{self._next_id:03d}"
        self._next_id += 1
        self._datasets[ds_id] = {
            "dataset_id": ds_id,
            "name": name,
            "scope": scope,
            "source_type": source_type,
            "description": description,
        }
        return self._datasets[ds_id]

    async def get_dataset(self, dataset_id):
        return self._datasets.get(dataset_id)

    async def get_dataset_entities(self, dataset_id):
        return [{"entity_id": "E1"}, {"entity_id": "E2"}]

    async def add_entities(self, dataset_id, entities):
        return len(entities)


class FakeQueryService:
    def __init__(self):
        pass

    async def pattern_match(self, concept, patterns):
        return [{"entity_id": "E1", "fact_object": "Supplier", "score": 0.9}]

    async def semantic_search(self, query_text, top_k=10):
        result = MagicMock()
        result.results = [
            MagicMock(entity_id="E1", fact_object="Supplier", score=0.95, attributes={"name": "Test"})
        ]
        return result

    async def hybrid_search(self, query_text, top_k=10):
        result = MagicMock()
        result.results = [
            MagicMock(entity_id="E2", fact_object="Guarantor", score=0.88, attributes={"name": "Hybrid"})
        ]
        return result


def _init_with_dataset_service():
    service = FakeDatasetService()
    init_mcp_dependencies(services={"dataset": service})
    return service


def _init_with_query_service():
    service = FakeQueryService()
    init_mcp_dependencies(services={"query": service})
    return service


class TestOERegisterDataset:
    """Test oe_register_dataset MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_register_dataset_success(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset

        _init_with_dataset_service()
        result = await oe_register_dataset(
            space_id="space_test",
            name="Q1 Financial Data",
            source_type="csv",
            description="Quarterly data",
        )

        assert result["success"] is True
        assert result["data"]["name"] == "Q1 Financial Data"
        assert result["data"]["source_type"] == "csv"
        assert result["data"]["dataset_id"].startswith("ds_")

    @pytest.mark.asyncio
    async def test_register_dataset_default_source_type(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset

        _init_with_dataset_service()
        result = await oe_register_dataset(space_id="space_test", name="Test DS")

        assert result["success"] is True
        assert result["data"]["source_type"] == "manual"

    @pytest.mark.asyncio
    async def test_register_dataset_without_deps(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset

        result = await oe_register_dataset(space_id="space_test", name="No Deps")

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_register_dataset_missing_service(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset

        init_mcp_dependencies(services={"other": object()})
        result = await oe_register_dataset(space_id="space_test", name="Missing Service")

        assert result["success"] is False
        assert result["error"]["code"] == "SERVICE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_register_dataset_invalid_source_type(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset

        _init_with_dataset_service()
        result = await oe_register_dataset(
            space_id="space_test",
            name="Bad Source",
            source_type="invalid_type",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_SOURCE_TYPE"
        assert "suggestion" in result["error"]


class TestOETriggerSync:
    """Test oe_trigger_sync MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_trigger_sync_success(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset, oe_trigger_sync

        service = _init_with_dataset_service()
        ds_result = await oe_register_dataset(space_id="space_test", name="Sync Test")
        dataset_id = ds_result["data"]["dataset_id"]

        result = await oe_trigger_sync(
            dataset_id=dataset_id,
            space_id="space_test",
            mode="full",
        )

        assert result["success"] is True
        assert result["data"]["dataset_id"] == dataset_id
        assert result["data"]["space_id"] == "space_test"
        assert result["data"]["mode"] == "full"
        assert result["data"]["synced_count"] == 2

    @pytest.mark.asyncio
    async def test_trigger_sync_dataset_not_found(self):
        from ontology_engine.mcp.tools.dataset import oe_trigger_sync

        _init_with_dataset_service()
        result = await oe_trigger_sync(
            dataset_id="ds_nonexistent",
            space_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DATASET_NOT_FOUND"
        assert result["error"]["suggestion"] == "Use oe_register_dataset to create a dataset first"

    @pytest.mark.asyncio
    async def test_trigger_sync_without_deps(self):
        from ontology_engine.mcp.tools.dataset import oe_trigger_sync

        result = await oe_trigger_sync(dataset_id="ds_001", space_id="space_test")

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_trigger_sync_invalid_mode(self):
        from ontology_engine.mcp.tools.dataset import oe_trigger_sync

        _init_with_dataset_service()
        result = await oe_trigger_sync(
            dataset_id="ds_001",
            space_id="space_test",
            mode="invalid_mode",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_SYNC_MODE"
        assert "suggestion" in result["error"]


class TestOEQuery:
    """Test oe_query MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_query_hybrid_mode(self):
        from ontology_engine.mcp.tools.query import oe_query

        _init_with_query_service()
        result = await oe_query(query="high risk suppliers", match_mode="hybrid")

        assert result["success"] is True
        assert result["data"]["match_mode"] == "hybrid"
        assert result["data"]["query"] == "high risk suppliers"
        assert len(result["data"]["results"]) > 0

    @pytest.mark.asyncio
    async def test_query_vector_mode(self):
        from ontology_engine.mcp.tools.query import oe_query

        _init_with_query_service()
        result = await oe_query(query="test query", match_mode="vector")

        assert result["success"] is True
        assert result["data"]["match_mode"] == "vector"

    @pytest.mark.asyncio
    async def test_query_pattern_mode(self):
        from ontology_engine.mcp.tools.query import oe_query

        _init_with_query_service()
        result = await oe_query(query="test pattern", match_mode="pattern")

        assert result["success"] is True
        assert result["data"]["match_mode"] == "pattern"

    @pytest.mark.asyncio
    async def test_query_invalid_mode(self):
        from ontology_engine.mcp.tools.query import oe_query

        _init_with_query_service()
        result = await oe_query(query="test", match_mode="invalid_mode")

        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_MATCH_MODE"
        assert result["error"]["suggestion"] == "Use one of: vector, keyword, hybrid, pattern"

    @pytest.mark.asyncio
    async def test_query_graph_mode_not_available(self):
        from ontology_engine.mcp.tools.query import oe_query

        _init_with_query_service()
        result = await oe_query(query="test", match_mode="graph")

        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_MATCH_MODE"

    @pytest.mark.asyncio
    async def test_query_top_k_limit(self):
        from ontology_engine.mcp.tools.query import oe_query

        _init_with_query_service()
        result = await oe_query(query="test", match_mode="pattern", top_k=1)

        assert result["success"] is True
        assert result["data"]["total_count"] <= 1

    @pytest.mark.asyncio
    async def test_query_without_deps(self):
        from ontology_engine.mcp.tools.query import oe_query

        result = await oe_query(query="test")

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_query_missing_service(self):
        from ontology_engine.mcp.tools.query import oe_query

        init_mcp_dependencies(services={"other": object()})
        result = await oe_query(query="test")

        assert result["success"] is False
        assert result["error"]["code"] == "SERVICE_NOT_FOUND"
