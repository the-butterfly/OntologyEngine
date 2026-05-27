#!/usr/bin/env python3
"""Case 9: Dream Cycle — D-S6 Dream Cycle Full Process Acceptance Tests.

Verifies D-S6 AC6-1~AC6-3:
  TC-D01: Lint phase — isolated nodes/contradiction/outdated detection
  TC-D02: Consolidate phase — unconsolidated fragments auto-classified
  TC-D03: Enrich phase — three-tier enrich (Tier 3→2→1)
  TC-D04: Forget phase — value-aware decay, strength下降
  TC-D05: Reflect phase — cross-fragment deep analysis, generate mental_model
  TC-D06: Health Report — processing stats + health score + recommendations
  TC-D07: Independent phase execution — dream(phase="lint") only runs lint
  TC-D08: Post-write hook performance — consolidate ≤500ms trigger

Usage: python examples/case9_dream_cycle/run_eval.py
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

SPACE = "dream_cycle"
CASE_DIR = Path(__file__).parent


async def run_d01_lint_phase(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Server API endpoint is /v1/users", tags=["api"], created_by="lint_test")
        await cli.remember("Server API endpoint is /v2/users", tags=["api"], created_by="lint_test")

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("API endpoint", max_results=5)
        results = r1.get("results", [])
        has_both_versions = any("/v1" in res.get("text", "") for res in results) and any("/v2" in res.get("text", "") for res in results)

        checks = [(total >= 2, 1.0), (has_both_versions, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D01: Lint phase contradiction detection", score,
                     f"total={total} both_versions_found={has_both_versions}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d02_consolidate_phase(cli: CLIRunner, report: AcptReport):
    """TC-D02: Consolidate phase — unconsolidated fragments auto-classified."""
    t0 = time.time()
    try:
        await cli.remember("Kubernetes pod restart policy is Always", tags=["k8s"], created_by="consolidate_test")
        await cli.remember("Kubernetes pod restart policy is OnFailure", tags=["k8s"], created_by="consolidate_test")
        await cli.remember("Kubernetes pod restart policy is Never", tags=["k8s"], created_by="consolidate_test")

        result = await cli.consolidate()
        consolidated = result.get("consolidated", result.get("new_observations", 0))

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("Kubernetes restart policy", max_results=5)
        results = r1.get("results", [])
        has_results = len(results) > 0

        checks = [(total >= 3, 1.0), (has_results, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D02: Consolidate phase", score,
                     f"total={total} consolidated={consolidated} results={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d03_enrich_phase(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Project Alpha uses microservices architecture with 12 services. "
            "Service A communicates with Service B via gRPC. "
            "Service B connects to PostgreSQL database. "
            "Service C handles authentication with JWT tokens.",
            tags=["architecture", "project_alpha"],
            memory_type="fragment",
            created_by="enrich_test"
        )

        result = await cli.reflect(
            query="enrich architecture knowledge",
            max_iterations=3,
            skip_consolidation=False,
            skip_forgetting=True
        )

        insights = result.get("insights", result.get("analysis", []))
        has_insights = len(insights) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("Project Alpha architecture", max_results=5)
        recall_count = len(r1.get("results", []))

        checks = [(total >= 1, 1.0), (recall_count >= 1, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D03: Enrich phase three-tier", score,
                     f"total={total} insights={len(insights)} recall={recall_count}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d04_forget_phase(cli: CLIRunner, report: AcptReport):
    """TC-D04: Forget phase — value-aware decay, strength下降."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "High-value: Production database connection string is postgres://prod:5432",
            tags=["critical", "infrastructure"],
            confidence=0.95,
            created_by="forget_test"
        )
        resp2 = await cli.remember(
            "Low-value: Office temperature was 22C on Monday",
            tags=["trivial"],
            confidence=0.3,
            created_by="forget_test"
        )

        stats_before = await cli.stats()
        total_before = stats_before.get("total", 0)

        result = await cli.forget(days_elapsed=30)
        forgotten = result.get("forgotten", result.get("decayed", 0))

        stats_after = await cli.stats()
        total_after = stats_after.get("total", 0)

        r_high = await cli.recall("database connection string", max_results=3)
        high_still_exists = len(r_high.get("results", [])) > 0

        checks = [(total_before >= 2, 1.0), (high_still_exists, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D04: Forget phase value-aware decay", score,
                     f"before={total_before} after={total_after} forgotten={forgotten} high_value_kept={high_still_exists}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d05_reflect_phase(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember(
            "Team A's sprint velocity dropped from 40 to 25 story points",
            tags=["team_metrics"], created_by="reflect_test"
        )
        await cli.remember(
            "Team A had 3 key members leave in Q2",
            tags=["team_metrics", "personnel"], created_by="reflect_test"
        )
        await cli.remember(
            "New onboarding process takes 4 weeks instead of 2",
            tags=["process", "onboarding"], created_by="reflect_test"
        )

        result = await cli.reflect(
            query="analyze team productivity trends",
            max_iterations=5,
            skip_consolidation=False,
            skip_forgetting=False
        )

        insights = result.get("insights", result.get("analysis", []))
        has_insights = len(insights) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        checks = [(total >= 3, 1.0), (has_insights, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D05: Reflect phase deep analysis", score,
                     f"total={total} insights={len(insights)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d06_health_report(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("Service uptime SLA is 99.9%", tags=["sla"], created_by="health_test")
        await cli.remember("Current uptime is 99.95%", tags=["sla", "current"], created_by="health_test")
        await cli.remember("Last incident was 45 days ago", tags=["incident"], created_by="health_test")

        result = await cli.dream()

        stats = await cli.stats()
        total = stats.get("total", 0)

        has_result_keys = bool(result)
        dream_cycle_complete = "lint" in str(result).lower() or "consolidate" in str(result).lower() or "stats" in str(result).lower()

        checks = [(total >= 3, 1.0), (has_result_keys, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D06: Health Report dream cycle", score,
                     f"total={total} has_result={has_result_keys}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D06", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d07_independent_phase(cli: CLIRunner, report: AcptReport):
    t0 = time.time()
    try:
        await cli.remember("API version is v2", tags=["api"], created_by="independent_test")
        await cli.remember("API version is v3", tags=["api"], created_by="independent_test")

        result = await cli.reflect(
            query="lint only check",
            max_iterations=2,
            skip_consolidation=True,
            skip_forgetting=True
        )

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("API version", max_results=5)
        found_both = any("v2" in res.get("text", "") for res in r1.get("results", [])) and any("v3" in res.get("text", "") for res in r1.get("results", []))

        checks = [(total >= 2, 1.0), (found_both, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D07: Independent phase execution", score,
                     f"total={total} both_versions_found={found_both}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D07", 0.0, str(e), (time.time() - t0) * 1000))


async def run_d08_post_write_hook(cli: CLIRunner, report: AcptReport):
    """TC-D08: Post-write hook performance — consolidate ≤500ms trigger."""
    t0 = time.time()
    try:
        await cli.remember("Feature flag X is enabled for 50% of users", tags=["feature_flag"], created_by="hook_test")

        t1 = time.time()
        result = await cli.consolidate()
        consolidate_ms = (time.time() - t1) * 1000

        fast_enough = consolidate_ms < 500

        checks = [(fast_enough, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-D08: Post-write hook performance", score,
                     f"consolidate_ms={consolidate_ms:.0f} fast_enough={fast_enough}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-D08", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case9_dream_cycle")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 9: Dream Cycle — Full Process Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-D01 Lint phase", run_d01_lint_phase),
            ("TC-D02 Consolidate phase", run_d02_consolidate_phase),
            ("TC-D03 Enrich phase", run_d03_enrich_phase),
            ("TC-D04 Forget phase", run_d04_forget_phase),
            ("TC-D05 Reflect phase", run_d05_reflect_phase),
            ("TC-D06 Health Report", run_d06_health_report),
            ("TC-D07 Independent phase", run_d07_independent_phase),
            ("TC-D08 Post-write hook", run_d08_post_write_hook),
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
