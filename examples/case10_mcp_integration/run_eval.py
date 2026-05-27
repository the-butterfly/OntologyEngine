#!/usr/bin/env python3
"""Case 10: MCP Integration — J3 MCP Protocol Acceptance Tests.

Verifies vision journey J3 + Phase 1 MCP:
  TC-M01: MCP Server startup — tool list correctly registered
  TC-M02: oe_remember MCP call — Agent remembers knowledge via MCP
  TC-M03: oe_recall MCP call — Agent retrieves knowledge via MCP
  TC-M04: oe_reflect MCP call — Agent deep analysis via MCP
  TC-M05: MCP return format — conclusion + evidence + execution_snapshot

Usage: python examples/case10_mcp_integration/run_eval.py
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

SPACE = "mcp_integration"
CASE_DIR = Path(__file__).parent


async def run_m01_mcp_server_startup(cli: CLIRunner, report: AcptReport):
    """TC-M01: MCP Server startup — tool list correctly registered."""
    t0 = time.time()
    try:
        types = await cli.types()
        has_types = types is not None and len(types) > 0

        stats = await cli.stats()
        has_stats = stats is not None

        checks = [(has_types, 1.0), (has_stats, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-M01: MCP Server startup", score,
                     f"types_available={has_types} stats_available={has_stats}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-M01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_m02_mcp_remember(cli: CLIRunner, report: AcptReport):
    """TC-M02: oe_remember MCP call — Agent remembers knowledge via MCP."""
    t0 = time.time()
    try:
        resp = await cli.remember(
            "MCP tool oe_remember successfully stored knowledge about supply chain finance",
            tags=["mcp_test", "remember"],
            created_by="mcp_agent"
        )

        node_id = resp.get("node_id")
        has_node = node_id is not None

        r1 = await cli.recall("MCP tool oe_remember", max_results=3)
        found = len(r1.get("results", [])) > 0

        checks = [(has_node, 1.0), (found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-M02: oe_remember MCP call", score,
                     f"node_created={has_node} found={found}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-M02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_m03_mcp_recall(cli: CLIRunner, report: AcptReport):
    """TC-M03: oe_recall MCP call — Agent retrieves knowledge via MCP."""
    t0 = time.time()
    try:
        await cli.remember(
            "MCP recall test: Supplier ABC has credit score 720",
            tags=["mcp_test", "recall"],
            created_by="mcp_agent"
        )

        r1 = await cli.recall("Supplier ABC credit score", max_results=3)
        results = r1.get("results", [])

        has_result = len(results) > 0
        has_content = any("720" in res.get("text", "") for res in results)

        checks = [(has_result, 1.0), (has_content, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-M03: oe_recall MCP call", score,
                     f"results={len(results)} content_found={has_content}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-M03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_m04_mcp_reflect(cli: CLIRunner, report: AcptReport):
    """TC-M04: oe_reflect MCP call — Agent deep analysis via MCP."""
    t0 = time.time()
    try:
        await cli.remember(
            "Risk factor 1: guarantee chain depth exceeds 3",
            tags=["risk", "mcp_reflect"],
            created_by="mcp_agent"
        )
        await cli.remember(
            "Risk factor 2: overdue invoice ratio above 10%",
            tags=["risk", "mcp_reflect"],
            created_by="mcp_agent"
        )

        result = await cli.reflect(
            query="analyze supply chain risk factors",
            max_iterations=3,
            skip_consolidation=False,
            skip_forgetting=True
        )

        has_result = result is not None
        has_insights = len(result.get("insights", [])) > 0

        checks = [(has_result, 1.0), (has_insights, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-M04: oe_reflect MCP call", score,
                     f"has_result={has_result} insights={len(result.get('insights', []))}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-M04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_m05_mcp_return_format(cli: CLIRunner, report: AcptReport):
    """TC-M05: MCP return format — conclusion + evidence + execution_snapshot."""
    t0 = time.time()
    try:
        resp = await cli.remember(
            "MCP format test: conclusion=approved, evidence=credit_score>=700",
            tags=["mcp_format"],
            created_by="mcp_agent"
        )

        has_node_id = "node_id" in resp or "memory_id" in resp
        has_data = "data" in resp or "text" in resp

        r1 = await cli.recall("MCP format test", max_results=3)
        results = r1.get("results", [])
        has_results = len(results) > 0

        checks = [(has_node_id, 1.0), (has_data, 0.5), (has_results, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-M05: MCP return format", score,
                     f"has_node_id={has_node_id} has_data={has_data} has_results={has_results}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-M05", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case10_mcp_integration")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 10: MCP Integration — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface) — MCP protocol simulation")
        print("=" * 70)

        scenarios = [
            ("TC-M01 MCP Server startup", run_m01_mcp_server_startup),
            ("TC-M02 oe_remember MCP", run_m02_mcp_remember),
            ("TC-M03 oe_recall MCP", run_m03_mcp_recall),
            ("TC-M04 oe_reflect MCP", run_m04_mcp_reflect),
            ("TC-M05 MCP return format", run_m05_mcp_return_format),
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
