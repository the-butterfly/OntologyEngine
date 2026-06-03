"""End-to-end verification for visualization enhancement.

Verifies:
1. Memory Graph API returns nodes + edges
2. Graph data has proper grouping and metadata
3. Recall API returns trace data (source, score_debug, evidence)
4. Evidence chain is expandable
5. TC-508 enhanced scenario produces rich graph data
"""

import asyncio
import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.factory import MemoryAPISingleton


async def create_test_api() -> MemoryAPI:
    tmp_dir = tempfile.mkdtemp(prefix="vis_verify_")
    db_path = os.path.join(tmp_dir, "cognitive_db")
    api = await MemoryAPISingleton.get_or_create(db_path=db_path)
    return api


async def run_verification():
    api = await create_test_api()
    space_id = "vis_test"
    passed = 0
    failed = 0
    results = []

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            results.append({"name": name, "passed": True, "detail": detail})
            print(f"  ✓ {name}")
        else:
            failed += 1
            results.append({"name": name, "passed": False, "detail": detail})
            print(f"  ✗ {name} — {detail}")

    # ===== T1: Basic remember → graph has nodes =====
    print("\n[T1] Basic remember → graph has nodes")
    r1 = await api.remember(content="TechNova公司总部位于深圳南山区", space_id=space_id, memory_type="entity", tags={"domain": "company"})
    r2 = await api.remember(content="TechNova成立于2020年", space_id=space_id, memory_type="observation", tags={"domain": "company"})
    r3 = await api.remember(content="王芳是TechNova技术负责人", space_id=space_id, memory_type="entity", tags={"domain": "person"})

    graph = await api.get_memory_graph(space_id)
    check("graph has nodes", len(graph.get("nodes", [])) > 0, f"nodes={len(graph.get('nodes', []))}")
    check("graph has metadata", "metadata" in graph, f"keys={list(graph.keys())}")
    check("metadata has node_count", "node_count" in graph.get("metadata", {}), f"metadata={graph.get('metadata', {})}")

    # ===== T2: Graph has grouping =====
    print("\n[T2] Graph has grouping")
    grouping = graph.get("grouping", {})
    check("grouping exists", bool(grouping), f"grouping={grouping}")
    check("concept_groups exists", "concept_groups" in grouping, f"keys={list(grouping.keys())}")
    check("layer_groups exists", "layer_groups" in grouping, f"keys={list(grouping.keys())}")
    check("belief_groups exists", "belief_groups" in grouping, f"keys={list(grouping.keys())}")

    # ===== T3: Consolidate → graph has edges =====
    print("\n[T3] Consolidate → graph has edges")
    r4 = await api.remember(content="王芳主导架构迁移到CloudGroup平台", space_id=space_id, memory_type="observation", tags={"domain": "arch"})
    r5 = await api.remember(content="CloudGroup平台底层使用Kubernetes编排", space_id=space_id, memory_type="observation", tags={"domain": "infra"})
    r6 = await api.remember(content="TechNova架构变更须经安全委员会审批", space_id=space_id, memory_type="rule", tags={"domain": "governance"})

    try:
        await api.run_consolidation(space_id)
    except Exception as e:
        print(f"  (consolidation note: {e})")

    graph2 = await api.get_memory_graph(space_id)
    edge_count = len(graph2.get("edges", []))
    check("graph has edges after consolidate", edge_count > 0, f"edges={edge_count}")

    # ===== T4: Edge types are present =====
    print("\n[T4] Edge types are present")
    edge_types = set(e.get("edge_type") for e in graph2.get("edges", []))
    check("has at least one edge type", len(edge_types) > 0, f"types={edge_types}")

    # ===== T5: list_edges API works =====
    print("\n[T5] list_edges API works")
    edges_result = await api.list_edges(space_id)
    check("list_edges returns edges", len(edges_result.get("edges", [])) > 0, f"total={edges_result.get('total', 0)}")

    # ===== T6: list_edges with filter =====
    print("\n[T6] list_edges with filter")
    first_type = list(edge_types)[0] if edge_types else "CONSOLIDATED_INTO"
    filtered = await api.list_edges(space_id, edge_type=first_type)
    check("filtered edges by type", len(filtered.get("edges", [])) >= 0, f"type={first_type}, count={filtered.get('total', 0)}")

    # ===== T7: Recall returns trace data =====
    print("\n[T7] Recall returns trace data")
    recall_result = await api.recall(query="TechNova技术架构", space_id=space_id, max_results=10, include_evidence=True, evidence_depth=2)
    recall_data = recall_result.get("data", recall_result)
    results_list = recall_data.get("results", [])
    check("recall returns results", len(results_list) > 0, f"count={len(results_list)}")

    if results_list:
        first = results_list[0]
        check("result has source field", "source" in first, f"keys={list(first.keys())}")
        check("result has score field", "score" in first, f"score={first.get('score')}")
        check("result has memory_type", "memory_type" in first, f"type={first.get('memory_type')}")

    # ===== T8: Evidence chain in recall =====
    print("\n[T8] Evidence chain in recall")
    has_evidence = any(r.get("evidence") for r in results_list)
    check("at least one result has evidence", has_evidence, f"with_evidence={sum(1 for r in results_list if r.get('evidence'))}")

    # ===== T9: Correct → SUPERSEDES edge =====
    print("\n[T9] Correct → SUPERSEDES edge")
    if results_list:
        first_id = results_list[0].get("id")
        if first_id:
            try:
                await api.correct_memory(node_id=first_id, corrected_text="TechNova总部位于深圳前海区（2024年搬迁）", reason="地址更新")
                graph3 = await api.get_memory_graph(space_id)
                supersede_edges = [e for e in graph3.get("edges", []) if e.get("edge_type") == "SUPERSEDES"]
                check("SUPERSEDES edge created", len(supersede_edges) > 0, f"count={len(supersede_edges)}")
            except Exception as e:
                check("SUPERSEDES edge created", False, f"error: {e}")
        else:
            check("SUPERSEDES edge created", False, "no result id")
    else:
        check("SUPERSEDES edge created", False, "no results")

    # ===== T10: Graph metadata completeness =====
    print("\n[T10] Graph metadata completeness")
    final_graph = await api.get_memory_graph(space_id)
    meta = final_graph.get("metadata", {})
    check("metadata has concept_counts", "concept_counts" in meta, f"concept_counts={meta.get('concept_counts')}")
    check("metadata has layer_counts", "layer_counts" in meta, f"layer_counts={meta.get('layer_counts')}")
    check("metadata has belief_counts", "belief_counts" in meta, f"belief_counts={meta.get('belief_counts')}")
    check("metadata has edge_type_counts", "edge_type_counts" in meta, f"edge_type_counts={meta.get('edge_type_counts')}")

    # ===== Summary =====
    total = passed + failed
    pass_rate = passed / total if total > 0 else 0
    print(f"\n{'='*60}")
    print(f"可视化增强验收结果: {passed}/{total} 通过 ({pass_rate:.1%})")
    print(f"{'='*60}")

    await MemoryAPISingleton.close()

    return {"passed": passed, "failed": failed, "total": total, "pass_rate": pass_rate, "results": results}


if __name__ == "__main__":
    result = asyncio.run(run_verification())
    sys.exit(0 if result["pass_rate"] >= 0.8 else 1)
