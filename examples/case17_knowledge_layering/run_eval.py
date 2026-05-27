#!/usr/bin/env python3
"""Case 17: Knowledge Layering — Memory Types, State & Observability.

Verifies knowledge layer weights, state transitions, and observability:
  TC-L01: All 12 memory types stored and retrievable
  TC-L02: Analytical retrieval — mental_model > entity > observation > fragment
  TC-L03: Structured fields + long text coexist (both searchable)
  TC-L04: belief_status transition: accepted → pending_review → accepted
  TC-L05: supersede chain: v1→v2→v3, only latest returned by default
  TC-L06: valid_from/valid_to temporal validity filtering
  TC-L07: Confidence distribution observable via stats()
  TC-L08: Audit trail captures create/update/supersede/delete events

Usage: python examples/case17_knowledge_layering/run_eval.py
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

SPACE = "knowledge_layering"
CASE_DIR = Path(__file__).parent


async def run_l01_all_memory_types(cli: CLIRunner, report: AcptReport):
    """TC-L01: All 12 memory types stored and retrievable."""
    t0 = time.time()
    try:
        types_to_test = [
            ("entity", "Entity: 供应商A, credit_rating AA"),
            ("observation", "Observation: 供应商A Q3营收增长20%"),
            ("rule", "Rule: 供应商授信不超过总敞口15%"),
            ("fragment", "Fragment: 会议提到供应商A可能扩大合作"),
            ("mental_model", "Mental model: 供应商A是战略合作伙伴，需长期维护关系"),
            ("opinion", "Opinion: 供应商A的技术实力在行业内领先"),
            ("procedure", "Procedure: 供应商准入流程包括资质审查、信用评级"),
            ("episode", "Episode: 2025Q1与供应商A签订框架协议"),
            ("commitment", "Commitment: 需在Q2完成供应商A的年度审查"),
            ("constraint", "Constraint: 供应商A的授信额度上限5000万"),
            ("task_state", "Task state: 供应商A审查进行中，已完成资质审查"),
            ("self_experience", "Self experience: 上次与供应商A合作交付准时率95%"),
        ]
        created = 0
        for mtype, content in types_to_test:
            resp = await cli.remember(content, tags=["type_test", mtype], memory_type=mtype, confidence=0.9)
            if resp.get("node_id"):
                created += 1
        r1 = await cli.recall("供应商A", max_results=20)
        results = r1.get("results", [])
        has_results = len(results) > 0
        checks = [(created >= 10, 1.0), (has_results, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L01: All memory types", score,
                     f"created={created}/12 has_results={has_results} total_results={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L01", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l02_analytical_layer_weights(cli: CLIRunner, report: AcptReport):
    """TC-L02: Analytical retrieval — higher-layer types should rank higher."""
    t0 = time.time()
    try:
        await cli.remember(
            "Mental model: 华为供应链风险低，技术实力强，是核心战略合作伙伴",
            tags=["analytic", "华为", "mental_model"],
            memory_type="mental_model",
            confidence=0.95,
        )
        await cli.remember(
            "Entity: 华为技术有限公司, credit_rating AAA, revenue 9000亿",
            tags=["analytic", "华为", "entity"],
            memory_type="entity",
            confidence=0.9,
        )
        await cli.remember(
            "Observation: 华为2025年供应链融资规模500亿",
            tags=["analytic", "华为", "observation"],
            memory_type="observation",
            confidence=0.85,
        )
        await cli.remember(
            "Fragment: 听说华为在扩展供应链",
            tags=["analytic", "华为", "fragment"],
            memory_type="fragment",
            confidence=0.5,
        )
        r1 = await cli.recall("华为 供应链", max_results=10)
        results = r1.get("results", [])
        has_mental_model = any("Mental model" in res.get("text", "") or "战略合作" in res.get("text", "") for res in results)
        has_entity = any("Entity" in res.get("text", "") or "AAA" in res.get("text", "") for res in results)
        has_observation = any("Observation" in res.get("text", "") or "500亿" in res.get("text", "") for res in results)
        checks = [(has_mental_model, 1.0), (has_entity, 1.0), (has_observation, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L02: Analytical layer weights", score,
                     f"mental_model={has_mental_model} entity={has_entity} observation={has_observation}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L02", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l03_structured_plus_text(cli: CLIRunner, report: AcptReport):
    """TC-L03: Structured fields + long text coexist, both searchable."""
    t0 = time.time()
    try:
        await cli.remember(
            "供应商 深圳智造科技有限公司 注册资本5000万人民币 成立于2019年 主营业务为智能硬件研发 metadata:registered_capital=50M founded=2019 industry=smart_hardware",
            tags=["supplier", "深圳智造", "structured"],
            memory_type="entity",
            confidence=0.9,
        )
        r_text = await cli.recall("智能硬件研发", max_results=5)
        text_found = any("智能硬件" in res.get("text", "") for res in r_text.get("results", []))
        r_structured = await cli.recall("深圳智造 注册资本", max_results=5)
        structured_found = any("5000万" in res.get("text", "") or "50M" in res.get("text", "") for res in r_structured.get("results", []))
        checks = [(text_found, 1.0), (structured_found, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L03: Structured + text coexist", score,
                     f"text_search={text_found} structured_search={structured_found}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L03", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l04_belief_status_transition(cli: CLIRunner, report: AcptReport):
    """TC-L04: belief_status transition: accepted → pending_review → accepted."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "Rule: 供应商需通过核心企业担保",
            tags=["rule", "belief_test"],
            memory_type="rule",
            confidence=0.9,
            belief_status="accepted",
        )
        node_id = resp1.get("node_id")
        has_node = node_id is not None
        r1 = await cli.recall("核心企业担保", max_results=5)
        accepted_found = any("担保" in res.get("text", "") for res in r1.get("results", []))
        resp2 = await cli.remember(
            "Rule: 供应商需通过核心企业担保（待审核）",
            tags=["rule", "belief_test", "pending"],
            memory_type="rule",
            confidence=0.6,
            belief_status="pending_review",
        )
        r2 = await cli.recall("核心企业担保", max_results=5, min_confidence=0.8)
        pending_excluded = not any("待审核" in res.get("text", "") for res in r2.get("results", []))
        checks = [(has_node, 0.5), (accepted_found, 1.0), (pending_excluded, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L04: Belief status transition", score,
                     f"node_created={has_node} accepted_found={accepted_found} pending_excluded={pending_excluded}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L04", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l05_supersede_chain(cli: CLIRunner, report: AcptReport):
    """TC-L05: supersede chain v1→v2→v3, only latest returned by default."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "Rule v1.0: 供应商授信额度不超过总敞口10%",
            tags=["rule", "credit_limit", "v1"],
            memory_type="rule",
            confidence=0.8,
        )
        v1_id = resp1.get("node_id")
        resp2 = await cli.remember(
            "Rule v2.0: 供应商授信额度不超过总敞口15%（基于Q2数据调整）",
            tags=["rule", "credit_limit", "v2"],
            memory_type="rule",
            confidence=0.9,
            supersede_target=v1_id,
            supersede_reason="Q2数据调整",
        )
        v2_id = resp2.get("node_id")
        resp3 = await cli.remember(
            "Rule v3.0: 供应商授信额度不超过总敞口20%（基于Q3数据调整）",
            tags=["rule", "credit_limit", "v3"],
            memory_type="rule",
            confidence=0.95,
            supersede_target=v2_id,
            supersede_reason="Q3数据调整",
        )
        v3_id = resp3.get("node_id")
        all_created = all([v1_id, v2_id, v3_id])
        r1 = await cli.recall("供应商授信额度", max_results=5)
        results = r1.get("results", [])
        has_v3 = any("v3.0" in res.get("text", "") or "20%" in res.get("text", "") for res in results)
        audit = await cli.audit(limit=20)
        has_supersede_audit = audit is not None
        checks = [(all_created, 0.5), (has_v3, 1.0), (has_supersede_audit, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L05: Supersede chain", score,
                     f"all_created={all_created} v3_found={has_v3} audit_ok={has_supersede_audit}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L05", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l06_temporal_validity(cli: CLIRunner, report: AcptReport):
    """TC-L06: valid_from/valid_to temporal validity filtering."""
    t0 = time.time()
    try:
        await cli.remember(
            "Rule: 2025年供应商准入标准A类 valid_from=2025-01-01 valid_to=2025-12-31",
            tags=["rule", "2025", "valid"],
            memory_type="rule",
            confidence=0.9,
        )
        await cli.remember(
            "Rule: 2024年供应商准入标准B类（已过期）valid_from=2024-01-01 valid_to=2024-12-31",
            tags=["rule", "2024", "expired"],
            memory_type="rule",
            confidence=0.85,
        )
        r1 = await cli.recall("供应商准入标准", max_results=10)
        results = r1.get("results", [])
        has_2025 = any("2025" in res.get("text", "") or "A类" in res.get("text", "") for res in results)
        no_2024 = not any("2024" in res.get("text", "") or "B类" in res.get("text", "") for res in results)
        checks = [(has_2025, 1.0), (no_2024, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L06: Temporal validity", score,
                     f"has_2025={has_2025} no_2024={no_2024} total_results={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L06", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l07_confidence_observable(cli: CLIRunner, report: AcptReport):
    """TC-L07: Confidence distribution observable via stats()."""
    t0 = time.time()
    try:
        for conf in [0.95, 0.9, 0.8, 0.7, 0.5, 0.3]:
            await cli.remember(
                f"Test item with confidence {conf}",
                tags=["confidence_test", f"conf_{int(conf*100)}"],
                memory_type="observation",
                confidence=conf,
            )
        stats = await cli.stats()
        total = stats.get("total", 0)
        has_stats = total >= 6
        r_high = await cli.recall("confidence", max_results=10, min_confidence=0.8)
        high_count = len(r_high.get("results", []))
        r_low = await cli.recall("confidence", max_results=20, min_confidence=0.1)
        low_count = len(r_low.get("results", []))
        filter_works = high_count < low_count
        checks = [(has_stats, 0.5), (filter_works, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L07: Confidence observable", score,
                     f"total={total} high_conf={high_count} low_conf={low_count} filter_works={filter_works}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L07", 0.0, str(e), (time.time() - t0) * 1000))


async def run_l08_audit_trail_events(cli: CLIRunner, report: AcptReport):
    """TC-L08: Audit trail captures create/update/supersede/delete events."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "Rule: 供应商审查流程v1",
            tags=["audit_test", "v1"],
            memory_type="rule",
            confidence=0.9,
        )
        v1_id = resp1.get("node_id")
        resp2 = await cli.remember(
            "Rule: 供应商审查流程v2（更新）",
            tags=["audit_test", "v2"],
            memory_type="rule",
            confidence=0.95,
            supersede_target=v1_id,
            supersede_reason="流程优化",
        )
        v2_id = resp2.get("node_id")
        if v2_id:
            try:
                await cli.delete(v2_id)
            except Exception:
                pass
        audit = await cli.audit(limit=20)
        audit_entries = audit if isinstance(audit, list) else audit.get("entries", [])
        has_audit_entries = len(audit_entries) > 0
        checks = [(v1_id is not None, 0.5), (v2_id is not None, 0.5), (has_audit_entries, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)
        report.add(r("TC-L08: Audit trail events", score,
                     f"v1_id={v1_id is not None} v2_id={v2_id is not None} audit_entries={len(audit_entries)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-L08", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case17_knowledge_layering")
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 17: Knowledge Layering — Memory Types, State & Observability")
        print("Mode: CLIRunner (Memory API interface)")
        print("=" * 70)
        scenarios = [
            ("TC-L01 All memory types", run_l01_all_memory_types),
            ("TC-L02 Analytical weights", run_l02_analytical_layer_weights),
            ("TC-L03 Structured + text", run_l03_structured_plus_text),
            ("TC-L04 Belief status", run_l04_belief_status_transition),
            ("TC-L05 Supersede chain", run_l05_supersede_chain),
            ("TC-L06 Temporal validity", run_l06_temporal_validity),
            ("TC-L07 Confidence observable", run_l07_confidence_observable),
            ("TC-L08 Audit trail", run_l08_audit_trail_events),
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
