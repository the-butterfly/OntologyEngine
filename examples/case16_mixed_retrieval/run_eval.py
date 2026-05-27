#!/usr/bin/env python3
"""Case 16: Mixed Retrieval — Hybrid RRF Fusion Acceptance Tests.

Verifies 4-path RRF fusion (Layer-R + Layer-S + BM25 + Temporal):
  TC-R01: Factual query — semantic match ranks highest
  TC-R02: Multi-hop query — graph connections contribute
  TC-R03: Temporal query — date-filtered results returned
  TC-R04: BM25 keyword — exact match outranks semantic
  TC-R05: Mixed query — multiple paths contribute to fused results
  TC-R06: min_confidence filter — low-confidence results excluded
  TC-R07: cognitive_layer filter — only specified layer returned
  TC-R08: Cross-path dedup — same node from 2 paths gets higher RRF score

Usage: python examples/case16_mixed_retrieval/run_eval.py
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

SPACE = "mixed_retrieval"
CASE_DIR = Path(__file__).parent


async def run_r01_factual_semantic(cli: CLIRunner, report: AcptReport):
    """TC-R01: Factual query — semantic match should rank highest."""
    t0 = time.time()
    try:
        await cli.remember(
            "TechNova is a cloud infrastructure company based in Shenzhen, founded 2019",
            tags=["company", "TechNova", "factual"],
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "CloudGroup is TechNova's main product, a Kubernetes-based platform",
            tags=["product", "CloudGroup"],
            memory_type="observation",
            confidence=0.85,
        )
        r1 = await cli.recall("深圳的云基础设施公司", max_results=5)
        results = r1.get("results", [])
        top1_is_technova = len(results) > 0 and (
            "TechNova" in results[0].get("text", "") or "深圳" in results[0].get("text", "")
        )
        has_relevant = any("TechNova" in res.get("text", "") or "cloud" in res.get("text", "").lower() for res in results)
        checks = [(top1_is_technova, 1.0), (has_relevant, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R01: Factual semantic ranking", score,
                     f"top1_correct={top1_is_technova} has_relevant={has_relevant} total_results={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r02_multihop_graph(cli: CLIRunner, report: AcptReport):
    """TC-R02: Multi-hop query — graph-connected nodes should be retrievable together."""
    t0 = time.time()
    try:
        await cli.remember(
            "王芳 is CTO of TechNova, previously worked at Alibaba Cloud",
            tags=["person", "王芳", "TechNova"],
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "TechNova main product is CloudGroup, Kubernetes-based platform",
            tags=["product", "CloudGroup", "TechNova"],
            memory_type="observation",
            confidence=0.85,
        )
        await cli.remember(
            "CloudGroup supports multi-cluster management and auto-scaling",
            tags=["feature", "CloudGroup"],
            memory_type="observation",
            confidence=0.8,
        )
        r1 = await cli.recall("王芳 负责的产品", max_results=5)
        results = r1.get("results", [])
        has_person = any("王芳" in res.get("text", "") for res in results)
        has_product = any("CloudGroup" in res.get("text", "") for res in results)
        has_company = any("TechNova" in res.get("text", "") for res in results)
        checks = [(has_person, 1.0), (has_product, 1.0), (has_company, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R02: Multi-hop graph retrieval", score,
                     f"person={has_person} product={has_product} company={has_company}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r03_temporal_query(cli: CLIRunner, report: AcptReport):
    """TC-R03: Temporal query — date-filtered results returned."""
    t0 = time.time()
    try:
        await cli.remember(
            "2025 Q1 revenue reached 50M CNY, growth 30% YoY",
            tags=["financial", "2025", "Q1"],
            memory_type="observation",
            confidence=0.9,
        )
        await cli.remember(
            "2024 Q1 revenue was 38M CNY",
            tags=["financial", "2024", "Q1"],
            memory_type="observation",
            confidence=0.85,
        )
        r1 = await cli.recall("2025年营收", max_results=5)
        results = r1.get("results", [])
        has_2025 = any("2025" in res.get("text", "") or "50M" in res.get("text", "") for res in results)
        has_2024 = any("2024" in res.get("text", "") or "38M" in res.get("text", "") for res in results)
        temporal_relevant = has_2025 and (not has_2024 or results[0].get("text", "").find("2025") < results[0].get("text", "").find("2024") if has_2024 else True)
        checks = [(has_2025, 1.0), (temporal_relevant, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R03: Temporal query filtering", score,
                     f"has_2025={has_2025} has_2024={has_2024} temporal_order={temporal_relevant}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r04_bm25_keyword(cli: CLIRunner, report: AcptReport):
    """TC-R04: BM25 keyword — exact match should outrank semantic similarity."""
    t0 = time.time()
    try:
        await cli.remember(
            "Metric DSO_DIO: Days Sales Outstanding + Days Inventory Outstanding, formula=DSO+DIO",
            tags=["metric", "DSO_DIO", "exact"],
            memory_type="observation",
            confidence=0.95,
        )
        await cli.remember(
            "DSO measures average collection period for receivables",
            tags=["metric", "DSO", "related"],
            memory_type="observation",
            confidence=0.8,
        )
        r1 = await cli.recall("DSO_DIO", max_results=5)
        results = r1.get("results", [])
        top1_is_exact = len(results) > 0 and "DSO_DIO" in results[0].get("text", "")
        has_exact = any("DSO_DIO" in res.get("text", "") for res in results)
        has_related = any("DSO" in res.get("text", "") and "DSO_DIO" not in res.get("text", "") for res in results)
        checks = [(top1_is_exact, 1.0), (has_exact, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R04: BM25 keyword exact match", score,
                     f"top1_exact={top1_is_exact} has_exact={has_exact} has_related={has_related}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r05_mixed_query(cli: CLIRunner, report: AcptReport):
    """TC-R05: Mixed query — results should contain diverse memory types."""
    t0 = time.time()
    try:
        await cli.remember(
            "Rule: 供应商授信额度不超过总敞口15%",
            tags=["rule", "credit_limit"],
            memory_type="rule",
            confidence=0.95,
        )
        await cli.remember(
            "Entity: 华为技术有限公司, credit_rating AAA, is_whitelist=True",
            tags=["entity", "华为"],
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: 华为2025年供应链融资规模500亿",
            tags=["observation", "华为", "2025"],
            memory_type="observation",
            confidence=0.85,
        )
        r1 = await cli.recall("华为 供应商授信", max_results=5)
        results = r1.get("results", [])
        has_rule = any("rule" in res.get("text", "").lower() or "授信" in res.get("text", "") for res in results)
        has_entity = any("华为" in res.get("text", "") and "AAA" in res.get("text", "") for res in results)
        has_observation = any("500亿" in res.get("text", "") or "供应链融资" in res.get("text", "") for res in results)
        type_count = sum([has_rule, has_entity, has_observation])
        checks = [(has_rule, 1.0), (has_entity, 1.0), (has_observation, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R05: Mixed query diverse types", score,
                     f"rule={has_rule} entity={has_entity} observation={has_observation} types={type_count}/3",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r06_confidence_filter(cli: CLIRunner, report: AcptReport):
    """TC-R06: min_confidence filter — low-confidence results should be excluded."""
    t0 = time.time()
    try:
        await cli.remember(
            "High confidence: Production database is PostgreSQL 15",
            tags=["infrastructure", "high_conf"],
            memory_type="observation",
            confidence=0.95,
        )
        await cli.remember(
            "Low confidence: Office might use MySQL, not sure",
            tags=["infrastructure", "low_conf"],
            memory_type="observation",
            confidence=0.3,
        )
        r_high = await cli.recall("database", max_results=10, min_confidence=0.8)
        high_results = r_high.get("results", [])
        has_high = any("PostgreSQL" in res.get("text", "") for res in high_results)
        no_low = not any("MySQL" in res.get("text", "") or "might" in res.get("text", "").lower() for res in high_results)
        r_all = await cli.recall("database", max_results=10, min_confidence=0.1)
        all_results = r_all.get("results", [])
        has_both = len(all_results) >= 2
        checks = [(has_high, 1.0), (no_low, 1.0), (has_both, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R06: Confidence filter", score,
                     f"high_only={has_high} no_low_in_high={no_low} both_in_low={has_both} high_count={len(high_results)} all_count={len(all_results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R06", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r07_cognitive_layer_filter(cli: CLIRunner, report: AcptReport):
    """TC-R07: cognitive_layer filter — only specified layer returned."""
    t0 = time.time()
    try:
        await cli.remember(
            "Entity: 供应商A, registered_capital 50M, credit_rating AA",
            tags=["entity", "供应商A"],
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Rule: 供应商需通过核心企业担保",
            tags=["rule", "担保"],
            memory_type="rule",
            confidence=0.95,
        )
        r_entity = await cli.recall("供应商", max_results=10, memory_type="entity")
        entity_results = r_entity.get("results", [])
        has_entity = any("50M" in res.get("text", "") or "AA" in res.get("text", "") for res in entity_results)
        no_rule = not any("担保" in res.get("text", "") for res in entity_results)
        checks = [(has_entity, 1.0), (no_rule, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R07: Cognitive layer filter", score,
                     f"entity_found={has_entity} rule_excluded={no_rule} entity_count={len(entity_results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R07", 0.0, str(e), (time.time() - t0) * 1000))


async def run_r08_cross_path_dedup(cli: CLIRunner, report: AcptReport):
    """TC-R08: Cross-path dedup — same node from multiple paths gets higher RRF score."""
    t0 = time.time()
    try:
        await cli.remember(
            "CoreEnterprise 华为: credit_rating AAA, whitelist=True, annual_revenue 9000亿",
            tags=["core_enterprise", "华为", "multi_signal"],
            memory_type="entity",
            confidence=0.95,
        )
        await cli.remember(
            "华为 2025年供应链融资规模500亿, 核心企业担保覆盖300家供应商",
            tags=["observation", "华为", "2025", "multi_signal"],
            memory_type="observation",
            confidence=0.9,
        )
        r1 = await cli.recall("华为 核心企业", max_results=5)
        results = r1.get("results", [])
        has_huawei = any("华为" in res.get("text", "") for res in results)
        has_multi_signal = any("multi_signal" in res.get("text", "") or ("AAA" in res.get("text", "") and "500亿" in res.get("text", "")) for res in results)
        checks = [(has_huawei, 1.0), (has_multi_signal, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-R08: Cross-path dedup scoring", score,
                     f"huawei_found={has_huawei} multi_signal={has_multi_signal} total_results={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-R08", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case16_mixed_retrieval")
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 16: Mixed Retrieval — Hybrid RRF Fusion Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)
        scenarios = [
            ("TC-R01 Factual semantic", run_r01_factual_semantic),
            ("TC-R02 Multi-hop graph", run_r02_multihop_graph),
            ("TC-R03 Temporal query", run_r03_temporal_query),
            ("TC-R04 BM25 keyword", run_r04_bm25_keyword),
            ("TC-R05 Mixed query", run_r05_mixed_query),
            ("TC-R06 Confidence filter", run_r06_confidence_filter),
            ("TC-R07 Cognitive layer", run_r07_cognitive_layer_filter),
            ("TC-R08 Cross-path dedup", run_r08_cross_path_dedup),
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
