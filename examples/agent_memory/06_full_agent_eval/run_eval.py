"""Case 13: Full Agent Memory Evaluation — CLI-Based Verification.

Comprehensive agent memory system evaluation covering all four
modeling objects and the compilation layer.

Core verification points:
  V-MOD-1:  User Model & DispositionProfile relationship
  V-MOD-2:  User Model progressive update
  V-MOD-3:  Task Model commitment lifecycle
  V-MOD-8:  Self Model tool reliability tracking
  V-LC-10:  Compilation layer (EntityPage/TopicPage)
  V-MOD-11: model_domain permission governance

Trajectories:
  T1: User Model creation & update
  T2: Task Model commitment tracking
  T3: Self Model experience recording
  T4: Compilation layer verification
  T5: Task context recall
  T6: Permission governance by model_domain
  T7: Cross-model reference
  T8: Full lifecycle with all modeling objects

Usage: python examples/case13_full_agent_memory_eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "full_agent_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_user_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户bob风险偏好：稳健型", memory_type="mental_model",
                           model_domain="user", tags={"tag": "user_model"}, created_by="bob")
        await cli.remember("用户bob沟通风格：简洁型", memory_type="mental_model",
                           model_domain="user", tags={"tag": "user_model"}, created_by="bob")
        recall = await cli.recall("bob的用户画像", max_results=5, user_id="bob")
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T1: User Model", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_task_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.record_commitment("完成数据迁移任务", deadline="2026-06-30T00:00:00Z",
                                        task_id="migration", created_by="bob")
        commitment_id = r.get("commitment_id")
        await cli.check_commitments(status="pending")
        ok = commitment_id is not None
        report.add(_ok("T2: Task Model commitment", ok, 1.0 if ok else 0.0,
                       f"commitment_id={commitment_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_self_model(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("工具data_api调用成功，延迟200ms", memory_type="self_experience",
                           model_domain="self", tags={"tag": "tool_reliability"})
        await cli.remember("工具data_api调用成功，延迟180ms", memory_type="self_experience",
                           model_domain="self", tags={"tag": "tool_reliability"})
        recall = await cli.recall("data_api工具可靠性", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T3: Self Model experience", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_compilation(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("华信科技：综合企业集团", memory_type="entity", tags={"tag": "company"})
        entity_id = r.get("node_id")
        await cli.remember("华信科技2025年营收50亿", memory_type="observation", tags={"tag": "company"})
        page = {}
        compile_error = None
        if entity_id:
            try:
                page = await cli.compile_entity(entity_id)
            except AttributeError as ae:
                compile_error = str(ae)
        summary = page.get("summary", "")
        ok = entity_id is not None and compile_error is None
        score = 1.0 if ok and len(summary) > 10 else 0.5 if entity_id else 0.0
        detail = f"entity_id={entity_id}, summary_len={len(summary)}"
        if compile_error:
            detail += f", BUG={compile_error}"
        report.add(_ok("T4: Compilation layer", ok, score, detail, (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_task_context_recall(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("迁移任务需要先备份数据库", memory_type="observation",
                           tags={"tag": "migration", "tag_2": "task_context"})
        await cli.remember("迁移目标：从MySQL迁移到PostgreSQL", memory_type="observation",
                           tags={"tag": "migration", "tag_2": "task_context"})
        recall = await cli.recall("数据迁移任务", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T5: Task context recall", ok, 1.0 if ok else 0.0,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_permission_governance(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户私有偏好", memory_type="mental_model", model_domain="user",
                           visibility="private", created_by="alice")
        await cli.remember("世界公共约束", memory_type="constraint", model_domain="world", visibility="shared")
        my = await cli.list_my("alice")
        ok = my is not None
        report.add(_ok("T6: Permission governance", ok, 1.0 if ok else 0.0,
                       f"list_my_ok={ok}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_cross_model_reference(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("用户carol偏好：积极型投资", memory_type="mental_model",
                           model_domain="user", created_by="carol")
        await cli.record_commitment("完成投资组合调整", task_id="portfolio", created_by="carol")
        await cli.remember("投资组合约束：单只股票不超过20%", memory_type="constraint", model_domain="world")
        recall = await cli.recall("carol的投资", max_results=10)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T7: Cross-model reference", ok, 1.0 if ok else 0.5,
                       f"hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_full_lifecycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("中芯科技2025年营收200亿", memory_type="entity", confidence=0.9)
        node_id = r.get("node_id") or ""
        ok_remember = len(node_id) > 0
        await cli.consolidate()
        correct = await cli.correct(node_id=node_id,
                                    corrected_text="中芯科技2026年Q1营收60亿",
                                    reason="季度更新", user_id="analyst")
        ok_correct = correct is not None
        dream = await cli.dream()
        ok_dream = dream is not None
        forget = await cli.forget(days_elapsed=30)
        ok_forget = forget is not None
        ok = ok_remember and ok_correct
        report.add(_ok("T8: Full lifecycle", ok,
                       sum([ok_remember, ok_correct, ok_dream, ok_forget]) / 4,
                       f"remember={ok_remember}, correct={ok_correct}, dream={ok_dream}, forget={ok_forget}",
                       (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 13: Full Agent Memory Evaluation — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: User Model", run_t1_user_model),
            ("T2: Task Model", run_t2_task_model),
            ("T3: Self Model", run_t3_self_model),
            ("T4: Compilation", run_t4_compilation),
            ("T5: Task context", run_t5_task_context_recall),
            ("T6: Permission", run_t6_permission_governance),
            ("T7: Cross-model", run_t7_cross_model_reference),
            ("T8: Full lifecycle", run_t8_full_lifecycle),
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
    out = save_report(report, Path(__file__).parent, "case13")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
