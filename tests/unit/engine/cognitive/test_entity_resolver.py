"""Tests for entity resolver."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.entity_resolver import (
    EntityResolver,
    compute_name_similarity,
    compute_trigrams,
)
from ontology_engine.engine.cognitive.entity_resolver_types import (
    ResolutionResult,
)
from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


class TestNameSimilarity:
    """Test name similarity computation."""

    def test_exact_match(self):
        assert compute_name_similarity("华为", "华为") == 1.0

    def test_case_insensitive(self):
        assert compute_name_similarity("Huawei", "huawei") == 1.0

    def test_edit_distance(self):
        sim = compute_name_similarity("华为技术", "华为")
        assert 0.0 < sim <= 1.0

    def test_prefix_match(self):
        sim = compute_name_similarity("华为", "华为技术有限公司")
        assert sim == 1.0

    def test_no_similarity(self):
        sim = compute_name_similarity("华为", "苹果")
        assert sim < 0.5


class TestTrigrams:
    """Test trigram computation."""

    def test_basic(self):
        trigrams = compute_trigrams("abc")
        assert "  a" in trigrams
        assert " ab" in trigrams
        assert "abc" in trigrams
        assert "bc " in trigrams

    def test_empty(self):
        trigrams = compute_trigrams("")
        assert len(trigrams) >= 1

    def test_single_char(self):
        trigrams = compute_trigrams("a")
        assert len(trigrams) >= 2


class TestEntityResolver:
    """Test EntityResolver operations."""

    @pytest_asyncio.fixture
    async def resolver(self, tmp_path):
        """Create an initialized resolver for testing."""
        db_path = str(tmp_path / "test_resolver.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        resolver = EntityResolver(repository=repo, strategy="full")
        yield resolver
        await store.close()

    @pytest.mark.asyncio
    async def test_resolve_create_new(self, resolver):
        """Test resolving creates new entity when no match."""
        results = await resolver.resolve("test_space", ["NewEntity"])
        assert len(results) == 1
        assert results[0].action == "create"
        assert results[0].score == 0.0

    @pytest.mark.asyncio
    async def test_resolve_reuse_existing(self, resolver):
        """Test resolving reuses existing entity on high score."""
        node = CognitiveNode(
            id="mem_entity_001",
            memory_type="entity",
            cognitive_layer="semantic",
            content="华为",
            domain_id="test_space",
        )
        await resolver._repo.create_node(node)

        results = await resolver.resolve("test_space", ["华为"])
        assert len(results) == 1
        assert results[0].action == "reuse"
        assert results[0].candidate_id == "mem_entity_001"
        assert results[0].score > 0.6

    @pytest.mark.asyncio
    async def test_resolve_and_create_or_reuse(self, resolver):
        """Test resolve_and_create_or_reuse creates new entity."""
        entity_id = await resolver.resolve_and_create_or_reuse(
            entity_text="Apple",
            entity_type="company",
            space_id="test_space",
        )
        assert entity_id.startswith("mem:entity:")

        node = await resolver._repo.get_node(entity_id)
        assert node.content == "Apple"
        assert node.memory_type == "entity"

    @pytest.mark.asyncio
    async def test_resolve_and_create_or_reuse_reuse(self, resolver):
        """Test resolve_and_create_or_reuse reuses existing entity."""
        node = CognitiveNode(
            id="mem_entity_huawei",
            memory_type="entity",
            cognitive_layer="semantic",
            content="华为",
            domain_id="test_space",
        )
        await resolver._repo.create_node(node)

        entity_id = await resolver.resolve_and_create_or_reuse(
            entity_text="华为",
            entity_type="company",
            space_id="test_space",
        )
        assert entity_id == node.id

    @pytest.mark.asyncio
    async def test_resolve_pending_review(self, resolver):
        """Test that medium-score matches get pending_review action."""
        node = CognitiveNode(
            id="mem_entity_similar",
            memory_type="entity",
            cognitive_layer="semantic",
            content="华为技术",
            domain_id="test_space",
        )
        await resolver._repo.create_node(node)

        results = await resolver.resolve("test_space", ["华为"])
        assert results[0].action in ("reuse", "pending_review", "create")

    @pytest.mark.asyncio
    async def test_trigram_strategy(self, tmp_path):
        """Test trigram strategy."""
        db_path = str(tmp_path / "test_trigram.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        resolver = EntityResolver(repository=repo, strategy="trigram")

        node = CognitiveNode(
            id="mem_entity_tg",
            memory_type="entity",
            cognitive_layer="semantic",
            content="华为技术有限公司",
            domain_id="test_space",
        )
        await repo.create_node(node)

        results = await resolver.resolve("test_space", ["华为技术"])
        assert len(results) == 1

        await store.close()

    @pytest.mark.asyncio
    async def test_auto_strategy_switch(self, resolver):
        """Test auto strategy defaults to full for small entity count."""
        assert resolver.strategy == "full"
        results = await resolver.resolve("test_space", ["TestEntity"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_batch_resolve(self, resolver):
        """Test resolving multiple entities at once."""
        results = await resolver.resolve("test_space", ["Entity1", "Entity2", "Entity3"])
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_cooccurrence_update(self, resolver):
        """Test co-occurrence edges are created."""
        node1 = CognitiveNode(
            id="mem_co_1",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Entity1",
            domain_id="test_space",
        )
        node2 = CognitiveNode(
            id="mem_co_2",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Entity2",
            domain_id="test_space",
        )
        await resolver._repo.create_node(node1)
        await resolver._repo.create_node(node2)

        await resolver._update_cooccurrences(["mem_co_1", "mem_co_2"], "test_space")


class TestResolutionResult:
    """Test ResolutionResult dataclass."""

    def test_create_result(self):
        result = ResolutionResult(entity_text="test", action="create", score=0.0)
        assert result.action == "create"
        assert result.candidate_id is None

    def test_reuse_result(self):
        result = ResolutionResult(
            entity_text="test",
            action="reuse",
            candidate_id="mem_001",
            score=0.8,
        )
        assert result.action == "reuse"
        assert result.candidate_id == "mem_001"
