"""Tests for query router."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.models import CognitiveNode, DispositionProfile
from ontology_engine.engine.cognitive.query_router import QueryRouter, detect_query_type
from ontology_engine.engine.cognitive.query_router_types import (
    PARAM_PRESETS,
)
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


class TestDetectQueryType:
    """Test query type detection."""

    def test_factual_zh(self):
        assert detect_query_type("华为是哪家公司") == "factual"

    def test_factual_en(self):
        assert detect_query_type("What is supply chain") == "factual"

    def test_multi_hop_zh(self):
        result = detect_query_type("为什么供应链中断")
        assert result in ("multi_hop", "mixed")

    def test_multi_hop_en(self):
        result = detect_query_type("How does supply chain affect pricing")
        assert result in ("multi_hop", "mixed")

    def test_temporal_zh(self):
        assert detect_query_type("2024年发生了变化") == "temporal"

    def test_temporal_en(self):
        assert detect_query_type("What happened before 2025") == "temporal"

    def test_analytical_zh(self):
        result = detect_query_type("计算风险占比")
        assert result in ("analytical", "mixed")

    def test_analytical_en(self):
        assert detect_query_type("Calculate the risk ratio") == "analytical"

    def test_mixed_factual_and_multi_hop(self):
        result = detect_query_type("供应链在哪里，为什么中断")
        assert result in ("mixed", "multi_hop")

    def test_priority_temporal_over_factual(self):
        result = detect_query_type("什么时候发生的事件")
        assert result == "temporal"

    def test_mixed_analytical_and_multi_hop(self):
        result = detect_query_type("分析原因，为什么导致中断")
        assert result in ("mixed", "analytical", "multi_hop")

    def test_default_factual(self):
        assert detect_query_type("supply chain management") == "factual"


class TestRetrievalParams:
    """Test RetrievalParams presets."""

    def test_factual_preset(self):
        params = PARAM_PRESETS["factual"]
        assert params.query_type == "factual"
        assert params.chroma_top_k == 10
        assert params.rrf_weights["w_layer_r"] == 0.5

    def test_multi_hop_preset(self):
        params = PARAM_PRESETS["multi_hop"]
        assert params.kuzu_max_depth == 3
        assert params.edge_weights.get("CAUSAL") == 2.0

    def test_temporal_preset(self):
        params = PARAM_PRESETS["temporal"]
        assert params.temporal_filter is True
        assert params.rrf_weights["w_temporal"] == 0.6

    def test_analytical_preset(self):
        params = PARAM_PRESETS["analytical"]
        assert params.chroma_top_k == 0

    def test_mixed_preset(self):
        params = PARAM_PRESETS["mixed"]
        assert params.bundle_search_enabled is True


class TestQueryRouter:
    """Test QueryRouter operations."""

    @pytest_asyncio.fixture
    async def router(self, tmp_path):
        """Create an initialized router for testing."""
        db_path = str(tmp_path / "test_router.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        rrf = RRFFusionEngine(repository=repo)
        router = QueryRouter(rrf_engine=rrf, repository=repo)
        yield router
        await store.close()

    @pytest.mark.asyncio
    async def test_route_factual(self, router):
        """Test routing a factual query."""
        results = await router.route("什么是供应链", "test_space")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_route_analytical_empty(self, router):
        """Test analytical queries return empty."""
        results = await router.route("计算风险占比", "test_space")
        assert results == []

    @pytest.mark.asyncio
    async def test_route_with_data(self, router):
        """Test routing with existing data."""
        node = CognitiveNode(
            id="mem_route_001",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Supply chain network",
            domain_id="test_space",
        )
        await router._repo.create_node(node)

        results = await router.route("supply chain", "test_space")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_route_with_disposition(self, router):
        """Test routing with DispositionProfile."""
        profile = DispositionProfile(
            id="profile_test",
            scene="audit",
            skepticism=0.9,
            thoroughness=0.8,
        )

        results = await router.route("test query", "test_space", disposition=profile)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_expand_evidence(self, router):
        """Test evidence expansion."""
        node = CognitiveNode(
            id="mem_expand_001",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Test observation",
            source_fragment_ids=[],
        )
        await router._repo.create_node(node)

        evidence = await router.expand_evidence("mem_expand_001", "test_space", depth=1)
        assert isinstance(evidence, list)

    @pytest.mark.asyncio
    async def test_expand_evidence_not_found(self, router):
        """Test evidence expansion for non-existent node."""
        evidence = await router.expand_evidence("nonexistent", "test_space")
        assert evidence == []

    @pytest.mark.asyncio
    async def test_short_circuit_override(self, router):
        """Test short-circuit override."""
        results = await router.route("test query", "test_space", allow_short_circuit=False)
        assert isinstance(results, list)
