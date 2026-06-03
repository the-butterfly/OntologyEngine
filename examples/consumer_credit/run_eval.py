#!/usr/bin/env python3
"""Consumer Credit Risk Assessment — OntologyEngine Acceptance Tests.

Runs 6 test cases against the consumer credit schema using CLIRunner.

Usage: python examples/consumer_credit/run_eval.py
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

SPACE = "consumer_credit"
CASE_DIR = Path(__file__).parent


async def run_c01_quality_borrower(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        resp = await cli.remember(
            "Borrower B001: credit_score 780, income 30000/month, "
            "employment 5 years, no defaults, installment_loan approved",
            tags={"tag": "borrower", "tag_2": "B001", "tag_3": "quality"},
            created_by="credit_test"
        )
        node_created = resp.get("node_id") is not None
        r1 = await cli.recall("B001 credit score", max_results=3)
        found = any("780" in res.get("text", "") for res in r1.get("results", []))
        checks = [(node_created, 1.0), (found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-C01: Quality borrower installment loan", score,
                     f"created={node_created} found={found}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-C01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_c02_quick_loan_routing(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Quick loan product: max_amount 50000, term 12 months, "
            "requires credit_score >= 650, auto_approval enabled",
            tags={"tag": "product", "tag_2": "quick_loan"},
            memory_type="observation",
            created_by="credit_test"
        )
        await cli.remember(
            "Borrower B002: credit_score 700, applied for quick_loan, approved",
            tags={"tag": "borrower", "tag_2": "B002", "tag_3": "quick_loan"},
            created_by="credit_test"
        )
        r1 = await cli.recall("quick loan product", max_results=3)
        has_product = any("50000" in res.get("text", "") or "650" in res.get("text", "") for res in r1.get("results", []))
        r2 = await cli.recall("B002 quick loan", max_results=3)
        has_approval = any("approved" in res.get("text", "").lower() for res in r2.get("results", []))
        checks = [(has_product, 1.0), (has_approval, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-C02: Quick loan product routing", score,
                     f"product_found={has_product} approval_found={has_approval}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-C02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_c03_medium_risk_rejection(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Borrower B003: credit_score 580, income 8000/month, "
            "employment 6 months, 1 default in past year, loan rejected",
            tags={"tag": "borrower", "tag_2": "B003", "tag_3": "rejected"},
            created_by="credit_test"
        )
        r1 = await cli.recall("B003 rejected", max_results=3)
        found_rejection = any("rejected" in res.get("text", "").lower() or "580" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found_rejection, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-C03: Medium risk borrower rejection", score,
                     f"rejection_found={found_rejection}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-C03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_c04_large_credit_rejection(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Large credit rule: loan_amount > 500000 requires manual review, "
            "credit_score >= 750, income >= 50000/month",
            tags={"tag": "rule", "tag_2": "large_credit"},
            memory_type="observation",
            created_by="credit_test"
        )
        await cli.remember(
            "Borrower B004: applied for 800000 loan, credit_score 720, "
            "income 40000/month, rejected - insufficient income",
            tags={"tag": "borrower", "tag_2": "B004", "tag_3": "rejected"},
            created_by="credit_test"
        )
        r1 = await cli.recall("large credit rule", max_results=3)
        has_rule = any("500000" in res.get("text", "") or "manual review" in res.get("text", "").lower() for res in r1.get("results", []))
        r2 = await cli.recall("B004 rejected", max_results=3)
        has_rejection = any("rejected" in res.get("text", "").lower() for res in r2.get("results", []))
        checks = [(has_rule, 1.0), (has_rejection, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-C04: Large credit rejection", score,
                     f"rule_found={has_rule} rejection_found={has_rejection}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-C04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_c05_risk_network(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Borrower B005 has co-borrower relationship with B006",
            tags={"tag": "co_borrower", "tag_2": "B005", "tag_3": "B006"},
            created_by="credit_test"
        )
        await cli.remember(
            "Borrower B006: credit_score 520, high risk, defaults 2",
            tags={"tag": "borrower", "tag_2": "B006", "tag_3": "high_risk"},
            created_by="credit_test"
        )
        r1 = await cli.recall("B005 co-borrower", max_results=3)
        has_relation = any("B006" in res.get("text", "") for res in r1.get("results", []))
        r2 = await cli.recall("B006 high risk", max_results=3)
        has_risk = any("520" in res.get("text", "") or "high risk" in res.get("text", "").lower() for res in r2.get("results", []))
        checks = [(has_relation, 1.0), (has_risk, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-C05: Associated risk network detection", score,
                     f"relation_found={has_relation} risk_found={has_risk}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-C05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_c06_blacklist_veto(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Blacklist rule: any borrower on fraud blacklist is auto-rejected, "
            "regardless of credit score",
            tags={"tag": "rule", "tag_2": "blacklist", "tag_3": "veto"},
            memory_type="observation",
            created_by="credit_test"
        )
        await cli.remember(
            "Borrower B007: credit_score 750, but on fraud blacklist, "
            "loan rejected - blacklist veto",
            tags={"tag": "borrower", "tag_2": "B007", "tag_3": "blacklist"},
            created_by="credit_test"
        )
        r1 = await cli.recall("blacklist veto", max_results=3)
        has_veto = any("blacklist" in res.get("text", "").lower() and "rejected" in res.get("text", "").lower() for res in r1.get("results", []))
        r2 = await cli.recall("B007", max_results=3)
        has_borrower = len(r2.get("results", [])) > 0
        checks = [(has_veto, 1.0), (has_borrower, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-C06: Blacklist veto", score,
                     f"veto_found={has_veto} borrower_found={has_borrower}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-C06", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="consumer_credit")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Consumer Credit Risk Assessment — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-C01 Quality borrower", run_c01_quality_borrower),
            ("TC-C02 Quick loan routing", run_c02_quick_loan_routing),
            ("TC-C03 Medium risk rejection", run_c03_medium_risk_rejection),
            ("TC-C04 Large credit rejection", run_c04_large_credit_rejection),
            ("TC-C05 Risk network", run_c05_risk_network),
            ("TC-C06 Blacklist veto", run_c06_blacklist_veto),
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
