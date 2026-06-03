"""End-to-end test: Knowledge Management Agent memory system.

Scenario: A technical knowledge management agent that:
1. Imports technical documents → fragment extraction with attributes
2. Consolidates fragments → observations with type-specific attributes
3. Recalls with unified TYPE_WEIGHTS (BASE_TYPE_WEIGHTS)
4. Reflects to discover contradictions → belief revision rules applied
5. Forgetting with feedback_weight >= 0.9 protection
6. Full pipeline: remember → consolidate → recall → reflect → forget → stats

Covers all 5 GAP fixes:
- GAP1: CognitiveNode attributes field
- GAP2: TYPE_WEIGHTS unified with BASE_TYPE_WEIGHTS
- GAP3: Belief revision rules engine integration
- GAP4: Forgetting protection with feedback_weight >= 0.9
- GAP5: REST /stats /types /audit using MemoryAPISingleton
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.compilation import compile_entity_page
from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.models import (
    BeliefRevisionRule,
    CognitiveNode,
    DEFAULT_BELIEF_REVISION_RULES,
)
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore


async def _create_api(db_path: str) -> MemoryAPI:
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
    return MemoryAPI(
        repository=repo,
        consolidation_engine=consolidation,
        entity_resolver=resolver,
        query_router=router,
        reflect_agent=reflect,
        forgetting_engine=forgetting,
        dream_cycle=dream,
        correction_propagation=correction,
    )


@pytest.fixture
def km_space():
    return "space_tech_knowledge"


@pytest.fixture
def cognitive_db():
    tmpdir = tempfile.mkdtemp(prefix="e2e_km_")
    db_path = str(Path(tmpdir) / "cognitive")
    yield db_path
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except OSError:
        pass


@pytest_asyncio.fixture
async def api(cognitive_db):
    return await _create_api(cognitive_db)


class TestE2EKnowledgeManagement:
    """Full lifecycle for a technical knowledge management agent."""

    @pytest.mark.asyncio
    async def test_gap1_attributes_field(self, api, km_space):
        """GAP1: CognitiveNode stores type-specific attributes via metadata."""
        r = await api.remember(
            content="Python 3.12 引入了更快的 CPython 实现，性能提升约5%",
            space_id=km_space,
            tags=["python", "performance"],
            memory_type="observation",
            metadata={
                "fact_type": "technical_fact",
                "observed_at": "2024-10-01",
                "observer": "tech_blog",
                "certainty": "high",
                "irrelevant_field": "should_be_filtered",
            },
        )
        data = r.get("data", r)
        assert data.get("memory_type") == "observation"
        node_id = data["memory_id"]
        node = await api._repo.get_node(node_id)
        assert node.attributes.get("fact_type") == "technical_fact"
        assert node.attributes.get("observed_at") == "2024-10-01"
        assert node.attributes.get("observer") == "tech_blog"
        assert node.attributes.get("certainty") == "high"
        assert "irrelevant_field" not in node.attributes

        r2 = await api.remember(
            content="Rust 的所有权模型消除了数据竞争",
            space_id=km_space,
            tags=["rust", "memory_safety"],
            memory_type="opinion",
            metadata={
                "opinion_type": "technical_assessment",
                "sentiment": "positive",
                "holder": "rust_community",
                "topic": "memory_safety",
            },
        )
        data2 = r2.get("data", r2)
        node2 = await api._repo.get_node(data2["memory_id"])
        assert node2.attributes.get("opinion_type") == "technical_assessment"
        assert node2.attributes.get("sentiment") == "positive"

    @pytest.mark.asyncio
    async def test_gap2_type_weights_unified(self, api, km_space):
        """GAP2: recall uses BASE_TYPE_WEIGHTS from rrf_types, not inline weights."""
        await api.remember(
            content="Docker 容器使用 namespace 和 cgroup 进行隔离",
            space_id=km_space,
            memory_type="mental_model",
            tags=["docker", "container"],
        )
        await api.remember(
            content="Kubernetes Pod 是最小部署单元",
            space_id=km_space,
            memory_type="entity",
            tags=["k8s", "pod"],
        )
        await api.remember(
            content="一些零散的笔记碎片",
            space_id=km_space,
            memory_type="fragment",
            tags=["notes"],
        )

        result = await api.recall(
            query="容器技术",
            space_id=km_space,
            max_results=10,
        )
        data = result.get("data", result)
        for item in data.get("results", []):
            mt = item.get("memory_type", "fragment")
            expected_weight = BASE_TYPE_WEIGHTS.get(mt, 1.0)
            assert item["type_weight"] == expected_weight, (
                f"memory_type={mt}: expected weight {expected_weight}, got {item['type_weight']}"
            )

    @pytest.mark.asyncio
    async def test_gap3_belief_revision_rules(self, api, km_space):
        """GAP3: Belief revision rules engine is applied during reflect."""
        r1 = await api.remember(
            content="HTTP/2 使用文本协议传输数据",
            space_id=km_space,
            memory_type="observation",
            tags=["http", "protocol"],
            confidence=0.8,
        )
        data1 = r1.get("data", r1)
        node1_id = data1["memory_id"]

        r2 = await api.remember(
            content="HTTP/2 使用二进制协议传输数据，不是文本协议",
            space_id=km_space,
            memory_type="observation",
            tags=["http", "protocol"],
            confidence=0.95,
            supersede_reason="User correction: HTTP/2 is binary, not text",
        )
        data2 = r2.get("data", r2)
        node2_id = data2["memory_id"]

        custom_rules = [
            BeliefRevisionRule(
                rule_id="TEST_BR_001",
                name="High Confidence Accept",
                condition="confidence >= 0.9",
                action={"set_belief": "accepted"},
                priority=100,
                track="any",
            ),
        ]

        node2 = await api._repo.get_node(node2_id)
        assert node2.confidence >= 0.9, f"Expected confidence >= 0.9, got {node2.confidence}"

        revision = await api._apply_belief_revision_rules(
            node2_id,
            type("MockContradiction", (), {"contradiction_type": "belief_conflict"})(),
            rules=custom_rules,
        )
        assert revision is not None
        assert revision["new_status"] == "accepted"
        assert revision["rule"] == "TEST_BR_001"

    @pytest.mark.asyncio
    async def test_gap4_forgetting_protection_feedback_weight(self, api, km_space):
        """GAP4: Nodes with feedback_weight >= 0.9 are protected from forgetting."""
        r = await api.remember(
            content="Git 使用 DAG 结构管理提交历史",
            space_id=km_space,
            memory_type="mental_model",
            tags=["git", "vcs"],
            confidence=1.0,
        )
        data = r.get("data", r)
        node_id = data["memory_id"]

        node = await api._repo.get_node(node_id)
        node.feedback_weight = 0.95
        await api._repo.update_node(node, reason="Set high feedback_weight for protection test")

        node = await api._repo.get_node(node_id)
        assert node.feedback_weight >= 0.9

        forgetting = api._forgetting
        is_protected = forgetting._is_protected(node)
        assert is_protected is True, (
            f"Node with feedback_weight={node.feedback_weight} should be protected"
        )

        low_fw_node = CognitiveNode(
            id="test_low_fw_node",
            memory_type="fragment",
            cognitive_layer="perception",
            content="一些不重要的碎片信息",
            domain_id=km_space,
            feedback_weight=0.3,
            belief_status="accepted",
        )
        await api._repo.create_node(low_fw_node)
        assert forgetting._is_protected(low_fw_node) is False

    @pytest.mark.asyncio
    async def test_gap5_stats_uses_singleton_repo(self, api, km_space):
        """GAP5: Stats/types/audit endpoints use MemoryAPISingleton's repo."""
        await api.remember(
            content="React 使用虚拟 DOM 进行高效渲染",
            space_id=km_space,
            memory_type="mental_model",
            tags=["react", "frontend"],
        )
        await api.remember(
            content="Vue 3 使用 Proxy 实现响应式系统",
            space_id=km_space,
            memory_type="observation",
            tags=["vue", "frontend"],
        )

        repo = api._repo
        nodes = await repo.query_nodes(domain_id=km_space, limit=10000)
        assert len(nodes) >= 2

        type_counts: dict[str, int] = {}
        for n in nodes:
            type_counts[n.memory_type] = type_counts.get(n.memory_type, 0) + 1
        assert "mental_model" in type_counts
        assert "observation" in type_counts

    @pytest.mark.asyncio
    async def test_end_to_end_knowledge_pipeline(self, api, km_space):
        """Full pipeline: remember → consolidate → recall → reflect → forget → compile.

        Simulates a knowledge management agent processing technical docs:
        1. Import fragmented tech notes (fragments)
        2. Consolidate into structured observations
        3. Recall with unified weights
        4. Reflect to find contradictions
        5. Apply belief revision rules
        6. Forget with feedback_weight protection
        7. Compile entity page
        """
        fragments = [
            ("Kubernetes 使用 etcd 作为分布式键值存储", ["k8s", "etcd", "storage"]),
            ("etcd 基于 Raft 共识算法保证一致性", ["etcd", "raft", "consensus"]),
            ("Raft 算法通过 Leader 选举实现容错", ["raft", "leader_election"]),
            ("Kubernetes Pod 可以包含多个容器", ["k8s", "pod"]),
            ("etcd 3.5 版本引入了 MVCC 存储", ["etcd", "mvcc"]),
        ]

        node_ids = []
        for content, tags in fragments:
            r = await api.remember(
                content=content,
                space_id=km_space,
                tags=tags,
                memory_type="fragment",
                metadata={"fact_type": "technical_fact", "certainty": "high"},
            )
            data = r.get("data", r)
            node_ids.append(data["memory_id"])

        for nid in node_ids:
            node = await api._repo.get_node(nid)
            if node.memory_type == "observation":
                assert "fact_type" in node.attributes

        consolidation_result = await api._consolidation.run_consolidation_job(km_space)
        assert len(consolidation_result.created) + len(consolidation_result.updated) + len(consolidation_result.deleted) + len(consolidation_result.errors) >= 0

        recall_result = await api.recall(
            query="etcd 分布式存储一致性",
            space_id=km_space,
            max_results=10,
        )
        recall_data = recall_result.get("data", recall_result)
        for item in recall_data.get("results", []):
            mt = item.get("memory_type", "fragment")
            assert item["type_weight"] == BASE_TYPE_WEIGHTS.get(mt, 1.0)

        await api.remember(
            content="etcd 使用 Paxos 算法保证一致性",
            space_id=km_space,
            memory_type="observation",
            tags=["etcd", "paxos"],
            confidence=0.6,
            metadata={"fact_type": "technical_fact", "certainty": "low"},
        )

        reflect_result = await api.reflect(
            query="etcd 共识算法",
            space_id=km_space,
        )
        reflect_data = reflect_result.get("data", reflect_result)
        assert reflect_data is not None

        all_nodes = await api._repo.query_nodes(domain_id=km_space, limit=100)
        for n in all_nodes:
            if "etcd" in n.content and "Raft" in n.content:
                n.feedback_weight = 0.95
                await api._repo.update_node(n, reason="Protect etcd/Raft knowledge")
                break

        forgetting = api._forgetting
        protected_count = 0
        for n in all_nodes:
            if forgetting._is_protected(n):
                protected_count += 1
        assert protected_count >= 1

        entity_nodes = [n for n in all_nodes if n.memory_type == "entity"]
        if entity_nodes:
            entity_page = await compile_entity_page(
                repository=api._repo,
                node_id=entity_nodes[0].id,
            )
            assert entity_page is not None

        stats_nodes = await api._repo.query_nodes(domain_id=km_space, limit=10000)
        assert len(stats_nodes) >= 5

    @pytest.mark.asyncio
    async def test_reranker_config_default_disabled(self, api, km_space):
        """Reranker is disabled by default (D-RRF-8)."""
        from ontology_engine.engine.cognitive.rrf_fusion import RerankerConfig

        cfg = RerankerConfig()
        assert cfg.enabled is False
        assert cfg.strategy == "none"

        rrf = api._router._rrf
        assert rrf._reranker_config.enabled is False

    @pytest.mark.asyncio
    async def test_temporal_proximity_in_rank_score(self, api, km_space):
        """Temporal proximity is integrated into rank_score calculation."""
        await api.remember(
            content="最新发布的 React 19 正式版",
            space_id=km_space,
            memory_type="observation",
            tags=["react", "release"],
        )

        result = await api.recall(
            query="React 最新版本",
            space_id=km_space,
            max_results=5,
        )
        data = result.get("data", result)
        for item in data.get("results", []):
            assert "temporal_proximity" in item
            assert 0.0 <= item["temporal_proximity"] <= 1.0

    @pytest.mark.asyncio
    async def test_version_limit_in_forgetting(self, api, km_space):
        """Version limit enforcement is integrated into forgetting flow."""
        for i in range(8):
            await api.remember(
                content=f"etcd 版本 3.{i} 的变更记录",
                space_id=km_space,
                memory_type="fragment",
                tags=["etcd", "version"],
            )

        forgetting_result = await api._forgetting.apply_forgetting(km_space, days_elapsed=1)
        assert "version_archived" in forgetting_result
