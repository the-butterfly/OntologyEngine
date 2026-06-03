#!/usr/bin/env python3
"""OntologyEngine performance benchmark against docs/01-overview/03-goals.md targets."""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import shutil
import statistics
import sys
import tempfile
import time
from typing import Any


TARGETS: dict[str, dict[str, Any]] = {
    "node_capacity": {"MVP": 1_000, "P1": 100_000, "P2": 500_000, "P3": 2_000_000},
    "simple_query_p99_ms": {"MVP": 1000, "P1": 200, "P2": 100, "P3": 50},
    "graph_traversal_p99_ms": {"MVP": None, "P1": 2000, "P2": 1000, "P3": 500},
    "hybrid_search_p99_ms": {"MVP": None, "P1": 1000, "P2": 500, "P3": 300},
    "rule_count": {"MVP": 10, "P1": 20, "P2": 200, "P3": 1000},
    "deploy_deps": {"MVP": 0, "P1": 0, "P2": 0, "P3": "optional"},
    "layer_rs": {"MVP": None, "P1": "basic", "P2": "full", "P3": "optimized"},
    "decision_traceability": {"MVP": None, "P1": "rule_level", "P2": "rule+data", "P3": "full_chain"},
}

PHASES = ["MVP", "P1", "P2", "P3"]


def classify_phase(metric: str, value: Any) -> str:
    targets = TARGETS[metric]
    if metric == "deploy_deps":
        return "MVP" if value == 0 else "FAIL"
    if metric in ("layer_rs", "decision_traceability"):
        return "N/A"
    best = "FAIL"
    for phase in PHASES:
        target = targets.get(phase)
        if target is None:
            continue
        if isinstance(value, (int, float)) and isinstance(target, (int, float)):
            if value <= target:
                best = phase
    return best


def p99(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = min(int(math.ceil(len(sorted_v) * 0.99)) - 1, len(sorted_v) - 1)
    return sorted_v[idx]


async def benchmark_node_capacity(quick: bool) -> dict[str, Any]:
    from ontology_engine.storage.sqlite.store import SQLiteStorage
    from ontology_engine.storage.base import EntityInstance

    sizes = [1_000] if quick else [1_000, 100_000, 500_000]
    results: dict[str, Any] = {"max_nodes": 0, "phases": {}}

    for target_size in sizes:
        tmp_dir = tempfile.mkdtemp(prefix="oe_bench_nodes_")
        db_path = os.path.join(tmp_dir, "meta.db")
        store = SQLiteStorage(db_path=db_path)
        try:
            await store.initialize()
            batch_size = 1000
            written = 0
            t0 = time.monotonic()
            for batch_start in range(0, target_size, batch_size):
                for i in range(batch_start, min(batch_start + batch_size, target_size)):
                    entity = EntityInstance(
                        _fact_object="Company",
                        entity_id=f"company_{i:08d}",
                        data={"name": f"Company {i}", "credit_score": 80.0 - (i % 50)},
                    )
                    await store.save_entity(entity)
                    written += 1
            elapsed = time.monotonic() - t0
            phase = classify_phase("node_capacity", written)
            results["phases"][target_size] = {
                "written": written,
                "elapsed_s": round(elapsed, 2),
                "phase": phase,
            }
            if written > results["max_nodes"]:
                results["max_nodes"] = written
            await store.close()
        except Exception as exc:
            results["phases"][target_size] = {"error": str(exc), "written": written}
            try:
                await store.close()
            except Exception:
                pass
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    results["achieved_phase"] = classify_phase("node_capacity", results["max_nodes"])
    return results


async def benchmark_simple_query_p99(quick: bool) -> dict[str, Any]:
    from ontology_engine.storage.sqlite.store import SQLiteStorage
    from ontology_engine.storage.base import EntityInstance

    node_count = 1_000 if quick else 10_000
    iterations = 20 if quick else 100

    tmp_dir = tempfile.mkdtemp(prefix="oe_bench_query_")
    db_path = os.path.join(tmp_dir, "meta.db")
    store = SQLiteStorage(db_path=db_path)
    latencies: list[float] = []

    try:
        await store.initialize()
        for i in range(node_count):
            entity = EntityInstance(
                _fact_object="Company",
                entity_id=f"company_{i:08d}",
                data={"name": f"Company {i}", "credit_score": 80.0 - (i % 50)},
            )
            await store.save_entity(entity)

        for i in range(iterations):
            eid = f"company_{(i * 37) % node_count:08d}"
            t0 = time.monotonic()
            result = await store.get_entity("Company", eid)
            dt = (time.monotonic() - t0) * 1000
            if result is not None:
                latencies.append(dt)

        p99_val = p99(latencies) if latencies else float("inf")
        await store.close()
    except Exception as exc:
        return {"error": str(exc), "p99_ms": float("inf")}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "p99_ms": round(p99_val, 2),
        "mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "iterations": len(latencies),
        "achieved_phase": classify_phase("simple_query_p99_ms", p99_val),
    }


async def benchmark_graph_traversal_p99(quick: bool) -> dict[str, Any]:
    try:
        from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore
    except Exception:
        return {"p99_ms": None, "achieved_phase": "SKIP", "reason": "ladybug not installed"}

    iterations = 10 if quick else 50
    node_count = 200 if quick else 2_000

    tmp_dir = tempfile.mkdtemp(prefix="oe_bench_graph_")
    db_path = os.path.join(tmp_dir, "graph.ladybug")
    store = LadybugGraphStore()
    latencies: list[float] = []

    try:
        await store.initialize(db_path=db_path)

        nodes = []
        for i in range(node_count):
            nid = f"entity_{i:08d}"
            await store.upsert_node(nid, ["Company"], {"name": f"Entity {i}"})
            nodes.append(nid)

        for i in range(0, node_count - 1, 2):
            await store.upsert_edge(
                f"edge_{i}",
                nodes[i],
                nodes[i + 1],
                "guarantees",
                {"weight": 1.0},
            )

        for i in range(iterations):
            nid = nodes[i % len(nodes)]
            t0 = time.monotonic()
            neighbors = await store.get_neighbors(nid, edge_type="guarantees", direction="outgoing")
            dt = (time.monotonic() - t0) * 1000
            latencies.append(dt)

        p99_val = p99(latencies) if latencies else float("inf")
        await store.close()
    except Exception as exc:
        return {"error": str(exc), "p99_ms": None, "achieved_phase": "FAIL"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "p99_ms": round(p99_val, 2),
        "mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "iterations": len(latencies),
        "achieved_phase": classify_phase("graph_traversal_p99_ms", p99_val),
    }


async def benchmark_hybrid_search_p99(quick: bool) -> dict[str, Any]:
    from ontology_engine.storage.vector.local_vector_store import LocalVectorStore

    iterations = 10 if quick else 50
    vector_count = 100 if quick else 1_000
    dimension = 128

    store = LocalVectorStore()
    latencies: list[float] = []

    try:
        await store.initialize(dimension=dimension)

        import random
        random.seed(42)
        ids = []
        vectors = []
        for i in range(vector_count):
            ids.append(f"vec_{i}")
            vectors.append([random.gauss(0, 1) for _ in range(dimension)])
        await store.add_vectors(ids, vectors)

        for i in range(iterations):
            query_vec = [random.gauss(0, 1) for _ in range(dimension)]
            t0 = time.monotonic()
            await store.search(query_vec, top_k=10)
            dt = (time.monotonic() - t0) * 1000
            latencies.append(dt)

        p99_val = p99(latencies) if latencies else float("inf")
        await store.close()
    except Exception as exc:
        return {"error": str(exc), "p99_ms": None, "achieved_phase": "FAIL"}

    return {
        "p99_ms": round(p99_val, 2),
        "mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "iterations": len(latencies),
        "achieved_phase": classify_phase("hybrid_search_p99_ms", p99_val),
        "note": "vector-only mock (no LLM embedding)",
    }


async def benchmark_rule_execution(quick: bool) -> dict[str, Any]:
    from ontology_engine.storage.sqlite.store import SQLiteStorage
    from ontology_engine.storage.base import EntityInstance

    rule_counts = [10] if quick else [10, 20, 200]
    tmp_dir = tempfile.mkdtemp(prefix="oe_bench_rules_")
    db_path = os.path.join(tmp_dir, "meta.db")
    store = SQLiteStorage(db_path=db_path)
    results: dict[str, Any] = {"phases": {}}

    try:
        await store.initialize()
        entity = EntityInstance(
            _fact_object="Company",
            entity_id="test_company",
            data={"name": "TestCo", "credit_score": 75.0, "debt_ratio": 0.6},
        )
        await store.save_entity(entity)

        for rule_count in rule_counts:
            t0 = time.monotonic()
            for i in range(rule_count):
                await store.log_rule_execution(
                    entity_id="test_company",
                    rule_id=f"rule_{i:04d}",
                    result=f"passed_{i}",
                )
            elapsed = time.monotonic() - t0

            log = await store.get_rule_execution_log("test_company")
            correctness = len(log) == rule_count

            phase = classify_phase("rule_count", rule_count)
            results["phases"][rule_count] = {
                "elapsed_s": round(elapsed, 2),
                "correctness": correctness,
                "phase": phase,
            }

        max_rules = max(rule_counts)
        results["achieved_phase"] = classify_phase("rule_count", max_rules)
        await store.close()
    except Exception as exc:
        results["error"] = str(exc)
        results["achieved_phase"] = "FAIL"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


async def benchmark_deploy_deps() -> dict[str, Any]:
    import re
    import subprocess

    forbidden_patterns = ["neo4j", "redis", "psycopg2", "psycopg"]
    found: list[str] = []
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_root, "ontology_engine")

    for pattern in forbidden_patterns:
        try:
            result = subprocess.run(
                ["grep", "-r", f"import {pattern}\\|from {pattern}", src_dir, "--include=*.py", "-l"],
                capture_output=True, text=True, timeout=30,
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    rel = os.path.relpath(line.strip(), project_root)
                    if "adapters/" not in rel:
                        found.append(f"{pattern} in {rel}")
        except Exception:
            pass

    dep_count = len(found)
    return {
        "forbidden_found": found,
        "dep_count": dep_count,
        "achieved_phase": "MVP" if dep_count == 0 else "FAIL",
    }


def format_results(all_results: dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("OntologyEngine Performance Benchmark")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'Metric':<25} {'MVP':>8} {'P1':>8} {'P2':>8} {'P3':>8} {'Measured':>12} {'Phase':>8}")
    lines.append("-" * 89)

    node_cap = all_results.get("node_capacity", {})
    max_nodes = node_cap.get("max_nodes", 0)
    lines.append(
        f"{'Node Capacity':<25} {'1K':>8} {'100K':>8} {'500K':>8} {'2M+':>8} {max_nodes:>12} {node_cap.get('achieved_phase', 'N/A'):>8}"
    )

    sq = all_results.get("simple_query_p99", {})
    sq_val = sq.get("p99_ms", "N/A")
    sq_phase = sq.get("achieved_phase", "N/A")
    sq_str = f"{sq_val} ms" if isinstance(sq_val, (int, float)) else str(sq_val)
    lines.append(
        f"{'Simple Query P99':<25} {'1s':>8} {'200ms':>8} {'100ms':>8} {'50ms':>8} {sq_str:>12} {sq_phase:>8}"
    )

    gt = all_results.get("graph_traversal_p99", {})
    gt_val = gt.get("p99_ms")
    gt_phase = gt.get("achieved_phase", "N/A")
    gt_str = f"{gt_val} ms" if isinstance(gt_val, (int, float)) else str(gt_val) if gt_val else "SKIP"
    lines.append(
        f"{'Graph Traversal P99':<25} {'-':>8} {'2s':>8} {'1s':>8} {'500ms':>8} {gt_str:>12} {gt_phase:>8}"
    )

    hs = all_results.get("hybrid_search_p99", {})
    hs_val = hs.get("p99_ms")
    hs_phase = hs.get("achieved_phase", "N/A")
    hs_str = f"{hs_val} ms" if isinstance(hs_val, (int, float)) else str(hs_val) if hs_val else "SKIP"
    lines.append(
        f"{'Hybrid Search P99':<25} {'-':>8} {'1s':>8} {'500ms':>8} {'300ms':>8} {hs_str:>12} {hs_phase:>8}"
    )

    re = all_results.get("rule_execution", {})
    re_phase = re.get("achieved_phase", "N/A")
    max_rules_tested = max(re.get("phases", {}).keys()) if re.get("phases") else 0
    lines.append(
        f"{'Rule Count':<25} {'10':>8} {'20':>8} {'200':>8} {'1000':>8} {max_rules_tested:>12} {re_phase:>8}"
    )

    dd = all_results.get("deploy_deps", {})
    dd_count = dd.get("dep_count", 0)
    dd_phase = dd.get("achieved_phase", "N/A")
    lines.append(
        f"{'Deploy Dependencies':<25} {'0':>8} {'0':>8} {'0':>8} {'opt':>8} {dd_count:>12} {dd_phase:>8}"
    )

    lines.append("")
    lines.append("=" * 60)
    lines.append("Detailed Results")
    lines.append("=" * 60)

    for key, val in all_results.items():
        lines.append(f"\n--- {key} ---")
        if isinstance(val, dict):
            for k, v in val.items():
                if k == "phases" and isinstance(v, dict):
                    for pk, pv in v.items():
                        lines.append(f"  {pk}: {pv}")
                else:
                    lines.append(f"  {k}: {v}")

    return "\n".join(lines)


async def run_all(quick: bool) -> dict[str, Any]:
    results: dict[str, Any] = {}

    print("1/6 Node Capacity Benchmark...")
    results["node_capacity"] = await benchmark_node_capacity(quick)

    print("2/6 Simple Query P99 Benchmark...")
    results["simple_query_p99"] = await benchmark_simple_query_p99(quick)

    print("3/6 Graph Traversal P99 Benchmark...")
    results["graph_traversal_p99"] = await benchmark_graph_traversal_p99(quick)

    print("4/6 Hybrid Search P99 Benchmark...")
    results["hybrid_search_p99"] = await benchmark_hybrid_search_p99(quick)

    print("5/6 Rule Execution Benchmark...")
    results["rule_execution"] = await benchmark_rule_execution(quick)

    print("6/6 Deploy Dependency Check...")
    results["deploy_deps"] = await benchmark_deploy_deps()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="OntologyEngine Performance Benchmark")
    parser.add_argument("--quick", action="store_true", help="Quick mode: reduced data volumes")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    args = parser.parse_args()

    results = asyncio.run(run_all(args.quick))

    if args.json:
        import json
        print(json.dumps(results, indent=2, default=str))
    else:
        print(format_results(results))


if __name__ == "__main__":
    main()
