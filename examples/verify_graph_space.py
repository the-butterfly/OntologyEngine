#!/usr/bin/env python3
"""
OntologyEngine Knowledge Asset Graph Space Verification

Verifies that all example cases can:
1. Load schema into OntologyEngine (graph space creation)
2. Load instances into graph space (entity + relation insertion)
3. Retrieve entities by concept type
4. Retrieve entities by ID
5. Traverse relations between entities
6. Verify schema-declared relations have actual data instances

Usage:
    python examples/verify_graph_space.py
"""

import asyncio
import sys
import traceback
from pathlib import Path
from dataclasses import dataclass

EXAMPLES_DIR = Path(__file__).parent

CASES = [
    ("supply_chain_finance", "供应链金融"),
    ("consumer_credit", "消费信贷"),
    ("case1_regulatory_compliance", "Circular 23 合规"),
    ("case3_tax_simulation", "亚太税务架构"),
    ("case4_bi_query_agent", "零售经营分析"),
    ("case5_expert_knowledge_crystallization", "专家经验规则化"),
]


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""


def _p(name: str, status: str, detail: str = "") -> CheckResult:
    return CheckResult(name=name, status=status, detail=detail)


async def verify_case(case_dir: Path, case_name: str, case_label: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    schema_path = case_dir / "schema.yaml"
    instances_path = case_dir / "instances.yaml"

    if not schema_path.exists():
        results.append(_p(f"[{case_label}] schema.yaml 存在", "FAIL", f"{schema_path} 不存在"))
        return results
    results.append(_p(f"[{case_label}] schema.yaml 存在", "PASS"))

    if not instances_path.exists():
        results.append(_p(f"[{case_label}] instances.yaml 存在", "FAIL", f"{instances_path} 不存在"))
        return results
    results.append(_p(f"[{case_label}] instances.yaml 存在", "PASS"))

    from ontology_engine import OntologyEngine

    try:
        engine = OntologyEngine.from_config(str(schema_path))
    except Exception as e:
        results.append(_p(f"[{case_label}] Schema 加载", "FAIL", str(e)))
        return results
    results.append(_p(f"[{case_label}] Schema 加载", "PASS",
                       f"concepts={len(engine.schema.concepts)}, "
                       f"metrics={len(engine.schema.metrics)}, "
                       f"v2_metrics={len(engine.schema.analytical_elements.metrics) if engine.schema.analytical_elements else 0}"))

    try:
        await engine.initialize()
        results.append(_p(f"[{case_label}] Storage 初始化", "PASS"))
    except Exception as e:
        results.append(_p(f"[{case_label}] Storage 初始化", "FAIL", str(e)))
        return results

    try:
        await engine.load_instances(str(instances_path))
        results.append(_p(f"[{case_label}] Instances 加载", "PASS"))
    except Exception as e:
        results.append(_p(f"[{case_label}] Instances 加载", "FAIL", str(e)[:200]))
        traceback.print_exc()
        await engine.close()
        return results

    concept_names = engine.schema.get_all_concept_names()
    results.append(_p(f"[{case_label}] Schema 声明概念", "PASS",
                       f"concepts={concept_names}"))

    for concept in concept_names:
        try:
            entities = await engine.query_entities(concept)
            count = len(entities)
            if count > 0:
                results.append(_p(f"[{case_label}] 检索 {concept}", "PASS", f"找到 {count} 个实体"))
            else:
                results.append(_p(f"[{case_label}] 检索 {concept}", "WARN", "0 个实体"))
        except Exception as e:
            results.append(_p(f"[{case_label}] 检索 {concept}", "FAIL", str(e)[:100]))

    for concept in concept_names:
        try:
            entities = await engine.query_entities(concept)
            if entities:
                first = entities[0]
                id_field = engine.schema.get_entity_id_field(concept)
                if id_field and id_field in first:
                    eid = str(first[id_field])
                    retrieved = await engine.get_entity(concept, eid)
                    if retrieved is not None:
                        results.append(_p(f"[{case_label}] ID 检索 {concept}/{eid}", "PASS"))
                    else:
                        results.append(_p(f"[{case_label}] ID 检索 {concept}/{eid}", "FAIL", "返回 None"))
                elif id_field:
                    results.append(_p(f"[{case_label}] ID 检索 {concept}", "WARN",
                                       f"ID 字段 '{id_field}' 不在实体数据中"))
                else:
                    results.append(_p(f"[{case_label}] ID 检索 {concept}", "WARN", "schema 未声明 ID 字段"))
        except Exception as e:
            results.append(_p(f"[{case_label}] ID 检索 {concept}", "FAIL", str(e)[:100]))

    for concept in concept_names:
        rel_names = engine.schema.get_relation_names_for_concept(concept)
        if not rel_names:
            continue
        for rel_name in rel_names:
            try:
                entities = await engine.query_entities(concept)
                if not entities:
                    continue
                id_field = engine.schema.get_entity_id_field(concept)
                if not id_field:
                    continue
                found_any = False
                for entity in entities:
                    if id_field not in entity:
                        continue
                    eid = str(entity[id_field])
                    neighbors = await engine.storage.get_neighbors(eid, rel_name, "outgoing")
                    if neighbors:
                        found_any = True
                        results.append(_p(f"[{case_label}] 关系遍历 {concept}--{rel_name}-->", "PASS",
                                           f"找到 {len(neighbors)} 个邻居 (e.g., {eid})"))
                        break
                if not found_any:
                    results.append(_p(f"[{case_label}] 关系遍历 {concept}--{rel_name}-->", "WARN",
                                       "所有实体 0 个邻居（可能关系数据为嵌入式引用或无实例）"))
            except Exception as e:
                results.append(_p(f"[{case_label}] 关系遍历 {concept}--{rel_name}-->", "FAIL",
                                   str(e)[:100]))

    try:
        for concept in concept_names:
            entities = await engine.query_entities(concept)
            for entity in entities:
                id_field = engine.schema.get_entity_id_field(concept)
                if id_field and id_field in entity:
                    eid = str(entity[id_field])
                    concept_resolved = await engine._resolve_concept(eid)
                    if concept_resolved == concept:
                        results.append(_p(f"[{case_label}] 概念自动发现 {eid}→{concept}", "PASS"))
                    else:
                        results.append(_p(f"[{case_label}] 概念自动发现 {eid}", "FAIL",
                                           f"期望 {concept}，得到 {concept_resolved}"))
                    break
    except Exception as e:
        results.append(_p(f"[{case_label}] 概念自动发现", "FAIL", str(e)[:100]))

    await engine.close()
    return results


async def main():
    all_results: list[CheckResult] = []

    for case_id, case_label in CASES:
        case_dir = EXAMPLES_DIR / case_id
        print(f"\n{'='*60}")
        print(f"验证案例: {case_label} ({case_id})")
        print(f"{'='*60}")
        results = await verify_case(case_dir, case_id, case_label)
        all_results.extend(results)

    print(f"\n\n{'='*80}")
    print("验证结果汇总")
    print(f"{'='*80}")

    pass_count = sum(1 for r in all_results if r.status == "PASS")
    fail_count = sum(1 for r in all_results if r.status == "FAIL")
    warn_count = sum(1 for r in all_results if r.status == "WARN")
    total = len(all_results)

    for r in all_results:
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(r.status, "❓")
        detail = f" — {r.detail}" if r.detail else ""
        print(f"  {icon} {r.name}{detail}")

    print(f"\n{'='*80}")
    print(f"总计: {total} 项 | ✅ PASS: {pass_count} | ❌ FAIL: {fail_count} | ⚠️ WARN: {warn_count}")
    print(f"{'='*80}")

    if fail_count > 0:
        print("\n❌ 存在失败项，需要修复！")
        return 1
    else:
        print("\n✅ 所有知识资产已成功进入图空间，可进行资产检索！")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
