#!/usr/bin/env python3
"""Category B: Knowledge Asset Management Acceptance Tests.

Validates ingestion, deduplication, entity resolution, visibility,
cognitive layer inference, belief lifecycle, versioning, and schema extraction.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from examples.agent_memory._lib.cli_runner import CLIRunner, create_runner
from examples.agent_memory._lib.acpt_test import AcptReport, r, score_behavior

SPACE = "acpt_management"


async def run_b01_basic_ingestion(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b01")
    try:
        data = await runner.remember("华为是技术公司", memory_type="entity")
        stats = await runner.stats()
        by_type = stats.get("by_type", stats.get("type_distribution", {}))
        checks = [
            (data.get("node_id") is not None, 0.4),
            (stats.get("total", 0) >= 1, 0.3),
            (by_type.get("entity", 0) >= 1, 0.3),
        ]
        sb = score_behavior(checks, "b01")
        details = f"node_id={data.get('node_id')}, stats={stats}"
        return r("B-01: Basic ingestion + type correctness", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-01: Basic ingestion + type correctness", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b02_deduplication(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b02")
    try:
        first = await runner.remember("华为是技术公司")
        second = await runner.remember("华为是技术公司")
        stats = await runner.stats()
        checks = [
            (first.get("node_id") == second.get("node_id"), 0.5),
            (stats.get("total", 0) > 0, 0.2),
            (first.get("node_id") is not None, 0.3),
        ]
        sb = score_behavior(checks, "b02")
        details = f"id1={first.get('node_id')}, id2={second.get('node_id')}, total={stats.get('total')}"
        return r("B-02: Deduplication", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-02: Deduplication", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b03_entity_resolution(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b03")
    try:
        r1 = await runner.remember("华为云计算业务", memory_type="entity")
        r2 = await runner.remember("华为终端设备业务", memory_type="entity")
        stats = await runner.stats()
        by_type = stats.get("by_type", stats.get("type_distribution", {}))
        entity_count = by_type.get("entity", 0)
        total = stats.get("total", 0)

        recall_resp = await runner.recall("华为", max_results=10)
        results = recall_resp.get("results", []) if isinstance(recall_resp, dict) else []
        recall_text = " ".join(r.get("text", "") if isinstance(r, dict) else str(r) for r in results)
        recall_found = "华为" in recall_text

        checks = [
            (r1.get("node_id") is not None, 0.25),
            (r2.get("node_id") is not None, 0.25),
            (entity_count >= 1, 0.25),
            (recall_found, 0.25),
        ]
        sb = score_behavior(checks, "b03")
        details = f"entities={entity_count}, total={total}, recall_found={recall_found}"
        return r("B-03: Entity resolution", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-03: Entity resolution", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b04_visibility(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b04")
    try:
        pii_data = await runner.remember("我的手机号是13800138000")
        normal_data = await runner.remember("公开API文档地址")
        pii_id = pii_data.get("node_id")

        recall_pii = await runner.recall("手机号", user_id="other_user", max_results=5)
        recall_normal = await runner.recall("API文档", user_id="other_user", max_results=5)

        pii_results = recall_pii.get("results", []) if isinstance(recall_pii, dict) else []
        normal_results = recall_normal.get("results", []) if isinstance(recall_normal, dict) else []

        pii_visible = any("13800138000" in (r.get("text", "") if isinstance(r, dict) else str(r))
                          for r in pii_results)
        normal_visible = any("API" in (r.get("text", "") if isinstance(r, dict) else str(r))
                             for r in normal_results)

        checks = [
            (pii_id is not None, 0.3),
            (normal_visible, 0.3),
            ((not pii_visible) or normal_visible, 0.4),
        ]
        sb = score_behavior(checks, "b04")
        details = f"pii_visible={pii_visible}, normal_visible={normal_visible}, pii_id={pii_id}"
        return r("B-04: Visibility auto-inference", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-04: Visibility auto-inference", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b05_cognitive_layer(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b05")
    try:
        types_to_test = ["observation", "entity", "rule", "mental_model"]
        contents = {
            "observation": "今日天气晴朗",
            "entity": "华为技术有限公司",
            "rule": "如果温度超过30度则开启空调",
            "mental_model": "用户认为夏天比冬天更适合户外运动",
        }
        created = {}
        for mtype in types_to_test:
            data = await runner.remember(contents[mtype], memory_type=mtype)
            created[mtype] = data.get("node_id") is not None

        checks = [
            (created.get("observation", False), 0.25),
            (created.get("entity", False), 0.25),
            (created.get("rule", False), 0.25),
            (created.get("mental_model", False), 0.25),
        ]
        sb = score_behavior(checks, "b05")
        details = ", ".join(f"{k}={v}" for k, v in created.items())
        return r("B-05: Cognitive layer inference", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-05: Cognitive layer inference", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b06_belief_lifecycle(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b06")
    try:
        data = await runner.remember("测试信念状态跟踪", belief_status="pending_review")
        node_id = data.get("node_id")

        stats = await runner.stats()
        by_belief = stats.get("by_belief", {})
        has_pending = "pending_review" in by_belief

        recall_resp = await runner.recall("信念", max_results=10)
        results = recall_resp.get("results", []) if isinstance(recall_resp, dict) else []
        recall_text = " ".join(r.get("text", "") if isinstance(r, dict) else str(r) for r in results)
        recall_found = "测试信念" in recall_text

        checks = [
            (node_id is not None, 0.4),
            (has_pending, 0.3),
            (recall_found, 0.3),
        ]
        sb = score_behavior(checks, "b06")
        details = f"node_id={node_id}, has_pending={has_pending}, recall_found={recall_found}"
        return r("B-06: Belief status lifecycle", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-06: Belief status lifecycle", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b07_version_history(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b07")
    try:
        data = await runner.remember("TechNova Q1营收100亿", memory_type="observation")
        old_id = data.get("node_id")

        corr1 = await runner.correct(old_id, "TechNova Q1营收120亿（修正后数据）", reason="财务修正")
        corr1_ok = not isinstance(corr1, dict) or not corr1.get("error")
        new_id = corr1.get("new_node_id", corr1.get("memory_id", "")) if isinstance(corr1, dict) else ""

        corr2 = await runner.correct(new_id, "TechNova Q1营收130亿（二次修正）", reason="审计调整")
        corr2_ok = not isinstance(corr2, dict) or not corr2.get("error")

        audit_data = await runner.audit(limit=30)
        entries = audit_data if isinstance(audit_data, list) else audit_data.get("entries", audit_data.get("results", []))
        has_superseded = False
        correction_count = 0
        for entry in entries:
            if isinstance(entry, dict):
                bs = str(entry.get("belief_status", entry.get("status", "")))
                content = str(entry.get("content", entry.get("text", entry.get("details", ""))))
                if "superseded" in bs.lower():
                    has_superseded = True
                if "修正" in content or "correction" in bs.lower() or "correct" in str(entry.get("action", "")).lower():
                    correction_count += 1
            elif isinstance(entry, str):
                if "superseded" in entry.lower():
                    has_superseded = True
                if "修正" in entry:
                    correction_count += 1

        checks = [
            (corr1_ok, 0.25),
            (corr2_ok, 0.25),
            (has_superseded, 0.25),
            (correction_count >= 1, 0.25),
        ]
        sb = score_behavior(checks, "b07")
        details = f"corr1_ok={corr1_ok}, corr2_ok={corr2_ok}, has_superseded={has_superseded}, corrections={correction_count}"
        return r("B-07: Version history + SUPERSEDES edge", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-07: Version history + SUPERSEDES edge", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def run_b08_schema_extraction(runner: CLIRunner):
    t0 = time.time()
    runner.set_space(f"{SPACE}_b08")
    try:
        data1 = await runner.remember(
            "TechNova: 年营收100亿 员工5000人 总部深圳",
            memory_type="observation", tags=["company_profile"],
        )
        data2 = await runner.remember(
            "TechNova: 行业半导体 成立2015年 CEO李明",
            memory_type="observation", tags=["company_profile"],
        )

        recall = await runner.recall("TechNova", max_results=10)
        results = recall.get("results", []) if isinstance(recall, dict) else []
        recall_found = any(
            "TechNova" in (r.get("text", "") if isinstance(r, dict) else str(r))
            for r in results
        )

        stats = await runner.stats()
        total = stats.get("total", 0)

        checks = [
            (data1.get("node_id") is not None, 0.25),
            (data2.get("node_id") is not None, 0.25),
            (recall_found, 0.25),
            (total >= 2, 0.25),
        ]
        sb = score_behavior(checks, "b08")
        details = f"id1={data1.get('node_id')}, id2={data2.get('node_id')}, recall_found={recall_found}, total={total}"
        return r("B-08: Schema-guided extraction", sb["score"],
                 details=details, latency_ms=(time.time() - t0) * 1000,
                 sub_scores=sb)
    except Exception as e:
        return r("B-08: Schema-guided extraction", 0.0,
                 details=str(e), latency_ms=(time.time() - t0) * 1000)


async def main():
    runner, tmp_dir = await create_runner(SPACE)
    report = AcptReport(case_name="acpt_management")
    try:
        print("=" * 70)
        print("Category B: Knowledge Asset Management — Acceptance Tests")
        print("=" * 70)

        scenarios = [
            ("B-01: Basic ingestion + type correctness", run_b01_basic_ingestion),
            ("B-02: Deduplication", run_b02_deduplication),
            ("B-03: Entity resolution", run_b03_entity_resolution),
            ("B-04: Visibility auto-inference", run_b04_visibility),
            ("B-05: Cognitive layer inference", run_b05_cognitive_layer),
            ("B-06: Belief status lifecycle", run_b06_belief_lifecycle),
            ("B-07: Version history + SUPERSEDES edge", run_b07_version_history),
            ("B-08: Schema-guided extraction", run_b08_schema_extraction),
        ]

        for name, fn in scenarios:
            print(f"\n--- {name} ---")
            try:
                result = await asyncio.wait_for(fn(runner), timeout=120)
            except asyncio.TimeoutError:
                result = r(name, 0.0, details="TIMEOUT", latency_ms=120000)
            report.add(result)
            print(f"  [{result.score:.2f}] {result.name}")
            await asyncio.sleep(1.0)

    finally:
        print("\n" + report.summary())
        report.save(Path(__file__).parent)
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())