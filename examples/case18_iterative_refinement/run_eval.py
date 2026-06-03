#!/usr/bin/env python3
"""Case 18: Iterative Refinement — Deep Research Support.

Verifies multi-round recall refinement for long-task support:
  TC-I01: Round 1 broad → Round 2 targeted → accuracy improves
  TC-I02: Gap analysis — identify missing knowledge types after Round 1
  TC-I03: Query refinement — add memory_type filter based on Round 1 results
  TC-I04: Evidence chain expansion — recall → get_node → deeper recall
  TC-I05: State checkpoint — save recall state, resume after new knowledge added
  TC-I06: Convergence detection — recall results stabilize after N rounds

Usage: python examples/case18_iterative_refinement/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.agent_memory._lib.cli_runner import CLIRunner, create_runner
from examples.agent_memory._lib.acpt_test import AcptReport, r

SPACE = "iterative_refinement"
CASE_DIR = Path(__file__).parent


async def run_i01_broad_to_targeted(cli: CLIRunner, report: AcptReport):
    """TC-I01: Round 1 broad recall → Round 2 targeted → accuracy improves."""
    t0 = time.time()
    try:
        await cli.remember(
            "Entity: TechNova, cloud infrastructure, Shenzhen, founded 2019, revenue 500M",
            tags={"tag": "company", "tag_2": "TechNova", "tag_3": "entity"},
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: TechNova Q3营收增长30%, 毛利率42%",
            tags={"tag": "company", "tag_2": "TechNova", "tag_3": "financial"},
            memory_type="observation",
            confidence=0.85,
        )
        await cli.remember(
            "Rule: cloud行业供应商准入标准: 注册资本>=1000万, 成立>=3年",
            tags={"tag": "rule", "tag_2": "cloud", "tag_3": "准入"},
            memory_type="rule",
            confidence=0.95,
        )
        await cli.remember(
            "Opinion: TechNova技术实力强, 但交付能力有待观察",
            tags={"tag": "company", "tag_2": "TechNova", "tag_3": "opinion"},
            memory_type="opinion",
            confidence=0.7,
        )
        r1 = await cli.recall("TechNova", max_results=10)
        round1_results = r1.get("results", [])
        round1_count = len(round1_results)
        r2 = await cli.recall("TechNova 财务", max_results=10, memory_type="observation")
        round2_results = r2.get("results", [])
        round2_financial = any("营收" in res.get("text", "") or "毛利率" in res.get("text", "") for res in round2_results)
        precision_improved = round2_financial and (round1_count == 0 or len(round2_results) <= round1_count)
        checks = [(round1_count >= 1, 1.0), (round2_financial, 1.0), (precision_improved, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-I01: Broad to targeted", score,
                     f"round1={round1_count} round2={len(round2_results)} financial_found={round2_financial} precision_improved={precision_improved}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-I01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_i02_gap_analysis(cli: CLIRunner, report: AcptReport):
    """TC-I02: Gap analysis — identify missing knowledge types after Round 1."""
    t0 = time.time()
    try:
        await cli.remember(
            "Entity: 供应商B, 注册资本2000万, 成立5年",
            tags={"tag": "supplier", "tag_2": "供应商B", "tag_3": "entity"},
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: 供应商B Q2交付准时率88%",
            tags={"tag": "supplier", "tag_2": "供应商B", "tag_3": "delivery"},
            memory_type="observation",
            confidence=0.8,
        )
        r1 = await cli.recall("供应商B", max_results=10)
        results = r1.get("results", [])
        has_entity = any("Entity" in res.get("text", "") or "注册资本" in res.get("text", "") for res in results)
        has_observation = any("Observation" in res.get("text", "") or "交付" in res.get("text", "") for res in results)
        has_rule = any("Rule" in res.get("text", "") or "准入标准" in res.get("text", "") for res in results)
        has_mental_model = any("Mental model" in res.get("text", "") for res in results)
        missing_types = []
        if not has_rule:
            missing_types.append("rule")
        if not has_mental_model:
            missing_types.append("mental_model")
        gap_identified = len(missing_types) > 0
        checks = [(has_entity, 1.0), (has_observation, 1.0), (gap_identified, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-I02: Gap analysis", score,
                     f"entity={has_entity} observation={has_observation} rule={has_rule} mental_model={has_mental_model} missing={missing_types}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-I02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_i03_query_refinement(cli: CLIRunner, report: AcptReport):
    """TC-I03: Query refinement — add memory_type filter based on Round 1 results."""
    t0 = time.time()
    try:
        await cli.remember(
            "Entity: 华为, credit_rating AAA, revenue 9000亿",
            tags={"tag": "company", "tag_2": "华为", "tag_3": "entity"},
            memory_type="entity",
            confidence=0.95,
        )
        await cli.remember(
            "Rule: 核心企业白名单制度, 华为在名单内",
            tags={"tag": "rule", "tag_2": "华为", "tag_3": "whitelist"},
            memory_type="rule",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: 华为2025年供应链融资500亿",
            tags={"tag": "observation", "tag_2": "华为", "tag_3": "financing"},
            memory_type="observation",
            confidence=0.85,
        )
        await cli.remember(
            "Fragment: 听说华为在考虑新的供应商政策",
            tags={"tag": "fragment", "tag_2": "华为", "tag_3": "rumor"},
            memory_type="fragment",
            confidence=0.4,
        )
        r1 = await cli.recall("华为", max_results=10)
        round1_all = len(r1.get("results", []))
        r2 = await cli.recall("华为", max_results=10, memory_type="entity")
        round2_entity = len(r2.get("results", []))
        entity_only = all("AAA" in res.get("text", "") or "Entity" in res.get("text", "") or "华为" in res.get("text", "") for res in r2.get("results", []))
        r3 = await cli.recall("华为", max_results=10, memory_type="rule")
        round3_rule = len(r3.get("results", []))
        rule_only = all("白名单" in res.get("text", "") or "Rule" in res.get("text", "") for res in r3.get("results", []))
        refinement_works = round2_entity <= round1_all and round3_rule <= round1_all and entity_only and rule_only
        checks = [(round1_all >= 3, 1.0), (entity_only, 1.0), (rule_only, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-I03: Query refinement", score,
                     f"round1_all={round1_all} round2_entity={round2_entity} round3_rule={round3_rule} entity_only={entity_only} rule_only={rule_only}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-I03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_i04_evidence_chain(cli: CLIRunner, report: AcptReport):
    """TC-I04: Evidence chain expansion — recall → get_node → deeper recall."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "Entity: 担保圈风险企业A, 担保链深度3层, 涉及B→C→D",
            tags={"tag": "risk", "tag_2": "担保圈", "tag_3": "企业A"},
            memory_type="entity",
            confidence=0.9,
        )
        node_a_id = resp1.get("node_id")
        await cli.remember(
            "Observation: 企业B为企业A担保5000万",
            tags={"tag": "risk", "tag_2": "担保圈", "tag_3": "企业B"},
            memory_type="observation",
            confidence=0.85,
        )
        await cli.remember(
            "Observation: 企业C为企业B担保3000万",
            tags={"tag": "risk", "tag_2": "担保圈", "tag_3": "企业C"},
            memory_type="observation",
            confidence=0.8,
        )
        await cli.remember(
            "Rule: 担保圈深度超过3层需特别审查",
            tags={"tag": "rule", "tag_2": "担保圈", "tag_3": "审查"},
            memory_type="rule",
            confidence=0.95,
        )
        r1 = await cli.recall("担保圈 企业A", max_results=5)
        has_entity = any("企业A" in res.get("text", "") for res in r1.get("results", []))
        r2 = await cli.recall("担保圈 企业B 企业C", max_results=5)
        has_chain = any("企业B" in res.get("text", "") and "企业C" in res.get("text", "") for res in r2.get("results", []))
        if not has_chain:
            has_chain = any("企业B" in res.get("text", "") for res in r2.get("results", [])) and any("企业C" in res.get("text", "") for res in r2.get("results", []))
        r3 = await cli.recall("担保圈 审查", max_results=5, memory_type="rule")
        has_rule = any("3层" in res.get("text", "") or "特别审查" in res.get("text", "") for res in r3.get("results", []))
        chain_complete = has_entity and has_chain and has_rule
        checks = [(has_entity, 1.0), (has_chain, 1.0), (has_rule, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-I04: Evidence chain expansion", score,
                     f"entity={has_entity} chain={has_chain} rule={has_rule} complete={chain_complete}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-I04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_i05_state_checkpoint(cli: CLIRunner, report: AcptReport):
    """TC-I05: State checkpoint — save recall state, resume after new knowledge added."""
    t0 = time.time()
    try:
        await cli.remember(
            "Entity: 供应商C, 注册资本3000万, 主营电子元器件",
            tags={"tag": "supplier", "tag_2": "供应商C", "tag_3": "entity"},
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: 供应商C 2024年交付准时率92%",
            tags={"tag": "supplier", "tag_2": "供应商C", "tag_3": "delivery"},
            memory_type="observation",
            confidence=0.85,
        )
        r1 = await cli.recall("供应商C", max_results=10)
        round1_count = len(r1.get("results", []))
        round1_ids = set(res.get("id", res.get("node_id", "")) for res in r1.get("results", []))
        await cli.remember(
            "Rule: 电子元器件供应商需通过ISO9001认证",
            tags={"tag": "rule", "tag_2": "电子元器件", "tag_3": "ISO9001"},
            memory_type="rule",
            confidence=0.95,
        )
        await cli.remember(
            "Observation: 供应商C已通过ISO9001认证",
            tags={"tag": "supplier", "tag_2": "供应商C", "tag_3": "ISO9001"},
            memory_type="observation",
            confidence=0.9,
        )
        r2 = await cli.recall("供应商C", max_results=10)
        round2_count = len(r2.get("results", []))
        round2_ids = set(res.get("id", res.get("node_id", "")) for res in r2.get("results", []))
        new_knowledge_found = round2_count > round1_count
        original_preserved = round1_ids.issubset(round2_ids) if round1_ids else True
        checks = [(round1_count >= 1, 1.0), (new_knowledge_found, 1.0), (original_preserved, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-I05: State checkpoint", score,
                     f"round1={round1_count} round2={round2_count} new_found={new_knowledge_found} original_preserved={original_preserved}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-I05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_i06_convergence_detection(cli: CLIRunner, report: AcptReport):
    """TC-I06: Convergence detection — recall results stabilize after N rounds."""
    t0 = time.time()
    try:
        await cli.remember(
            "Entity: 供应商D, 注册资本1000万, 主营物流服务",
            tags={"tag": "supplier", "tag_2": "供应商D", "tag_3": "entity"},
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: 供应商D 2024年准时交付率95%",
            tags={"tag": "supplier", "tag_2": "供应商D", "tag_3": "delivery"},
            memory_type="observation",
            confidence=0.85,
        )
        await cli.remember(
            "Opinion: 供应商D服务态度好, 但价格偏高",
            tags={"tag": "supplier", "tag_2": "供应商D", "tag_3": "opinion"},
            memory_type="opinion",
            confidence=0.7,
        )
        prev_ids = None
        converged = False
        rounds = 0
        for i in range(3):
            resp = await cli.recall("供应商D", max_results=10)
            results = resp.get("results", [])
            current_ids = frozenset(res.get("id", res.get("node_id", "")) for res in results)
            if prev_ids is not None and current_ids == prev_ids:
                converged = True
                break
            prev_ids = current_ids
            rounds += 1
        checks = [(rounds >= 1, 1.0), (converged, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-I06: Convergence detection", score,
                     f"rounds={rounds} converged={converged} final_count={len(prev_ids) if prev_ids else 0}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-I06", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case18_iterative_refinement")
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 18: Iterative Refinement — Deep Research Support")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)
        scenarios = [
            ("TC-I01 Broad to targeted", run_i01_broad_to_targeted),
            ("TC-I02 Gap analysis", run_i02_gap_analysis),
            ("TC-I03 Query refinement", run_i03_query_refinement),
            ("TC-I04 Evidence chain", run_i04_evidence_chain),
            ("TC-I05 State checkpoint", run_i05_state_checkpoint),
            ("TC-I06 Convergence", run_i06_convergence_detection),
        ]
        for name, fn in scenarios:
            print(f"\n--- {name} ---")
            try:
                await asyncio.wait_for(fn(runner, report), timeout=120)
            except asyncio.TimeoutError:
                report.add(r(name, 0.0, "TIMEOUT", 120000))
            await asyncio.sleep(0.5)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n" + report.summary())
    out = report.save(CASE_DIR)
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    asyncio.run(main())
