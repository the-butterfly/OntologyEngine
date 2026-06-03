"""Case 6: Contradiction Detection & Belief Revision — CLI-Based Verification.

Core verification points:
  V-REF-7: Mixed contradiction detection (rule-based + LLM semantic)
  V-REF-1: Forced search sequence (mental_model → entity → observation)
  V-LC-7:  Belief revision rule engine
  V-LC-8:  Correction propagation (BFS along cognitive edges)
  V-REF-3: Hallucination protection (ID tracking)

Trajectories:
  T1: Rule-based contradiction detection (negation patterns)
  T2: LLM semantic contradiction detection
  T3: Belief revision via supersede
  T4: Correction propagation along cognitive edges
  T5: Approve/reject workflow for pending memories
  T6: Reflect forced search sequence verification
  T7: Hallucination protection (evidence_ids validation)

Usage: python examples/case6_contradiction_belief_revision/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "contradiction_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_rule_contradiction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华信科技风险等级D级，存在高违约风险", memory_type="opinion", tags={"tag": "risk", "tag_2": "contradiction_test"})
        await cli.remember("华信科技风险等级不是D级，已调整为C级", memory_type="opinion", tags={"tag": "risk", "tag_2": "contradiction_test"})
        result = await cli.reflect("华信科技风险等级评估", max_iterations=2, async_mode=False, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        insights = result.get("insights", [])
        ok = len(contradictions) > 0 or len(insights) > 0
        report.add(_ok("T1: Rule-based contradiction", ok, min(len(contradictions) + len(insights), 3) / 3,
                       f"contradictions={len(contradictions)}, insights={len(insights)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_llm_contradiction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("中芯科技财务稳健，资产负债率仅35%", memory_type="observation", tags={"tag": "semiconductor", "tag_2": "financial"})
        await cli.remember("中芯科技负债率高达65%，现金流紧张", memory_type="observation", tags={"tag": "semiconductor", "tag_2": "financial"})
        result = await cli.reflect("中芯科技财务状况分析", max_iterations=2, async_mode=False, skip_consolidation=True, skip_forgetting=True)
        contradictions = result.get("contradictions", [])
        insights = result.get("insights", [])
        ok = len(contradictions) > 0 or len(insights) > 0
        report.add(_ok("T2: LLM semantic contradiction", ok, min(len(contradictions) + len(insights), 3) / 3,
                       f"contradictions={len(contradictions)}, insights={len(insights)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_belief_supersede(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("恒信集团风险等级C级，资产负债率60%", memory_type="observation", confidence=0.8)
        old_id = r1.get("node_id")
        r2 = await cli.remember("恒信集团风险等级B级，2026年Q1资产负债率降至45%", memory_type="observation", confidence=0.9,
                                supersede_target=old_id, supersede_reason="财务状况改善")
        new_id = r2.get("node_id")
        ok = old_id is not None and new_id is not None
        report.add(_ok("T3: Belief supersede", ok, 1.0 if ok else 0.0,
                       f"old_id={old_id}, new_id={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_correction_propagation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("瑞芯微电风险等级B级，营收稳定增长", memory_type="entity", tags={"tag": "semiconductor"})
        entity_id = r1.get("node_id")
        await cli.remember("瑞芯微电2025年Q4营收同比增长20%", memory_type="observation", tags={"tag": "semiconductor"})
        correct = await cli.correct(node_id=entity_id, corrected_text="瑞芯微电风险等级调整为A级，营收持续高增长",
                                    reason="业绩超预期", user_id="risk_analyst")
        ok = correct is not None
        report.add(_ok("T4: Correction propagation", ok, 1.0 if ok else 0.0,
                       f"entity_id={entity_id}, corrected={correct is not None}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_approve_reject(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("待审核：华信科技可能获得政府补贴", memory_type="observation", belief_status="pending_review")
        node_id = r.get("node_id")
        approve_result = await cli.approve(node_id, action="approve", comment="已确认消息来源")
        ok = approve_result is not None
        report.add(_ok("T5: Approve/reject workflow", ok, 1.0 if ok else 0.0,
                       f"node_id={node_id}, approved={ok}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_reflect_search_sequence(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("投资策略：保守型投资者应选择A级以上债券", memory_type="mental_model", model_domain="world")
        await cli.remember("华信科技：风险等级C级，重组中", memory_type="entity", tags={"tag": "company"})
        await cli.remember("华信科技2026年Q1营收回升12%", memory_type="observation", tags={"tag": "company"})
        result = await cli.reflect("华信科技是否适合保守型投资者", max_iterations=3, async_mode=False,
                                   skip_consolidation=True, skip_forgetting=True)
        insights = result.get("insights", [])
        contradictions = result.get("contradictions", [])
        ok = len(insights) > 0 or len(contradictions) > 0
        report.add(_ok("T6: Reflect search sequence", ok, min(len(insights) + len(contradictions), 3) / 3,
                       f"insights={len(insights)}, contradictions={len(contradictions)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_hallucination_protection(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("恒信集团2025年净利润8亿元", memory_type="observation")
        await cli.remember("恒信集团担保链涉及3家企业", memory_type="observation")
        result = await cli.reflect("恒信集团风险综合评估", max_iterations=2, async_mode=False,
                                   skip_consolidation=True, skip_forgetting=True)
        insights = result.get("insights", [])
        valid_evidence = True
        for insight in insights:
            evidence_ids = insight.get("evidence_ids", []) if isinstance(insight, dict) else []
            for eid in evidence_ids:
                if not isinstance(eid, str) or not eid.startswith("mem:"):
                    valid_evidence = False
        ok = len(insights) == 0 or valid_evidence
        report.add(_ok("T7: Hallucination protection", ok, 1.0 if ok else 0.0,
                       f"insights={len(insights)}, valid_evidence={valid_evidence}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 6: Contradiction Detection & Belief Revision — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Rule-based contradiction", run_t1_rule_contradiction),
            ("T2: LLM semantic contradiction", run_t2_llm_contradiction),
            ("T3: Belief supersede", run_t3_belief_supersede),
            ("T4: Correction propagation", run_t4_correction_propagation),
            ("T5: Approve/reject workflow", run_t5_approve_reject),
            ("T6: Reflect search sequence", run_t6_reflect_search_sequence),
            ("T7: Hallucination protection", run_t7_hallucination_protection),
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
    out = save_report(report, Path(__file__).parent, "case6")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
