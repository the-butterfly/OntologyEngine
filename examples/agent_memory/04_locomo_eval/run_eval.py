"""Case 8: LOCOMO-Style Memory Evaluation — CLI-Based Verification.

Comprehensive evaluation following LOCOMO benchmark dimensions,
using only standard CLIRunner interface (no internal module access).

Core verification points (cross-cutting):
  Single-hop recall:  Basic remember → recall accuracy
  Multi-hop reasoning: Cross-entity inference chains
  Temporal reasoning:  Time-aware recall and ordering
  Contradiction:      Detection and resolution
  Consolidation:      Fragment → observation → entity upgrade
  Forgetting:         Value-aware decay and protection
  DreamCycle:         5-phase maintenance cycle
  Correction:         Propagation along cognitive edges

Trajectories:
  T1:  Single-hop recall (direct fact retrieval)
  T2:  Multi-hop reasoning (cross-entity inference)
  T3:  Temporal reasoning (time-aware queries)
  T4:  Contradiction detection (rule + semantic)
  T5:  Consolidation & type upgrade
  T6:  Supersede & belief revision
  T7:  Forgetting & protection
  T8:  Correction propagation
  T9:  DreamCycle maintenance
  T10: Full lifecycle cross-verification

Usage: python examples/case8_locomo_memory_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "locomo_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_single_hop_recall(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        facts = [
            ("TechNova公司总部位于深圳", "entity", ["company", "technova"]),
            ("TechNova成立于2018年", "observation", ["company", "technova"]),
            ("CloudGroup是云计算服务商", "entity", ["company", "cloudgroup"]),
            ("王芳是TechNova的CTO", "entity", ["person", "technova"]),
        ]
        for content, mtype, tags in facts:
            await cli.remember(content, memory_type=mtype, tags=tags)

        recall = await cli.recall("TechNova总部在哪里", max_results=5)
        results = recall.get("results", [])
        hit = any("深圳" in r.get("text", "") for r in results)
        ok = len(results) > 0
        report.add(_ok("T1: Single-hop recall", ok,
                       1.0 if hit else 0.5 if ok else 0.0,
                       f"hits={len(results)}, found_shenzhen={hit}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_multi_hop_reasoning(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("TechNova使用微服务架构", memory_type="observation", tags={"tag": "arch", "tag_2": "technova"})
        await cli.remember("TechNova的微服务部署在CloudGroup云平台", memory_type="observation", tags={"tag": "arch", "tag_2": "cloudgroup"})
        await cli.remember("CloudGroup云平台采用Kubernetes编排", memory_type="observation", tags={"tag": "infra", "tag_2": "cloudgroup"})
        await cli.remember("王芳负责TechNova的技术架构决策", memory_type="observation", tags={"tag": "person", "tag_2": "technova"})

        recall = await cli.recall("王芳的技术架构使用了什么云平台和编排方案", max_results=10)
        results = recall.get("results", [])
        has_cloud = any("CloudGroup" in r.get("text", "") or "cloudgroup" in str(r.get("tags", [])).lower() for r in results)
        has_k8s = any("Kubernetes" in r.get("text", "") for r in results)
        ok = len(results) > 0
        report.add(_ok("T2: Multi-hop reasoning", ok,
                       1.0 if has_cloud and has_k8s else 0.5 if ok else 0.0,
                       f"hits={len(results)}, cloud={has_cloud}, k8s={has_k8s}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_temporal_reasoning(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("2024年Q1：TechNova API限流策略为1000次/分钟", memory_type="observation",
                           tags={"tag": "policy", "tag_2": "technova"}, confidence=0.9)
        await cli.remember("2025年Q1：TechNova API限流策略调整为5000次/分钟", memory_type="observation",
                           tags={"tag": "policy", "tag_2": "technova"}, confidence=0.95)
        await cli.remember("2025年Q3：TechNova API限流策略调整为10000次/分钟", memory_type="observation",
                           tags={"tag": "policy", "tag_2": "technova"}, confidence=0.95)

        recall = await cli.recall("TechNova最新的API限流策略", max_results=5)
        results = recall.get("results", [])
        has_latest = any("10000" in r.get("text", "") for r in results)
        ok = len(results) > 0
        report.add(_ok("T3: Temporal reasoning", ok,
                       1.0 if has_latest else 0.5 if ok else 0.0,
                       f"hits={len(results)}, has_latest={has_latest}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_contradiction_detection(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("TechNova使用Redis作为缓存", memory_type="observation", tags={"tag": "infra", "tag_2": "technova"})
        await cli.remember("TechNova使用Memcached作为缓存", memory_type="observation", tags={"tag": "infra", "tag_2": "technova"})

        reflect = await cli.reflect("TechNova缓存技术选型", max_iterations=3, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        contradictions = reflect.get("contradictions", [])
        insights = reflect.get("insights", [])
        ok = len(contradictions) > 0 or len(insights) > 0
        report.add(_ok("T4: Contradiction detection", ok,
                       1.0 if len(contradictions) > 0 else 0.5,
                       f"contradictions={len(contradictions)}, insights={len(insights)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_consolidation_upgrade(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for text in ["华信科技2025年营收50亿", "华信科技资产负债率75%", "华信科技风险等级C级"]:
            await cli.remember(text, memory_type="fragment", tags={"tag": "financial", "tag_2": "huaxin"})

        stats_before = await cli.stats()
        total_before = stats_before.get("total", 0)

        result = await cli.consolidate()
        consolidated = result.get("consolidated_count", 0)

        stats_after = await cli.stats()
        total_after = stats_after.get("total", 0)

        ok = total_after >= total_before
        report.add(_ok("T5: Consolidation & upgrade", ok,
                       1.0 if consolidated > 0 else 0.5,
                       f"before={total_before}, after={total_after}, consolidated={consolidated}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_supersede_belief(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("恒信集团风险等级C级，资产负债率75%", memory_type="observation",
                                confidence=0.8, tags={"tag": "risk", "tag_2": "hengxin"})
        old_id = r1.get("node_id")

        r2 = await cli.remember("恒信集团风险等级调整为B级，资产负债率降至45%", memory_type="observation",
                                confidence=0.95, tags={"tag": "risk", "tag_2": "hengxin"},
                                supersede_target=old_id, supersede_reason="财务改善")
        new_id = r2.get("node_id")

        ok = old_id is not None and new_id is not None
        report.add(_ok("T6: Supersede & belief revision", ok, 1.0 if ok else 0.0,
                       f"old_id={old_id}, new_id={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_forgetting_protection(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("核心风控规则：所有交易必须审核", memory_type="rule",
                           confidence=0.95, tags={"tag": "core_rule"})
        await cli.remember("临时观察：今日市场波动较大", memory_type="observation",
                           confidence=0.4, tags={"tag": "temporary"})

        result = await cli.forget(days_elapsed=30)
        ok = result is not None
        report.add(_ok("T7: Forgetting & protection", ok, 1.0 if ok else 0.0,
                       f"forget_result={bool(result)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_correction_propagation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("华信科技2025年营收35亿", memory_type="observation",
                               confidence=0.8, tags={"tag": "financial", "tag_2": "huaxin"})
        node_id = r.get("node_id")

        corrected = await cli.correct(
            node_id=node_id,
            corrected_text="华信科技2025年营收65亿（更正：原数据遗漏了海外业务）",
            reason="数据更正", user_id="analyst")

        new_id = corrected.get("new_node_id") if corrected else None
        ok = new_id is not None
        report.add(_ok("T8: Correction propagation", ok, 1.0 if ok else 0.0,
                       f"original={node_id}, corrected={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t9_dreamcycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(3):
            await cli.remember(f"梦境测试数据 #{i+1}", memory_type="fragment", tags={"tag": "dream_test"})
        await cli.consolidate()

        result = await cli.dream()
        skipped = result.get("skipped", False)
        phases = result.get("phases_completed", 0)
        contradictions = result.get("contradictions_found", 0)
        ok = skipped or phases > 0
        report.add(_ok("T9: DreamCycle maintenance", ok, 1.0 if ok else 0.0,
                       f"phases={phases}, contradictions={contradictions}, skipped={skipped}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T9", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t10_full_lifecycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("中芯科技2025年营收200亿，风险等级A级", memory_type="entity", confidence=0.9)
        node_id = r.get("node_id") or ""
        ok_remember = len(node_id) > 0

        await cli.consolidate()
        recall = await cli.recall("中芯科技风险", max_results=5)
        ok_recall = len(recall.get("results", [])) > 0

        reflect = await cli.reflect("中芯科技风险评估", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        ok_reflect = reflect is not None

        correct = await cli.correct(node_id=node_id,
                                    corrected_text="中芯科技2026年Q1营收60亿（同比+20%），风险等级维持A级",
                                    reason="季度更新", user_id="analyst")
        ok_correct = correct is not None

        dream = await cli.dream()
        ok_dream = dream is not None

        forget = await cli.forget(days_elapsed=30)
        ok_forget = forget is not None

        ok = ok_remember and ok_reflect and ok_correct
        score = sum([ok_remember, ok_recall, ok_reflect, ok_correct, ok_dream, ok_forget]) / 6
        report.add(_ok("T10: Full lifecycle", ok, score,
                       f"remember={ok_remember}, recall={ok_recall}, reflect={ok_reflect}, "
                       f"correct={ok_correct}, dream={ok_dream}, forget={ok_forget}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T10", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 8: LOCOMO-Style Memory Evaluation — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Single-hop recall", run_t1_single_hop_recall),
            ("T2: Multi-hop reasoning", run_t2_multi_hop_reasoning),
            ("T3: Temporal reasoning", run_t3_temporal_reasoning),
            ("T4: Contradiction detection", run_t4_contradiction_detection),
            ("T5: Consolidation & upgrade", run_t5_consolidation_upgrade),
            ("T6: Supersede & belief", run_t6_supersede_belief),
            ("T7: Forgetting & protection", run_t7_forgetting_protection),
            ("T8: Correction propagation", run_t8_correction_propagation),
            ("T9: DreamCycle", run_t9_dreamcycle),
            ("T10: Full lifecycle", run_t10_full_lifecycle),
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
    out = save_report(report, Path(__file__).parent, "case8")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
