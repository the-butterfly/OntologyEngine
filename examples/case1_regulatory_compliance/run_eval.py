#!/usr/bin/env python3
"""Case 1: Regulatory Compliance — Circular 23 Acceptance Tests.

6 test cases using CLIRunner (Memory API interface):
  TC-101: Schema + instance loading
  TC-102: Baseline compliance analysis
  TC-103: Whitelist update + re-analysis
  TC-104: Version rollback
  TC-105: Recall evidence fragments
  TC-106: Reflect analysis summary

Usage: python examples/case1_regulatory_compliance/run_eval.py
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

SPACE = "case1_circular23"
CASE_DIR = Path(__file__).parent


async def run_tc101(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("Supplier SUP_A: 深圳智造科技有限公司, registered_capital 50M CNY", tags=["supplier", "SUP_A"], created_by="compliance_test")
        r2 = await cli.remember("Supplier SUP_B: 某贸易有限公司, registered_capital 1M CNY", tags=["supplier", "SUP_B"], created_by="compliance_test")
        r3 = await cli.remember("CoreEnterprise CE_HW: 华为技术有限公司, credit_rating AAA, is_in_regulatory_whitelist=True", tags=["core_enterprise", "CE_HW"], created_by="compliance_test")
        r4 = await cli.remember("Invoice INV_001: amount 5M, supplier SUP_A, verified=True", tags=["invoice", "evidence"], created_by="compliance_test")
        all_created = all(r.get("node_id") is not None for r in [r1, r2, r3, r4])
        stats = await cli.stats()
        total = stats.get("total", 0)
        checks = [(all_created, 1.0), (total >= 4, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-101: Schema + instance loading", score, f"created={sum(1 for r in [r1,r2,r3,r4] if r.get('node_id'))}/4 total={total}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-101", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc102(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        for i, (sid, name, capital) in enumerate([("SUP_A", "深圳智造科技", "50M"), ("SUP_B", "某贸易公司", "1M"), ("SUP_C", "新兴科技", "5M"), ("SUP_D", "卓越制造", "100M"), ("SUP_E", "部分担保供应商", "20M")]):
            await cli.remember(f"Supplier {sid}: {name}, registered_capital {capital} CNY, status ACTIVE", tags=["supplier", sid, "baseline"], created_by="compliance_test")
        await cli.remember("CoreEnterprise CE_HW: 华为, is_in_regulatory_whitelist=True", tags=["core_enterprise", "whitelist"], created_by="compliance_test")
        r1 = await cli.recall("supplier baseline", max_results=10)
        found = len(r1.get("results", []))
        checks = [(found >= 5, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-102: Baseline compliance analysis", score, f"suppliers_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-102", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc103(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Whitelist v2026.04.2 update: added SUP_C5 as pilot enterprise", tags=["whitelist", "v2026.04.2", "update"], memory_type="observation", created_by="compliance_test")
        await cli.remember("Supplier SUP_C5: 试点企业, registered_capital 30M CNY, is_in_regulatory_whitelist=True", tags=["supplier", "SUP_C5", "whitelist"], created_by="compliance_test")
        r1 = await cli.recall("whitelist v2026.04.2", max_results=3)
        has_update = any("v2026.04.2" in res.get("text", "") or "SUP_C5" in res.get("text", "") for res in r1.get("results", []))
        checks = [(has_update, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-103: Whitelist update + re-analysis", score, f"whitelist_update_found={has_update}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-103", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc104(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        # Step 1: Store v2026.04.2 whitelist entry
        await cli.remember("Whitelist v2026.04.2: SUP_C5 is approved pilot enterprise", tags=["whitelist", "v2026.04.2"], memory_type="observation", created_by="compliance_test")
        r_v2 = await cli.recall("whitelist v2026.04.2 SUP_C5", max_results=3)
        v2_exists = any("SUP_C5" in res.get("text", "") for res in r_v2.get("results", []))

        # Step 2: Store rollback record (simulating revert to v2026.04.1 where SUP_C5 is NOT approved)
        await cli.remember("Version rollback: whitelist reverted from v2026.04.2 to v2026.04.1. SUP_C5 approval revoked.", tags=["whitelist", "rollback", "v2026.04.1"], memory_type="observation", created_by="compliance_test")

        # Step 3: Verify rollback record is retrievable and references both versions
        r_rollback = await cli.recall("whitelist rollback v2026.04.1", max_results=3)
        has_rollback = any("rollback" in res.get("text", "").lower() or "v2026.04.1" in res.get("text", "") for res in r_rollback.get("results", []))

        # Step 4: Verify version history is traceable (both v2026.04.1 and v2026.04.2 records exist)
        r_history = await cli.recall("whitelist version history SUP_C5", max_results=5)
        history_results = r_history.get("results", [])
        has_v1_ref = any("v2026.04.1" in res.get("text", "") for res in history_results)
        has_v2_ref = any("v2026.04.2" in res.get("text", "") for res in history_results)
        has_version_trace = has_v1_ref and has_v2_ref

        checks = [(v2_exists, 0.5), (has_rollback, 1.0), (has_version_trace, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-104: Version rollback", score, f"v2_existed={v2_exists} rollback_found={has_rollback} version_trace={has_version_trace}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-104", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc105(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("银发〔2026〕23号 第八条: 核心企业白名单制度，供应商需通过核心企业担保", tags=["regulation", "circular23", "article8"], memory_type="observation", created_by="compliance_test")
        await cli.remember("Invoice evidence: SUP_A invoice INV_001 verified, amount 5M CNY", tags=["evidence", "invoice", "SUP_A"], created_by="compliance_test")
        r1 = await cli.recall("银发〔2026〕23号 第八条", max_results=5)
        has_regulation = any("23号" in res.get("text", "") or "第八条" in res.get("text", "") for res in r1.get("results", []))
        r2 = await cli.recall("invoice evidence SUP_A", max_results=3)
        has_evidence = len(r2.get("results", [])) > 0
        checks = [(has_regulation, 1.0), (has_evidence, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-105: Recall evidence fragments", score, f"regulation_found={has_regulation} evidence_found={has_evidence}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-105", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc106(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Compliance risk report: 5 suppliers analyzed, 1 passed (20%), 4 failed. Key finding: whitelist coverage low. Risk level: HIGH. Action: expand whitelist or reject non-compliant suppliers.", tags=["report", "compliance", "risk"], memory_type="observation", created_by="compliance_test")
        r1 = await cli.recall("compliance risk report", max_results=3)
        has_report = any("risk" in res.get("text", "").lower() and "compliance" in res.get("text", "").lower() for res in r1.get("results", []))
        r2 = await cli.recall("key findings whitelist", max_results=3)
        has_findings = any("whitelist" in res.get("text", "").lower() for res in r2.get("results", []))
        checks = [(has_report, 1.0), (has_findings, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-106: Reflect analysis summary", score, f"report_found={has_report} findings_found={has_findings}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-106", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case1_regulatory_compliance")
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 1: Regulatory Compliance — Circular 23 Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)
        scenarios = [
            ("TC-101 Schema + instance loading", run_tc101),
            ("TC-102 Baseline compliance analysis", run_tc102),
            ("TC-103 Whitelist update + re-analysis", run_tc103),
            ("TC-104 Version rollback", run_tc104),
            ("TC-105 Recall evidence fragments", run_tc105),
            ("TC-106 Reflect analysis summary", run_tc106),
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
