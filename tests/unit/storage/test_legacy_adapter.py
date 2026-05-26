"""Tests for LegacyStorageAdapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from ontology_engine.engine.cognitive.models import CognitiveNode, DispositionProfile
from ontology_engine.storage.cognitive_interface import SearchQuery, StorageInterface
from ontology_engine.storage.legacy_adapter import LegacyStorageAdapter


class _MockBackend:
    """Mock CognitiveStorageBackend for testing."""

    def __init__(self) -> None:
        self.save_cognitive_node = AsyncMock()
        self.get_cognitive_node = AsyncMock(return_value=None)
        self.list_cognitive_nodes = AsyncMock(return_value=[])
        self.delete_cognitive_node = AsyncMock()
        self.update_cognitive_node_belief = AsyncMock()
        self.update_cognitive_node_with_occ = AsyncMock(return_value=None)
        self.save_cognitive_edge = AsyncMock(return_value={})
        self.list_cognitive_edges = AsyncMock(return_value=[])
        self.save_disposition = AsyncMock()
        self.get_disposition = AsyncMock(return_value=None)
        self.compute_dynamic_weights = AsyncMock(return_value={})


def _make_node(node_id: str = "test_node_1", **kwargs) -> CognitiveNode:
    return CognitiveNode(
        id=node_id,
        memory_type=kwargs.get("memory_type", "entity"),
        cognitive_layer=kwargs.get("cognitive_layer", "semantic"),
        content=kwargs.get("content", "Test content"),
        domain_id=kwargs.get("domain_id", "test_domain"),
        space_id=kwargs.get("space_id", "default"),
        **{k: v for k, v in kwargs.items() if k not in ("id", "memory_type", "cognitive_layer", "content", "domain_id", "space_id")},
    )


class TestLegacyStorageAdapterIsStorageInterface:
    def test_is_instance(self):
        backend = _MockBackend()
        adapter = LegacyStorageAdapter(backend)
        assert isinstance(adapter, StorageInterface)


class TestSaveNode:
    @pytest.mark.asyncio
    async def test_save_node_delegates_and_returns_id(self):
        backend = _MockBackend()
        adapter = LegacyStorageAdapter(backend)
        node = _make_node()
        result = await adapter.save_node(node)
        assert result == node.id
        backend.save_cognitive_node.assert_awaited_once()
        call_args = backend.save_cognitive_node.call_args[0][0]
        assert call_args["id"] == node.id
        assert call_args["content"] == "Test content"


class TestGetNode:
    @pytest.mark.asyncio
    async def test_get_node_returns_none_when_not_found(self):
        backend = _MockBackend()
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.get_node("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_converts_dict_to_cognitive_node(self):
        backend = _MockBackend()
        node = _make_node()
        backend.get_cognitive_node = AsyncMock(return_value=node.to_dict())
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.get_node(node.id)
        assert isinstance(result, CognitiveNode)
        assert result.id == node.id
        assert result.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_node_returns_cognitive_node_directly(self):
        backend = _MockBackend()
        node = _make_node()
        backend.get_cognitive_node = AsyncMock(return_value=node)
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.get_node(node.id)
        assert result is node


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_search_result(self):
        backend = _MockBackend()
        node = _make_node()
        backend.list_cognitive_nodes = AsyncMock(return_value=[node.to_dict()])
        adapter = LegacyStorageAdapter(backend)
        query = SearchQuery(query_text="test", space_id="default", top_k=10)
        result = await adapter.search(query)
        assert len(result.nodes) == 1
        assert isinstance(result.nodes[0], CognitiveNode)
        assert result.nodes[0].id == node.id
        assert node.id in result.scores

    @pytest.mark.asyncio
    async def test_search_passes_filters(self):
        backend = _MockBackend()
        backend.list_cognitive_nodes = AsyncMock(return_value=[])
        adapter = LegacyStorageAdapter(backend)
        query = SearchQuery(
            query_text="test",
            space_id="space1",
            top_k=5,
            memory_type="entity",
            cognitive_layer="semantic",
            belief_status="accepted",
        )
        await adapter.search(query)
        backend.list_cognitive_nodes.assert_awaited_once_with(
            memory_type="entity",
            cognitive_layer="semantic",
            belief_status="accepted",
            domain_id="space1",
            limit=5,
        )


class TestDeleteNode:
    @pytest.mark.asyncio
    async def test_delete_node_delegates(self):
        backend = _MockBackend()
        adapter = LegacyStorageAdapter(backend)
        await adapter.delete_node("node_1")
        backend.delete_cognitive_node.assert_awaited_once_with("node_1")


class TestBatchSave:
    @pytest.mark.asyncio
    async def test_batch_save_returns_ids(self):
        backend = _MockBackend()
        adapter = LegacyStorageAdapter(backend)
        nodes = [_make_node("n1"), _make_node("n2")]
        result = await adapter.batch_save(nodes)
        assert result == ["n1", "n2"]
        assert backend.save_cognitive_node.await_count == 2


class TestCount:
    @pytest.mark.asyncio
    async def test_count_returns_length(self):
        backend = _MockBackend()
        backend.list_cognitive_nodes = AsyncMock(
            return_value=[{"id": "1"}, {"id": "2"}, {"id": "3"}]
        )
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.count({"memory_type": "entity"})
        assert result == 3
        backend.list_cognitive_nodes.assert_awaited_once_with(
            limit=999999, memory_type="entity"
        )


class TestListNodes:
    @pytest.mark.asyncio
    async def test_list_nodes_converts_dicts(self):
        backend = _MockBackend()
        node = _make_node()
        backend.list_cognitive_nodes = AsyncMock(return_value=[node.to_dict()])
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.list_nodes(memory_type="entity", limit=50)
        assert len(result) == 1
        assert isinstance(result[0], CognitiveNode)
        assert result[0].id == node.id

    @pytest.mark.asyncio
    async def test_list_nodes_passes_all_params(self):
        backend = _MockBackend()
        backend.list_cognitive_nodes = AsyncMock(return_value=[])
        adapter = LegacyStorageAdapter(backend)
        await adapter.list_nodes(
            memory_type="entity",
            cognitive_layer="semantic",
            belief_status="accepted",
            domain_id="d1",
            space_id="s1",
            limit=10,
            as_of="2024-01-01",
        )
        backend.list_cognitive_nodes.assert_awaited_once_with(
            memory_type="entity",
            cognitive_layer="semantic",
            belief_status="accepted",
            domain_id="d1",
            space_id="s1",
            limit=10,
            as_of="2024-01-01",
        )


class TestUpdateNodeWithOcc:
    @pytest.mark.asyncio
    async def test_update_node_with_occ_delegates(self):
        backend = _MockBackend()
        backend.update_cognitive_node_with_occ = AsyncMock(return_value={"id": "n1"})
        adapter = LegacyStorageAdapter(backend)
        updates = {"content": "new"}
        result = await adapter.update_node_with_occ("n1", 1, updates)
        assert result == {"id": "n1"}
        backend.update_cognitive_node_with_occ.assert_awaited_once_with("n1", 1, updates)


class TestDispositionMethods:
    @pytest.mark.asyncio
    async def test_save_disposition_delegates(self):
        backend = _MockBackend()
        adapter = LegacyStorageAdapter(backend)
        profile = DispositionProfile(id="p1", scene="test")
        await adapter.save_disposition(profile.to_dict())
        backend.save_disposition.assert_awaited_once_with(profile.to_dict())

    @pytest.mark.asyncio
    async def test_get_disposition_delegates(self):
        backend = _MockBackend()
        backend.get_disposition = AsyncMock(return_value={"id": "p1", "scene": "test"})
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.get_disposition(profile_id="p1")
        assert result == {"id": "p1", "scene": "test"}
        backend.get_disposition.assert_awaited_once_with(
            profile_id="p1", scene=None, domain_id=None
        )

    @pytest.mark.asyncio
    async def test_compute_dynamic_weights_delegates(self):
        backend = _MockBackend()
        backend.compute_dynamic_weights = AsyncMock(
            return_value={"entity": 2.5, "observation": 1.8}
        )
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.compute_dynamic_weights({"skepticism": 0.8})
        assert result == {"entity": 2.5, "observation": 1.8}
        backend.compute_dynamic_weights.assert_awaited_once_with({"skepticism": 0.8})


class TestEdgeMethods:
    @pytest.mark.asyncio
    async def test_save_edge_delegates(self):
        backend = _MockBackend()
        backend.save_cognitive_edge = AsyncMock(
            return_value={"edge_type": "SUPPORTS", "from_id": "a", "to_id": "b"}
        )
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.save_edge("SUPPORTS", "a", "b", {"strength": 0.8})
        assert result["edge_type"] == "SUPPORTS"
        backend.save_cognitive_edge.assert_awaited_once_with(
            edge_type="SUPPORTS", from_id="a", to_id="b", properties={"strength": 0.8}
        )

    @pytest.mark.asyncio
    async def test_list_edges_delegates(self):
        backend = _MockBackend()
        backend.list_cognitive_edges = AsyncMock(
            return_value=[{"edge_type": "SUPPORTS", "from_id": "a", "to_id": "b"}]
        )
        adapter = LegacyStorageAdapter(backend)
        result = await adapter.list_edges(from_id="a", limit=10)
        assert len(result) == 1
        backend.list_cognitive_edges.assert_awaited_once_with(
            from_id="a", to_id=None, edge_type=None, limit=10
        )
