"""Tests for DefaultRetrievalBackend."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ontology_engine.storage.base import HybridSearchResult, VectorSearchResult
from ontology_engine.storage.retrieval import DefaultRetrievalBackend


class TestDefaultRetrievalBackend:
    """Exercise DefaultRetrievalBackend orchestration."""

    @pytest.fixture
    def storage(self):
        s = AsyncMock()
        s.query_entities = AsyncMock(return_value=[])
        s.get_neighbors = AsyncMock(return_value=[])
        s.get_entity_by_id = AsyncMock(return_value=None)
        return s

    @pytest.fixture
    def graph_store(self):
        g = AsyncMock()
        g.get_neighbors = AsyncMock(return_value=[])
        g.execute_cypher = AsyncMock(return_value=[])
        return g

    @pytest.fixture
    def vector_store(self):
        v = AsyncMock()
        v.search = AsyncMock(return_value=[])
        return v

    @pytest.fixture
    def retrieval(self, storage, graph_store, vector_store):
        return DefaultRetrievalBackend(
            storage=storage,
            graph_store=graph_store,
            vector_store=vector_store,
        )

    # -------------------------------------------------------------------------
    # Semantic search
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_semantic_search_no_vector_store(self, storage):
        r = DefaultRetrievalBackend(storage=storage, vector_store=None)
        result = await r.semantic_search("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_semantic_search_with_embedder(self, storage, vector_store):
        vector_store.search.return_value = [
            VectorSearchResult(id="e1", score=0.9, metadata={"concept_type": "A"}),
        ]
        embedder = lambda text: [1.0, 0.0]  # noqa: E731
        r = DefaultRetrievalBackend(
            storage=storage, vector_store=vector_store, embedder=embedder
        )
        results = await r.semantic_search("hello", top_k=5)
        assert len(results) == 1
        assert results[0].id == "e1"
        vector_store.search.assert_awaited_once_with([1.0, 0.0], top_k=5)

    @pytest.mark.asyncio
    async def test_semantic_search_concept_filter(self, storage, vector_store):
        vector_store.search.return_value = [
            VectorSearchResult(id="e1", score=0.9, metadata={"concept_type": "A"}),
            VectorSearchResult(id="e2", score=0.8, metadata={"concept_type": "B"}),
        ]
        embedder = lambda text: [1.0, 0.0]  # noqa: E731
        r = DefaultRetrievalBackend(
            storage=storage, vector_store=vector_store, embedder=embedder
        )
        results = await r.semantic_search("hello", concept_type="A")
        assert len(results) == 1
        assert results[0].id == "e1"

    @pytest.mark.asyncio
    async def test_semantic_search_without_embedder_raises(self, storage, vector_store):
        r = DefaultRetrievalBackend(storage=storage, vector_store=vector_store)
        with pytest.raises(NotImplementedError, match="embedder"):
            await r.semantic_search("hello")

    # -------------------------------------------------------------------------
    # Hybrid search
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_hybrid_search_independent_then_fuse(self, storage, graph_store, vector_store):
        """Test the default fusion strategy independent_then_fuse."""
        vector_store.search.return_value = [
            VectorSearchResult(id="e1", score=1.0, metadata={}),
            VectorSearchResult(id="e2", score=0.5, metadata={}),
        ]
        graph_store.get_neighbors.return_value = [
            {"neighbor_id": "e2"},
            {"neighbor_id": "e3"},
        ]
        r = DefaultRetrievalBackend(
            storage=storage,
            graph_store=graph_store,
            vector_store=vector_store,
        )
        result = await r.hybrid_search(
            query_vector=[1.0, 0.0],
            graph_seed_id="seed",
            top_k=10,
            fusion_strategy="independent_then_fuse",
        )
        assert isinstance(result, HybridSearchResult)
        ids = {r.id for r in result.results}
        assert "e1" in ids
        assert "e2" in ids
        assert "e3" in ids
        # Check intermediate scores are present
        assert result.semantic_scores
        assert result.graph_scores
        assert result.fusion_metadata["strategy"] == "independent_then_fuse"

    @pytest.mark.asyncio
    async def test_hybrid_search_filter_then_fuse(self, storage, graph_store, vector_store):
        """Test filter_then_fuse strategy."""
        vector_store.search.return_value = [
            VectorSearchResult(id="e1", score=1.0, metadata={}),
            VectorSearchResult(id="e2", score=0.5, metadata={}),
        ]
        graph_store.get_neighbors.return_value = [
            {"neighbor_id": "e2"},
            {"neighbor_id": "e3"},
        ]
        r = DefaultRetrievalBackend(
            storage=storage,
            graph_store=graph_store,
            vector_store=vector_store,
        )
        result = await r.hybrid_search(
            query_vector=[1.0, 0.0],
            graph_seed_id="seed",
            top_k=10,
            fusion_strategy="filter_then_fuse",
            path_pattern=[("supplies", "CoreEnterprise")],
            path_weight=0.3,
        )
        assert isinstance(result, HybridSearchResult)
        assert result.fusion_metadata["strategy"] == "filter_then_fuse"

    @pytest.mark.asyncio
    async def test_hybrid_search_unknown_strategy_raises(self, retrieval):
        with pytest.raises(ValueError, match="Unknown fusion strategy"):
            await retrieval.hybrid_search(
                query_vector=[1.0, 0.0],
                fusion_strategy="unknown",
            )

    @pytest.mark.asyncio
    async def test_hybrid_search_no_vector_or_graph(self, storage):
        r = DefaultRetrievalBackend(storage=storage)
        result = await r.hybrid_search(query_vector=[1.0, 0.0])
        assert isinstance(result, HybridSearchResult)
        assert result.results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_with_path_pattern(self, storage, graph_store, vector_store):
        """Test hybrid_search with path_pattern parameter."""
        vector_store.search.return_value = [
            VectorSearchResult(id="e1", score=1.0, metadata={}),
        ]
        graph_store.get_neighbors.return_value = [
            {"neighbor_id": "e2", "properties": {"weight": 0.8}},
        ]
        r = DefaultRetrievalBackend(
            storage=storage,
            graph_store=graph_store,
            vector_store=vector_store,
        )
        result = await r.hybrid_search(
            query_vector=[1.0, 0.0],
            graph_seed_id="seed",
            top_k=10,
            path_pattern=[("guarantees", "Company")],
            path_weight=0.3,
        )
        assert isinstance(result, HybridSearchResult)
        assert result.path_match_scores is not None

    # -------------------------------------------------------------------------
    # Graph pattern match
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_graph_pattern_match_empty_pattern(self, storage):
        from ontology_engine.storage.base import EntityInstance
        storage.query_entities.return_value = [
            EntityInstance(concept="Company", entity_id="c1", data={"name": "A"}),
        ]
        r = DefaultRetrievalBackend(storage=storage)
        results = await r.graph_pattern_match("Company", [])
        assert len(results) == 1
        assert results[0]["nodes"][0]["entity_id"] == "c1"

    @pytest.mark.asyncio
    async def test_graph_pattern_match_short_path(self, storage, graph_store):
        """Test short path (<=2 hops) uses get_neighbors."""
        from ontology_engine.storage.base import EntityInstance
        storage.query_entities.return_value = [
            EntityInstance(concept="Company", entity_id="c1", data={}),
        ]
        graph_store.get_neighbors.return_value = [
            {"neighbor_id": "c2", "edge_type": "guarantees"},
        ]
        r = DefaultRetrievalBackend(storage=storage, graph_store=graph_store)
        results = await r.graph_pattern_match(
            "Company",
            [("guarantees", "Company")],
        )
        assert len(results) == 1
        # Verify get_neighbors was called with node_concept
        graph_store.get_neighbors.assert_called()
        call_args = graph_store.get_neighbors.call_args
        assert call_args[1].get("node_concept") == "Company"

    @pytest.mark.asyncio
    async def test_graph_pattern_match_long_path_uses_cypher(self, storage, graph_store):
        """Test long path (>2 hops) uses Cypher."""
        from ontology_engine.storage.base import EntityInstance
        storage.query_entities.return_value = [
            EntityInstance(concept="Company", entity_id="c1", data={}),
        ]
        # 3-hop pattern triggers Cypher path
        graph_store.execute_cypher.return_value = [
            {
                "start.entity_id": "c1",
                "n1.entity_id": "c2",
                "n2.entity_id": "c3",
                "n3.entity_id": "ce1",
            }
        ]
        r = DefaultRetrievalBackend(storage=storage, graph_store=graph_store)
        results = await r.graph_pattern_match(
            "Company",
            [("guarantees", "Company"), ("owns", "Company"), ("supplies", "CoreEnterprise")],
        )
        assert len(results) == 1
        # Verify execute_cypher was called
        graph_store.execute_cypher.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graph_pattern_match_with_fallback(self, storage):
        """Test fallback to DuckDB when no graph store."""
        from ontology_engine.storage.base import EntityInstance, RelationInstance
        storage.query_entities.return_value = [
            EntityInstance(concept="Company", entity_id="c1", data={}),
        ]
        storage.get_neighbors.return_value = [
            (
                EntityInstance(concept="Invoice", entity_id="i1", data={}),
                RelationInstance("has_invoice", "c1", "i1"),
            )
        ]
        storage.get_entity_by_id.return_value = None
        r = DefaultRetrievalBackend(storage=storage)
        results = await r.graph_pattern_match(
            "Company",
            [("has_invoice", "Invoice")],
        )
        assert len(results) == 1
        assert results[0]["nodes"][0]["entity_id"] == "c1"
        assert results[0]["nodes"][1]["entity_id"] == "i1"

    @pytest.mark.asyncio
    async def test_graph_pattern_match_no_match(self, storage, graph_store):
        from ontology_engine.storage.base import EntityInstance
        storage.query_entities.return_value = [
            EntityInstance(concept="Company", entity_id="c1", data={}),
        ]
        graph_store.get_neighbors.return_value = []
        r = DefaultRetrievalBackend(storage=storage, graph_store=graph_store)
        results = await r.graph_pattern_match(
            "Company",
            [("guarantees", "Company")],
        )
        assert results == []

