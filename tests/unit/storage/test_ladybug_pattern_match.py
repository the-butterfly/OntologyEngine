"""Integration tests for graph pattern matching with ladybug.

Tests the DefaultRetrievalBackend graph_pattern_match method
when using ladybug as the graph store.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

# Skip if ladybug not installed
pytest.importorskip("ladybug", reason="ladybug not installed - install with: pip install ontology-engine[ladybug]")

from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore
from ontology_engine.storage.retrieval import DefaultRetrievalBackend


class TestLadybugPatternMatch:
    """Integration tests for pattern matching with ladybug."""

    @pytest.fixture
    def ladybug_store(self, tmp_path):
        """Create an in-memory LadybugGraphStore."""
        db_path = str(tmp_path / "pattern_test.ladybug")
        store = LadybugGraphStore()
        return store

    @pytest_asyncio.fixture
    async def initialized_retrieval(self, ladybug_store, tmp_path):
        """Create initialized retrieval backend with test data."""
        db_path = str(tmp_path / "pattern_retrieval.ladybug")
        await ladybug_store.initialize(db_path)

        # Create test graph: C1 -guarantees-> C2 -supplies-> CE1
        await ladybug_store.upsert_node("c1", ["Company"], {"region": "华东"})
        await ladybug_store.upsert_node("c2", ["Company"], {"region": "华南"})
        await ladybug_store.upsert_node("ce1", ["CoreEnterprise"], {"name": "CE1"})

        await ladybug_store.upsert_edge("e1", "c1", "c2", "guarantees")
        await ladybug_store.upsert_edge("e2", "c2", "ce1", "supplies")

        # Use storage mock for entity queries
        from unittest.mock import AsyncMock
        mock_storage = AsyncMock()
        mock_storage.query_entities.return_value = []
        mock_storage.get_neighbors.return_value = []
        mock_storage.get_entity_by_id.return_value = None

        retrieval = DefaultRetrievalBackend(
            storage=mock_storage,
            graph_store=ladybug_store,
        )

        yield retrieval

        await ladybug_store.close()

    @pytest.mark.asyncio
    async def test_pattern_match_2hop(self, initialized_retrieval):
        """Test 2-hop path pattern matching."""
        # First add start nodes via storage mock
        from ontology_engine.storage.base import EntityInstance
        initialized_retrieval.storage.query_entities.return_value = [
            EntityInstance(_fact_object="Company", entity_id="c1", data={"region": "华东"}),
        ]

        results = await initialized_retrieval.graph_pattern_match(
            "Company",
            [("guarantees", "Company")],
        )
        # Should match c1 -> c2 via guarantees
        assert len(results) == 1
        assert results[0]["nodes"][0]["entity_id"] == "c1"
        assert results[0]["nodes"][1]["entity_id"] == "c2"

    @pytest.mark.asyncio
    async def test_pattern_match_3hop_uses_cypher(self, initialized_retrieval):
        """Test 3-hop pattern uses Cypher native MATCH."""
        from ontology_engine.storage.base import EntityInstance
        initialized_retrieval.storage.query_entities.return_value = [
            EntityInstance(_fact_object="Company", entity_id="c1", data={}),
        ]

        results = await initialized_retrieval.graph_pattern_match(
            "Company",
            [("guarantees", "Company"), ("supplies", "CoreEnterprise")],
        )
        # Should match full chain c1 -> c2 -> ce1
        assert len(results) == 1
        assert results[0]["nodes"][0]["entity_id"] == "c1"
        assert results[0]["nodes"][1]["entity_id"] == "c2"
        assert results[0]["nodes"][2]["entity_id"] == "ce1"

    @pytest.mark.asyncio
    async def test_pattern_match_no_match(self, initialized_retrieval):
        """Test pattern match returns empty when no match."""
        from ontology_engine.storage.base import EntityInstance
        initialized_retrieval.storage.query_entities.return_value = [
            EntityInstance(_fact_object="Company", entity_id="ce1", data={}),
        ]

        results = await initialized_retrieval.graph_pattern_match(
            "CoreEnterprise",
            [("guarantees", "Company")],
        )
        # ce1 has no outgoing guarantees edges, so no match
        assert results == []

    @pytest.mark.asyncio
    async def test_pattern_match_with_filters(self, initialized_retrieval):
        """Test pattern match with start node filters."""
        from ontology_engine.storage.base import EntityInstance
        initialized_retrieval.storage.query_entities.return_value = [
            EntityInstance(_fact_object="Company", entity_id="c1", data={"region": "华东"}),
            EntityInstance(_fact_object="Company", entity_id="c2", data={"region": "华南"}),
        ]

        results = await initialized_retrieval.graph_pattern_match(
            "Company",
            [("guarantees", "Company")],
            start_filters={"region": "华东"},
        )
        # Should only start from c1 (华东)
        assert len(results) == 1
        assert results[0]["nodes"][0]["entity_id"] == "c1"
