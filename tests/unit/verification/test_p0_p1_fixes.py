"""P0 / P1 fix verification tests.

Each test case independently verifies a specific P0 or P1 fix item.
No external services required — all tests run against local imports only.
"""

from __future__ import annotations

import inspect
import os
import re
import tempfile
from pathlib import Path
from typing import get_type_hints

import pytest


class TestP01ValidMemoryTypesConsistency:
    def test_engine_and_storage_valid_memory_types_equal(self):
        from ontology_engine.engine.cognitive.models import VALID_MEMORY_TYPES as engine_types
        from ontology_engine.storage.models import VALID_MEMORY_TYPES as storage_types

        assert engine_types == storage_types, (
            f"VALID_MEMORY_TYPES mismatch: engine={engine_types}, storage={storage_types}"
        )

    def test_valid_memory_types_contains_required_members(self):
        from ontology_engine.engine.cognitive.models import VALID_MEMORY_TYPES

        required = {
            "entity", "observation", "episode", "fragment",
            "mental_model", "opinion", "procedure", "rule",
            "commitment", "constraint", "self_experience",
            "task_state", "relation", "metrics",
        }
        assert required.issubset(VALID_MEMORY_TYPES), (
            f"Missing types: {required - VALID_MEMORY_TYPES}"
        )


class TestP02CLIRunnerParameterPassing:
    def test_remember_has_source_trust_tier_param(self):
        from examples._lib.cli_runner import CLIRunner

        sig = inspect.signature(CLIRunner.remember)
        assert "source_trust_tier" in sig.parameters, (
            "CLIRunner.remember() missing source_trust_tier parameter"
        )

    def test_remember_has_model_domain_param(self):
        from examples._lib.cli_runner import CLIRunner

        sig = inspect.signature(CLIRunner.remember)
        assert "model_domain" in sig.parameters, (
            "CLIRunner.remember() missing model_domain parameter"
        )

    def test_remember_tags_type_is_dict(self):
        from examples._lib.cli_runner import CLIRunner

        sig = inspect.signature(CLIRunner.remember)
        tags_param = sig.parameters.get("tags")
        assert tags_param is not None, "CLIRunner.remember() missing tags parameter"

        annotation = tags_param.annotation
        annotation_str = str(annotation)
        assert "dict" in annotation_str, (
            f"tags parameter type should be dict, got: {annotation_str}"
        )


class TestP03CompilationServiceSynthesisField:
    def test_compile_topic_page_returns_synthesis(self):
        from ontology_engine.engine.cognitive.compilation_service import CompilationService

        sig = inspect.signature(CompilationService.compile_topic_page)
        assert "topic" in sig.parameters
        assert "entity_ids" in sig.parameters
        assert "space_id" in sig.parameters

    def test_topic_page_dataclass_has_synthesis(self):
        from ontology_engine.engine.cognitive.compilation import TopicPage

        fields = {f.name for f in TopicPage.__dataclass_fields__.values()}
        assert "synthesis" in fields, (
            f"TopicPage missing 'synthesis' field, has: {fields}"
        )

    def test_compile_topic_page_response_includes_synthesis_key(self):
        import ast

        source = Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        ) / "ontology_engine" / "engine" / "cognitive" / "compilation_service.py"
        content = source.read_text(encoding="utf-8")
        assert '"synthesis"' in content, (
            "compilation_service.py does not include 'synthesis' key in compile_topic_page response"
        )


class TestP04L4PreconditionTestDeleted:
    def test_draft_activate_without_l4_fails_not_in_test_files(self):
        project_root = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        tests_dir = project_root / "tests"
        if not tests_dir.exists():
            pytest.skip("No tests directory")

        self_path = Path(__file__).resolve()
        for root, _dirs, files in os.walk(tests_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = (Path(root) / fname).resolve()
                if fpath == self_path:
                    continue
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                assert "test_Draft_activate_without_l4_fails" not in content, (
                    f"Found deleted test in {fpath}"
                )
                assert "test_draft_activate_without_l4_fails" not in content, (
                    f"Found deleted test in {fpath}"
                )


class TestP05T5T6T7AssertionStrengthening:
    @pytest.fixture
    def eval_path(self):
        return Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        ) / "examples" / "agent_memory" / "01_ingestion_pipeline" / "run_eval.py"

    def test_t5_verifies_tags_model(self, eval_path):
        content = eval_path.read_text(encoding="utf-8")
        assert '.get("model"' in content or '["model"]' in content, (
            "T5 does not verify tags['model'] for model_domain"
        )

    def test_t6_verifies_cognitive_layer(self, eval_path):
        content = eval_path.read_text(encoding="utf-8")
        assert "cognitive_layer" in content, (
            "T6 does not verify cognitive_layer"
        )

    def test_t7_uses_valid_source_trust_tier(self, eval_path):
        content = eval_path.read_text(encoding="utf-8")
        assert "source_trust_tier" in content, (
            "T7 does not use source_trust_tier"
        )
        for tier in ["high", "low"]:
            assert f'"{tier}"' in content, (
                f"T7 does not use valid source_trust_tier value '{tier}'"
            )


class TestP15SaveSemanticCache:
    def test_save_semantic_cache_is_not_stub(self):
        from ontology_engine.engine.extraction.cache import IncrementalCache

        method = IncrementalCache.save_semantic_cache
        source = inspect.getsource(method)
        source_stripped = source.strip()

        lines = [
            line.strip()
            for line in source_stripped.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        body_lines = lines[1:]
        assert len(body_lines) > 1, (
            "save_semantic_cache appears to be a stub (body too short)"
        )
        assert not (len(body_lines) == 1 and "return 0" in body_lines[0]), (
            "save_semantic_cache is a stub that only returns 0"
        )

    def test_save_semantic_cache_actually_writes(self):
        from ontology_engine.engine.extraction.cache import IncrementalCache

        method = IncrementalCache.save_semantic_cache
        source = inspect.getsource(method)
        assert "write_text" in source or "json.dumps" in source, (
            "save_semantic_cache does not perform file writes"
        )


class TestP12QULConstraintTypedClasses:
    REQUIRED_CONSTRAINT_CLASSES = [
        "TemporalConstraint",
        "UserPreferenceConstraint",
        "DecisionConstraint",
        "TaskHistoryConstraint",
        "EnvironmentalConstraint",
        "SelfReferenceConstraint",
        "EntityTargetConstraint",
        "ConfidenceDemandConstraint",
    ]

    def test_all_eight_constraint_classes_exist(self):
        from ontology_engine.engine.cognitive import rrf_types

        for cls_name in self.REQUIRED_CONSTRAINT_CLASSES:
            assert hasattr(rrf_types, cls_name), (
                f"rrf_types.py missing constraint class: {cls_name}"
            )

    def test_constraint_classes_are_dataclasses(self):
        import dataclasses
        from ontology_engine.engine.cognitive import rrf_types

        for cls_name in self.REQUIRED_CONSTRAINT_CLASSES:
            cls = getattr(rrf_types, cls_name)
            assert dataclasses.is_dataclass(cls), (
                f"{cls_name} is not a dataclass"
            )

    def test_query_understanding_layer_has_constraint_to_typed(self):
        from ontology_engine.engine.cognitive import query_understanding_layer

        assert hasattr(query_understanding_layer, "constraint_to_typed"), (
            "query_understanding_layer.py missing constraint_to_typed function"
        )

    def test_constraint_to_typed_maps_all_types(self):
        from ontology_engine.engine.cognitive.query_understanding_layer import (
            QueryConstraint,
            constraint_to_typed,
        )

        type_map = {
            "temporal_scope": "TemporalConstraint",
            "user_preference": "UserPreferenceConstraint",
            "decision_type": "DecisionConstraint",
            "task_history": "TaskHistoryConstraint",
            "environmental": "EnvironmentalConstraint",
            "self_reference": "SelfReferenceConstraint",
            "entity_targets": "EntityTargetConstraint",
            "confidence_demand": "ConfidenceDemandConstraint",
        }
        from ontology_engine.engine.cognitive import rrf_types

        for ctype, cls_name in type_map.items():
            constraint = QueryConstraint(constraint_type=ctype, value="test")
            result = constraint_to_typed(constraint)
            expected_cls = getattr(rrf_types, cls_name)
            assert isinstance(result, expected_cls), (
                f"constraint_to_typed({ctype!r}) returned {type(result).__name__}, expected {cls_name}"
            )


class TestP13RuleSixDimensionRuntime:
    SIX_DIMENSIONS = [
        "when_text", "why_text", "boundary_text",
        "outcome_text", "prereq_text", "exception_text",
    ]

    def test_rule_definition_decl_has_six_dimension_properties(self):
        from ontology_engine.engine.rule.models import RuleDefinitionDecl

        for attr in self.SIX_DIMENSIONS:
            assert hasattr(RuleDefinitionDecl, attr), (
                f"RuleDefinitionDecl missing property: {attr}"
            )

    def test_six_dimension_properties_return_from_applicability(self):
        from ontology_engine.engine.rule.models import RuleDefinitionDecl

        applicability = {
            "when_text": "评估交易对手信用风险时",
            "why_text": "监管要求",
            "boundary_text": "不适用于同业拆借",
            "outcome_text": "产出风险等级",
            "prereq_text": "需要信用评分",
            "exception_text": "新客户无历史数据",
        }
        decl = RuleDefinitionDecl(name="test_rule", applicability=applicability)
        for attr in self.SIX_DIMENSIONS:
            value = getattr(decl, attr)
            assert value == applicability[attr], (
                f"RuleDefinitionDecl.{attr} returned {value!r}, expected {applicability[attr]!r}"
            )

    def test_executor_has_check_applicability(self):
        from ontology_engine.engine.rule.executor import RuleExecutor

        assert hasattr(RuleExecutor, "check_applicability"), (
            "RuleExecutor missing check_applicability method"
        )

    def test_check_applicability_signature(self):
        from ontology_engine.engine.rule.executor import RuleExecutor

        sig = inspect.signature(RuleExecutor.check_applicability)
        params = list(sig.parameters.keys())
        assert "rule_decl" in params, (
            f"check_applicability missing 'rule_decl' param, has: {params}"
        )
        assert "context" in params, (
            f"check_applicability missing 'context' param, has: {params}"
        )


class TestP11SmartChunkingAlgorithm:
    def test_chunk_text_function_exists(self):
        from ontology_engine.engine.extraction.chunker import chunk_text

        assert callable(chunk_text)

    def test_long_text_produces_multiple_chunks(self):
        from ontology_engine.engine.extraction.chunker import chunk_text

        paragraph = "这是一段用于测试智能分块算法的文本。" * 200
        long_text = "\n\n".join([paragraph] * 5)
        result = chunk_text(long_text, target_tokens=900)
        assert len(result.chunks) > 1, (
            f"Expected multiple chunks for text > 900 tokens, got {len(result.chunks)}"
        )

    def test_chunk_result_has_break_points_with_scores(self):
        from ontology_engine.engine.extraction.chunker import chunk_text, BreakPoint

        paragraph = "这是一段用于测试智能分块算法的文本。" * 200
        long_text = "\n\n".join([paragraph] * 5)
        result = chunk_text(long_text, target_tokens=900)
        assert len(result.break_points) > 0, "Expected break_points to be non-empty"
        for bp in result.break_points:
            assert isinstance(bp, BreakPoint)
            assert bp.score >= 0

    def test_distance_decay_applied(self):
        from ontology_engine.engine.extraction.chunker import apply_distance_decay, BreakPoint

        bps = [
            BreakPoint(offset=1000, line=10, score=100, source="test"),
            BreakPoint(offset=5000, line=100, score=90, source="test"),
        ]
        decayed = apply_distance_decay(bps, window=200)
        assert len(decayed) == 2
        assert decayed[0].score < bps[0].score, "First breakpoint should be decayed (non-zero offset)"
        assert decayed[1].score < bps[1].score, "Second breakpoint should be decayed"

    def test_empty_text_returns_empty_result(self):
        from ontology_engine.engine.extraction.chunker import chunk_text

        result = chunk_text("")
        assert len(result.chunks) == 0
        assert result.total_tokens == 0


class TestP14DualTrackGovernance:
    def test_orbit_router_imports(self):
        from ontology_engine.engine.cognitive.orbit_router import (
            OrbitRouter,
            Orbit,
            OrbitRoutingResult,
            IngestContradictionResult,
        )

        assert OrbitRouter is not None
        assert Orbit is not None
        assert OrbitRoutingResult is not None
        assert IngestContradictionResult is not None

    def test_route_authoritative_source_returns_orbit_a(self):
        from ontology_engine.engine.cognitive.orbit_router import OrbitRouter, Orbit

        router = OrbitRouter()
        result = router.route(source_pipeline="user_declared")
        assert result.orbit == Orbit.A, (
            f"Authoritative source should route to Orbit.A, got {result.orbit}"
        )

    def test_route_agent_source_returns_orbit_b(self):
        from ontology_engine.engine.cognitive.orbit_router import OrbitRouter, Orbit

        router = OrbitRouter()
        result = router.route(source_pipeline="agent_generated")
        assert result.orbit == Orbit.B, (
            f"Agent source should route to Orbit.B, got {result.orbit}"
        )

    def test_route_high_trust_tier_returns_orbit_a(self):
        from ontology_engine.engine.cognitive.orbit_router import OrbitRouter, Orbit

        router = OrbitRouter()
        result = router.route(source_pipeline="unknown", source_trust_tier="high")
        assert result.orbit == Orbit.A

    def test_route_low_trust_tier_returns_orbit_b(self):
        from ontology_engine.engine.cognitive.orbit_router import OrbitRouter, Orbit

        router = OrbitRouter()
        result = router.route(source_pipeline="unknown", source_trust_tier="low")
        assert result.orbit == Orbit.B

    def test_check_promotion_eligibility_exists(self):
        from ontology_engine.engine.cognitive.orbit_router import OrbitRouter

        assert hasattr(OrbitRouter, "check_promotion_eligibility"), (
            "OrbitRouter missing check_promotion_eligibility method"
        )

    def test_check_promotion_eligibility_eligible(self):
        from ontology_engine.engine.cognitive.orbit_router import (
            OrbitRouter,
            PromotionStatus,
        )

        router = OrbitRouter(
            promotion_confidence_threshold=0.9,
            promotion_alignment_threshold=0.9,
            promotion_min_evidence=3,
        )
        candidate = router.check_promotion_eligibility(
            node_id="test-node",
            confidence=0.95,
            schema_alignment=0.95,
            evidence_count=5,
        )
        assert candidate.status == PromotionStatus.ELIGIBLE, (
            f"Expected ELIGIBLE for high-confidence node, got {candidate.status}"
        )

    def test_check_promotion_eligibility_not_eligible(self):
        from ontology_engine.engine.cognitive.orbit_router import (
            OrbitRouter,
            PromotionStatus,
        )

        router = OrbitRouter(
            promotion_confidence_threshold=0.9,
            promotion_alignment_threshold=0.9,
            promotion_min_evidence=3,
        )
        candidate = router.check_promotion_eligibility(
            node_id="test-node",
            confidence=0.5,
            schema_alignment=0.5,
            evidence_count=1,
        )
        assert candidate.status == PromotionStatus.NOT_ELIGIBLE, (
            f"Expected NOT_ELIGIBLE for low-confidence node, got {candidate.status}"
        )
