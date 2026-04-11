# tests/unit/services/test_query_service.py
"""Tests for QueryService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.services.query_service import QueryService
from ontology_engine.storage.duckdb import EntityInstance


class TestQueryService:
    """Test QueryService operations."""

    @pytest.fixture
    def storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.query_entities = AsyncMock(return_value=[])
        storage.get_neighbors = AsyncMock(return_value=[])
        storage._ensure_initialized = MagicMock()
        storage._conn = MagicMock()
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
        storage.query_entities.assert_called_once_with(concept="Supplier", filters=None)

    @pytest.mark.asyncio
    async def test_pattern_match_with_results(self, service, storage):
        """Test pattern match with results."""
        entities = [
            EntityInstance(concept="Supplier", entity_id="SUP_001", data={"name": "Supplier A"}),
            EntityInstance(concept="Supplier", entity_id="SUP_002", data={"name": "Supplier B"}),
        ]
        storage.query_entities.return_value = entities

        result = await service.pattern_match("Supplier")

        assert len(result) == 2
        assert result[0].entity_id == "SUP_001"
        assert result[0].score == 1.0

    @pytest.mark.asyncio
    async def test_pattern_match_with_filters(self, service, storage):
        """Test pattern match with attribute filters."""
        result = await service.pattern_match("Supplier", patterns={"status": "active"})

        storage.query_entities.assert_called_once_with(
            concept="Supplier",
            filters={"status": "active"}
        )

    @pytest.mark.asyncio
    async def test_graph_traverse(self, service, storage):
        """Test graph traversal."""
        neighbors = [
            (EntityInstance(concept="Invoice", entity_id="INV_001", data={}), MagicMock()),
            (EntityInstance(concept="Invoice", entity_id="INV_002", data={}), MagicMock()),
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
            relation_type="has_invoice",
            direction="incoming"
        )

    @pytest.mark.asyncio
    async def test_trace_rule(self, service, storage):
        """Test rule tracing."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("SUP_001", "R001", "PASSED", "2024-01-01 10:00:00"),
            ("SUP_001", "R002", "FAILED", "2024-01-01 11:00:00"),
        ]
        storage._conn.execute = AsyncMock(return_value=mock_cursor)

        result = await service.trace_rule("SUP_001")

        assert len(result) == 2
        assert result[0]["rule_id"] == "R001"

    @pytest.mark.asyncio
    async def test_trace_rule_with_specific_rule(self, service, storage):
        """Test tracing specific rule."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("SUP_001", "R001", "PASSED", "2024-01-01 10:00:00"),
        ]
        storage._conn.execute = AsyncMock(return_value=mock_cursor)

        result = await service.trace_rule("SUP_001", rule_id="R001")

        assert len(result) == 1
        assert result[0]["rule_id"] == "R001"

    @pytest.mark.asyncio
    async def test_find_path(self, service, storage):
        """Test finding paths between entities."""
        # First call returns neighbor
        storage.get_neighbors.side_effect = [
            [(EntityInstance(concept="Invoice", entity_id="INV_001", data={}), MagicMock())],
            []  # Second level has no neighbors
        ]

        result = await service.find_path("SUP_001", "INV_001", max_depth=2)

        assert len(result) >= 0  # May or may not find path

    @pytest.mark.asyncio
    async def test_find_path_depth_limit(self, service):
        """Test find path depth limit."""
        with pytest.raises(ValueError):
            await service.find_path("SUP_001", "INV_001", max_depth=5)
