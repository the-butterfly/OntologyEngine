import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ontology_engine.engine.cognitive.memory_api import MemoryAPI, ReflectionJobStore
from ontology_engine.engine.cognitive.models import CognitiveNode


def _make_api(qul=None, ingestion=None) -> MemoryAPI:
    return MemoryAPI(
        repository=AsyncMock(),
        consolidation_engine=AsyncMock(),
        entity_resolver=AsyncMock(),
        query_router=AsyncMock(),
        reflect_agent=AsyncMock(),
        forgetting_engine=AsyncMock(),
        dream_cycle=AsyncMock(),
        correction_propagation=AsyncMock(),
        vector_index=AsyncMock(),
        qul=qul,
        ingestion_service=ingestion,
    )


class TestQULIntegration:
    @pytest.mark.asyncio
    async def test_recall_uses_qul_when_available(self):
        mock_qul = MagicMock()
        mock_qul.extract_constraints = AsyncMock(return_value=[
            MagicMock(constraint_type="temporal_scope", value="last_week", confidence=0.9)
        ])
        mock_strategy = MagicMock()
        mock_qul.map_to_retrieval_strategy = MagicMock(return_value=mock_strategy)
        mock_qul.infer_query_type = MagicMock(return_value="temporal")

        api = _make_api(qul=mock_qul)
        mock_result = MagicMock()
        mock_result.doc_id = "n1"
        mock_result.text = "test result"
        mock_result.score = 0.9
        mock_result.memory_type = "entity"
        mock_result.type_weight = 2.0
        mock_result.tags = []
        mock_result.space_id = "test"
        mock_result.node_id = "n1"
        api._router.route = AsyncMock(return_value=[mock_result])
        api._repo.get_profile_by_scene = AsyncMock(return_value=None)
        api._repo.get_node = AsyncMock(return_value=MagicMock(
            id="n1", content="test", memory_type="entity", cognitive_layer="semantic",
            confidence=0.9, belief_status="accepted", tags=[], space_id="test",
            created_at="2026-01-01", access_count=0, last_access_at=None,
            strength=1.0, version=1, source_fragment_ids=[], proof_count=0,
        ))

        from ontology_engine.engine.cognitive.memory_api import RecallRequest
        req = RecallRequest(query="what did I decide last week?", space_id="test")

        await api._recall(req)

        mock_qul.extract_constraints.assert_called_once()
        mock_qul.map_to_retrieval_strategy.assert_called_once()
        mock_qul.infer_query_type.assert_called_once()
        api._router.route.assert_called_once()
        call_kwargs = api._router.route.call_args
        assert call_kwargs.kwargs.get("strategy_adjustment") is mock_strategy

    @pytest.mark.asyncio
    async def test_recall_falls_back_when_qul_fails(self):
        mock_qul = MagicMock()
        mock_qul.extract_constraints = AsyncMock(side_effect=RuntimeError("QUL error"))

        api = _make_api(qul=mock_qul)
        api._router.route = AsyncMock(return_value=[])
        api._repo.get_profile_by_scene = AsyncMock(return_value=None)

        from ontology_engine.engine.cognitive.memory_api import RecallRequest
        req = RecallRequest(query="test query", space_id="test")

        await api._recall(req)

        api._router.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_without_qul_uses_detect_query_type(self):
        api = _make_api(qul=None)
        api._router.route = AsyncMock(return_value=[])
        api._repo.get_profile_by_scene = AsyncMock(return_value=None)

        from ontology_engine.engine.cognitive.memory_api import RecallRequest
        req = RecallRequest(query="test query", space_id="test")

        await api._recall(req)

        api._router.route.assert_called_once()
        call_kwargs = api._router.route.call_args
        assert call_kwargs.kwargs.get("strategy_adjustment") is None

    @pytest.mark.asyncio
    async def test_recall_applies_constraint_boost(self):
        mock_qul = MagicMock()
        constraint = MagicMock(constraint_type="user_preference", value="cautious", confidence=0.8)
        mock_qul.extract_constraints = AsyncMock(return_value=[constraint])
        mock_qul.map_to_retrieval_strategy = MagicMock(return_value=MagicMock())
        mock_qul.infer_query_type = MagicMock(return_value="preference")
        mock_qul.apply_constraint_boost = MagicMock(return_value=[
            MagicMock(doc_id="n1", score=0.9, type_weight=2.0, rank_score=1.8, text="test", memory_type="entity", tags=[], space_id="test", node_id="n1", get=lambda k, d=None: {"text": "test"}.get(k, d)),
        ])

        api = _make_api(qul=mock_qul)
        mock_result = MagicMock()
        mock_result.doc_id = "n1"
        mock_result.text = "test"
        mock_result.score = 0.9
        mock_result.memory_type = "entity"
        mock_result.type_weight = 2.0
        mock_result.tags = []
        mock_result.space_id = "test"
        mock_result.node_id = "n1"
        api._router.route = AsyncMock(return_value=[mock_result])
        api._repo.get_profile_by_scene = AsyncMock(return_value=None)
        api._repo.get_node = AsyncMock(return_value=MagicMock(
            id="n1", content="test", memory_type="entity", cognitive_layer="semantic",
            confidence=0.9, belief_status="accepted", tags=[], space_id="test",
            created_at="2026-01-01", access_count=0, last_access_at=None,
            strength=1.0, version=1, source_fragment_ids=[], proof_count=0,
        ))

        from ontology_engine.engine.cognitive.memory_api import RecallRequest
        req = RecallRequest(query="I prefer cautious approaches", space_id="test")

        result = await api._recall(req)

        mock_qul.apply_constraint_boost.assert_called_once()


class TestIngestionIntegration:
    @pytest.mark.asyncio
    async def test_remember_uses_ingestion_when_available(self):
        mock_ingestion = AsyncMock()
        mock_ingestion.ingest.return_value = {
            "cognitive_node_id": "mem:entity:test:abc123",
            "fragment_id": "frag:abc123",
        }

        api = _make_api(ingestion=mock_ingestion)
        api._dedup_gate = AsyncMock()
        api._dedup_gate.check.return_value = MagicMock(
            decision=MagicMock(value="accept"), duplicate_of=None, reason="", marginal_value=0.0
        )

        from ontology_engine.engine.cognitive.memory_api import RememberRequest
        req = RememberRequest(
            content="Test content for ingestion",
            space_id="test",
            memory_type="entity",
        )

        result = await api._remember(req)

        mock_ingestion.ingest.assert_called_once()
        assert result["data"]["memory_id"] == "mem:entity:test:abc123"
        assert result["data"]["fragment_id"] == "frag:abc123"

    @pytest.mark.asyncio
    async def test_remember_falls_back_when_ingestion_fails(self):
        mock_ingestion = AsyncMock()
        mock_ingestion.ingest.side_effect = RuntimeError("Ingestion error")

        api = _make_api(ingestion=mock_ingestion)
        api._dedup_gate = AsyncMock()
        api._dedup_gate.check.return_value = MagicMock(
            decision=MagicMock(value="accept"), duplicate_of=None, reason="", marginal_value=0.0
        )
        api._repo.create_node = AsyncMock()

        from ontology_engine.engine.cognitive.memory_api import RememberRequest
        req = RememberRequest(
            content="Test content fallback",
            space_id="test",
            memory_type="entity",
        )

        result = await api._remember(req)

        mock_ingestion.ingest.assert_called_once()
        api._repo.create_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_remember_without_ingestion_uses_direct_create(self):
        api = _make_api(ingestion=None)
        api._dedup_gate = AsyncMock()
        api._dedup_gate.check.return_value = MagicMock(
            decision=MagicMock(value="accept"), duplicate_of=None, reason="", marginal_value=0.0
        )
        api._repo.create_node = AsyncMock()

        from ontology_engine.engine.cognitive.memory_api import RememberRequest
        req = RememberRequest(
            content="Test content direct",
            space_id="test",
            memory_type="entity",
        )

        result = await api._remember(req)

        api._repo.create_node.assert_called_once()


class TestContradictionCandidateHandling:
    @pytest.mark.asyncio
    async def test_contradiction_candidate_sets_pending_review(self):
        api = _make_api()
        api._dedup_gate = AsyncMock()

        from ontology_engine.engine.cognitive.deduplication_gate import WriteDecision
        api._dedup_gate.check.return_value = MagicMock(
            decision=WriteDecision.CONTRADICTION_CANDIDATE,
            duplicate_of=None,
            reason="Similar to existing",
            marginal_value=0.0,
        )
        api._repo.create_node = AsyncMock()

        from ontology_engine.engine.cognitive.memory_api import RememberRequest
        req = RememberRequest(
            content="Contradictory content",
            space_id="test",
            memory_type="opinion",
        )

        result = await api._remember(req)

        created_node = api._repo.create_node.call_args[0][0]
        assert created_node.belief_status == "pending_review"


class TestModelDomainInference:
    def test_infer_model_domain_world(self):
        assert MemoryAPI._infer_model_domain("entity") == "world"
        assert MemoryAPI._infer_model_domain("rule") == "world"
        assert MemoryAPI._infer_model_domain("observation") == "world"

    def test_infer_model_domain_self(self):
        assert MemoryAPI._infer_model_domain("mental_model") == "self"
        assert MemoryAPI._infer_model_domain("opinion") == "self"
        assert MemoryAPI._infer_model_domain("self_experience") == "self"

    def test_infer_model_domain_task(self):
        assert MemoryAPI._infer_model_domain("commitment") == "task"
        assert MemoryAPI._infer_model_domain("procedure") == "task"
        assert MemoryAPI._infer_model_domain("episode") == "task"

    def test_infer_model_domain_default(self):
        assert MemoryAPI._infer_model_domain("unknown_type") == "world"


class TestReflectionJobStoreAsync:
    @pytest.mark.asyncio
    async def test_create_and_get_job(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")
        assert job.query == "test query"
        assert job.space_id == "test_space"

        retrieved = await store.get_job(job.reflection_id)
        assert retrieved is not None
        assert retrieved.query == "test query"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        store = ReflectionJobStore()
        result = await store.get_job("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_progress(self):
        store = ReflectionJobStore()
        job = await store.create_job("test query", "test_space")
        await store.update_progress(job.reflection_id, "consolidation", "completed")
        updated = await store.get_job(job.reflection_id)
        assert updated.progress.progress["consolidation"] == "completed"
