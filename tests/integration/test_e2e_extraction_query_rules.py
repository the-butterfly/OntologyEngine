"""End-to-end integration test: Extraction → Retrieval → Rule Execution.

Covers the changes from Phase 7D/7B/7G and S-2/S-4 fixes:
- Phase 7D: ExpressionEngine L0/L1 auto-selection + 43 functions
- Phase 7B: QueryRouter, LayerRRetriever, LayerSRetriever, RRFFusion
- Phase 7G: ASTExtractor, LLMExtractor, DedupStrategy, IncrementalCache
- S-2 fix: DEFINED_IN_FROM_METRIC edge in LadybugGraphStore
- S-4 fix: as_of/include_history temporal parameters in query traverse
"""

import os
import tempfile

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from ontology_engine.api.server import create_app
from ontology_engine.api import dependencies
from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.storage.base import EntityInstance, RelationInstance
from ontology_engine.services import QueryService, EntityService, SchemaService
from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata, ConceptDefinition
from ontology_engine.engine.expression.engine import ExpressionEngine
from ontology_engine.engine.expression.errors import (
    FormulaError,
    FormulaSecurityError,
    FormulaSyntaxError,
)
from ontology_engine.engine.query.router import (
    QueryType,
    detect_query_type,
    build_retrieval_params,
)
from ontology_engine.engine.query.rrf_fusion import RRFFusion, RRFDocument
from ontology_engine.engine.extraction.ast_extractor import ASTExtractor
from ontology_engine.engine.extraction.dedup import DedupStrategy
from ontology_engine.engine.extraction.cache import IncrementalCache
from ontology_engine.engine.extraction.pipeline import ExtractionPipeline
from ontology_engine.engine.rule.models import (
    ActionClause,
    ConditionClause,
    ExecutionContext,
    RuleStep,
)
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.dag_executor import DAGExecutor
from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def storage():
    s = SQLiteStorage(db_path=":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def seeded_storage(storage):
    entities = [
        EntityInstance(
            _fact_object="Counterparty",
            entity_id="CP_001",
            data={
                "name": "Acme Corp",
                "status": "ACTIVE",
                "credit_rating": "BBB",
                "overdue_ratio": 3.5,
                "contract_fulfillment_rate": 85,
            },
        ),
        EntityInstance(
            _fact_object="Counterparty",
            entity_id="CP_002",
            data={
                "name": "Beta Ltd",
                "status": "INACTIVE",
                "credit_rating": "CCC",
                "overdue_ratio": 12.0,
                "contract_fulfillment_rate": 45,
            },
        ),
        EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_001",
            data={"amount": 100000, "status": "PAID", "valid_from": "2025-01-01", "valid_to": "2025-12-31"},
        ),
        EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_002",
            data={"amount": 200000, "status": "OVERDUE", "valid_from": "2025-06-01", "valid_to": None},
        ),
        EntityInstance(
            _fact_object="Contract",
            entity_id="CTR_001",
            data={"contract_amount": 500000, "start_date": "2025-01-01", "end_date": "2025-12-31"},
        ),
    ]
    for e in entities:
        await storage.save_entity(e)

    relations = [
        RelationInstance(relation_name="has_invoice", from_entity_id="CP_001", to_entity_id="INV_001", data={}),
        RelationInstance(relation_name="has_invoice", from_entity_id="CP_001", to_entity_id="INV_002", data={}),
        RelationInstance(relation_name="has_contract", from_entity_id="CP_001", to_entity_id="CTR_001", data={}),
        RelationInstance(relation_name="has_invoice", from_entity_id="CP_002", to_entity_id="INV_002", data={}),
    ]
    for r in relations:
        await storage.save_relation(r)

    return storage


@pytest_asyncio.fixture
async def app(seeded_storage):
    application = create_app()

    schema = KGMLSchema(
        metadata=SchemaMetadata(id="test", name="test", version="1.0"),
        concepts=[
            ConceptDefinition(name="Counterparty", description="A counterparty"),
            ConceptDefinition(name="Invoice", description="An invoice"),
            ConceptDefinition(name="Contract", description="A contract"),
        ],
        metrics=[],
        rules=None,
    )

    services = {
        "schema": SchemaService(storage=seeded_storage),
        "entity": EntityService(storage=seeded_storage, schema=schema),
        "query": QueryService(storage=seeded_storage),
    }
    dependencies.init_dependencies(seeded_storage, services)

    yield application

    dependencies.init_dependencies(None, {})


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Phase 7D: Expression Engine L0/L1
# =============================================================================


class TestExpressionEngineL0L1:
    """Test L0/L1 auto-selection and extended function library."""

    def test_l0_simple_arithmetic(self):
        engine = ExpressionEngine()
        assert engine.evaluate("1 + 2") == 3
        assert engine.evaluate("10 * 5 - 3") == 47

    def test_l0_comparison(self):
        engine = ExpressionEngine()
        assert engine.evaluate("5 > 3") is True
        assert engine.evaluate("5 < 3") is False

    def test_l0_string_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("upper('hello')") == "HELLO"
        assert engine.evaluate("lower('WORLD')") == "world"
        assert engine.evaluate("trim('  hi  ')") == "hi"
        assert engine.evaluate("len('abc')") == 3
        assert engine.evaluate("contains('hello', 'ell')") is True
        assert engine.evaluate("starts_with('hello', 'hel')") is True
        assert engine.evaluate("ends_with('hello', 'llo')") is True

    def test_l0_conditional_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("coalesce(None, None, 42)") == 42
        assert engine.evaluate("if_expr(True, 1, 0)") == 1
        assert engine.evaluate("if_expr(False, 1, 0)") == 0
        assert engine.evaluate("is_null(None)") is True
        assert engine.evaluate("is_null(42)") is False

    def test_l0_math_functions(self):
        engine = ExpressionEngine()
        assert engine.evaluate("ceil(3.1)") == 4
        assert engine.evaluate("floor(3.9)") == 3
        assert engine.evaluate("sqrt(100)") == 10.0
        assert engine.evaluate("clamp(15, 0, 10)") == 10

    def test_l0_date_functions(self):
        engine = ExpressionEngine()
        assert isinstance(engine.evaluate("today()"), str)
        assert isinstance(engine.evaluate("now()"), str)
        assert engine.evaluate("year('2026-04-19')") == 2026
        assert engine.evaluate("month('2026-04-19')") == 4
        assert engine.evaluate("day('2026-04-19')") == 19

    def test_l1_multiline_expression(self):
        engine = ExpressionEngine()
        result = engine.evaluate("""
score = 50
if score >= 80:
    result = 20
else:
    if score >= 60:
        result = 10
    else:
        result = 0
result
""")
        assert result == 0

    def test_l1_list_aggregate(self):
        engine = ExpressionEngine()
        assert engine.evaluate("sum([1, 2, 3])") == 6
        assert engine.evaluate("avg([10, 20, 30])") == 20.0
        assert engine.evaluate("count([1, None, 3])") == 2

    def test_l0_fallback_to_l1(self):
        engine = ExpressionEngine()
        result = engine.evaluate("sum(items)", {"items": [1, 2, 3]})
        assert result == 6

    def test_security_bitwise_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises((FormulaSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("1 << 2")

    def test_security_mod_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises((FormulaSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("10 % 3")

    def test_security_import_blocked(self):
        engine = ExpressionEngine()
        with pytest.raises((FormulaSyntaxError, FormulaSecurityError, FormulaError)):
            engine.evaluate("__import__('os').system('ls')")

    def test_function_count(self):
        engine = ExpressionEngine()
        assert len(engine.SAFE_FUNCTIONS) >= 40

    def test_auto_selection_l0(self):
        engine = ExpressionEngine()
        assert engine._select_executor("1 + 2") == "l0"

    def test_auto_selection_l1_multiline(self):
        engine = ExpressionEngine()
        assert engine._select_executor("x = 1\ny = 2") == "l1"

    def test_auto_selection_l1_control_flow(self):
        engine = ExpressionEngine()
        assert engine._select_executor("if x > 0: pass") == "l1"

    def test_auto_selection_l1_list_literal(self):
        engine = ExpressionEngine()
        assert engine._select_executor("sum([1, 2, 3])") == "l1"


# =============================================================================
# Phase 7B: Query Engine
# =============================================================================


class TestQueryRouter:
    """Test query type detection and retrieval params."""

    def test_factual_query(self):
        assert detect_query_type("谁是供应商A") == QueryType.FACTUAL
        assert detect_query_type("what is the invoice amount") == QueryType.FACTUAL

    def test_multi_hop_query(self):
        result = detect_query_type("如何导致影响")
        assert result in (QueryType.MULTI_HOP, QueryType.MIXED)

    def test_temporal_query(self):
        result = detect_query_type("历史趋势")
        assert result in (QueryType.TEMPORAL, QueryType.MIXED)

    def test_analytical_query(self):
        assert detect_query_type("计算信用评分") == QueryType.ANALYTICAL
        assert detect_query_type("calculate risk score") == QueryType.ANALYTICAL

    def test_mixed_query(self):
        result = detect_query_type("为什么信用评分的历史变化趋势")
        assert result == QueryType.MIXED

    def test_default_factual(self):
        assert detect_query_type("random text") == QueryType.FACTUAL

    def test_retrieval_params_factual(self):
        params = build_retrieval_params(QueryType.FACTUAL)
        assert params.chroma_top_k == 10
        assert params.rrf_weights["layer_r"] == 0.6
        assert params.rrf_weights["layer_s"] == 0.2

    def test_retrieval_params_multi_hop(self):
        params = build_retrieval_params(QueryType.MULTI_HOP)
        assert params.ladybug_max_depth == 3
        assert params.bundle_search_enabled is True
        assert params.rrf_weights["layer_s"] == 0.5

    def test_retrieval_params_temporal(self):
        params = build_retrieval_params(QueryType.TEMPORAL)
        assert params.temporal_filter is True

    def test_retrieval_params_analytical(self):
        params = build_retrieval_params(QueryType.ANALYTICAL)
        assert params.trace_to_backtrack is True
        assert params.rrf_weights["layer_r"] == 0.0


class TestRRFFusion:
    """Test RRF fusion with query-type weights."""

    def test_fusion_basic(self):
        fusion = RRFFusion(k=60)
        layer_r = [
            RRFDocument(doc_id="a", doc_type="fragment", score=0.9, source="layer_r"),
            RRFDocument(doc_id="b", doc_type="fragment", score=0.8, source="layer_r"),
        ]
        layer_s = [
            RRFDocument(doc_id="a", doc_type="entity", score=0.7, source="layer_s"),
            RRFDocument(doc_id="c", doc_type="entity", score=0.6, source="layer_s"),
        ]
        result = fusion.fuse(layer_r, layer_s, weights={"layer_r": 0.6, "layer_s": 0.4})
        ids = [d.doc_id for d in result]
        assert "a" in ids
        assert "b" in ids
        assert "c" in ids
        a_doc = next(d for d in result if d.doc_id == "a")
        assert a_doc.score > 0

    def test_fusion_dedup_same_id(self):
        fusion = RRFFusion(k=60)
        layer_r = [RRFDocument(doc_id="x", doc_type="fragment", score=0.9, source="layer_r")]
        layer_s = [RRFDocument(doc_id="x", doc_type="entity", score=0.8, source="layer_s")]
        result = fusion.fuse(layer_r, layer_s)
        assert len(result) == 1
        assert result[0].score > 0

    def test_fusion_empty_inputs(self):
        fusion = RRFFusion(k=60)
        result = fusion.fuse([], [])
        assert result == []


# =============================================================================
# Phase 7G: Extraction Pipeline
# =============================================================================


class TestASTExtractor:
    """Test AST extraction from source files."""

    def test_extract_python_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class Counterparty:\n    pass\n\ndef calculate_score():\n    pass\n")
            f.flush()
            try:
                extractor = ASTExtractor()
                result = extractor.extract(f.name)
                assert len(result.entities) >= 3
                fact_objects = [e["_fact_object"] for e in result.entities]
                assert "code:File" in fact_objects
                assert "code:Class" in fact_objects
                assert "code:Function" in fact_objects
                assert len(result.edges) >= 2
                assert len(result.extracted_from_edges) >= 2
            finally:
                os.unlink(f.name)

    def test_extract_markdown_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\n## Section 1\n\nContent\n### Subsection\n")
            f.flush()
            try:
                extractor = ASTExtractor()
                result = extractor.extract(f.name)
                assert len(result.entities) >= 4
                fact_objects = [e["_fact_object"] for e in result.entities]
                assert "doc:Document" in fact_objects
                assert "doc:Heading" in fact_objects
            finally:
                os.unlink(f.name)

    def test_extract_nonexistent_file(self):
        extractor = ASTExtractor()
        result = extractor.extract("/nonexistent/file.py")
        assert len(result.entities) == 0

    def test_identify_language(self):
        extractor = ASTExtractor()
        assert extractor.identify_language("test.py") is not None
        assert extractor.identify_language("test.py").name == "python"
        assert extractor.identify_language("test.md") is not None
        assert extractor.identify_language("test.yaml") is not None
        assert extractor.identify_language("test.xyz") is None


class TestDedupStrategy:
    """Test entity/edge dedup and contradiction detection."""

    def test_dedup_entities_by_id(self):
        strategy = DedupStrategy()
        entities = [
            {"entity_id": "E1", "_fact_object": "A", "confidence": 0.7, "attributes": {"name": "X"}},
            {"entity_id": "E1", "_fact_object": "A", "confidence": 0.9, "attributes": {"name": "X", "extra": "Y"}},
        ]
        result = strategy.dedup_entities(entities)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.9
        assert result[0]["attributes"].get("extra") == "Y"

    def test_dedup_entities_ast_priority(self):
        strategy = DedupStrategy()
        entities = [
            {"entity_id": "E1", "_fact_object": "A", "confidence": 1.0, "source_pipeline": "ast_extraction", "attributes": {"name": "X"}},
            {"entity_id": "E1", "_fact_object": "A", "confidence": 0.7, "source_pipeline": "llm_extraction", "attributes": {"name": "X", "desc": "from LLM"}},
        ]
        result = strategy.dedup_entities(entities)
        assert len(result) == 1
        assert result[0]["source_pipeline"] == "ast_extraction"
        assert result[0]["attributes"].get("desc") == "from LLM"

    def test_dedup_edges(self):
        strategy = DedupStrategy()
        edges = [
            {"from_id": "A", "to_id": "B", "relation_name": "rel", "source_pipeline": "ast", "confidence": 0.8},
            {"from_id": "A", "to_id": "B", "relation_name": "rel", "source_pipeline": "ast", "confidence": 0.9},
        ]
        result = strategy.dedup_edges(edges)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.9

    def test_contradiction_detection(self):
        strategy = DedupStrategy()
        entities = [
            {"entity_id": "E1", "confidence": 0.9, "source_pipeline": "ast", "attributes": {"status": "ACTIVE"}},
            {"entity_id": "E1", "confidence": 0.8, "source_pipeline": "llm", "attributes": {"status": "INACTIVE"}},
        ]
        contradictions = strategy.detect_contradictions(entities, entities[:1])
        assert len(contradictions) >= 1
        assert contradictions[0].attribute == "status"
        assert contradictions[0].severity == "high"


class TestIncrementalCache:
    """Test 3-layer cache: AST + semantic + checkpoints."""

    def test_ast_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = IncrementalCache(cache_dir=os.path.join(tmpdir, "cache"))
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("class Foo: pass\n")

            from pathlib import Path
            result = {"entities": [{"id": "1"}], "edges": [], "extracted_from_edges": []}
            cache.save_ast_cache(Path(test_file), result, Path(tmpdir))

            loaded = cache.load_ast_cache(Path(test_file), Path(tmpdir))
            assert loaded is not None
            assert len(loaded["entities"]) == 1

    def test_semantic_cache_miss(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = IncrementalCache(cache_dir=os.path.join(tmpdir, "cache"))
            cached_e, cached_ed, cached_c, uncached = cache.check_semantic_cache(
                ["nonexistent.py"], Path(tmpdir)
            )
            assert len(uncached) == 1

    def test_checkpoint_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = IncrementalCache(cache_dir=os.path.join(tmpdir, "cache"))
            cache.create_checkpoint("run_001")

            cp = cache.load_checkpoint("run_001")
            assert cp is not None
            assert cp["run_id"] == "run_001"

            cache.update_checkpoint("run_001", "test.py", {"entities": [{"id": "1"}]})
            cp = cache.load_checkpoint("run_001")
            assert cp["processed_files"] == 1

            cache.clear_checkpoint("run_001")
            assert cache.load_checkpoint("run_001") is None


class TestExtractionPipeline:
    """Test 3-pass extraction pipeline orchestrator."""

    def test_ingest_python_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, "cache")
            test_file = os.path.join(tmpdir, "counterparty.py")
            with open(test_file, "w") as f:
                f.write("class Counterparty:\n    pass\n\ndef calculate_risk():\n    pass\n")

            pipeline = ExtractionPipeline(cache_dir=cache_dir)
            result = pipeline.ingest([test_file], root=tmpdir)

            assert len(result.unique_entities) >= 3
            assert len(result.extracted_from_edges) >= 2
            fact_objects = [e["_fact_object"] for e in result.unique_entities]
            assert "code:File" in fact_objects
            assert "code:Class" in fact_objects

    def test_ingest_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = ExtractionPipeline(cache_dir=os.path.join(tmpdir, "cache"))
            result = pipeline.ingest([], root=tmpdir)
            assert len(result.unique_entities) == 0


# =============================================================================
# S-4 Fix: Temporal Parameters in Query API
# =============================================================================


class TestTemporalQueryParameters:
    """Test as_of/include_history parameters through API."""

    @pytest.mark.asyncio
    async def test_traverse_with_as_of(self, client):
        resp = await client.get(
            "/v1/query/traverse/CP_001",
            params={
                "relation_name": "has_invoice",
                "direction": "outgoing",
                "depth": 1,
                "as_of": "2025-06-15T00:00:00",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_traverse_with_include_history(self, client):
        resp = await client.get(
            "/v1/query/traverse/CP_001",
            params={
                "relation_name": "has_invoice",
                "direction": "outgoing",
                "depth": 1,
                "include_history": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_traverse_post_with_temporal(self, client):
        resp = await client.post(
            "/v1/query/traverse/CP_001",
            json={
                "relation_name": "has_invoice",
                "direction": "outgoing",
                "depth": 1,
                "as_of": "2025-06-15T00:00:00",
                "include_history": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_graph_query_with_temporal(self, client):
        resp = await client.post(
            "/v1/query/graph",
            json={
                "start": {"entity_id": "CP_001"},
                "traverse": [{"relation_name": "has_invoice", "direction": "outgoing", "max_hops": 1}],
                "as_of": "2025-06-15T00:00:00",
                "include_history": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True


# =============================================================================
# DAG Rule Execution with L0/L1 Expressions
# =============================================================================


@OperatorRegistry.register("e2e_compute_score")
class E2EComputeScoreOperator(Operator):
    @property
    def name(self) -> str:
        return "e2e_compute_score"

    async def execute(self, inputs: dict, config: dict, context: dict) -> dict:
        base = inputs.get("base_score", 50)
        bonus = inputs.get("bonus", 10)
        return {"score": base + bonus}


@OperatorRegistry.register("e2e_apply_formula")
class E2EApplyFormulaOperator(Operator):
    @property
    def name(self) -> str:
        return "e2e_apply_formula"

    async def execute(self, inputs: dict, config: dict, context: dict) -> dict:
        formula = inputs.get("formula", "0")
        engine = ExpressionEngine()
        try:
            result = engine.evaluate(formula, context)
            return {"result": result, "formula": formula}
        except FormulaError:
            return {"result": None, "formula": formula}


class TestRuleExecutionWithExpressions:
    """Test DAG rule execution using L0/L1 expression engine."""

    @pytest.mark.asyncio
    async def test_dag_linear_execution(self):
        steps = [
            RuleStep(
                id="step_base",
                name="Compute Base Score",
                rule_group="credit_scoring",
                order=1,
                when=ConditionClause(expression="overdue_ratio < 5"),
                then=ActionClause(
                    operator="e2e_compute_score",
                    params={"base_score": 70, "bonus": 20},
                    output_mapping={"score": "base_score"},
                ),
            ),
            RuleStep(
                id="step_penalty",
                name="Apply Penalty",
                rule_group="credit_scoring",
                order=2,
                when=ConditionClause(expression="overdue_ratio >= 5"),
                then=ActionClause(
                    operator="e2e_compute_score",
                    params={"base_score": 40, "bonus": 0},
                    output_mapping={"score": "penalty_score"},
                ),
            ),
        ]

        builder = DAGBuilder()
        dag = builder.build(steps)
        executor = DAGExecutor()

        context = ExecutionContext(entity_id="CP_001", dimension="credit", entity_data={"overdue_ratio": 3.5})
        result = await executor.execute(dag, context)
        assert isinstance(result.results, dict)

    @pytest.mark.asyncio
    async def test_dag_with_depends_on(self):
        steps = [
            RuleStep(
                id="step_compute",
                name="Compute",
                rule_group="chained_scoring",
                order=1,
                when=ConditionClause(expression="True"),
                then=ActionClause(
                    operator="e2e_compute_score",
                    params={"base_score": 60, "bonus": 15},
                    output_mapping={"score": "computed_score"},
                ),
            ),
            RuleStep(
                id="step_formula",
                name="Apply Formula",
                rule_group="chained_scoring",
                order=2,
                depends_on=["step_compute"],
                when=ConditionClause(expression="True"),
                then=ActionClause(
                    operator="e2e_apply_formula",
                    params={"formula": "clamp(score, 0, 100)"},
                    output_mapping={"result": "final_score"},
                ),
            ),
        ]

        builder = DAGBuilder()
        dag = builder.build(steps)
        assert len(dag.layers) >= 1

        executor = DAGExecutor()
        context = ExecutionContext(entity_id="CP_001", dimension="credit", entity_data={"score": 75})
        result = await executor.execute(dag, context)
        assert isinstance(result.results, dict)


# =============================================================================
# Full E2E Flow: Ingest → Query → Rule Execute via API
# =============================================================================


class TestFullE2EFlow:
    """End-to-end: create entities → traverse graph → execute rules."""

    @pytest.mark.asyncio
    async def test_create_and_traverse(self, client):
        resp = await client.get(
            "/v1/query/traverse/CP_001",
            params={"relation_name": "has_invoice", "direction": "outgoing", "depth": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert len(results) == 2
        neighbor_ids = {r["entity_id"] for r in results}
        assert "INV_001" in neighbor_ids
        assert "INV_002" in neighbor_ids

    @pytest.mark.asyncio
    async def test_create_and_pattern_match(self, client):
        resp = await client.get("/v1/query/pattern-match/Counterparty")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_create_and_path_finding(self, client):
        resp = await client.get("/v1/query/path/CP_001/INV_001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        paths = body["data"]["paths"]
        assert len(paths) >= 1

    @pytest.mark.asyncio
    async def test_graph_query_with_traverse(self, client):
        resp = await client.post(
            "/v1/query/graph",
            json={
                "start": {"entity_id": "CP_001"},
                "traverse": [
                    {"relation_name": "has_invoice", "direction": "outgoing", "max_hops": 1},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_with_fact_object_field(self, client):
        resp = await client.get(
            "/v1/query/pattern-match/Counterparty",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        for r in results:
            assert "fact_object" in r
            assert r["fact_object"] == "Counterparty"
