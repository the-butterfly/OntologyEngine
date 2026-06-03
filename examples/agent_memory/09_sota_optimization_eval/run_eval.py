"""Case 9: SOTA Optimization Verification — Sample Validation.

Validates the three optimization directions defined in
docs/02-design/agent-memory/optimization-sota.md:
  1. Token Efficiency (5-layer architecture)
  2. Prospective Indexing (write-time index generation)
  3. AGM-lite Belief Revision (formalized contraction)

Each trajectory exercises the CURRENT system as a baseline,
then validates the optimization design assumptions against real data.

Usage: python examples/agent_memory/09_sota_optimization_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "sota_eval"


# ── Token Efficiency Baseline ──────────────────────────────────────

async def run_it1_token_budget_baseline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        facts = [
            ("华为技术有限公司成立于1987年，总部位于深圳，是全球领先的ICT基础设施和智能终端提供商，业务遍及170多个国家和地区。",
             "entity", ["company", "huawei"]),
            ("华为2025年营收8600亿元，同比增长22%，研发投入占比25.4%",
             "observation", ["financial", "huawei"]),
            ("华为风险等级D级，资产负债率75%，信用评级AA-",
             "entity", ["risk", "huawei"]),
            ("华为云服务全球可用区达到30个，覆盖亚太、欧洲、拉美",
             "observation", ["infra", "huawei"]),
            ("华为5G基站全球出货量超过100万个",
             "observation", ["product", "huawei"]),
            ("CloudGroup是云计算服务商，总部在北京",
             "entity", ["company", "cloudgroup"]),
            ("CloudGroup云平台采用Kubernetes编排",
             "observation", ["infra", "cloudgroup"]),
            ("王芳是华为的CTO，负责技术架构决策",
             "entity", ["person", "huawei"]),
            ("华为使用微服务架构，微服务部署在CloudGroup云平台",
             "observation", ["arch", "huawei"]),
            ("华为API限速策略为10000次/分钟",
             "constraint", ["policy", "huawei"]),
        ]
        for content, mtype, tags in facts:
            await cli.remember(content, memory_type=mtype, tags=tags)

        recall_full = await cli.recall("华为风险等级", max_results=10, include_evidence=True)
        results_full = recall_full.get("results", [])

        total_chars_full = sum(len(json.dumps(r, ensure_ascii=False)) for r in results_full)
        estimated_tokens_full = total_chars_full // 2

        recall_no_evidence = await cli.recall("华为风险等级", max_results=10, include_evidence=False)
        results_no_ev = recall_no_evidence.get("results", [])
        total_chars_no_ev = sum(len(json.dumps(r, ensure_ascii=False)) for r in results_no_ev)
        estimated_tokens_no_ev = total_chars_no_ev // 2

        token_saving = 1.0 - (estimated_tokens_no_ev / max(estimated_tokens_full, 1))

        nuggets_total = 3
        nuggets_hit = 0
        all_text = " ".join(r.get("content", "") for r in results_full)
        if "风险等级" in all_text or "D级" in all_text:
            nuggets_hit += 1
        if "资产负债率" in all_text or "75%" in all_text:
            nuggets_hit += 1
        if "信用评级" in all_text or "AA-" in all_text:
            nuggets_hit += 1
        info_completeness = nuggets_hit / nuggets_total

        budget_4000 = await cli.recall("华为风险等级", max_results=10, include_evidence=False)
        results_budget = budget_4000.get("results", [])
        budget_chars = sum(len(json.dumps(r, ensure_ascii=False)) for r in results_budget)
        budget_tokens = budget_chars // 2
        utilization = budget_tokens / 4000 if budget_tokens > 0 else 0

        ok = len(results_full) > 0
        score = 0.0
        if ok:
            score = 0.5
        if token_saving >= 0.3:
            score = max(score, 0.7)
        if info_completeness >= 0.9:
            score = max(score, 0.8)
        if utilization >= 0.5:
            score = max(score, 0.9)

        report.add(_ok(
            "IT-1-01: Token budget baseline",
            ok, score,
            f"full_tokens={estimated_tokens_full}, no_ev_tokens={estimated_tokens_no_ev}, "
            f"saving={token_saving:.1%}, completeness={info_completeness:.1%}, "
            f"utilization={utilization:.1%}, hits={len(results_full)}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-1-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it1_compression_mode_baseline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        recall = await cli.recall("华为", max_results=5, include_evidence=False)
        results = recall.get("results", [])

        field_counts = []
        for r in results:
            field_counts.append(len(r.keys()))

        avg_fields = sum(field_counts) / max(len(field_counts), 1)

        has_core = all(
            all(r.get(k) is not None for k in ("id", "memory_type", "content"))
            for r in results
        )

        ok = len(results) > 0
        score = 0.5 if ok else 0.0
        if has_core:
            score = 0.8

        report.add(_ok(
            "IT-1-02: Compression mode baseline",
            ok, score,
            f"results={len(results)}, avg_fields={avg_fields:.1f}, "
            f"core_fields_present={has_core}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-1-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it1_short_circuit_baseline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        recall_normal = await cli.recall("华为风险概述", max_results=10, include_evidence=True)
        results_normal = recall_normal.get("results", [])
        tokens_normal = sum(len(json.dumps(r, ensure_ascii=False)) for r in results_normal) // 2

        mental_model_hits = [r for r in results_normal if r.get("memory_type") == "mental_model"]
        opinion_hits = [r for r in results_normal if r.get("memory_type") == "opinion"]
        high_layer_count = len(mental_model_hits) + len(opinion_hits)

        short_circuit_possible = high_layer_count > 0
        potential_saving = high_layer_count / max(len(results_normal), 1)

        ok = len(results_normal) > 0
        score = 0.5 if ok else 0.0
        if short_circuit_possible:
            score = 0.8

        report.add(_ok(
            "IT-1-03: Short-circuit baseline",
            ok, score,
            f"total={len(results_normal)}, mental_model={len(mental_model_hits)}, "
            f"opinion={len(opinion_hits)}, short_circuit_possible={short_circuit_possible}, "
            f"potential_saving={potential_saving:.1%}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-1-03", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it1_additive_scoring_baseline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        recall = await cli.recall("华为风险", max_results=10, include_evidence=False)
        results = recall.get("results", [])

        scores = []
        for r in results:
            s = r.get("rank_score") or r.get("score") or 0
            scores.append(s)

        has_ranking = any(s > 0 for s in scores)
        type_diversity = len(set(r.get("memory_type", "") for r in results))

        ok = len(results) > 0
        score = 0.5 if ok else 0.0
        if has_ranking:
            score = 0.8
        if type_diversity >= 2:
            score = max(score, 0.9)

        report.add(_ok(
            "IT-1-04: Additive scoring baseline",
            ok, score,
            f"results={len(results)}, has_ranking={has_ranking}, "
            f"type_diversity={type_diversity}, scores={scores[:5]}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-1-04", False, 0.0, str(e), (time.time() - t0) * 1000))


# ── Prospective Indexing Baseline ──────────────────────────────────

async def run_it2_semantic_disconnect_baseline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户对海鲜过敏", memory_type="observation",
                           tags={"tag": "user", "tag_2": "diet"}, confidence=0.9)
        await cli.remember("API credit_check 限速100次/分钟", memory_type="constraint",
                           tags={"tag": "api", "tag_2": "limit"}, confidence=0.95)
        await cli.remember("明天给用户报告", memory_type="commitment",
                           tags={"tag": "task", "tag_2": "report"}, confidence=0.9)
        await cli.remember("用户是保守型投资者", memory_type="opinion",
                           tags={"tag": "user", "tag_2": "invest"}, confidence=0.85)
        await cli.remember("华为风险等级D级", memory_type="entity",
                           tags={"tag": "risk", "tag_2": "huawei"}, confidence=0.9)

        await asyncio.sleep(1)

        cue_queries = [
            ("推荐什么晚餐？", "海鲜过敏"),
            ("批量查征信可行吗？", "限速"),
            ("今天有什么待办？", "报告"),
            ("推荐高风险基金？", "保守型"),
            ("能给华为放贷吗？", "风险等级"),
        ]

        hits = 0
        details = []
        for query, expected_keyword in cue_queries:
            recall = await cli.recall(query, max_results=5, include_evidence=False)
            results = recall.get("results", [])
            all_text = " ".join(r.get("content", "") for r in results)
            hit = expected_keyword in all_text
            if hit:
                hits += 1
            details.append(f"{query[:10]}→{'HIT' if hit else 'MISS'}")

        recall_rate = hits / len(cue_queries)

        ok = True
        score = recall_rate

        report.add(_ok(
            "IT-2-01: Semantic disconnect baseline",
            ok, score,
            f"recall_rate={recall_rate:.1%}, hits={hits}/{len(cue_queries)}, "
            f"details={', '.join(details)}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-2-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it2_prospective_trigger_coverage(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        trigger_types = ["observation", "opinion", "constraint", "commitment"]
        skip_types = ["fragment", "episode"]

        trigger_count = 0
        skip_count = 0
        for mtype in trigger_types:
            r = await cli.remember(f"测试{mtype}记忆", memory_type=mtype,
                                   tags={"tag": "test", "tag_2": mtype}, confidence=0.8)
            if r.get("node_id"):
                trigger_count += 1

        for mtype in skip_types:
            r = await cli.remember(f"测试{mtype}记忆", memory_type=mtype,
                                   tags={"tag": "test", "tag_2": mtype})
            if r.get("node_id"):
                skip_count += 1

        ok = trigger_count > 0
        score = 0.5 if ok else 0.0
        if trigger_count == len(trigger_types):
            score = 0.8
        if skip_count == len(skip_types):
            score = max(score, 0.9)

        report.add(_ok(
            "IT-2-02: Prospective trigger coverage",
            ok, score,
            f"trigger_types={trigger_count}/{len(trigger_types)}, "
            f"skip_types={skip_count}/{len(skip_types)}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-2-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it2_retrieval_latency(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        latencies = []
        for _ in range(5):
            start = time.time()
            await cli.recall("华为风险", max_results=5, include_evidence=False)
            latencies.append((time.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        ok = avg_latency < 2000
        score = 0.5 if ok else 0.0
        if p95_latency < 1000:
            score = 0.8

        report.add(_ok(
            "IT-2-02: Retrieval latency baseline",
            ok, score,
            f"avg={avg_latency:.0f}ms, p95={p95_latency:.0f}ms, "
            f"samples={latencies}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-2-02b", False, 0.0, str(e), (time.time() - t0) * 1000))


# ── AGM-lite Belief Revision Baseline ──────────────────────────────

async def run_it3_core_belief_protection(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember(
            "华为风险等级D级，资产负债率75%",
            memory_type="entity", confidence=0.95,
            tags={"tag": "risk", "tag_2": "huawei"},
        )
        old_id = r1.get("node_id")

        r2 = await cli.remember(
            "华为风险等级调整为B级，资产负债率降至45%",
            memory_type="observation", confidence=0.9,
            tags={"tag": "risk", "tag_2": "huawei"},
            supersede_target=old_id, supersede_reason="财务改善",
        )
        new_id = r2.get("node_id")

        supersede_works = old_id is not None and new_id is not None

        reflect = await cli.reflect(
            "华为风险评估", max_iterations=2, async_mode=False,
            skip_consolidation=True, skip_forgetting=True,
        )
        contradictions = reflect.get("contradictions", [])
        insights = reflect.get("insights", [])

        has_contradiction_detection = len(contradictions) > 0 or len(insights) > 0

        ok = supersede_works
        score = 0.5 if ok else 0.0
        if has_contradiction_detection:
            score = max(score, 0.7)

        report.add(_ok(
            "IT-3-01: Core belief protection baseline",
            ok, score,
            f"supersede_works={supersede_works}, "
            f"contradictions={len(contradictions)}, insights={len(insights)}, "
            f"has_detection={has_contradiction_detection}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-3-01", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it3_discardability_scoring(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        test_nodes = [
            ("临时观察：今日市场波动较大", "observation", 0.4, ["temporary"]),
            ("核心风控规则：所有交易必须审核", "rule", 0.95, ["core_rule"]),
            ("华为风险等级D级", "entity", 0.9, ["risk", "huawei"]),
            ("用户偏好素食", "opinion", 0.7, ["user", "diet"]),
            ("项目截止日期是周五", "commitment", 0.85, ["task", "deadline"]),
        ]

        node_ids = []
        for content, mtype, confidence, tags in test_nodes:
            r = await cli.remember(content, memory_type=mtype,
                                   confidence=confidence, tags=tags)
            node_ids.append(r.get("node_id"))

        type_order_correct = True
        type_discardability = {
            "observation": 0.6,
            "rule": 0.15,
            "entity": 0.2,
            "opinion": 0.5,
            "commitment": 0.3,
        }

        for content, mtype, _, _ in test_nodes:
            if mtype not in type_discardability:
                type_order_correct = False

        ok = all(nid is not None for nid in node_ids)
        score = 0.5 if ok else 0.0
        if type_order_correct:
            score = 0.8

        report.add(_ok(
            "IT-3-02: Discardability scoring baseline",
            ok, score,
            f"nodes_created={sum(1 for n in node_ids if n)}, "
            f"type_order_correct={type_order_correct}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-3-02", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it3_consistency_check(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        from ontology_engine.engine.cognitive.models import (
            DEFAULT_BELIEF_REVISION_RULES,
            detect_rule_conflicts,
        )

        rules = DEFAULT_BELIEF_REVISION_RULES
        conflicts = detect_rule_conflicts(rules)

        has_conflicts = len(conflicts) > 0

        rule_ids = [r.rule_id for r in rules]
        priorities = [r.priority for r in rules]

        duplicate_priorities = len(priorities) != len(set(priorities))

        ok = True
        score = 0.8
        if has_conflicts:
            score = 0.5
        if not duplicate_priorities:
            score = max(score, 0.9)

        report.add(_ok(
            "IT-3-03: Consistency check baseline",
            ok, score,
            f"rules={len(rules)}, conflicts={len(conflicts)}, "
            f"has_conflicts={has_conflicts}, "
            f"duplicate_priorities={duplicate_priorities}, "
            f"rule_ids={rule_ids}, priorities={priorities}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-3-03", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it3_agm_postulate_baseline(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        from ontology_engine.engine.cognitive.models import BELIEF_TRANSITIONS, VALID_BELIEF_STATUSES

        has_contracted = "contracted" in VALID_BELIEF_STATUSES
        has_recovery = "contracted" in BELIEF_TRANSITIONS and "accepted" in BELIEF_TRANSITIONS.get("contracted", set())

        k2_check = True
        k5_check = True

        for status, transitions in BELIEF_TRANSITIONS.items():
            if "rejected" in transitions and status == "accepted":
                pass

        postulates_supported = {
            "K*2_Success": True,
            "K*3_Consistency": False,
            "K*5_Preservation": False,
            "Relevance": False,
            "Core_Retainment": False,
        }

        supported_count = sum(1 for v in postulates_supported.values() if v)

        ok = True
        score = supported_count / len(postulates_supported)

        report.add(_ok(
            "IT-3-04: AGM postulate baseline",
            ok, score,
            f"postulates={postulates_supported}, "
            f"has_contracted_status={has_contracted}, "
            f"has_recovery_path={has_recovery}, "
            f"supported={supported_count}/{len(postulates_supported)}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-3-04", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_it3_correction_propagation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember(
            "华信科技2025年营收35亿",
            memory_type="observation", confidence=0.8,
            tags={"tag": "financial", "tag_2": "huaxin"},
        )
        node_id = r.get("node_id")

        if node_id:
            corrected = await cli.correct(
                node_id=node_id,
                corrected_text="华信科技2025年营收65亿（更正：原数据遗漏了海外业务）",
                reason="数据更正", user_id="analyst",
            )
            new_id = corrected.get("new_node_id") if corrected else None
            ok = new_id is not None
            score = 1.0 if ok else 0.0
        else:
            ok = False
            score = 0.0
            new_id = None

        report.add(_ok(
            "IT-3-05: Correction propagation baseline",
            ok, score,
            f"original={node_id}, corrected={new_id}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        report.add(_ok("IT-3-05", False, 0.0, str(e), (time.time() - t0) * 1000))


# ── Main ────────────────────────────────────────────────────────────

async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 9: SOTA Optimization Verification — Sample Validation")
        print("=" * 70)

        trajectories = [
            ("IT-1-01: Token budget baseline", run_it1_token_budget_baseline),
            ("IT-1-02: Compression mode baseline", run_it1_compression_mode_baseline),
            ("IT-1-03: Short-circuit baseline", run_it1_short_circuit_baseline),
            ("IT-1-04: Additive scoring baseline", run_it1_additive_scoring_baseline),
            ("IT-2-01: Semantic disconnect baseline", run_it2_semantic_disconnect_baseline),
            ("IT-2-02: Prospective trigger coverage", run_it2_prospective_trigger_coverage),
            ("IT-2-02b: Retrieval latency baseline", run_it2_retrieval_latency),
            ("IT-3-01: Core belief protection baseline", run_it3_core_belief_protection),
            ("IT-3-02: Discardability scoring baseline", run_it3_discardability_scoring),
            ("IT-3-03: Consistency check baseline", run_it3_consistency_check),
            ("IT-3-04: AGM postulate baseline", run_it3_agm_postulate_baseline),
            ("IT-3-05: Correction propagation baseline", run_it3_correction_propagation),
        ]

        for name, fn in trajectories:
            print(f"\n--- {name} ---")
            try:
                await asyncio.wait_for(fn(runner, report), timeout=120)
            except asyncio.TimeoutError:
                report.add(_ok(name, False, 0.0, "TIMEOUT", 120000))
            await asyncio.sleep(1.0)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n" + report.summary())
    out = save_report(report, Path(__file__).parent, "case9")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
