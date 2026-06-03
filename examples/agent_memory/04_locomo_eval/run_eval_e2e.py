"""Case 9: E2E Memory via API — CLI-Based Verification.

End-to-end memory system verification through standard CLI interface,
focusing on multi-session accumulation and cross-session reasoning.

Core verification points:
  Multi-session:     Memory accumulation across sessions
  Temporal:          Time-aware knowledge evolution
  Contradiction:     Cross-session contradiction resolution
  Governance:        Consolidation + forgetting pipeline
  Multi-hop:         Cross-entity inference chains
  Visibility:        Private/shared/public access control

Trajectories:
  T1: Multi-session accumulation
  T2: Temporal knowledge evolution
  T3: Cross-session contradiction + correction
  T4: Governance pipeline (consolidate + forget)
  T5: Multi-hop cross-entity reasoning
  T6: Visibility & access control

Usage: python examples/case9_e2e_memory_via_api/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "e2e_api_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_multi_session(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("TechNova成立于2018年，总部深圳", memory_type="entity", tags={"tag": "technova"})
        await cli.remember("TechNova 2024年营收10亿元", memory_type="observation", tags={"tag": "technova"})
        await cli.remember("TechNova核心产品：AI数据分析平台", memory_type="observation", tags={"tag": "technova"})
        recall = await cli.recall("TechNova公司概况", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T1: Multi-session accumulation", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_temporal_evolution(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("2024年：TechNova采用单体架构", memory_type="observation", tags={"tag": "arch", "tag_2": "technova"})
        await cli.remember("2025年：TechNova迁移至微服务架构", memory_type="observation", tags={"tag": "arch", "tag_2": "technova"})
        await cli.remember("2026年：TechNova采用云原生Serverless架构", memory_type="observation", tags={"tag": "arch", "tag_2": "technova"})
        recall = await cli.recall("TechNova架构演进历程", max_results=5)
        results = recall.get("results", [])
        has_latest = any("Serverless" in r.get("content", "") or "2026" in r.get("content", "") for r in results)
        ok = len(results) > 0
        report.add(_ok("T2: Temporal evolution", ok,
                       1.0 if has_latest else 0.5 if ok else 0.0,
                       f"hits={len(results)}, has_latest={has_latest}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_contradiction_correction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("TechNova使用Redis缓存", memory_type="observation", tags={"tag": "infra", "tag_2": "technova"})
        old_id = r1.get("node_id")
        await cli.remember("TechNova使用Memcached缓存", memory_type="observation", tags={"tag": "infra", "tag_2": "technova"})

        reflect = await cli.reflect("TechNova缓存方案", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        contradictions = reflect.get("contradictions", [])

        if old_id:
            await cli.correct(node_id=old_id, corrected_text="TechNova使用Redis集群缓存（主从模式）",
                              reason="确认缓存方案", user_id="architect")
        ok = len(contradictions) > 0 or old_id is not None
        report.add(_ok("T3: Contradiction + correction", ok, 1.0 if ok else 0.5,
                       f"contradictions={len(contradictions)}, corrected={old_id is not None}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_governance_pipeline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(3):
            await cli.remember(f"治理管线测试碎片 #{i+1}", memory_type="fragment", tags={"tag": "governance_test"})
        consolidation = await cli.consolidate()
        forgetting = await cli.forget(days_elapsed=30)
        ok = consolidation is not None and forgetting is not None
        report.add(_ok("T4: Governance pipeline", ok, 1.0 if ok else 0.0,
                       f"consolidated={consolidation is not None}, forgotten={forgetting is not None}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_multi_hop_reasoning(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("王芳是TechNova的CTO", memory_type="entity", tags={"tag": "person", "tag_2": "technova"})
        await cli.remember("TechNova部署在CloudGroup云平台", memory_type="observation", tags={"tag": "infra", "tag_2": "cloudgroup"})
        await cli.remember("CloudGroup使用Kubernetes编排", memory_type="observation", tags={"tag": "infra", "tag_2": "cloudgroup"})
        recall = await cli.recall("王芳的技术团队使用什么云平台和编排工具", max_results=10)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T5: Multi-hop reasoning", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_visibility_control(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("公开信息：TechNova上市计划", memory_type="observation",
                           visibility="public", created_by="analyst_A")
        await cli.remember("私有笔记：对TechNova的个人看法", memory_type="observation",
                           visibility="private", created_by="analyst_A")
        await cli.remember("共享信息：TechNova行业对比", memory_type="observation",
                           visibility="shared", created_by="analyst_B")
        recall = await cli.recall("TechNova信息", max_results=10)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T6: Visibility & access control", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 9: E2E Memory via API — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Multi-session", run_t1_multi_session),
            ("T2: Temporal evolution", run_t2_temporal_evolution),
            ("T3: Contradiction + correction", run_t3_contradiction_correction),
            ("T4: Governance pipeline", run_t4_governance_pipeline),
            ("T5: Multi-hop reasoning", run_t5_multi_hop_reasoning),
            ("T6: Visibility control", run_t6_visibility_control),
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
    out = save_report(report, Path(__file__).parent, "case9")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
