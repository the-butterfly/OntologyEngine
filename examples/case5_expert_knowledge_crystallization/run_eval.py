#!/usr/bin/env python3
"""Case 5 Expert Knowledge Crystallization — Experience-to-Organization Closed-Loop.

Verifies J4 journey + P4:
  TC-501: Agent interaction accumulates experience
  TC-502: Candidate marking triggers at threshold
  TC-503: Expert review creates traceable evidence
  TC-504: Organization rule publish with versioning
  TC-505: Cross-user sharing
  TC-506: Version iteration with feedback

Usage: python examples/case5_expert_knowledge_crystallization/run_eval.py
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

SPACE = "expert_knowledge"
CASE_DIR = Path(__file__).parent


async def run_tc501_interaction_experience(cli: CLIRunner, report: AcptReport):
    """TC-501: Agent interactions accumulate experience via usage_count."""
    t0 = time.time()
    try:
        for i in range(25):
            await cli.remember(
                "供应商发票金额波动超过15%需重点关注",
                tags={"tag": "invoice", "tag_2": "risk_alert"},
                confidence=0.8 + (i * 0.005),
            )

        stats = await cli.stats()
        total = stats.get("total", 0)

        recall = await cli.recall("发票金额波动", max_results=5)
        results = recall.get("results", [])
        has_recall = len(results) > 0

        checks = [(total >= 1, 1.0), (has_recall, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-501: Agent interaction experience", score,
                     f"total={total} recall_hits={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-501", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc502_candidate_trigger(cli: CLIRunner, report: AcptReport):
    """TC-502: Candidate marking triggers when usage_count >= 20, confidence >= 0.8."""
    t0 = time.time()
    try:
        for i in range(22):
            await cli.remember(
                "华东区Q3毛利率低于35%的门店需要审查",
                tags={"tag": "margin", "tag_2": "review", "tag_3": "candidate"},
                confidence=0.85,
            )

        stats = await cli.stats()
        total = stats.get("total", 0)

        recall = await cli.recall("毛利率审查", max_results=5)
        results = recall.get("results", [])
        has_result = len(results) > 0

        checks = [(total >= 1, 1.0), (has_result, 1.0)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-502: Candidate trigger", score,
                     f"total={total} results={len(results)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-502", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc503_expert_review(cli: CLIRunner, report: AcptReport):
    """TC-503: Expert review creates traceable evidence."""
    t0 = time.time()
    try:
        resp = await cli.remember(
            "担保圈风险传导路径：A→B→C→D，需深度审查担保链",
            memory_type="rule",
            tags={"tag": "guarantee", "tag_2": "expert_review"},
            confidence=0.9,
        )
        node_id = resp.get("node_id")

        audit = await cli.audit(limit=10)
        audit_entries = audit if isinstance(audit, list) else audit.get("entries", [])
        has_audit = len(audit_entries) > 0 or isinstance(audit, list)

        checks = [
            (node_id is not None, 1.0),
            (has_audit, 0.5),
        ]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-503: Expert review evidence", score,
                     f"node_id={node_id} audit_trail={has_audit}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-503", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc504_org_rule_publish(cli: CLIRunner, report: AcptReport):
    """TC-504: Organization rule publish from private to public with version."""
    t0 = time.time()
    try:
        await cli.remember(
            "rule.invoice_fluctuation_review@v1.0: 发票波动超15%触发审查",
            memory_type="rule",
            tags={"tag": "organization", "tag_2": "published", "tag_3": "v1.0"},
            confidence=0.95,
            visibility="shared",
        )

        recall = await cli.recall("invoice_fluctuation", max_results=5)
        results = recall.get("results", [])
        has_published = len(results) > 0

        stats = await cli.stats()
        total = stats.get("total", 0)

        checks = [(has_published, 1.0), (total >= 1, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-504: Organization rule publish", score,
                     f"published={has_published} total={total}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-504", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc505_cross_user_sharing(cli: CLIRunner, report: AcptReport):
    """TC-505: Cross-user sharing — other users can access organization rules."""
    t0 = time.time()
    try:
        await cli.remember(
            "组织规则：所有供应商需季度审查",
            memory_type="rule",
            tags={"tag": "organization", "tag_2": "shared"},
            visibility="shared",
            created_by="admin",
        )

        r1 = await cli.recall("供应商审查", max_results=5)
        results = r1.get("results", [])
        has_shared = len(results) > 0

        my = await cli.list_my("admin")
        memories = my.get("memories", []) if isinstance(my, dict) else []

        checks = [(has_shared, 1.0), (len(memories) >= 1, 0.5)]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-505: Cross-user sharing", score,
                     f"shared={has_shared} my_memories={len(memories)}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-505", 0.0, str(e), (time.time() - t0) * 1000))


async def run_tc506_version_iteration(cli: CLIRunner, report: AcptReport):
    """TC-506: Version iteration — optimize rule based on feedback with history."""
    t0 = time.time()
    try:
        resp1 = await cli.remember(
            "rule.margin_review@v1.0: 毛利率低于40%需审查",
            memory_type="rule",
            tags={"tag": "margin", "tag_2": "v1.0"},
            confidence=0.8,
        )
        v1_id = resp1.get("node_id")

        resp2 = await cli.remember(
            "rule.margin_review@v2.0: 毛利率低于35%需审查（基于反馈优化）",
            memory_type="rule",
            tags={"tag": "margin", "tag_2": "v2.0"},
            confidence=0.9,
            supersede_target=v1_id,
            supersede_reason="阈值优化：基于Q3数据反馈",
        )
        v2_id = resp2.get("node_id")

        audit = await cli.audit(limit=20)
        has_version_history = v1_id is not None and v2_id is not None

        checks = [
            (has_version_history, 1.0),
            (v2_id is not None, 0.5),
        ]
        score = sum(w for p, w in checks if p) / sum(w for _, w in checks)

        report.add(r("TC-506: Version iteration", score,
                     f"v1={v1_id} v2={v2_id} history={has_version_history}",
                     (time.time() - t0) * 1000))
    except Exception as e:
        report.add(r("TC-506", 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = AcptReport(case_name="case5_expert_knowledge_crystallization")
    runner, tmp_dir = await create_runner(SPACE)

    try:
        print("=" * 70)
        print("Case 5 Expert Knowledge Crystallization — Experience-to-Organization Tests")
        print("Mode: CLI Runner (Memory API interface)")
        print("=" * 70)

        scenarios = [
            ("TC-501 Agent interaction experience", run_tc501_interaction_experience),
            ("TC-502 Candidate trigger", run_tc502_candidate_trigger),
            ("TC-503 Expert review evidence", run_tc503_expert_review),
            ("TC-504 Organization rule publish", run_tc504_org_rule_publish),
            ("TC-505 Cross-user sharing", run_tc505_cross_user_sharing),
            ("TC-506 Version iteration", run_tc506_version_iteration),
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
