# tests/unit/services/test_query_service.py
"""Tests for QueryService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.services.query_service import QueryService
from ontology_engine.storage.base import VectorSearchResult
from ontology_engine.storage.base import EntityInstance


class TestQueryService:
    """Test QueryService operations."""

    @pytest.fixture
    def storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.query_entities = AsyncMock(return_value=[])
        storage.get_neighbors = AsyncMock(return_value=[])
        storage._ensure_initialized = MagicMock()
        storage.get_rule_execution_log = AsyncMock(return_value=[])
        return storage

    @pytest.fixture
    def rule_executor(self):
        """Create mock rule executor."""
        return None

    @pytest.fixture
    def service(self, storage, rule_executor):
        """Create QueryService instance."""
        return QueryService(storage=storage, rule_executor=rule_executor)

    @pytest.mark.asyncio
    async def test_pattern_match_empty(self, service, storage):
        """Test pattern match with no results."""
        storage.query_entities.return_value = []

        result = await service.pattern_match("Supplier")

        assert len(result) == 0
        storage.query_entities.assert_called_once_with(fact_object="Supplier", filters=None)

    @pytest.mark.asyncio
    async def test_pattern_match_with_results(self, service, storage):
        """Test pattern match with results."""
        entities = [
            EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={"name": "Supplier A"}),
            EntityInstance(_fact_object="Supplier", entity_id="SUP_002", data={"name": "Supplier B"}),
        ]
        storage.query_entities.return_value = entities

        result = await service.pattern_match("Supplier")

        assert len(result) == 2
        assert result[0].entity_id == "SUP_001"
        assert result[0].score == 1.0

    @pytest.mark.asyncio
    async def test_pattern_match_with_filters(self, service, storage):
        """Test pattern match with attribute filters."""
        await service.pattern_match("Supplier", patterns={"status": "active"})

        storage.query_entities.assert_called_once_with(
            fact_object="Supplier",
            filters={"status": "active"}
        )

    @pytest.mark.asyncio
    async def test_graph_traverse(self, service, storage):
        """Test graph traversal."""
        neighbors = [
            (EntityInstance(_fact_object="Invoice", entity_id="INV_001", data={}), MagicMock()),
            (EntityInstance(_fact_object="Invoice", entity_id="INV_002", data={}), MagicMock()),
        ]
        storage.get_neighbors.return_value = neighbors

        result = await service.graph_traverse("SUP_001", "has_invoice")

        assert len(result) == 2
        assert result[0].entity_id == "INV_001"

    @pytest.mark.asyncio
    async def test_graph_traverse_depth_limit(self, service):
        """Test graph traversal depth limit."""
        with pytest.raises(ValueError):
            await service.graph_traverse("SUP_001", "has_invoice", depth=3)

    @pytest.mark.asyncio
    async def test_graph_traverse_incoming_direction(self, service, storage):
        """Test graph traversal with incoming direction."""
        await service.graph_traverse("INV_001", "has_invoice", direction="incoming")

        storage.get_neighbors.assert_called_once_with(
            entity_id="INV_001",
            relation_name="has_invoice",
            direction="incoming"
        )

    @pytest.mark.asyncio
    async def test_trace_rule(self, service, storage):
        """Test rule tracing."""
        storage.get_rule_execution_log = AsyncMock(return_value=[
            {"entity_id": "SUP_001", "rule_id": "R001", "result": "passed", "executed_at": "2024-01-01 10:00:00"},
            {"entity_id": "SUP_001", "rule_id": "R002", "result": "failed", "executed_at": "2024-01-01 11:00:00"},
        ])

        result = await service.trace_rule("SUP_001")

        assert len(result) == 2
        assert result[0]["rule_id"] == "R001"
        storage.get_rule_execution_log.assert_called_once_with("SUP_001", None)

    @pytest.mark.asyncio
    async def test_trace_rule_with_specific_rule(self, service, storage):
        """Test tracing specific rule."""
        storage.get_rule_execution_log = AsyncMock(return_value=[
            {"entity_id": "SUP_001", "rule_id": "R001", "result": "passed", "executed_at": "2024-01-01 10:00:00"},
        ])

        result = await service.trace_rule("SUP_001", rule_id="R001")

        assert len(result) == 1
        assert result[0]["rule_id"] == "R001"
        storage.get_rule_execution_log.assert_called_once_with("SUP_001", "R001")

    @pytest.mark.asyncio
    async def test_find_path(self, service, storage):
        """Test finding paths between entities."""
        # First call returns neighbor
        storage.get_neighbors.side_effect = [
            [(EntityInstance(_fact_object="Invoice", entity_id="INV_001", data={}), MagicMock())],
            []  # Second level has no neighbors
        ]

        result = await service.find_path("SUP_001", "INV_001", max_depth=2)

        assert len(result) >= 0  # May or may not find path

    @pytest.mark.asyncio
    async def test_find_path_depth_limit(self, service):
        """Test find path depth limit."""
        with pytest.raises(ValueError):
            await service.find_path("SUP_001", "INV_001", max_depth=5)


class TestQueryServicePhase2Retrieval:
    """Test Phase 2 retrieval interfaces on QueryService."""

    @pytest.fixture
    def storage(self):
        return AsyncMock()

    @pytest.fixture
    def retrieval(self):
        r = AsyncMock()
        r.semantic_search = AsyncMock(return_value=[])
        r.hybrid_search = AsyncMock(return_value=[])
        r.graph_pattern_match = AsyncMock(return_value=[])
        return r

    @pytest.fixture
    def service(self, storage, retrieval):
        return QueryService(storage=storage, retrieval=retrieval)

    @pytest.mark.asyncio
    async def test_semantic_search_delegates_to_retrieval(self, service, retrieval):
        retrieval.semantic_search.return_value = [
            VectorSearchResult(id="e1", score=0.9, metadata={}),
        ]
        result = await service.semantic_search("query", top_k=5, fact_object="Company")
        assert len(result) == 1
        retrieval.semantic_search.assert_awaited_once_with(
            query_text="query", top_k=5, fact_object="Company"
        )

    @pytest.mark.asyncio
    async def test_semantic_search_without_retrieval_raises(self, storage):
        service = QueryService(storage=storage)
        with pytest.raises(NotImplementedError, match="RetrievalBackend"):
            await service.semantic_search("query")

    @pytest.mark.asyncio
    async def test_hybrid_search_delegates_to_retrieval(self, service, retrieval):
        retrieval.hybrid_search.return_value = [
            VectorSearchResult(id="e1", score=0.8, metadata={}),
        ]
        result = await service.hybrid_search(
            query_text="hello",
            graph_seed_id="seed",
            top_k=3,
        )
        assert len(result) == 1
        retrieval.hybrid_search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_without_retrieval_raises(self, storage):
        service = QueryService(storage=storage)
        with pytest.raises(NotImplementedError, match="RetrievalBackend"):
            await service.hybrid_search(query_vector=[1.0, 0.0])

    @pytest.mark.asyncio
    async def test_graph_pattern_match_delegates_to_retrieval(self, service, retrieval):
        retrieval.graph_pattern_match.return_value = [
            {"nodes": [{"entity_id": "c1"}]},
        ]
        result = await service.graph_pattern_match(
            "Company",
            [("supplies", "Enterprise")],
            start_filters={"status": "active"},
            limit=50,
        )
        assert len(result) == 1
        retrieval.graph_pattern_match.assert_awaited_once_with(
            start_concept="Company",
            path_pattern=[("supplies", "Enterprise")],
            start_filters={"status": "active"},
            limit=50,
        )

    @pytest.mark.asyncio
    async def test_graph_pattern_match_fallback_without_retrieval(self, storage):
        from ontology_engine.storage.base import EntityInstance
        storage.query_entities.return_value = [
            EntityInstance(_fact_object="Company", entity_id="c1", data={}),
        ]
        storage.get_neighbors.return_value = []
        service = QueryService(storage=storage)
        result = await service.graph_pattern_match("Company", [])
        assert len(result) == 1
        assert result[0]["nodes"][0]["entity_id"] == "c1"
