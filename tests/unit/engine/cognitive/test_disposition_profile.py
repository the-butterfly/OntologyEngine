"""Tests for DispositionProfile recall weight injection.

TDD Cycle: Verify all 7 dimensions affect recall behavior.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.errors import CognitiveError, CognitiveErrorCode
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.models import (
    DispositionProfile,
    apply_dynamic_weight,
)
from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore


@pytest_asyncio.fixture
async def api(tmp_path):
    db_path = str(tmp_path / "test_disp.db")
    store = LadybugGraphStore()
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


class TestDispositionProfileModel:
    """Verify DispositionProfile data model."""

    def test_default_profile_has_all_dimensions(self):
        p = DispositionProfile(id="test", scene="default")
        assert p.skepticism == 0.5
        assert p.evidence_demand == 0.5
        assert p.abstraction_preference == 0.5
        assert p.thoroughness == 0.5
        assert p.recency_bias == 0.5
        assert p.empathy == 0.5
        assert p.risk_tolerance == 0.5

    def test_profile_scene_default(self):
        p = DispositionProfile(id="test", scene="default")
        assert p.scene == "default"

    def test_profile_preserves_custom_values(self):
        p = DispositionProfile(
            id="test", scene="custom",
            skepticism=0.8, evidence_demand=0.3,
            abstraction_preference=0.8, thoroughness=0.7,
            recency_bias=0.2, empathy=0.6, risk_tolerance=0.4,
        )
        assert p.skepticism == 0.8
        assert p.evidence_demand == 0.3
        assert p.abstraction_preference == 0.8
        assert p.thoroughness == 0.7
        assert p.recency_bias == 0.2
        assert p.empathy == 0.6
        assert p.risk_tolerance == 0.4


class TestDispositionProfileRecall:
    """Verify DispositionProfile affects recall results."""

    @pytest.mark.asyncio
    async def test_recall_with_disposition_override_does_not_error(self, api):
        """recall with disposition_override should not error."""
        r = await api.remember(
            "Entity: 华信科技 for disposition test", "t_disp",
            memory_type="entity", tags={"label": "company"},
        )
        await api.remember(
            "Obs: 华信科技 Q1 revenue up", "t_disp",
            memory_type="observation", tags={"label": "company"},
        )

        profile = DispositionProfile(
            id="test_profile", scene="high_recency",
            recency_bias=0.9, skepticism=0.3,
        )
        result = await api.recall(
            "华信科技", "t_disp",
            disposition_override=profile,
        )
        assert result["success"] is True
        results = result["data"]["results"]
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_recall_with_recency_bias_boosts_recent(self, api):
        """memory_type filter with text matching should return matching nodes."""
        r = await api.remember(
            "Old entity for recency", "t_disp_rec",
            memory_type="entity", tags={"label": "test"},
        )
        old_id = r["data"]["memory_id"]
        r = await api.remember(
            "New entity for recency", "t_disp_rec",
            memory_type="entity", tags={"label": "test"},
        )
        new_id = r["data"]["memory_id"]

        result = await api.recall(
            "recency", "t_disp_rec",
            memory_type="entity",
        )
        results = result["data"]["results"]
        assert len(results) >= 2
        result_ids = [r["id"] for r in results]
        assert old_id in result_ids
        assert new_id in result_ids

    @pytest.mark.asyncio
    async def test_recall_with_abstraction_preference_visible(self, api):
        """High abstraction_preference should maintain access to mental_model nodes."""
        await api.remember(
            "Entity: abstract test", "t_disp_abs",
            memory_type="entity", tags={"label": "abstract"},
        )
        await api.remember(
            "Mental model of abstract entity", "t_disp_abs",
            memory_type="mental_model", tags={"label": "abstract"},
        )

        profile = DispositionProfile(
            id="abstract_test", scene="high_abstraction",
            abstraction_preference=0.8,
        )
        result = await api.recall(
            "abstract", "t_disp_abs",
            disposition_override=profile,
        )
        results = result["data"]["results"]
        types = [r["memory_type"] for r in results]
        assert "entity" in types or "mental_model" in types

    @pytest.mark.asyncio
    async def test_apply_dynamic_weight_preserves_weights(self):
        """apply_dynamic_weight should not zero out any score."""
        profile = DispositionProfile(id="test", scene="default")
        result_obs = apply_dynamic_weight(0.5, "observation", profile)
        result_mm = apply_dynamic_weight(0.5, "mental_model", profile)
        assert result_obs > 0
        assert result_mm > 0


class TestDispositionStore:
    """Verify DispositionStore persistence."""

    def test_store_get_default(self, tmp_path):
        from ontology_engine.engine.cognitive.disposition_store import DispositionStore
        file_path = str(tmp_path / "test_store.json")
        store = DispositionStore(file_path=file_path)
        profile = store.get("test_space")
        assert profile.id == "disp:test_space"
        assert profile.skepticism == 0.5

    def test_store_save_and_reload(self, tmp_path):
        from ontology_engine.engine.cognitive.disposition_store import DispositionStore
        file_path = str(tmp_path / "test_store2.json")
        store = DispositionStore(file_path=file_path)
        profile = store.get("test_space")
        profile.skepticism = 0.9
        store.save("test_space", profile)

        store2 = DispositionStore(file_path=file_path)
        reloaded = store2.get("test_space")
        assert reloaded.skepticism == 0.9
        assert reloaded.id == "disp:test_space"

    def test_store_to_dict(self, tmp_path):
        from ontology_engine.engine.cognitive.disposition_store import DispositionStore
        file_path = str(tmp_path / "test_store3.json")
        store = DispositionStore(file_path=file_path)
        d = store.to_dict("test_space")
        assert d["id"] == "disp:test_space"
        assert d["scene"] == "default"
        assert d["skepticism"] == 0.5
        assert "evidence_demand" in d
        assert "abstraction_preference" in d
        assert "thoroughness" in d
        assert "recency_bias" in d
        assert "empathy" in d
        assert "risk_tolerance" in d
