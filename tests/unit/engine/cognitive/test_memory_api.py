"""Tests for memory API."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveErrorCode,
    InvalidMemoryTypeError,
    InvalidVisibilityError,
)
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI, ReflectionJobStore
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.reflect_types import ReflectionPhase, ReflectionStatus
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


@pytest_asyncio.fixture
async def api(tmp_path):
    """Create an initialized MemoryAPI for testing."""
    db_path = str(tmp_path / "test_memory_api.kuzu")
    store = KuzuGraphStore()
    await store.initialize(db_path)
    repo = CognitiveRepository(store)
    consolidation = ConsolidationEngine(repository=repo)
    resolver = EntityResolver(repository=repo)
    rrf = RRFFusionEngine(repository=repo)
    router = QueryRouter(rrf_engine=rrf, repository=repo)
    reflect = ReflectAgent(repository=repo, query_router=router)
    forgetting = ForgettingEngine(repository=repo)
    dream = DreamCycle(repository=repo, forgetting_engine=forgetting)
    correction = CorrectionPropagation(repository=repo)
    memory_api = MemoryAPI(
        repository=repo,
        consolidation_engine=consolidation,
        entity_resolver=resolver,
        query_router=router,
        reflect_agent=reflect,
        forgetting_engine=forgetting,
        dream_cycle=dream,
        correction_propagation=correction,
    )
    yield memory_api
    await store.close()


class TestMemoryAPI:
    """Test MemoryAPI three-operation cognitive API."""

    @pytest.mark.asyncio
    async def test_remember_l1(self, api):
        """Test L1 remember with minimal args."""
        result = await api.remember("Alice works at Google", "test_space")
        assert result["success"] is True
        assert "memory_id" in result["data"]
        assert result["data"]["memory_type"] == "fragment"
        assert result["data"]["visibility"] == "shared"

    @pytest.mark.asyncio
    async def test_remember_l2(self, api):
        """Test L2 remember with tags and type."""
        result = await api.remember(
            "Risk score is 85",
            "test_space",
            tags={"domain": "risk", "source": "report"},
            memory_type="observation",
        )
        assert result["success"] is True
        assert result["data"]["memory_type"] == "observation"

    @pytest.mark.asyncio
    async def test_remember_empty_content(self, api):
        """Test remember with empty content raises error."""
        with pytest.raises(CognitiveError) as exc_info:
            await api.remember("", "test_space")
        assert exc_info.value.code == CognitiveErrorCode.EMPTY_INPUT

    @pytest.mark.asyncio
    async def test_remember_auto_consolidate(self, api):
        """Test remember with auto_consolidate."""
        result = await api.remember(
            "Test content",
            "test_space",
            auto_consolidate=True,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_remember_invalid_memory_type(self, api):
        """Test remember with invalid memory_type raises InvalidMemoryTypeError."""
        with pytest.raises(InvalidMemoryTypeError) as exc_info:
            await api.remember("test", "test_space", memory_type="invalid_type")
        assert exc_info.value.code == CognitiveErrorCode.INVALID_MEMORY_TYPE

    @pytest.mark.asyncio
    async def test_recall_l1(self, api):
        """Test L1 recall with minimal args."""
        await api.remember("Supply chain involves suppliers", "test_space")

        result = await api.recall("supply chain", "test_space")
        assert result["success"] is True
        assert "results" in result["data"]

    @pytest.mark.asyncio
    async def test_recall_with_type_filter(self, api):
        """Test recall with memory_type filter."""
        await api.remember("Test entity", "test_space", memory_type="entity")

        result = await api.recall("test", "test_space", memory_type="entity")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_recall_empty_query(self, api):
        """Test recall with empty query raises error."""
        with pytest.raises(CognitiveError) as exc_info:
            await api.recall("", "test_space")
        assert exc_info.value.code == CognitiveErrorCode.EMPTY_INPUT

    @pytest.mark.asyncio
    async def test_recall_with_evidence(self, api):
        """Test recall with evidence chain expansion."""
        await api.remember("Test content", "test_space")

        result = await api.recall(
            "test",
            "test_space",
            include_evidence=True,
            evidence_depth=1,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_reflect_sync(self, api):
        """Test synchronous reflect."""
        result = await api.reflect("test query", "test_space", async_mode=False)
        assert result["success"] is True
        assert "insights" in result["data"]
        assert "contradictions" in result["data"]

    @pytest.mark.asyncio
    async def test_reflect_async(self, api):
        """Test async reflect returns reflection_id."""
        result = await api.reflect("test query", "test_space", async_mode=True)
        assert result["success"] is True
        assert "reflection_id" in result["data"]
        assert result["data"]["status"] in ("pending", "in_progress")

    @pytest.mark.asyncio
    async def test_reflect_empty_query(self, api):
        """Test reflect with empty query raises error."""
        with pytest.raises(CognitiveError) as exc_info:
            await api.reflect("", "test_space")
        assert exc_info.value.code == CognitiveErrorCode.EMPTY_INPUT

    @pytest.mark.asyncio
    async def test_reflect_with_data(self, api):
        """Test reflect with existing data."""
        await api.remember("Company A has high risk", "test_space")
        await api.remember("Company A debt ratio is 0.75", "test_space")

        result = await api.reflect("Company A risk", "test_space", async_mode=False)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_remember_deduplication(self, api):
        """Test that same content gets same memory_id."""
        r1 = await api.remember("Same content", "test_space")
        r2 = await api.remember("Same content", "test_space")
        assert r1["data"]["memory_id"] == r2["data"]["memory_id"]

    @pytest.mark.asyncio
    async def test_remember_with_visibility(self, api):
        """Test remember with explicit visibility."""
        result = await api.remember(
            "Private note",
            "test_space",
            visibility="private",
            created_by="user_001",
        )
        assert result["success"] is True
        assert result["data"]["visibility"] == "private"

    @pytest.mark.asyncio
    async def test_remember_invalid_visibility(self, api):
        """Test remember with invalid visibility raises error."""
        with pytest.raises(InvalidVisibilityError) as exc_info:
            await api.remember("test", "test_space", visibility="invalid")
        assert exc_info.value.code == CognitiveErrorCode.INVALID_VISIBILITY

    @pytest.mark.asyncio
    async def test_recall_with_user_id_visibility_filter(self, api):
        """Test recall with user_id filters private memories."""
        await api.remember("Public info", "test_space", visibility="public")
        await api.remember(
            "Private note",
            "test_space",
            visibility="private",
            created_by="user_001",
        )
        await api.remember(
            "Other private",
            "test_space",
            visibility="private",
            created_by="user_002",
        )

        result = await api.recall("info", "test_space", memory_type="fragment", user_id="user_001")
        assert result["success"] is True
        for r in result["data"]["results"]:
            if r.get("visibility") == "private":
                assert r.get("created_by") == "user_001"

    @pytest.mark.asyncio
    async def test_get_reflection_status(self, api):
        """Test get_reflection_status for async reflect."""
        result = await api.reflect("test query", "test_space", async_mode=True)
        reflection_id = result["data"]["reflection_id"]

        await asyncio.sleep(0.1)

        status = await api.get_reflection_status(reflection_id)
        assert status["success"] is True
        assert status["data"]["reflection_id"] == reflection_id
        assert status["data"]["status"] in ("pending", "in_progress", "completed")

    @pytest.mark.asyncio
    async def test_get_reflection_status_not_found(self, api):
        """Test get_reflection_status with invalid ID raises error."""
        with pytest.raises(CognitiveError):
            await api.get_reflection_status("nonexistent_id")


class TestMemoryAPIHelpers:
    """Test MemoryAPI helper methods."""

    def test_generate_memory_id(self, api):
        id1 = api._generate_memory_id("test", "space1", "fragment")
        id2 = api._generate_memory_id("test", "space1", "fragment")
        id3 = api._generate_memory_id("test", "space2", "fragment")
        id4 = api._generate_memory_id("test", "space1", "entity")
        assert id1 == id2
        assert id1 != id3
        assert "mem:fragment:space1:" in id1
        assert "mem:entity:space1:" in id4
        assert id1 != id4

    def test_infer_cognitive_layer(self):
        assert MemoryAPI._infer_cognitive_layer("mental_model") == "opinion"
        assert MemoryAPI._infer_cognitive_layer("entity") == "semantic"
        assert MemoryAPI._infer_cognitive_layer("observation") == "opinion"
        assert MemoryAPI._infer_cognitive_layer("procedure") == "procedure"
        assert MemoryAPI._infer_cognitive_layer("fragment") == "perception"
        assert MemoryAPI._infer_cognitive_layer("unknown") == "perception"

    def test_determine_visibility(self):
        assert MemoryAPI._determine_visibility("test", "entity") == "shared"
        assert MemoryAPI._determine_visibility("test", "rule") == "shared"
        assert MemoryAPI._determine_visibility("test", "mental_model") == "shared"
        assert MemoryAPI._determine_visibility("test", "episode", "user_input") == "private"
        assert MemoryAPI._determine_visibility("test", "fragment") == "shared"
        assert MemoryAPI._determine_visibility("test", "episode") == "shared"

    def test_determine_visibility_with_pii(self):
        assert MemoryAPI._determine_visibility("Call me at 555-123-4567", "fragment") == "private"
        assert MemoryAPI._determine_visibility("My SSN is 123-45-6789", "fragment") == "private"
        assert MemoryAPI._determine_visibility("Email me at user@example.com", "fragment") == "private"
        assert MemoryAPI._determine_visibility("passport number ABC123", "fragment") == "private"

    def test_contains_personal_info(self):
        assert MemoryAPI._contains_personal_info("Phone: 555-123-4567") is True
        assert MemoryAPI._contains_personal_info("SSN: 123-45-6789") is True
        assert MemoryAPI._contains_personal_info("Email: test@example.com") is True
        assert MemoryAPI._contains_personal_info("passport no: XYZ") is True
        assert MemoryAPI._contains_personal_info("social security number") is True
        assert MemoryAPI._contains_personal_info("Normal text without PII") is False


class TestReflectionJobStore:

    @pytest.mark.asyncio
    async def test_create_job(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")
        assert job.reflection_id.startswith("refl:")
        assert job.query == "test query"
        assert job.space_id == "test_space"
        assert job.progress is not None
        assert job.progress.status == ReflectionStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_job(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")
        retrieved = await store.get_job(job.reflection_id)
        assert retrieved is not None
        assert retrieved.reflection_id == job.reflection_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        store = ReflectionJobStore()
        assert await store.get_job("nonexistent") is None

    @pytest.mark.asyncio
    async def test_update_progress(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")

        await store.update_progress(job.reflection_id, ReflectionPhase.RETRIEVAL.value, "in_progress")
        assert job.progress.status == ReflectionStatus.IN_PROGRESS

        await store.update_progress(job.reflection_id, ReflectionPhase.RETRIEVAL.value, "completed")
        for phase in ReflectionPhase:
            if phase != ReflectionPhase.RETRIEVAL:
                await store.update_progress(job.reflection_id, phase.value, "completed")
        assert job.progress.status == ReflectionStatus.COMPLETED
        assert job.progress.completed_at is not None

    @pytest.mark.asyncio
    async def test_set_partial_results(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")

        await store.set_partial_results(job.reflection_id, "insights", [{"text": "test"}])
        assert job.progress.partial_results["insights"] == [{"text": "test"}]

    @pytest.mark.asyncio
    async def test_set_error(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")

        await store.set_error(job.reflection_id, "Something went wrong")
        assert job.progress.status == ReflectionStatus.FAILED
        assert job.progress.error == "Something went wrong"


class TestErrorCodes:
    """Test error code system."""

    def test_cognitive_error_with_code(self):
        err = CognitiveError("test error", CognitiveErrorCode.EMPTY_INPUT)
        assert err.code == CognitiveErrorCode.EMPTY_INPUT
        assert err.http_status == 422

    def test_cognitive_error_to_dict(self):
        err = CognitiveError("test error", CognitiveErrorCode.EMPTY_INPUT)
        d = err.to_dict()
        assert d["error_code"] == "EMPTY_INPUT"
        assert d["message"] == "test error"
        assert d["http_status"] == 422

    def test_cognitive_error_without_code(self):
        err = CognitiveError("test error")
        assert err.code is None
        assert err.http_status == 500

    def test_invalid_memory_type_error(self):
        err = InvalidMemoryTypeError("bad_type", {"entity", "fragment"})
        assert err.code == CognitiveErrorCode.INVALID_MEMORY_TYPE
        assert "bad_type" in str(err)

    def test_invalid_visibility_error(self):
        err = InvalidVisibilityError("bad_vis", {"private", "shared", "public"})
        assert err.code == CognitiveErrorCode.INVALID_VISIBILITY
        assert "bad_vis" in str(err)

    def test_memory_not_ready_error(self):
        from ontology_engine.engine.cognitive.errors import MemoryNotReadyError
        err = MemoryNotReadyError()
        assert err.code == CognitiveErrorCode.MEMORY_NOT_READY
        assert err.http_status == 503

    def test_consolidation_in_progress_error(self):
        from ontology_engine.engine.cognitive.errors import ConsolidationInProgressError
        err = ConsolidationInProgressError()
        assert err.code == CognitiveErrorCode.CONSOLIDATION_IN_PROGRESS
        assert err.http_status == 409

    def test_protected_memory_error(self):
        from ontology_engine.engine.cognitive.errors import ProtectedMemoryError
        err = ProtectedMemoryError()
        assert err.code == CognitiveErrorCode.PROTECTED_MEMORY
        assert err.http_status == 403

    def test_reflect_timeout_error(self):
        from ontology_engine.engine.cognitive.errors import ReflectTimeoutError
        err = ReflectTimeoutError()
        assert err.code == CognitiveErrorCode.REFLECT_TIMEOUT
        assert err.http_status == 504

    def test_memory_stale_error(self):
        from ontology_engine.engine.cognitive.errors import MemoryStaleError
        err = MemoryStaleError()
        assert err.code == CognitiveErrorCode.MEMORY_STALE
        assert err.http_status == 200

    def test_node_not_found_error(self):
        from ontology_engine.engine.cognitive.errors import CognitiveNodeNotFoundError
        err = CognitiveNodeNotFoundError("node_123")
        assert err.code == CognitiveErrorCode.NODE_NOT_FOUND
        assert err.http_status == 404


class TestRecallNewParameters:
    """Test recall with new L2/L3 parameters."""

    @pytest.mark.asyncio
    async def test_recall_with_min_confidence(self, api):
        """Test recall with min_confidence filter."""
        await api.remember("High confidence fact", "test_space", confidence=0.9)
        await api.remember("Low confidence guess", "test_space", confidence=0.2)

        result = await api.recall("fact", "test_space", min_confidence=0.5)
        assert result["success"] is True
        for r in result["data"]["results"]:
            assert r.get("confidence", 1.0) >= 0.5

    @pytest.mark.asyncio
    async def test_recall_min_confidence_default_filters_low(self, api):
        """Test recall default min_confidence=0.5 filters low confidence."""
        await api.remember("Low confidence", "test_space", confidence=0.1)

        result = await api.recall("low confidence", "test_space")
        assert result["success"] is True
        for r in result["data"]["results"]:
            assert r.get("confidence", 1.0) >= 0.5

    @pytest.mark.asyncio
    async def test_recall_min_confidence_zero_returns_all(self, api):
        """Test recall with min_confidence=0 returns all results."""
        await api.remember("Low confidence", "test_space", confidence=0.1)

        result = await api.recall("low confidence", "test_space", min_confidence=0.0)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_recall_with_token_budget(self, api):
        """Test recall with token_budget truncation."""
        for i in range(5):
            await api.remember(f"Memory item {i} " + "x" * 100, "test_space")

        result = await api.recall("memory", "test_space", token_budget=50)
        assert result["success"] is True
        assert len(result["data"]["results"]) <= 5

    @pytest.mark.asyncio
    async def test_recall_returns_strength_and_confidence(self, api):
        """Test recall results include strength and confidence fields."""
        await api.remember("Test content for strength", "test_space")

        result = await api.recall("test", "test_space")
        assert result["success"] is True
        assert "total_tokens" in result["data"]
        if result["data"]["results"]:
            r = result["data"]["results"][0]
            assert "strength" in r
            assert "confidence" in r
            assert "strength_breakdown" in r

    @pytest.mark.asyncio
    async def test_recall_returns_query_type(self, api):
        """Test recall returns query_type field."""
        await api.remember("Test content", "test_space")

        result = await api.recall("test", "test_space")
        assert result["success"] is True
        assert "query_type" in result["data"]

        result_typed = await api.recall("test", "test_space", memory_type="fragment")
        assert result_typed["success"] is True
        assert result_typed["data"]["query_type"] == "type_filter"


class TestReflectNewParameters:
    """Test reflect with new L3 parameters."""

    @pytest.mark.asyncio
    async def test_reflect_skip_consolidation(self, api):
        """Test reflect with skip_consolidation=True."""
        result = await api.reflect(
            "test query", "test_space",
            async_mode=False,
            skip_consolidation=True,
        )
        assert result["success"] is True
        assert result["data"]["consolidation"] is None

    @pytest.mark.asyncio
    async def test_reflect_skip_forgetting(self, api):
        """Test reflect with skip_forgetting=True."""
        result = await api.reflect(
            "test query", "test_space",
            async_mode=False,
            skip_forgetting=True,
        )
        assert result["success"] is True
        assert result["data"]["forgetting"] is None

    @pytest.mark.asyncio
    async def test_reflect_skip_correction_propagation(self, api):
        """Test reflect with skip_correction_propagation=True."""
        result = await api.reflect(
            "test query", "test_space",
            async_mode=False,
            skip_correction_propagation=True,
        )
        assert result["success"] is True
        assert result["data"]["correction_propagation"] is None

    @pytest.mark.asyncio
    async def test_reflect_with_cascade_depth(self, api):
        """Test reflect with cascade_depth parameter."""
        result = await api.reflect(
            "test query", "test_space",
            async_mode=False,
            cascade_depth=5,
        )
        assert result["success"] is True


class TestRememberWithConfidence:
    """Test remember with confidence parameter."""

    @pytest.mark.asyncio
    async def test_remember_with_confidence(self, api):
        """Test remember with explicit confidence."""
        result = await api.remember(
            "High confidence fact",
            "test_space",
            confidence=0.95,
        )
        assert result["success"] is True

        recall_result = await api.recall("high confidence", "test_space")
        if recall_result["data"]["results"]:
            confidences = [r["confidence"] for r in recall_result["data"]["results"]]
            assert 0.95 in confidences


class TestComputeStrength:
    """Test _compute_strength static method."""

    def test_compute_strength_default_node(self):
        from ontology_engine.engine.cognitive.models import CognitiveNode

        node = CognitiveNode(
            id="mem:fragment:test",
            memory_type="fragment",
            cognitive_layer="perception",
            content="test content",
        )
        result = MemoryAPI._compute_strength(node)
        assert "value" in result
        assert "breakdown" in result
        assert 0.0 <= result["value"] <= 1.0
        assert "recency" in result["breakdown"]
        assert "evidence" in result["breakdown"]
        assert "feedback" in result["breakdown"]
        assert "access_frequency" in result["breakdown"]

    def test_compute_strength_with_access_count(self):
        from ontology_engine.engine.cognitive.models import CognitiveNode

        node = CognitiveNode(
            id="mem:fragment:test",
            memory_type="fragment",
            cognitive_layer="perception",
            content="test content",
            access_count=50,
            feedback_weight=0.8,
        )
        result = MemoryAPI._compute_strength(node)
        assert result["breakdown"]["access_frequency"] == 1.0
        assert result["breakdown"]["feedback"] == 0.8


class TestCorrectionPropagation:
    """Test CorrectionPropagation engine."""

    @pytest.mark.asyncio
    async def test_propagation_no_trigger_belief(self, api):
        """Test propagation does not trigger for accepted belief."""
        result = await api._correction_propagation.propagate("nonexistent_node")
        assert result.propagated_count == 0

    @pytest.mark.asyncio
    async def test_propagation_result_structure(self):
        from ontology_engine.engine.cognitive.correction_propagation import PropagationResult

        result = PropagationResult()
        assert result.reviewed_node_ids == []
        assert result.propagated_count == 0
        assert result.depth_reached == 0
        assert result.errors == []
