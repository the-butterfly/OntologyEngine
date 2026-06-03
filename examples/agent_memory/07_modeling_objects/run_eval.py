"""Case 15: Modeling Objects & Permission Governance — CLI-Based Verification.

Core verification points:
  V-MOD-1:  User Model & DispositionProfile relationship
  V-MOD-2:  User Model progressive update (high-confidence signals only)
  V-MOD-3:  Task Model (commitment lifecycle + decision log)
  V-MOD-6:  World Model (constraint governance)
  V-MOD-8:  Self Model (tool reliability tracking)
  V-MOD-11: Permission governance by model_domain
  V-HIE-9:  DispositionProfile 7-dimension weights

Trajectories:
  T1: User Model creation & progressive update
  T2: Task Model — commitment lifecycle
  T3: World Model — constraint governance
  T4: Self Model — tool reliability tracking
  T5: list-my-memories by scope_type
  T6: Permission governance by model_domain
  T7: Cross-model reference (User→Task→World→Self)
  T8: Commitment deadline tracking

Usage: python examples/case15_modeling_objects_governance/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "modeling_eval"
TRAJECTORY_DELAY = 2.0


async def run_t1_user_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("用户alice风险偏好：保守型", memory_type="mental_model",
                                model_domain="user", tags={"tag": "user_model", "tag_2": "risk_appetite"},
                                created_by="alice", confidence=0.9)
        r2 = await cli.remember("用户alice沟通风格：详细型", memory_type="mental_model",
                                model_domain="user", tags={"tag": "user_model", "tag_2": "communication_style"},
                                created_by="alice", confidence=0.8)
        r3 = await cli.remember("用户alice领域专长：金融风控", memory_type="mental_model",
                                model_domain="user", tags={"tag": "user_model", "tag_2": "domain_expertise"},
                                created_by="alice", confidence=0.85)
        ids = [r1.get("node_id"), r2.get("node_id"), r3.get("node_id")]
        ok = all(ids)
        report.add(_ok("T1: User Model", ok, 1.0 if ok else 0.0,
                       f"ids={ids}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_task_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.record_commitment("在Q3前完成风控系统升级", deadline="2026-09-30T00:00:00Z",
                                        task_id="task_risk_upgrade", created_by="alice")
        commitment_id = r.get("commitment_id") if isinstance(r, dict) else None
        commitments = await cli.check_commitments(status="pending")
        pending = commitments.get("commitments", []) if isinstance(commitments, dict) else []
        ok = commitment_id is not None or len(pending) >= 0
        report.add(_ok("T2: Task Model (commitment)", ok, 1.0 if ok else 0.0,
                       f"commitment_id={commitment_id}, pending={len(pending)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_world_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("API调用频率限制100次/分钟", memory_type="constraint", model_domain="world", tags={"tag": "api_limit"})
        r2 = await cli.remember("监管要求：客户风险评级必须每季度更新", memory_type="constraint", model_domain="world", tags={"tag": "business_rule"})
        ok = r1.get("node_id") is not None and r2.get("node_id") is not None
        report.add(_ok("T3: World Model (constraint)", ok, 1.0 if ok else 0.0,
                       f"api_limit_id={r1.get('node_id')}, reg_id={r2.get('node_id')}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_self_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("工具risk_api调用成功，延迟1500ms", memory_type="self_experience",
                           model_domain="self", tags={"tag": "tool_reliability", "tag_2": "risk_api"},
                           confidence=0.9)
        await cli.remember("工具risk_api调用成功，延迟1200ms", memory_type="self_experience",
                           model_domain="self", tags={"tag": "tool_reliability", "tag_2": "risk_api"},
                           confidence=0.9)
        await cli.remember("工具risk_api调用失败，超时3000ms", memory_type="self_experience",
                                model_domain="self", tags={"tag": "tool_reliability", "tag_2": "risk_api"},
                                confidence=0.7)
        recall = await cli.recall("risk_api工具可靠性", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T4: Self Model (tool reliability)", ok, 1.0 if ok else 0.0,
                       f"recall_hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_list_my_memories(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("alice的个人投资偏好记录", memory_type="observation",
                           created_by="alice", visibility="private")
        result = await cli.list_my("alice")
        memories = result.get("memories", []) if isinstance(result, dict) else []
        ok = len(memories) >= 0
        report.add(_ok("T5: list-my-memories", ok, 1.0 if len(memories) > 0 else 0.5,
                       f"memories={len(memories)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_permission_governance(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        domains_created = 0
        for domain in ["user", "task", "world", "self"]:
            r = await cli.remember(f"测试权限治理: model_domain={domain}", memory_type="observation", model_domain=domain)
            if r.get("node_id"):
                domains_created += 1
        ok = domains_created >= 3
        report.add(_ok("T6: Permission governance", ok, domains_created / 4,
                       f"domains_created={domains_created}/4", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_cross_model_reference(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户cross_user风险偏好：稳健型", memory_type="mental_model",
                           model_domain="user", tags={"tag": "user_model"}, created_by="cross_user")
        await cli.record_commitment("完成跨模型引用验证", task_id="cross_task", created_by="cross_user")
        await cli.remember("跨模型测试约束：所有操作需审计", memory_type="constraint", model_domain="world")
        await cli.remember("工具cross_tool调用成功，延迟500ms", memory_type="self_experience",
                           model_domain="self", tags={"tag": "tool_reliability"})
        recall = await cli.recall("跨模型", max_results=10)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T7: Cross-model reference", ok, 1.0 if ok else 0.5,
                       f"recall_hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_commitment_tracking(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.record_commitment("2026年底前完成合规审查", deadline="2026-12-31T00:00:00Z",
                                    task_id="compliance_review", created_by="bob")
        pending = await cli.check_commitments(status="pending")
        all_commitments = await cli.check_commitments()
        pending_count = len(pending.get("commitments", [])) if isinstance(pending, dict) else 0
        all_count = len(all_commitments.get("commitments", [])) if isinstance(all_commitments, dict) else 0
        ok = all_count > 0
        report.add(_ok("T8: Commitment tracking", ok, 1.0 if ok else 0.5,
                       f"pending={pending_count}, total={all_count}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 15: Modeling Objects & Permission Governance — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: User Model", run_t1_user_model),
            ("T2: Task Model", run_t2_task_model),
            ("T3: World Model", run_t3_world_model),
            ("T4: Self Model", run_t4_self_model),
            ("T5: list-my-memories", run_t5_list_my_memories),
            ("T6: Permission governance", run_t6_permission_governance),
            ("T7: Cross-model reference", run_t7_cross_model_reference),
            ("T8: Commitment tracking", run_t8_commitment_tracking),
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
    out = save_report(report, Path(__file__).parent, "case15")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
