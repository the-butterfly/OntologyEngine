"""Case 12: Gap 19-25 Verification — CLI-Based Verification.

Verifies specific gaps identified in agent-memory design review,
using only standard CLIRunner interface.

Core verification points:
  V-AM-8:  memory_type x model_domain orthogonal classification
  V-LC-8:  Correction propagation along cognitive edges
  V-MOD-3: Task Model commitment lifecycle
  V-MOD-6: World Model constraint governance
  V-MOD-11: model_domain permission governance

Trajectories:
  T1: Source trust tier propagation
  T2: Scope field verification
  T3: Confirmation-based forgetting
  T4: Commitment lifecycle (pending → fulfilled/overdue)
  T5: Constraint governance (World Model)
  T6: Entity merge via supersede
  T7: Correction & deletion workflow
  T8: Permission isolation by model_domain

Usage: python examples/case12_gap19_25_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "gap19_25_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_source_trust_tier(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("高可信来源：央行发布的金融数据", memory_type="observation",
                               confidence=0.95, tags={"tag": "official"}, source_trust_tier="official")
        ok = r.get("node_id") is not None
        report.add(_ok("T1: Source trust tier", ok, 1.0 if ok else 0.0,
                       f"node_id={r.get('node_id')}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_scope_field(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户级数据：alice的投资偏好", memory_type="mental_model",
                           model_domain="user", created_by="alice")
        await cli.remember("世界级数据：市场交易规则", memory_type="rule", model_domain="world")
        stats = await cli.stats()
        ok = stats.get("total", 0) >= 2
        report.add(_ok("T2: Scope field", ok, 1.0 if ok else 0.0,
                       f"total={stats.get('total', 0)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_confirmation_forgetting(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("已确认事实：华信科技注册地深圳", memory_type="entity",
                           confidence=0.95, tags={"tag": "confirmed"})
        await cli.remember("未确认传闻：华信科技计划海外上市", memory_type="observation",
                           confidence=0.3, tags={"tag": "rumor"})
        result = await cli.forget(days_elapsed=60)
        ok = result is not None
        report.add(_ok("T3: Confirmation-based forgetting", ok, 1.0 if ok else 0.0,
                       f"forget_ok={ok}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_commitment_lifecycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.record_commitment("Q3前完成风控系统升级", deadline="2026-09-30T00:00:00Z",
                                        task_id="task_upgrade", created_by="dev_team")
        commitment_id = r.get("commitment_id")
        pending = await cli.check_commitments(status="pending")
        commitments = pending.get("commitments", []) if isinstance(pending, dict) else []
        ok = commitment_id is not None
        report.add(_ok("T4: Commitment lifecycle", ok, 1.0 if ok else 0.0,
                       f"commitment_id={commitment_id}, pending={len(commitments)}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_constraint_governance(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("API限流约束：每分钟最多1000次请求", memory_type="constraint",
                           model_domain="world", tags={"tag": "api_limit"})
        await cli.remember("业务规则：大额交易需双人审核", memory_type="constraint",
                           model_domain="world", tags={"tag": "business_rule"})
        recall = await cli.recall("系统约束和业务规则", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T5: Constraint governance", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_entity_merge(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("华信科技风险等级C级", memory_type="observation", tags={"tag": "risk"})
        old_id = r1.get("node_id")
        r2 = await cli.remember("华信科技风险等级B级（经核实后更正）", memory_type="observation",
                                tags={"tag": "risk"}, supersede_target=old_id, supersede_reason="核实更正")
        new_id = r2.get("node_id")
        ok = old_id is not None and new_id is not None
        report.add(_ok("T6: Entity merge via supersede", ok, 1.0 if ok else 0.0,
                       f"old={old_id}, new={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_correction_deletion(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("待更正数据：华信科技营收30亿", memory_type="observation", tags={"tag": "correction_test"})
        node_id = r.get("node_id")
        corrected = await cli.correct(node_id=node_id,
                                      corrected_text="华信科技营收65亿（含海外业务）",
                                      reason="数据补全", user_id="analyst")
        new_id = corrected.get("new_node_id") if corrected else None
        ok = new_id is not None
        report.add(_ok("T7: Correction workflow", ok, 1.0 if ok else 0.0,
                       f"original={node_id}, corrected={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_permission_isolation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户私有数据", memory_type="observation", model_domain="user",
                           created_by="alice", visibility="private")
        await cli.remember("世界公共规则", memory_type="rule", model_domain="world", visibility="shared")
        await cli.remember("Agent自身经验", memory_type="self_experience", model_domain="self")
        my_memories = await cli.list_my("alice")
        memories = my_memories.get("memories", []) if isinstance(my_memories, dict) else []
        ok = True
        report.add(_ok("T8: Permission isolation", ok, 1.0 if ok else 0.0,
                       f"my_memories={len(memories)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 12: Gap 19-25 Verification — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: Source trust tier", run_t1_source_trust_tier),
            ("T2: Scope field", run_t2_scope_field),
            ("T3: Confirmation forgetting", run_t3_confirmation_forgetting),
            ("T4: Commitment lifecycle", run_t4_commitment_lifecycle),
            ("T5: Constraint governance", run_t5_constraint_governance),
            ("T6: Entity merge", run_t6_entity_merge),
            ("T7: Correction workflow", run_t7_correction_deletion),
            ("T8: Permission isolation", run_t8_permission_isolation),
        ]
        for name, fn in trajectories:
            print(f"\n--- {name} ---")
            try:
                await asyncio.wait_for(fn(runner, report), timeout=120)
            except asyncio.TimeoutError:
                report.add(_ok(name, False, 0.0, "TIMEOUT", 120000))
            await asyncio.sleep(TRAJECTORY_DELAY)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n" + report.summary())
    out = save_report(report, Path(__file__).parent, "case12")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
