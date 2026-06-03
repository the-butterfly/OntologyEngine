"""Tests for reflect agent."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.models import CognitiveNode, DispositionProfile
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent, HallucinationError
from ontology_engine.engine.cognitive.reflect_types import (
    ContradictionReport,
    Insight,
    MentalModelUpdate,
    ReflectResult,
)
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore


class TestReflectTypes:
    """Test reflect type dataclasses."""

    def test_insight(self):
        i = Insight(text="test insight", confidence=0.8, evidence_ids=["id1"])
        assert i.text == "test insight"
        assert i.confidence == 0.8

    def test_contradiction_report(self):
        cr = ContradictionReport(
            node_ids=["id1", "id2"],
            contradiction_type="value_conflict",
            suggested_resolution="Review both",
        )
        assert len(cr.node_ids) == 2

    def test_mental_model_update(self):
        mu = MentalModelUpdate(model_id="mm1", update_type="refine")
        assert mu.model_id == "mm1"

    def test_reflect_result(self):
        rr = ReflectResult()
        assert rr.insights == []
        assert rr.contradictions == []


class TestReflectAgent:
    """Test ReflectAgent operations."""

    @pytest_asyncio.fixture
    async def agent(self, tmp_path):
        """Create an initialized reflect agent for testing."""
        db_path = str(tmp_path / "test_reflect.ladybug")
        store = LadybugGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        rrf = RRFFusionEngine(repository=repo)
        router = QueryRouter(rrf_engine=rrf, repository=repo)
        agent = ReflectAgent(repository=repo, query_router=router)
        yield agent
        await store.close()

    @pytest.mark.asyncio
    async def test_reflect_empty_space(self, agent):
        """Test reflection with no data."""
        result = await agent.reflect("test query", "empty_space")
        assert isinstance(result, ReflectResult)
        assert result.insights == []
        assert result.contradictions == []

    @pytest.mark.asyncio
    async def test_reflect_with_data(self, agent):
        """Test reflection with existing data."""
        node = CognitiveNode(
            id="mem_reflect_001",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Supply chain involves suppliers",
            domain_id="test_space",
        )
        await agent._repo.create_node(node)

        result = await agent.reflect("supply chain", "test_space")
        assert isinstance(result, ReflectResult)

    @pytest.mark.asyncio
    async def test_reflect_with_disposition(self, agent):
        """Test reflection with DispositionProfile."""
        profile = DispositionProfile(
            id="profile_reflect",
            scene="audit",
            skepticism=0.9,
        )

        result = await agent.reflect("test query", "test_space", disposition=profile)
        assert isinstance(result, ReflectResult)

    @pytest.mark.asyncio
    async def test_hallucination_validation(self, agent):
        """Test hallucination validation catches invalid IDs."""
        result = ReflectResult(
            insights=[Insight(text="test", evidence_ids=["fake_id"])],
        )

        with pytest.raises(HallucinationError):
            agent._validate_result(result, {"real_id"})

    @pytest.mark.asyncio
    async def test_hallucination_validation_passes(self, agent):
        """Test hallucination validation passes for valid IDs."""
        result = ReflectResult(
            insights=[Insight(text="test", evidence_ids=["real_id"])],
        )

        agent._validate_result(result, {"real_id"})

    @pytest.mark.asyncio
    async def test_build_system_prompt(self, agent):
        """Test system prompt building."""
        prompt = agent.build_system_prompt("test query", "test_space", None)
        assert "test_space" in prompt

    @pytest.mark.asyncio
    async def test_build_system_prompt_with_disposition(self, agent):
        """Test system prompt with skeptical disposition."""
        profile = DispositionProfile(
            id="profile_skeptic",
            scene="audit",
            skepticism=0.9,
        )
        prompt = agent.build_system_prompt("test query", "test_space", profile)
        assert "skeptical" in prompt.lower() or "contradiction" in prompt.lower()

    @pytest.mark.asyncio
    async def test_max_iterations(self, agent):
        """Test that reflection respects max_iterations."""
        result = await agent.reflect("test query", "test_space", max_iterations=2)
        assert isinstance(result, ReflectResult)

    @pytest.mark.asyncio
    async def test_consolidation_trigger(self, agent):
        """Test that reflection triggers consolidation for many fragments."""
        for i in range(6):
            node = CognitiveNode(
                id=f"mem_frag_{i}",
                memory_type="fragment",
                cognitive_layer="perception",
                content=f"Fragment {i}",
                domain_id="test_space",
            )
            await agent._repo.create_node(node)

        result = await agent.reflect("test query", "test_space")
        assert len(result.consolidation_requests) > 0
