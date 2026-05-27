#!/usr/bin/env python3
"""Case 7: Multi-Agent Orchestration — J6 Multi-Agent Coordination Acceptance Tests.

Verifies vision journey J6 + core problem P5 + Phase 3:
  TC-701: Ingest Agent updates knowledge
  TC-702: Analysis Agent queries via shared knowledge
  TC-703: Execution Agent generates report
  TC-704: Shared memory verification (agents share knowledge, not prompts)
  TC-705: trace_to chain完整性
  TC-706: End-to-end risk identification (3-agent协同)

Usage: python examples/case7_multi_agent_orchestration/run_eval.py
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

SPACE = "multi_agent_orchestration"
CASE_DIR = Path(__file__).parent


async def run_701_ingest_agent_update(cli: CLIRunner, report: AcptReport):
    """TC-701: Ingest Agent reads latest financial report and updates knowledge."""
    t0 = time.time()
    try:
        ingest_cli = CLIRunner(cli.api, space_id=f"{SPACE}_ingest")

        resp1 = await ingest_cli.remember(
            "Q3 2026 revenue: 5.2B CNY, up 15% YoY. Gross margin 32%.",
            tags=["financial_report", "Q3_2026"],
            source_pipeline="ingest_agent",
            created_by="agent_ingest"
        )
        resp2 = await ingest_cli.remember(
            "Supply chain risk: 3 suppliers in guarantee cycle A-B-C-A detected.",
            tags=["risk_alert", "guarantee_cycle"],
            source_pipeline="ingest_agent",
            created_by="agent_ingest"
        )
        resp3 = await ingest_cli.remember(
            "Counterparty DEF credit score dropped from 720 to 650.",
            tags=["credit_risk", "counterparty"],
            source_pipeline="ingest_agent",
            created_by="agent_ingest"
        )

        ids = [resp1.get("node_id"), resp2.get("node_id"), resp3.get("node_id")]
        all_created = all(nid is not None for nid in ids)

        score = 1.0 if all_created else 0.0
        report.add(r("TC-701: Ingest Agent update knowledge", score,
                     f"created={sum(1 for i in ids if i)}/3 ids={[i[:16] if i else None for i in ids]}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-701", 0.0, str(e), (time.time() - t0) * 1000))


async def run_702_analysis_agent_query(cli: CLIRunner, report: AcptReport):
    """TC-702: Analysis Agent queries via OntologyEngine shared knowledge."""
    t0 = time.time()
    try:
        # Use SAME space_id to simulate shared knowledge between agents
        shared_space = f"{SPACE}_shared_knowledge"
        ingest_cli = CLIRunner(cli.api, space_id=shared_space)
        analysis_cli = CLIRunner(cli.api, space_id=shared_space)

        await ingest_cli.remember(
            "Q3 2026 revenue: 5.2B CNY, up 15% YoY. Gross margin 32%.",
            tags=["financial_report"], created_by="agent_ingest", visibility="shared"
        )
        await ingest_cli.remember(
            "Supply chain risk: 3 suppliers in guarantee cycle detected.",
            tags=["risk_alert"], created_by="agent_ingest", visibility="shared"
        )

        r1 = await analysis_cli.recall("Q3 revenue", max_results=3)
        r2 = await analysis_cli.recall("supply chain risk", max_results=3)

        results1 = r1.get("results", [])
        results2 = r2.get("results", [])

        has_revenue = any("revenue" in res.get("text", "").lower() or "5.2B" in res.get("text", "") for res in results1)
        has_risk = any("risk" in res.get("text", "").lower() or "guarantee" in res.get("text", "").lower() for res in results2)

        checks = [(has_revenue, 1.0), (has_risk, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-702: Analysis Agent query shared knowledge", score,
                     f"revenue_found={has_revenue} risk_found={has_risk}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-702", 0.0, str(e), (time.time() - t0) * 1000))


async def run_703_execution_agent_report(cli: CLIRunner, report: AcptReport):
    """TC-703: Execution Agent generates risk report based on analysis results."""
    t0 = time.time()
    try:
        exec_cli = CLIRunner(cli.api, space_id=f"{SPACE}_execution")

        resp = await exec_cli.remember(
            "Risk Report 2026-Q3: 3 high-risk suppliers identified. "
            "Recommendation: reduce exposure to guarantee cycle participants. "
            "Credit limit for Counterparty DEF reduced by 20%.",
            tags=["risk_report", "Q3_2026"],
            memory_type="observation",
            created_by="agent_execution"
        )

        node_id = resp.get("node_id")
        has_report = node_id is not None

        r1 = await exec_cli.recall("risk report Q3", max_results=3)
        found_report = len(r1.get("results", [])) > 0

        checks = [(has_report, 1.0), (found_report, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-703: Execution Agent generate report", score,
                     f"report_created={has_report} report_found={found_report}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-703", 0.0, str(e), (time.time() - t0) * 1000))


async def run_704_shared_memory_verification(cli: CLIRunner, report: AcptReport):
    """TC-704: Agents share knowledge via OntologyEngine, not prompts."""
    t0 = time.time()
    try:
        ingest_cli = CLIRunner(cli.api, space_id=f"{SPACE}_shared")
        analysis_cli = CLIRunner(cli.api, space_id=f"{SPACE}_shared")
        exec_cli = CLIRunner(cli.api, space_id=f"{SPACE}_shared")

        await ingest_cli.remember(
            "Supplier XYZ has been flagged for potential fraud investigation.",
            tags=["fraud_alert"], created_by="agent_ingest", visibility="shared"
        )

        r_analysis = await analysis_cli.recall("fraud investigation", max_results=3)
        r_exec = await exec_cli.recall("Supplier XYZ", max_results=3)

        analysis_found = len(r_analysis.get("results", [])) > 0
        exec_found = len(r_exec.get("results", [])) > 0

        stats = await ingest_cli.stats()
        total = stats.get("total", 0)

        checks = [(analysis_found, 1.0), (exec_found, 1.0), (total >= 1, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-704: Shared memory verification", score,
                     f"analysis_sees={analysis_found} exec_sees={exec_found} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-704", 0.0, str(e), (time.time() - t0) * 1000))


async def run_705_trace_to_chain(cli: CLIRunner, report: AcptReport):
    """TC-705: Every operation records to trace_to chain."""
    t0 = time.time()
    try:
        trace_cli = CLIRunner(cli.api, space_id=f"{SPACE}_trace")

        resp1 = await trace_cli.remember(
            "Initial risk assessment: Counterparty ABC score 720",
            tags=["risk_assessment"], created_by="agent_ingest",
            source_pipeline="ingest"
        )
        node_id_1 = resp1.get("node_id")

        resp2 = await trace_cli.remember(
            "Updated risk assessment: Counterparty ABC score dropped to 650",
            tags=["risk_assessment"], created_by="agent_analysis",
            source_pipeline="analysis",
            supersede_target=node_id_1,
            supersede_reason="score updated based on new data"
        )
        node_id_2 = resp2.get("node_id")

        audit = await trace_cli.audit(limit=20)
        audit_entries = audit.get("entries", audit.get("audit_trail", []))
        has_audit = len(audit_entries) >= 1

        checks = [(node_id_1 is not None, 1.0), (node_id_2 is not None, 1.0), (has_audit, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-705: trace_to chain", score,
                     f"node1={node_id_1 is not None} node2={node_id_2 is not None} audit_entries={len(audit_entries)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-705", 0.0, str(e), (time.time() - t0) * 1000))


async def run_706_e2e_risk_identification(cli: CLIRunner, report: AcptReport):
    """TC-706: 3-agent协同 complete risk identification workflow."""
    t0 = time.time()
    try:
        shared_space = f"{SPACE}_e2e"
        ingest_cli = CLIRunner(cli.api, space_id=shared_space)
        analysis_cli = CLIRunner(cli.api, space_id=shared_space)
        exec_cli = CLIRunner(cli.api, space_id=shared_space)

        # Step 1: Ingest Agent ingests raw data
        await ingest_cli.remember(
            "Supplier A: revenue 50M, credit score 680, guarantee chain depth 3",
            tags=["supplier_data"], created_by="agent_ingest", visibility="shared"
        )
        await ingest_cli.remember(
            "Supplier B: revenue 30M, credit score 620, guarantee chain depth 4",
            tags=["supplier_data"], created_by="agent_ingest", visibility="shared"
        )

        # Step 2: Analysis Agent queries and analyzes
        r1 = await analysis_cli.recall("supplier credit score", max_results=5)
        analysis_results = r1.get("results", [])

        await analysis_cli.remember(
            "Analysis: Supplier A and B both in high-risk guarantee cycle. "
            "Recommendation: reject both applications.",
            tags=["analysis_result"], created_by="agent_analysis", visibility="shared"
        )

        # Step 3: Execution Agent generates final report
        await exec_cli.remember(
            "Final Decision: Supplier A - REJECT, Supplier B - REJECT. "
            "Reason: guarantee chain risk exceeds threshold.",
            tags=["final_decision"], created_by="agent_execution", visibility="shared"
        )

        r_decision = await exec_cli.recall("final decision reject", max_results=3)
        decision_found = len(r_decision.get("results", [])) > 0

        stats = await ingest_cli.stats()
        total = stats.get("total", 0)

        checks = [
            (len(analysis_results) >= 1, 1.0),
            (decision_found, 1.0),
            (total >= 4, 1.0),
        ]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-706: E2E risk identification", score,
                     f"analysis_results={len(analysis_results)} decision_found={decision_found} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-706", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case7_multi_agent_orchestration")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 7: Multi-Agent Orchestration — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface) — multi-agent simulation")
        print("=" * 70)

        scenarios = [
            ("TC-701 Ingest Agent update", run_701_ingest_agent_update),
            ("TC-702 Analysis Agent query", run_702_analysis_agent_query),
            ("TC-703 Execution Agent report", run_703_execution_agent_report),
            ("TC-704 Shared memory verification", run_704_shared_memory_verification),
            ("TC-705 trace_to chain", run_705_trace_to_chain),
            ("TC-706 E2E risk identification", run_706_e2e_risk_identification),
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
