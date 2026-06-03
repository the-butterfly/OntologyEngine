"""Tests for consolidation engine."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.consolidation_engine import (
    ConsolidationEngine,
    group_by_tags,
)
from ontology_engine.engine.cognitive.consolidation_types import (
    HISTORY_MAX_ENTRIES,
    CreateAction,
    ConsolidationResult,
    DeleteAction,
    Fragment,
    UpdateAction,
)
from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore


class TestGroupByTags:
    """Test tag grouping for isolation."""

    def test_empty_fragments(self):
        result = group_by_tags([])
        assert result == {}

    def test_single_fragment(self):
        f = Fragment(id="f1", content="test", tags={"key": "a"})
        result = group_by_tags([f])
        assert len(result) == 1
        assert len(result['{"key": "a"}']) == 1

    def test_tags_sorted(self):
        f = Fragment(id="f1", content="test", tags={"key": "a"})
        result = group_by_tags([f])
        assert '{"key": "a"}' in result

    def test_different_tags_isolated(self):
        f1 = Fragment(id="f1", content="test1", tags={"key": "a"})
        f2 = Fragment(id="f2", content="test2", tags={"key": "b"})
        result = group_by_tags([f1, f2])
        assert len(result) == 2
        assert '{"key": "a"}' in result
        assert '{"key": "b"}' in result

    def test_same_tags_grouped(self):
        f1 = Fragment(id="f1", content="test1", tags={"key": "a"})
        f2 = Fragment(id="f2", content="test2", tags={"key": "a"})
        result = group_by_tags([f1, f2])
        assert len(result) == 1
        assert len(result['{"key": "a"}']) == 2

    def test_no_tags(self):
        f = Fragment(id="f1", content="test", tags={})
        result = group_by_tags([f])
        assert "" in result


class TestConsolidationEngine:
    """Test ConsolidationEngine operations."""

    @pytest_asyncio.fixture
    async def engine(self, tmp_path):
        """Create an initialized consolidation engine for testing."""
        db_path = str(tmp_path / "test_consolidation.ladybug")
        store = LadybugGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        engine = ConsolidationEngine(repository=repo)
        yield engine
        await store.close()

    @pytest.mark.asyncio
    async def test_execute_create(self, engine):
        """Test creating a new observation from fragments."""
        fragments = [
            Fragment(id="frag_1", content="Supply chain involves suppliers"),
            Fragment(id="frag_2", content="Manufacturers are part of supply chain"),
        ]

        action = CreateAction(
            text="Supply chain is a network of suppliers and manufacturers",
            memory_type="observation",
            cognitive_layer="semantic",
            source_fragments=fragments,
            confidence=0.8,
        )

        node_id = await engine.execute_create(action, "test_space")
        assert node_id.startswith("mem:observation:")

        node = await engine._repo.get_node(node_id)
        assert node.content == "Supply chain is a network of suppliers and manufacturers"
        assert node.memory_type == "observation"
        assert node.cognitive_layer == "semantic"
        assert len(node.source_fragment_ids) == 2
        assert len(node.history) == 1
        assert node.history[0]["change_reason"] == "consolidation"

    @pytest.mark.asyncio
    async def test_execute_update(self, engine):
        """Test updating an existing observation with new fragments."""
        existing_node = CognitiveNode(
            id="mem_obs_001",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Original observation",
            source_fragment_ids=["frag_old"],
        )
        await engine._repo.create_node(existing_node)

        new_fragments = [
            Fragment(id="frag_new_1", content="Additional evidence"),
        ]

        action = UpdateAction(
            target_id="mem_obs_001",
            updated_text="Original observation with additional evidence",
            new_source_fragments=new_fragments,
            confidence=0.7,
        )

        node_id = await engine.execute_update(action, "test_space")
        assert node_id == "mem_obs_001"

        updated = await engine._repo.get_node("mem_obs_001")
        assert "frag_new_1" in updated.source_fragment_ids
        assert "frag_old" in updated.source_fragment_ids
        assert len(updated.history) >= 1
        consolidation_entries = [h for h in updated.history if h.get("change_reason") == "consolidation"]
        assert len(consolidation_entries) >= 1

    @pytest.mark.asyncio
    async def test_execute_delete(self, engine):
        """Test superseding an existing observation."""
        existing_node = CognitiveNode(
            id="mem_obs_del",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Outdated observation",
            belief_status="accepted",
        )
        await engine._repo.create_node(existing_node)

        action = DeleteAction(
            target_id="mem_obs_del",
            replacement_id="mem_obs_new",
            reason="superseded_by_consolidation",
        )

        node_id = await engine.execute_delete(action, "test_space")
        assert node_id == "mem_obs_del"

        superseded = await engine._repo.get_node("mem_obs_del")
        assert superseded.belief_status == "superseded"

    @pytest.mark.asyncio
    async def test_rule_based_consolidation_create(self, engine):
        """Test rule-based consolidation creates observation when no existing."""
        fragments = [
            Fragment(id="frag_1", content="Test fragment 1", tags={"model": "observation"}),
            Fragment(id="frag_2", content="Test fragment 2", tags={"model": "observation"}),
        ]

        actions = engine._rule_based_consolidation(fragments, [])
        assert len(actions) == 1
        assert isinstance(actions[0], CreateAction)
        assert actions[0].memory_type == "observation"

    @pytest.mark.asyncio
    async def test_rule_based_consolidation_update(self, engine):
        """Test rule-based consolidation updates when existing nodes found."""
        fragments = [
            Fragment(id="frag_1", content="New evidence", tags={"model": "observation"}),
        ]

        existing = CognitiveNode(
            id="mem_existing",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Existing observation",
        )

        actions = engine._rule_based_consolidation(fragments, [existing])
        assert len(actions) == 1
        assert isinstance(actions[0], UpdateAction)
        assert actions[0].target_id == "mem_existing"

    @pytest.mark.asyncio
    async def test_history_max_entries(self, engine):
        """Test that history is truncated at HISTORY_MAX_ENTRIES."""
        existing_node = CognitiveNode(
            id="mem_history_max",
            memory_type="observation",
            cognitive_layer="semantic",
            content="Test",
            source_fragment_ids=["frag_0"],
            history=[{"action": "access", "i": i} for i in range(HISTORY_MAX_ENTRIES)],
        )
        await engine._repo.create_node(existing_node)

        action = UpdateAction(
            target_id="mem_history_max",
            updated_text="Updated",
            new_source_fragments=[Fragment(id="frag_new", content="new")],
        )

        await engine.execute_update(action, "test_space")

        updated = await engine._repo.get_node("mem_history_max")
        assert len(updated.history) <= HISTORY_MAX_ENTRIES + 2

    @pytest.mark.asyncio
    async def test_consolidation_result_merge(self):
        """Test ConsolidationResult merge."""
        r1 = ConsolidationResult(created=["a"], updated=["b"], errors=[{"e": 1}])
        r2 = ConsolidationResult(created=["c"], deleted=["d"], errors=[{"e": 2}])

        merged = r1.merge(r2)
        assert merged.created == ["a", "c"]
        assert merged.updated == ["b"]
        assert merged.deleted == ["d"]
        assert len(merged.errors) == 2

    @pytest.mark.asyncio
    async def test_maybe_trigger_consolidation_below_threshold(self, engine):
        """Test that consolidation is not triggered below threshold."""
        result = await engine.maybe_trigger_consolidation("empty_space", "write_async")
        assert result is False

    @pytest.mark.asyncio
    async def test_maybe_trigger_consolidation_manual(self, engine):
        """Test that manual trigger always runs."""
        result = await engine.maybe_trigger_consolidation("empty_space", "manual")
        assert result is True

    @pytest.mark.asyncio
    async def test_adaptive_batch_halving(self, engine):
        """Test adaptive batch halving with LLM failure."""
        call_count = 0

        async def failing_llm(fragments, existing):
            nonlocal call_count
            call_count += 1
            if len(fragments) > 1:
                raise RuntimeError("LLM context too long")
            return [CreateAction(
                text=fragments[0].content,
                source_fragments=fragments,
            )]

        engine_with_llm = ConsolidationEngine(
            repository=engine._repo,
            llm_consolidate_fn=failing_llm,
        )

        fragments = [
            Fragment(id=f"frag_{i}", content=f"Content {i}", tags={"model": "test"})
            for i in range(4)
        ]

        actions = await engine_with_llm._consolidate_batch_with_llm(fragments, [])
        assert call_count > 1
        assert len(actions) >= 1


class TestConsolidationResult:
    """Test ConsolidationResult dataclass."""

    def test_empty_result(self):
        result = ConsolidationResult()
        assert result.created == []
        assert result.updated == []
        assert result.deleted == []
        assert result.errors == []

    def test_merge_preserves_order(self):
        r1 = ConsolidationResult(created=["a", "b"])
        r2 = ConsolidationResult(created=["c"])
        merged = r1.merge(r2)
        assert merged.created == ["a", "b", "c"]
