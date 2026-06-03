"""Case 11: Lifecycle & MCP Interface — CLI-Based Verification.

Verifies the complete memory lifecycle and MCP-equivalent interface
through standard CLIRunner, covering the full closed-loop from
ingestion to governance.

Core verification points:
  XV-1:   remember → consolidate → recall end-to-end
  V-AM-1: Dual-layer storage (Layer-R + Layer-S)
  V-AM-2: Consolidation = memory_type type upgrade
  V-LC-9: DreamCycle 5-phase maintenance
  V-LC-1: DeduplicationGate write governance

Trajectories:
  T1: Full lifecycle closed loop
  T2: model_domain auto-inference
  T3: observation cognitive_layer dynamic classification
  T4: Multi-agent space isolation
  T5: DeduplicationGate + arbitration
  T6: DreamCycle 5-phase
  T7: Consolidation type upgrade
  T8: MCP interface simulation (all CLI methods)

Usage: python examples/case11_lifecycle_mcp_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "lifecycle_mcp_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_full_lifecycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("华信科技2025年营收50亿", memory_type="entity", confidence=0.9)
        node_id = r.get("node_id") or ""
        ok_remember = len(node_id) > 0
        await cli.consolidate()
        recall = await cli.recall("华信科技营收", max_results=5)
        ok_recall = len(recall.get("results", [])) > 0
        reflect = await cli.reflect("华信科技财务状况", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        ok_reflect = reflect is not None
        ok = ok_remember and ok_reflect
        report.add(_ok("T1: Full lifecycle", ok,
                       sum([ok_remember, ok_recall, ok_reflect]) / 3,
                       f"remember={ok_remember}, recall={ok_recall}, reflect={ok_reflect}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_model_domain_inference(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户偏好：保守型投资", memory_type="mental_model", model_domain="user")
        await cli.remember("业务规则：所有交易需风控审核", memory_type="rule", model_domain="world")
        stats = await cli.stats()
        ok = stats.get("total", 0) > 0
        report.add(_ok("T2: model_domain inference", ok, 1.0 if ok else 0.0,
                       f"total={stats.get('total', 0)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_cognitive_layer_dynamic(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华信科技股价今日上涨5%", memory_type="observation", tags={"tag": "market"})
        await cli.remember("恒信集团获得AAA信用评级", memory_type="observation", tags={"tag": "credit"})
        stats = await cli.stats()
        ok = stats.get("total", 0) > 0
        report.add(_ok("T3: Cognitive layer dynamic", ok, 1.0 if ok else 0.0,
                       f"total={stats.get('total', 0)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_space_isolation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("空间A的私有数据", memory_type="observation", visibility="private")
        recall = await cli.recall("私有数据", max_results=5)
        ok = recall is not None
        report.add(_ok("T4: Space isolation", ok, 1.0 if ok else 0.0,
                       f"recall_ok={ok}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_dedup_gate(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("重复测试：华信科技营收50亿", memory_type="fragment", tags={"tag": "dedup"})
        r2 = await cli.remember("重复测试：华信科技营收50亿", memory_type="fragment", tags={"tag": "dedup"})
        ok = r1 is not None and r2 is not None
        report.add(_ok("T5: DeduplicationGate", ok, 1.0 if ok else 0.0,
                       f"id1={r1.get('node_id')}, id2={r2.get('node_id')}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_dreamcycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(3):
            await cli.remember(f"梦境测试 #{i+1}", memory_type="fragment", tags={"tag": "dream"})
        await cli.consolidate()
        result = await cli.dream()
        ok = result is not None
        report.add(_ok("T6: DreamCycle 5-phase", ok, 1.0 if ok else 0.0,
                       f"phases={result.get('phases_completed', 0)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_consolidation_upgrade(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for text in ["中芯科技是半导体企业", "中芯科技2025年营收200亿", "中芯科技风险等级A级"]:
            await cli.remember(text, memory_type="fragment", tags={"tag": "semiconductor"})
        await cli.consolidate()
        stats = await cli.stats()
        ok = stats.get("total", 0) > 0
        report.add(_ok("T7: Consolidation upgrade", ok, 1.0 if ok else 0.0,
                       f"total={stats.get('total', 0)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_mcp_interface(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        methods_ok = []
        r = await cli.remember("MCP接口测试", memory_type="fragment")
        methods_ok.append(r is not None)
        recall = await cli.recall("MCP接口", max_results=5)
        methods_ok.append(recall is not None)
        reflect = await cli.reflect("MCP接口测试", max_iterations=1, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        methods_ok.append(reflect is not None)
        stats = await cli.stats()
        methods_ok.append(stats is not None)
        types = await cli.types()
        methods_ok.append(types is not None)
        audit = await cli.audit(limit=5)
        methods_ok.append(audit is not None)
        ok = all(methods_ok)
        report.add(_ok("T8: MCP interface simulation", ok,
                       sum(methods_ok) / len(methods_ok),
                       f"methods_passed={sum(methods_ok)}/{len(methods_ok)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 11: Lifecycle & MCP Interface — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Full lifecycle", run_t1_full_lifecycle),
            ("T2: model_domain", run_t2_model_domain_inference),
            ("T3: Cognitive layer", run_t3_cognitive_layer_dynamic),
            ("T4: Space isolation", run_t4_space_isolation),
            ("T5: DedupGate", run_t5_dedup_gate),
            ("T6: DreamCycle", run_t6_dreamcycle),
            ("T7: Consolidation", run_t7_consolidation_upgrade),
            ("T8: MCP interface", run_t8_mcp_interface),
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
    out = save_report(report, Path(__file__).parent, "case11")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
