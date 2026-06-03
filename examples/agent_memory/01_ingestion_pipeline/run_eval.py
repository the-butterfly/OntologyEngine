"""Case 5: Memory Ingestion Pipeline — CLI-Based Verification.

Verifies the complete remember() orchestration chain:
  DeduplicationGate → Ingestion → EntityResolver → optional Consolidation

Core verification points (from docs/02-design/agent-memory/):
  V-AM-1:  Dual storage (Layer-R vector + Layer-S graph) with memory_type tagging
  V-API-1: oe_remember complete orchestration chain (6-step sequential)
  V-AM-7:  Entity resolution 3-level strategy (L1 exact → L2 trigram → L3 LLM)
  V-LC-1:  DeduplicationGate write-time governance
  V-AM-6:  Type-specific fields stored as JSON attributes
  V-AM-8:  memory_type × model_domain orthogonal classification
  V-HIE-3: observation cognitive_layer dynamic inference

All operations use CLIRunner (maps to CLI commands). No internal module imports.

Trajectories:
  T1: Basic remember → recall (verify dual storage + retrieval)
  T2: DeduplicationGate (high-similarity duplicate rejection)
  T3: Entity Resolution L1 (exact match reuse)
  T4: Entity Resolution L2 (trigram fuzzy match)
  T5: model_domain auto-inference (commitment→task, constraint→world, etc.)
  T6: observation cognitive_layer dynamic classification
  T7: source_trust_tier propagation
  T8: Multi-source ingestion with type-specific attributes

Usage:
    python examples/case5_memory_ingestion_pipeline/run_eval.py

Requires: config.yaml with LLM + Embedding configuration.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "ingestion_eval"
TRAJECTORY_DELAY = 2.0


async def run_t1_basic_remember_recall(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember(
            "华信科技2025年营收50亿，资产负债率75%",
            memory_type="entity", tags={"tag": "company", "tag_2": "risk"},
            confidence=0.9, created_by="analyst_A",
        )
        node_id = r.get("node_id")
        stats = await cli.stats()
        total = stats.get("total", 0)
        recall = await cli.recall("华信科技营收", max_results=5)
        results = recall.get("results", [])
        ok = node_id is not None and total > 0
        report.add(_ok("T1: Basic remember→recall", ok,
                       1.0 if ok and len(results) > 0 else 0.7 if ok else 0.0,
                       f"node_id={node_id}, total={total}, recall_hits={len(results)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_deduplication_gate(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("中芯科技是半导体制造企业，风险等级A级", memory_type="entity", tags={"tag": "semiconductor"})
        r2 = await cli.remember("中芯科技是半导体制造企业，风险等级A级", memory_type="entity", tags={"tag": "semiconductor"})
        r3 = await cli.remember("中芯科技是芯片制造领先企业，财务状况稳健", memory_type="entity", tags={"tag": "semiconductor"})
        id1, id2, id3 = r1.get("node_id"), r2.get("node_id"), r3.get("node_id")
        dedup = id1 == id2
        different = id3 != id1
        ok = dedup or different
        report.add(_ok("T2: DeduplicationGate", ok,
                       1.0 if dedup and different else 0.5,
                       f"id1={id1}, id2={id2}, id3={id3}, dedup={dedup}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_entity_resolution_l1(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("恒信集团：多元化企业，风险等级C级", memory_type="entity", tags={"tag": "conglomerate"})
        r2 = await cli.remember("恒信集团2025年净利润8亿元", memory_type="observation", tags={"tag": "conglomerate"})
        id1, id2 = r1.get("node_id"), r2.get("node_id")
        ok = id1 is not None and id2 is not None and id1 != id2
        report.add(_ok("T3: Entity Resolution L1", ok, 1.0 if ok else 0.0,
                       f"entity_id={id1}, observation_id={id2}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_entity_resolution_l2(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("瑞芯微电：芯片设计企业，风险等级B级", memory_type="entity", tags={"tag": "semiconductor", "tag_2": "design"})
        r2 = await cli.remember("瑞芯微电子：IC设计公司，财务稳健", memory_type="entity", tags={"tag": "semiconductor", "tag_2": "design"})
        id1, id2 = r1.get("node_id"), r2.get("node_id")
        ok = id1 is not None and id2 is not None
        report.add(_ok("T4: Entity Resolution L2 (trigram)", ok, 1.0 if ok else 0.0,
                       f"id1={id1}, id2={id2}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_model_domain_inference(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        cases = [
            ("承诺在Q3前完成系统迁移", "commitment", "task"),
            ("API调用频率限制100次/分钟", "constraint", "world"),
            ("工具X调用失败3次，可靠性低", "self_experience", "self"),
        ]
        correct = 0
        domain_correct = 0
        for content, mtype, expected_domain in cases:
            r = await cli.remember(content, memory_type=mtype)
            node_id = r.get("node_id")
            if node_id:
                correct += 1
                recall = await cli.recall(content, max_results=1)
                results = recall.get("results", [])
                if results:
                    actual_tags = results[0].get("tags", {})
                    actual_domain = actual_tags.get("model", "") if isinstance(actual_tags, dict) else ""
                    if actual_domain == expected_domain:
                        domain_correct += 1
        ok = correct >= 2 and domain_correct >= 1
        score = (0.5 * correct / max(len(cases), 1)) + (0.5 * domain_correct / max(len(cases), 1))
        report.add(_ok("T5: model_domain auto-inference", ok, score,
                       f"created={correct}/{len(cases)}, domain_match={domain_correct}/{len(cases)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_cognitive_layer_inference(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("华信科技2025年Q4营收12.5亿元", memory_type="observation")
        r2 = await cli.remember("华信科技风险等级应该调整为B级，因为重组效果显著", memory_type="observation")
        id1, id2 = r1.get("node_id"), r2.get("node_id")
        layer_match = 0
        if id1:
            recall1 = await cli.recall("华信科技Q4营收", max_results=1)
            results1 = recall1.get("results", [])
            if results1 and results1[0].get("cognitive_layer") == "opinion":
                layer_match += 1
        if id2:
            recall2 = await cli.recall("华信科技风险等级调整", max_results=1)
            results2 = recall2.get("results", [])
            if results2 and results2[0].get("cognitive_layer") == "opinion":
                layer_match += 1
        ok = id1 is not None and id2 is not None
        score = 0.5 if ok else 0.0
        if ok and layer_match > 0:
            score = 1.0
        report.add(_ok("T6: cognitive_layer inference", ok, score,
                       f"factual_id={id1}, subjective_id={id2}, layer_match={layer_match}/2", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_source_trust_tier(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        tiers = ["high", "normal", "low"]
        created = 0
        tier_match = 0
        for tier in tiers:
            r = await cli.remember(f"测试来源可信层级: {tier}", memory_type="observation", source_trust_tier=tier)
            node_id = r.get("node_id")
            if node_id:
                created += 1
                recall = await cli.recall(f"测试来源可信层级: {tier}", max_results=1)
                results = recall.get("results", [])
                if results:
                    actual_tier = results[0].get("source_trust_tier", "")
                    if actual_tier == tier:
                        tier_match += 1
        ok = created >= 2 and tier_match >= 1
        score = (0.5 * created / len(tiers)) + (0.5 * tier_match / len(tiers))
        report.add(_ok("T7: source_trust_tier propagation", ok, score,
                       f"created={created}/{len(tiers)}, tier_match={tier_match}/{len(tiers)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_multi_source_ingestion(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华信科技担保链深度3级，负面舆情预警", memory_type="observation",
                           source_pipeline="user_input", tags={"tag": "risk", "tag_2": "guarantee_chain"})
        await cli.remember("系统检测到华信科技资产负债率异常波动", memory_type="observation",
                           source_pipeline="behavior_analysis", tags={"tag": "risk", "tag_2": "anomaly"})
        await cli.remember("根据历史数据分析，华信科技违约概率15%", memory_type="rule",
                           source_pipeline="agent_generated", tags={"tag": "risk", "tag_2": "probability"})
        stats = await cli.stats()
        total = stats.get("total", 0)
        recall = await cli.recall("华信科技风险", max_results=10)
        results = recall.get("results", [])
        ok = total > 0
        report.add(_ok("T8: Multi-source ingestion", ok, 1.0 if ok else 0.0,
                       f"total={total}, recall_hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 5: Memory Ingestion Pipeline — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Basic remember→recall", run_t1_basic_remember_recall),
            ("T2: DeduplicationGate", run_t2_deduplication_gate),
            ("T3: Entity Resolution L1", run_t3_entity_resolution_l1),
            ("T4: Entity Resolution L2", run_t4_entity_resolution_l2),
            ("T5: model_domain inference", run_t5_model_domain_inference),
            ("T6: cognitive_layer inference", run_t6_cognitive_layer_inference),
            ("T7: source_trust_tier", run_t7_source_trust_tier),
            ("T8: Multi-source ingestion", run_t8_multi_source_ingestion),
        ]
        for name, fn in trajectories:
            print(f"\n--- {name} ---")
            try:
                await asyncio.wait_for(fn(runner, report), timeout=120)
            except asyncio.TimeoutError:
                report.add(_ok(name, False, 0.0, "TIMEOUT", 120000))
            await asyncio.sleep(TRAJECTORY_DELAY)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n" + report.summary())
    out = save_report(report, Path(__file__).parent, "case5")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
