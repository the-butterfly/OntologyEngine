#!/usr/bin/env python3
"""Case 3: APAC HQ Strategy Sandbox — Acceptance Tests.

6 test cases using CLIRunner (Memory API interface):
  TC-301: Scenario A loading (HK-dominant)
  TC-302: Scenario B loading (SG-dominant)
  TC-303: Scenario C loading (dual-center)
  TC-304: Scenario comparison (A vs B vs C)
  TC-305: Parameter change impact (B v1 → B v1.1)
  TC-306: Recommendation report generation

Usage: python examples/case3_tax_simulation/run_eval.py
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

SPACE = "case3_tax_simulation"
CASE_DIR = Path(__file__).parent


async def run_tc301(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Scenario A: HK-dominant APAC HQ. Subsidiary HK_01 in Hong Kong, annual_revenue 500M HKD, employee_count 120.", tags=["scenario_A", "HK", "subsidiary"], created_by="tax_test")
        r1 = await cli.recall("Scenario A HK subsidiary", max_results=3)
        found = any("HK" in res.get("text", "") and "500M" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-301: Scenario A loading", score, f"HK_scenario_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-301", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc302(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Scenario B: SG-dominant APAC HQ. Subsidiary SG_01 in Singapore, annual_revenue 400M SGD, employee_count 200.", tags=["scenario_B", "SG", "subsidiary"], created_by="tax_test")
        r1 = await cli.recall("Scenario B SG subsidiary", max_results=3)
        found = any("SG" in res.get("text", "") and "400M" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-302: Scenario B loading", score, f"SG_scenario_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-302", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc303(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Scenario C: Dual-center APAC HQ. HK_01 in Hong Kong, SG_01 in Singapore, CN_01 in Shanghai. Multi-jurisdiction structure.", tags=["scenario_C", "dual_center", "multi_jurisdiction"], created_by="tax_test")
        r1 = await cli.recall("Scenario C dual-center", max_results=5)
        results = r1.get("results", [])
        has_hk = any("HK" in res.get("text", "") for res in results)
        has_sg = any("SG" in res.get("text", "") for res in results)
        has_cn = any("CN" in res.get("text", "") or "Shanghai" in res.get("text", "") for res in results)
        checks = [(has_hk, 0.5), (has_sg, 0.5), (has_cn, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-303: Scenario C loading", score, f"HK={has_hk} SG={has_sg} CN={has_cn}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-303", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc304(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Scenario comparison analysis: A(HK 16.5% tax) vs B(SG 17% tax) vs C(dual HK+SG+CN). A: lowest single-jurisdiction. B: best trading hub. C: optimal overall but highest setup cost.", tags=["comparison", "scenario_analysis", "tc304"], memory_type="observation", created_by="tax_test")
        r1 = await cli.recall("scenario comparison analysis", max_results=3)
        found = any("comparison" in res.get("text", "").lower() for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-304: Scenario comparison", score, f"comparison_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-304", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc305(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Scenario B v1.1: SG tax incentive reduces effective rate from 17% to 12% for regional HQ. IntercompanyTransaction TXN_001: HK_01→SG_01, amount 100M, treaty_rate 7%.", tags=["parameter_change", "scenario_B", "v1.1", "transaction"], memory_type="observation", created_by="tax_test")
        r1 = await cli.recall("Scenario B v1.1 parameter change", max_results=3)
        found = any("v1.1" in res.get("text", "") or "12" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-305: Parameter change impact", score, f"parameter_change_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-305", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc306(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Recommendation: Scenario B v1.1 (SG-led) is optimal. Effective tax rate 12%, lower setup cost SGD 3M, strong trading hub infrastructure. Risk: policy change may remove incentive.", tags=["recommendation", "scenario_B", "optimal"], memory_type="observation", created_by="tax_test")
        r1 = await cli.recall("recommendation APAC HQ optimal", max_results=3)
        found = any("recommendation" in res.get("text", "").lower() or "optimal" in res.get("text", "").lower() for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-306: Recommendation report", score, f"recommendation_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-306", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case3_tax_simulation")
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 3: APAC HQ Strategy Sandbox — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)
        scenarios = [
            ("TC-301 Scenario A loading", run_tc301),
            ("TC-302 Scenario B loading", run_tc302),
            ("TC-303 Scenario C loading", run_tc303),
            ("TC-304 Scenario comparison", run_tc304),
            ("TC-305 Parameter change impact", run_tc305),
            ("TC-306 Recommendation report", run_tc306),
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
