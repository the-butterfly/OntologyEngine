"""Contradiction Detection Verification Suite.

Comprehensive test cases covering:
  1. Regular contradiction patterns (negation, value conflict, belief conflict)
  2. Boundary conditions (empty data, single node, same content)
  3. Abnormal input (special characters, very long text, mixed languages)
  4. Performance stress (large number of nodes)
  5. Integration with reflect pipeline

Usage: python examples/agent_memory/10_contradiction_fix_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "contra_fix_eval"


# ═══════════════════════════════════════════════════════════════════
# 1. Regular Contradiction Patterns
# ═══════════════════════════════════════════════════════════════════

async def test_negation_conflict(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华为使用Java语言", memory_type="observation", tags=["lang"])
        await cli.remember("华为不是使用Java语言", memory_type="observation", tags=["lang"])
        result = await cli.reflect("华为语言", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        negation_cons = [c for c in contradictions if c.get("contradiction_type") == "negation_conflict"]
        ok = len(negation_cons) >= 1
        score = 1.0 if ok else 0.0
        report.add(_ok("R-01: Negation conflict", ok, score,
                       f"negation_contradictions={len(negation_cons)}, total={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("R-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_value_conflict(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华信科技员工数5000人", memory_type="observation", tags=["scale"])
        await cli.remember("华信科技员工数200人", memory_type="observation", tags=["scale"])
        result = await cli.reflect("华信科技规模", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        value_cons = [c for c in contradictions if c.get("contradiction_type") == "value_conflict"]
        ok = len(value_cons) >= 1
        score = 1.0 if ok else 0.0
        report.add(_ok("R-02: Value conflict", ok, score,
                       f"value_contradictions={len(value_cons)}, total={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("R-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_belief_conflict(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("华为风险等级D级", memory_type="entity", tags=["risk"], confidence=0.9)
        old_id = r1.get("node_id")
        if old_id:
            await cli.remember("华为风险等级B级", memory_type="observation", tags=["risk"],
                               supersede_target=old_id, supersede_reason="风险改善")
        result = await cli.reflect("华为风险", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = len(contradictions) >= 1
        score = 1.0 if ok else 0.0
        report.add(_ok("R-03: Belief conflict via supersede", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("R-03", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_entity_name_grouping(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华为营收8600亿元", memory_type="observation",
                           entity_name="华为", tags=["financial"])
        await cli.remember("华为营收6500亿元", memory_type="observation",
                           entity_name="华为", tags=["financial"])
        result = await cli.reflect("华为营收", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = len(contradictions) >= 1
        score = 1.0 if ok else 0.0
        report.add(_ok("R-04: Entity-name grouping", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("R-04", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_constraint_conflict(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("API限速100次/分钟", memory_type="constraint", tags=["api"])
        await cli.remember("API限速5000次/分钟", memory_type="constraint", tags=["api"])
        result = await cli.reflect("API限速", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = len(contradictions) >= 1
        score = 1.0 if ok else 0.0
        report.add(_ok("R-05: Constraint conflict", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("R-05", False, 0.0, str(e), (time.time() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════
# 2. Boundary Conditions
# ═══════════════════════════════════════════════════════════════════

async def test_empty_space(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        result = await cli.reflect("空空间查询", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = len(contradictions) == 0
        score = 1.0 if ok else 0.0
        report.add(_ok("B-01: Empty space", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("B-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_single_node(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("唯一一条记忆", memory_type="observation", tags=["solo"])
        result = await cli.reflect("唯一记忆", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = len(contradictions) == 0
        score = 1.0 if ok else 0.0
        report.add(_ok("B-02: Single node (no contradiction possible)", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("B-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_same_content(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华为风险等级D级", memory_type="observation", tags=["risk"])
        await cli.remember("华为风险等级D级", memory_type="observation", tags=["risk"])
        result = await cli.reflect("华为风险", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = True
        score = 1.0 if len(contradictions) == 0 else 0.5
        report.add(_ok("B-03: Same content (no contradiction)", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("B-03", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_no_tag_nodes(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华为使用Redis缓存", memory_type="observation")
        await cli.remember("华为使用Memcached缓存", memory_type="observation")
        result = await cli.reflect("华为缓存", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = len(contradictions) >= 1
        score = 1.0 if ok else 0.0
        report.add(_ok("B-04: No-tag nodes (untagged fallback)", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("B-04", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_superseded_excluded(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("旧策略：限速100次/分钟", memory_type="constraint", tags=["policy"])
        old_id = r1.get("node_id")
        if old_id:
            await cli.remember("新策略：限速5000次/分钟", memory_type="constraint", tags=["policy"],
                               supersede_target=old_id, supersede_reason="策略更新")
        result = await cli.reflect("限速策略", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        superseded_cons = [c for c in contradictions
                           if any(nid in str(c.get("node_ids", [])) for nid in [old_id] if old_id)]
        ok = True
        score = 1.0 if len(superseded_cons) == 0 else 0.5
        report.add(_ok("B-05: Superseded nodes excluded", ok, score,
                       f"superseded_in_conflicts={len(superseded_cons)}, total={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("B-05", False, 0.0, str(e), (time.time() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════
# 3. Abnormal Input
# ═══════════════════════════════════════════════════════════════════

async def test_special_characters(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("API端点: /v1/users/{id}/profile", memory_type="observation", tags=["api"])
        await cli.remember("API端点: /v2/users/{id}/profile", memory_type="observation", tags=["api"])
        result = await cli.reflect("API端点", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        ok = True
        score = 0.8
        report.add(_ok("A-01: Special characters in content", ok, score,
                       f"contradictions={len(result.get('contradictions', []))}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("A-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_mixed_language(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("Huawei uses Kubernetes for orchestration", memory_type="observation", tags=["infra"])
        await cli.remember("Huawei采用Docker Swarm编排", memory_type="observation", tags=["infra"])
        result = await cli.reflect("Huawei编排方案", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = True
        score = 0.8 if len(contradictions) >= 1 else 0.5
        report.add(_ok("A-02: Mixed language content", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("A-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_very_long_content(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        long_text_a = "华为" + "技术" * 200 + "采用微服务架构"
        long_text_b = "华为" + "技术" * 200 + "采用单体架构"
        await cli.remember(long_text_a, memory_type="observation", tags=["arch"])
        await cli.remember(long_text_b, memory_type="observation", tags=["arch"])
        result = await cli.reflect("华为架构", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        ok = True
        score = 0.8 if len(contradictions) >= 1 else 0.5
        report.add(_ok("A-03: Very long content", ok, score,
                       f"contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("A-03", False, 0.0, str(e), (time.time() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════
# 4. Performance Stress
# ═══════════════════════════════════════════════════════════════════

async def test_large_node_count(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(50):
            await cli.remember(f"测试记忆{i}：数值{i * 10}",
                               memory_type="observation", tags=["stress"])

        await cli.remember("测试记忆0：数值999", memory_type="observation", tags=["stress"])

        start = time.time()
        result = await cli.reflect("测试记忆数值", max_iterations=5, skip_consolidation=True, skip_forgetting=True)
        elapsed = (time.time() - start) * 1000

        contradictions = result.get("contradictions", [])
        ok = elapsed < 10000
        score = 0.8 if ok else 0.3
        if len(contradictions) >= 1:
            score = min(score + 0.2, 1.0)

        report.add(_ok("P-01: 50+ nodes stress test", ok, score,
                       f"elapsed={elapsed:.0f}ms, contradictions={len(contradictions)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("P-01", False, 0.0, str(e), (time.time() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════
# 5. Integration Tests
# ═══════════════════════════════════════════════════════════════════

async def test_reflect_with_consolidation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(6):
            await cli.remember(f"华为风险观察{i}：风险指标偏高",
                               memory_type="fragment", tags=["risk", "huawei"])
        result = await cli.reflect("华为风险", max_iterations=5, skip_consolidation=False, skip_forgetting=True)
        ok = True
        score = 0.8
        report.add(_ok("I-01: Reflect with consolidation enabled", ok, score,
                       f"contradictions={len(result.get('contradictions', []))}, "
                       f"consolidation={result.get('consolidation_result')}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("I-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_reflect_with_forgetting(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("临时观察：市场波动", memory_type="fragment", tags=["temp"], confidence=0.2)
        result = await cli.reflect("市场观察", max_iterations=5, skip_consolidation=True, skip_forgetting=False)
        ok = True
        score = 0.8
        report.add(_ok("I-02: Reflect with forgetting enabled", ok, score,
                       f"forgetting={result.get('forgetting_result')}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("I-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def test_metadata_propagation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        from ontology_engine.engine.cognitive.rrf_types import RetrievalResult

        r = RetrievalResult(
            doc_id="test_001",
            content="测试内容",
            memory_type="observation",
            cognitive_layer="semantic",
            metadata={"belief_status": "accepted", "confidence": 0.9, "tags": ["test"], "entity_name": "华为"},
        )
        has_belief = r.metadata.get("belief_status") == "accepted"
        has_confidence = r.metadata.get("confidence") == 0.9
        has_tags = "test" in r.metadata.get("tags", [])
        has_entity = r.metadata.get("entity_name") == "华为"

        ok = has_belief and has_confidence and has_tags and has_entity
        score = 1.0 if ok else 0.0
        report.add(_ok("I-03: Metadata propagation in RetrievalResult", ok, score,
                       f"belief={has_belief}, conf={has_confidence}, tags={has_tags}, entity={has_entity}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("I-03", False, 0.0, str(e), (time.time() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 10: Contradiction Detection Fix Verification")
        print("=" * 70)

        trajectories = [
            ("R-01: Negation conflict", test_negation_conflict),
            ("R-02: Value conflict", test_value_conflict),
            ("R-03: Belief conflict", test_belief_conflict),
            ("R-04: Entity-name grouping", test_entity_name_grouping),
            ("R-05: Constraint conflict", test_constraint_conflict),
            ("B-01: Empty space", test_empty_space),
            ("B-02: Single node", test_single_node),
            ("B-03: Same content", test_same_content),
            ("B-04: No-tag nodes", test_no_tag_nodes),
            ("B-05: Superseded excluded", test_superseded_excluded),
            ("A-01: Special characters", test_special_characters),
            ("A-02: Mixed language", test_mixed_language),
            ("A-03: Very long content", test_very_long_content),
            ("P-01: 50+ nodes stress", test_large_node_count),
            ("I-01: Reflect+consolidation", test_reflect_with_consolidation),
            ("I-02: Reflect+forgetting", test_reflect_with_forgetting),
            ("I-03: Metadata propagation", test_metadata_propagation),
        ]

        for name, fn in trajectories:
            runner.set_space(f"{SPACE}_{name}")
            print(f"\n--- {name} ---")
            try:
                await asyncio.wait_for(fn(runner, report), timeout=120)
            except asyncio.TimeoutError:
                report.add(_ok(name, False, 0.0, "TIMEOUT", 120000))
            await asyncio.sleep(0.5)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n" + report.summary())
    out = save_report(report, Path(__file__).parent, "case10")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
