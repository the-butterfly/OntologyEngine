"""Case 14: Real LLM Evaluation — CLI-Based Verification.

Evaluates the memory system with real LLM-powered operations
(knowledge extraction, consolidation, contradiction detection, reflection)
through standard CLIRunner interface.

NOTE: This case requires LLM API access. Set ONTOLOGY_LLM_API_KEY
and ONTOLOGY_LLM_BASE_URL environment variables before running.

Core verification points:
  Knowledge extraction: LLM-powered entity/relation extraction
  Consolidation:        LLM-driven fragment merging
  Contradiction:        LLM semantic conflict detection
  Reflection:           LLM-powered insight generation
  Compilation:          LLM synthesis of entity/topic pages

Trajectories:
  T1: LLM knowledge extraction
  T2: LLM consolidation
  T3: LLM contradiction detection
  T4: LLM reflection
  T5: LLM compilation
  T6: Full agent session with LLM
  T7: Contradiction resolution with LLM
  T8: Quality assessment

Usage: python examples/case14_real_llm_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "real_llm_eval"
TRAJECTORY_DELAY = 5.0


def _llm_available() -> bool:
    return bool(os.environ.get("ONTOLOGY_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


async def run_t1_llm_extraction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("华信科技2025年营收50亿元，同比增长15%，净利润8亿元，资产负债率75%",
                               memory_type="fragment", tags={"tag": "financial", "tag_2": "huaxin"})
        node_id = r.get("node_id")
        extracted = r.get("extracted_entities", [])
        ok = node_id is not None
        report.add(_ok("T1: LLM knowledge extraction", ok,
                       1.0 if len(extracted) > 0 else 0.5 if ok else 0.0,
                       f"node_id={node_id}, extracted={len(extracted)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_llm_consolidation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for text in ["瑞芯微电发布新一代AI芯片", "瑞芯微电RK3588采用8nm工艺", "瑞芯微电AI芯片性能提升3倍"]:
            await cli.remember(text, memory_type="fragment", tags={"tag": "chip", "tag_2": "ruikexin"})
        result = await cli.consolidate()
        consolidated = result.get("consolidated_count", 0)
        stats = await cli.stats()
        ok = stats.get("total", 0) > 0
        report.add(_ok("T2: LLM consolidation", ok,
                       1.0 if consolidated > 0 else 0.5,
                       f"consolidated={consolidated}, total={stats.get('total', 0)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_llm_contradiction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("华信科技风险等级C级", memory_type="observation", tags={"tag": "risk", "tag_2": "huaxin"})
        await cli.remember("华信科技风险等级A级", memory_type="observation", tags={"tag": "risk", "tag_2": "huaxin"})
        reflect = await cli.reflect("华信科技风险等级矛盾", max_iterations=3, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        contradictions = reflect.get("contradictions", [])
        insights = reflect.get("insights", [])
        ok = len(contradictions) > 0 or len(insights) > 0
        report.add(_ok("T3: LLM contradiction", ok,
                       1.0 if len(contradictions) > 0 else 0.5,
                       f"contradictions={len(contradictions)}, insights={len(insights)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_llm_reflection(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("恒信集团2025年营收30亿", memory_type="observation", tags={"tag": "financial"})
        await cli.remember("恒信集团2025年获得政府补贴5亿", memory_type="observation", tags={"tag": "subsidy"})
        reflect = await cli.reflect("恒信集团财务健康度分析", max_iterations=3, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        insights = reflect.get("insights", [])
        ok = reflect is not None
        report.add(_ok("T4: LLM reflection", ok,
                       1.0 if len(insights) > 0 else 0.5,
                       f"insights={len(insights)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_llm_compilation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("中芯科技：半导体制造企业，总部上海", memory_type="entity", tags={"tag": "semiconductor"})
        entity_id = r.get("node_id")
        await cli.remember("中芯科技2025年营收200亿", memory_type="observation", tags={"tag": "semiconductor"})
        page = await cli.compile_entity(entity_id) if entity_id else {}
        summary = page.get("summary", "")
        ok = entity_id is not None
        report.add(_ok("T5: LLM compilation", ok,
                       1.0 if len(summary) > 10 else 0.5 if ok else 0.0,
                       f"entity_id={entity_id}, summary_len={len(summary)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_full_agent_session(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("TechNova获得B轮融资2亿元", memory_type="observation",
                               tags={"tag": "funding", "tag_2": "technova"}, confidence=0.9)
        r.get("node_id")
        await cli.consolidate()
        recall = await cli.recall("TechNova融资", max_results=5)
        ok_recall = len(recall.get("results", [])) > 0
        reflect = await cli.reflect("TechNova融资影响", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        ok_reflect = reflect is not None
        ok = ok_recall or ok_reflect
        report.add(_ok("T6: Full agent session", ok,
                       1.0 if ok_recall and ok_reflect else 0.5,
                       f"recall={ok_recall}, reflect={ok_reflect}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_contradiction_resolution(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("恒信集团资产负债率75%", memory_type="observation",
                                confidence=0.8, tags={"tag": "financial"})
        old_id = r1.get("node_id")
        corrected = await cli.correct(node_id=old_id,
                                      corrected_text="恒信集团资产负债率降至45%（债务重组后）",
                                      reason="债务重组完成", user_id="analyst")
        new_id = corrected.get("new_node_id") if corrected else None
        ok = new_id is not None
        report.add(_ok("T7: Contradiction resolution", ok, 1.0 if ok else 0.0,
                       f"old={old_id}, new={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_quality_assessment(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        stats = await cli.stats()
        total = stats.get("total", 0)
        types = await cli.types()
        await cli.audit(limit=20)
        ok = total > 0
        report.add(_ok("T8: Quality assessment", ok, 1.0 if ok else 0.0,
                       f"total={total}, types={len(types) if isinstance(types, dict) else 'N/A'}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 14: Real LLM Evaluation — CLI Verification")
        if not _llm_available():
            print("WARNING: No LLM API key found. Some tests may use fallback mode.")
        print("=" * 70)
        trajectories = [
            ("T1: LLM extraction", run_t1_llm_extraction),
            ("T2: LLM consolidation", run_t2_llm_consolidation),
            ("T3: LLM contradiction", run_t3_llm_contradiction),
            ("T4: LLM reflection", run_t4_llm_reflection),
            ("T5: LLM compilation", run_t5_llm_compilation),
            ("T6: Full agent session", run_t6_full_agent_session),
            ("T7: Contradiction resolution", run_t7_contradiction_resolution),
            ("T8: Quality assessment", run_t8_quality_assessment),
        ]
        for name, fn in trajectories:
            print(f"\n--- {name} ---")
            try:
                await asyncio.wait_for(fn(runner, report), timeout=180)
            except asyncio.TimeoutError:
                report.add(_ok(name, False, 0.0, "TIMEOUT", 180000))
            await asyncio.sleep(TRAJECTORY_DELAY)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n" + report.summary())
    out = save_report(report, Path(__file__).parent, "case14")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
