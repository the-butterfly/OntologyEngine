"""Tests for DispositionProfile pipeline injection and contradiction detection.

TDD-4: Verify disposition flows through recall pipeline and affects contradiction detection.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.models import (
    DispositionProfile,
)
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


@pytest_asyncio.fixture
async def api(tmp_path):
    db_path = str(tmp_path / "test_pipeline.db")
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


class TestDispositionPipeline:
    """Verify disposition flows through recall pipeline."""

    @pytest.mark.asyncio
    async def test_recall_with_disposition_dict_does_not_error(self, api):
        r = await api.remember(
            "Entity: dict pipeline test", "t_pipe_dict",
            memory_type="entity", tags=["test"],
        )
        result = await api.recall(
            "dict pipeline", "t_pipe_dict",
            memory_type="entity",
            disposition_override={"skepticism": 0.8, "scene": "test"},
        )
        assert result["success"] is True
        assert len(result["data"]["results"]) >= 1

    @pytest.mark.asyncio
    async def test_recall_with_disposition_scene_string(self, api):
        r = await api.remember(
            "Entity: scene string test", "t_pipe_scene",
            memory_type="entity", tags=["test"],
        )
        result = await api.recall(
            "scene string", "t_pipe_scene",
            memory_type="entity",
            disposition_override="audit",
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_recall_with_disposition_profile_object(self, api):
        r = await api.remember(
            "Entity: profile object test", "t_pipe_obj",
            memory_type="entity", tags=["test"],
        )
        profile = DispositionProfile(
            id="pipe_test", scene="custom",
            skepticism=0.8, evidence_demand=0.6,
        )
        result = await api.recall(
            "profile object", "t_pipe_obj",
            memory_type="entity",
            disposition_override=profile,
        )
        assert result["success"] is True
        assert len(result["data"]["results"]) >= 1

    @pytest.mark.asyncio
    async def test_recall_with_disposition_from_store(self, api):
        from ontology_engine.engine.cognitive.disposition_store import DispositionStore
        r = await api.remember(
            "Entity: store pipeline", "t_pipe_store",
            memory_type="entity", tags=["test"],
        )
        result = await api.recall(
            "store pipeline", "t_pipe_store",
            memory_type="entity",
            disposition_override={"scene": "audit"},
        )
        assert result["success"] is True
        assert len(result["data"]["results"]) >= 1

    @pytest.mark.asyncio
    async def test_recall_null_disposition_is_handled(self, api):
        r = await api.remember(
            "Entity: null disp test", "t_pipe_null",
            memory_type="entity", tags=["test"],
        )
        result = await api.recall(
            "null disp", "t_pipe_null",
            memory_type="entity",
            disposition_override=None,
        )
        assert result["success"] is True


class TestContradictionWithDisposition:
    """Verify DispositionProfile.skepticism affects contradiction detection."""

    @pytest.mark.asyncio
    async def test_negation_conflict_detected_with_high_skepticism(self, api):
        r1 = await api.remember(
            "华信科技使用Oracle数据库", "t_contra1",
            memory_type="observation", tags=["tech"],
        )
        r2 = await api.remember(
            "华信科技不是使用Oracle数据库", "t_contra1",
            memory_type="observation", tags=["tech"],
        )
        id1 = r1["data"]["memory_id"]
        id2 = r2["data"]["memory_id"]

        high_skep = DispositionProfile(id="high_skep", scene="test", skepticism=0.8)
        cons = await api._reflect._detect_rule_based_contradictions(
            "database", "t_contra1", disposition=high_skep,
        )
        cons_ids = {cid for c in cons for cid in c.node_ids}
        assert id1 in cons_ids
        assert id2 in cons_ids
        assert len(cons) >= 1

    @pytest.mark.asyncio
    async def test_low_skepticism_suppresses_negation_conflict(self, api):
        r1 = await api.remember(
            "技术公司使用Java语言", "t_contra2",
            memory_type="observation", tags=["lang"],
        )
        r2 = await api.remember(
            "技术公司不是使用Java语言", "t_contra2",
            memory_type="observation", tags=["lang"],
        )

        low_skep = DispositionProfile(id="low_skep", scene="test", skepticism=0.3)
        cons = await api._reflect._detect_rule_based_contradictions(
            "Java", "t_contra2", disposition=low_skep,
        )
        assert len(cons) == 0

    @pytest.mark.asyncio
    async def test_high_skepticism_detects_value_conflict(self, api):
        r1 = await api.remember(
            "华信科技员工数5000人", "t_contra3",
            memory_type="observation", tags=["scale"],
        )
        r2 = await api.remember(
            "华信科技员工数200人", "t_contra3",
            memory_type="observation", tags=["scale"],
        )
        id1 = r1["data"]["memory_id"]
        id2 = r2["data"]["memory_id"]

        high_skep = DispositionProfile(id="high_skep2", scene="test", skepticism=0.8)
        cons = await api._reflect._detect_rule_based_contradictions(
            "员工", "t_contra3", disposition=high_skep,
        )
        cons_ids = {cid for c in cons for cid in c.node_ids}
        assert id1 in cons_ids or id2 in cons_ids

    @pytest.mark.asyncio
    async def test_low_skepticism_suppresses_value_conflict(self, api):
        r1 = await api.remember(
            "项目预算100万元", "t_contra4",
            memory_type="observation", tags=["budget"],
        )
        r2 = await api.remember(
            "项目预算50万元", "t_contra4",
            memory_type="observation", tags=["budget"],
        )

        low_skep = DispositionProfile(id="low_skep2", scene="test", skepticism=0.3)
        cons = await api._reflect._detect_rule_based_contradictions(
            "预算", "t_contra4", disposition=low_skep,
        )
        assert len(cons) == 0

    @pytest.mark.asyncio
    async def test_default_skepticism_detects_obvious_contradiction(self, api):
        r1 = await api.remember(
            "项目采用敏捷开发模式", "t_contra5",
            memory_type="observation", tags=["method"],
        )
        r2 = await api.remember(
            "项目不采用敏捷开发模式", "t_contra5",
            memory_type="observation", tags=["method"],
        )
        id1 = r1["data"]["memory_id"]
        id2 = r2["data"]["memory_id"]

        default = DispositionProfile(id="default", scene="test")
        cons = await api._reflect._detect_rule_based_contradictions(
            "敏捷", "t_contra5", disposition=default,
        )
        cons_ids = {cid for c in cons for cid in c.node_ids}
        assert id1 in cons_ids
        assert id2 in cons_ids
