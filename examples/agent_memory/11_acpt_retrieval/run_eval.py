#!/usr/bin/env python3
"""Category A: Retrieval Effectiveness Acceptance Tests.

9 scenarios covering the retrieval quality spectrum:
  A-01: Single-hop exact match (F1 score)
  A-02: Semantic gap recall (rank-weighted)
  A-03: Multi-hop recall chain (chain adjacency)
  A-04: Temporal ordering (rank position check)
  A-05: Cross-type recall (type diversity)
  A-06: Confidence filtering
  A-07: Evidence chain expansion
  A-08: Private memory isolation
  A-09: Token budget truncation

Usage: python examples/agent_memory/11_acpt_retrieval/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from examples.agent_memory._lib.cli_runner import CLIRunner, create_runner
from examples.agent_memory._lib.acpt_test import (
    AcptReport,
    r,
    f1_score,
    rank_weighted_score,
    check_recall_chain_adjacency,
)

SPACE = "acpt_retrieval"


def _extract_results(recall_resp: dict) -> list[dict]:
    results = recall_resp.get("results", [])
    return results


async def run_a01_single_hop(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a01")

    await runner.remember(
        "TechNova公司总部位于深圳南山区",
        memory_type="entity", tags={"tag": "company", "tag_2": "location"}, confidence=0.9,
    )
    await runner.remember(
        "TechNova成立于2020年",
        memory_type="observation", tags={"tag": "company", "tag_2": "founding"}, confidence=0.9,
    )
    await runner.remember(
        "竞争对手是云帆科技",
        memory_type="observation", tags={"tag": "competition"}, confidence=0.8,
    )

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall("TechNova总部在哪里", max_results=5, include_evidence=False)
    results = _extract_results(recall_resp)

    scores = f1_score(results, expected_keywords=["深圳"])
    f1 = scores["f1"]
    precision = scores["precision"]
    recall = scores["recall"]

    all_text = " ".join(r.get("text", "") for r in results)
    noise_penalty = 0.1 if "云帆" in all_text else 0.0

    score = max(0.0, f1 - noise_penalty)

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-01 Single-hop exact match",
        score,
        f"f1={f1:.4f} precision={precision:.4f} recall={recall:.4f} noise_penalty={noise_penalty:.1f}",
        latency_ms,
        {"f1": f1, "precision": precision, "recall": recall},
    )


async def run_a02_semantic_gap(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a02")

    await runner.remember(
        "TechNova微服务部署在CloudGroup云平台上",
        memory_type="observation", tags={"tag": "infra", "tag_2": "cloud"}, confidence=0.9,
    )
    await runner.remember(
        "使用Kubernetes作为容器编排方案",
        memory_type="observation", tags={"tag": "infra", "tag_2": "k8s"}, confidence=0.9,
    )
    await runner.remember(
        "后端服务用Go语言开发",
        memory_type="observation", tags={"tag": "backend", "tag_2": "go"}, confidence=0.9,
    )
    await runner.remember(
        "前端用React框架",
        memory_type="observation", tags={"tag": "frontend", "tag_2": "react"}, confidence=0.9,
    )

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall("云平台技术栈", max_results=10, include_evidence=False)
    results = _extract_results(recall_resp)

    rw_score = rank_weighted_score(results, ["CloudGroup", "Kubernetes"])

    cloudgroup_rank = None
    k8s_rank = None
    for i, res in enumerate(results, start=1):
        text = res.get("text", "")
        if cloudgroup_rank is None and "CloudGroup" in text:
            cloudgroup_rank = i
        if k8s_rank is None and "Kubernetes" in text:
            k8s_rank = i

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-02 Semantic gap recall",
        rw_score,
        f"rank_weighted={rw_score:.4f} CloudGroup_rank={cloudgroup_rank} K8s_rank={k8s_rank}",
        latency_ms,
        {"rank_weighted": rw_score},
    )


async def run_a03_multi_hop(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a03")

    await runner.remember(
        "王芳是TechNova技术负责人",
        memory_type="entity", tags={"tag": "person", "tag_2": "leadership"}, confidence=0.9,
    )
    await runner.remember(
        "王芳主导架构迁移到CloudGroup平台",
        memory_type="observation", tags={"tag": "arch", "tag_2": "migration"}, confidence=0.9,
    )
    await runner.remember(
        "CloudGroup平台底层使用Kubernetes编排",
        memory_type="observation", tags={"tag": "infra", "tag_2": "k8s"}, confidence=0.9,
    )

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall(
        "王芳团队的技术架构使用了什么平台和编排方案",
        max_results=10, include_evidence=False,
    )
    results = _extract_results(recall_resp)

    chain_result = check_recall_chain_adjacency(
        results, [("王芳", "CloudGroup"), ("CloudGroup", "Kubernetes")]
    )
    adj_score = chain_result["adjacency_score"]

    pair_details = ", ".join(
        f"{k}={v:.4f}" for k, v in chain_result.items() if k != "adjacency_score"
    )

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-03 Multi-hop recall chain",
        adj_score,
        f"adjacency={adj_score:.4f} {pair_details}",
        latency_ms,
        chain_result,
    )


async def run_a04_temporal_ordering(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a04")

    await runner.remember(
        "2023年Q1: TechNova API限流策略为1000次/分钟",
        memory_type="constraint", tags={"tag": "api", "tag_2": "policy"}, confidence=0.85,
    )
    await runner.remember(
        "2024年Q3: TechNova API限流策略调整为5000次/分钟",
        memory_type="constraint", tags={"tag": "api", "tag_2": "policy"}, confidence=0.85,
    )
    await runner.remember(
        "2025年Q2: TechNova API限流策略提高至10000次/分钟",
        memory_type="constraint", tags={"tag": "api", "tag_2": "policy"}, confidence=0.85,
    )

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall(
        "TechNova最新的API限流策略", max_results=10, include_evidence=False,
    )
    results = _extract_results(recall_resp)

    score = 0.0
    if results:
        rank1_text = results[0].get("text", "")
        if "10000" in rank1_text:
            score += 0.5
        elif any("10000" in r.get("text", "") for r in results):
            score += 0.25

        last_text = results[-1].get("text", "")
        if "1000" in last_text:
            score += 0.5

    rank1_has_latest = bool(results) and "10000" in results[0].get("text", "")
    last_has_oldest = bool(results) and "1000" in results[-1].get("text", "")

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-04 Temporal ordering",
        score,
        f"rank1_has_latest={rank1_has_latest} last_has_oldest={last_has_oldest}",
        latency_ms,
        {"rank1_latest": float(rank1_has_latest), "last_oldest": float(last_has_oldest)},
    )


async def run_a05_cross_type(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a05")

    await runner.remember(
        "TechNova战略转向AI领域",
        memory_type="observation", tags={"tag": "strategy", "tag_2": "ai"}, confidence=0.9,
    )
    await runner.remember(
        "TechNova架构变更须经安全委员会审批",
        memory_type="rule", tags={"tag": "governance", "tag_2": "security"}, confidence=0.95,
    )
    await runner.remember(
        "TechNova_核心架构",
        memory_type="entity", tags={"tag": "arch", "tag_2": "core"}, confidence=0.9,
    )

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall(
        "TechNova架构", memory_type=None, max_results=10, include_evidence=False,
    )
    results = _extract_results(recall_resp)

    found_types = set()
    for res in results:
        mt = res.get("memory_type", "")
        if mt:
            found_types.add(mt)

    distinct_count = len(found_types)
    score = min(distinct_count / 3, 1.0)

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-05 Cross-type recall",
        score,
        f"types_found={sorted(found_types)}, distinct_count={distinct_count}",
        latency_ms,
        {"distinct_types": float(distinct_count)},
    )


async def run_a06_confidence_filtering(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a06")

    await runner.remember(
        "SQL注入防护已全面启用",
        memory_type="observation", tags={"tag": "security", "tag_2": "sql"}, confidence=1.0,
    )
    await runner.remember(
        "可能存在CSRF风险",
        memory_type="observation", tags={"tag": "security", "tag_2": "csrf"}, confidence=0.3,
    )
    await runner.remember(
        "登录页面配置了速率限制",
        memory_type="observation", tags={"tag": "security", "tag_2": "ratelimit"}, confidence=0.5,
    )

    await asyncio.sleep(0.5)

    recall_resp = await runner.recall(
        "安全防护措施", max_results=10, min_confidence=0.5, include_evidence=False,
    )
    results = _extract_results(recall_resp)

    all_text = " ".join(r.get("text", "") for r in results)
    low_conf_excluded = "CSRF" not in all_text
    relevant_found = "SQL" in all_text or "速率" in all_text

    if low_conf_excluded and relevant_found:
        score = 1.0
    elif low_conf_excluded or relevant_found:
        score = 0.5
    else:
        score = 0.0

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-06 Confidence filtering",
        score,
        f"low_conf_excluded={low_conf_excluded} relevant_found={relevant_found}",
        latency_ms,
        {"low_conf_excluded": float(low_conf_excluded), "relevant_found": float(relevant_found)},
    )


async def run_a07_evidence_chain(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a07")

    await runner.remember(
        "Q3延迟降低15%",
        memory_type="fragment", tags={"tag": "performance"}, confidence=0.85,
    )
    await runner.remember(
        "Q3吞吐量提升20%",
        memory_type="fragment", tags={"tag": "performance"}, confidence=0.85,
    )
    await runner.remember(
        "Q3错误率下降至0.1%",
        memory_type="fragment", tags={"tag": "performance"}, confidence=0.85,
    )

    await asyncio.sleep(0.5)

    await runner.consolidate()
    await asyncio.sleep(0.5)

    recall_resp = await runner.recall(
        "Q3性能", max_results=10, include_evidence=True, evidence_depth=2,
    )
    results = _extract_results(recall_resp)

    has_evidence = False
    evidence_non_empty = False
    for res in results:
        ev = res.get("evidence", None)
        if ev is not None:
            has_evidence = True
            if isinstance(ev, list) and len(ev) > 0:
                evidence_non_empty = True
            break

    if has_evidence and evidence_non_empty:
        score = 1.0
    elif has_evidence:
        score = 0.5
    else:
        score = 0.0

    evidence_depth_found = 0
    for res in results:
        ev = res.get("evidence", [])
        if isinstance(ev, list):
            evidence_depth_found = max(evidence_depth_found, len(ev))

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-07 Evidence chain expansion",
        score,
        f"has_evidence={has_evidence} evidence_depth={evidence_depth_found}",
        latency_ms,
        {"has_evidence": float(has_evidence), "evidence_non_empty": float(evidence_non_empty)},
    )


async def run_a08_private_isolation(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a08")

    await runner.remember(
        "bob的数据库密钥是sk-abc123",
        memory_type="observation", tags={"tag": "secret", "tag_2": "db"},
        confidence=0.95, visibility="private", created_by="bob",
    )
    await runner.remember(
        "公开API文档地址/wiki/api",
        memory_type="observation", tags={"tag": "public", "tag_2": "api"},
        confidence=0.9, visibility="shared", created_by="alice",
    )

    await asyncio.sleep(0.5)

    alice_recall = await runner.recall(
        "密钥", max_results=10, user_id="alice", include_evidence=False,
    )
    alice_results = _extract_results(alice_recall)
    alice_text = " ".join(r.get("text", "") for r in alice_results)
    alice_leak = "sk-abc123" in alice_text

    bob_recall = await runner.recall(
        "密钥", max_results=10, user_id="bob", include_evidence=False,
    )
    bob_results = _extract_results(bob_recall)
    bob_text = " ".join(r.get("text", "") for r in bob_results)
    bob_found = "sk-abc123" in bob_text

    if not alice_leak and bob_found:
        score = 1.0
    elif not alice_leak or bob_found:
        score = 0.5
    else:
        score = 0.0

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-08 Private memory isolation",
        score,
        f"alice_leak={alice_leak} bob_found={bob_found}",
        latency_ms,
        {"alice_leak": float(alice_leak), "bob_found": float(bob_found)},
    )


async def run_a09_token_budget(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_a09")

    for i in range(8):
        content = (
            f"TechNova系统性能监控记录第{i+1}号："
            f"在生产环境中，TechNova微服务集群持续运行超过120天无故障，"
            f"平均响应时间维持在45ms以下，并发连接数峰值达到85000，"
            f"内存使用率稳定在62%左右。"
        )
        await runner.remember(
            content,
            memory_type="observation", tags={"tag": "performance", "tag_2": "monitoring"}, confidence=0.85,
        )

    await asyncio.sleep(0.5)

    recall_resp = await runner.api.recall(
        query="memories",
        space_id=runner.space,
        max_results=10,
        include_evidence=False,
        token_budget=400,
    )
    data = recall_resp.get("data", recall_resp)
    results = data.get("results", [])

    result_count = len(results)
    total_chars = sum(len(r.get("text", "")) for r in results)
    budget = 400

    if result_count > 0 and result_count < 10:
        score = 1.0
    elif result_count > 0:
        score = 0.5
    else:
        score = 0.0

    latency_ms = (time.time() - t0) * 1000
    return r(
        "A-09 Token budget truncation",
        score,
        f"result_count={result_count} budget={budget} total_chars={total_chars}",
        latency_ms,
        {"result_count": float(result_count), "total_chars": float(total_chars)},
    )


async def main():
    runner, tmp_dir = await create_runner(SPACE)
    report = AcptReport(case_name="acpt_retrieval")

    try:
        print("=" * 70)
        print("Category A: Retrieval Effectiveness Acceptance Tests")
        print("=" * 70)

        scenarios = [
            ("A-01 Single-hop exact match", run_a01_single_hop),
            ("A-02 Semantic gap recall", run_a02_semantic_gap),
            ("A-03 Multi-hop recall chain", run_a03_multi_hop),
            ("A-04 Temporal ordering", run_a04_temporal_ordering),
            ("A-05 Cross-type recall", run_a05_cross_type),
            ("A-06 Confidence filtering", run_a06_confidence_filtering),
            ("A-07 Evidence chain expansion", run_a07_evidence_chain),
            ("A-08 Private memory isolation", run_a08_private_isolation),
            ("A-09 Token budget truncation", run_a09_token_budget),
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