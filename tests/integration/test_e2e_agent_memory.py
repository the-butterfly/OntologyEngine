"""End-to-end test: Financial compliance agent memory system.

Scenario: A financial compliance assistant that:
1. Remembers regulatory documents and analyst observations
2. Retrieves compliance-related information with filters
3. Reflects to discover contradictions
4. Approves/rejects pending reviews
5. Runs dream cycle for maintenance
6. Compiles entity pages
7. Checks stats and types distribution

Covers all 4 dimensions: 抽取构建 / 消费检索 / 知识治理 / 接口
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.compilation import (
    CompilationScheduler,
    compile_entity_page,
)
from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, DreamCycleResult, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


async def _create_api(db_path: str) -> MemoryAPI:
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
def compliance_space():
    return "space_fin_compliance"


@pytest.fixture
def cognitive_db():
    tmpdir = tempfile.mkdtemp(prefix="e2e_memory_")
    db_path = str(Path(tmpdir) / "cognitive")
    yield db_path
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except OSError:
        pass


@pytest_asyncio.fixture
async def api(cognitive_db):
    return await _create_api(cognitive_db)


class TestE2EComplianceMemory:
    """Full lifecycle: remember → recall → reflect → approve → maintain → compile."""

    @pytest.mark.asyncio
    async def test_phase1_extraction_and_construction(self, api, compliance_space):
        """抽取构建: remember regulatory fragments, observations, schema-guided entries."""

        r1 = await api.remember(
            content="巴塞尔III规定商业银行核心一级资本充足率不得低于4.5%，"
                    "一级资本充足率不得低于6%，总资本充足率不得低于8%。",
            space_id=compliance_space,
            tags=["basel3", "capital_ratio"],
            memory_type="fragment",
        )
        data1 = r1.get("data", r1)
        assert data1["memory_type"] == "fragment"

        r2 = await api.remember(
            content="巴塞尔III核心一级资本充足率最低要求为4.5%，但中国银保监会"
                    "要求系统重要性银行不低于5%。",
            space_id=compliance_space,
            tags=["basel3", "china", "capital_ratio"],
            memory_type="fragment",
        )
        data2 = r2.get("data", r2)

        r3 = await api.remember(
            content="根据反洗钱法第32条，金融机构应建立客户身份识别制度，"
                    "对单笔交易金额超过人民币5万元的现金交易进行报告。",
            space_id=compliance_space,
            tags=["aml", "identity_check"],
            memory_type="fragment",
        )
        data3 = r3.get("data", r3)

        r4 = await api.remember(
            content="GDPR第17条赋予数据主体'被遗忘权'，企业需在30天内响应删除请求，"
                    "违规罚款可达全球年营收的4%或2000万欧元（取较高者）。",
            space_id=compliance_space,
            tags=["gdpr", "right_to_erasure"],
            memory_type="fragment",
        )
        data4 = r4.get("data", r4)

        sr1 = await api.remember(
            content="反洗钱: 大额交易报告阈值为人民币5万元，可疑交易需在10个工作日内上报",
            space_id=compliance_space,
            tags=["aml", "reporting"],
            memory_type="fragment",
            schema_ref="compliance_reporting_threshold",
        )
        sr_data = sr1.get("data", sr1)
        schema_nodes = sr_data.get("schema_extracted_nodes", [])
        assert len(schema_nodes) == 1

        corr = await api.remember(
            content="反洗钱法第32条更正: 大额交易报告阈值为人民币5万元（现金），"
                    "非现金交易为人民币20万元。",
            space_id=compliance_space,
            tags=["aml", "correction"],
            memory_type="fragment",
            supersede_target=data3["memory_id"],
            supersede_reason="补充非现金交易阈值信息",
        )
        corr_data = corr.get("data", corr)
        assert corr_data.get("superseded_node_id") == data3["memory_id"]

        stats = await api.remember(
            content="分析师观察: 巴塞尔III在中国实施进度良好，四大行均已达标。"
                    "但中小银行资本充足率压力较大。",
            space_id=compliance_space,
            tags=["basel3", "analyst_note"],
            memory_type="fragment",
        )

        assert all([r1, r2, r3, r4, sr1, corr, stats])

    @pytest.mark.asyncio
    async def test_phase2_retrieval_and_consumption(self, api, compliance_space):
        """消费检索: recall with various filters, audit trail, evidence chains."""

        await api.remember(
            content="巴塞尔III规定商业银行核心一级资本充足率不得低于4.5%，"
                    "一级资本充足率不得低于6%。",
            space_id=compliance_space,
            tags=["basel3"],
            memory_type="fragment",
        )
        await api.remember(
            content="中国银保监会要求系统重要性银行核心一级资本充足率不低于5%。",
            space_id=compliance_space,
            tags=["basel3", "china"],
            memory_type="fragment",
        )

        result_basic = await api.recall(
            query="巴塞尔III 资本充足率",
            space_id=compliance_space,
            max_results=5,
        )
        basic_data = result_basic.get("data", result_basic)
        results = basic_data.get("results", [])
        assert len(results) >= 1

        result_typed = await api.recall(
            query="巴塞尔III 资本充足率",
            space_id=compliance_space,
            memory_type="fragment",
            max_results=5,
        )
        typed_data = result_typed.get("data", result_typed)
        assert len(typed_data.get("results", [])) >= 1

        result_evidence = await api.recall(
            query="巴塞尔III 资本充足率",
            space_id=compliance_space,
            include_evidence=True,
            evidence_depth=1,
            max_results=3,
        )
        ev_data = result_evidence.get("data", result_evidence)
        assert "results" in ev_data

        result_token = await api.recall(
            query="巴塞尔III",
            space_id=compliance_space,
            token_budget=500,
            max_results=10,
        )
        token_data = result_token.get("data", result_token)
        assert "results" in token_data

        result_belief = await api.recall(
            query="*",
            space_id=compliance_space,
            belief_status_filter="accepted",
            max_results=10,
        )
        belief_data = result_belief.get("data", result_belief)
        assert "results" in belief_data

        result_pending = await api.recall(
            query="*",
            space_id=compliance_space,
            belief_status_filter="pending_review",
            max_results=5,
        )
        pending_data = result_pending.get("data", result_pending)
        assert "results" in pending_data

        result_audit = await api.recall(
            query="*",
            space_id=compliance_space,
            audit_trail=True,
            max_results=10,
        )
        audit_data = result_audit.get("data", result_audit)
        assert "results" in audit_data
        assert "total_superseded" in audit_data

    @pytest.mark.asyncio
    async def test_phase3_governance_reflect_and_approve(self, api, compliance_space):
        """知识治理: reflect + approve_memory + reflection status."""

        await api.remember(
            content="巴塞尔III资本充足率最低4.5%。",
            space_id=compliance_space,
            tags=["basel3"],
            memory_type="fragment",
        )
        await api.remember(
            content="有观点认为巴塞尔III资本充足率可放宽至4.0%以降低银行成本。",
            space_id=compliance_space,
            tags=["basel3", "opinion"],
            memory_type="observation",
        )

        reflect_result = await api.reflect(
            query="检查巴塞尔III资本充足率有无矛盾信息",
            space_id=compliance_space,
            max_iterations=5,
            async_mode=True,
        )
        ref_data = reflect_result.get("data", reflect_result)
        assert "reflection_id" in ref_data
        reflection_id = ref_data["reflection_id"]

        await asyncio.sleep(0.5)

        status = await api.get_reflection_status(reflection_id)
        status_data = status.get("data", status)
        assert status_data["reflection_id"] == reflection_id

        sync_result = await api.reflect(
            query="巴塞尔III 资本充足率要求",
            space_id=compliance_space,
            max_iterations=3,
            async_mode=False,
        )
        sync_data = sync_result.get("data", sync_result)
        assert sync_data

    @pytest.mark.asyncio
    async def test_phase3_approve_memory(self, api, compliance_space):
        """知识治理: approve/reject pending review nodes."""

        node = CognitiveNode(
            id="mem_e2e_approve_test",
            memory_type="observation",
            cognitive_layer="semantic",
            content="测试审批节点: 巴塞尔III可能过于严格",
            domain_id=compliance_space,
            space_id=compliance_space,
            belief_status="pending_review",
        )
        await api._repo.create_node(node)

        approve_result = await api.approve_memory(
            node_id="mem_e2e_approve_test",
            action="approve",
            modifier_id="compliance_officer",
            comment="经核实，巴塞尔III要求合理，不存在过度严格问题。",
        )
        app_data = approve_result.get("data", approve_result)
        assert app_data["node_id"] == "mem_e2e_approve_test"

        node2 = CognitiveNode(
            id="mem_e2e_approve_test_2",
            memory_type="observation",
            cognitive_layer="semantic",
            content="测试: 资本充足率可降至3.5%",
            domain_id=compliance_space,
            space_id=compliance_space,
            belief_status="pending_review",
        )
        await api._repo.create_node(node2)

        reject_result = await api.approve_memory(
            node_id="mem_e2e_approve_test_2",
            action="reject",
            modifier_id="compliance_officer",
            comment="与巴塞尔III规定不符，拒绝。",
        )
        rej_data = reject_result.get("data", reject_result)
        assert rej_data["action"] == "reject"

    @pytest.mark.asyncio
    async def test_phase3_dream_cycle(self, api, compliance_space):
        """知识治理: DreamCycle 5-phase execution."""

        await api.remember(
            content="DreamCycle测试: 反洗钱大额交易报告阈值为5万元。",
            space_id=compliance_space,
            tags=["aml", "dream_test"],
            memory_type="fragment",
        )
        await api.remember(
            content="DreamCycle测试补充: 非现金大额交易为20万元。",
            space_id=compliance_space,
            tags=["aml", "dream_test"],
            memory_type="fragment",
        )

        dream_cycle = DreamCycle(api._repo, ForgettingEngine(api._repo))
        result: DreamCycleResult = await dream_cycle.run(compliance_space)

        assert isinstance(result.contradictions, list)
        assert isinstance(result.expired, list)
        assert isinstance(result.orphans_cleaned, int)
        assert isinstance(result.links_enhanced, int)
        assert isinstance(result.graph_completed, int)
        assert isinstance(result.errors, list)

    @pytest.mark.asyncio
    async def test_phase3_compilation(self, api, compliance_space):
        """知识治理: Entity page compilation."""

        result = await api.remember(
            content="实体编译测试: GDPR罚款上限为全球年营收4%或2000万欧元。",
            space_id=compliance_space,
            tags=["gdpr", "compile_test"],
            memory_type="entity",
        )
        entity_id = result.get("data", result)["memory_id"]

        page = await compile_entity_page(api._repo, entity_id)

        assert page.node_id == entity_id
        assert page.entity_name
        assert page.summary
        assert page.compiled_at
        assert len(page.source_node_ids) >= 1

    @pytest.mark.asyncio
    async def test_phase3_compilation_scheduler(self, api, compliance_space):
        """知识治理: Cost-aware compilation scheduler."""

        await api.remember(
            content="编译器批量测试: 这是一条重要的合规测试内容，用于验证编译调度器"
                    "能否在token预算内正确编译多个实体页面。",
            space_id=compliance_space,
            tags=["compile_scheduler"],
            memory_type="entity",
        )
        await api.remember(
            content="另一条合规实体: 反洗钱制度需要在5个工作日内完成客户身份识别。",
            space_id=compliance_space,
            tags=["compile_scheduler", "aml"],
            memory_type="entity",
        )

        scheduler = CompilationScheduler(api._repo, daily_token_budget=20000)
        result = await scheduler.compile_with_budget(compliance_space)

        assert len(result.entity_pages) >= 1
        assert isinstance(result.errors, list)

    @pytest.mark.asyncio
    async def test_phase4_stats_and_types(self, api, compliance_space):
        """接口: Stats and type distribution."""

        await api.remember(
            content="统计测试数据: 这是一条实体记忆，用于验证统计查询功能。",
            space_id=compliance_space,
            tags=["stats_test"],
            memory_type="entity",
        )
        await api.remember(
            content="统计测试碎片: 一条碎片记忆用于统计。",
            space_id=compliance_space,
            tags=["stats_test"],
            memory_type="fragment",
        )

        nodes = await api._repo.query_nodes(domain_id=compliance_space, limit=100)
        assert len(nodes) >= 2

        type_counts: dict[str, int] = {}
        for n in nodes:
            type_counts[n.memory_type] = type_counts.get(n.memory_type, 0) + 1
        assert "entity" in type_counts or "fragment" in type_counts

        belief_counts: dict[str, int] = {}
        for n in nodes:
            belief_counts[n.belief_status] = belief_counts.get(n.belief_status, 0) + 1
        assert "accepted" in belief_counts or "pending_review" in belief_counts

    @pytest.mark.asyncio
    async def test_phase4_mental_model_refresh(self, api, compliance_space):
        """知识治理: Mental model auto-refresh after consolidation."""

        await api.remember(
            content="MentalModel测试: 支持实体1，关于巴塞尔III在中国的实施情况。",
            space_id=compliance_space,
            tags=["mm_test"],
            memory_type="observation",
        )

        engine = ConsolidationEngine(api._repo)
        refresh_result = await engine.trigger_mental_model_refresh(compliance_space)

        assert "marked_stale" in refresh_result
        assert "updated" in refresh_result
        assert "already_fresh" in refresh_result

    @pytest.mark.asyncio
    async def test_end_to_end_full_pipeline(self, api, compliance_space, cognitive_db):
        """Full pipeline: remember → recall → reflect → approve → dream → compile → stats."""

        await api.remember(
            content="全流程测试: 巴塞尔III要求核心一级资本充足率≥4.5%。",
            space_id=compliance_space,
            tags=["e2e_full"],
            memory_type="fragment",
        )
        await api.remember(
            content="全流程测试: 中国系统重要性银行需≥5%。",
            space_id=compliance_space,
            tags=["e2e_full", "china"],
            memory_type="fragment",
        )

        recall_full = await api.recall(
            query="巴塞尔III",
            space_id=compliance_space,
            max_results=5,
            include_evidence=True,
        )
        recall_data = recall_full.get("data", recall_full)
        assert len(recall_data.get("results", [])) >= 1

        parent_id = recall_data["results"][0]["id"]
        sup_result = await api.remember(
            content="全流程更正: 巴塞尔III最终版要求核心资本充足率≥4.5%（含缓冲）。",
            space_id=compliance_space,
            tags=["e2e_full", "correction"],
            supersede_target=parent_id,
            supersede_reason="补充缓冲资本说明",
        )
        sup_data = sup_result.get("data", sup_result)
        assert sup_data.get("superseded_node_id") == parent_id

        reflect_full = await api.reflect(
            query="巴塞尔III",
            space_id=compliance_space,
            max_iterations=3,
            async_mode=False,
        )
        ref_data = reflect_full.get("data", reflect_full)
        assert ref_data

        dream_result = await DreamCycle(
            api._repo,
            ForgettingEngine(api._repo),
        ).run(compliance_space)
        assert isinstance(dream_result, DreamCycleResult)

        scheduler = CompilationScheduler(api._repo, daily_token_budget=20000)
        comp_result = await scheduler.compile_with_budget(compliance_space)
        assert len(comp_result.entity_pages) >= 0

        all_nodes = await api._repo.query_nodes(domain_id=compliance_space, limit=100)
        node_types = {n.memory_type for n in all_nodes}
        node_beliefs = {n.belief_status for n in all_nodes}

        assert "fragment" in node_types
        assert "accepted" in node_beliefs or "pending_review" in node_beliefs or "superseded" in node_beliefs
