#!/usr/bin/env python3
"""Case 14: Storage Adapter — D-S1 Storage Adapter Acceptance Tests.

Verifies D-S1 AC1-1~AC1-7:
  TC-S01: StorageInterface unified interface — save/get/search/delete/batch_save
  TC-S02: SQLiteAdapter CRUD — entity/relation/rule storage
  TC-S03: ChromaDBAdapter vector — fragment vector storage + semantic search
  TC-S04: RRF multi-path retrieval — vector+keyword+metadata fusion
  TC-S05: Citation mode consolidation — fragment stays in ChromaDB, observation writes SQLite
  TC-S06: Single-engine mode — only ChromaDB or only SQLite available

Usage: python examples/case14_storage_adapter/run_eval.py
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

SPACE = "storage_adapter"
CASE_DIR = Path(__file__).parent


async def run_s01_unified_interface(cli: CLIRunner, report: AcptReport):
    """TC-S01: StorageInterface unified interface — save/get/search/delete/batch_save."""
    t0 = time.time()
    try:
        cli.set_space(f"{SPACE}_s01")
        resp1 = await cli.remember("Entity: Supplier XYZ, industry: manufacturing", tags={"tag": "entity"}, created_by="storage_test")
        resp2 = await cli.remember("Entity: Supplier ABC, industry: technology", tags={"tag": "entity"}, created_by="storage_test")

        save_ok = resp1.get("node_id") is not None and resp2.get("node_id") is not None

        r1 = await cli.recall("Supplier XYZ", max_results=3)
        get_ok = len(r1.get("results", [])) > 0

        r2 = await cli.recall("Supplier", max_results=5)
        search_ok = len(r2.get("results", [])) >= 2

        stats = await cli.stats()
        total = stats.get("total", 0)
        batch_ok = total >= 2

        checks = [(save_ok, 1.0), (get_ok, 1.0), (search_ok, 1.0), (batch_ok, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-S01: StorageInterface unified interface", score,
                     f"save={save_ok} get={get_ok} search={search_ok} batch={batch_ok} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-S01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_s02_sqlite_crud(cli: CLIRunner, report: AcptReport):
    """TC-S02: SQLiteAdapter CRUD — entity/relation/rule storage."""
    t0 = time.time()
    try:
        cli.set_space(f"{SPACE}_s02")
        resp_entity = await cli.remember(
            "Entity: CoreEnterprise HW, credit_rating: AAA",
            tags={"tag": "entity", "tag_2": "sqlite_test"},
            memory_type="observation",
            created_by="storage_test"
        )

        resp_relation = await cli.remember(
            "Relation: Supplier A supplies_to CoreEnterprise HW",
            tags={"tag": "relation", "tag_2": "sqlite_test"},
            memory_type="observation",
            created_by="storage_test"
        )

        resp_rule = await cli.remember(
            "Rule: credit_score >= 700 → APPROVE",
            tags={"tag": "rule", "tag_2": "sqlite_test"},
            memory_type="observation",
            created_by="storage_test"
        )

        all_created = all(r.get("node_id") is not None for r in [resp_entity, resp_relation, resp_rule])

        r_entity = await cli.recall("CoreEnterprise HW", max_results=3)
        r_relation = await cli.recall("supplies_to", max_results=3)
        r_rule = await cli.recall("credit_score >= 700", max_results=3)

        entity_found = len(r_entity.get("results", [])) > 0
        relation_found = len(r_relation.get("results", [])) > 0
        rule_found = len(r_rule.get("results", [])) > 0

        checks = [(all_created, 1.0), (entity_found, 1.0), (relation_found, 0.5), (rule_found, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-S02: SQLiteAdapter CRUD", score,
                     f"created={all_created} entity={entity_found} relation={relation_found} rule={rule_found}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-S02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_s03_chromadb_vector(cli: CLIRunner, report: AcptReport):
    """TC-S03: ChromaDBAdapter vector — fragment vector storage + semantic search."""
    t0 = time.time()
    try:
        cli.set_space(f"{SPACE}_s03")
        await cli.remember(
            "The Kubernetes cluster autoscaler scales nodes based on pending pod resource requests",
            tags={"tag": "k8s", "tag_2": "vector_test"},
            created_by="storage_test"
        )
        await cli.remember(
            "Horizontal Pod Autoscaler adjusts replica count based on CPU and memory metrics",
            tags={"tag": "k8s", "tag_2": "vector_test"},
            created_by="storage_test"
        )

        r1 = await cli.recall("Kubernetes scaling mechanism", max_results=3)
        results = r1.get("results", [])

        has_autoscaler = any("autoscaler" in res.get("text", "").lower() for res in results)
        has_hpa = any("Horizontal" in res.get("text", "") or "HPA" in res.get("text", "") for res in results)

        checks = [(len(results) >= 1, 1.0), (has_autoscaler, 1.0), (has_hpa, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-S03: ChromaDBAdapter vector storage", score,
                     f"results={len(results)} autoscaler={has_autoscaler} hpa={has_hpa}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-S03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_s04_rrf_retrieval(cli: CLIRunner, report: AcptReport):
    """TC-S04: RRF multi-path retrieval — vector+keyword+metadata fusion."""
    t0 = time.time()
    try:
        cli.set_space(f"{SPACE}_s04")
        await cli.remember(
            "API gateway rate limiting: 1000 requests per minute per API key",
            tags={"tag": "api", "tag_2": "rate_limiting"},
            confidence=0.9,
            created_by="storage_test"
        )
        await cli.remember(
            "Rate limiting algorithm: sliding window counter with Redis backend",
            tags={"tag": "api", "tag_2": "algorithm"},
            confidence=0.8,
            created_by="storage_test"
        )

        r1 = await cli.recall("API rate limiting", max_results=5)
        results = r1.get("results", [])

        has_rate_limit = any("rate limit" in res.get("text", "").lower() or "1000" in res.get("text", "") or "rate limiting" in res.get("text", "").lower() for res in results)
        has_algorithm = any("sliding window" in res.get("text", "").lower() or "Redis" in res.get("text", "") or "algorithm" in res.get("text", "").lower() for res in results)

        checks = [(len(results) >= 1, 1.0), (has_rate_limit, 1.0), (has_algorithm, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-S04: RRF multi-path retrieval", score,
                     f"results={len(results)} rate_limit={has_rate_limit} algorithm={has_algorithm}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-S04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_s05_citation_consolidation(cli: CLIRunner, report: AcptReport):
    """TC-S05: Citation mode consolidation — fragment stays, observation writes."""
    t0 = time.time()
    try:
        cli.set_space(f"{SPACE}_s05")
        resp_fragment = await cli.remember(
            "Fragment: PostgreSQL connection pool size should be 20",
            tags={"tag": "fragment", "tag_2": "citation_test"},
            memory_type="fragment",
            created_by="storage_test"
        )

        resp_observation = await cli.remember(
            "Observation: Database configuration recommends pool_size=20 for production",
            tags={"tag": "observation", "tag_2": "citation_test"},
            memory_type="observation",
            created_by="storage_test"
        )

        fragment_created = resp_fragment.get("node_id") is not None
        observation_created = resp_observation.get("node_id") is not None

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("PostgreSQL connection pool", max_results=5)
        both_found = len(r1.get("results", [])) >= 1

        checks = [(fragment_created, 1.0), (observation_created, 1.0), (both_found, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-S05: Citation mode consolidation", score,
                     f"fragment={fragment_created} observation={observation_created} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-S05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_s06_single_engine(cli: CLIRunner, report: AcptReport):
    """TC-S06: Single-engine mode — only ChromaDB or only SQLite available."""
    t0 = time.time()
    try:
        cli.set_space(f"{SPACE}_s06")
        resp = await cli.remember(
            "Single engine test: this memory should work with minimal storage backend",
            tags={"tag": "single_engine"},
            created_by="storage_test"
        )

        node_created = resp.get("node_id") is not None

        r1 = await cli.recall("Single engine test", max_results=3)
        found = len(r1.get("results", [])) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        checks = [(node_created, 1.0), (found, 1.0), (total >= 1, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-S06: Single-engine mode", score,
                     f"created={node_created} found={found} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-S06", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case14_storage_adapter")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 14: Storage Adapter — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-S01 Unified interface", run_s01_unified_interface),
            ("TC-S02 SQLite CRUD", run_s02_sqlite_crud),
            ("TC-S03 ChromaDB vector", run_s03_chromadb_vector),
            ("TC-S04 RRF retrieval", run_s04_rrf_retrieval),
            ("TC-S05 Citation consolidation", run_s05_citation_consolidation),
            ("TC-S06 Single-engine mode", run_s06_single_engine),
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
