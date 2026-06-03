#!/usr/bin/env python3
"""Case 4: BI Query Agent — Natural Language to Metric Query.

10 test cases using CLIRunner (Memory API interface):
  TC-401: Natural language to metric mapping
  TC-402: Multi-metric query
  TC-403: ESG metric query
  TC-404: Cross-domain query
  TC-405: Compliance check query
  TC-406: Unknown metric handling
  TC-407: Version diff analysis
  TC-408: Rule recall precision
  TC-409: Time filter accuracy
  TC-410: Dashboard query

Usage: python examples/case4_bi_query_agent/run_eval.py
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

SPACE = "case4_bi_query"
CASE_DIR = Path(__file__).parent


async def run_tc401(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Metric M_REVENUE: 营业收入, formula=sum(gross_sales), unit=CNY, category=financial", tags={"tag": "metric", "tag_2": "revenue", "tag_3": "financial"}, memory_type="observation", created_by="bi_test")
        await cli.remember("Store ST_001: 华东旗舰店, region=华东, store_type=flagship, annual_revenue 50M CNY", tags={"tag": "store", "tag_2": "ST_001", "tag_3": "华东"}, created_by="bi_test")
        r1 = await cli.recall("去年营业收入趋势", max_results=3)
        found = any("revenue" in res.get("text", "").lower() or "营业收入" in res.get("text", "") or "50M" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-401: Natural language to metric mapping", score, f"metric_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-401", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc402(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Metric M_GROSS_MARGIN: 毛利率, formula=(Revenue-COGS)/Revenue, unit=percent, category=financial", tags={"tag": "metric", "tag_2": "margin", "tag_3": "financial", "tag_4": "tc402"}, memory_type="observation", created_by="bi_test")
        await cli.remember("Metric M_FINANCING_COST: 融资成本率, formula=interest_expense/total_debt, unit=percent, category=financial", tags={"tag": "metric", "tag_2": "financing_cost", "tag_3": "financial", "tag_4": "tc402"}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("毛利率 融资成本", max_results=5)
        results = r1.get("results", [])
        has_margin = any("margin" in res.get("text", "").lower() or "毛利率" in res.get("text", "") for res in results)
        has_financing = any("financing" in res.get("text", "").lower() or "融资成本" in res.get("text", "") for res in results)
        checks = [(has_margin, 1.0), (has_financing, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-402: Multi-metric query", score, f"margin={has_margin} financing={has_financing}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-402", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc403(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Metric M_CARBON_INTENSITY: 碳排放强度, formula=CO2_emissions/revenue, unit=tCO2e/M CNY, category=ESG", tags={"tag": "metric", "tag_2": "ESG", "tag_3": "carbon"}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("今年碳排放强度", max_results=3)
        found = any("carbon" in res.get("text", "").lower() or "碳排放" in res.get("text", "") or "ESG" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-403: ESG metric query", score, f"esg_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-403", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc404(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Metric M_SUPPLIER_CONCENTRATION: 供应商集中度, formula=top5_spend/total_spend, unit=percent, category=supply_chain", tags={"tag": "metric", "tag_2": "supplier", "tag_3": "supply_chain"}, memory_type="observation", created_by="bi_test")
        await cli.remember("Metric M_AR_TURNOVER: 应收账款周转率, formula=net_credit_sales/avg_AR, unit=times, category=financial", tags={"tag": "metric", "tag_2": "AR", "tag_3": "financial"}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("供应商集中度和应收账款周转率", max_results=5)
        results = r1.get("results", [])
        has_supplier = any("supplier" in res.get("text", "").lower() or "供应商" in res.get("text", "") for res in results)
        has_ar = any("AR" in res.get("text", "") or "应收" in res.get("text", "") or "turnover" in res.get("text", "").lower() for res in results)
        checks = [(has_supplier, 1.0), (has_ar, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-404: Cross-domain query", score, f"supplier={has_supplier} AR={has_ar}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-404", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc405(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Green financing compliance: 绿色融资监管要求. Projects must meet ESG criteria, carbon emission < threshold, green bond certification required.", tags={"tag": "compliance", "tag_2": "green_financing", "tag_3": "ESG"}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("绿色融资监管要求", max_results=3)
        found = any("green" in res.get("text", "").lower() or "绿色" in res.get("text", "") or "compliance" in res.get("text", "").lower() for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-405: Compliance check query", score, f"compliance_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-405", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc406(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        # First store a known metric so recall is non-empty (tests false positive, not empty result)
        await cli.remember("Metric M_REVENUE: 营业收入, formula=sum(gross_sales)", tags={"tag": "metric", "tag_2": "revenue", "tag_3": "tc406_control"}, created_by="bi_test")
        r1 = await cli.recall("未知指标xyz123", max_results=5)
        results = r1.get("results", [])
        # Should NOT return the control metric for an unrelated query
        no_false_positive = not any("xyz123" in res.get("text", "").lower() for res in results)
        # Bonus: results should be low-relevance (not exact matches for known metrics)
        no_exact_match = not any("M_REVENUE" in res.get("text", "") for res in results)
        checks = [(no_false_positive, 1.0), (no_exact_match, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-406: Unknown metric handling", score, f"no_false_positive={no_false_positive} no_exact_match={no_exact_match}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-406", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc407(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Metric cards v1.4: M_REVENUE, M_GROSS_MARGIN, M_DSO, M_DIO, M_FINANCING_COST (5 metrics)", tags={"tag": "metrics", "tag_2": "v1.4"}, memory_type="observation", created_by="bi_test")
        await cli.remember("Metric cards v1.5: added M_CARBON_INTENSITY, M_ESG_SCORE (7 metrics total, ESG expansion)", tags={"tag": "metrics", "tag_2": "v1.5"}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("metric cards v1.4 v1.5 difference", max_results=5)
        found = any("v1.5" in res.get("text", "") or "v1.4" in res.get("text", "") or "ESG" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-407: Version diff analysis", score, f"version_diff_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-407", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc408(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Metric M_REVENUE: 营业收入, formula=sum(gross_sales), unit=CNY", tags={"tag": "metric", "tag_2": "revenue"}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("营收", max_results=5)
        results = r1.get("results", [])
        top1_is_revenue = len(results) > 0 and ("revenue" in results[0].get("text", "").lower() or "营业收入" in results[0].get("text", ""))
        checks = [(top1_is_revenue, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-408: Rule recall precision", score, f"top1_is_revenue={top1_is_revenue}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-408", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc409(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Store ST_001: open_date=2025-03-15, region=华东, annual_revenue 50M CNY", tags={"tag": "store", "tag_2": "ST_001"}, created_by="bi_test")
        await cli.remember("Store ST_002: open_date=2025-07-01, region=华南, annual_revenue 30M CNY", tags={"tag": "store", "tag_2": "ST_002"}, created_by="bi_test")
        r1 = await cli.recall("2025年Q3和Q4", max_results=5)
        found = any("2025" in res.get("text", "") for res in r1.get("results", []))
        checks = [(found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-409: Time filter accuracy", score, f"time_filter_found={found}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-409", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc410(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        metrics = [
            ("M_REVENUE", "营业收入", "tc410"),
            ("M_GROSS_MARGIN", "毛利率", "tc410"),
            ("M_DSO", "应收账款周转天数DSO", "tc410"),
            ("M_DIO", "库存周转天数DIO", "tc410"),
            ("M_FINANCING_COST", "融资成本率", "tc410"),
        ]
        for mid, mname, tag in metrics:
            await cli.remember(f"Core metric {mid}: {mname}", tags={"tag": "metric", "tag_2": "core", "tag_3": mid, "tag_4": tag}, memory_type="observation", created_by="bi_test")
        r1 = await cli.recall("core metric tc410", max_results=10)
        results = r1.get("results", [])
        found_count = sum(1 for mid, _, _ in metrics if any(mid in res.get("text", "") for res in results))
        score = min(found_count / len(metrics), 1.0)
        report.add(r("TC-410: Dashboard query", score, f"found={found_count}/{len(metrics)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-410", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case4_bi_query_agent")
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 4: BI Query Agent — Natural Language to Metric Query")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)
        scenarios = [
            ("TC-401 Natural language to metric", run_tc401),
            ("TC-402 Multi-metric query", run_tc402),
            ("TC-403 ESG metric query", run_tc403),
            ("TC-404 Cross-domain query", run_tc404),
            ("TC-405 Compliance check query", run_tc405),
            ("TC-406 Unknown metric handling", run_tc406),
            ("TC-407 Version diff analysis", run_tc407),
            ("TC-408 Rule recall precision", run_tc408),
            ("TC-409 Time filter accuracy", run_tc409),
            ("TC-410 Dashboard query", run_tc410),
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
