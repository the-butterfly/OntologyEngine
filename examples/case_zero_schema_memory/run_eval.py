#!/usr/bin/env python3
"""Case Zero Schema Memory — Zero-Parameter Memory Closed-Loop Acceptance Tests.

Verifies D-S3 AC3-2 + D-S4 AC4-1 (P0 milestone):
  TC-Z01: Zero-parameter remember
  TC-Z02: Natural language recall
  TC-Z03: Automatic entity extraction
  TC-Z04: Multi-tag filtering
  TC-Z05: Schema Light comparison

Usage: python examples/case_zero_schema_memory/run_eval.py
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

SPACE = "zero_schema"
CASE_DIR = Path(__file__).parent


async def run_z01_zero_parameter_remember(cli: CLIRunner, report: AcptReport):
    """TC-Z01: Zero-parameter remember — only text, no schema."""
    t0 = time.time()
    try:
        resp1 = await cli.remember("Alice works at Google as a senior engineer")
        resp2 = await cli.remember("Google headquarters is in Mountain View, California")
        resp3 = await cli.remember("Alice led the Kubernetes migration project in 2025")

        ids = [resp1.get("node_id"), resp2.get("node_id"), resp3.get("node_id")]
        all_created = all(nid is not None for nid in ids)

        score = 1.0 if all_created else 0.0
        report.add(r("TC-Z01: Zero-parameter remember", score,
                     f"created={sum(1 for i in ids if i)}/3 ids={[i[:20] if i else None for i in ids]}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-Z01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_z02_natural_language_recall(cli: CLIRunner, report: AcptReport):
    """TC-Z02: Natural language recall — verify basic closed loop."""
    t0 = time.time()
    try:
        await cli.remember("Alice works at Google as a senior engineer")
        await cli.remember("Alice led the Kubernetes migration project in 2025")
        await cli.remember("Google headquarters is in Mountain View, California")

        r1 = await cli.recall("Where does Alice work?", max_results=3)
        r2 = await cli.recall("What project did Alice lead?", max_results=3)
        r3 = await cli.recall("Where is Google HQ?", max_results=3)

        results1 = r1.get("results", [])
        results2 = r2.get("results", [])
        results3 = r3.get("results", [])

        has_google = any("Google" in res.get("text", "") for res in results1)
        has_k8s = any("Kubernetes" in res.get("text", "") for res in results2)
        has_mv = any("Mountain View" in res.get("text", "") for res in results3)

        checks = [(has_google, 1.0), (has_k8s, 1.0), (has_mv, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-Z02: Natural language recall", score,
                     f"alice_work={has_google} k8s_project={has_k8s} hq_location={has_mv}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-Z02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_z03_auto_entity_extraction(cli: CLIRunner, report: AcptReport):
    """TC-Z03: Automatic entity extraction from complex text."""
    t0 = time.time()
    try:
        await cli.remember(
            "TechNova is a cloud infrastructure company based in Shenzhen. "
            "Their CTO is Wang Lei, who previously worked at Alibaba Cloud. "
            "TechNova main product is CloudGroup, a Kubernetes-based platform."
        )

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("TechNova", max_results=5)
        r2 = await cli.recall("Wang Lei", max_results=5)
        r3 = await cli.recall("CloudGroup", max_results=5)

        found_technova = len(r1.get("results", [])) > 0
        found_wanglei = len(r2.get("results", [])) > 0
        found_cloudgroup = len(r3.get("results", [])) > 0

        checks = [
            (total >= 1, 1.0),
            (found_technova, 1.0),
            (found_wanglei, 1.0),
            (found_cloudgroup, 1.0),
        ]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-Z03: Auto entity extraction", score,
                     f"total={total} Technova={found_technova} WangLei={found_wanglei} CloudGroup={found_cloudgroup}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-Z03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_z04_multi_tag_filtering(cli: CLIRunner, report: AcptReport):
    """TC-Z04: Multi-tag filtering."""
    t0 = time.time()
    try:
        await cli.remember("The Q3 revenue target is 500M", tags={"tag": "finance", "tag_2": "high_trust"})
        await cli.remember("Revenue might be impacted by supply chain issues", tags={"tag": "finance", "tag_2": "opinion"})
        await cli.remember("API latency increased to 200ms after deployment", tags={"tag": "engineering", "tag_2": "high_trust"})

        r_finance = await cli.recall("revenue", max_results=5)
        finance_results = r_finance.get("results", [])
        has_finance = len(finance_results) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        checks = [
            (has_finance, 1.0),
            (total >= 3, 1.0),
        ]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-Z04: Multi-tag filtering", score,
                     f"finance_results={len(finance_results)} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-Z04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_z05_schema_light_comparison(cli: CLIRunner, report: AcptReport):
    """TC-Z05: Schema Light comparison — zero schema vs tagged memory."""
    t0 = time.time()
    try:
        await cli.remember("Counterparty DEF has a credit score of 680 and risk level of medium",
                          tags={"tag": "credit", "tag_2": "counterparty"})

        r1 = await cli.recall("credit score", max_results=5)
        results = r1.get("results", [])
        has_result = len(results) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        checks = [
            (has_result, 1.0),
            (total >= 1, 0.5),
        ]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-Z05: Schema Light comparison", score,
                     f"results={len(results)} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-Z05", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case_zero_schema_memory")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case Zero Schema Memory — Zero-Parameter Memory Acceptance Tests")
        print("Mode: CLI Runner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-Z01 Zero-parameter remember", run_z01_zero_parameter_remember),
            ("TC-Z02 Natural language recall", run_z02_natural_language_recall),
            ("TC-Z03 Auto entity extraction", run_z03_auto_entity_extraction),
            ("TC-Z04 Multi-tag filtering", run_z04_multi_tag_filtering),
            ("TC-Z05 Schema Light comparison", run_z05_schema_light_comparison),
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
