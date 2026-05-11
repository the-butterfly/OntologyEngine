"""Tests for cognitive engine repository."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveNodeConflictError,
    CognitiveNodeNotFoundError,
    DispositionProfileNotFoundError,
    InvalidBeliefTransitionError,
)
from ontology_engine.engine.cognitive.models import (
    CognitiveEdge,
    CognitiveNode,
    DispositionProfile,
)
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


class TestCognitiveRepository:
    """Test CognitiveRepository operations."""

    @pytest_asyncio.fixture
    async def repo(self, tmp_path):
        """Create an initialized repository for testing."""
        db_path = str(tmp_path / "test_cognitive_repo.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        yield repo
        await store.close()

    def _make_node(self, node_id: str = "mem_test_001", **kwargs) -> CognitiveNode:
        """Helper to create a test CognitiveNode."""
        return CognitiveNode(
            id=node_id,
            memory_type=kwargs.get("memory_type", "entity"),
            cognitive_layer=kwargs.get("cognitive_layer", "semantic"),
            content=kwargs.get("content", "Test memory content"),
            domain_id=kwargs.get("domain_id", "test_domain"),
            space_id=kwargs.get("space_id", "default"),
            **{k: v for k, v in kwargs.items() if k not in ("id", "memory_type", "cognitive_layer", "content", "domain_id", "space_id")},
        )

    @pytest.mark.asyncio
    async def test_create_and_get_node(self, repo):
        """Test creating and retrieving a cognitive node."""
        node = self._make_node()
        created = await repo.create_node(node)

        assert created.id == node.id
        assert created.created_at is not None
        assert created.updated_at is not None

        retrieved = await repo.get_node(node.id)
        assert retrieved.id == node.id
        assert retrieved.memory_type == "entity"
        assert retrieved.cognitive_layer == "semantic"
        assert retrieved.content == "Test memory content"

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, repo):
        """Test get_node raises error for non-existent node."""
        with pytest.raises(CognitiveNodeNotFoundError):
            await repo.get_node("nonexistent")

    @pytest.mark.asyncio
    async def test_update_node(self, repo):
        """Test updating a cognitive node."""
        node = self._make_node()
        await repo.create_node(node)

        node.content = "Updated content"
        updated = await repo.update_node(node, reason="Test update")

        assert updated.updated_at is not None
        retrieved = await repo.get_node(node.id)
        assert retrieved.content == "Updated content"
        assert len(retrieved.history) >= 1

    @pytest.mark.asyncio
    async def test_update_nonexistent_node(self, repo):
        """Test update raises error for non-existent node."""
        node = self._make_node("mem_nonexistent")
        with pytest.raises(CognitiveNodeNotFoundError):
            await repo.update_node(node)

    @pytest.mark.asyncio
    async def test_update_node_occ_success(self, repo):
        """Test update with matching expected_version succeeds."""
        node = self._make_node("mem_occ_ok")
        await repo.create_node(node)

        retrieved = await repo.get_node(node.id)
        version = retrieved.version if retrieved.version else len(retrieved.history or [])

        retrieved.content = "OCC updated content"
        updated = await repo.update_node(retrieved, expected_version=version)
        assert updated.content == "OCC updated content"

    @pytest.mark.asyncio
    async def test_update_node_occ_conflict(self, repo):
        """Test update with mismatched expected_version raises conflict."""
        node = self._make_node("mem_occ_conflict")
        await repo.create_node(node)

        node.content = "Stale update"
        with pytest.raises(CognitiveNodeConflictError):
            await repo.update_node(node, expected_version=999)

    @pytest.mark.asyncio
    async def test_delete_node(self, repo):
        """Test deleting a cognitive node."""
        node = self._make_node("mem_delete_test")
        await repo.create_node(node)

        await repo.delete_node(node.id)

        with pytest.raises(CognitiveNodeNotFoundError):
            await repo.get_node(node.id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_node(self, repo):
        """Test delete raises error for non-existent node."""
        with pytest.raises(CognitiveNodeNotFoundError):
            await repo.delete_node("nonexistent")

    @pytest.mark.asyncio
    async def test_query_nodes_by_type(self, repo):
        """Test querying nodes by memory_type."""
        await repo.create_node(self._make_node("mem_1", memory_type="entity"))
        await repo.create_node(self._make_node("mem_2", memory_type="observation"))
        await repo.create_node(self._make_node("mem_3", memory_type="entity"))

        results = await repo.query_nodes(memory_type="entity")
        assert len(results) == 2
        assert all(r.memory_type == "entity" for r in results)

    @pytest.mark.asyncio
    async def test_query_nodes_by_layer(self, repo):
        """Test querying nodes by cognitive_layer."""
        await repo.create_node(self._make_node("mem_1", cognitive_layer="semantic"))
        await repo.create_node(self._make_node("mem_2", cognitive_layer="opinion"))

        results = await repo.query_nodes(cognitive_layer="opinion")
        assert len(results) == 1
        assert results[0].cognitive_layer == "opinion"

    @pytest.mark.asyncio
    async def test_query_nodes_by_belief_status(self, repo):
        """Test querying nodes by belief_status."""
        await repo.create_node(self._make_node("mem_1", belief_status="accepted"))
        await repo.create_node(self._make_node("mem_2", belief_status="contradicted"))

        results = await repo.query_nodes(belief_status="contradicted")
        assert len(results) == 1
        assert results[0].belief_status == "contradicted"

    @pytest.mark.asyncio
    async def test_transition_belief_valid(self, repo):
        """Test valid belief status transition."""
        node = self._make_node("mem_belief", belief_status="accepted")
        await repo.create_node(node)

        updated = await repo.transition_belief(node.id, "contradicted", reason="New evidence")

        assert updated.belief_status == "contradicted"
        retrieved = await repo.get_node(node.id)
        assert retrieved.belief_status == "contradicted"

    @pytest.mark.asyncio
    async def test_transition_belief_invalid(self, repo):
        """Test invalid belief status transition."""
        node = self._make_node("mem_belief_inv", belief_status="contradicted")
        await repo.create_node(node)

        with pytest.raises(InvalidBeliefTransitionError):
            await repo.transition_belief(node.id, "superseded")

    @pytest.mark.asyncio
    async def test_transition_belief_invalid_status(self, repo):
        """Test transition to invalid belief status."""
        node = self._make_node("mem_belief_invalid")
        await repo.create_node(node)

        with pytest.raises(CognitiveError):
            await repo.transition_belief(node.id, "invalid_status")

    @pytest.mark.asyncio
    async def test_create_node_with_invalid_type(self, repo):
        """Test creating node with invalid memory_type."""
        node = self._make_node("mem_invalid_type", memory_type="invalid")
        with pytest.raises(CognitiveError):
            await repo.create_node(node)

    @pytest.mark.asyncio
    async def test_create_node_with_invalid_layer(self, repo):
        """Test creating node with invalid cognitive_layer."""
        node = self._make_node("mem_invalid_layer", cognitive_layer="invalid")
        with pytest.raises(CognitiveError):
            await repo.create_node(node)

    @pytest.mark.asyncio
    async def test_create_node_with_empty_content(self, repo):
        """Test creating node with empty content."""
        node = self._make_node("mem_empty_content", content="")
        with pytest.raises(CognitiveError):
            await repo.create_node(node)

    @pytest.mark.asyncio
    async def test_record_access(self, repo):
        """Test recording a node access."""
        node = self._make_node("mem_access")
        await repo.create_node(node)

        await repo.record_access(node.id)

        retrieved = await repo.get_node(node.id)
        assert len(retrieved.history) >= 1
        assert retrieved.history[-1]["action"] == "access"


class TestDispositionProfileRepository:
    """Test DispositionProfile repository operations."""

    @pytest_asyncio.fixture
    async def repo(self, tmp_path):
        """Create an initialized repository for testing."""
        db_path = str(tmp_path / "test_dispo_repo.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)
        yield repo
        await store.close()

    def _make_profile(self, profile_id: str = "profile_test_001", **kwargs) -> DispositionProfile:
        """Helper to create a test DispositionProfile."""
        return DispositionProfile(
            id=profile_id,
            scene=kwargs.get("scene", "test_scene"),
            skepticism=kwargs.get("skepticism", 0.5),
            empathy=kwargs.get("empathy", 0.5),
            risk_tolerance=kwargs.get("risk_tolerance", 0.5),
            domain_id=kwargs.get("domain_id", "test_domain"),
            **{k: v for k, v in kwargs.items() if k not in ("id", "scene", "skepticism", "empathy", "risk_tolerance", "domain_id")},
        )

    @pytest.mark.asyncio
    async def test_create_and_get_profile(self, repo):
        """Test creating and retrieving a disposition profile."""
        profile = self._make_profile(skepticism=0.8, empathy=0.6)
        created = await repo.create_profile(profile)

        assert created.id == profile.id
        assert created.skepticism == 0.8

        retrieved = await repo.get_profile(profile.id)
        assert retrieved.skepticism == 0.8
        assert retrieved.empathy == 0.6

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, repo):
        """Test get_profile raises error for non-existent profile."""
        with pytest.raises(DispositionProfileNotFoundError):
            await repo.get_profile("nonexistent")

    @pytest.mark.asyncio
    async def test_get_profile_by_scene(self, repo):
        """Test retrieving profile by scene."""
        profile = self._make_profile(scene="financial_analysis", skepticism=0.9)
        await repo.create_profile(profile)

        retrieved = await repo.get_profile_by_scene("financial_analysis")
        assert retrieved.scene == "financial_analysis"
        assert retrieved.skepticism == 0.9

    @pytest.mark.asyncio
    async def test_get_profile_by_scene_not_found(self, repo):
        """Test get_profile_by_scene raises error."""
        with pytest.raises(DispositionProfileNotFoundError):
            await repo.get_profile_by_scene("nonexistent_scene")

    @pytest.mark.asyncio
    async def test_compute_weights(self, repo):
        """Test computing dynamic weights from a profile."""
        profile = self._make_profile(skepticism=0.8, empathy=0.8, risk_tolerance=0.6)
        weights = await repo.compute_weights(profile)

        assert "mental_model" in weights
        assert "opinion" in weights
        assert "entity" in weights
        assert "observation" in weights
        assert "procedure" in weights

        assert weights["mental_model"] < 3.0
        assert weights["entity"] > 2.0
        assert weights["observation"] > 1.5


class TestCognitiveEdge:
    """Test CognitiveEdge model."""

    def test_create_edge(self):
        """Test creating a cognitive edge."""
        edge = CognitiveEdge(
            edge_type="SUPPORTS",
            from_id="mem_1",
            to_id="mem_2",
            properties={"strength": 0.8},
        )
        assert edge.edge_type == "SUPPORTS"
        assert edge.from_id == "mem_1"
        assert edge.to_id == "mem_2"
        assert edge.properties["strength"] == 0.8
        assert edge.created_at is None
