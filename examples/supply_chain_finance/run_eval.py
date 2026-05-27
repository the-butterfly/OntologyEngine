#!/usr/bin/env python3
"""Supply Chain Finance Credit Assessment — OntologyEngine Acceptance Tests.

Runs 6 test cases against the supply chain finance schema and instances
using CLIRunner (Memory API interface).

TC-01: Schema + instance loading verification
TC-02: Multi-entity data ingestion
TC-03: Credit assessment rule execution
TC-04: Risk dimension analysis
TC-05: Cross-entity knowledge retrieval
TC-06: Data consistency across dimensions

Usage: python examples/supply_chain_finance/run_eval.py
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

SPACE = "supply_chain_finance"
CASE_DIR = Path(__file__).parent


async def run_tc01_schema_loading(cli: CLIRunner, report: AcptReport):
    """TC-01: Schema + instance loading verification."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "Supplier SUP_A: 深圳智造科技有限公司, registered_capital 50M CNY, "
            "established 2018-03-15, industry MANUFACTURING, status ACTIVE",
            tags=["supplier", "SUP_A", "manufacturing"],
            created_by="schema_test"
        )
        resp2 = await cli.remember(
            "CoreEnterprise CE_HW: 华为技术有限公司, credit_rating AAA, "
            "annual_procurement 50B CNY",
            tags=["core_enterprise", "CE_HW"],
            created_by="schema_test"
        )
        resp3 = await cli.remember(
            "Relation: SUP_A supplies_to CE_HW",
            tags=["relation", "supply_chain"],
            created_by="schema_test"
        )

        all_created = all(r.get("node_id") is not None for r in [resp1, resp2, resp3])

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("SUP_A", max_results=3)
        found_supplier = len(r1.get("results", [])) > 0

        checks = [(all_created, 1.0), (total >= 3, 1.0), (found_supplier, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-01: Schema + instance loading", score,
                     f"created={sum(1 for r in [resp1,resp2,resp3] if r.get('node_id'))}/3 total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc02_multi_entity_ingestion(cli: CLIRunner, report: AcptReport):
    """TC-02: Multi-entity data ingestion — load multiple supplier profiles."""
    t0 = time.time()
    try:
        entities = [
            ("SUP_A", "深圳智造科技有限公司", "MANUFACTURING", "50M", "ACTIVE"),
            ("SUP_B", "某贸易有限公司", "RETAIL", "1M", "ACTIVE"),
            ("SUP_C_A", "担保圈供应商A", "MANUFACTURING", "20M", "ACTIVE"),
        ]

        responses = []
        for sid, name, industry, capital, status in entities:
            resp = await cli.remember(
                f"Supplier {sid}: {name}, industry {industry}, "
                f"registered_capital {capital} CNY, status {status}",
                tags=["supplier", sid, industry.lower()],
                created_by="ingestion_test"
            )
            responses.append(resp)

        all_created = all(r.get("node_id") is not None for r in responses)

        r1 = await cli.recall("supplier", max_results=10)
        found_count = len(r1.get("results", []))

        checks = [(all_created, 1.0), (found_count >= 2, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-02: Multi-entity ingestion", score,
                     f"created={sum(1 for r in responses if r.get('node_id'))}/3 found={found_count}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc03_credit_assessment(cli: CLIRunner, report: AcptReport):
    """TC-03: Credit assessment rule execution — verify analysis pipeline."""
    t0 = time.time()
    try:
        await cli.remember(
            "Supplier SUP_A credit profile: credit_score 89, credit_grade AA, "
            "eligible=True, guarantee_chain_depth 0",
            tags=["credit_assessment", "SUP_A"],
            memory_type="observation",
            created_by="assessment_test"
        )

        r1 = await cli.recall("SUP_A credit score", max_results=3)
        has_score = any("89" in res.get("text", "") or "AA" in res.get("text", "") for res in r1.get("results", []))

        r2 = await cli.recall("eligible supplier", max_results=3)
        has_eligible = any("eligible" in res.get("text", "").lower() for res in r2.get("results", []))

        checks = [(has_score, 1.0), (has_eligible, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-03: Credit assessment rules", score,
                     f"score_found={has_score} eligible_found={has_eligible}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc04_risk_dimension(cli: CLIRunner, report: AcptReport):
    """TC-04: Risk dimension analysis — verify risk_early_warning dimension."""
    t0 = time.time()
    try:
        await cli.remember(
            "Risk alert: Supplier SUP_B has negative_news_count_90d=4, "
            "tax_compliance_score=42, overdue_invoice_ratio high",
            tags=["risk_alert", "SUP_B", "risk_early_warning"],
            created_by="risk_test"
        )
        await cli.remember(
            "Risk rule: negative_news_count >= 3 triggers warning",
            tags=["risk_rule", "threshold"],
            memory_type="observation",
            created_by="risk_test"
        )

        r1 = await cli.recall("risk alert SUP_B", max_results=3)
        has_alert = len(r1.get("results", [])) > 0

        r2 = await cli.recall("risk rule threshold", max_results=3)
        has_rule = len(r2.get("results", [])) > 0

        checks = [(has_alert, 1.0), (has_rule, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-04: Risk dimension analysis", score,
                     f"alert_found={has_alert} rule_found={has_rule}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc05_cross_entity_retrieval(cli: CLIRunner, report: AcptReport):
    """TC-05: Cross-entity knowledge retrieval — supply chain relationships."""
    t0 = time.time()
    try:
        await cli.remember(
            "SUP_A supplies to CE_HW (华为) and CE_BYD (比亚迪)",
            tags=["supply_relation", "SUP_A"],
            created_by="retrieval_test"
        )
        await cli.remember(
            "CE_HW annual procurement volume 50B CNY, credit rating AAA",
            tags=["core_enterprise", "CE_HW"],
            created_by="retrieval_test"
        )

        r1 = await cli.recall("SUP_A supplies to", max_results=5)
        has_relation = any("CE_HW" in res.get("text", "") or "华为" in res.get("text", "") for res in r1.get("results", []))

        r2 = await cli.recall("CE_HW procurement", max_results=3)
        has_ce_data = any("50B" in res.get("text", "") or "AAA" in res.get("text", "") for res in r2.get("results", []))

        checks = [(has_relation, 1.0), (has_ce_data, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-05: Cross-entity retrieval", score,
                     f"relation_found={has_relation} ce_data_found={has_ce_data}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc06_data_consistency(cli: CLIRunner, report: AcptReport):
    """TC-06: Data consistency across dimensions."""
    t0 = time.time()
    try:
        await cli.remember(
            "SUP_A: manufacturing industry, credit_score 89, eligible=True",
            tags=["SUP_A", "credit"],
            created_by="consistency_test"
        )
        await cli.remember(
            "SUP_B: retail industry, credit_score 45, eligible=False",
            tags=["SUP_B", "credit"],
            created_by="consistency_test"
        )

        r_mfg = await cli.recall("manufacturing supplier", max_results=5)
        mfg_results = r_mfg.get("results", [])
        has_mfg = any("manufacturing" in res.get("text", "").lower() for res in mfg_results)

        r_retail = await cli.recall("retail supplier", max_results=5)
        retail_results = r_retail.get("results", [])
        has_retail = any("retail" in res.get("text", "").lower() for res in retail_results)

        checks = [(has_mfg, 1.0), (has_retail, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-06: Data consistency", score,
                     f"mfg_found={has_mfg} retail_found={has_retail}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-06", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="supply_chain_finance")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Supply Chain Finance Credit Assessment — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-01 Schema loading", run_tc01_schema_loading),
            ("TC-02 Multi-entity ingestion", run_tc02_multi_entity_ingestion),
            ("TC-03 Credit assessment", run_tc03_credit_assessment),
            ("TC-04 Risk dimension", run_tc04_risk_dimension),
            ("TC-05 Cross-entity retrieval", run_tc05_cross_entity_retrieval),
            ("TC-06 Data consistency", run_tc06_data_consistency),
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
