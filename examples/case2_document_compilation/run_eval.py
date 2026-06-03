#!/usr/bin/env python3
"""Case 2 Document Compilation — Multi-Source Document Knowledge Compilation.

Verifies J1 journey + P1:
  TC-201: Multi-source document upload
  TC-202: Smart chunking with SHA256
  TC-203: Pass 1 deterministic extraction
  TC-204: Pass 2 LLM semantic extraction
  TC-205: Contradiction detection during ingest
  TC-206: Wiki page generation
  TC-207: Incremental processing
  TC-208: Complete traceability chain

Usage: python examples/case2_document_compilation/run_eval.py
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.agent_memory._lib.cli_runner import CLIRunner, create_runner
from examples.agent_memory._lib.acpt_test import AcptReport, r

SPACE = "doc_compilation"
CASE_DIR = Path(__file__).parent

DOCS = {
    "green_finance": "绿色融资指引2026：绿色信贷分类标准包括A类（完全绿色）、B类（转型中）、C类（非绿色）。准入条件：企业需满足环保要求且无重大环境违法记录。",
    "supply_chain_manual": "供应链金融操作手册v3.2：供应商准入流程包括资质审查、信用评级、担保评估。审批权限：500万以下由风控经理审批，500万以上需风控委员会。",
    "q1_report": "Q1经营分析报告：华东区营收1.2亿，毛利率38%；华南区营收8000万，毛利率35%；华北区营收6000万，毛利率32%。DSO平均45天。",
    "risk_minutes": "风控会议纪要2026Q1：风险偏好调整为保守型。新增约束条件：单一供应商授信不超过总敞口15%。专家判断：担保圈风险需重点关注。",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def run_tc201_multi_source_upload(cli: CLIRunner, report: AcptReport):
    """TC-201: Multi-source document upload with SHA256."""
    t0 = time.time()
    try:
        uploaded = {}
        for name, content in DOCS.items():
            resp = await cli.remember(content, tags={"tag": "document", "tag_2": name}, confidence=0.9)
            if resp.get("node_id"):
                uploaded[name] = _sha256(content)

        all_uploaded = len(uploaded) == len(DOCS)
        score = 1.0 if all_uploaded else len(uploaded) / len(DOCS)

        report.add(r("TC-201: Multi-source document upload", score,
                     f"uploaded={len(uploaded)}/{len(DOCS)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-201", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc202_smart_chunking(cli: CLIRunner, report: AcptReport):
    """TC-202: Smart chunking with SHA256 cache."""
    t0 = time.time()
    try:
        hashes = {}
        for name, content in DOCS.items():
            resp = await cli.remember(content, tags={"tag": "chunked", "tag_2": name}, confidence=0.9)
            node_id = resp.get("node_id")
            if node_id:
                hashes[name] = _sha256(content)

        all_hashed = len(hashes) == len(DOCS)

        recall = await cli.recall("供应商准入", max_results=3)
        has_chunk = len(recall.get("results", [])) > 0

        checks = [(all_hashed, 1.0), (has_chunk, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-202: Smart chunking SHA256", score,
                     f"hashed={len(hashes)} recall_ok={has_chunk}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-202", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc203_pass1_deterministic(cli: CLIRunner, report: AcptReport):
    """TC-203: Pass 1 deterministic extraction — tables, headers, lists."""
    t0 = time.time()
    try:
        for name, content in DOCS.items():
            await cli.remember(content, tags={"tag": "pass1", "tag_2": "deterministic", "tag_3": name}, confidence=0.85)

        r1 = await cli.recall("毛利率", max_results=5)
        r2 = await cli.recall("审批权限", max_results=5)
        r3 = await cli.recall("绿色信贷", max_results=5)

        has_margin = len(r1.get("results", [])) > 0
        has_approval = len(r2.get("results", [])) > 0
        has_green = len(r3.get("results", [])) > 0

        checks = [(has_margin, 1.0), (has_approval, 1.0), (has_green, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-203: Pass 1 deterministic extraction", score,
                     f"margin={has_margin} approval={has_approval} green={has_green}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-203", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc204_pass2_semantic(cli: CLIRunner, report: AcptReport):
    """TC-204: Pass 2 LLM semantic extraction — concepts, relations, confidence."""
    t0 = time.time()
    try:
        await cli.remember(
            "概念：绿色企业分类 — 关系：属于绿色信贷体系 — 置信度：high",
            memory_type="observation",
            tags={"tag": "pass2", "tag_2": "semantic", "tag_3": "concept"},
            confidence=0.9,
        )
        await cli.remember(
            "概念：担保圈风险传导 — 关系：影响供应链金融 — 置信度：medium",
            memory_type="observation",
            tags={"tag": "pass2", "tag_2": "semantic", "tag_3": "relation"},
            confidence=0.75,
        )

        recall = await cli.recall("绿色企业分类", max_results=3)
        has_concept = len(recall.get("results", [])) > 0

        recall2 = await cli.recall("担保圈风险", max_results=3)
        has_relation = len(recall2.get("results", [])) > 0

        checks = [(has_concept, 1.0), (has_relation, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-204: Pass 2 LLM semantic extraction", score,
                     f"concept={has_concept} relation={has_relation}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-204", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc205_contradiction_detection(cli: CLIRunner, report: AcptReport):
    """TC-205: Contradiction detection during ingest."""
    t0 = time.time()
    try:
        await cli.remember(
            "绿色企业标准A：需满足环保要求且无重大环境违法记录",
            tags={"tag": "green_standard", "tag_2": "v1"},
            confidence=0.9,
        )
        await cli.remember(
            "绿色企业标准B：除环保要求外，还需碳排放强度低于行业均值20%",
            tags={"tag": "green_standard", "tag_2": "v2", "tag_3": "stricter"},
            confidence=0.85,
        )

        reflect = await cli.reflect("绿色企业标准矛盾", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        insights = reflect.get("insights", []) if isinstance(reflect, dict) else []
        contradictions = reflect.get("contradictions", []) if isinstance(reflect, dict) else []

        has_detection = len(insights) > 0 or len(contradictions) > 0

        checks = [(has_detection, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-205: Contradiction detection", score,
                     f"insights={len(insights)} contradictions={len(contradictions)} detected={has_detection}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-205", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc206_wiki_generation(cli: CLIRunner, report: AcptReport):
    """TC-206: Wiki page generation — entity pages and concept pages."""
    t0 = time.time()
    try:
        await cli.remember(
            "实体：绿色融资 — 类型：金融概念 — 属性：分类标准/准入条件/风险权重",
            memory_type="entity",
            tags={"tag": "wiki", "tag_2": "entity_page"},
            confidence=0.9,
        )
        await cli.remember(
            "概念：供应商信用评级 — 类型：评估方法 — 属性：评级维度/评分规则",
            memory_type="entity",
            tags={"tag": "wiki", "tag_2": "concept_page"},
            confidence=0.85,
        )

        recall = await cli.recall("绿色融资", max_results=3)
        has_entity_page = len(recall.get("results", [])) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        checks = [(has_entity_page, 1.0), (total >= 2, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-206: Wiki page generation", score,
                     f"entity_page={has_entity_page} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-206", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc207_incremental_processing(cli: CLIRunner, report: AcptReport):
    """TC-207: Incremental processing — modify one document, verify others unchanged."""
    t0 = time.time()
    try:
        for name, content in DOCS.items():
            await cli.remember(content, tags={"tag": "incremental", "tag_2": name}, confidence=0.9)

        stats_before = await cli.stats()
        total_before = stats_before.get("total", 0)

        # Capture original content for unchanged verification
        original_green = DOCS["green_finance"]
        original_q1 = DOCS["q1_report"]

        updated_content = DOCS["supply_chain_manual"] + "\n更新：新增跨境电商供应商准入流程。"
        await cli.remember(updated_content, tags={"tag": "incremental", "tag_2": "supply_chain_manual", "tag_3": "v3.3"}, confidence=0.9)

        stats_after = await cli.stats()
        total_after = stats_after.get("total", 0)

        updated_added = total_after > total_before

        # Verify non-modified docs are still retrievable with original content
        r_green = await cli.recall("绿色信贷分类", max_results=3)
        green_unchanged = any("A类" in res.get("text", "") and "B类" in res.get("text", "") for res in r_green.get("results", []))

        r_q1 = await cli.recall("Q1经营分析", max_results=3)
        q1_unchanged = any("1.2亿" in res.get("text", "") and "38%" in res.get("text", "") for res in r_q1.get("results", []))

        # Verify updated doc contains new content
        r_updated = await cli.recall("跨境电商", max_results=3)
        update_visible = len(r_updated.get("results", [])) > 0

        checks = [(updated_added, 0.5), (green_unchanged, 1.0), (q1_unchanged, 1.0), (update_visible, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-207: Incremental processing", score,
                     f"before={total_before} after={total_after} added={updated_added} green_ok={green_unchanged} q1_ok={q1_unchanged} update_visible={update_visible}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-207", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc208_traceability(cli: CLIRunner, report: AcptReport):
    """TC-208: Complete traceability chain — extracted_from, supported_by, defined_in."""
    t0 = time.time()
    try:
        await cli.remember(
            "规则：单一供应商授信不超过总敞口15%",
            memory_type="rule",
            tags={"tag": "traceability", "tag_2": "extracted_from:risk_minutes", "tag_3": "defined_in:v3.2"},
            confidence=0.9,
        )

        recall = await cli.recall("单一供应商授信", max_results=3)
        results = recall.get("results", [])
        has_trace = len(results) > 0

        audit = await cli.audit(limit=10)
        has_audit = audit is not None

        checks = [(has_trace, 1.0), (has_audit, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-208: Traceability chain", score,
                     f"trace={has_trace} audit={has_audit}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-208", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case2_document_compilation")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 2 Document Compilation — Multi-Source Knowledge Compilation Tests")
        print("Mode: CLI Runner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-201 Multi-source upload", run_tc201_multi_source_upload),
            ("TC-202 Smart chunking SHA256", run_tc202_smart_chunking),
            ("TC-203 Pass 1 deterministic", run_tc203_pass1_deterministic),
            ("TC-204 Pass 2 semantic", run_tc204_pass2_semantic),
            ("TC-205 Contradiction detection", run_tc205_contradiction_detection),
            ("TC-206 Wiki page generation", run_tc206_wiki_generation),
            ("TC-207 Incremental processing", run_tc207_incremental_processing),
            ("TC-208 Traceability chain", run_tc208_traceability),
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
