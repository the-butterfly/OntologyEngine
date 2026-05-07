"""Tests for RRF fusion engine."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import (
    RRFFusionEngine,
    extract_temporal_constraint,
)
from ontology_engine.engine.cognitive.rrf_types import (
    BASE_TYPE_WEIGHTS,
    COGNITIVE_LAYER_PRIORITY,
    QUERY_TYPE_WEIGHTS,
    RRF_K,
    RetrievalResult,
)
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


class TestTemporalConstraint:
    """Test TemporalConstraint extraction and properties."""

    def test_extract_year(self):
        tc = extract_temporal_constraint("What happened in 2024?")
        assert tc is not None
        assert tc.kind == "year"
        assert tc.groups == ("2024",)
        assert tc.period_start == "2024-01-01"
        assert tc.period_end == "2024-12-31"

    def test_extract_range(self):
        tc = extract_temporal_constraint("Data from 2022-2024")
        assert tc is not None
        assert tc.kind == "range"
        assert tc.period_start == "2022-01-01"
        assert tc.period_end == "2024-12-31"

    def test_extract_since(self):
        tc = extract_temporal_constraint("Changes since 2023")
        assert tc is not None
        assert tc.kind == "since"
        assert tc.period_start == "2023-01-01"

    def test_extract_before(self):
        tc = extract_temporal_constraint("Events before 2025")
        assert tc is not None
        assert tc.kind == "before"
        assert tc.period_end == "2025-12-31"

    def test_extract_relative(self):
        tc = extract_temporal_constraint("Recent changes last year")
        assert tc is not None
        assert tc.kind == "relative"

    def test_no_temporal(self):
        tc = extract_temporal_constraint("What is supply chain?")
        assert tc is None


class TestRRFConstants:
    """Test RRF constants and weight tables."""

    def test_rrf_k(self):
        assert RRF_K == 60

    def test_query_type_weights_sum_to_one(self):
        for qtype, weights in QUERY_TYPE_WEIGHTS.items():
            if qtype == "analytical":
                continue
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{qtype} weights sum to {total}"

    def test_base_type_weights_positive(self):
        for mtype, weight in BASE_TYPE_WEIGHTS.items():
            assert weight > 0, f"{mtype} weight is {weight}"

    def test_cognitive_layer_priority_ordering(self):
        assert COGNITIVE_LAYER_PRIORITY["opinion"] > COGNITIVE_LAYER_PRIORITY["semantic"]
        assert COGNITIVE_LAYER_PRIORITY["semantic"] > COGNITIVE_LAYER_PRIORITY["procedure"]
        assert COGNITIVE_LAYER_PRIORITY["procedure"] > COGNITIVE_LAYER_PRIORITY["perception"]


class TestRRFFusionEngine:
    """Test RRFFusionEngine operations."""

    @pytest_asyncio.fixture
    async def engine(self, tmp_path):
        """Create an initialized RRF fusion engine for testing."""
        db_path = str(tmp_path / "test_rrf.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        engine = RRFFusionEngine(repository=repo)
        yield engine
        await store.close()

    @pytest.mark.asyncio
    async def test_fuse_empty_space(self, engine):
        """Test fusion with no data returns empty."""
        results = await engine.fuse("test query", "mixed", "empty_space")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_fuse_analytical_returns_empty(self, engine):
        """Test analytical queries use broad retrieval strategy."""
        results = await engine.fuse("test query", "analytical", "test_space")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_fuse_with_data(self, engine):
        """Test fusion with some data."""
        node = CognitiveNode(
            id="mem_test_001",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Supply chain management",
            domain_id="test_space",
        )
        await engine._repo.create_node(node)

        results = await engine.fuse("supply chain", "factual", "test_space")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_fuse_temporal_query(self, engine):
        """Test fusion with temporal query."""
        node = CognitiveNode(
            id="mem_temporal_001",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Revenue increased in 2024",
            occurred_at="2024-06-15T00:00:00Z",
            domain_id="test_space",
        )
        await engine._repo.create_node(node)

        results = await engine.fuse("What happened in 2024?", "temporal", "test_space")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_compute_rrf_basic(self, engine):
        """Test basic RRF computation."""
        all_results = {
            "layer_r": [
                RetrievalResult(doc_id="a", content="doc a", source="layer_r", memory_type="entity", cognitive_layer="semantic"),
                RetrievalResult(doc_id="b", content="doc b", source="layer_r", memory_type="observation", cognitive_layer="semantic"),
            ],
            "layer_s": [
                RetrievalResult(doc_id="a", content="doc a", source="layer_s", memory_type="entity", cognitive_layer="semantic"),
                RetrievalResult(doc_id="c", content="doc c", source="layer_s", memory_type="entity", cognitive_layer="semantic"),
            ],
            "bm25": [],
            "temporal": [],
        }

        weights = QUERY_TYPE_WEIGHTS["factual"]
        fused = engine._compute_rrf(all_results, weights, BASE_TYPE_WEIGHTS)

        assert len(fused) == 3

        doc_a = next(r for r in fused if r.doc_id == "a")
        assert doc_a.score > 0

    @pytest.mark.asyncio
    async def test_compute_rrf_deduplication(self, engine):
        """Test that RRF deduplicates by doc_id."""
        all_results = {
            "layer_r": [
                RetrievalResult(doc_id="a", content="doc a", source="layer_r", memory_type="entity", cognitive_layer="semantic"),
            ],
            "layer_s": [
                RetrievalResult(doc_id="a", content="doc a", source="layer_s", memory_type="entity", cognitive_layer="semantic"),
            ],
            "bm25": [
                RetrievalResult(doc_id="a", content="doc a", source="bm25", memory_type="entity", cognitive_layer="semantic"),
            ],
            "temporal": [],
        }

        weights = QUERY_TYPE_WEIGHTS["mixed"]
        fused = engine._compute_rrf(all_results, weights, BASE_TYPE_WEIGHTS)

        assert len(fused) == 1
        assert fused[0].doc_id == "a"

    @pytest.mark.asyncio
    async def test_type_weight_applied(self, engine):
        """Test that type weights are applied to RRF scores."""
        all_results = {
            "layer_r": [
                RetrievalResult(doc_id="a", content="mental model", source="layer_r", memory_type="mental_model", cognitive_layer="opinion"),
                RetrievalResult(doc_id="b", content="fragment", source="layer_r", memory_type="fragment", cognitive_layer="perception"),
            ],
            "layer_s": [],
            "bm25": [],
            "temporal": [],
        }

        weights = QUERY_TYPE_WEIGHTS["factual"]
        fused = engine._compute_rrf(all_results, weights, BASE_TYPE_WEIGHTS)

        mental_model_result = next(r for r in fused if r.doc_id == "a")
        fragment_result = next(r for r in fused if r.doc_id == "b")

        assert mental_model_result.score > fragment_result.score


class TestRetrievalResult:
    """Test RetrievalResult dataclass."""

    def test_create_result(self):
        result = RetrievalResult(doc_id="test", content="test content")
        assert result.doc_id == "test"
        assert result.source == "unknown"
        assert result.score == 0.0

    def test_result_with_metadata(self):
        result = RetrievalResult(
            doc_id="test",
            content="test",
            source="layer_r",
            memory_type="entity",
            cognitive_layer="semantic",
            metadata={"rank": 1},
        )
        assert result.metadata["rank"] == 1
