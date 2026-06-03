"""Tests for CognitiveStore.search_cognitive() delegation to CognitiveStorage."""

from __future__ import annotations

from typing import Any

from unittest.mock import AsyncMock

import pytest

from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.storage.cognitive.store import CognitiveStore
from ontology_engine.storage.cognitive_interface import SearchQuery, SearchResult


def _make_node(node_id: str = "test-001", **kwargs: Any) -> CognitiveNode:
    defaults: dict[str, Any] = dict(
        id=node_id,
        memory_type="observation",
        cognitive_layer="semantic",
        content="Test content",
        space_id="default",
    )
    defaults.update(kwargs)
    return CognitiveNode(**defaults)


class TestSearchCognitiveDelegation:
    @pytest.mark.asyncio
    async def test_delegates_to_storage_search(self):
        graph_store = AsyncMock()
        storage = AsyncMock()

        n1 = _make_node("n1", content="apple fruit")
        n2 = _make_node("n2", content="apple company")

        storage.search.return_value = SearchResult(
            nodes=[n1, n2],
            scores={"n1": 0.0164, "n2": 0.0161},
            semantic_scores={"n1": 0.95, "n2": 0.88},
            keyword_scores={"n1": 0.9, "n2": 0.7},
            fusion_metadata={"strategy": "rrf", "k": 60},
        )

        with pytest.warns(DeprecationWarning):
            store = CognitiveStore(graph_store=graph_store, storage=storage)
        results = await store.search_cognitive(
            query="apple",
            space_id="default",
            top_k=5,
            memory_type="observation",
        )

        storage.search.assert_called_once()
        call_args = storage.search.call_args[0][0]
        assert isinstance(call_args, SearchQuery)
        assert call_args.query_text == "apple"
        assert call_args.space_id == "default"
        assert call_args.top_k == 5
        assert call_args.memory_type == "observation"

        assert len(results) == 2
        assert results[0]["id"] == "n1"
        assert results[0]["score"] == 0.0164
        assert results[0]["semantic_score"] == 0.95
        assert results[0]["keyword_score"] == 0.9
        assert results[0]["fusion_metadata"]["strategy"] == "rrf"

    @pytest.mark.asyncio
    async def test_fallback_when_no_storage(self):
        graph_store = AsyncMock()
        graph_store.search_cognitive.return_value = [
            {"id": "n1", "content": "apple fruit", "score": 1.0},
            {"id": "n2", "content": "banana", "score": 0.0},
        ]

        with pytest.warns(DeprecationWarning):
            store = CognitiveStore(graph_store=graph_store, storage=None)
        results = await store.search_cognitive(
            query="apple",
            space_id="default",
        )

        assert len(results) == 2
        matched = [r for r in results if r.get("score", 0) > 0]
        assert len(matched) == 1
        assert matched[0]["id"] == "n1"

    @pytest.mark.asyncio
    async def test_search_result_without_optional_scores(self):
        graph_store = AsyncMock()
        storage = AsyncMock()

        n1 = _make_node("n1", content="test")
        storage.search.return_value = SearchResult(
            nodes=[n1],
            scores={"n1": 0.02},
        )

        with pytest.warns(DeprecationWarning):
            store = CognitiveStore(graph_store=graph_store, storage=storage)
        results = await store.search_cognitive(query="test", space_id="default")

        assert len(results) == 1
        assert results[0]["score"] == 0.02
        assert "semantic_score" not in results[0]
        assert "keyword_score" not in results[0]
        assert "fusion_metadata" not in results[0]

    @pytest.mark.asyncio
    async def test_search_preserves_node_fields(self):
        graph_store = AsyncMock()
        storage = AsyncMock()

        n1 = _make_node(
            "n1",
            memory_type="entity",
            cognitive_layer="semantic",
            content="test entity",
            space_id="space-1",
            confidence=0.9,
            belief_status="accepted",
        )
        storage.search.return_value = SearchResult(
            nodes=[n1],
            scores={"n1": 0.03},
        )

        with pytest.warns(DeprecationWarning):
            store = CognitiveStore(graph_store=graph_store, storage=storage)
        results = await store.search_cognitive(query="test", space_id="space-1")

        assert results[0]["memory_type"] == "entity"
        assert results[0]["cognitive_layer"] == "semantic"
        assert results[0]["content"] == "test entity"
        assert results[0]["space_id"] == "space-1"
        assert results[0]["confidence"] == 0.9
        assert results[0]["belief_status"] == "accepted"
