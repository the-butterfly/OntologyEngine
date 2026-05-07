"""Case 10: CLI Agent Simulation — CLI-Based Verification.

Simulates a CLI agent interacting with the memory system across
multiple sessions, using only standard CLIRunner interface.

Core verification points:
  Onboarding:    New agent session with initial knowledge
  Policy update: Time-aware policy changes
  Contradiction: Cross-session conflict detection
  Governance:    Consolidation + forgetting workflow
  Multi-hop:     Cross-entity reasoning
  Belief:        Belief revision with approval

Trajectories:
  T1: Onboarding session (initial knowledge ingestion)
  T2: Policy update session (temporal reasoning)
  T3: Contradiction discovery session
  T4: Governance session (consolidate + forget)
  T5: Multi-hop reasoning session
  T6: Belief revision & approval session

Usage: python examples/case10_cli_agent_simulation/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "cli_agent_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_onboarding(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("新员工入职：TechNova公司成立于2018年", memory_type="observation",
                           tags=["onboarding", "technova"], created_by="agent")
        await cli.remember("新员工入职：TechNova核心业务是AI数据分析", memory_type="observation",
                           tags=["onboarding", "technova"], created_by="agent")
        await cli.remember("新员工入职：TechNova总部位于深圳南山", memory_type="observation",
                           tags=["onboarding", "technova"], created_by="agent")
        recall = await cli.recall("TechNova基本信息", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T1: Onboarding session", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_policy_update(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("旧策略：API限流1000次/分钟", memory_type="rule",
                           tags=["policy", "api"], confidence=0.8)
        await cli.remember("新策略：API限流提升至5000次/分钟（2025年Q2生效）", memory_type="rule",
                               tags=["policy", "api"], confidence=0.95)
        recall = await cli.recall("API限流策略", max_results=5)
        results = recall.get("results", [])
        has_new = any("5000" in r.get("content", "") for r in results)
        ok = len(results) > 0
        report.add(_ok("T2: Policy update session", ok,
                       1.0 if has_new else 0.5 if ok else 0.0,
                       f"hits={len(results)}, has_new_policy={has_new}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_contradiction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("TechNova使用Redis作为消息队列", memory_type="observation", tags=["infra", "technova"])
        await cli.remember("TechNova使用RabbitMQ作为消息队列", memory_type="observation", tags=["infra", "technova"])
        reflect = await cli.reflect("TechNova消息队列方案", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        contradictions = reflect.get("contradictions", [])
        insights = reflect.get("insights", [])
        ok = len(contradictions) > 0 or len(insights) > 0
        report.add(_ok("T3: Contradiction discovery", ok,
                       1.0 if len(contradictions) > 0 else 0.5,
                       f"contradictions={len(contradictions)}, insights={len(insights)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_governance(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(3):
            await cli.remember(f"治理会话碎片 #{i+1}", memory_type="fragment", tags=["governance"])
        consolidation = await cli.consolidate()
        forgetting = await cli.forget(days_elapsed=30)
        dream = await cli.dream()
        ok_c = consolidation is not None
        ok_f = forgetting is not None
        ok_d = dream is not None
        ok = ok_c and ok_f
        report.add(_ok("T4: Governance session", ok,
                       sum([ok_c, ok_f, ok_d]) / 3,
                       f"consolidate={ok_c}, forget={ok_f}, dream={ok_d}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_multi_hop(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("王芳是TechNova的CTO", memory_type="entity", tags=["person", "technova"])
        await cli.remember("TechNova使用CloudGroup云服务", memory_type="observation", tags=["infra"])
        await cli.remember("CloudGroup区域：亚太区使用AWS基础设施", memory_type="observation", tags=["infra", "cloudgroup"])
        recall = await cli.recall("王芳团队使用的云基础设施", max_results=10)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T5: Multi-hop reasoning", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_belief_revision(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("TechNova风险等级C级", memory_type="observation",
                                confidence=0.7, tags=["risk", "technova"])
        old_id = r1.get("node_id")
        r2 = await cli.remember("TechNova风险等级调整为A级（获得新一轮融资后）", memory_type="observation",
                                confidence=0.95, tags=["risk", "technova"],
                                supersede_target=old_id, supersede_reason="融资改善")
        new_id = r2.get("node_id")
        ok = old_id is not None and new_id is not None
        report.add(_ok("T6: Belief revision & approval", ok, 1.0 if ok else 0.0,
                       f"old_id={old_id}, new_id={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 10: CLI Agent Simulation — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Onboarding", run_t1_onboarding),
            ("T2: Policy update", run_t2_policy_update),
            ("T3: Contradiction", run_t3_contradiction),
            ("T4: Governance", run_t4_governance),
            ("T5: Multi-hop", run_t5_multi_hop),
            ("T6: Belief revision", run_t6_belief_revision),
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
    out = save_report(report, Path(__file__).parent, "case10")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
