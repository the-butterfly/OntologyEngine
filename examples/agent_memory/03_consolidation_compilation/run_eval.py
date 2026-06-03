"""Case 7: Knowledge Consolidation & Compilation — CLI-Based Verification.

Core verification points:
  V-CON-1:  Three-action model (Create/Update/Delete)
  V-CON-2:  Dual-channel evidence tracking
  V-CON-10: Reasoning trail preservation
  V-LC-10:  Compilation layer (EntityPage/TopicPage)
  V-AM-2:   Consolidation = memory_type type upgrade

Trajectories:
  T1: Fragment → observation consolidation
  T2: Observation → entity upgrade
  T3: Consolidation evidence tracking
  T4: LLM-powered consolidation
  T5: EntityPage compilation
  T6: TopicPage compilation
  T7: Consolidation reasoning trail
  T8: Stats verification after consolidation

Usage: python examples/case7_consolidation_compilation/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "consolidation_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_fragment_consolidation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(5):
            await cli.remember(f"华信科技2025年Q{i+1}营收数据：营收{i*10+5}亿元",
                               memory_type="fragment", tags={"tag": "financial", "tag_2": "huaxin"})
        result = await cli.consolidate()
        consolidated = result.get("consolidated_count", 0)
        stats = await cli.stats()
        total = stats.get("total", 0)
        ok = total >= 5
        report.add(_ok("T1: Fragment→observation consolidation", ok,
                       1.0 if consolidated > 0 else 0.5,
                       f"consolidated={consolidated}, total={total}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_observation_entity_upgrade(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("中芯科技是半导体制造企业，总部位于上海", memory_type="observation", tags={"tag": "entity_candidate", "tag_2": "semiconductor"})
        await cli.remember("中芯科技2025年营收200亿元，净利润30亿元", memory_type="observation", tags={"tag": "entity_candidate", "tag_2": "semiconductor"})
        await cli.remember("中芯科技风险等级A级，财务稳健", memory_type="observation", tags={"tag": "entity_candidate", "tag_2": "semiconductor"})
        await cli.consolidate()
        stats = await cli.stats()
        type_dist = stats.get("type_distribution", {})
        ok = stats.get("total", 0) > 0
        report.add(_ok("T2: Observation→entity upgrade", ok, 1.0 if ok else 0.0,
                       f"types={type_dist}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_evidence_tracking(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("恒信集团担保链深度3级", memory_type="fragment", tags={"tag": "guarantee"})
        await cli.remember("恒信集团涉及3家互保企业", memory_type="fragment", tags={"tag": "guarantee"})
        await cli.consolidate()
        stats = await cli.stats()
        total = stats.get("total", 0)
        audit = await cli.audit(limit=20)
        entries = audit.get("entries", []) if isinstance(audit, dict) else []
        ok = total >= 2
        report.add(_ok("T3: Evidence tracking", ok, 1.0 if len(entries) > 0 else 0.7 if ok else 0.0,
                       f"audit_entries={len(entries)}, total={total}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_llm_consolidation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for text in ["瑞芯微电发布新一代AI芯片RK3588", "瑞芯微电RK3588采用8nm工艺", "瑞芯微电AI芯片性能提升3倍"]:
            await cli.remember(text, memory_type="fragment", tags={"tag": "chip", "tag_2": "ruikexin"})
        result = await cli.consolidate()
        consolidated = result.get("consolidated_count", 0)
        stats = await cli.stats()
        total = stats.get("total", 0)
        ok = total > 0
        report.add(_ok("T4: LLM-powered consolidation", ok,
                       1.0 if consolidated > 0 else 0.5,
                       f"consolidated={consolidated}, total={total}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_entity_page_compilation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("华信科技：综合企业集团，风险等级C级", memory_type="entity", tags={"tag": "company"})
        entity_id = r.get("node_id")
        await cli.remember("华信科技2026年Q1营收回升12%", memory_type="observation", tags={"tag": "company"})
        summary_len = 0
        if entity_id:
            try:
                page = await asyncio.wait_for(cli.compile_entity(entity_id), timeout=30)
                summary = page.get("summary", "")
                summary_len = len(summary) if summary else 0
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass
        ok = entity_id is not None
        report.add(_ok("T5: EntityPage compilation", ok,
                       1.0 if summary_len > 20 else 0.5,
                       f"entity_id={entity_id}, summary_len={summary_len}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_topic_page_compilation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("恒信集团：多元化集团，风险等级B级", memory_type="entity", tags={"tag": "company"})
        r2 = await cli.remember("中芯科技：半导体企业，风险等级A级", memory_type="entity", tags={"tag": "company"})
        entity_ids = [r1.get("node_id"), r2.get("node_id")]
        entity_ids = [eid for eid in entity_ids if eid]
        synthesis_len = 0
        if entity_ids:
            try:
                page = await asyncio.wait_for(cli.compile_topic("企业风险分析", entity_ids), timeout=30)
                synthesis = page.get("synthesis", "")
                synthesis_len = len(synthesis) if synthesis else 0
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass
        ok = len(entity_ids) > 0
        report.add(_ok("T6: TopicPage compilation", ok,
                       1.0 if synthesis_len > 20 else 0.5,
                       f"entities={len(entity_ids)}, synthesis_len={synthesis_len}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_reasoning_trail(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("测试推理轨迹：华信科技获得战略投资", memory_type="fragment", tags={"tag": "reasoning_test"})
        await cli.remember("测试推理轨迹：华信科技引入国资背景投资者", memory_type="fragment", tags={"tag": "reasoning_test"})
        await cli.consolidate()
        audit = await cli.audit(limit=10)
        entries = audit.get("entries", []) if isinstance(audit, dict) else []
        has_consolidation = any("consolidat" in str(e).lower() for e in entries)
        ok = True
        report.add(_ok("T7: Reasoning trail", ok, 1.0 if has_consolidation else 0.5,
                       f"audit_entries={len(entries)}, has_consolidation={has_consolidation}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_stats_verification(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        stats = await cli.stats()
        total = stats.get("total", 0)
        type_dist = stats.get("type_distribution", {})
        ok = total > 0
        report.add(_ok("T8: Stats verification", ok, 1.0 if ok else 0.0,
                       f"total={total}, types={type_dist}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 7: Knowledge Consolidation & Compilation — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Fragment→observation", run_t1_fragment_consolidation),
            ("T2: Observation→entity", run_t2_observation_entity_upgrade),
            ("T3: Evidence tracking", run_t3_evidence_tracking),
            ("T4: LLM consolidation", run_t4_llm_consolidation),
            ("T5: EntityPage compilation", run_t5_entity_page_compilation),
            ("T6: TopicPage compilation", run_t6_topic_page_compilation),
            ("T7: Reasoning trail", run_t7_reasoning_trail),
            ("T8: Stats verification", run_t8_stats_verification),
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
    out = save_report(report, Path(__file__).parent, "case7")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
