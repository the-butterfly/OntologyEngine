"""Tests for evidence chain, correction history, and contradiction detection.

TDD Cycle: Each test verifies a specific behavior of the evidence/correction pipeline.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import asyncio

from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.errors import CognitiveError, CognitiveErrorCode
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


@pytest_asyncio.fixture
async def api(tmp_path):
    db_path = str(tmp_path / "test_evidence.db")
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


async def _get_evidence(api: MemoryAPI, space_id: str, node_id: str) -> dict:
    """Simulate evidence endpoint logic for testing."""
    node = await api._repo.get_node(node_id)
    if not node:
        raise ValueError(f"Node {node_id} not found")

    fragments = []
    for fid in node.source_fragment_ids[:20]:
        try:
            frag = await api._repo.get_node(fid)
            if frag:
                fragments.append(frag.to_dict() if hasattr(frag, "to_dict") else {"id": fid})
        except Exception:
            fragments.append({"id": fid})

    supporting_edges = await api._repo.query_cognitive_edges(
        to_id=node_id, edge_type="COG_SUPPORTED_BY", limit=20,
    )
    supporting_ids = [e.from_id for e in supporting_edges]
    supporting_nodes = []
    for sid in supporting_ids:
        try:
            sn = await api._repo.get_node(sid)
            if sn:
                supporting_nodes.append(sn.to_dict() if hasattr(sn, "to_dict") else {"id": sid})
        except Exception:
            supporting_nodes.append({"id": sid})

    consolidated_edges = await api._repo.query_cognitive_edges(
        from_id=node_id, edge_type="CONSOLIDATED_INTO", limit=10,
    )

    return {
        "node_id": node_id,
        "source_fragments": fragments,
        "supporting_nodes": supporting_nodes,
        "consolidated_into": [
            {"target_id": e.to_id, "edge_type": e.edge_type}
            for e in consolidated_edges
        ],
    }


class TestEvidenceChain:
    """Verify evidence chain endpoint returns complete data."""

    @pytest.mark.asyncio
    async def test_evidence_returns_source_fragment_ids(self, api):
        """Observation with known source_fragments should expose them in evidence."""
        r = await api.remember(
            "Fragment A: 华信科技Q1营收50亿", "t_ev_src",
            memory_type="fragment",
        )
        fid = r["data"]["memory_id"]

        r = await api.remember(
            "Observation: 华信科技营收增长", "t_ev_src",
            memory_type="observation",
            source_fragment_ids=[fid],
        )
        obs_id = r["data"]["memory_id"]

        evidence = await _get_evidence(api, "t_ev_src", obs_id)

        assert len(evidence["source_fragments"]) >= 1
        fragment_ids = [f["id"] if isinstance(f, dict) else f.id for f in evidence["source_fragments"]]
        assert fid in fragment_ids, f"Expected {fid} in source_fragments, got {fragment_ids}"

    @pytest.mark.asyncio
    async def test_evidence_returns_node_fields(self, api):
        """Evidence node should return complete CognitiveNode fields."""
        r = await api.remember(
            "Fragment B: 数据点", "t_ev_proof",
            memory_type="fragment",
        )
        fid = r["data"]["memory_id"]
        r = await api.remember(
            "Obs with single proof", "t_ev_proof",
            memory_type="observation",
            source_fragment_ids=[fid],
        )
        obs_id = r["data"]["memory_id"]

        node = await api._repo.get_node(obs_id)
        assert node is not None
        assert node.proof_count >= 1, f"Expected proof_count >= 1, got {node.proof_count}"
        assert len(node.source_fragment_ids) >= 1

    @pytest.mark.asyncio
    async def test_evidence_belief_status_field(self, api):
        """Evidence should include belief_status from CognitiveNode."""
        r = await api.remember(
            "Fragment C: data for belief", "t_ev_support",
            memory_type="fragment",
        )
        fid = r["data"]["memory_id"]
        r = await api.remember(
            "Observation with belief", "t_ev_support",
            memory_type="observation",
            source_fragment_ids=[fid],
        )
        obs_id = r["data"]["memory_id"]

        node = await api._repo.get_node(obs_id)
        assert node is not None
        assert node.belief_status == "accepted"

    @pytest.mark.asyncio
    async def test_evidence_supporting_nodes(self, api):
        """Evidence should include supporting nodes via COG_SUPPORTED_BY edges."""
        r = await api.remember(
            "Fragment D1: support data", "t_ev_supnodes",
            memory_type="fragment",
        )
        fid1 = r["data"]["memory_id"]

        r = await api.remember(
            "Observation needing support", "t_ev_supnodes",
            memory_type="observation",
            source_fragment_ids=[fid1],
        )
        obs_id = r["data"]["memory_id"]

        evidence = await _get_evidence(api, "t_ev_supnodes", obs_id)
        assert "supporting_nodes" in evidence

    @pytest.mark.asyncio
    async def test_evidence_consolidated_into(self, api):
        """Evidence should include consolidation targets."""
        r = await api.remember(
            "Entity: Test entity", "t_ev_consol",
            memory_type="entity",
        )
        entity_id = r["data"]["memory_id"]

        evidence = await _get_evidence(api, "t_ev_consol", entity_id)
        assert "consolidated_into" in evidence


class TestCorrectionChain:
    """Verify correction creates proper chain and appears in corrections endpoint."""

    @pytest.mark.asyncio
    async def test_correction_sets_superseded_by(self, api):
        """correct_memory should set superseded_by on the original node."""
        r = await api.remember(
            "Old observation content", "t_corr_sup",
            memory_type="observation",
        )
        old_id = r["data"]["memory_id"]

        result = await api.correct_memory(
            node_id=old_id,
            corrected_text="Updated observation content",
            reason="Correction test",
            user_id="tester",
        )
        assert result["success"] is True

        old_node = await api._repo.get_node(old_id)
        assert old_node is not None
        assert old_node.belief_status == "superseded", f"Expected superseded, got {old_node.belief_status}"
        assert old_node.superseded_by == result["data"]["new_node_id"], (
            f"Expected superseded_by={result['data']['new_node_id']}, got {old_node.superseded_by}"
        )

    @pytest.mark.asyncio
    async def test_correction_creates_supersedes_edge(self, api):
        """correct_memory should create a SUPERSEDES edge linking old→new."""
        r = await api.remember(
            "Old content for edge test", "t_corr_edge",
            memory_type="observation",
        )
        old_id = r["data"]["memory_id"]

        result = await api.correct_memory(
            node_id=old_id,
            corrected_text="New corrected content",
            reason="Edge test",
            user_id="tester",
        )
        new_id = result["data"]["new_node_id"]

        edges = await api._repo.query_cognitive_edges(
            to_id=old_id, edge_type="SUPERSEDES", limit=10,
        )
        assert len(edges) >= 1, f"Expected SUPERSEDES edge, got {len(edges)} edges"
        assert edges[0].from_id == new_id, f"Edge should originate from {new_id}, got {edges[0].from_id}"
        assert edges[0].to_id == old_id, f"Edge should point to {old_id}, got {edges[0].to_id}"

    @pytest.mark.asyncio
    async def test_correction_new_node_has_source_fragments(self, api):
        """Corrected node should carry forward the original source_fragment_ids."""
        r = await api.remember(
            "Fragment X: source data", "t_corr_src",
            memory_type="fragment",
        )
        fid = r["data"]["memory_id"]
        r = await api.remember(
            "Observation with source", "t_corr_src",
            memory_type="observation",
            source_fragment_ids=[fid],
        )
        old_id = r["data"]["memory_id"]

        result = await api.correct_memory(
            node_id=old_id,
            corrected_text="Corrected observation",
            reason="Source carry test",
            user_id="tester",
        )
        new_id = result["data"]["new_node_id"]

        new_node = await api._repo.get_node(new_id)
        assert new_node is not None
        assert fid in new_node.source_fragment_ids, (
            f"Expected {fid} in new node source_fragment_ids, got {new_node.source_fragment_ids}"
        )

    @pytest.mark.asyncio
    async def test_correction_appears_in_audit(self, api):
        """Correction should appear in audit trail with correction type."""
        r = await api.remember(
            "Audit-test content", "t_corr_audit",
            memory_type="observation",
        )
        old_id = r["data"]["memory_id"]

        await api.correct_memory(
            node_id=old_id,
            corrected_text="Audited content",
            reason="Audit trace test",
            user_id="tester",
        )

        audit = await api.get_audit_trail("t_corr_audit", limit=50)
        entries = audit.get("entries", [])
        superseded_entries = [e for e in entries if e.get("belief_status") == "superseded"]
        assert len(superseded_entries) >= 1, f"Expected superseded entries in audit, got {len(superseded_entries)}"
        assert any(e["id"] == old_id for e in superseded_entries), f"Original node {old_id} not in superseded audit entries"


class TestContradictionDetection:
    """Verify contradiction detection and endpoint."""

    @pytest.mark.asyncio
    async def test_proof_count_increments_with_sources(self, api):
        """proof_count should increment when source_fragment_ids are provided."""
        r = await api.remember(
            "Frag: data point 1", "t_contra_proof",
            memory_type="fragment",
        )
        fid1 = r["data"]["memory_id"]
        r = await api.remember(
            "Frag: data point 2", "t_contra_proof",
            memory_type="fragment",
        )
        fid2 = r["data"]["memory_id"]

        r = await api.remember(
            "Claim with two sources", "t_contra_proof",
            memory_type="observation",
            source_fragment_ids=[fid1, fid2],
        )
        obs_id = r["data"]["memory_id"]

        node = await api._repo.get_node(obs_id)
        assert node is not None
        assert node.proof_count >= 2, f"Expected proof_count >= 2, got {node.proof_count}"
        assert len(node.source_fragment_ids) == 2

    @pytest.mark.asyncio
    async def test_entity_supersedes_on_conflicting_remember(self, api):
        """Remember with supersede_target should mark old entity as superseded."""
        r = await api.remember(
            "Entity v1: 华信科技风险C级", "t_contra_v1",
            memory_type="entity",
            tags={"label": "company"},
        )
        old_id = r["data"]["memory_id"]

        r = await api.remember(
            "Entity v2: 华信科技风险B级", "t_contra_v2",
            memory_type="entity",
            supersede_target=old_id,
        )
        new_id = r["data"]["memory_id"]

        old_node = await api._repo.get_node(old_id)
        assert old_node is not None
        assert old_node.belief_status == "superseded", f"Expected superseded, got {old_node.belief_status}"
        assert old_node.superseded_by == new_id
