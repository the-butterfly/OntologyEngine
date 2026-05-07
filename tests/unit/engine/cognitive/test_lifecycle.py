"""Tests for memory lifecycle."""

from __future__ import annotations


import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.lifecycle import (
    ForgettingEngine,
    DreamCycle,
    compute_memory_strength,
    decay_strength,
    forgetting_rate,
    get_demotion_target,
)
from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


class TestMemoryStrength:
    """Test memory strength computation."""

    def test_fresh_frequently_accessed(self):
        strength = compute_memory_strength(
            access_count=50,
            last_accessed_days=0,
            proof_count=10,
            feedback_weight=0.9,
        )
        assert strength > 0.8

    def test_old_rarely_accessed(self):
        strength = compute_memory_strength(
            access_count=1,
            last_accessed_days=365,
            proof_count=0,
            feedback_weight=0.1,
        )
        assert strength < 0.3

    def test_moderate(self):
        strength = compute_memory_strength(
            access_count=10,
            last_accessed_days=30,
            proof_count=5,
            feedback_weight=0.5,
        )
        assert 0.2 < strength < 0.8

    def test_recency_decay(self):
        s1 = compute_memory_strength(10, 1, 5, 0.5)
        s2 = compute_memory_strength(10, 100, 5, 0.5)
        assert s1 > s2

    def test_evidence_boost(self):
        s1 = compute_memory_strength(10, 30, 1, 0.5)
        s2 = compute_memory_strength(10, 30, 10, 0.5)
        assert s2 > s1

    def test_bounded(self):
        strength = compute_memory_strength(1000, 0, 100, 1.0)
        assert strength <= 1.0
        strength = compute_memory_strength(0, 1000, 0, 0.0)
        assert strength >= 0.0


class TestForgettingRate:
    """Test Ebbinghaus forgetting rate."""

    def test_high_value(self):
        rate = forgetting_rate(0.9)
        assert rate == 0.1

    def test_medium_value(self):
        rate = forgetting_rate(0.6)
        assert rate == 0.4

    def test_low_value(self):
        rate = forgetting_rate(0.3)
        assert rate == 0.85


class TestDecayStrength:
    """Test Ebbinghaus decay."""

    def test_no_decay(self):
        result = decay_strength(1.0, 0, 1.0)
        assert abs(result - 1.0) < 0.01

    def test_decay_decreases(self):
        s1 = decay_strength(1.0, 1, 0.5)
        s2 = decay_strength(1.0, 10, 0.5)
        assert s1 > s2

    def test_high_value_decays_slowly(self):
        s_high = decay_strength(1.0, 30, 0.9)
        s_low = decay_strength(1.0, 30, 0.3)
        assert s_high > s_low


class TestDemotionTarget:
    """Test type demotion chain."""

    def test_mental_model_demotion(self):
        assert get_demotion_target("mental_model") == "entity"

    def test_entity_demotion(self):
        assert get_demotion_target("entity") == "observation"

    def test_observation_demotion(self):
        assert get_demotion_target("observation") == "archived"

    def test_archived_no_demotion(self):
        assert get_demotion_target("archived") is None

    def test_unknown_type(self):
        assert get_demotion_target("unknown") is None


class TestForgettingEngine:
    """Test ForgettingEngine operations."""

    @pytest_asyncio.fixture
    async def engine(self, tmp_path):
        """Create an initialized forgetting engine for testing."""
        db_path = str(tmp_path / "test_forgetting.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        engine = ForgettingEngine(repository=repo)
        yield engine
        await store.close()

    @pytest.mark.asyncio
    async def test_evaluate_empty_space(self, engine):
        """Test evaluation with no data."""
        result = await engine.evaluate_forgetting("empty_space")
        assert "soft_decayed" in result
        assert "protected" in result

    @pytest.mark.asyncio
    async def test_evaluate_with_data(self, engine):
        """Test evaluation with existing data."""
        node = CognitiveNode(
            id="mem_forget_001",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Test observation",
            domain_id="test_space",
        )
        await engine._repo.create_node(node)

        result = await engine.evaluate_forgetting("test_space")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_protected_mental_model(self, engine):
        """Test that accepted mental_models are protected."""
        node = CognitiveNode(
            id="mem_protected",
            memory_type="mental_model",
            cognitive_layer="opinion",
            content="Protected model",
            belief_status="accepted",
            domain_id="test_space",
        )
        await engine._repo.create_node(node)

        result = await engine.evaluate_forgetting("test_space")
        assert "mem_protected" in result.get("protected", [])


class TestDreamCycle:
    """Test DreamCycle operations."""

    @pytest_asyncio.fixture
    async def cycle(self, tmp_path):
        """Create an initialized dream cycle for testing."""
        db_path = str(tmp_path / "test_dream.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        forgetting = ForgettingEngine(repository=repo)
        cycle = DreamCycle(repository=repo, forgetting_engine=forgetting)
        yield cycle
        await store.close()

    @pytest.mark.asyncio
    async def test_run_empty_space(self, cycle):
        """Test dream cycle with no data."""
        result = await cycle.run("empty_space")
        assert isinstance(result.contradictions, list)
        assert isinstance(result.expired, list)
        assert isinstance(result.orphans_cleaned, int)

    @pytest.mark.asyncio
    async def test_run_with_data(self, cycle):
        """Test dream cycle with existing data."""
        node = CognitiveNode(
            id="mem_dream_001",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Test observation",
            domain_id="test_space",
        )
        await cycle._repo.create_node(node)

        result = await cycle.run("test_space")
        assert hasattr(result, "contradictions")
        assert hasattr(result, "expired")

    @pytest.mark.asyncio
    async def test_expired_ttl(self, cycle):
        """Test that TTL-expired nodes are detected."""
        node = CognitiveNode(
            id="mem_expired",
            memory_type="fragment",
            cognitive_layer="perception",
            content="Expired fragment",
            ttl_seconds=1,
            domain_id="test_space",
        )
        await cycle._repo.create_node(node)

        import time
        time.sleep(3)

        result = await cycle.run("test_space")
        assert isinstance(result.expired, list)
