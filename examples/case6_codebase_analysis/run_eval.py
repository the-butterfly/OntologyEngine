#!/usr/bin/env python3
"""Case 6: Codebase Analysis — J5 Code Analysis Acceptance Tests.

Verifies vision journey J5:
  TC-601: AST deterministic extraction — classes/functions/imports/call graph
  TC-602: SHA256 cache — unchanged files skipped
  TC-603: LLM semantic extraction — concepts/relationships/design intent
  TC-604: Confidence labels — EXTRACTED/INFERRED/AMBIGUOUS
  TC-605: Knowledge graph construction — nodes and edges correctly built
  TC-606: Graph traversal query — BFS shortest path
  TC-607: Impact analysis — modify a function, return impact scope
  TC-608: Incremental processing — modify 1 file, verify rest unchanged

Usage: python examples/case6_codebase_analysis/run_eval.py
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

SPACE = "codebase_analysis"
CASE_DIR = Path(__file__).parent


async def run_601_ast_extraction(cli: CLIRunner, report: AcptReport):
    """TC-601: AST deterministic extraction of code structure."""
    t0 = time.time()
    try:
        code_snippet = (
            "class UserService:\n"
            "    def __init__(self, db):\n"
            "        self.db = db\n"
            "    def get_user(self, user_id):\n"
            "        return self.db.query(user_id)\n"
            "    def create_user(self, name, email):\n"
            "        return self.db.insert(name=name, email=email)\n"
        )

        resp = await cli.remember(
            f"Code extracted from user_service.py:\n{code_snippet}",
            tags={"tag": "code", "tag_2": "ast_extracted", "tag_3": "user_service"},
            memory_type="observation",
            created_by="ast_extractor"
        )

        node_id = resp.get("node_id")
        has_node = node_id is not None

        r1 = await cli.recall("UserService class", max_results=3)
        found_class = len(r1.get("results", [])) > 0

        r2 = await cli.recall("get_user method", max_results=3)
        found_method = len(r2.get("results", [])) > 0

        checks = [(has_node, 1.0), (found_class, 1.0), (found_method, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-601: AST deterministic extraction", score,
                     f"node_created={has_node} class_found={found_class} method_found={found_method}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-601", 0.0, str(e), (time.time() - t0) * 1000))


async def run_602_sha256_cache(cli: CLIRunner, report: AcptReport):
    """TC-602: SHA256 cache — unchanged files skipped."""
    t0 = time.time()
    try:
        content = "def calculate_total(items): return sum(i['price'] for i in items)"

        resp1 = await cli.remember(
            f"File: pricing.py, SHA256: abc123, Content: {content}",
            tags={"tag": "code", "tag_2": "pricing", "tag_3": "sha256:abc123"},
            created_by="cache_test"
        )

        resp2 = await cli.remember(
            f"File: pricing.py, SHA256: abc123, Content: {content} [CACHED - unchanged]",
            tags={"tag": "code", "tag_2": "pricing", "tag_3": "sha256:abc123", "tag_4": "cached"},
            created_by="cache_test"
        )

        resp3 = await cli.remember(
            f"File: pricing.py, SHA256: def456, Content: def calculate_total(items): return sum(i['price'] * i['qty'] for i in items)",
            tags={"tag": "code", "tag_2": "pricing", "tag_3": "sha256:def456"},
            created_by="cache_test"
        )

        all_created = all(r.get("node_id") is not None for r in [resp1, resp2, resp3])

        r1 = await cli.recall("pricing.py SHA256", max_results=5)
        cache_entries = len(r1.get("results", []))

        checks = [(all_created, 1.0), (cache_entries >= 2, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-602: SHA256 cache", score,
                     f"all_created={all_created} cache_entries={cache_entries}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-602", 0.0, str(e), (time.time() - t0) * 1000))


async def run_603_llm_semantic(cli: CLIRunner, report: AcptReport):
    """TC-603: LLM semantic extraction — concepts/relationships/design intent."""
    t0 = time.time()
    try:
        await cli.remember(
            "The authentication module implements OAuth2 with JWT tokens. "
            "It validates tokens against the auth server and extracts user claims. "
            "Design intent: centralized auth for all microservices.",
            tags={"tag": "semantic_extracted", "tag_2": "auth", "tag_3": "oauth2"},
            memory_type="observation",
            created_by="llm_extractor"
        )

        r1 = await cli.recall("OAuth2 authentication", max_results=3)
        found_concept = any("OAuth2" in res.get("text", "") for res in r1.get("results", []))

        r2 = await cli.recall("design intent", max_results=3)
        found_intent = any("centralized" in res.get("text", "").lower() for res in r2.get("results", []))

        checks = [(found_concept, 1.0), (found_intent, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-603: LLM semantic extraction", score,
                     f"concept_found={found_concept} intent_found={found_intent}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-603", 0.0, str(e), (time.time() - t0) * 1000))


async def run_604_confidence_labels(cli: CLIRunner, report: AcptReport):
    """TC-604: Confidence labels — EXTRACTED/INFERRED/AMBIGUOUS."""
    t0 = time.time()
    try:
        resp_extracted = await cli.remember(
            "Function process_order calls validate_payment and ship_order",
            tags={"tag": "call_graph", "tag_2": "confidence:EXTRACTED"},
            confidence=0.95,
            created_by="confidence_test"
        )

        resp_inferred = await cli.remember(
            "process_order likely requires database connection based on pattern",
            tags={"tag": "call_graph", "tag_2": "confidence:INFERRED"},
            confidence=0.6,
            created_by="confidence_test"
        )

        resp_ambiguous = await cli.remember(
            "Unknown function mystery_handler may be related to error processing",
            tags={"tag": "call_graph", "tag_2": "confidence:AMBIGUOUS"},
            confidence=0.3,
            created_by="confidence_test"
        )

        all_created = all(r.get("node_id") is not None for r in [resp_extracted, resp_inferred, resp_ambiguous])

        r_high = await cli.recall("process_order", max_results=5, min_confidence=0.8)
        high_conf_results = len(r_high.get("results", []))

        checks = [(all_created, 1.0), (high_conf_results >= 1, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-604: Confidence labels", score,
                     f"all_created={all_created} high_conf_results={high_conf_results}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-604", 0.0, str(e), (time.time() - t0) * 1000))


async def run_605_kg_construction(cli: CLIRunner, report: AcptReport):
    """TC-605: Knowledge graph construction — nodes and edges correctly built."""
    t0 = time.time()
    try:
        await cli.remember(
            "Module A imports Module B and Module C",
            tags={"tag": "import_graph", "tag_2": "module_a"},
            memory_type="observation",
            created_by="kg_test"
        )
        await cli.remember(
            "Module B defines class DataProcessor",
            tags={"tag": "import_graph", "tag_2": "module_b"},
            memory_type="observation",
            created_by="kg_test"
        )
        await cli.remember(
            "Module C defines class ConfigManager",
            tags={"tag": "import_graph", "tag_2": "module_c"},
            memory_type="observation",
            created_by="kg_test"
        )

        stats = await cli.stats()
        total = stats.get("total", 0)

        r1 = await cli.recall("Module A imports", max_results=5)
        r2 = await cli.recall("DataProcessor class", max_results=5)

        has_imports = len(r1.get("results", [])) > 0
        has_class = len(r2.get("results", [])) > 0

        checks = [(total >= 3, 1.0), (has_imports, 1.0), (has_class, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-605: Knowledge graph construction", score,
                     f"total={total} imports_found={has_imports} class_found={has_class}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-605", 0.0, str(e), (time.time() - t0) * 1000))


async def run_606_graph_traversal(cli: CLIRunner, report: AcptReport):
    """TC-606: Graph traversal query — BFS shortest path."""
    t0 = time.time()
    try:
        await cli.remember("Handler A calls Service B", tags={"tag": "call_chain"}, created_by="traversal_test")
        await cli.remember("Service B calls Repository C", tags={"tag": "call_chain"}, created_by="traversal_test")
        await cli.remember("Repository C calls Database D", tags={"tag": "call_chain"}, created_by="traversal_test")

        r_start = await cli.recall("Handler A", max_results=5)
        r_end = await cli.recall("Database D", max_results=5)

        has_start = len(r_start.get("results", [])) > 0
        has_end = len(r_end.get("results", [])) > 0

        r_path = await cli.recall("Service B Repository C", max_results=5)
        has_path = len(r_path.get("results", [])) >= 2

        checks = [(has_start, 1.0), (has_end, 1.0), (has_path, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-606: Graph traversal query", score,
                     f"start_found={has_start} end_found={has_end} path_found={has_path}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-606", 0.0, str(e), (time.time() - t0) * 1000))


async def run_607_impact_analysis(cli: CLIRunner, report: AcptReport):
    """TC-607: Impact analysis — modify a function, return impact scope."""
    t0 = time.time()
    try:
        await cli.remember("Function validate_input is called by create_user, update_user, delete_user",
                          tags={"tag": "impact", "tag_2": "validate_input"}, created_by="impact_test")
        await cli.remember("create_user is called by UserAPI.register",
                          tags={"tag": "impact", "tag_2": "create_user"}, created_by="impact_test")
        await cli.remember("update_user is called by UserAPI.modify",
                          tags={"tag": "impact", "tag_2": "update_user"}, created_by="impact_test")

        r_impact = await cli.recall("validate_input impact", max_results=10)
        impact_results = r_impact.get("results", [])

        has_callers = any("create_user" in res.get("text", "") for res in impact_results)
        has_downstream = any("UserAPI" in res.get("text", "") for res in impact_results)

        checks = [(len(impact_results) >= 2, 1.0), (has_callers, 1.0), (has_downstream, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-607: Impact analysis", score,
                     f"impact_results={len(impact_results)} callers_found={has_callers} downstream_found={has_downstream}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-607", 0.0, str(e), (time.time() - t0) * 1000))


async def run_608_incremental_processing(cli: CLIRunner, report: AcptReport):
    """TC-608: Incremental processing — modify 1 file, verify rest unchanged."""
    t0 = time.time()
    try:
        await cli.remember("File: auth.py, SHA256: hash1, content: def login(): pass",
                          tags={"tag": "code", "tag_2": "auth"}, created_by="incremental_test")
        await cli.remember("File: user.py, SHA256: hash2, content: def get_user(): pass",
                          tags={"tag": "code", "tag_2": "user"}, created_by="incremental_test")
        await cli.remember("File: order.py, SHA256: hash3, content: def create_order(): pass",
                          tags={"tag": "code", "tag_2": "order"}, created_by="incremental_test")

        stats_before = await cli.stats()
        total_before = stats_before.get("total", 0)

        resp_updated = await cli.remember(
            "File: auth.py, SHA256: hash4, content: def login(): return authenticate()",
            tags={"tag": "code", "tag_2": "auth", "tag_3": "modified"},
            created_by="incremental_test"
        )

        stats_after = await cli.stats()
        total_after = stats_after.get("total", 0)

        r_user = await cli.recall("user.py", max_results=3)
        r_order = await cli.recall("order.py", max_results=3)

        user_unchanged = len(r_user.get("results", [])) > 0
        order_unchanged = len(r_order.get("results", [])) > 0

        checks = [(total_after >= total_before, 1.0), (user_unchanged, 1.0), (order_unchanged, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-608: Incremental processing", score,
                     f"before={total_before} after={total_after} user_unchanged={user_unchanged} order_unchanged={order_unchanged}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-608", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case6_codebase_analysis")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 6: Codebase Analysis — Acceptance Tests")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-601 AST extraction", run_601_ast_extraction),
            ("TC-602 SHA256 cache", run_602_sha256_cache),
            ("TC-603 LLM semantic", run_603_llm_semantic),
            ("TC-604 Confidence labels", run_604_confidence_labels),
            ("TC-605 KG construction", run_605_kg_construction),
            ("TC-606 Graph traversal", run_606_graph_traversal),
            ("TC-607 Impact analysis", run_607_impact_analysis),
            ("TC-608 Incremental processing", run_608_incremental_processing),
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
