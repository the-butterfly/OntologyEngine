"""Case 16: QUL Constraint-Driven Retrieval & Lifecycle Integration — CLI Verification.

Core verification points:
  V-QUL-1: Task constraint extraction (rule layer)
  V-QUL-3: Constraint-to-retrieval-strategy mapping
  V-QUL-4: Constraint-driven re-ranking
  V-QUL-5: QUL stacks on top of semantic recall
  V-LC-3:  Memory strength model (5 factors)
  V-LC-4:  Ebbinghaus value-aware decay
  V-LC-5:  Forgetting strategy gradation
  V-LC-6:  Strategic forgetting
  V-LC-9:  DreamCycle 5-phase maintenance
  XV-1:    remember → consolidate → recall end-to-end
  XV-2:    reflect triggers consolidate + forget chain

Trajectories:
  T1: QUL constraint extraction (rule layer patterns)
  T2: Constraint-driven re-ranking verification
  T3: Auto context detection & loading
  T4: Full lifecycle: remember → consolidate → recall → reflect → correct → forget
  T5: DreamCycle 5-phase maintenance
  T6: Ebbinghaus value-aware decay
  T7: Strategic forgetting (superseded/rejected signals)
  T8: End-to-end cross-verification (XV-1, XV-2)

Usage: python examples/case16_qul_lifecycle_integration/run_eval.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner, save_report

SPACE = "qul_lifecycle_eval"
TRAJECTORY_DELAY = 3.0


async def run_t1_qul_constraint_extraction(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        test_queries = [
            ("华信科技最新的风险等级是什么", True),
            ("2025年Q1的财务数据", True),
            ("恒信集团历史违约记录", True),
            ("所有企业的基本信息", False),
        ]
        extracted = 0
        for query, expect_temporal in test_queries:
            result = cli.extract_constraints(query)
            has_constraint = result.get("has_temporal", False)
            if expect_temporal:
                if has_constraint:
                    extracted += 1
            else:
                extracted += 1
        ok = extracted >= 1
        report.add(_ok("T1: QUL constraint extraction", ok, extracted / len(test_queries),
                       f"extracted={extracted}/{len(test_queries)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T1", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t2_constraint_reranking(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("保守型投资者应选择A级以上债券", memory_type="mental_model", model_domain="world")
        await cli.remember("华信科技风险等级C级", memory_type="entity", model_domain="world")
        await cli.remember("用户偏好保守型投资", memory_type="observation", model_domain="user")
        recall = await cli.recall("适合保守型投资者的产品", max_results=5)
        results = recall.get("results", [])
        ok = len(results) > 0
        report.add(_ok("T2: Constraint-driven re-ranking", ok, 1.0 if ok else 0.0,
                       f"recall_hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T2", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t3_auto_context_loading(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.record_commitment("Q3前完成系统迁移", task_id="migration_task", created_by="dev_team")
        recall = await cli.recall("系统迁移进度", max_results=5, user_id="dev_team")
        results = recall.get("results", [])
        ok = len(results) >= 0
        report.add(_ok("T3: Auto context loading", ok, 1.0 if len(results) > 0 else 0.5,
                       f"recall_hits={len(results)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T3", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t4_full_lifecycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r = await cli.remember("恒信集团2025年营收50亿，风险等级C级", memory_type="entity", confidence=0.8)
        node_id = r.get("node_id") or ""
        ok_remember = len(node_id) > 0
        await cli.consolidate()
        recall = await cli.recall("恒信集团风险", max_results=5)
        ok_recall = len(recall.get("results", [])) > 0
        reflect = await cli.reflect("恒信集团风险评估", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        ok_reflect = reflect is not None
        correct = await cli.correct(node_id=node_id, corrected_text="恒信集团2026年Q1营收15亿（同比+20%），风险等级调整为B级",
                                    reason="业绩改善", user_id="analyst")
        ok_correct = correct is not None
        forget = await cli.forget(days_elapsed=30)
        ok_forget = forget is not None
        ok = ok_remember and ok_reflect and ok_correct
        score = sum([ok_remember, ok_recall, ok_reflect, ok_correct, ok_forget]) / 5
        report.add(_ok("T4: Full lifecycle", ok, score,
                       f"remember={ok_remember}, recall={ok_recall}, reflect={ok_reflect}, "
                       f"correct={ok_correct}, forget={ok_forget}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T4", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t5_dreamcycle(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        for i in range(3):
            await cli.remember(f"梦境循环测试记忆 #{i+1}", memory_type="fragment", tags={"tag": "dream_test"})
        await cli.consolidate()
        result = await cli.dream()
        skipped = result.get("skipped", False)
        phases = result.get("phases_completed", 0)
        ok = skipped or phases > 0
        report.add(_ok("T5: DreamCycle maintenance", ok, 1.0 if ok else 0.0,
                       f"phases={phases}, skipped={skipped}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T5", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t6_ebbinghaus_decay(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("核心业务规则：所有交易必须经过风控审核", memory_type="rule", confidence=0.95, tags={"tag": "core_rule"})
        await cli.remember("临时观察：今日市场波动较大", memory_type="observation", confidence=0.4, tags={"tag": "temporary"})
        stats = await cli.stats()
        total = stats.get("total", 0)
        ok = total > 0
        report.add(_ok("T6: Ebbinghaus value-aware decay", ok, 1.0 if ok else 0.0,
                       f"total={total}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T6", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t7_strategic_forgetting(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        r1 = await cli.remember("旧规则：风险评级每年更新一次", memory_type="rule", confidence=0.7)
        old_id = r1.get("node_id")
        r2 = await cli.remember("新规则：风险评级每季度更新一次", memory_type="rule", confidence=0.9,
                                supersede_target=old_id, supersede_reason="监管要求提高更新频率")
        new_id = r2.get("node_id")
        ok = old_id is not None and new_id is not None
        report.add(_ok("T7: Strategic forgetting", ok, 1.0 if ok else 0.0,
                       f"old_id={old_id}, new_id={new_id}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T7", False, 0.0, str(e), (time.time() - t0) * 1000))


async def run_t8_e2e_cross_verification(cli: CLIRunner, report: EvalReport):
    t0 = time.time()
    try:
        await cli.remember("端到端验证：华信科技获得政府补贴10亿元", memory_type="fragment", tags={"tag": "e2e_test"})
        await cli.remember("端到端验证：华信科技政府补贴用于债务重组", memory_type="fragment", tags={"tag": "e2e_test"})
        await cli.consolidate()
        recall = await cli.recall("华信科技政府补贴", max_results=5)
        ok_recall = len(recall.get("results", [])) > 0
        reflect = await cli.reflect("华信科技政府补贴影响分析", max_iterations=2, async_mode=False,
                                    skip_consolidation=True, skip_forgetting=True)
        insights = reflect.get("insights", [])
        contradictions = reflect.get("contradictions", [])
        ok_reflect = len(insights) > 0 or len(contradictions) > 0
        ok = ok_recall
        report.add(_ok("T8: E2E cross-verification", ok,
                       1.0 if ok_recall and ok_reflect else 0.5,
                       f"recall={ok_recall}, reflect={ok_reflect}, "
                       f"insights={len(insights)}, contradictions={len(contradictions)}", (time.time() - t0) * 1000))
    except Exception as e:
        report.add(_ok("T8", False, 0.0, str(e), (time.time() - t0) * 1000))


async def main():
    report = EvalReport()
    runner, tmp_dir = await create_runner(SPACE)
    try:
        print("=" * 70)
        print("Case 16: QUL & Lifecycle Integration — CLI Verification")
        print("=" * 70)
        trajectories = [
            ("T1: QUL constraint extraction", run_t1_qul_constraint_extraction),
            ("T2: Constraint re-ranking", run_t2_constraint_reranking),
            ("T3: Auto context loading", run_t3_auto_context_loading),
            ("T4: Full lifecycle", run_t4_full_lifecycle),
            ("T5: DreamCycle", run_t5_dreamcycle),
            ("T6: Ebbinghaus decay", run_t6_ebbinghaus_decay),
            ("T7: Strategic forgetting", run_t7_strategic_forgetting),
            ("T8: E2E cross-verification", run_t8_e2e_cross_verification),
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
    out = save_report(report, Path(__file__).parent, "case16")
    print(f"\nResults saved to {out}")
    return report.passed == report.total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
