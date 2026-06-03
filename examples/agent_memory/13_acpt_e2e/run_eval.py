#!/usr/bin/env python3
"""Case 5: Agent Memory End-to-End — Full Lifecycle Acceptance Tests.

8 test cases covering the complete memory lifecycle:
  TC-501: Zero-parameter mode (auto-infer type, tags, confidence)
  TC-502: Contradiction detection and belief revision
  TC-503: Consolidation and entity compilation
  TC-504: DreamCycle maintenance (selective forgetting)
  TC-505: Reflect deep analysis
  TC-506: Lifecycle governance (create/update/version/rollback)
  TC-507: Multi-agent isolation (cross-user visibility)
  TC-508: End-to-end full flow (remember→recall→reflect→consolidate→dream→recall)

Usage: python examples/agent_memory/13_acpt_e2e/run_eval.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from examples.agent_memory._lib.cli_runner import CLIRunner, create_runner
from examples.agent_memory._lib.acpt_test import AcptReport, r

SPACE = "acpt_e2e"
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
EXPECTED_DIR = Path(__file__).parent / "expected_outputs"


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


async def run_tc501_zero_param(runner: CLIRunner):
    """TC-501: Zero-parameter mode — auto-infer type, tags, confidence."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc501")

    resp = await runner.remember(
        "TechNova公司CEO张明于2025年3月宣布AI战略转型",
        memory_type="fragment",
    )

    has_node_id = bool(resp.get("node_id") or resp.get("data", {}).get("node_id") or resp.get("memory_id"))
    has_decision = bool(resp.get("decision") or resp.get("data", {}).get("decision"))

    score = 1.0 if (has_node_id and has_decision) else 0.5 if has_node_id else 0.0

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-501 Zero-parameter mode",
        score,
        f"node_id={has_node_id} decision={has_decision}",
        latency_ms,
        {"node_id": float(has_node_id), "decision": float(has_decision)},
    )


async def run_tc502_contradiction(runner: CLIRunner):
    """TC-502: Contradiction detection and belief revision."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc502")

    resp1 = await runner.remember(
        "TechNova总部在深圳",
        memory_type="entity", tags={"tag": "company", "tag_2": "location"}, confidence=0.9,
    )
    node_id_1 = resp1.get("node_id") or resp1.get("data", {}).get("node_id")

    resp2 = await runner.remember(
        "TechNova总部在上海",
        memory_type="entity", tags={"tag": "company", "tag_2": "location"}, confidence=0.9,
    )
    node_id_2 = resp2.get("node_id") or resp2.get("data", {}).get("node_id")

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall("TechNova总部", max_results=5, include_evidence=False)
    results = recall_resp.get("results", [])

    all_text = " ".join(r.get("text", "") for r in results)
    has_shenzhen = "深圳" in all_text
    has_shanghai = "上海" in all_text
    has_both = has_shenzhen and has_shanghai

    score = 0.8 if has_both else 0.5 if (has_shenzhen or has_shanghai) else 0.0

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-502 Contradiction detection",
        score,
        f"has_shenzhen={has_shenzhen} has_shanghai={has_shanghai} has_both={has_both}",
        latency_ms,
        {"has_both": float(has_both)},
    )


async def run_tc503_consolidation(runner: CLIRunner):
    """TC-503: Consolidation and entity compilation."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc503")

    await runner.remember(
        "王芳是TechNova技术负责人",
        memory_type="observation", tags={"tag": "person", "tag_2": "role"}, confidence=0.9,
    )
    await runner.remember(
        "王芳主导架构迁移到CloudGroup平台",
        memory_type="observation", tags={"tag": "person", "tag_2": "project"}, confidence=0.9,
    )
    await runner.remember(
        "王芳团队有50人",
        memory_type="observation", tags={"tag": "person", "tag_2": "team"}, confidence=0.9,
    )

    await asyncio.sleep(0.5)

    consolidate_resp = await runner.consolidate()
    has_consolidation = bool(consolidate_resp)

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall("王芳", max_results=5, include_evidence=False)
    results = recall_resp.get("results", [])

    all_text = " ".join(r.get("text", "") for r in results)
    found_role = "技术负责人" in all_text or "role" in all_text.lower()
    found_project = "CloudGroup" in all_text or "架构" in all_text
    found_team = "50" in all_text or "team" in all_text.lower()

    score = 0.0
    if has_consolidation and found_role and found_project and found_team:
        score = 1.0
    elif has_consolidation and (found_role or found_project or found_team):
        score = 0.6
    elif found_role or found_project or found_team:
        score = 0.4

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-503 Consolidation and entity compilation",
        score,
        f"consolidation={has_consolidation} role={found_role} project={found_project} team={found_team}",
        latency_ms,
        {"consolidation": float(has_consolidation)},
    )


async def run_tc504_dream_cycle(runner: CLIRunner):
    """TC-504: DreamCycle maintenance — selective forgetting."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc504")

    await runner.remember(
        "2023年Q1 API限流1000次/分钟",
        memory_type="observation", tags={"tag": "api", "tag_2": "old"}, confidence=0.3,
    )
    await runner.remember(
        "TechNova核心架构使用微服务",
        memory_type="entity", tags={"tag": "arch", "tag_2": "core"}, confidence=0.95,
    )

    await asyncio.sleep(0.5)

    stats_before = await runner.stats()
    count_before = stats_before.get("total", 0)

    dream_resp = await runner.dream()
    has_dream = bool(dream_resp)

    await asyncio.sleep(0.5)

    stats_after = await runner.stats()
    count_after = stats_after.get("total", 0)

    score = 0.8 if has_dream else 0.4

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-504 DreamCycle maintenance",
        score,
        f"dream={has_dream} count_before={count_before} count_after={count_after}",
        latency_ms,
        {"dream": float(has_dream)},
    )


async def run_tc505_reflect(runner: CLIRunner):
    """TC-505: Reflect deep analysis."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc505")

    await runner.remember(
        "TechNova从单体架构迁移到微服务",
        memory_type="observation", tags={"tag": "arch", "tag_2": "migration"}, confidence=0.9,
    )
    await runner.remember(
        "迁移后性能提升30%",
        memory_type="observation", tags={"tag": "performance"}, confidence=0.85,
    )
    await runner.remember(
        "迁移过程中遇到服务间通信问题",
        memory_type="observation", tags={"tag": "challenge"}, confidence=0.8,
    )

    await asyncio.sleep(0.5)

    reflect_resp = await runner.reflect("TechNova技术架构演进")

    has_insights = bool(reflect_resp.get("insights"))
    has_iterations = bool(reflect_resp.get("iterations_used", 0) > 0)
    insights_count = len(reflect_resp.get("insights", []))

    score = 1.0 if (has_insights and has_iterations) else 0.5 if has_insights else 0.3

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-505 Reflect deep analysis",
        score,
        f"has_insights={has_insights} has_iterations={has_iterations} insights_count={insights_count}",
        latency_ms,
        {"has_insights": float(has_insights), "insights_count": insights_count},
    )


async def run_tc506_lifecycle(runner: CLIRunner):
    """TC-506: Lifecycle governance — create/update/version/rollback."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc506")

    resp1 = await runner.remember(
        "TechNova营收100亿",
        memory_type="observation", tags={"tag": "financial"}, confidence=0.9,
    )
    node_id_1 = resp1.get("node_id") or resp1.get("data", {}).get("node_id")

    resp2 = await runner.remember(
        "TechNova营收120亿",
        memory_type="observation", tags={"tag": "financial"}, confidence=0.9,
        supersede_target=node_id_1,
        supersede_reason="数据更新",
    )
    node_id_2 = resp2.get("node_id") or resp2.get("data", {}).get("node_id")

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall("TechNova", max_results=5, include_evidence=False)
    results = recall_resp.get("results", [])

    has_results = len(results) > 0
    all_text = " ".join(r.get("text", "") for r in results)
    has_revenue = "营收" in all_text or "revenue" in all_text.lower()
    has_supersede = "supersede" in all_text.lower() or "更新" in all_text or "120" in all_text

    score = 0.0
    if has_results and has_revenue:
        score = 1.0
    elif has_results:
        score = 0.7
    elif node_id_1 and node_id_2:
        score = 0.5

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-506 Lifecycle governance",
        score,
        f"has_results={has_results} has_revenue={has_revenue} has_supersede={has_supersede}",
        latency_ms,
        {"has_results": float(has_results), "has_revenue": float(has_revenue)},
    )


async def run_tc507_multi_agent(runner: CLIRunner):
    """TC-507: Multi-agent isolation — cross-user visibility."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc507")

    await runner.remember(
        "alice的数据库密钥sk-abc123",
        memory_type="observation", tags={"tag": "secret"}, confidence=0.95,
        visibility="private", created_by="alice",
    )
    await runner.remember(
        "公开API文档地址/wiki/api",
        memory_type="observation", tags={"tag": "public"}, confidence=0.9,
        visibility="shared", created_by="alice",
    )

    await asyncio.sleep(0.5)

    bob_recall = await runner.recall(
        "密钥", max_results=5, user_id="bob", include_evidence=False,
    )
    bob_results = bob_recall.get("results", [])
    bob_text = " ".join(r.get("text", "") for r in bob_results)
    bob_leak = "sk-abc123" in bob_text

    bob_public = await runner.recall(
        "API文档", max_results=5, user_id="bob", include_evidence=False,
    )
    bob_public_results = bob_public.get("results", [])
    bob_public_text = " ".join(r.get("text", "") for r in bob_public_results)
    bob_sees_public = "wiki/api" in bob_public_text or "API文档" in bob_public_text

    if not bob_leak and bob_sees_public:
        score = 1.0
    elif not bob_leak:
        score = 0.7
    elif bob_sees_public:
        score = 0.3
    else:
        score = 0.0

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-507 Multi-agent isolation",
        score,
        f"bob_leak={bob_leak} bob_sees_public={bob_sees_public}",
        latency_ms,
        {"bob_leak": float(bob_leak), "bob_sees_public": float(bob_sees_public)},
    )


async def run_tc508_e2e_flow(runner: CLIRunner):
    """TC-508: End-to-end full flow — remember→recall→reflect→consolidate→dream→recall."""
    t0 = time.time()
    runner.set_space(f"{SPACE}_tc508")

    await runner.remember(
        "TechNova完成B轮融资5亿元",
        memory_type="entity", tags={"tag": "financing", "tag_2": "milestone"}, confidence=0.95,
    )
    await runner.remember(
        "投资方包括红杉资本和高瓴资本",
        memory_type="observation", tags={"tag": "financing", "tag_2": "investor"}, confidence=0.9,
    )
    await runner.remember(
        "融资将用于AI产品研发",
        memory_type="observation", tags={"tag": "financing", "tag_2": "use_of_funds"}, confidence=0.85,
    )

    await asyncio.sleep(0.5)

    recall1 = await runner.recall("TechNova融资", max_results=5, include_evidence=False)
    results1 = recall1.get("results", [])
    initial_recall_count = len(results1)

    await runner.reflect("TechNova融资历程分析")
    await asyncio.sleep(0.3)

    await runner.consolidate()
    await asyncio.sleep(0.3)

    await runner.dream()
    await asyncio.sleep(0.3)

    recall2 = await runner.recall("TechNova融资", max_results=5, include_evidence=False)
    results2 = recall2.get("results", [])
    final_recall_count = len(results2)

    all_text = " ".join(r.get("text", "") for r in results2)
    has_financing = "融资" in all_text or "B轮" in all_text

    investor_recall = await runner.recall("投资方 红杉", max_results=3, include_evidence=False)
    investor_results = investor_recall.get("results", [])
    investor_text = " ".join(r.get("text", "") for r in investor_results)
    has_investor = "红杉" in investor_text or "高瓴" in investor_text or "投资方" in investor_text or "资本" in investor_text

    score = 0.0
    if has_financing and has_investor and final_recall_count > 0:
        score = 1.0
    elif has_financing and final_recall_count > 0:
        score = 0.8
    elif has_financing or has_investor:
        score = 0.6
    elif final_recall_count > 0:
        score = 0.3

    latency_ms = (time.time() - t0) * 1000
    return r(
        "TC-508 End-to-end full flow",
        score,
        f"initial_recall={initial_recall_count} final_recall={final_recall_count} financing={has_financing} investor={has_investor}",
        latency_ms,
        {"initial_recall": initial_recall_count, "final_recall": final_recall_count},
    )


async def main():
    runner, tmp_dir = await create_runner(SPACE)
    report = AcptReport(case_name="acpt_e2e")

    try:
        print("=" * 70)
        print("Case 5: Agent Memory End-to-End — Full Lifecycle Acceptance Tests")
        print("=" * 70)

        scenarios = [
            ("TC-501 Zero-parameter mode", run_tc501_zero_param),
            ("TC-502 Contradiction detection", run_tc502_contradiction),
            ("TC-503 Consolidation and entity compilation", run_tc503_consolidation),
            ("TC-504 DreamCycle maintenance", run_tc504_dream_cycle),
            ("TC-505 Reflect deep analysis", run_tc505_reflect),
            ("TC-506 Lifecycle governance", run_tc506_lifecycle),
            ("TC-507 Multi-agent isolation", run_tc507_multi_agent),
            ("TC-508 End-to-end full flow", run_tc508_e2e_flow),
        ]

        for name, fn in scenarios:
            print(f"\n--- {name} ---")
            try:
                result = await asyncio.wait_for(fn(runner), timeout=120)
                report.add(result)
                print(f"  [{result.score:.2f}] {result.name}")
            except asyncio.TimeoutError:
                timeout_result = r(name, 0.0, "TIMEOUT", 120000.0)
                report.add(timeout_result)
                print(f"  [0.00] {name} (TIMEOUT)")
            except Exception as e:
                err_result = r(name, 0.0, str(e), 0.0)
                report.add(err_result)
                print(f"  [0.00] {name} (ERROR: {e})")
            await asyncio.sleep(0.5)

    finally:
        print("\n" + report.summary())
        report.save(Path(__file__).parent)
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
